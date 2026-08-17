"""Data PERFORMS his bit — at a tempo a human can see.

2026-08-16, three different stories, one verdict in three phrasings: "the
mascot is a sticker", "never does a bit", "a mascot who never performs".
The showrunner was right, and the cause was a units mismatch, not a missing
capability: every action animator is a one-way ARC (setup at phase 0,
climax at 1) and `_bake_host` fed it raw beat progress — which crosses 0..1
ONCE, over a 10-18 second beat. One shove spread across fifteen seconds is
a statue in any window a viewer actually watches. Measured on the real
sprites (mean frame diff per half-second, 15s beat, first ten seconds):

    raw arc       1.0 - 2.1     <- the sticker
    effort reps   5.3 - 19.3    <- alive the whole beat

`_perf_phase` maps beat progress to performance phase: four ping-pong
STRUGGLE reps (strain toward the climax, get pushed back) across the first
80% of the beat, then one committed FINALE run of the whole arc that lands
phase 1.0 exactly on the payoff pose. Ping-pong rather than modulo because
the arcs are not seamless loops — a %-wrap snaps climax back to setup in
one frame, which reads as a glitch; the mirror reads as effort.

    python -m unittest tests.test_mascot_performs -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data_learning import charts as C  # noqa: E402

P = C._perf_phase


class TestThePayoffStillLands(unittest.TestCase):
    """The clamp in `_host_img` ("CLAMP do NOT modulo") took its own bug to
    win — phase 1.0 must land the payoff pose, reps or no reps."""

    def test_phase_one_is_the_payoff(self):
        self.assertAlmostEqual(P(1.0), 1.0, places=6)

    def test_beyond_one_stays_the_payoff(self):
        self.assertAlmostEqual(P(1.3), 1.0, places=6)

    def test_the_finale_is_one_unbroken_run(self):
        """From 80% of the beat the arc plays start-to-climax once, no
        reps — the decisive push after the struggle."""
        pts = [P(0.8 + i * 0.02) for i in range(11)]
        self.assertAlmostEqual(pts[0], 0.0, places=6)
        self.assertAlmostEqual(pts[-1], 1.0, places=6)
        for a, b in zip(pts, pts[1:]):
            self.assertGreater(b, a)


class TestTheStruggleActuallyStruggles(unittest.TestCase):

    def test_four_reps_before_the_finale(self):
        """Count direction changes across [0, 0.8): four ping-pong reps is
        seven reversals. Fewer means the reps degraded back toward the
        single fifteen-second shove."""
        xs = [P(i / 1000) for i in range(800)]
        flips = sum(1 for a, b, c in zip(xs, xs[1:], xs[2:])
                    if (b - a) * (c - b) < 0)
        self.assertEqual(flips, 7)

    def test_the_climax_is_saved_for_the_finale(self):
        """The struggle caps at 0.85 — the audience sees the full climax
        exactly once, at the end. A struggle that reaches 1.0 four times
        spends the payoff before it means anything."""
        peak = max(P(i / 1000) for i in range(800))
        self.assertLessEqual(peak, 0.85 + 1e-9)
        self.assertGreater(peak, 0.80)

    def test_the_tempo_is_working_pace_not_a_blur(self):
        """One rep spans a fifth of the struggle = ~2.4s of a 15s beat and
        ~1.2s of a 6s one. The bound that matters: per-frame phase motion
        at 30fps on the LONGEST beat stays well above the sticker regime."""
        beat_s, fps = 18.0, 30.0
        dt = 1.0 / (beat_s * fps)          # phase step per frame
        deltas = [abs(P(t + dt) - P(t))
                  for t in [i / 500 for i in range(int(0.8 * 500))]]
        self.assertGreater(sum(deltas) / len(deltas), 5 * dt,
                           "reps move the pose less than 5x the raw arc — "
                           "that is the statue again")

    def test_no_wrap_glitch(self):
        """The largest single-frame phase jump anywhere must stay small —
        a modulo wrap would show up here as a ~1.0 discontinuity."""
        step = 1.0 / (10.0 * 30.0)          # worst case: a SHORT 10s beat
        jumps = [abs(P(t + step) - P(t))
                 for t in [i / 2000 for i in range(1999)]]
        self.assertLess(max(jumps), 0.08)


class TestTheBakeUsesIt(unittest.TestCase):

    def test_bake_host_routes_through_perf_phase(self):
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def _bake_host(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("_host_img(action, _perf_phase(phase))", body)

    def test_the_attach_log_keeps_raw_beat_progress(self):
        """The sidecar's phase is the contract the manifest and benchmark
        validator read — it stays beat progress, not performance phase."""
        src = (ROOT / "data_learning" / "charts.py").read_text()
        body = src.split("def _bake_host(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"phase": round(float(min(1.0, max(0.0, phase)))', body)

    def test_the_cache_is_fine_grained_enough_for_reps(self):
        """Six-ish pose reversals across the beat at 40 buckets staircased;
        80 keeps them smooth. The cache key is the only place granularity
        lives."""
        src = (ROOT / "data_learning" / "charts.py").read_text()
        self.assertIn("round(phase * 80) / 80", src)


class TestRepairCannotConvergeTheStory(unittest.TestCase):
    """The other half of "three near-identical template charts": repair sees
    one scene at a time and steered every scene of a story onto rank+*.
    A candidate whose depiction is already on ANOTHER scene now survives
    only when nothing distinct passed the objective gate."""

    SRC = (ROOT / "scripts" / "scene_repair.py").read_text()

    def test_the_distinctness_pass_exists(self):
        self.assertIn("STORY-LEVEL DISTINCTNESS", self.SRC)
        self.assertIn("_elsewhere", self.SRC)

    def test_it_reads_the_other_scenes_current_kinds(self):
        body = self.SRC.split("STORY-LEVEL DISTINCTNESS", 1)[1]
        self.assertIn("j != idx", body)

    def test_it_reads_already_planned_scenes_too(self):
        """Two sequential repairs in one run talk through the plan file —
        without reading it, repair 2 undoes repair 1's variety."""
        body = self.SRC.split("STORY-LEVEL DISTINCTNESS", 1)[1]
        self.assertIn('_k != str(idx)', body)

    def test_a_duplicate_is_a_last_resort_not_a_ban(self):
        """When NOTHING distinct passes the objective gate, the duplicate
        still ships — a repeated depiction beats a broken scene."""
        body = self.SRC.split("STORY-LEVEL DISTINCTNESS", 1)[1].split(
            "ranking = ", 1)[0]
        self.assertIn("if _distinct", body)


class TestCutoutRetries(unittest.TestCase):
    """~110 one-shot HTTP 500s in a single run, each silently downgrading a
    scene toward the plain templates the judge blocks."""

    SRC = (ROOT / "data_learning" / "scene_media.py").read_text()

    def test_three_attempts_with_seed_jitter(self):
        body = self.SRC.split("RETRY WITH A DIFFERENT SEED", 1)[1]
        self.assertIn("range(3)", body)
        self.assertIn("seed + attempt * 7919", body)

    def test_failure_is_still_non_fatal(self):
        body = self.SRC.split("RETRY WITH A DIFFERENT SEED", 1)[1].split(
            "def ", 1)[0]
        self.assertIn("return None", body)


if __name__ == "__main__":
    unittest.main()


class TestExplainerVerdictsSurviveTheRunner(unittest.TestCase):
    """Found while verifying the rotation: explainer's persist step did not
    include the showrunner ledger, so every explainer verdict died with the
    runner. The rotation, repair distinctness and the doctor's evidence all
    read that ledger — they were half-blind for exactly the channel that
    needed them. (Trending was covered by daily.yml's blanket `state/`.)"""

    def test_the_ledger_is_in_the_persist_list(self):
        src = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        persist = src.split("explainer: update posted log", 1)[1].split(
            "shell:", 1)[0]
        self.assertIn("state/showrunner_verdicts.jsonl", persist)
