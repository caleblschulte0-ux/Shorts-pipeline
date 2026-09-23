#!/usr/bin/env python3
"""REDRAW the scene the showrunner named — the illustrated arm's repair.

`scene_repair` restructures a CHART: it swaps one chart kind for another.
An illustrated video has no chart to swap; every beat is a drawn scene of
the subject. So its repair is the brain redrawing the one scene the judge
named, handed exactly what the judge SAW (`weakest_scene`: visible evidence,
root cause, repair goal, and that scene's depiction note) and the code that
drew it. The redraw passes the same sandbox and verifier as a first draft.

Nothing here decides anything. `propose` writes the redrawn scene into the
story config and returns an `undo`; the caller re-renders, re-judges, and
keeps it only if the gate scores the new cut higher — the same keep-best
rule every repair in this repo lives under.

Precedence in the renderer is saved code > hand-drawn teacher > brain draft,
which is what lets a repair that beat a teacher stick.
"""
from __future__ import annotations

import copy
import inspect
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import scene_repair as _sr  # noqa: E402


def critique_for(verdict: dict, k: int) -> str:
    """What the judge said about window k, in its own words."""
    ws = verdict.get("weakest_scene") or {}
    lines = []
    for key in ("failure_class", "visible_evidence", "root_cause", "repair_goal"):
        if ws.get(key):
            lines.append(f"- {key.replace('_', ' ')}: {ws[key]}")
    for d in verdict.get("depictions") or []:
        if str(d.get("id", "")).lower() == f"seg{k}" and d.get("note"):
            lines.append(f"- its depiction grade: bespoke {d.get('bespoke')}/3, "
                         f"proves the claim {d.get('proves_claim')}/3 — {d['note']}")
    for p in verdict.get("problems") or []:
        if f"seg{k}" in str(p).lower():
            lines.append(f"- problem: {p}")
    return "\n".join(lines) or "- (the judge named this scene as the weakest)"


def _prior_code(story_cfg: dict, role: str, beat: int, slug: str) -> str:
    """The code that drew the scene being repaired: the saved brain scene,
    else the hand-drawn teacher's source, renamed to `scene`."""
    from data_learning import subject_scenes as SS
    if role in ("hook", "closing"):
        code = story_cfg.get(f"{role}_scene")
        fn = ((SS.hook_for if role == "hook" else SS.closing_for)(slug) or (None,))[0]
    else:
        code = (story_cfg.get("segments") or [{}])[beat].get("illustrated_scene")
        fn = SS.scene_for(slug, beat)
    if isinstance(code, str) and code.strip():
        return code
    if fn is not None:
        return inspect.getsource(fn).replace(f"def {fn.__name__}(", "def scene(", 1)
    return "(none — this scene fell back to the current look)"


def propose(slug: str, verdict: dict, config_path: Path, log=print) -> dict:
    """Redraw the named scene and write it into `config_path`. Returns
    {"window", "role", "beat", "undo"}; raises when there is nothing to
    redraw or nothing the brain drew passed the verifier."""
    from data_learning import story, scene_author as SA
    from data_learning import subject_scenes as SS
    config_path = Path(config_path)
    cfg = json.loads(config_path.read_text())
    story_cfg = next(s for s in cfg["stories"] if s["slug"] == slug)
    before = copy.deepcopy(story_cfg)
    with tempfile.TemporaryDirectory() as td:
        st = story.build(story_cfg, cfg, Path(td), REPO)
        segs = list(st.segments)
    n = len(segs)
    k = _sr.judged_window(verdict)
    if k is None:
        raise RuntimeError("the verdict names no weakest scene — nothing to redraw")
    role = _sr.window_role(k, n)
    beat = _sr.window_to_beat(k, n)
    if role == "hook" and not (story_cfg.get("hook_scene") or SS.hook_for(slug)):
        # No hook scene: the hook plays over beat 0's, so a weak hook is
        # beat 0 redrawn with the judge's words about the opening.
        role = "beat"
    if role in ("hook", "closing"):
        idx = story_cfg.get(f"{role}_data", 0)
        idx = idx if isinstance(idx, int) and 0 <= idx < n else 0
        insight, target = segs[idx].insight, role
    else:
        idx, insight, target = beat, segs[beat].insight, beat
    log(f"[scene_redraw] {slug}: judge named seg{k} ({role}) — redrawing "
        f"{'the ' + role if role != 'beat' else f'beat {beat}'}")
    fn, got = SA.redraw(story_cfg, target, insight,
                        _prior_code(story_cfg, role, beat, slug),
                        critique_for(verdict, k), log=log)
    if fn is None:
        raise RuntimeError(f"no verified redraw: {got}")
    if role in ("hook", "closing"):
        story_cfg[f"{role}_scene"], story_cfg[f"{role}_data"] = got, idx
    else:
        story_cfg["segments"][beat]["illustrated_scene"] = got
    config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")

    def undo() -> None:
        """Put this story back exactly as it was. Never raises."""
        try:
            c = json.loads(config_path.read_text())
            for j, s in enumerate(c.get("stories", [])):
                if s.get("slug") == slug:
                    c["stories"][j] = before
            config_path.write_text(json.dumps(c, indent=2, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            log(f"[scene_redraw] undo failed: {e}")

    return {"window": k, "role": role, "beat": beat, "undo": undo}
