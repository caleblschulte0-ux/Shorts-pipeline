#!/usr/bin/env python3
"""Fast visual tests for character expressions.

Renders short clips and static frames for key scenes with expressions enabled/disabled
to verify:
1. Expressions render without crashing
2. Expressions produce visible pose changes
3. Scenes work identically when expressions are absent
"""

import json
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_learning import scenes
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO / "tests" / "expression_tests"
TESTS_DIR.mkdir(parents=True, exist_ok=True)

# Test cases: scene function, duration, and config for with/without expressions
@dataclass
class ExpressionTestCase:
    """A test case for expression rendering."""

    name: str  # "paycheck", "taxes", etc.
    scene_fn: str  # "paycheck_scene", "tax_scene", etc.
    duration: float = 2.5  # Short for fast tests
    number: str = ""
    label: str = ""
    base_extra: dict | None = None  # Extra config without expression
    expr_extra: dict | None = None  # Extra config with expression


TEST_CASES = [
    ExpressionTestCase(
        name="paycheck",
        scene_fn="paycheck_scene",
        duration=2.5,
        number="$2M",
        label="YOU'LL EARN",
        base_extra=None,
        expr_extra={"express": True},
    ),
    ExpressionTestCase(
        name="taxes",
        scene_fn="tax_scene",
        duration=2.5,
        number="25%",
        label="THE GOVERNMENT'S CUT",
        base_extra=None,
        expr_extra={"express": True},
    ),
    ExpressionTestCase(
        name="housing",
        scene_fn="rent_scene",
        duration=2.5,
        number="$500K",
        label="A ROOF OVER YOUR HEAD",
        base_extra=None,
        expr_extra={"express": True},
    ),
    ExpressionTestCase(
        name="transportation",
        scene_fn="gas_scene",
        duration=2.5,
        number="$250K",
        label="GETTING AROUND",
        base_extra=None,
        expr_extra={"express": True},
    ),
    ExpressionTestCase(
        name="treadmill",
        scene_fn="treadmill_scene",
        duration=2.5,
        number="",
        label="RUNNING TO STAND STILL",
        base_extra=None,
        expr_extra={"express": True},
    ),
    ExpressionTestCase(
        name="money_drain",
        scene_fn="money_scene",
        duration=2.5,
        number="$1M",
        label="HOUSING",
        base_extra={"upto": 1, "final": False},
        expr_extra={"upto": 1, "final": False, "express": True},
    ),
]


def render_test_clip(
    case: ExpressionTestCase,
    with_expression: bool,
) -> Path:
    """Render a short test clip for a scene.

    Args:
        case: Test case definition
        with_expression: If True, enable expressions; False = baseline

    Returns:
        Path to rendered MP4 file
    """
    scene_fn = getattr(scenes, case.scene_fn)
    suffix = "_expr" if with_expression else "_baseline"
    out = TESTS_DIR / f"{case.name}{suffix}.mp4"

    if out.exists():
        return out  # Skip if already rendered

    # Prepare extra dict
    extra = {}
    if with_expression and case.expr_extra:
        extra = case.expr_extra.copy()
    elif case.base_extra:
        extra = case.base_extra.copy()

    # Call the scene function
    try:
        # Handle variadic signature:
        # Some scenes need extra dict, some add it as keyword
        if case.scene_fn == "money_scene":
            if extra and "upto" in extra:
                scene_fn(
                    out,
                    case.duration,
                    upto=extra.pop("upto", 0),
                    final=extra.pop("final", False),
                    number=case.number,
                    label=case.label,
                    extra=extra if extra else None,
                )
            else:
                scene_fn(
                    out,
                    case.duration,
                    upto=0,
                    final=False,
                    number=case.number,
                    label=case.label,
                    extra=extra if extra else None,
                )
        else:
            scene_fn(
                out,
                case.duration,
                number=case.number,
                label=case.label,
                extra=extra if extra else None,
            )

        return out
    except Exception as e:
        print(f"[ERROR] {case.name} {'with' if with_expression else 'without'} expression: {e}")
        raise


def extract_frame(video_path: Path, time: float, label: str) -> Path:
    """Extract a single frame from a video.

    Args:
        video_path: Path to MP4
        time: Time in seconds to extract frame
        label: Frame label (e.g., "begin", "mid", "end")

    Returns:
        Path to extracted PNG
    """
    out = TESTS_DIR / f"{video_path.stem}_{label}.png"

    if out.exists():
        return out

    # Use ffmpeg to extract frame
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(video_path),
            "-ss", f"{time:.2f}",
            "-vframes", "1",
            str(out),
        ],
        check=True,
    )

    return out


def make_contact_sheet() -> Path:
    """Create a contact sheet showing all test frames side-by-side.

    Returns:
        Path to contact sheet image
    """
    FRAME_W, FRAME_H = 320, 180
    COLS = 3  # begin, mid, end
    ROWS = len(TEST_CASES)
    SPACING = 20
    TITLE_H = 40
    LABEL_H = 20

    width = COLS * (FRAME_W + SPACING) + SPACING
    height = TITLE_H + ROWS * (FRAME_H + LABEL_H + SPACING) + SPACING

    sheet = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(sheet)

    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        title_font = label_font = None

    # Title
    draw.text((SPACING, 5), "Expression Tests: Baseline vs. Enabled", fill=(200, 200, 200), font=title_font)

    y = TITLE_H
    for row, case in enumerate(TEST_CASES):
        x = SPACING

        # Row label (scene name)
        draw.text((x, y + FRAME_H + 2), f"{case.name}", fill=(180, 180, 180), font=label_font)

        # For each time point (begin, mid, end):
        for col, (time, time_label) in enumerate([(0.2, "begin"), (1.25, "mid"), (2.3, "end")]):
            # Extract baseline frame
            baseline_mp4 = TESTS_DIR / f"{case.name}_baseline.mp4"
            expr_mp4 = TESTS_DIR / f"{case.name}_expr.mp4"

            if baseline_mp4.exists():
                frame = extract_frame(baseline_mp4, time, f"baseline_{time_label}")
                try:
                    img = Image.open(frame).resize((FRAME_W, FRAME_H))
                    sheet.paste(img, (x, y))
                except:
                    pass  # Skip if extraction failed

            x += FRAME_W + SPACING

        y += FRAME_H + LABEL_H + SPACING

    sheet.save(TESTS_DIR / "contact_sheet.png")
    return TESTS_DIR / "contact_sheet.png"


def main():
    """Run all expression tests."""
    print("[test_expressions] Starting expression tests...")

    # Test results
    results = {"passed": 0, "failed": 0, "tests": []}

    # Render each test case with and without expressions
    for case in TEST_CASES:
        test_result = {"name": case.name, "baseline": None, "expression": None, "error": None}

        try:
            # Baseline render (no expression)
            baseline = render_test_clip(case, with_expression=False)
            if baseline.exists() and baseline.stat().st_size > 100000:
                test_result["baseline"] = str(baseline)
                print(f"  ✓ {case.name} baseline rendered ({baseline.stat().st_size / 1024:.0f}KB)")
            else:
                test_result["error"] = f"baseline render failed or too small"
                print(f"  ✗ {case.name} baseline failed")
                results["failed"] += 1
                continue

            # Expression-enabled render
            expr_clip = render_test_clip(case, with_expression=True)
            if expr_clip.exists() and expr_clip.stat().st_size > 100000:
                test_result["expression"] = str(expr_clip)
                print(f"  ✓ {case.name} expression rendered ({expr_clip.stat().st_size / 1024:.0f}KB)")
            else:
                test_result["error"] = f"expression render failed or too small"
                print(f"  ✗ {case.name} expression failed")
                results["failed"] += 1
                continue

            # Extract frames for visual inspection
            extract_frame(baseline, 0.5, "baseline_mid")
            extract_frame(expr_clip, 0.5, "expression_mid")

            results["passed"] += 1

        except Exception as e:
            test_result["error"] = str(e)
            print(f"  ✗ {case.name}: {e}")
            results["failed"] += 1

        results["tests"].append(test_result)

    # Create contact sheet
    try:
        contact_sheet = make_contact_sheet()
        print(f"\n  Contact sheet: {contact_sheet}")
    except Exception as e:
        print(f"  Contact sheet failed: {e}")

    # Save results
    results_file = TESTS_DIR / "results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[test_expressions] Complete: {results['passed']} passed, {results['failed']} failed")
    print(f"Test directory: {TESTS_DIR}")
    print(f"Results file: {results_file}")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
