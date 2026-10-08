"""A beat is about eight seconds, and the budget lives in the registry.

Operator, 2026-10-05: "15 seconds per beat is far too long." Posted beats
ran 26 words (the forge asked for "~22" and nothing held it there) at 130
spoken words a minute. Held here:

  * the live registry carries the budget and shared/pacing.py reads it;
    no other file states a word count;
  * every writer is told it: the forge's prompt, the takeover brief, the
    rewrite mailbox's rules and its say cap;
  * the forge feeds an over-length draft back instead of banking it;
  * the editorial gate HOLDS a story over it as a `pace:` word reason, and
    the mailbox treats that as a rewrite job;
  * `tighten()` compresses a queued story through the mailbox's validator,
    refuses an invented number, persists once, and runs before the gate;
  * the renderer retimes every engine's lines at the budget's tempo BEFORE
    measuring them, and records each window's seconds for the posted log.
"""
from __future__ import annotations

import inspect
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import pacing  # noqa: E402

B = pacing.budget()
LONG = ("In nineteen ninety the share of rural homes with electricity was "
        "sixty one percent and by twenty twenty two it had climbed to eighty "
        "three percent which is a remarkable rise")          # 31 words


def _story(say=LONG, hook="Your town's lights came on 30 years late.",
           closing="The grid got there.", question="Did yours?"):
    return {"slug": "t-pace", "title": "Rural Homes Caught Up On Electricity",
            "hook": hook, "closing": closing, "question": question,
            "segments": [{"topic": "rural power", "say": say},
                         {"topic": "the gap", "say": "The gap closed to 4 points."}]}


class TheBudgetIsTheRegistrys(unittest.TestCase):
    def test_the_live_registry_carries_it_and_pacing_reads_it(self):
        reg = json.loads((ROOT / "config/channel_registry.json").read_text())
        pac = reg["channels"]["explainer"]["formats"]["data_story"]["pacing"]
        for k in pacing.IF_UNSET:
            self.assertIn(k, pac, k)
            self.assertEqual(B[k], type(pacing.IF_UNSET[k])(pac[k]), k)
        self.assertLessEqual(B["say_words"], 18)
        self.assertLessEqual(B["beat_max_s"], 9)
        self.assertGreater(B["tempo"], 1.0)

    def test_no_other_file_states_a_word_count(self):
        for rel in ("scripts/story_forge.py", "shared/authoring_brief.py",
                    "shared/rewrite_mailbox.py"):
            src = (ROOT / rel).read_text()
            self.assertNotRegex(src, r"~\s?22 words|at most 40 words|~22\)", rel)
        self.assertNotIn("= 40", (ROOT / "shared/rewrite_mailbox.py").read_text())

    def test_problems_name_every_line_over_and_nothing_under(self):
        self.assertEqual(pacing.problems(_story(say="Rural power: 61 to 83 percent.")), [])
        probs = pacing.problems(_story())
        self.assertEqual(len(probs), 1)
        self.assertIn("beat 1 says 31 words", probs[0])
        self.assertIn(f"max {B['say_words']}", probs[0])
        probs = pacing.problems(_story(hook=" ".join(["word"] * (B["hook_words"] + 1))))
        self.assertTrue(any(p.startswith("hook is") for p in probs))


class EveryWriterIsTold(unittest.TestCase):
    def test_the_forge_prompt_and_the_brief_and_the_mailbox_state_it(self):
        from scripts import story_forge as SF
        from shared import authoring_brief as AB
        from shared import rewrite_mailbox as RW
        self.assertIn("_pace.rule()", inspect.getsource(SF._brain_words))
        self.assertIn(pacing.rule(), " ".join(RW.RULES))
        self.assertEqual(RW.MAX_SAY_WORDS, B["say_words"])
        self.assertIn("pace:", RW._WORD_PREFIX)
        req = AB.explainer_rewrite_request("20260801") if hasattr(AB, "explainer_rewrite_request") else None
        src = inspect.getsource(AB)
        self.assertIn("_pacing_rule()", src)

    def test_the_forge_feeds_an_over_length_draft_back(self):
        from scripts import story_forge as SF
        dss = [{"key": "k1", "title": "Rural power", "unit": "percent",
                "insight_type": "trend", "geography": "World",
                "points": [{"label": "1990", "value": 61.0}, {"label": "2022", "value": 83.0}]}]
        drafts = [{"title": "Rural Homes Caught Up On Electricity 30 Years Late",
                   "hook": "Your town's lights came on 30 years late.",
                   "closing": "The grid got there.", "question": "Did yours?",
                   "says": [LONG], "hashtags": ["data"]},
                  {"title": "Rural Homes Caught Up On Electricity 30 Years Late",
                   "hook": "Your town's lights came on 30 years late.",
                   "closing": "The grid got there.", "question": "Did yours?",
                   "says": ["Rural power went from 61 percent to 83 percent."],
                   "hashtags": ["data"]}]
        notes = []

        def brain(dss_, reject_note=None):
            notes.append(reject_note)
            return drafts[min(len(notes) - 1, 1)]
        with mock.patch.object(SF, "_brain_words", brain), \
                mock.patch("scripts.editorial_gate.premise_ok",
                           return_value={"ok": True, "reasons": [], "judge": "stub"}), \
                mock.patch("shared.hook_doctrine.floor", return_value=[]):
            w, by = SF._words_that_clear_the_bar(dss)
        self.assertEqual(w["says"][0], drafts[1]["says"][0])
        self.assertIn("pace:", notes[1] or "")
        self.assertIn("brain(attempt 2", by)

    def test_the_deterministic_say_fits(self):
        from scripts import story_forge as SF
        ds = {"title": "Rural power", "unit": "percent", "insight_type": "trend",
              "points": [{"label": "1990", "value": 61.0}, {"label": "2022", "value": 83.0}]}
        self.assertLessEqual(pacing.words(SF._say(ds)), B["say_words"])
        ds["insight_type"] = "rank"
        ds["points"].append({"label": "2030", "value": 90.0})
        self.assertLessEqual(pacing.words(SF._say(ds)), B["say_words"])


class TheGateHoldsAndTheMailboxAsks(unittest.TestCase):
    def test_a_long_beat_is_a_pace_hold_and_a_word_reason(self):
        from scripts import editorial_gate as EG
        from shared import rewrite_mailbox as RW
        sc = _story()
        with mock.patch.object(EG, "data_provenance", return_value={"ok": True, "reasons": []}), \
                mock.patch.object(EG, "data_is_a_finding", return_value={"ok": True, "reasons": []}), \
                mock.patch.object(EG, "beat_numbers_are_on_screen",
                                  return_value={"ok": True, "reasons": [], "notes": []}), \
                mock.patch.object(EG, "premise_ok", return_value={"ok": True, "reasons": [], "judge": "x"}), \
                mock.patch.object(EG, "beats_are_distinct", return_value={"ok": True, "reasons": []}), \
                mock.patch.object(EG, "beats_support_one_thesis",
                                  return_value={"ok": True, "reasons": [], "judge": "x"}):
            v = EG.pre_render_verdict(sc, use_llm=False)
            self.assertFalse(v["ok"])
            self.assertFalse(v["pace_ok"])
            self.assertTrue(any(r.startswith("pace: beat 1 says 31 words") for r in v["reasons"]), v["reasons"])
            holds = RW.word_holds(sc)
        self.assertTrue(any(h.startswith("pace:") for h in holds), holds)

    def test_post_stories_tightens_before_the_gate(self):
        src = (ROOT / "scripts/post_stories.py").read_text()
        self.assertLess(src.index("_pacing.tighten(sc"), src.index("pre = _eg.pre_render_verdict(sc)"))
        self.assertIn('facts["beat_s_max"]', src)


class TightenIsAValidatedRewrite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cfg = self.tmp / "niche.config.json"
        self.cfg.write_text(json.dumps({"stories": [_story()]}, indent=2))
        self.sc = json.loads(self.cfg.read_text())["stories"][0]
        self.good = {"hook": "Your town's lights came on 30 years late.",
                     "closing": "The grid got there.", "question": "Did yours?",
                     "segments": [{"topic": "rural power", "say": "Rural power: 61 percent in 1990, 83 by 2022."},
                                  {"topic": "the gap", "say": "The gap closed to 4 points."}]}

    def _validate_stub(self):
        # the mailbox's validator needs the beats' datasets on disk; here the
        # words are the thing under test, so its number/entity checks are
        # replaced by the pace check alone
        from shared import rewrite_mailbox as RW

        def validate(sc, ans):
            import copy
            cand = copy.deepcopy(sc)
            for k in ("hook", "closing", "question"):
                cand[k] = ans[k]
            for a, c in zip(cand["segments"], ans["segments"]):
                a["say"] = c["say"]
            if re.search(r"\b99\b", json.dumps(ans)):
                return None, ["segment 1: number(s) not derivable from this beat's data: 99"]
            p = pacing.problems(cand)
            return (None, ["still held by the gate: pace: " + p[0]]) if p else (cand, [])
        return mock.patch.object(RW, "validate", validate)

    def test_a_good_rewrite_lands_in_memory_and_on_disk_once(self):
        calls = []
        with self._validate_stub():
            r = pacing.tighten(self.sc, config_path=self.cfg,
                               brain=lambda p: (calls.append(p), json.dumps(self.good))[1], log=lambda m: None)
            self.assertTrue(r["changed"])
            self.assertEqual(self.sc["segments"][0]["say"], self.good["segments"][0]["say"])
            self.assertEqual(self.sc["words_by"], pacing.WORDS_BY)
            on_disk = json.loads(self.cfg.read_text())["stories"][0]
            self.assertEqual(on_disk["segments"][0]["say"], self.good["segments"][0]["say"])
            self.assertEqual(on_disk["words_by"], pacing.WORDS_BY)
            self.assertIn(pacing.rule(), calls[0])
            # inside the budget now: no second brain call
            r2 = pacing.tighten(self.sc, config_path=self.cfg,
                                brain=lambda p: self.fail("asked again"), log=lambda m: None)
        self.assertFalse(r2["changed"])

    def test_an_invented_number_is_refused_and_the_story_is_untouched(self):
        bad = json.loads(json.dumps(self.good))
        bad["segments"][0]["say"] = "Rural power hit 99 percent."
        notes = []
        with self._validate_stub():
            r = pacing.tighten(self.sc, config_path=self.cfg,
                               brain=lambda p: (notes.append(p), json.dumps(bad))[1], log=lambda m: None)
        self.assertFalse(r["changed"])
        self.assertIn("not derivable", r["reasons"][0])
        self.assertEqual(self.sc["segments"][0]["say"], LONG)
        self.assertEqual(json.loads(self.cfg.read_text())["stories"][0]["segments"][0]["say"], LONG)
        self.assertEqual(len(notes), 2)                          # it was told why, and tried again
        self.assertIn("REFUSED", notes[1])

    def test_no_brain_leaves_the_story_to_the_gate(self):
        r = pacing.tighten(self.sc, config_path=self.cfg, brain=lambda p: None, log=lambda m: None)
        self.assertFalse(r["changed"])
        self.assertEqual(r["reasons"], ["no brain answered"])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class TheRendererPlaysItAtTempo(unittest.TestCase):
    def test_every_engine_is_retimed_before_it_is_measured(self):
        from data_learning import studio_render as R
        src = inspect.getsource(R.synth_narration)
        self.assertEqual(src.count("_retime(w, tempo)"), 2)          # elevenlabs, speechify
        self.assertIn("speed=tempo", src)                             # kokoro, natively
        for m in re.finditer(r"_retime\(w, tempo\)\n(\s+)d = _dur\(w\)", src):
            pass
        self.assertEqual(len(re.findall(r"_retime\(w, tempo\)\s+d = _dur\(w\)", src)), 2)
        self.assertNotIn("speed=1.10", src)
        self.assertEqual(R._tempo(), B["tempo"])

    def test_retime_shortens_a_line_by_the_tempo(self):
        from data_learning import studio_render as R
        tmp = Path(tempfile.mkdtemp())
        w = tmp / "s0.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "sine=frequency=440:duration=2.0", "-ar", "24000", str(w)], check=True)
        before = R._dur(w)
        R._retime(w, 1.25)
        after = R._dur(w)
        self.assertAlmostEqual(after, before / 1.25, delta=0.05)
        R._retime(w, 1.0)
        self.assertAlmostEqual(R._dur(w), after, delta=0.01)

    def test_the_sidecar_carries_every_windows_seconds(self):
        src = (ROOT / "data_learning/studio_render.py").read_text()
        self.assertIn('_style["beat_s"] = [round(b - a, 2) for a, b in windows]', src)
        self.assertIn('_style["tempo"] = _tempo()', src)


if __name__ == "__main__":
    unittest.main()
