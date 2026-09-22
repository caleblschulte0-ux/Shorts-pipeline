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

Return ONLY a JSON object, no prose:
{{"shots": [{{"index": <int>, "depicts": <true|false>, "why": "<one line>"}}, ...]}}
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
                  "why": str(r.get("why") or "")[:200]}
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
            dropped.append({"index": i, "why": v.get("why", "")})
        else:
            kept[i] = p
    return kept, dropped
