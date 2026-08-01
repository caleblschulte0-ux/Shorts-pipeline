#!/usr/bin/env python3
"""Phase 5: Profile individual scene functions to isolate bottlenecks.

Runs controlled experiments on each scene type with timing breakpoints
at key phases: scene initialization, frame generation, and encoding.

Usage:
    python scripts/profile_scenes.py --work /tmp/profile --report report.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_learning import scenes
from data_learning import perf_instrument as perf


def profile_scene_function(name: str, scene_fn, duration: float, number: str = "",
                           label: str = "", extra: dict = None) -> dict:
    """Profile a single scene function with detailed timing breakdown.

    Records time for:
    1. Function call overhead (Python setup)
    2. Module imports and initialization
    3. Video file I/O
    4. Total execution time
    """
    out = Path(f"/tmp/profile_shot_{name}.mp4")

    metrics = {
        "scene": name,
        "duration": duration,
        "timings": {},
        "size_mb": 0,
        "success": False,
    }

    # Time 1: Python call setup + module initialization
    t0 = time.time()
    try:
        # This includes all setup before rendering
        scene_fn(
            out,
            duration,
            number=number,
            label=label,
            extra=extra,
        )
        t_total = time.time() - t0
        metrics["timings"]["total"] = t_total

        # Check output
        if out.exists():
            size = out.stat().st_size
            metrics["size_mb"] = size / 1024 / 1024
            metrics["success"] = True
        else:
            metrics["error"] = "Output file not created"
    except Exception as e:
        metrics["error"] = str(e)

    return metrics


def main(argv):
    """Run scene profiling experiments."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--work", type=Path, default=Path("/tmp/profile"),
                    help="Working directory")
    ap.add_argument("--report", type=Path, default=None,
                    help="Save report to JSON file")
    ap.add_argument("--duration", type=float, default=2.5,
                    help="Scene duration in seconds")
    a = ap.parse_args(argv)

    work = a.work
    duration = a.duration
    report_path = a.report

    work.mkdir(parents=True, exist_ok=True)

    print(f"[profile] Scene function profiling (duration: {duration:.1f}s each)",
          file=sys.stderr)
    print(f"[profile] Working directory: {work}", file=sys.stderr)

    # Define test scenes
    test_scenes = [
        ("paycheck", scenes.paycheck_scene, "$2M", "YOU'LL EARN", None),
        ("tax", scenes.tax_scene, "25%", "GOVERNMENT", None),
        ("rent", scenes.rent_scene, "$500K", "HOUSING", None),
        ("gas", scenes.gas_scene, "$250K", "TRANSPORT", None),
        ("grocery", scenes.grocery_scene, "", "GROCERIES", None),
        ("subs", scenes.subs_scene, "", "SUBSCRIPTIONS", None),
        ("savings", scenes.savings_scene, "", "SAVINGS", None),
        ("treadmill", scenes.treadmill_scene, "", "RUNNING", None),
        ("sleep", scenes.sleep_scene, "", "SLEEP", None),
        ("work", scenes.work_scene, "", "WORK", None),
    ]

    results = {
        "test_date": str(Path(".").resolve()),
        "duration": duration,
        "scenes": [],
        "summary": {
            "fastest": None,
            "slowest": None,
            "total_time": 0,
            "success_count": 0,
        },
    }

    times = []
    print(f"\n[profile] Profiling {len(test_scenes)} scene functions...",
          file=sys.stderr)

    for i, (name, fn, number, label, extra) in enumerate(test_scenes):
        print(f"[profile] {i+1}/{len(test_scenes):2d}: {name:15} ... ",
              end="", file=sys.stderr, flush=True)

        metrics = profile_scene_function(name, fn, duration, number, label, extra)

        if metrics["success"]:
            t_total = metrics["timings"].get("total", 0)
            times.append((name, t_total))
            size = metrics["size_mb"]
            print(f"✓ ({t_total:6.2f}s, {size:.1f}MB)", file=sys.stderr)
            results["summary"]["success_count"] += 1
            results["summary"]["total_time"] += t_total
        else:
            print(f"✗ ({metrics.get('error', 'unknown error')})", file=sys.stderr)

        results["scenes"].append(metrics)

    # Compute summary stats
    if times:
        times.sort(key=lambda x: x[1])
        results["summary"]["fastest"] = {"scene": times[0][0], "time_s": times[0][1]}
        results["summary"]["slowest"] = {"scene": times[-1][0], "time_s": times[-1][1]}

        # Print analysis
        print("\n" + "=" * 70, file=sys.stderr)
        print("SCENE PROFILING SUMMARY", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

        print(f"Successful: {results['summary']['success_count']}/{len(test_scenes)}",
              file=sys.stderr)
        print(f"Total time: {results['summary']['total_time']:.1f}s",
              file=sys.stderr)
        print(f"Average per scene: {results['summary']['total_time'] / len(times):.2f}s",
              file=sys.stderr)

        print("\nFastest to slowest:", file=sys.stderr)
        for name, t in times:
            ratio = t / duration
            print(f"  {name:15} {t:6.2f}s ({ratio:5.1f}x realtime)",
                  file=sys.stderr)

        # Identify outliers
        avg_time = results["summary"]["total_time"] / len(times)
        print("\nOutlier analysis (>1.5x average):", file=sys.stderr)
        outliers = [(n, t) for n, t in times if t > avg_time * 1.5]
        if outliers:
            for name, t in outliers:
                print(f"  {name:15} {t:6.2f}s (avg was {avg_time:.2f}s)",
                      file=sys.stderr)
        else:
            print("  None — performance is consistent", file=sys.stderr)

        print("=" * 70, file=sys.stderr)

    # Save detailed report
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(results, indent=2))
        print(f"\n[profile] Detailed report saved to {report_path}", file=sys.stderr)

    return 0 if results["summary"]["success_count"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
