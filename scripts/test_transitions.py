#!/usr/bin/env python3
"""Every cut was the same dissolve, and the timing sum had no owner.

THE DEFECT. `pro_render.XFADE = 0.6`, applied to every join. A 39-shot film is
38 identical 0.6-second crossfades and never once hard-cuts. A dissolve says
"time passed" or "these belong together"; saying it 38 times in a row says
nothing, and it drains energy — a hard cut between two moving shots is the
cheapest way to make an edit feel alive. LOW_ENERGY appeared in two blind
verdicts and BORING in four.

THE RISK, WHICH IS WHY THIS FILE IS MOSTLY ARITHMETIC. Per-join overlaps mean
there is no constant left to re-derive shot start times from, and those times
drive THREE separate consumers: the voice-over delays, the SRT cue times, and
the beatmap that chapters and the repair loop read. Get the sum wrong and the
film desyncs from its own captions — silently, with everything green. So the
sum lives in one function, `transitions.starts`, and the tests below check it
against what ffmpeg actually produces rather than against itself.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from shared import transitions as T  # noqa: E402
from data_learning import planner  # noqa: E402


def test_a_still_is_never_CUT_INTO():
    """The documented rule from `footage_hybrid`, kept exactly."""
    assert T.join_for({"kind": "depict", "_beat": 0},
                      {"kind": "image", "_beat": 1}) == T.DISSOLVE
    assert T.join_for({"kind": "scene_free", "_beat": 0},
                      {"kind": "image_text", "_beat": 1}) == T.DISSOLVE
    print("ok  never a hard cut INTO a held still")


def test_cutting_OUT_of_a_still_is_allowed():
    """The rule is about the arrival, and applying it wider changed nothing.

    Dissolving both sides of every still left 33 dissolves and 5 cuts out of
    38 joins on shared-air, because the plan alternates depict/image and
    almost every join touches a still.
    """
    assert T.join_for({"kind": "image", "_beat": 0},
                      {"kind": "depict", "_beat": 1}) == T.CUT
    print("ok  leaving a still on a cut is allowed — the rule is about arrival")


def test_a_join_inside_one_beat_dissolves():
    """Same source, different phase: a hard cut there is a jump cut."""
    assert T.join_for({"kind": "depict", "_beat": 3},
                      {"kind": "depict", "_beat": 3}) == T.DISSOLVE
    assert T.join_for({"kind": "depict", "_beat": 3},
                      {"kind": "depict", "_beat": 4}) == T.CUT
    print("ok  within a beat dissolves; across beats cuts")


def test_starts_is_the_ONLY_timing_sum():
    """Three consumers, one function. Checked against the old constant."""
    secs = [4.0, 2.0, 5.0, 3.0]
    uniform = [0.6] * 3
    st = T.starts(secs, uniform)
    # exactly what `offset += seconds[i] - XFADE` used to produce
    assert st == [0.0, 3.4, 4.8, 9.2], st
    assert abs(T.total(secs, uniform) - (sum(secs) - 3 * 0.6)) < 1e-9
    # a short final join list (or none) must not raise or silently shift
    assert T.starts(secs, []) == [0.0, 4.0, 6.0, 11.0]
    assert T.starts([], []) == [] and T.total([], []) == 0.0
    print("ok  starts() reproduces the old uniform sum and survives edge cases")


def test_the_sum_matches_what_ffmpeg_ACTUALLY_produces():
    """The one that matters. Arithmetic agreeing with itself proves nothing."""
    from data_learning import footage_hybrid as fh
    secs = [3.0, 2.0, 4.0, 2.5]
    joins = [T.CUT, T.DISSOLVE, T.CUT]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        clips = []
        for i, s in enumerate(secs):
            c = d / f"c{i}.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", f"testsrc=size=320x180:rate=30:duration={s}",
                 "-t", str(s), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 str(c)], check=True)
            clips.append(c)
        out = d / "joined.mp4"
        fh.dissolve_join(clips, out, xfade=joins)
        actual = fh._duration(out)
    predicted = T.total(secs, joins)
    assert abs(predicted - actual) < 0.10, (
        f"predicted {predicted:.3f}s but ffmpeg produced {actual:.3f}s — the "
        "voice, the captions and the beatmap all derive their positions from "
        "this sum, so a drift here desyncs the film from its own subtitles")
    print(f"ok  ffmpeg agrees with starts(): {predicted:.2f}s vs {actual:.2f}s")


def test_a_wrong_length_list_is_REFUSED_not_padded():
    """Silently padding would desync the tail of every film that hit it."""
    from data_learning import footage_hybrid as fh
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        clips = []
        for i in range(3):
            c = d / f"c{i}.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "testsrc=size=320x180:rate=30:duration=1",
                 "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 str(c)], check=True)
            clips.append(c)
        try:
            fh.dissolve_join(clips, d / "x.mp4", xfade=[0.5])
        except RuntimeError as e:
            assert "2 joins" in str(e), e
        else:
            raise AssertionError("a 1-value list for 2 joins was accepted")
    print("ok  a length mismatch is refused, not quietly padded")


def test_a_scalar_still_works():
    """Every other caller (footage_preview, the perf harness) passes a float."""
    assert T.starts([2.0, 2.0], [0.6]) == [0.0, 1.4]
    print("ok  the scalar path is unchanged for existing callers")


def test_the_real_films_actually_get_hard_cuts():
    """Wiring, on the two stories in the current sprint."""
    for slug, floor in (("shared-air", 12), ("money-goes", 10)):
        beats = json.loads(
            (REPO / "data_learning" / "pro_stories" / f"{slug}.beats.json")
            .read_text())["beats"]
        shots = planner.plan_story(beats, [5.0] * len(beats))
        joins = T.plan_joins(shots)
        assert len(joins) == len(shots) - 1, (slug, len(joins), len(shots))
        cuts = sum(1 for j in joins if j <= T.CUT + 1e-9)
        assert cuts >= floor, (
            f"{slug} plans only {cuts} hard cuts in {len(joins)} joins — it "
            "was 0, and a film that never cuts is what LOW_ENERGY describes")
        print(f"ok  {slug}: {T.summary(joins)}")


if __name__ == "__main__":
    test_a_still_is_never_CUT_INTO()
    test_cutting_OUT_of_a_still_is_allowed()
    test_a_join_inside_one_beat_dissolves()
    test_starts_is_the_ONLY_timing_sum()
    test_the_sum_matches_what_ffmpeg_ACTUALLY_produces()
    test_a_wrong_length_list_is_REFUSED_not_padded()
    test_a_scalar_still_works()
    test_the_real_films_actually_get_hard_cuts()
    print("all transition checks pass")
