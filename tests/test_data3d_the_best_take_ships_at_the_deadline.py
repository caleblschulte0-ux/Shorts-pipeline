"""A 3D short ships at the deadline (tools/data3d/daily/ship.py, 2026-11-28).

The operator: "a shot should take 2-3 render+judge rounds max" (2026-11-25) and, after the lava short spent 90 hours in
the judge loop with no video, "make this into a fully autonomous system that produces a new 3d video in a timely
manner like at the very least 1 a day" (2026-11-28). The only way out of the loop used to be a pass."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "data3d" / "daily"))
import ship

SCRIPT = {"lines": ["a", "b", "c"]}


def _round(rows):
    return "## 2026-11-28 00:00Z · storyboard\n\n| shot | score | panel | result |\n|---|---|---|---|\n" + \
        "".join(f"| {n} | {s} | - | {r} |\n" for n, s, r in rows) + "\n"


def test_a_shot_that_never_passed_holds_the_video_only_until_its_third_round():
    two = _round([(1, 72, "PASS"), (2, 40, "FAIL"), (3, 71, "PASS")]) + _round([(2, 55, "FAIL")])
    assert ship.owed("x", SCRIPT, two) and "shot 2" in ship.owed("x", SCRIPT, two)[0]
    assert ship.owed("x", SCRIPT, two + _round([(2, 0, "FAIL")])) == []


def test_a_shot_nobody_judged_is_owed_its_rounds():
    assert len(ship.owed("x", SCRIPT, "")) == 3


def test_a_kept_pass_counts_as_a_pass():
    assert ship.owed("x", {"lines": ["a"]}, _round([(1, 74, "PASS (kept)")])) == []


def test_a_story_of_the_daily_pipeline_ships_without_a_panel():
    assert ship.owed("x", dict(SCRIPT, pipeline="daily"), "") == []


def test_the_ship_workflow_asks_the_rule_and_never_posts():
    wf = (ROOT / ".github" / "workflows" / "data3d_ship.yml").read_text()
    assert "daily/ship.py check" in wf
    assert "STAGING: 'on'" in wf
    for word in ("post_data3d", "videos.insert", "data3d_upload", "YOUTUBE", "TIKTOK"):
        assert word not in wf.split("\njobs:\n", 1)[1], word


def test_lava_has_had_its_rounds():
    assert ship.owed("lava") == []
