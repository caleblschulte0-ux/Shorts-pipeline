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


def data_is_a_finding(sc: dict) -> dict:
    """A RANKING WHOSE TAIL IS ZERO IS MISSING DATA WEARING A FINDING'S CLOTHES.

    `data_provenance` above checks that a source is real, dated and official.
    It never looks at the NUMBERS, so a dataset can carry a perfect World Bank
    citation and still say something that is not true.

    On 2026-09-09 this channel authored, rendered and titled a video
    `oil-rich-algeria-runs-on-0-fossil-fuels-at-home` from a "Top 5 countries"
    ranking that read:

        Kosovo 86.1, Albania 0.0, Algeria 0.0, Angola 0.0, Antigua 0.0

    — the first four countries ALPHABETICALLY, which is what a tie among
    ABSENT values sorts to. Algeria does not run on 0% fossil fuels; the
    publisher has no row for it. The forge's spread guard had been inverted by
    its own divide-by-zero fallback (`max(abs(tail), 1e-9)`), so the flattest
    possible data scored as the biggest finding in the catalogue and got
    picked twice in one evening.

    The forge is fixed, but the forge is not the only producer: a ChatGPT
    takeover authors datasets, and 1,116 of these files already sit on disk.
    So the READER refuses it too, and this is the half that holds.

    Deliberately narrow. It fires ONLY on a ranking, because a ranking is
    ordered by value — a 0 inside the top five means fewer than five entities
    have a value at all. A trend or a comparison reaches zero honestly all the
    time ("Moon landings since 1972: zero" is a real beat this channel has
    run), and nothing here touches those.
    """
    reasons = []
    for i, seg in enumerate(sc.get("segments", [])):
        p = _seg_data_path(seg)
        if p is None:
            continue
        try:
            d = json.loads(p.read_text())
        except Exception:  # noqa: BLE001 — data_provenance reports this
            continue
        if str(d.get("insight_type", "")).strip().lower() != "rank":
            continue
        pts = [x for x in (d.get("points") or [])
               if isinstance(x, dict) and x.get("value") is not None]
        if len(pts) < 2:
            continue
        try:
            vals = [float(x["value"]) for x in pts]
        except (TypeError, ValueError):
            continue
        zeros = [str(x.get("label", "?"))
                 for x, v in zip(pts, vals) if v == 0.0]
        if zeros and max(vals) != 0.0:
            reasons.append(
                f"seg{i} ({p.name}): a RANKING with {len(zeros)} of "
                f"{len(vals)} entries at exactly 0 "
                f"({', '.join(zeros[:4])}) — in a list ordered by value that "
                f"is missing data, not a result")
        elif vals and max(vals) == 0.0:
            reasons.append(
                f"seg{i} ({p.name}): a RANKING where every entry is 0 — "
                f"there is no finding here")
    return {"ok": not reasons, "reasons": reasons}


#: How far a spoken headline may be from anything the picture can show before
#: it stops being a rounding and becomes a number from another universe.
#:
#: `shared/beat_match` already answers "is this number derivable from this
#: beat's data", generously — a difference, a percentage change, a share, a
#: unit rescale all pass. Measured over the 957 configured beats that speak a
#: quantity, 131 fail it. Refusing all of them would hold a third of the
#: queue, and most are a writer's aside ("on a 50 thousand dollar car") rather
#: than a lie.
#:
#: But the tail is not that. 33 beats are a THOUSAND times or more away from
#: everything on screen — "About 117 billion people have ever been born" over
#: a chart whose largest value is in the thousands. A viewer hearing that
#: looks for it, finds nothing remotely like it, and stops trusting the
#: picture. That is the class this refuses; 28 of 305 stories, and every one
#: of them is genuinely broken.
#:
#: The rest are REPORTED, not refused — they are in `reasons` where the run
#: log and the repair loop can see them, and they do not fail the story.
WILD_NUMBER = 1000.0


def beat_numbers_are_on_screen(sc: dict) -> dict:
    """Does each beat SAY a number its own picture can show?

    An authoring fault, and the standing rule it breaks is this repo's oldest:
    the brain writes only the words, every number comes from the source. The
    forge checks this inside its retry loop when IT writes a story — but the
    forge is not the only author, it gives up after three attempts and ships
    anyway, and 305 stories were written before the check existed. Nothing
    downstream looked.

    The showrunner reads the result off the screen:

        "seg1 shows 2000-vs-2012 at 33% while the voice says 92% by 2023"
        "the scale's numbers never reach the narrated 3.5M / 3.0M"
                                self-checkout-cashier-jobs, 2026-09-09
    """
    from shared import beat_match as bm
    reasons, notes = [], []
    for i, seg in enumerate(sc.get("segments", [])):
        p = _seg_data_path(seg)
        say = str(seg.get("say") or "").strip()
        if p is None or not say:
            continue
        try:
            d = json.loads(p.read_text())
            vals = [float(x["value"]) for x in (d.get("points") or [])
                    if isinstance(x, dict) and x.get("value") is not None]
        except Exception:  # noqa: BLE001 — data_provenance reports this
            continue
        if not vals:
            continue
        m = bm.check(say, vals, d.get("unit", ""))
        if m["ok"]:
            continue
        head = abs(float(m.get("headline") or 0.0))
        on = [abs(v) for v in bm.sayable(vals, d.get("unit", "")) if v]
        if not on or head == 0.0:
            continue
        off = min(max(head / v, v / head) for v in on)
        line = (f"seg{i}: the line's headline number ({head:,.6g}) is "
                f"{off:,.0f}x away from anything this beat's picture can "
                f"show — say a number the picture shows")
        (reasons if off >= WILD_NUMBER else notes).append(line)
    return {"ok": not reasons, "reasons": reasons, "notes": notes}


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
        from shared.script_generator import _call_llm  # type: ignore
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
        # ONLY the two exact tokens the prompt asked for count as evidence.
        # This used to be `if verdict == REJECT ... else: llm-pass`, which
        # turned every malformed answer — `{}`, a misspelled verdict, a
        # non-string, an unrelated JSON object — into an affirmative
        # "the brain approved this" label (doctor finding ec1665fbf9fa,
        # 2026-08-15). A judge told to default to REJECT when unsure must
        # never have its garbage read as a PASS. Anything that is not an
        # exact PASS/REJECT is UNAVAILABLE evidence: the deterministic floor
        # above already passed (we only reach here when `reasons` is empty),
        # so it stands, exactly as it does when no brain is reachable — but
        # labeled honestly, never as an LLM pass.
        v = data.get("verdict") if isinstance(data, dict) else None
        v = v.strip().upper() if isinstance(v, str) else None
        if v == "REJECT":
            reasons.append("brain: " + str(data.get("reason", "weak premise")))
            verdict = {"ok": False, "reasons": reasons, "judge": "llm"}
        elif v == "PASS":
            verdict["judge"] = "llm-pass"
        else:
            verdict["judge"] = ("deterministic (llm verdict unusable: "
                                f"{str(data)[:60]!r})")
    except Exception as e:  # noqa: BLE001 — brain optional; floor already held
        verdict["judge"] = f"deterministic (llm unavailable: {str(e)[:80]})"
    return verdict


# ---------------------------------------------------------------------------
# Combined pre-render editorial verdict (no video needed)
# ---------------------------------------------------------------------------
def beats_are_distinct(sc: dict) -> dict:
    """Does this story say more than ONE thing?

    Operator, 2026-09-08: *"we would say the same thing in 3 different beats
    just show it a different way that's dumb af."* The renderer already
    prunes a restated beat (`data_learning.beat_claims`), but pruning is a
    salvage: it makes a repetitive story into its least repetitive cut. It
    cannot invent a second fact.

    HERE is where refusing is the right answer, because here there is another
    story in the queue to render instead. `driving-side-of-the-road` prunes
    all the way down to one beat — 30% of people, 76 countries, 25% of road
    miles are one claim measured three ways — and one fact is not a video.

    Offline and deterministic: it reads the same dataset files
    `data_provenance` reads, and judges nothing it cannot load. A story whose
    segments are not resolvable here is not accused of anything.
    """
    from data_learning import beat_claims
    from data_learning.insights import Insight
    from data_learning.sources.base import DataPoint, Source

    beats = []
    for seg in sc.get("segments", []):
        p = _seg_data_path(seg)
        if p is None:
            continue
        try:
            d = json.loads(p.read_text())
            pts = [DataPoint(label=str(x["label"]), value=float(x["value"]))
                   for x in d.get("points", []) if x.get("value") is not None]
        except Exception:  # noqa: BLE001 — data_provenance reports this
            continue
        if len(pts) < 2:
            continue
        src = d.get("source") or {}
        beats.append(Insight(
            kind=seg.get("insight_type", "auto"), topic=seg.get("topic", ""),
            main_insight=seg.get("say", ""), items=pts,
            source=Source(name=str(src.get("name", "")),
                          publisher=str(src.get("publisher", "")),
                          url=str(src.get("url", "")),
                          access_date=str(src.get("access_date", ""))),
            unit=d.get("unit", ""), highlight_label=str(pts[0].label)))
    if len(beats) < 2:
        return {"ok": True, "reasons": []}      # nothing to judge
    if not beat_claims.one_fact_stretched(beats):
        return {"ok": True, "reasons": []}
    kept, dropped = beat_claims.prune_restatements(beats)
    return {"ok": False, "reasons": [
        f"one fact stretched over {len(beats)} beats — "
        f"{len(dropped)} restate the first "
        f"({', '.join(str(d.topic) for d in dropped) or 'unnamed'}); "
        f"only {len(kept)} distinct claim(s)"]}


def pre_render_verdict(sc: dict, *, use_llm: bool = True) -> dict:
    """Real-data + premise checks, combined. Run BEFORE rendering so a story
    that can never publish doesn't burn a render."""
    prov = data_provenance(sc)
    # The numbers themselves, not just the citation over them.
    finding = data_is_a_finding(sc)
    # And the numbers the VOICE says, against the picture it says them over.
    spoken = beat_numbers_are_on_screen(sc)
    prem = premise_ok(sc, use_llm=use_llm)
    # A story that says one thing three times can never be a good video, and
    # finding that out costs one file read rather than a render.
    dist = beats_are_distinct(sc)
    reasons = ([f"data: {r}" for r in prov["reasons"]]
               + [f"data: {r}" for r in finding["reasons"]]
               + [f"premise: {r}" for r in prem["reasons"]]
               + [f"beats: {r}" for r in dist["reasons"]]
               + [f"beats: {r}" for r in spoken["reasons"]]
               # Reported, not refused — see `WILD_NUMBER`.
               + [f"beats (noted): {r}" for r in spoken["notes"]])
    return {"ok": (prov["ok"] and finding["ok"] and prem["ok"]
                   and dist["ok"] and spoken["ok"]),
            "reasons": reasons,
            "data_ok": prov["ok"] and finding["ok"],
            "premise_ok": prem["ok"],
            "beats_ok": dist["ok"] and spoken["ok"]}


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
