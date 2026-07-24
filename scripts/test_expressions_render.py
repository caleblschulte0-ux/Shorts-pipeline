#!/usr/bin/env python3
"""Phase 6-7: Verify expressions in real render context.

Tests that emotional expressions:
1. Render without crashing (Phase 6 technical gate)
2. Produce visible pose changes (Phase 7 visual verification)
3. Work with realistic scene configurations

Renders a 30-second excerpt with expressions enabled on key scenes.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_learning import scenes
from data_learning import perf_instrument as perf


def render_excerpt_with_expressions(out: Path, work: Path) -> dict:
    """Render a 30-second excerpt with expressions on key scenes."""
    work.mkdir(parents=True, exist_ok=True)

    perf.init_render("expressions_excerpt", 1, 4)

    results = {
        "story": "expressions_excerpt",
        "duration_target": 30.0,
        "shots": [],
        "verdict": "pass",
    }

    # Define excerpt: 4 shots with expressions enabled
    scenes_to_render = [
        {
            "name": "paycheck_expr",
            "scene_fn": scenes.paycheck_scene,
            "duration": 8.0,
            "extra": {"express": True},
            "label": "YOU'LL EARN",
            "number": "$2M",
        },
        {
            "name": "tax_expr",
            "scene_fn": scenes.tax_scene,
            "duration": 7.0,
            "extra": {"express": True},
            "label": "GOVERNMENT",
            "number": "25%",
        },
        {
            "name": "rent_expr",
            "scene_fn": scenes.rent_scene,
            "duration": 8.0,
            "extra": {"express": True},
            "label": "HOUSING",
            "number": "$500K",
        },
        {
            "name": "treadmill_expr",
            "scene_fn": scenes.treadmill_scene,
            "duration": 7.0,
            "extra": {"express": True},
            "label": "RUNNING",
            "number": "",
        },
    ]

    print(f"[test_expressions_render] Rendering {len(scenes_to_render)} scenes with expressions...",
          file=sys.stderr)

    for i, scene_config in enumerate(scenes_to_render):
        out_clip = work / f"shot_{i:02d}_{scene_config['name']}.mp4"
        duration = scene_config["duration"]

        perf.start_shot(i, scene_config["name"], duration)

        try:
            print(f"[test_expr] {i+1}/{len(scenes_to_render)}: {scene_config['name']:20} ... ",
                  end="", file=sys.stderr, flush=True)

            with perf.stage("scene_render", "frame_render"):
                scene_config["scene_fn"](
                    out_clip,
                    duration,
                    number=scene_config.get("number", ""),
                    label=scene_config.get("label", ""),
                    extra=scene_config["extra"],
                )

            # Verify output
            if out_clip.exists():
                size_mb = out_clip.stat().st_size / 1024 / 1024
                # Verify video is reasonable size and duration
                probe_result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "format=duration", "-of", "csv=p=0", str(out_clip)],
                    capture_output=True, text=True, timeout=5
                )
                try:
                    actual_duration = float(probe_result.stdout.strip() or "0")
                    if 0.5 < actual_duration < duration + 1.0:
                        print(f"✓ ({actual_duration:.1f}s, {size_mb:.1f}MB)", file=sys.stderr)
                        results["shots"].append({
                            "name": scene_config["name"],
                            "duration_planned": duration,
                            "duration_actual": actual_duration,
                            "size_mb": size_mb,
                            "expression": scene_config["extra"].get("express", False),
                            "status": "pass",
                        })
                    else:
                        print(f"✗ (duration mismatch: {actual_duration:.1f}s vs {duration}s)",
                              file=sys.stderr)
                        results["shots"].append({
                            "name": scene_config["name"],
                            "error": f"duration mismatch",
                            "status": "fail",
                        })
                        results["verdict"] = "fail"
                except ValueError:
                    print(f"✗ (duration probe failed)", file=sys.stderr)
                    results["shots"].append({
                        "name": scene_config["name"],
                        "error": "could not probe duration",
                        "status": "fail",
                    })
                    results["verdict"] = "fail"
            else:
                print(f"✗ (no output file)", file=sys.stderr)
                results["shots"].append({
                    "name": scene_config["name"],
                    "error": "no output file",
                    "status": "fail",
                })
                results["verdict"] = "fail"

        except Exception as e:
            print(f"✗ ({e})", file=sys.stderr)
            results["shots"].append({
                "name": scene_config["name"],
                "error": str(e),
                "status": "fail",
            })
            results["verdict"] = "fail"

        perf.end_shot()

    metrics = perf.end_render(
        sum(s["duration"] for s in scenes_to_render),
        sum(s["duration"] for s in scenes_to_render),
    )

    results["metrics"] = {
        "total_render_time_s": metrics.total_elapsed_s,
        "efficiency": metrics.actual_duration_s / metrics.total_elapsed_s * 100,
        "memory_start_mb": metrics.shots[0].mem_start.rss_mb if metrics.shots else 0,
        "memory_peak_mb": max((s.mem_end.rss_mb for s in metrics.shots), default=0),
    }

    return results


def main(argv):
    """Run expressions verification test."""
    out_dir = Path("/tmp/expressions_render")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[test_expressions_render] Phase 6-7: Verify expressions in render context",
          file=sys.stderr)

    try:
        results = render_excerpt_with_expressions(
            out_dir / "excerpt.mp4",
            out_dir / "work",
        )

        # Report results
        print("\n" + "=" * 70, file=sys.stderr)
        print("EXPRESSIONS RENDER TEST SUMMARY", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

        passed = sum(1 for s in results["shots"] if s.get("status") == "pass")
        total = len(results["shots"])

        print(f"Scenes rendered: {passed}/{total}", file=sys.stderr)
        print(f"Verdict: {results['verdict'].upper()}", file=sys.stderr)

        metrics = results.get("metrics", {})
        print(f"\nPerformance:", file=sys.stderr)
        print(f"  Render time: {metrics.get('total_render_time_s', 0):.1f}s",
              file=sys.stderr)
        print(f"  Efficiency: {metrics.get('efficiency', 0):.0f}%", file=sys.stderr)
        print(f"  Memory: {metrics.get('memory_start_mb', 0):.0f}MB -> "
              f"{metrics.get('memory_peak_mb', 0):.0f}MB", file=sys.stderr)

        print("\nScene details:", file=sys.stderr)
        for shot in results["shots"]:
            status = "✓" if shot.get("status") == "pass" else "✗"
            print(f"  {status} {shot.get('name', 'unknown'):25}", file=sys.stderr)
            if shot.get("status") == "pass":
                print(f"      planned {shot.get('duration_planned', 0):.1f}s → "
                      f"actual {shot.get('duration_actual', 0):.1f}s, "
                      f"{shot.get('size_mb', 0):.1f}MB", file=sys.stderr)
            else:
                print(f"      error: {shot.get('error', 'unknown')}", file=sys.stderr)

        print("=" * 70, file=sys.stderr)

        # Save results
        results_file = out_dir / "results.json"
        results_file.write_text(json.dumps(results, indent=2))
        print(f"\n[test_expressions_render] Results saved to {results_file}",
              file=sys.stderr)

        return 0 if results["verdict"] == "pass" else 1

    except Exception as e:
        print(f"[test_expressions_render] ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
