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


def candidates(cfg: dict, posted: set, n: int,
               held: set | None = None) -> list[str]:
    """The next `n` unposted stories the registry's split puts in the new
    look, in queue (config) order — the order the posting run reaches them.

    Two kinds of story do not use up one of the `n` (2026-10-08: no
    illustrated video posted, while every forge run spent two of its three
    picks on ozone-hole-recovery and helium-supply-squeeze, both fully drawn
    and both held in the rewrite mailbox by the pre-render gate, so the
    drawing budget advanced one story a run):
      * a story whose every beat already has a saved scene still goes
        through (its scenes are re-checked on load), but does not count;
      * a story with an OPEN rewrite request cannot render until it is
        rewritten, so it is skipped — drawing it first only feeds a queue
        the posting run will not take from.
    """
    from shared import style_arms
    if held is None:
        held = _held_slugs()
    out, counted = [], 0
    for s in cfg.get("stories", []):
        slug = s.get("slug")
        if not slug or slug in posted or slug in held:
            continue
        if style_arms.choose(slug) != "illustrated":
            continue
        out.append(slug)
        segs = s.get("segments") or []
        drawn = bool(segs) and all(
            isinstance(g.get("illustrated_scene"), str)
            and g["illustrated_scene"].strip() for g in segs)
        if not drawn:
            counted += 1
            if counted >= n:
                break
    return out


def _held_slugs() -> set:
    """Slugs the pre-render gate parked in the rewrite mailbox."""
    try:
        from shared import rewrite_mailbox
        return {r.get("slug") for r in rewrite_mailbox.open_requests()
                if r.get("slug")}
    except Exception:  # noqa: BLE001 — no mailbox: nothing is held
        return set()


def _unpostable(cfg: dict) -> set:
    """Slugs the deterministic pre-render gate holds for reasons no drawing
    fixes (a source that is not real): 2026-10-10 the night's batch spent its
    clock on measles and helium, both held that morning for their data."""
    out = set()
    try:
        from scripts import editorial_gate as eg
    except Exception:  # noqa: BLE001
        return out
    for s in cfg.get("stories", []):
        try:
            v = eg.pre_render_verdict(s, use_llm=False)
        except Exception:  # noqa: BLE001
            continue
        if not v["ok"] and any(r.startswith("data:") for r in v["reasons"]):
            out.add(s.get("slug"))
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
        _was = seg_cfg.get("illustrated_scene")
        if SA.saved_scene(seg_cfg, log=lambda m: log(f"[{slug}] seg{i}: {m}")):
            # an old scene re-judged to today's standard is saved as such
            if seg_cfg.get("illustrated_scene") != _was:
                _save_scene(config_path, slug, i, seg_cfg["illustrated_scene"])
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
    slugs = candidates(cfg, posted, args.stories, held=_held_slugs() | _unpostable(cfg))
    print(f"[predraw] next new-look stories: {slugs}", flush=True)
    complete = 0
    for slug in slugs:
        if deadline - time.monotonic() < 120:
            print("[predraw] budget spent", flush=True)
            break
        # The words first (2026-10-10: the night's batch drew phone-checks and
        # hpv to today's look, and the morning run held both because their
        # narration was still a readout). A story whose words cannot be made
        # current is not drawn: the posting run would not take it.
        sc = next(s for s in cfg["stories"] if s.get("slug") == slug)
        try:
            from shared import narration
            narration.retell(sc, config_path=args.config,
                             log=lambda m: print(f"[predraw] {m}", flush=True))
            told = narration.problems(sc)
        except Exception as e:  # noqa: BLE001 — the posting run retells again
            told = []
            print(f"[predraw] {slug}: retell skipped ({e})", flush=True)
        if told:
            print(f"[predraw] {slug}: not drawn — narration still a readout: "
                  f"{told[0]}", flush=True)
            continue
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
