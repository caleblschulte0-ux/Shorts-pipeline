#!/usr/bin/env python3
"""Unit tests for perf_instrument module."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_learning import perf_instrument as perf


def test_basic_timing():
    """Test basic stage timing."""
    perf.init_render("test_story", 2, 5)

    with perf.stage("test_stage_1"):
        time.sleep(0.1)

    with perf.stage("test_stage_2"):
        time.sleep(0.05)

    metrics = perf.end_render(10.0, 10.0)

    assert metrics is not None
    assert metrics.story_slug == "test_story"
    assert "test_stage_1" in metrics.stages
    assert "test_stage_2" in metrics.stages
    assert metrics.stages["test_stage_1"]["elapsed_s"] >= 0.1
    assert metrics.stages["test_stage_2"]["elapsed_s"] >= 0.05
    print("✓ test_basic_timing passed")


def test_shot_metrics():
    """Test per-shot tracking."""
    perf.init_render("shot_test", 1, 3)

    for i in range(3):
        perf.start_shot(i, f"shot_kind_{i}", 2.5)
        with perf.stage("render", "frame_render"):
            time.sleep(0.02)
        perf.end_shot()

    metrics = perf.end_render(7.5, 7.5)

    assert len(metrics.shots) == 3
    for i, shot in enumerate(metrics.shots):
        assert shot.shot_idx == i
        assert shot.planned_duration_s == 2.5
        assert shot.frame_render_s > 0
    print("✓ test_shot_metrics passed")


def test_memory_capture():
    """Test memory snapshot capture."""
    snap = perf._capture_memory()
    assert snap.rss_mb >= 0
    assert snap.available_mb >= 0
    assert snap.fd_count >= 0
    print(f"✓ test_memory_capture passed (RSS: {snap.rss_mb:.1f}MB, FD: {snap.fd_count})")


def test_report_generation():
    """Test JSON and summary report generation."""
    perf.init_render("report_test", 1, 2)

    for i in range(2):
        perf.start_shot(i, f"kind_{i}", 2.5)
        with perf.stage("render", "frame_render"):
            time.sleep(0.01)
        perf.end_shot()

    metrics = perf.end_render(5.0, 5.0)

    json_report = perf.report_json(metrics)
    assert "report_test" in json_report
    assert "shots" in json_report

    summary = perf.report_summary(metrics)
    assert "report_test" in summary
    assert "5.0s" in summary or "5.0" in summary
    print("✓ test_report_generation passed")


if __name__ == "__main__":
    test_basic_timing()
    test_shot_metrics()
    test_memory_capture()
    test_report_generation()
    print("\n✓ All perf_instrument tests passed!")
