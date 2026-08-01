#!/usr/bin/env python3
"""The healer must receive findings it can ACT on.

THE DEFECT (2026-08-01, shared-air run 30702082224 — real data, both halves
reproduced below). The judging loop produced 6 findings and applied 0 repairs,
then stopped after attempt 1 of 3. Not because the film was unfixable — because
every finding reaching the healer was unaddressable, for two separate reasons:

1. FOUR OF THE FIVE technical "blockers" were stopwatch readings. render_gates
   returns (ok, notes) where notes mixes pass markers, diagnostic context and
   the line that says what broke. judges.technical only filtered the "✓" pass
   markers, so context lines like "total 2684s for 167s of video, 41 shots" and
   "media resolution 839s vs local render 650s" became severity:blocker film
   defects. The repair planner then spent five of six tasks on them, every one
   resolving to "no automated repair for this code".

2. The ONE genuinely repairable finding — the director's STALE_SPAN at
   "112.0-119.5s" — was dropped with "target is a time range, not a beat".
   `_beat_index`'s own docstring said time ranges are mapped "via the beatmap";
   no caller ever passed one. The director ALWAYS reports spans that way (it
   watches the rendered film and has a clock, not a beat list), so this silently
   discarded the entire class of defect the director exists to catch.

Together: a self-healing loop that renders, judges, plans, and heals nothing.
Both halves are pinned here so neither can regress into the other's shadow.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))


def test_gate_stats_are_not_defects():
    """Only the line the gate MARKED as a failure is a complaint."""
    from data_learning.judges import _complaints
    # verbatim from performance.json's gate on the shared-air render
    notes = [
        "total 2684s for 167s of video, 41 shots",
        "kind depict: n=15 median-cost 2.6x first->last 0.84x",
        "kind image: n=12 median-cost 1.2x first->last 0.51x",
        "media resolution 839s vs local render 650s",
        "FAIL: unexplained per-shot outliers: image: 1 shot(s) >3x the kind "
        "median 1.2x",
    ]
    got = _complaints(notes)
    assert got == [notes[-1]], got
    print(f"ok  5 gate lines -> {len(got)} defect (the marked failure), "
          "not 5 blockers")


def test_unmarked_gates_still_report_everything():
    """A gate that does not use the FAIL: marker must not go quiet.

    gate_package reports bare strings ("meta.json missing"). If the filter
    required a marker, a genuinely missing artifact would become invisible —
    trading a noisy healer for a blind one.
    """
    from data_learning.judges import _complaints
    got = _complaints(["✓ srt", "meta.json missing", "thumbnail missing"])
    assert got == ["meta.json missing", "thumbnail missing"], got
    assert _complaints([]) == ["failed"]
    assert _complaints(["✓ all good"]) == ["failed"]
    print("ok  an unmarked gate still reports every failure it names")


def test_a_span_target_resolves_to_a_beat():
    """'112.0-119.5s' is the beat whose span covers its midpoint."""
    from data_learning.auto_repair import _beat_index
    beatmap = {"beats": [{"t": "0.0-15.4"}, {"t": "14.8-25.6"},
                         {"t": "25.6-112.0"}, {"t": "112.0-119.5"},
                         {"t": "119.5-167.0"}]}
    assert _beat_index("112.0-119.5s", 5, beatmap) == 3
    assert _beat_index("0.0-15.4s", 5, beatmap) == 0
    # unchanged forms keep working
    assert _beat_index("beat 7", 10, beatmap) == 7
    assert _beat_index(4, 10, beatmap) == 4
    # honest misses stay misses — never guess a beat
    assert _beat_index("112.0-119.5s", 5, None) is None
    assert _beat_index("900.0-950.0s", 5, beatmap) is None
    assert _beat_index("the ending", 5, beatmap) is None
    print("ok  a span target resolves to its beat (and misses stay honest)")


def test_the_director_finding_now_gets_repaired():
    """End to end: the exact task that was dropped now applies."""
    from data_learning import auto_repair
    plan = {"repair_class": "local", "tasks": [
        {"id": "t006", "defect_code": "STALE_SPAN", "target": "112.0-119.5s"}]}
    story = {"beats": [{"hold": 0}, {"hold": 0}, {"hold": 0},
                       {"hold": 3.0}, {"hold": 0}]}
    beatmap = {"beats": [{"t": "0.0-15.4"}, {"t": "14.8-25.6"},
                         {"t": "25.6-112.0"}, {"t": "112.0-119.5"},
                         {"t": "119.5-167.0"}]}
    revised, journal = auto_repair.apply(plan, story, escalation="local",
                                         beatmap=beatmap)
    assert journal[0]["applied"] is True, journal
    assert revised["beats"][3]["hold"] == 1.5, revised["beats"][3]
    assert story["beats"][3]["hold"] == 3.0, "apply() must not mutate the input"
    # and without a beatmap it still refuses rather than repairing the wrong beat
    _, blind = auto_repair.apply(plan, story, escalation="local")
    assert blind[0]["applied"] is False, blind
    print("ok  the STALE_SPAN that was dropped now halves the right beat's hold")


def test_a_film_can_be_soulless_without_a_single_card():
    """NO_SOUL/SAMENESS must repair something on a film with no card beats.

    The third defect from the same run. Every soul/sameness label resolved to
    one strategy — "convert card beats to scenes" — so on a stock-footage film
    with zero cards the repair was a no-op BY CONSTRUCTION: the finding was
    consumed, the journal said "convert 0 card beat(s)", and nothing changed.
    That is the commonest failure mode of a stock-driven pipeline having no
    repair at all. BORING and LOW_ENERGY were worse: in the judge's vocabulary,
    in no strategy whatsoever.
    """
    from data_learning import auto_repair
    story = {"beats": [
        # anchored: the query depicts what the beat says
        {"narration": "Breathe in. You are holding molecules of air.",
         "image": {"query": "breath cold air winter"}},
        # unanchored: generic wallpaper, shares nothing with its own line
        {"narration": "Air does not stay put. It has no home.",
         "image": {"query": "time lapse clouds sky"}},
        {"narration": "Every person alive exhales into the same pool.",
         "image": {"query": "ocean waves aerial"}},
        {"narration": "The mixing takes about a year.",
         "image": {"query": "green leaves sunlight close up"}},
    ]}
    assert auto_repair._least_anchored(story["beats"]) == [1, 2, 3]
    for code in ("NO_SOUL", "SAMENESS", "EMPTY_COMPOSITION", "BORING",
                 "LOW_ENERGY"):
        plan = {"repair_class": "scene",
                "tasks": [{"id": "x", "defect_code": code, "target": "film"}]}
        revised, journal = auto_repair.apply(plan, story, escalation="scene")
        assert journal[0]["applied"] is True, (code, journal)
        touched = [b for b in revised["beats"]
                   if b.get("_prefer_scene") or b.get("_media_reseed")]
        assert len(touched) == 3, (code, touched)
        assert not revised["beats"][0].get("_prefer_scene"), \
            f"{code} touched the ANCHORED beat — anchoring is what protects it"
    print("ok  a card-less film's soul/sameness/boring labels now repair beats")


def test_anchoring_is_about_the_beats_own_words():
    """The test is film-agnostic: query vs the narration that beat SPEAKS."""
    from data_learning.auto_repair import _anchored
    assert _anchored({"narration": "The glacier is melting fast.",
                      "image": {"query": "glacier ice melting water"}})
    assert not _anchored({"narration": "The glacier is melting fast.",
                          "image": {"query": "two people talking outdoors"}})
    # crude stemming: breathing/breath/breathe are the same subject
    assert _anchored({"narration": "Breathing moves the whole atmosphere.",
                      "image": {"query": "breath cold air"}})
    # A query with no content words carries no evidence either way, so it is
    # NOT flagged. Unanchored must mean "we read the query and it depicts
    # something else", never "we could not read the query" — a healer that
    # rewrites beats it cannot assess is guessing.
    assert _anchored({"narration": "It is what it is.",
                      "image": {"query": "the of and a"}})
    # a designed beat has no query to anchor — never flagged
    assert _anchored({"narration": "Anything at all.", "flat": {"kind": "scene_free"}})
    print("ok  anchoring compares a query to its own beat's spoken words")


if __name__ == "__main__":
    test_gate_stats_are_not_defects()
    test_unmarked_gates_still_report_everything()
    test_a_span_target_resolves_to_a_beat()
    test_the_director_finding_now_gets_repaired()
    test_a_film_can_be_soulless_without_a_single_card()
    test_anchoring_is_about_the_beats_own_words()
    print("all healer-input checks pass")
