"""Only a video made to TODAY's standard is uploaded, by any path.

Operator, 2026-10-09, after a two-day-old render of the twins story reached
TikTok and a retired-look video went out the same morning: "make sure that
this never happens again ... you need to be double checking, triple
checking that that's all going to be updated and none of this shit's going
to happen again. In terms of like stuff posting that isn't updated."

Every render writes `standard` into its `<mp4>.style.json` sidecar. Before
an upload — the posting run's own and the mailbox claim's, which ships a
render kept from an earlier run — `problems` refuses a video that:

  * was rendered under an older standard (bump STANDARD whenever a rule a
    video must meet changes: the look, the hook, the narration);
  * is in a look the registry has retired (`style_arms` weight 0), or had a
    beat fall back to it;
  * opens on a hook under `hook_doctrine.floor`, or tells its beats as a
    readout of numbers or names a group nobody knows (`narration.problems`).

A refusal is not a gate verdict and never touches the showrunner: the story
stays in the queue and the next run renders it fresh, to today's standard.
"""
from __future__ import annotations

from pathlib import Path

#: the date of the rules a video must meet; see the module docstring
STANDARD = "2026-10-09"


def stamp() -> dict:
    return {"standard": STANDARD}


def problems(mp4: Path, story_cfg: dict | None) -> list[str]:
    from shared import style_arms
    side = style_arms.read(Path(mp4)) or {}
    out = []
    if side.get("standard") != STANDARD:
        out.append(f"rendered under the {side.get('standard') or 'pre-2026-10-09'} "
                   f"standard, not today's {STANDARD}")
    arm = side.get("style_arm") or "current"
    try:
        live = style_arms.weights()
    except Exception:  # noqa: BLE001 — no registry: the arm cannot be vouched for
        live = {}
    if live.get(arm, 0) <= 0:
        out.append(f"rendered in the {arm!r} look, which the registry has retired")
    elif side.get("fallback_beats"):
        out.append(f"beat(s) {side['fallback_beats']} fell back to the old look")
    sc = story_cfg or {}
    from shared import hook_doctrine, narration
    hook = str(sc.get("hook") or "")
    if hook and hook_doctrine.floor(hook):
        out.append(f"the hook is under the floor: {hook_doctrine.floor(hook)[0]}")
    out += [f"the narration {p}" for p in narration.problems(sc)]
    return out
