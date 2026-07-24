#!/usr/bin/env python3
"""Phase 4.4: Deterministic performance test mode.

Renders 5 representative scene shots to quickly isolate render bottlenecks.
Used for comparative profiling and diagnosing slowdowns without full pipeline overhead.

Usage:
    python scripts/perf_test_render.py --work /tmp/perf_test --report /tmp/report.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_learning import scenes
from data_learning import perf_instrument as perf


def run_perf_test(work_dir: Path) -> dict:
    """Run deterministic performance test on 5 representative shots.

    Returns metrics dictionary with timing for each shot type.
    """
    work_dir.mkdir(parents=True, exist_ok=True)

    test_shots = [
        {
            "name": "paycheck",
            "fn": scenes.paycheck_scene,
            "duration": 2.5,
            "number": "$2M",
            "label": "YOU'LL EARN",
            "extra": None,
        },
        {
            "name": "tax",
            "fn": scenes.tax_scene,
            "duration": 2.5,
            "number": "25%",
            "label": "GOVERNMENT",
            "extra": None,
        },
        {
            "name": "rent",
            "fn": scenes.rent_scene,
            "duration": 2.5,
            "number": "$500K",
            "label": "HOUSING",
            "extra": None,
        },
        {
            "name": "gas",
            "fn": scenes.gas_scene,
            "duration": 2.5,
            "number": "$250K",
            "label": "TRANSPORT",
            "extra": None,
        },
        {
            "name": "treadmill",
            "fn": scenes.treadmill_scene,
            "duration": 2.5,
            "number": "",
            "label": "RUNNING",
            "extra": None,
        },
    ]

    perf.init_render("perf_test", 1, len(test_shots))

    print(f"[perf_test] Running {len(test_shots)} representative shots...",
          file=sys.stderr)

    for i, shot in enumerate(test_shots):
        out = work_dir / f"shot_{i:02d}_{shot['name']}.mp4"
        perf.start_shot(i, shot["name"], shot["duration"])

        try:
            print(f"[perf_test] {i+1}/{len(test_shots)}: {shot['name']:15} ... ",
                  end="", file=sys.stderr, flush=True)

            with perf.stage("scene_render", "frame_render"):
                shot["fn"](
                    out,
                    shot["duration"],
                    number=shot["number"],
                    label=shot["label"],
                    extra=shot["extra"],
                )

            size_mb = out.stat().st_size / 1024 / 1024
            print(f"✓ ({size_mb:.1f}MB)", file=sys.stderr)

        except Exception as e:
            print(f"✗ ({e})", file=sys.stderr)

        perf.end_shot()

    return perf.end_render(sum(s["duration"] for s in test_shots),
                           sum(s["duration"] for s in test_shots))


def main(argv):
    """Run performance test render."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, default=Path("/tmp/perf_test"),
                    help="Working directory for temp files")
    ap.add_argument("--report", type=Path, default=None,
                    help="Save detailed report to JSON file")
    a = ap.parse_args(argv)

    work = a.work
    report_path = a.report

    try:
        metrics = run_perf_test(work)

        if metrics:
            print("\n" + "=" * 70, file=sys.stderr)
            print("PERFORMANCE TEST SUMMARY", file=sys.stderr)
            print("=" * 70, file=sys.stderr)

            total = metrics.total_elapsed_s
            video_dur = metrics.actual_duration_s
            shots = metrics.shots

            print(f"Total render time: {total:.1f}s", file=sys.stderr)
            print(f"Video duration: {video_dur:.1f}s", file=sys.stderr)
            if total > 0:
                efficiency = video_dur / total * 100
                print(f"Efficiency: {efficiency:.0f}% "
                      f"(rendering takes {total/video_dur:.1f}x video length)",
                      file=sys.stderr)
            print(f"Shots rendered: {len(shots)}", file=sys.stderr)

            # Stage breakdown
            stages = metrics.stages
            if stages:
                print("\nStage breakdown:", file=sys.stderr)
                for stage_name in sorted(stages.keys()):
                    data = stages[stage_name]
                    elapsed = data.get("elapsed_s", 0)
                    calls = data.get("count", 0)
                    pct = 100 * elapsed / total if total > 0 else 0
                    print(f"  {stage_name:25} {elapsed:6.2f}s ({pct:5.1f}%) "
                          f"[{calls} calls]", file=sys.stderr)

            # Shot breakdown
            if shots:
                print("\nPer-shot times:", file=sys.stderr)
                for shot in shots:
                    idx = shot.shot_idx
                    kind = shot.shot_kind
                    total_s = shot.total_s
                    render_s = shot.frame_render_s
                    print(f"  Shot {idx}: {kind:20} {total_s:6.2f}s "
                          f"(render {render_s:5.2f}s)",
                          file=sys.stderr)

                # Memory summary
                if shots[0].mem_start.rss_mb > 0:
                    first_rss = shots[0].mem_start.rss_mb
                    peak_rss = max((s.mem_end.rss_mb for s in shots), default=0)
                    print("\nMemory:", file=sys.stderr)
                    print(f"  Start: {first_rss:.0f}MB", file=sys.stderr)
                    print(f"  Peak:  {peak_rss:.0f}MB (Δ{peak_rss - first_rss:+.0f}MB)",
                          file=sys.stderr)

            # Save detailed report if requested
            if report_path:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(perf.report_json(metrics))
                print(f"\nDetailed report saved to {report_path}", file=sys.stderr)

            print("=" * 70, file=sys.stderr)
            return 0
        else:
            print("[perf_test] ERROR: No metrics collected", file=sys.stderr)
            return 1

    except Exception as e:
        print(f"[perf_test] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
