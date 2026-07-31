"""Editorial gate — the channel's fail-CLOSED publish control.

The pipeline historically failed OPEN everywhere: an infra hiccup shipped the
video anyway, an empty queue invented synthetic stories, a weak premise
rendered regardless. That optimises for uptime and volume, not taste. This
module inverts the default for the *publish* decision — a video uploads only
if it PROVES it deserves to. Anything unproven is HELD, never shipped.

Three hard rules, every one fail-closed:

  1. PUBLISH FREEZE — uploading requires an explicit opt-in
     (``PUBLISH_ENABLED=1`` in the env, or ``--publish`` on the CLI). Absent
     that, the pipeline still renders + reviews (so previews keep working) but
     never uploads. This is the in-repo kill-switch (there is no YAML cron to
     disable; the daily kickoff is an external Claude Routine, so the freeze
     has to live on the upload path itself).

  2. REAL DATA ONLY — every segment's data source must be real: officiality in
     {official, primary, secondary}, with a publisher and an access date.
     LLM-authored "illustrative" numbers can NEVER publish. (A data channel
     that authors its own numbers to keep the queue full is not a data
     channel.)

  3. PREMISE BAR — the title + hook must clear a taste bar: a genuine
     expectation-reversal and a consequential number, not a searchable noun
     phrase ("Tectonic Plates on the Move"). Weak premises die before render.

None of these raise; each returns a verdict dict ``{ok: bool, reasons: [...]}``
so the caller can log exactly why a video was held.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data_learning" / "data"

# Officiality values that count as a REAL, citable source. Everything else —
# most importantly "illustrative" — is LLM-authored and may not publish.
REAL_OFFICIALITY = {"official", "primary", "secondary"}


# ---------------------------------------------------------------------------
# Rule 1 — publish freeze
# ---------------------------------------------------------------------------
def publish_enabled(cli_flag: bool = False) -> bool:
    """True only if publishing is explicitly opted into. Default: frozen."""
    if cli_flag:
        return True
    return os.environ.get("PUBLISH_ENABLED", "").strip().lower() in (
        "1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Rule 2 — real data only
# ---------------------------------------------------------------------------
def _seg_data_path(seg: dict) -> Path | None:
    """Resolve a segment's dataset file the same way story.build does."""
    fn = (seg.get("params") or {}).get("file") or f"{seg.get('key', '')}.json"
    if not fn or fn == ".json":
        return None
    p = DATA_DIR / fn
    return p if p.exists() else None


def data_provenance(sc: dict) -> dict:
    """Check every segment's data source is real (not illustrative). Fail-closed:
    an unresolved / undated / unofficial source counts as NOT real."""
    reasons, checked = [], 0
    for i, seg in enumerate(sc.get("segments", [])):
        p = _seg_data_path(seg)
        if p is None:
            reasons.append(f"seg{i} ({seg.get('key','?')}): no resolvable dataset file")
            continue
        try:
            data = json.loads(p.read_text())
        except Exception as e:  # noqa: BLE001
            reasons.append(f"seg{i}: unreadable dataset ({e})")
            continue
        checked += 1
        src = data.get("source") or {}
        off = str(src.get("officiality", "")).strip().lower()
        if off not in REAL_OFFICIALITY:
            reasons.append(
                f"seg{i} ({p.name}): source officiality={off or 'missing'!r} "
                f"— not a real source (needs {sorted(REAL_OFFICIALITY)})")
        if not str(src.get("publisher", "")).strip():
            reasons.append(f"seg{i} ({p.name}): no publisher")
        if not str(src.get("access_date", "")).strip():
            reasons.append(f"seg{i} ({p.name}): no access_date")
    if checked == 0 and not reasons:
        reasons.append("no data segments to verify")
    return {"ok": not reasons, "reasons": reasons}


# ---------------------------------------------------------------------------
# Rule 3 — premise bar
# ---------------------------------------------------------------------------
_NUM_RE = re.compile(r"\d")
# Bare-noun "middle-school PowerPoint" title smell: a short Title Case phrase
# with no verb, number, or tension. We can't fully parse English cheaply, so we
# flag the common failure shape and let the adversarial LLM judge the rest.
_TENSION = re.compile(
    r"\b(fake|wrong|lie|lied|myth|actually|really|secret|hidden|isn't|aren't|"
    r"won't|can't|never|no one|nobody|more than|less than|fewer|worse|beat|"
    r"beats|lost|losing|winning|wins|costs?|costing|vanish|disappear|collaps|"
    r"than|but|why|how|what)\b", re.I)


def premise_ok(sc: dict, *, use_llm: bool = True) -> dict:
    """Grade the PREMISE (title + hook) before we spend a render on it.

    Deterministic hard floor (fail-closed): the hook must name a consequential
    number, and the title must not be a bare noun phrase. When a brain is
    reachable, an ADVERSARIAL judge (whose job is to find reasons to REJECT)
    has the final say; when it isn't, the deterministic floor stands.
    """
    title = (sc.get("title") or "").strip()
    hook = (sc.get("hook") or "").strip()
    reasons = []

    if not _NUM_RE.search(hook) and not _NUM_RE.search(title):
        reasons.append("no consequential number in the title or hook")
    # Bare-noun title: <=5 words, Title Case-ish, no number, no tension word.
    words = title.split()
    if (len(words) <= 5 and not _NUM_RE.search(title)
            and not _TENSION.search(title) and "?" not in title):
        reasons.append(
            f"title reads as a searchable noun phrase, not a premise: {title!r}")

    verdict = {"ok": not reasons, "reasons": reasons, "judge": "deterministic"}
    if reasons or not use_llm:
        return verdict

    # Adversarial LLM judge — argue AGAINST publishing; approve only a genuine
    # expectation-reversal. Best-effort: if the brain is down, the deterministic
    # floor above already governs.
    try:
        import sys
        if str(REPO) not in sys.path:
            sys.path.insert(0, str(REPO))
        from script_generator import _call_llm  # type: ignore
        sysmsg = (
            "You are a ruthless YouTube Shorts editor. Your ONLY job is to "
            "REJECT weak premises. A premise passes ONLY if it reverses a "
            "specific expectation the viewer already holds AND hangs on one "
            "consequential, verifiable number. A searchable noun phrase "
            "('Oldest Written Languages', 'Tectonic Plates on the Move') is an "
            "automatic REJECT. Default to REJECT when unsure.")
        user = (
            f"TITLE: {title}\nHOOK: {hook}\n\n"
            "Return STRICT JSON: {\"verdict\":\"PASS\"|\"REJECT\","
            "\"reason\":\"<one sentence>\"}.")
        raw = _call_llm(sysmsg, user)
        m = re.search(r"\{.*\}", raw, re.S)
        data = json.loads(m.group(0)) if m else {}
        if str(data.get("verdict", "")).upper() == "REJECT":
            reasons.append("brain: " + str(data.get("reason", "weak premise")))
            verdict = {"ok": False, "reasons": reasons, "judge": "llm"}
        else:
            verdict["judge"] = "llm-pass"
    except Exception as e:  # noqa: BLE001 — brain optional; floor already held
        verdict["judge"] = f"deterministic (llm unavailable: {str(e)[:80]})"
    return verdict


# ---------------------------------------------------------------------------
# Combined pre-render editorial verdict (no video needed)
# ---------------------------------------------------------------------------
def pre_render_verdict(sc: dict, *, use_llm: bool = True) -> dict:
    """Real-data + premise checks, combined. Run BEFORE rendering so a story
    that can never publish doesn't burn a render."""
    prov = data_provenance(sc)
    prem = premise_ok(sc, use_llm=use_llm)
    reasons = ([f"data: {r}" for r in prov["reasons"]]
               + [f"premise: {r}" for r in prem["reasons"]])
    return {"ok": prov["ok"] and prem["ok"], "reasons": reasons,
            "data_ok": prov["ok"], "premise_ok": prem["ok"]}


if __name__ == "__main__":
    import sys
    cfg = json.loads((REPO / "data_learning" / "niche.config.json").read_text())
    stories = {s["slug"]: s for s in cfg.get("stories", [])}
    sel = sys.argv[1:] or list(stories)
    npass = 0
    for slug in sel:
        sc = stories.get(slug)
        if not sc:
            print(f"{slug}: (unknown)")
            continue
        v = pre_render_verdict(sc, use_llm=False)
        npass += v["ok"]
        print(f"{'PASS' if v['ok'] else 'HOLD'}  {slug}")
        for r in v["reasons"][:6]:
            print(f"        - {r}")
    print(f"\n{npass}/{len(sel)} would pass the pre-render editorial gate "
          f"(data + premise, deterministic only).")
