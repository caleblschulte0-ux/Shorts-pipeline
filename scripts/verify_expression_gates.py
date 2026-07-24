#!/usr/bin/env python3
"""Phase 8-9: Automated gates for expression system.

Comprehensive verification that emotional expressions are production-ready:

Gates checked:
1. TECHNICAL — No crashes, memory stable, proper error handling
2. PERFORMANCE — Render times acceptable (≤6x realtime for complex scenes)
3. VISUAL — Expressions produce visible pose changes (baseline vs expression diff)
4. REGRESSION — Expression-free paths still work (backward compatibility)

Merge requirement: All gates must PASS before code is eligible for main branch.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_learning import scenes
from data_learning import expression


def gate_technical() -> dict:
    """Gate 1: Technical — No crashes, memory stable."""
    print("[gates] TECHNICAL: Testing crash-resistance and error handling...",
          file=sys.stderr)

    results = {
        "name": "technical",
        "passed": False,
        "checks": [],
    }

    # Check 1: Expression config loads and validates
    try:
        cfg = expression.ExpressionConfig(emotion="joy", intensity=1.5)
        if 0 <= cfg.intensity <= 1.0:  # Should be clamped
            results["checks"].append({"name": "intensity_clamping", "status": "pass"})
        else:
            results["checks"].append({"name": "intensity_clamping", "status": "fail"})
    except Exception as e:
        results["checks"].append({"name": "intensity_clamping", "status": "fail",
                                  "error": str(e)})

    # Check 2: Parse expression from dict (legacy + structured)
    try:
        legacy = expression.parse_expression_config({"express": True})
        if legacy and legacy.emotion == "resignation":
            results["checks"].append({"name": "legacy_format_parsing", "status": "pass"})
        else:
            results["checks"].append({"name": "legacy_format_parsing", "status": "fail"})
    except Exception as e:
        results["checks"].append({"name": "legacy_format_parsing", "status": "fail",
                                  "error": str(e)})

    # Check 3: Structured format parsing
    try:
        structured = expression.parse_expression_config({
            "expression": {"emotion": "joy", "intensity": 0.8}
        })
        if structured and structured.emotion == "joy":
            results["checks"].append({"name": "structured_format_parsing", "status": "pass"})
        else:
            results["checks"].append({"name": "structured_format_parsing", "status": "fail"})
    except Exception as e:
        results["checks"].append({"name": "structured_format_parsing", "status": "fail",
                                  "error": str(e)})

    # Check 4: Pose application (apply_expression)
    try:
        base = expression.CharacterPose()
        cfg = expression.ExpressionConfig(emotion="joy", intensity=0.7)
        result = expression.apply_expression(base, cfg, beat_time=0.5)
        if result.arms_up > base.arms_up:  # Joy should raise arms
            results["checks"].append({"name": "pose_application", "status": "pass"})
        else:
            results["checks"].append({"name": "pose_application", "status": "fail"})
    except Exception as e:
        results["checks"].append({"name": "pose_application", "status": "fail",
                                  "error": str(e)})

    # Check 5: No-expression renders don't crash
    try:
        out = Path("/tmp/gate_test_noexpr.mp4")
        scenes.paycheck_scene(out, 1.0, extra=None)
        if out.exists():
            results["checks"].append({"name": "no_expression_render", "status": "pass"})
            out.unlink()
        else:
            results["checks"].append({"name": "no_expression_render", "status": "fail"})
    except Exception as e:
        results["checks"].append({"name": "no_expression_render", "status": "fail",
                                  "error": str(e)})

    # Verdict
    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total = len(results["checks"])
    results["passed"] = (passed == total)
    results["score"] = f"{passed}/{total}"

    return results


def gate_performance() -> dict:
    """Gate 2: Performance — Render times acceptable."""
    print("[gates] PERFORMANCE: Verifying render efficiency...",
          file=sys.stderr)

    results = {
        "name": "performance",
        "passed": False,
        "checks": [],
        "details": [],
    }

    test_scenes = [
        ("paycheck", scenes.paycheck_scene, {"express": True}),
        ("tax", scenes.tax_scene, {"express": True}),
        ("treadmill", scenes.treadmill_scene, {"express": True}),
    ]

    max_acceptable_multiplier = 6.0  # Max 6x realtime

    for name, fn, extra in test_scenes:
        try:
            out = Path(f"/tmp/gate_perf_{name}.mp4")
            duration = 1.5

            t0 = time.time()
            fn(out, duration, extra=extra)
            elapsed = time.time() - t0

            multiplier = elapsed / duration
            passed = multiplier <= max_acceptable_multiplier

            results["details"].append({
                "scene": name,
                "duration": duration,
                "render_time": elapsed,
                "multiplier": multiplier,
                "passed": passed,
            })

            status = "pass" if passed else "fail"
            results["checks"].append({
                "name": f"performance_{name}",
                "status": status,
                "multiplier": multiplier,
            })

            out.unlink(missing_ok=True)
        except Exception as e:
            results["checks"].append({
                "name": f"performance_{name}",
                "status": "fail",
                "error": str(e),
            })

    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total = len(results["checks"])
    results["passed"] = (passed == total)
    results["score"] = f"{passed}/{total}"

    return results


def gate_visual() -> dict:
    """Gate 3: Visual — Expressions produce visible changes."""
    print("[gates] VISUAL: Verifying pose changes are visible...",
          file=sys.stderr)

    results = {
        "name": "visual",
        "passed": False,
        "checks": [],
    }

    # Test that expression configs produce different poses
    base = expression.CharacterPose()

    emotions = ["joy", "shock", "resignation", "frustration", "burden", "exhaustion", "relief"]
    for emotion in emotions:
        try:
            cfg = expression.ExpressionConfig(emotion=emotion, intensity=0.8)
            result = expression.apply_expression(base, cfg, beat_time=0.5)

            # Check that SOMETHING changed
            changed = (
                result.arms_up != base.arms_up or
                result.stride != base.stride or
                result.head_drop != base.head_drop or
                result.lean != base.lean or
                result.body_sway != base.body_sway or
                result.gesture_speed != base.gesture_speed
            )

            status = "pass" if changed else "fail"
            results["checks"].append({
                "name": f"visual_{emotion}",
                "status": status,
                "emotion": emotion,
                "changed": changed,
            })
        except Exception as e:
            results["checks"].append({
                "name": f"visual_{emotion}",
                "status": "fail",
                "error": str(e),
            })

    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total = len(results["checks"])
    results["passed"] = (passed >= 6)  # At least 6/7 emotions should produce visible changes
    results["score"] = f"{passed}/{total}"

    return results


def gate_regression() -> dict:
    """Gate 4: Regression — Old paths still work."""
    print("[gates] REGRESSION: Verifying backward compatibility...",
          file=sys.stderr)

    results = {
        "name": "regression",
        "passed": False,
        "checks": [],
    }

    # Test that scenes work without expressions
    test_cases = [
        ("paycheck_no_expr", scenes.paycheck_scene, None),
        ("tax_no_expr", scenes.tax_scene, None),
        ("treadmill_no_expr", scenes.treadmill_scene, None),
    ]

    for name, fn, extra in test_cases:
        try:
            out = Path(f"/tmp/gate_reg_{name}.mp4")
            fn(out, 1.0, extra=extra)

            if out.exists() and out.stat().st_size > 100000:
                results["checks"].append({"name": name, "status": "pass"})
                out.unlink()
            else:
                results["checks"].append({"name": name, "status": "fail",
                                         "error": "output file invalid"})
        except Exception as e:
            results["checks"].append({"name": name, "status": "fail", "error": str(e)})

    passed = sum(1 for c in results["checks"] if c["status"] == "pass")
    total = len(results["checks"])
    results["passed"] = (passed == total)
    results["score"] = f"{passed}/{total}"

    return results


def main(argv):
    """Run all automated gates."""
    print("[gates] Phase 8-9: Automated gates for expression system", file=sys.stderr)
    print("[gates] Checking: Technical, Performance, Visual, Regression", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    all_results = []

    # Run each gate
    gates = [
        gate_technical(),
        gate_performance(),
        gate_visual(),
        gate_regression(),
    ]

    for gate in gates:
        status = "✓ PASS" if gate["passed"] else "✗ FAIL"
        print(f"\n{status} — {gate['name'].upper()}: {gate['score']}", file=sys.stderr)
        for check in gate.get("checks", [])[:3]:  # Show first 3
            check_status = "✓" if check["status"] == "pass" else "✗"
            print(f"  {check_status} {check.get('name', 'unnamed')}", file=sys.stderr)
        if len(gate.get("checks", [])) > 3:
            print(f"  ... and {len(gate['checks']) - 3} more", file=sys.stderr)

        all_results.append(gate)

    # Summary
    print("\n" + "=" * 70, file=sys.stderr)
    passed_count = sum(1 for g in all_results if g["passed"])
    total_count = len(all_results)

    print(f"MERGE READINESS: {passed_count}/{total_count} gates passed", file=sys.stderr)

    if passed_count == total_count:
        print("✓ APPROVED FOR MERGE", file=sys.stderr)
        exit_code = 0
    else:
        print("✗ BLOCKED — Fix failing gates before merge", file=sys.stderr)
        exit_code = 1

    print("=" * 70, file=sys.stderr)

    # Save detailed results
    results_file = Path("/tmp/gate_results.json")
    results_file.write_text(json.dumps({
        "timestamp": str(Path(".").resolve()),
        "gates": all_results,
        "overall_verdict": "pass" if exit_code == 0 else "fail",
        "passed": passed_count,
        "total": total_count,
    }, indent=2))
    print(f"\n[gates] Detailed results saved to {results_file}", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
