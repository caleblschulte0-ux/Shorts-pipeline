"""judges — the production judge set, adapted to the closed-loop contract.

Each adapter turns an existing gate into a NORMALIZED verdict the repair engine
can consume:

    {"pass": bool|None, "overall_10": float|None, "personality": float|None,
     "confidence": 0..1, "findings": [{...}]}

and each finding carries what a repair actually needs:

    {"defect_code", "severity", "complaint", "recommended_fix",
     "beat"|"target"|"time_range", "frame", "confidence"}

The point is that judge feedback stops being a pass/fail boolean. ``worst_beat``,
``fix``, reject labels, pacing complaints and hook complaints all become repair
instructions with a target.

Contract: an adapter returns a dict, or None to ABSTAIN (its input genuinely
wasn't available). It may raise — the loop records that as a failure. Required
judges that abstain or fail block advancement; that is the fail-closed law.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for _p in (REPO, REPO / "scripts"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

RUBRIC = "2026-07-30"


def _read(p: Path):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _pkg(out: Path) -> Path:
    return Path(out).with_name(Path(out).stem + "_pkg")


# --------------------------------------------------------------------- taste
def taste(out: Path, ctx: dict | None = None) -> dict | None:
    """The blind vision taste verdict (TASTE_JUDGE.md), read from the package.

    This is the one judge a script cannot compute — a fresh vision agent looks
    at the evidence with no code, no intent and no previous score, and its
    object is serialized here by scripts/judge_verdict.py. Its `overall_10` is
    the professional-quality score the policy now binds on; its `worst_beat`
    and `fix` become repair tasks instead of prose in a log.
    """
    v = _read(_pkg(out) / "verdict.json")
    if v is None:
        return None                     # abstain: nobody has judged this cut yet
    findings = []
    for label in v.get("reject_labels", []) or []:
        findings.append({
            "judge": "taste",
            "defect_code": str(label).upper(),
            "severity": "blocker",      # the reject vocabulary is hard by design
            "complaint": v.get("one_line", ""),
            "recommended_fix": v.get("fix", ""),
            "target": v.get("worst_beat") or "film",
            "confidence": 0.9,
        })
    # A worst beat named without a hard label is still a real, targeted defect.
    if not findings and v.get("worst_beat"):
        findings.append({
            "judge": "taste",
            "defect_code": "WEAK_DEPICTION", "severity": "major",
            "complaint": v.get("worst_beat"), "recommended_fix": v.get("fix", ""),
            "target": v.get("worst_beat"), "confidence": 0.7,
        })
    return {
        "pass": bool(v.get("pass")),
        "overall_10": v.get("overall_10"),
        "personality": v.get("personality"),
        "card_fraction_estimate": v.get("card_fraction_estimate"),
        "one_line": v.get("one_line", ""),
        "confidence": 0.9,
        "findings": findings,
        "mp4_sha256_claimed": v.get("mp4_sha256"),
    }


# ----------------------------------------------------------------- technical
_PASS_MARK = ("✓",)
_FAIL_MARK = ("FAIL:", "✗", "ERROR:")


def _complaints(notes) -> list[str]:
    """The lines of a FAILING gate that are actually DEFECTS.

    A render_gates check returns (ok, notes), and `notes` mixes three things:
    pass markers ("✓ meta.json"), diagnostic context ("total 2684s for 167s of
    video, 41 shots", "media resolution 839s vs local render 650s"), and the
    line that says what broke ("FAIL: unexplained per-shot outliers: ...").

    Handing the whole list to the repair planner turns a stopwatch reading into
    a `severity: blocker` film defect. On the 2026-08-01 shared-air render that
    is exactly what happened: ONE real failure became FIVE blockers, four of
    them performance stats, and the healer spent five of its six repair tasks
    on tasks whose only possible outcome is "no automated repair for this code".
    The loop applied ZERO repairs and stopped after one attempt of three.

    So: drop the pass markers; if the gate explicitly marked any line as a
    failure, ONLY those are complaints. Gates that do not use the marker
    (gate_package's "meta.json missing") keep reporting every line, so nothing
    that really is a defect goes quiet.
    """
    lines = [str(w) for w in (notes or [])]
    kept = [w for w in lines if not w.lstrip().startswith(_PASS_MARK)]
    marked = [w for w in kept if w.lstrip().startswith(_FAIL_MARK)]
    return marked or kept or ["failed"]


def technical(out: Path, ctx: dict | None = None) -> dict:
    """Encode, duration, package completeness, fallback honesty, performance."""
    import render_gates
    pkg, findings = _pkg(out), []
    mp4 = Path(out)
    if not mp4.exists():
        return {"pass": False, "confidence": 1.0, "findings": [{
            "defect_code": "ARTIFACT_INTEGRITY", "severity": "blocker",
            "complaint": "no rendered mp4 on disk",
            "recommended_fix": "re-render", "target": "film", "confidence": 1.0}]}
    checks = []
    try:
        checks.append(("TECHNICAL",
                       render_gates.gate_technical(mp4, 30.0, 1800.0)))
    except Exception as e:  # noqa: BLE001
        checks.append(("TECHNICAL", (False, [f"probe failed: {str(e)[:120]}"])))
    for code, fn in (("ARTIFACT_INTEGRITY", lambda: render_gates.gate_package(mp4, pkg)),
                     ("ARTIFACT_INTEGRITY", lambda: render_gates.gate_fallbacks(pkg)),
                     ("TECHNICAL", lambda: render_gates.gate_performance(pkg))):
        try:
            checks.append((code, fn()))
        except Exception as e:  # noqa: BLE001 — a gate that cannot run is a finding
            checks.append((code, (False, [f"gate error: {str(e)[:120]}"])))
    for code, (ok, why) in checks:
        if ok:
            continue
        for w in _complaints(why):
            findings.append({
                "defect_code": code, "severity": "blocker",
                "complaint": str(w)[:300],
                "recommended_fix": "fix the technical defect and re-render",
                "target": "film", "confidence": 1.0})
    return {"pass": not findings, "confidence": 1.0, "findings": findings}


# ------------------------------------------------------------------ factual
def factual(out: Path, ctx: dict | None = None) -> dict | None:
    """Numeric-claim provenance. Abstains when the story does not opt in."""
    story = (ctx or {}).get("story") or {}
    if not story.get("require_provenance"):
        rep = _read(Path(out).with_suffix(".facts-report.json"))
        if rep is None:
            return None                 # abstain: nothing claims provenance here
    else:
        rep = _read(Path(out).with_suffix(".facts-report.json"))
        if rep is None:
            import facts_gate
            rep = facts_gate.evaluate(story.get("slug", ""))
    findings = []
    for err in (rep or {}).get("errors", []) or []:
        findings.append({
            "defect_code": "FACTUAL_UNSOURCED", "severity": "blocker",
            "complaint": str(err)[:300],
            "recommended_fix": "add a claim source, or cut the spoken number",
            "target": "film", "confidence": 1.0})
    return {"pass": bool((rep or {}).get("pass")), "confidence": 1.0,
            "findings": findings}


# ---------------------------------------------------- media context / suitability
_BRAND_TOKENS = ("bodycam", "body cam", "police", "newsreel", "broadcast",
                 "news report", "cctv", "dashcam", "livestream", "watermark")


def media_context(out: Path, ctx: dict | None = None) -> dict | None:
    """Media SUITABILITY, not just licence. The render that prompted this loop
    was licence-clean and still filled a gentle film with watermarked broadcast
    news and police bodycam footage — nothing asked whether the asset belonged.

    This is a heuristic on the credits, deliberately conservative: it raises a
    finding for review, it does not silently drop assets.
    """
    credits = _read(_pkg(out) / "credits.json")
    if credits is None:
        return None
    items = credits if isinstance(credits, list) else (
        credits.get("items") or credits.get("sources") or [])
    findings = []
    for it in items:
        title = str(it.get("title", ""))
        low = title.lower()
        hits = [t for t in _BRAND_TOKENS if t in low]
        if hits:
            findings.append({
                "defect_code": "MEDIA_UNSUITABLE", "severity": "major",
                "complaint": f"asset reads as third-party branded/press material "
                             f"({', '.join(hits)}): {title[:90]}",
                "recommended_fix": "replace with clean, unbranded footage that "
                                   "depicts the narrated subject",
                "target": title[:60] or "media", "confidence": 0.6})
    return {"pass": not findings, "confidence": 0.6, "findings": findings,
            "n_assets": len(items)}


# ------------------------------------------------------------------ captions
def captions(out: Path, ctx: dict | None = None) -> dict:
    srt = Path(out).with_suffix(".srt")
    if not srt.exists():
        return {"pass": False, "confidence": 1.0, "findings": [{
            "defect_code": "CAPTIONS", "severity": "major",
            "complaint": "no .srt captions beside the render",
            "recommended_fix": "emit captions in the publishing package",
            "target": "film", "confidence": 1.0}]}
    text = srt.read_text(errors="replace")
    longest = max((len(l) for l in text.splitlines()
                   if l.strip() and "-->" not in l and not l.strip().isdigit()),
                  default=0)
    findings = []
    if longest > 92:
        findings.append({
            "defect_code": "CAPTIONS", "severity": "minor",
            "complaint": f"a caption line runs {longest} chars — hard to read",
            "recommended_fix": "wrap caption lines under ~90 characters",
            "target": "film", "confidence": 0.8})
    return {"pass": not findings, "confidence": 0.9, "findings": findings}


# --------------------------------------------------- pacing / retention risk
def pacing_retention(out: Path, ctx: dict | None = None) -> dict | None:
    """Stale spans + dead fraction, straight from the director's own measures.
    Deep (pixel) work only runs when the caller asks for it — it is minutes,
    not milliseconds — otherwise this reads what the render already recorded."""
    import no_dull_beats as ndb
    mp4 = Path(out)
    if not mp4.exists():
        return None
    findings = []
    try:
        for a, b in ndb.novelty_check(mp4) or []:
            findings.append({
                "defect_code": "STALE_SPAN", "severity": "major",
                "complaint": f"nothing new for {b - a:.1f}s",
                "recommended_fix": "cut, or introduce a genuinely new element",
                "time_range": f"{a:.1f}-{b:.1f}s", "target": f"{a:.1f}-{b:.1f}s",
                "confidence": 0.9})
    except Exception as e:  # noqa: BLE001
        return {"pass": None, "confidence": 0.0, "findings": [],
                "error": f"novelty check failed: {str(e)[:120]}"}
    return {"pass": not findings, "confidence": 0.9, "findings": findings}


def variety(out: Path, ctx: dict | None = None) -> dict | None:
    """Card/visual-family budget measured on the render."""
    import no_dull_beats as ndb
    beats = ((ctx or {}).get("story") or {}).get("beats")
    bm = _pkg(out) / "beatmap.json"
    if not beats or not bm.exists():
        return None
    try:
        frac, over = ndb.composition_budget(beats, bm)
    except Exception as e:  # noqa: BLE001
        return {"pass": None, "confidence": 0.0, "findings": [],
                "error": f"budget failed: {str(e)[:120]}"}
    findings = []
    if over:
        findings.append({
            "defect_code": "CARDS_OVER_BUDGET", "severity": "blocker",
            "complaint": f"data-cards are {frac:.0%} of the video",
            "recommended_fix": "carry beats with character scenes or footage",
            "target": "film", "confidence": 0.95})
    return {"pass": not findings, "confidence": 0.9, "findings": findings,
            "card_fraction": frac}


def hook(out: Path, ctx: dict | None = None) -> dict | None:
    """The opening decides retention; grade it as its own judge."""
    import hook_director
    beats = ((ctx or {}).get("story") or {}).get("beats") or []
    if not beats or not Path(out).exists():
        return None
    line = str(beats[0].get("say") or beats[0].get("text") or "").strip()
    if not line:
        return None
    try:
        g = hook_director.grade(line, Path(out))
    except Exception as e:  # noqa: BLE001
        return {"pass": None, "confidence": 0.0, "findings": [],
                "error": f"hook grade failed: {str(e)[:120]}"}
    findings = []
    if not g.get("pass"):
        findings.append({
            "defect_code": "HOOK_WEAK", "severity": "major",
            "complaint": f"hook scores {g.get('total')}/10 "
                         f"(visual={g.get('visual', {}).get('gates')}, "
                         f"line={g.get('line', {}).get('gates')})",
            "recommended_fix": "re-open on motion with a stated promise",
            "beat": 0, "target": "beat 0", "confidence": 0.85})
    return {"pass": bool(g.get("pass")), "confidence": 0.85,
            "findings": findings, "hook_total": g.get("total")}


# ------------------------------------------------------------------ registry
def default_specs(deep: bool = False):
    """The judge set every render is graded by. `required` judges fail closed.

    Kept as a function (not a constant) so the loop can compose a different set
    per format without any story-specific branching.
    """
    from data_learning.judge_loop import JudgeSpec
    specs = [
        JudgeSpec("taste", taste, required=True, blind=True,
                  rubric_version=RUBRIC, provider="vision_subagent"),
        JudgeSpec("technical", technical, required=True, rubric_version=RUBRIC),
        JudgeSpec("factual", factual, required=True, rubric_version=RUBRIC),
        JudgeSpec("media_context", media_context, rubric_version=RUBRIC),
        JudgeSpec("captions", captions, rubric_version=RUBRIC),
        JudgeSpec("variety", variety, rubric_version=RUBRIC),
        JudgeSpec("hook", hook, rubric_version=RUBRIC),
    ]
    if deep:
        specs.append(JudgeSpec("pacing_retention", pacing_retention,
                               rubric_version=RUBRIC))
    return specs
