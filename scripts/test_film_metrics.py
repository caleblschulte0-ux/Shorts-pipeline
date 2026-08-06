#!/usr/bin/env python3
"""The shot-plan scorer must catch the regression that cost twelve hours.

On 2026-08-01/02 five full renders of one story were judged, 2.5-4.5 hours
each. Two of the five changes made the film measurably worse and there was no
way to know until the video existed and a blind judge had looked at it:

    attempt  figure shots  overall  personality
    1        14            4.0      2
    3        14            3.5      2
    4         0            3.5      2     <- the library ban removed every human
    5         0            3.0      1     <- judge adds NO_CHARACTER

Column two is a property of the SHOT PLAN. It needs no media, no ffmpeg, no
judge and no network. These tests prove the scorer would have refused that
change in milliseconds, which is the entire justification for the module.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from shared import film_metrics as fm  # noqa: E402

def score(shots, beats=None, *, duration_source="estimated"):
    """Every fixture here is a hand-written plan, so its seconds are all of a
    kind. Saying so is the whole point: `compare` refuses two dicts that do
    not agree on where their seconds came from, and a test that let itself
    off that requirement would not be exercising the code that ships."""
    return fm.score_plan(shots, beats, duration_source=duration_source)


# The real attempt-1 shape: figures present, some real media, some cards.
A1 = ([{"kind": "scene_free", "seconds": 4.0}] * 14
      + [{"kind": "depict", "seconds": 5.0, "motion_query": "child running",
          "line": "a child running in the sun"}] * 15
      + [{"kind": "image", "seconds": 4.0}] * 12)
# The attempt-4 shape: every figure replaced by stock.
A4 = ([{"kind": "depict", "seconds": 5.0, "motion_query": f"thing {i}",
        "line": f"a line about thing {i}"} for i in range(29)]
      + [{"kind": "image", "seconds": 4.0}] * 8)


def test_the_regression_is_visible_without_a_render():
    before, after = score(A1), score(A4)
    # `figure_shots` counts a human on screen BY ANY MEANS — the 14 pictogram
    # scenes plus the 15 "child running" clips, which contain a person too.
    # It used to count only `scene_*`, which made a film carried entirely by
    # real footage of people score zero characters. Both halves stay visible
    # so the original regression is still legible as what it was.
    assert before["pictogram_shots"] == 14, before
    assert before["live_figure_shots"] == 15, before
    assert before["figure_shots"] == 29, before
    # A4 is the ban: no scenes, and stock of "thing N" — not one human left.
    assert after["pictogram_shots"] == 0 and after["live_figure_shots"] == 0, after
    assert after["figure_shots"] == 0, after
    cmp = fm.compare(before, after)
    assert cmp["verdict"] == "REGRESSION", cmp
    assert any("figure_shots" in x for x in cmp["regressed"]), cmp
    print(f"ok  the character loss shows up as {cmp['verdict']}: {cmp['regressed']}")


def test_a_film_of_REAL_PEOPLE_is_not_called_characterless():
    """The metric's name was a lie and it had the sign backwards.

    Every blind judge's memorable frame was real footage of a person, and
    every one of them called the drawn pictograms the worst thing on screen.
    A scorer that counts only pictograms would refuse a film for replacing
    clip art with people — the opposite of what the evidence asks for.
    """
    live = score([{"kind": "depict", "seconds": 4.0,
                           "motion_query": "person standing still",
                           "line": "x"}] * 6)
    assert live["figure_shots"] == 6, live
    assert live["pictogram_shots"] == 0 and live["live_figure_shots"] == 6, live
    assert fm.guard(score(A1), live) == [], (
        "a film of real people must not trip the no-character guard")
    print("ok  real footage of people counts as characters on screen")


def test_the_guard_refuses_it_outright():
    """Some changes are never worth making whatever else improves."""
    bad = fm.guard(score(A1), score(A4))
    assert bad and "ZERO" in bad[0], bad
    # and it does not fire on a change that keeps people on screen
    ok = fm.guard(score(A1), score(A1[:20]))
    assert ok == [], ok
    print(f"ok  guard refuses the figure-wipe: {bad[0]}")


def test_compare_reports_regressions_not_only_wins():
    """Reporting only the wins is how the figure-wipe shipped as a fix."""
    before = score(A1)
    # a change that removes duplicates AND every figure: one win, one loss
    after = score(A4)
    cmp = fm.compare(before, after)
    assert cmp["regressed"], cmp
    assert cmp["verdict"] == "REGRESSION", (
        "any regression must dominate, or a mixed change reads as progress")
    print("ok  a mixed change reads as REGRESSION, not 'improvement'")


def test_a_SCENE_SHOWING_A_BIG_NUMBER_is_a_card():
    """A renamed money bar is still a money bar.

    `card_fraction` counted `flat_*` only and reported money-goes at 15% while
    the blind judge, looking at the frames, estimated 40% and fired
    CARDS_OVER_BUDGET — the rubric's "#1 killer". The gap was the designed
    scenes that display a giant number and a caption: on screen those are stat
    plates, and only their class name says "character".
    """
    plate = {"kind": "scene_money", "seconds": 4.0, "props": True,
             "number": "$2,400", "label": "LEFT THIS MONTH"}
    person = {"kind": "scene_free", "seconds": 4.0, "props": False}
    m = score([plate] * 3 + [person] * 3)
    assert m["plate_scene_fraction"] == 0.5, m
    assert m["card_fraction"] == 0.5, m
    assert m["flat_card_fraction"] == 0.0, m
    # ...and a propless scene, which carries no number and no label, is not
    # a card: it is the person alone, which is what the rubric asks for.
    only_people = score([person] * 4)
    assert only_people["card_fraction"] == 0.0, only_people
    print("ok  a scene displaying a number counts as a card; a bare figure does not")


def test_duplicate_media_is_counted():
    """36 slots / 32 clips was real, and a judge named the pairs by timestamp."""
    dupes = [{"kind": "depict", "seconds": 4.0, "motion_query": "reeds in wind"},
             {"kind": "depict", "seconds": 4.0, "motion_query": "reeds in wind"},
             {"kind": "depict", "seconds": 4.0, "motion_query": "ocean waves"}]
    m = score(dupes)
    assert m["duplicate_media"] == 1, m
    assert m["distinct_media"] == 2, m
    print("ok  a repeated media query is counted before it is ever fetched")


def test_unanchored_media_is_counted():
    """A query sharing no word with its line would serve any other beat."""
    m = score([
        {"kind": "depict", "seconds": 4, "motion_query": "glacier ice melting",
         "line": "The glacier is melting fast."},
        {"kind": "depict", "seconds": 4, "motion_query": "two people talking",
         "line": "The glacier is melting fast."},
    ])
    assert m["anchorable_media"] == 2 and m["unanchored_media"] == 1, m
    print("ok  an unanchored query is counted against the plan")


def test_not_measured_is_None_never_zero():
    """A false zero on an unmeasured axis manufactures fake regressions.

    This module did exactly that on its own first real comparison: a plan
    rebuilt from performance.json carries no media queries, scored
    unanchored_media=0, and comparing a real plan against it reported
    "REGRESSION: unanchored 0 -> 8" for a change that improved the film.
    """
    blind = score([{"kind": "scene_free", "seconds": 4.0}])
    assert blind["duplicate_media"] is None, blind
    assert blind["unanchored_media"] is None, blind
    assert blind["unanchored_fraction"] is None, blind
    assert "n/a" in blind["summary"], blind["summary"]
    # ...and compare() then declines to judge that axis at all
    real = score([{"kind": "depict", "seconds": 4.0,
                           "motion_query": "x y", "line": "nothing alike"}])
    cmp = fm.compare(blind, real)
    assert not any("unanchored" in x for x in cmp["regressed"]), cmp
    print("ok  an unmeasured axis is None, and compare() skips it")


def test_an_empty_plan_does_not_explode():
    """Metrics must never be the thing that breaks a render."""
    m = score([])
    assert m["shots"] == 0 and m["figure_shots"] == 0, m
    assert isinstance(m["summary"], str), m
    assert fm.compare(m, m)["verdict"] == "no change"
    print("ok  an empty plan scores cleanly instead of raising")


def test_the_ledger_round_trips_and_trends():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "led.jsonl"
        # five weak renders, then five better ones
        for i in range(5):
            fm.record("s", score(A4), path=f,
                      verdict={"overall_10": 3.0, "personality": 1})
        for i in range(5):
            fm.record("s", score(A1), path=f,
                      verdict={"overall_10": 6.0, "personality": 3})
        rows = fm.history(f)
        assert len(rows) == 10, len(rows)
        t = fm.trend(rows, n=5)
        assert t["enough_data"] and t["direction"] == "better", t
        assert t["delta_overall"] == 3.0, t
        # ...and it says "worse" when it is worse, not just when it is better
        t2 = fm.trend(list(reversed(rows)), n=5)
        assert t2["direction"] == "worse", t2
    print("ok  the ledger records, reads back, and reports BOTH directions")


def test_trend_refuses_to_judge_too_little_data():
    """A retro that launders noise into a mandate is worse than none."""
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "led.jsonl"
        fm.record("s", score(A1), path=f,
                  verdict={"overall_10": 4.0, "personality": 2})
        assert fm.trend(fm.history(f), n=5)["enough_data"] is False
    print("ok  trend refuses to call a direction without two full windows")


def test_unanchored_is_reported_not_repaired():
    """A number that can be satisfied without improving the film gets no lever.

    Deriving queries from narration took unanchored 8/15 -> 0/15 and produced
    'every argument anyone ever' and 'means next person breathe' — unsearchable
    verb salad that would degrade every beat to a card. The metric is advisory;
    `unanchored_beats` hands an author the evidence and suggests nothing.
    """
    assert fm.UNANCHORED_IS_ADVISORY is True
    assert "unanchored_media" not in fm.__dict__.get("REPAIRABLE", {}), \
        "unanchored must never be wired to an automatic transformation"
    rows = fm.unanchored_beats([
        {"kind": "depict", "motion_query": "two people talking outdoors",
         "line": "Every argument anyone has ever had ended with them exhaling."},
        {"kind": "depict", "motion_query": "glacier ice melting",
         "line": "The glacier is melting."},
    ])
    assert len(rows) == 1, rows
    assert rows[0]["query"] == "two people talking outdoors", rows
    assert "argument" in rows[0]["line"], rows
    assert "suggestion" not in rows[0] and "fix" not in rows[0], (
        "the module must not propose a replacement query — the one it tried "
        "was word salad")
    print("ok  unanchored beats are reported to an author, never auto-rewritten")


def test_a_defect_seen_once_is_not_a_code_problem():
    """The sample-size-of-one error that produced two regressions in five.

    UI_WIDGET appeared in ONE verdict. The response was a code change that
    banned the whole scene library, which deleted every human in the film and
    cost a full point. A label has to survive a render before it is evidence
    about the machine rather than about that film.
    """
    rows = [{"head": "aaaaaaaa", "reject_labels": ["UI_WIDGET"]},
            {"head": "bbbbbbbb", "reject_labels": ["SAMENESS", "NO_CHARACTER"]},
            {"head": "cccccccc", "reject_labels": ["SAMENESS"]}]
    r = fm.recurring_defects(rows, n=5)
    assert list(r["recurring"]) == ["SAMENESS"], r
    assert r["recurring"]["SAMENESS"] == ["bbbbbbbb", "cccccccc"], r
    assert set(r["once"]) == {"UI_WIDGET", "NO_CHARACTER"}, r
    assert r["n_judged"] == 3, r
    print("ok  one sighting is a film problem; two is a code problem")


def test_recurrence_says_nothing_when_nothing_was_judged():
    r = fm.recurring_defects([{"head": "x"}, {"head": "y"}], n=5)
    assert r["recurring"] == {} and r["once"] == {} and r["n_judged"] == 0, r
    print("ok  unjudged renders produce no mandate")


def test_a_flat_window_is_itself_a_finding():
    """Five renders that never move mean the changes are the wrong changes."""
    flat = [{"overall_10": 4.0} for _ in range(5)]
    assert fm.stagnant(flat, n=5), "a dead-flat window must be reported"
    down = [{"overall_10": v} for v in (4.0, 4.0, 3.5, 3.5, 3.0)]
    assert "no better than" in fm.stagnant(down, n=5)
    up = [{"overall_10": v} for v in (3.0, 3.5, 4.0, 5.0, 6.0)]
    assert fm.stagnant(up, n=5) is None, "real movement must not be nagged"
    # ...and it refuses to call a window that has not happened yet
    assert fm.stagnant([{"overall_10": 4.0}], n=5) is None
    print("ok  stagnation is reported, and only once there is a full window")


def test_the_planner_does_not_rewrite_authored_queries():
    """The reverted change, pinned so it is not re-attempted."""
    import json
    from pathlib import Path as _P
    from data_learning import planner
    beats = [{"job": "DEVELOP", "mode": "footage",
              "narration": "Every argument anyone has ever had ended with them exhaling.",
              "understand": "a real person mid-conversation",
              "image": {"query": "two people talking outdoors"}}]
    got = planner._motion_subject(beats[0], beats[0]["image"])
    assert got == "two people talking outdoors", (
        f"the planner rewrote an authored query to {got!r} — that path was "
        "reverted on 2026-08-02 because it produced unsearchable verb salad")
    print("ok  the planner keeps the authored query instead of guessing one")


def test_estimated_and_measured_seconds_are_NEVER_diffed():
    """THE BUG THIS EXISTS FOR, reproduced exactly.

    2026-08-06. `quality_sprint check` scores a plan with a flat 5.0s per beat
    so it can answer in milliseconds. `produce()` records renders with real
    TTS durations. `check` diffed one against the other and printed

        -  shot_lengths 31 -> 17
        -  length_span_s 9.55 -> 4.5
              => REGRESSION

    on a change that touched nothing but how figures were COUNTED. The whole
    delta was the units. Beat length decides how many shots a beat chunks
    into, so it moves every count in the dict, and the cut metrics ARE
    lengths.

    That REGRESSION was about to refuse the next render — the guard would have
    spent its authority on a fight with its own arithmetic. A gate that fires
    on everything is indistinguishable from one that fires on nothing, except
    that people eventually turn it off.
    """
    plan = [{"kind": "scene_free", "seconds": 5.0}] * 10
    est = score(plan, duration_source="estimated")
    # same shots, real narration lengths — a longer film, same structure
    meas = score([{"kind": "scene_free", "seconds": 9.2}] * 10,
                 duration_source="measured")
    cmp = fm.compare(est, meas)
    assert cmp["verdict"] == "incomparable", cmp
    assert not cmp["regressed"], (
        "a units mismatch must produce NO findings — a fabricated regression "
        "is worse than silence, because it teaches the reader to ignore real "
        "ones")
    assert fm.guard(est, meas) == [], "a guard must not fire on a unit mismatch"
    print("ok  estimated vs measured seconds is 'incomparable', not REGRESSION")


def test_a_row_that_does_not_say_is_incomparable_with_everything():
    """Including with itself. Every ledger row written before this change is
    `unknown`; those renders were real, but nothing recorded their provenance,
    and inferring it now would be the same guess this module refuses when it
    writes `None` for an unmeasured axis."""
    old = score([{"kind": "scene_free", "seconds": 4.0}] * 8,
                duration_source="unknown")
    assert fm.compare(old, old)["verdict"] == "incomparable"
    new = score([{"kind": "scene_free", "seconds": 4.0}] * 8)
    assert fm.compare(old, new)["verdict"] == "incomparable"
    assert fm.compare(new, new)["verdict"] == "no change", (
        "two tagged, matching scores must still compare normally")
    print("ok  an untagged row is incomparable, with anything, including itself")


def test_the_plan_history_is_SEPARATE_from_the_render_ledger():
    """A free offline score must never land in the window `trend()` averages.

    The two files answer different questions — 'did this change help' costs
    milliseconds and has no verdict; 'is the channel improving' costs hours
    and is nothing but verdicts. Mixing them lets a shell loop running `check`
    flood the trend with verdict-less rows and flatten it to no-signal.
    """
    with tempfile.TemporaryDirectory() as d:
        snaps = Path(d) / "snap.jsonl"
        ledger = Path(d) / "ledger.jsonl"
        m = score(A1)
        fm.snapshot("s", m, note="offline", head="aaa", path=snaps)
        fm.record("s", m, verdict={"overall_10": 4.5, "personality": 3,
                                   "reject_labels": [], "pass": True},
                  note="rendered", head="bbb", path=ledger)
        got = fm.snapshots("s", path=snaps)
        assert len(got) == 1 and got[0]["head"] == "aaa"
        assert "overall_10" not in got[0], (
            "a snapshot carries no score — it never watched a film")
        assert len(fm.history(ledger)) == 1
        assert fm.history(ledger)[0]["overall_10"] == 4.5
    print("ok  offline plan scores and judged renders live in separate files")


if __name__ == "__main__":
    test_estimated_and_measured_seconds_are_NEVER_diffed()
    test_a_row_that_does_not_say_is_incomparable_with_everything()
    test_the_plan_history_is_SEPARATE_from_the_render_ledger()
    test_the_regression_is_visible_without_a_render()
    test_a_film_of_REAL_PEOPLE_is_not_called_characterless()
    test_the_guard_refuses_it_outright()
    test_a_SCENE_SHOWING_A_BIG_NUMBER_is_a_card()
    test_compare_reports_regressions_not_only_wins()
    test_duplicate_media_is_counted()
    test_unanchored_media_is_counted()
    test_not_measured_is_None_never_zero()
    test_an_empty_plan_does_not_explode()
    test_the_ledger_round_trips_and_trends()
    test_trend_refuses_to_judge_too_little_data()
    test_unanchored_is_reported_not_repaired()
    test_a_defect_seen_once_is_not_a_code_problem()
    test_recurrence_says_nothing_when_nothing_was_judged()
    test_a_flat_window_is_itself_a_finding()
    test_the_planner_does_not_rewrite_authored_queries()
    print("all film-metrics checks pass")
