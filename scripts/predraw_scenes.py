#!/usr/bin/env python3
"""DRAW THE NEW LOOK BEFORE THE POSTING RUN, not during it.

The explainer's A/B split is two of each look a day (`style_arms.quota`),
and a new-look (illustrated) video renders in that look only when EVERY beat
has a verified subject scene (`studio_render`: one video, one look). Until
2026-10-07 those scenes were drawn only inside the posting render, against
that video's drawing clock, and the first beat the brain could not get past
the verifier sent the whole video to the current look. From 2026-10-05 18:34
to 2026-10-07 not one illustrated video rendered: 41 queued new-look stories
held 0 saved scenes between them, every posting run started each of them
from beat 0, and the slots the operator asked for ("two of A, two of B")
went unfilled.

This step runs in the story forge, hours before the posting window, and does
the drawing with its own clock: for the next new-look stories in queue
order, every beat whose saved scene is missing or no longer passes the load
check (compile + the lit-art craft check) is drawn through the SAME
`scene_author.scene_for_segment` the renderer calls — same prompt, same
sandbox, same verifier, same viewer glance. Nothing is relaxed; a scene this
step saves is exactly a scene the renderer would have saved. Each verified
scene is written to `niche.config.json` the moment it passes, touching only
that segment, so a timeout never loses work.

    python scripts/predraw_scenes.py --stories 3 --budget-min 30
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CONFIG = REPO / "data_learning" / "niche.config.json"
POSTED = REPO / "state" / "explainer_posted_log.json"


def candidates(cfg: dict, posted: set, n: int) -> list[str]:
    """The next `n` unposted stories the registry's split puts in the new
    look, in queue (config) order — the order the posting run reaches them."""
    from shared import style_arms
    out = []
    for s in cfg.get("stories", []):
        slug = s.get("slug")
        if not slug or slug in posted:
            continue
        if style_arms.choose(slug) != "illustrated":
            continue
        out.append(slug)
        if len(out) >= n:
            break
    return out


def _save_scene(config_path: Path, slug: str, index: int, code: str) -> None:
    """Write one verified scene onto one segment — re-reading the file first
    so a concurrent edit to any other story or segment survives."""
    from shared.fsutil import write_json_if_changed
    cfg = json.loads(config_path.read_text())
    for s in cfg.get("stories", []):
        if s.get("slug") == slug:
            segs = s.get("segments") or []
            if 0 <= index < len(segs):
                segs[index]["illustrated_scene"] = code
            break
    write_json_if_changed(config_path, cfg, ensure_ascii=False)


def predraw(slug: str, cfg: dict, config_path: Path, deadline: float,
            log=print) -> dict:
    """Draw every missing beat of one story. {"drawn", "kept", "missing"}."""
    from data_learning import story, scene_author as SA
    story_cfg = next(s for s in cfg["stories"] if s["slug"] == slug)
    with tempfile.TemporaryDirectory() as td:
        st = story.build(story_cfg, cfg, Path(td), REPO)
        segs = list(st.segments)
    res = {"drawn": [], "kept": [], "missing": []}
    for i, sg in enumerate(segs):
        ins = getattr(sg, "insight", None)
        if ins is None:
            continue
        cfg_segs = story_cfg.get("segments") or []
        seg_cfg = cfg_segs[i] if i < len(cfg_segs) else {}
        if SA.saved_scene(seg_cfg, log=lambda m: log(f"[{slug}] seg{i}: {m}")):
            res["kept"].append(i)
            continue
        left = deadline - time.monotonic()
        if left < 120:
            res["missing"].append(i)
            continue
        SA.set_budget(min(SA.BUDGET_S, left))
        fn = SA.scene_for_segment(story_cfg, i, ins,
                                  log=lambda m: log(f"[{slug}] seg{i}: {m}"))
        code = seg_cfg.get("illustrated_scene") if fn is not None else None
        if fn is not None and isinstance(code, str) and code.strip():
            _save_scene(config_path, slug, i, code)
            res["drawn"].append(i)
        else:
            res["missing"].append(i)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stories", type=int, default=3,
                    help="how many of the next new-look stories to complete")
    ap.add_argument("--budget-min", type=float, default=30.0,
                    help="wall-clock minutes for the whole step")
    ap.add_argument("--config", type=Path, default=CONFIG)
    args = ap.parse_args(argv)

    from data_learning import scene_author as SA
    if not SA.shutil.which("claude"):
        print("[predraw] no claude CLI — nothing can be drawn; skipping")
        return 0
    cfg = json.loads(args.config.read_text())
    try:
        posted = set(json.loads(POSTED.read_text()).get("posted", {}))
    except Exception:  # noqa: BLE001 — no log: nothing is posted yet
        posted = set()
    deadline = time.monotonic() + args.budget_min * 60
    slugs = candidates(cfg, posted, args.stories)
    print(f"[predraw] next new-look stories: {slugs}", flush=True)
    complete = 0
    for slug in slugs:
        if deadline - time.monotonic() < 120:
            print("[predraw] budget spent", flush=True)
            break
        try:
            r = predraw(slug, cfg, args.config, deadline,
                        log=lambda m: print(f"[predraw] {m}", flush=True))
        except Exception as e:  # noqa: BLE001 — one story never stops the rest
            print(f"[predraw] {slug}: skipped ({type(e).__name__}: {e})", flush=True)
            continue
        ok = not r["missing"]
        complete += ok
        print(f"[predraw] {slug}: drawn {r['drawn']}, kept {r['kept']}, "
              f"missing {r['missing']} — "
              f"{'READY for the new look' if ok else 'not ready yet'}", flush=True)
    print(f"[predraw] {complete}/{len(slugs)} stories ready to render in the new look")
    return 0


if __name__ == "__main__":
    sys.exit(main())
