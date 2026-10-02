"""The story scout reads what the clips SHOW, not only what strangers typed.

2026-10-01: the scout proposed three stories and the director, holding the
transcripts and frames, refused all three because the footage did not say
what the titles did —

    "The boar snipe never appears: the 9h40 clip shows Summit1g dying, but
     the transcript and frames never show a boar or any cause."
    "No clip shows a capture, a revenge or a release on bail."

Every one of those clips had just been downloaded, transcribed and looked
at, and the run threw it away. Nothing stopped tomorrow's scout proposing
the same three stories from the same titles. `clip_memory` keeps what was
watched and what was refused; these tests hold that the catalogue carries
it, the scout is told, a refused story is not re-analysed, the director may
tell the smaller story a padded proposal really holds — and that a "story"
of one clip is still refused.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from third_capture import clip_memory as cm              # noqa: E402
from third_capture import storyline as sl                # noqa: E402
from third_capture import story_director as sd           # noqa: E402


def _url(slug, ch="summit1g"):
    return f"https://www.twitch.tv/{ch}/clip/{slug}"


def _clip(slug, title, date_="2026-10-01", ch="summit1g", posted=False,
          views=None):
    c = {"source_url": _url(slug, ch), "title": title, "channel": ch,
         "date": date_, "posted": posted}
    if views:
        c["views"] = views
    return c


# ---------------------------------------------------------------- memory
class TheMemoryKeepsWhatWasWatched(unittest.TestCase):
    def test_a_transcript_never_erases_a_scene_summary(self):
        mem = cm.empty()
        cm.note_clip(mem, _url("boar"), day="2026-10-01",
                     saw="Summit1g dies in a field; no attacker visible",
                     people=["Summit1g"])
        cm.note_clip(mem, _url("boar"), said="what the hell just happened")
        ev = cm.evidence(mem, _url("boar"))
        self.assertIn("no attacker visible", ev)
        self.assertIn("what the hell just happened", ev)

    def test_unknown_clip_has_no_evidence(self):
        self.assertEqual(cm.evidence(cm.empty(), _url("never")), "")

    def test_round_trip_and_tolerant_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            mem = cm.empty()
            cm.note_clip(mem, _url("a"), day="2026-10-01", saw="x happens")
            cm.save(mem, p, today=date(2026, 10, 2))
            self.assertIn("x happens", cm.evidence(cm.load(p), _url("a")))
            p.write_text("{torn")
            self.assertEqual(cm.load(p), cm.empty(),
                             "learning state, not dedupe state: a corrupt "
                             "file costs re-analysis, never a run")

    def test_old_entries_age_out(self):
        mem = cm.empty()
        cm.note_clip(mem, _url("old"), day="2026-07-01", saw="old")
        cm.note_clip(mem, _url("new"), day="2026-10-01", saw="new")
        cm.note_story_tried(mem, [_url("old"), _url("o2")], why="no",
                            day="2026-07-01")
        out = cm.prune(mem, today=date(2026, 10, 2))
        self.assertEqual(set(out["clips"]), {sl.clip_key(_url("new"))})
        self.assertEqual(out["stories_tried"], [])

    def test_a_full_memory_is_still_a_small_file(self):
        """state/ is for small JSON (<256KB): fill every field to its cap."""
        mem = cm.empty()
        for i in range(cm.MAX_CLIPS + 200):
            cm.note_clip(mem, _url(f"Clip{i:05d}AbcdefGhijklMnopq-xyz12345"),
                         day="2026-10-01", channel="x" * 30,
                         saw="w" * 400, said="s" * 400,
                         people=["p" * 40] * 6)
        for i in range(cm.MAX_STORIES + 20):
            cm.note_story_tried(mem, [_url(f"a{i}"), _url(f"b{i}"),
                                      _url(f"c{i}")],
                                premise="p" * 300, why="w" * 300,
                                day="2026-10-01")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "m.json"
            cm.save(mem, p, today=date(2026, 10, 2))
            size = p.stat().st_size
            kept = json.loads(p.read_text())
        self.assertLessEqual(len(kept["clips"]), cm.MAX_CLIPS)
        self.assertLess(size, 256 * 1024, f"{size} bytes")


class ARefusedStoryIsNotReanalysed(unittest.TestCase):
    def setUp(self):
        self.mem = cm.empty()
        self.refused = [_url("a"), _url("b"), _url("c")]
        cm.note_story_tried(self.mem, self.refused,
                            premise="sniped by a boar, then loses a duel",
                            why="the boar never appears", day="2026-10-01")

    def test_the_same_proposal_is_recognised(self):
        self.assertIsNotNone(cm.already_tried(self.mem, self.refused))

    def test_a_smaller_retelling_is_recognised(self):
        self.assertIsNotNone(cm.already_tried(self.mem, self.refused[:2]))

    def test_a_new_clip_makes_it_a_new_hypothesis(self):
        """The clip that was missing may be the payoff that arrived today."""
        self.assertIsNone(cm.already_tried(self.mem,
                                           self.refused + [_url("payoff")]))

    def test_only_two_or_more_clips_are_a_story_to_remember(self):
        mem = cm.empty()
        cm.note_story_tried(mem, [_url("solo")], why="x")
        self.assertEqual(mem["stories_tried"], [])


# ------------------------------------------------------------- catalogue
class TheCatalogueCarriesTheEvidence(unittest.TestCase):
    def setUp(self):
        self.corpus = [
            _clip("boar", "Summit1G Gets Sniped By A Boar", views=900),
            _clip("duel", "summit loses the duel to pika", views=700),
            _clip("q", "?", date_="2026-09-28"),                   # junk title
            _clip("post", "Summit1g Finally Beats The Raid",
                  date_="2026-09-20", posted=True),
        ]
        self.mem = cm.empty()
        cm.note_clip(self.mem, _url("boar"),
                     saw="Summit1g dies in a field; no attacker visible",
                     said="what the hell just happened")
        cm.note_clip(self.mem, _url("q"),
                     saw="Summit1g rage-quits and walks off camera")

    def test_without_memory_the_catalogue_is_unchanged(self):
        """Equivalence: the old call and an empty memory build the same
        catalogue, line for line."""
        self.assertEqual(sl.build_catalogue(self.corpus),
                         sl.build_catalogue(self.corpus,
                                            memory=cm.empty()))

    def test_a_watched_clip_says_what_it_showed(self):
        lines, ids = sl.build_catalogue(self.corpus, memory=self.mem)
        boar = next(ln for ln in lines if "Sniped By A Boar" in ln)
        self.assertIn("saw: Summit1g dies in a field; no attacker visible",
                      boar)
        self.assertIn('said: "what the hell just happened"', boar)
        duel = next(ln for ln in lines if "duel" in ln)
        self.assertNotIn("saw:", duel, "an unwatched clip claims nothing")

    def test_a_junk_title_we_have_watched_is_not_dropped(self):
        without, _ = sl.build_catalogue(self.corpus)
        self.assertFalse(any("rage-quits" in ln for ln in without))
        self.assertFalse(any(ln.endswith("| ?") for ln in without))
        with_mem, _ = sl.build_catalogue(self.corpus, memory=self.mem)
        self.assertTrue(any("rage-quits" in ln for ln in with_mem))

    def test_refusals_are_written_in_the_catalogue_ids(self):
        lines, ids = sl.build_catalogue(self.corpus, memory=self.mem)
        cm.note_story_tried(self.mem, [_url("boar"), _url("duel")],
                            premise="boar then duel",
                            why="the boar never appears")
        by_key = {sl.clip_key(c["source_url"]): cid
                  for cid, c in ids.items()}
        out = cm.tried_lines(self.mem, by_key)
        self.assertEqual(len(out), 1)
        self.assertIn(by_key[sl.clip_key(_url("boar"))], out[0])
        self.assertIn("the boar never appears", out[0])


# ----------------------------------------------------------------- scout
class TheScoutIsToldWhatIsEvidence(unittest.TestCase):
    def test_the_prompt_puts_footage_before_titles(self):
        p = sd._SCOUT_SYSTEM
        self.assertIn("saw:", p)
        self.assertIn("EVIDENCE BEFORE TITLES", p)
        self.assertIn("footage wins", p)
        self.assertIn("ALREADY REFUSED", p)

    def test_refusals_reach_the_scout(self):
        seen = {}

        def brain(user, system):
            seen["user"] = user
            return {"stories": []}
        with mock.patch.object(sd, "_brain", side_effect=brain):
            sd.scout_stories(["C1 | a", "C2 | b"], {"C1", "C2"},
                             tried=["[C1, C2] boar — refused: no boar"])
        self.assertIn("ALREADY REFUSED", seen["user"])
        self.assertIn("refused: no boar", seen["user"])

    def test_no_refusals_adds_nothing(self):
        seen = {}

        def brain(user, system):
            seen["user"] = user
            return {"stories": []}
        with mock.patch.object(sd, "_brain", side_effect=brain):
            sd.scout_stories(["C1 | a", "C2 | b"], {"C1", "C2"})
        self.assertNotIn("ALREADY REFUSED", seen["user"])


# -------------------------------------------------------------- director
def _plan_answer(sources):
    beats = [{"source_id": s, "start": 0, "end": 10,
              "role": r, "purpose": "advances it"}
             for s, r in zip(sources, ["setup", "escalation", "payoff"])]
    beats[-1]["role"] = "payoff"
    return {"is_story": True, "premise": "p", "central_question": "q?",
            "structure": "chronological", "structure_reason": "r",
            "title": "t", "hook_overlay": "he never saw it coming",
            "target_duration": 40, "beats": beats}


class TheDirectorMayTellTheSmallerStory(unittest.TestCase):
    durations = {"a": 30.0, "b": 30.0, "c": 30.0}

    def test_two_sources_still_make_a_story(self):
        rs = []
        self.assertIsNotNone(sd.validate_edl(_plan_answer(["a", "b", "b"]),
                                             self.durations, reasons=rs), rs)

    def test_one_source_is_a_clip_not_a_story(self):
        rs = []
        self.assertIsNone(sd.validate_edl(_plan_answer(["a", "a", "a"]),
                                          self.durations, reasons=rs))
        self.assertIn("one source", "; ".join(rs))

    def test_the_hypothesis_invites_the_story_the_footage_shows(self):
        seen = {}

        def brain(user, system):
            seen["user"] = user
            return {"is_story": False, "why_not": "x"}
        reps = [{"source_id": s, "channel": "s", "duration_s": 30,
                 "summary": "x"} for s in ("a", "b")]
        with mock.patch.object(sd, "_brain", side_effect=brain):
            sd.plan_story(reps, None, hypothesis="boar then duel")
        u = seen["user"]
        self.assertIn("HYPOTHESIS", u)
        self.assertIn("what the footage DOES show", u)
        self.assertIn("two or more", u)


# ------------------------------------------------------------- the wiring
class TheRunRemembers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = (ROOT / "scripts" / "run_third.py").read_text()
        tree = ast.parse(cls.src)
        cls.fns = {n.name: ast.get_source_segment(cls.src, n)
                   for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)}

    def test_the_story_arm_reads_and_writes_the_memory(self):
        body = self.fns["_story_attempt"]
        self.assertIn("build_catalogue(corpus,", body)
        self.assertIn("memory=_memory()", body)
        self.assertIn("tried=_refused", body)
        self.assertIn("clip_memory.already_tried(", body)
        self.assertIn("_remember_clip(c[\"source_url\"]", body)
        self.assertIn("_remember_refused(", body)

    def test_a_refusal_is_remembered_only_when_editorial(self):
        body = self.fns["_story_attempt"]
        i = body.index("_remember_refused(")
        self.assertIn('if rej.get("editorial"):', body[i - 200:i])

    def test_the_clip_arm_remembers_what_was_said(self):
        body = self.fns["process"]
        i = body.index("clip_edit.transcribe_words(info[\"path\"], wmodel)")
        self.assertIn("_remember_clip(info[\"url\"]", body[i:i + 400])

    def test_the_memory_is_committed(self):
        wf = (ROOT / ".github" / "workflows" / "third.yml").read_text()
        self.assertIn("state/third_clip_memory.json", wf)
        self.assertIn('"state/third_clip_memory.json"',
                      self.fns["_checkpoint_log"]
                      if "_checkpoint_log" in self.fns else self.src)


if __name__ == "__main__":
    unittest.main()
