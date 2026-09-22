"""EVERY TOP-PANEL SHOT IS CHECKED AGAINST ITS OWN LINE BEFORE IT IS PLACED.

`junk_imagery` is the showrunner's ONE fatal check, and on the trending
channel it was 27 of 101 verdicts in the twelve days to 2026-09-22: "a
polaroid photo-wall that belongs to no beat", "a gavel on a medicine book
under 'the state's security'", "a truffle chocolate kiosk for a
hardware-store story", "a stone lion statue for a real mountain lion".
Every one was a keyword-matched stock photo that nothing looked at before
it was composited over the gameplay. The judge's own fix note, three times
in one afternoon: "gate every top-panel shot against its own script line
before placement and drop any image that matches only the brand token".

So the renderer asks the Claude HEADLESS BRAIN — the same `claude` CLI on
the subscription that the showrunner is — to look at the panels it is
about to place, one call for the whole story, and answer per shot: does
this picture depict this line? A shot the brain rejects gets NO panel: the
gameplay shows through for that window (the renderer already handles a
missing panel), which the gate reads as plain, not as a lie.

FAIL DIRECTION. The brain unavailable, timing out, or answering nothing
parseable keeps every panel — the status quo, judged afterwards by the
showrunner as before. A definite "no" is the only thing that removes a
picture. `SHOT_RELEVANCE=off` disables the check.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

TIMEOUT_S = int(os.environ.get("SHOT_RELEVANCE_TIMEOUT", "240"))

_PROMPT = """You are checking the illustrations of a short vertical video BEFORE \
they are placed. Each shot below pairs one image file with the exact line of \
narration it will sit over, for the story titled: {title}

For EVERY shot, READ the image file with the Read tool, then decide whether \
the picture DEPICTS what that line is about — the subject, object or action \
the viewer is being told about — such that a stranger would see the picture \
and the line as the same thing. A generic stock photo, a brand logo or \
product, a keyword coincidence (a courtroom gavel for "the state's security", \
a medical textbook, a photo wall, a fruit stand under "picking my paint"), a \
different animal, a statue for a real animal, or an image about a different \
story is NOT a depiction. When in doubt, say false: a missing picture costs \
less than a wrong one.

Shots:
{shots}

For every shot you reject, also give better_query: 2-4 concrete words an \
image search would need to return a picture that DOES depict the line (the \
object or action itself: "security deposit form", "empty apartment walk", \
"paint store aisle"), never a brand or a mood word. Empty when nothing would.

Return ONLY a JSON object, no prose:
{{"shots": [{{"index": <int>, "depicts": <true|false>, "why": "<one line>", \
"better_query": "<2-4 words or empty>"}}, ...]}}
"""


def enabled() -> bool:
    """On by default IN CI, where the render job installs the CLI for the
    showrunner; off by default on a developer machine, where a local
    `claude` would be asked to grade unit-test fixtures. `SHOT_RELEVANCE`
    set explicitly wins either way (same shape as `llm_mailbox.enabled`)."""
    v = os.environ.get("SHOT_RELEVANCE")
    if v is not None:
        return v.lower() not in ("0", "off", "false", "")
    return bool(os.environ.get("GITHUB_ACTIONS"))


def judge_panels(panels: list[tuple[int, Path, str]], title: str = "",
                 model: str | None = None) -> dict[int, dict] | None:
    """{shot_index: {"depicts": bool, "why": str}} from the headless brain,
    or None when it could not answer (no CLI, failure, timeout, unparseable).
    `panels` is [(shot_index, image_path, narrated_line), ...]."""
    if not panels:
        return {}
    if not shutil.which("claude"):
        return None
    shots = "\n".join(f"- shot {i}: image {p} — line: \"{line.strip()}\""
                      for i, p, line in panels)
    prompt = _PROMPT.format(title=title or "(untitled)", shots=shots)
    model = model or os.environ.get("SHOT_RELEVANCE_MODEL",
                                    os.environ.get("SHOWRUNNER_MODEL", "sonnet"))
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model,
             "--allowedTools", "Read", "--output-format", "text"],
            capture_output=True, text=True, timeout=TIMEOUT_S)
    except Exception:  # noqa: BLE001 — timeout, missing binary, OS error
        return None
    if proc.returncode != 0:
        return None
    try:
        from scripts.showrunner_review import parse_judge_json
        data = parse_judge_json(proc.stdout or "")
    except Exception:  # noqa: BLE001
        return None
    rows = data.get("shots") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return None
    out: dict[int, dict] = {}
    for r in rows:
        try:
            i = int(r.get("index"))
        except Exception:  # noqa: BLE001
            continue
        out[i] = {"depicts": bool(r.get("depicts")),
                  "why": str(r.get("why") or "")[:200],
                  "better_query": str(r.get("better_query") or "").strip()[:60]}
    return out or None


def filter_panels(panels: dict[int, Path], shots: list[dict], title: str = "",
                  verdicts: dict[int, dict] | None = None) -> tuple[dict[int, Path], list[dict]]:
    """Drop every panel the brain says does not depict its line. Returns the
    kept panels and a list of {index, why} for the dropped ones. Panels the
    brain did not rule on (or could not rule on at all) are kept."""
    if not panels or not enabled():
        return panels, []
    if verdicts is None:
        pairs = []
        for i, p in sorted(panels.items()):
            shot = shots[i] if i < len(shots) else {}
            line = shot.get("phrase") or shot.get("line") or shot.get("text") or ""
            pairs.append((i, p, str(line)))
        verdicts = judge_panels(pairs, title=title)
    if not verdicts:
        return panels, []
    kept, dropped = {}, []
    for i, p in panels.items():
        v = verdicts.get(i)
        if v is not None and v.get("depicts") is False:
            dropped.append({"index": i, "why": v.get("why", ""),
                            "better_query": v.get("better_query", "")})
        else:
            kept[i] = p
    return kept, dropped


_ATTESTED = ("image_url", "image", "media_sha256", "media_bytes")


def replace_dropped(pkg: dict, dropped: list[dict], materialise,
                    title: str = "") -> tuple[dict[int, Path], list[dict]]:
    """ONE replacement round for the panels the brain rejected.

    Dropping a wrong picture fixed junk_imagery and opened the next hole
    the same afternoon (2026-09-22, 20:15, the staff story at 65): "after
    the post card there is not a single story illustration". A gap is
    better than a lie, and a right picture is better than either. So each
    rejected shot is searched AGAIN with the brain's own `better_query`
    through the same self-fill lanes Phase B uses, materialised by the
    renderer's `materialise(index, url) -> Path`, and judged once more.
    A replacement the brain also rejects is dropped; one it cannot rule
    on is kept (the status quo for a picture nothing said no to). A shot
    with no better query, or no search hit, keeps its gap and its
    original fields. Bounded: one search per rejected shot, one judge
    call for the whole round, never a third."""
    if not dropped or not enabled():
        return {}, []
    shots = pkg.get("shots") or []
    try:
        from scripts.exchange_phase_b import self_fill
    except Exception:  # noqa: BLE001
        return {}, []
    fresh: dict[int, Path] = {}
    for d in dropped:
        i = int(d.get("index", -1))
        q = str(d.get("better_query") or "").strip()
        if not q or not 0 <= i < len(shots):
            continue
        shot = shots[i]
        before = dict(shot)
        shot["query"] = q
        for k in _ATTESTED:            # a new picture carries no old attestation
            shot.pop(k, None)
        url = None
        try:
            url = self_fill(pkg, i)
        except Exception:  # noqa: BLE001
            url = None
        panel = None
        if url:
            shot["image_url"] = url
            try:
                panel = materialise(i, url)
            except Exception:  # noqa: BLE001
                panel = None
        if panel:
            fresh[i] = Path(panel)
        else:
            shot.clear()
            shot.update(before)
    if not fresh:
        return {}, []
    kept, dropped_again = filter_panels(fresh, shots, title=title)
    for d in dropped_again:            # the second no: the gap stays, the shot goes back
        i = d["index"]
        shots[i].pop("image_url", None)
    return kept, dropped_again
