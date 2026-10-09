"""THE EXPLAINER'S VOICE IS A CLONE OF A REAL NARRATOR, AND IT IS LISTENED TO.

Operator, 2026-10-08: paying for ElevenLabs "sucks", yet the voice is the
difference between one of our videos and a half as interesting one; a voice
people can tell is AI "is cooked"; recording their own "defeats the whole
point of it being autonomous". Of a Chatterbox clone of a LibriTTS-R
narrator on the voice lab page: "chatterbox lowkey sound better then eleven
labs".

So Chatterbox (engines/chatterbox_tts.py) voices the narration first, on
the runner's CPU, for free. What these tests hold:

  * it goes FIRST, and a video it cannot voice cleanly is voiced WHOLE by
    the next engine, never half and half;
  * every line is LISTENED to, because the showrunner judges frames and an
    LLM voice can ad-lib — a line that does not say its words is redrawn,
    and a line that still does not is a fallback, not a shipped stumble;
  * a line it voiced is never voiced again (the line cache);
  * its process gets no secret: it is third-party code in a job that holds
    the YouTube token;
  * the credit a voice's licence asks for rides on every video it narrated
    (LibriTTS-R is CC BY; the GLOBE voices are CC0 and need none);
  * the voices on the lab page are in the repo, small, and pinned;
  * the channel's ONE voice is Voice 38 on the full model (caaleb,
    2026-10-09, after the finals: "make that the new voice of the
    channel"), and a long run finishes on Turbo in that same voice.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engines import chatterbox_tts as cb  # noqa: E402


def _wav(path: Path, secs: float = 2.0) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(b"\x01\x00" * int(24000 * secs))
    return path


class _Listener:
    def __init__(self, said):
        self.said = said

    def transcribe(self, path, **kw):
        return {"text": self.said(path) if callable(self.said) else self.said}


class EveryLineIsListenedTo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._was = cb._LISTENER

    def tearDown(self):
        cb._LISTENER = self._was

    def _heard(self, text, said, secs=3.0, normalize=None):
        cb._LISTENER = _Listener(said)
        with mock.patch.dict(sys.modules, {"whisper": mock.MagicMock()}):
            return cb.heard(_wav(self.tmp / "l.wav", secs), text, normalize)

    def test_a_line_that_says_its_words_passes(self):
        ok, _ = self._heard("Sand is vanishing five times faster.",
                            " Sand is vanishing five times faster.")
        self.assertTrue(ok)

    def test_an_ad_lib_or_a_dropped_clause_fails(self):
        ok, why = self._heard(
            "We now mine fifty billion tonnes of sand and gravel a year.",
            " We now mine, uh, sand. Sand.")
        self.assertFalse(ok, why)

    def test_digits_the_listener_writes_agree_with_spelled_words(self):
        from data_learning.studio_render import _tts_text
        ok, why = self._heard("We mine fifty billion tonnes a year.",
                              " We mine 50 billion tonnes a year.",
                              normalize=_tts_text)
        self.assertTrue(ok, why)

    def test_a_line_far_too_long_or_short_for_its_words_fails(self):
        text = "Rivers replace just thirteen billion tonnes a year."
        self.assertFalse(self._heard(text, text, secs=20.0)[0])
        self.assertFalse(self._heard(text, text, secs=0.4)[0])

    def test_no_listener_means_no_line(self):
        cb._LISTENER = None
        with mock.patch.dict(sys.modules, {"whisper": None}):
            ok, why = cb.heard(_wav(self.tmp / "x.wav", 3.0), "one two three four five")
        self.assertFalse(ok)
        self.assertIn("listener", why)


class ABadLineIsRedrawnThenHandedOn(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.calls = []

    def _worker(self, items, model, ref, timeout):
        self.calls.append([(t, s) for t, _o, s in items])
        for _t, o, _s in items:
            _wav(Path(o))
        return True

    def _run(self, heard):
        texts = ["line one here", "line two here"]
        outs = [self.tmp / "s0.wav", self.tmp / "s1.wav"]
        with mock.patch.object(cb, "available", return_value=True), \
                mock.patch.object(cb, "_run_worker", self._worker), \
                mock.patch.object(cb, "heard", heard):
            return cb.maybe_voice(texts, outs)

    def test_only_the_bad_line_is_redrawn_with_a_new_seed(self):
        seen = {}

        def heard(wav, text, normalize=None):
            seen[text] = seen.get(text, 0) + 1
            return (text != "line two here" or seen[text] > 1), "mumbled"
        self.assertIsNotNone(self._run(heard))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([t for t, _ in self.calls[1]], ["line two here"])
        self.assertNotEqual(self.calls[0][1][1], self.calls[1][0][1])

    def test_a_line_that_never_comes_out_right_is_a_fallback(self):
        out = self._run(lambda wav, text, normalize=None: (text != "line two here", "mumbled"))
        self.assertIsNone(out)
        self.assertEqual(len(self.calls), cb.REDRAWS + 1)
        self.assertIn("would not come out right", cb.LAST_FAILURE)

    def test_it_never_raises(self):
        with mock.patch.object(cb, "available", side_effect=RuntimeError("boom")):
            self.assertIsNone(cb.maybe_voice(["a"], [self.tmp / "a.wav"]))

    def test_the_same_words_get_the_same_seed(self):
        self.assertEqual(cb._seed("hello", 0), cb._seed("hello", 0))
        self.assertNotEqual(cb._seed("hello", 0), cb._seed("hello", 1))


class TheWorkerIsHandedAbsolutePaths(unittest.TestCase):
    """The worker runs with cwd = the work dir; a relative path in its job
    resolved twice and every line fell through (voice-preview, 2026-10-08)."""

    def test_a_relative_work_dir_still_reaches_the_worker_whole(self):
        tmp = Path(tempfile.mkdtemp())
        seen = {}

        def run(cmd, **kw):
            import json as _j
            job = Path(cmd[-1])
            seen["job_abs"] = job.is_absolute()
            spec = _j.loads(job.read_text())
            seen["paths"] = [spec["ref"]] + [l["out"] for l in spec["lines"]]
            for l in spec["lines"]:
                _wav(Path(l["out"]))
            return mock.Mock(returncode=0, stderr="")
        old = os.getcwd()
        os.chdir(tmp)
        try:
            (tmp / "w").mkdir()
            with mock.patch("subprocess.run", side_effect=run), \
                    mock.patch.object(cb, "_trim", lambda a, b: Path(a).replace(b)):
                ok = cb._run_worker([("hi there", Path("w/s0.wav"), 1)], "turbo",
                                    Path("ref.ogg"), 10)
        finally:
            os.chdir(old)
        self.assertTrue(ok)
        self.assertTrue(seen["job_abs"])
        self.assertTrue(all(Path(p).is_absolute() for p in seen["paths"]), seen)


class ChatterboxGoesFirstAndWhole(unittest.TestCase):
    def setUp(self):
        from data_learning import studio_render as R
        self.R = R
        self.tmp = Path(tempfile.mkdtemp())
        self.n = 0

    def _voice(self, ok):
        def voice(texts, outs, **kw):
            self.n += len(texts)
            if not ok:
                cb.LAST_FAILURE = "line 1 would not come out right"
                return None
            return [_wav(Path(o), 1.0) for o in outs]
        return voice

    def _narrate(self, ok, env=None):
        R = self.R
        with mock.patch.object(cb, "available", return_value=True), \
                mock.patch.object(cb, "maybe_voice", self._voice(ok)), \
                mock.patch.object(R, "_retime", lambda w, t: None), \
                mock.patch.dict(os.environ, env or {}, clear=False):
            return R._chatterbox_lines(["one line", "two line"], self.tmp)

    def test_its_lines_are_the_narration(self):
        out = self._narrate(True)
        self.assertEqual([p.name for p in out], ["s0.wav", "s1.wav"])

    def test_a_failure_is_recorded_and_hands_the_whole_video_on(self):
        self.assertIsNone(self._narrate(False))
        self.assertIn("would not come out right",
                      self.R.TTS_USED["why_not_chatterbox"])

    def test_a_line_it_voiced_is_not_voiced_again(self):
        env = {"TTS_CACHE_DIR": str(self.tmp / "cache")}
        self._narrate(True, env)
        first = self.n
        self._narrate(True, env)
        self.assertEqual(first, 2)
        self.assertEqual(self.n, 2, "the second narration re-voiced cached lines")

    def test_synth_narration_asks_chatterbox_before_anyone_paid(self):
        import ast
        import inspect
        src = inspect.getsource(self.R.synth_narration)
        calls = [n.func.id for n in ast.walk(ast.parse(src.lstrip()))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertIn("_chatterbox_lines", calls)
        order = [c for c in calls if c in ("_chatterbox_lines", "_elevenlabs_wav",
                                           "_speechify_wav")]
        self.assertEqual(order[0], "_chatterbox_lines")


class ItsProcessHoldsNoSecret(unittest.TestCase):
    def test_the_worker_env_is_an_allow_list(self):
        loud = {"YOUTUBE_TOKEN_JSON_EXPLAINER": "t", "GITHUB_TOKEN": "g",
                "CLAUDE_CODE_OAUTH_TOKEN": "c", "SPEECHIFY_API_KEY": "s",
                "SOME_FUTURE_SECRET": "f"}
        with mock.patch.dict(os.environ, loud):
            env = cb._worker_env()
        for k in loud:
            self.assertNotIn(k, env)
        self.assertNotIn("t", [v for k, v in env.items() if k != "PATH"])
        self.assertEqual(env.get("HF_HUB_OFFLINE"), "1")

    def test_the_worker_runs_isolated_in_its_own_venv(self):
        src = (ROOT / "engines" / "chatterbox_tts.py").read_text()
        self.assertRegex(src, r'\[str\(VENV_PY\), "-I", str\(WORKER\)')
        self.assertIn("env=_worker_env()", src)

    def test_the_pipeline_never_imports_chatterbox_itself(self):
        for p in list((ROOT / "data_learning").glob("*.py")) + \
                list((ROOT / "scripts").glob("*.py")) + [ROOT / "engines" / "chatterbox_tts.py"]:
            self.assertNotRegex(p.read_text(errors="ignore"),
                                r"^\s*(from|import) chatterbox\b", p.name)


class TheVoicesAreInTheRepoAndPinned(unittest.TestCase):
    def test_every_lab_voice_is_a_small_clip_in_the_repo(self):
        for n in cb.VOICES:
            p = cb.voice_ref(n)
            self.assertTrue(p.is_file(), p)
            self.assertLess(p.stat().st_size, 256 * 1024, p)

    def test_the_lock_pins_every_package_exactly(self):
        lines = [l.split("#")[0].strip() for l in cb.LOCK.read_text().splitlines()]
        lines = [l for l in lines if l]
        self.assertTrue(any(l.startswith("chatterbox-tts==") for l in lines))
        for l in lines:
            self.assertRegex(l, r"^[A-Za-z0-9_.\-\[\]]+==[^=\s]+$", l)

    def test_every_model_file_is_pinned_by_size_and_hash(self):
        for name, spec in cb.META["models"].items():
            self.assertRegex(spec["revision"], r"^[0-9a-f]{40}$", name)
            self.assertTrue(spec["files"], name)
            for rel, f in spec["files"].items():
                self.assertRegex(f["sha256"], r"^[0-9a-f]{64}$", rel)
                self.assertGreater(f["bytes"], 0, rel)

    def test_an_unknown_voice_or_model_setting_resolves(self):
        with mock.patch.dict(os.environ, {"CHATTERBOX_MODEL": "nonsense"}):
            self.assertEqual(cb.model_name(), cb.DEFAULT_MODEL)
        with mock.patch.dict(os.environ, {"CHATTERBOX_VOICE": ""}):
            self.assertEqual(cb.voice_ref(), cb.voice_ref(cb.DEFAULT_VOICE))


class TheCreditRidesOnEveryVideoItNarrated(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import post_stories
        self.ps = post_stories
        self.tmp = Path(tempfile.mkdtemp())

    def _mp4(self, engine):
        import json
        mp4 = self.tmp / f"{engine}.mp4"
        if engine:
            mp4.with_suffix(".style.json").write_text(json.dumps({"tts": {"engine": engine}}))
        return mp4

    def _voiced(self, stem):
        import json
        mp4 = self.tmp / f"{stem}.mp4"
        mp4.with_suffix(".style.json").write_text(json.dumps(
            {"tts": {"engine": "chatterbox", "voice": f"{stem} (full)"}}))
        return mp4

    def test_a_libritts_voice_credits_the_corpus(self):
        self.assertIn(cb.CREDIT, self.ps._desc_suffix({}, self._voiced("libritts_r_3000")))

    def test_the_globe_voice_is_cc0_and_credits_nothing(self):
        self.assertNotIn(cb.CREDIT, self.ps._desc_suffix({}, self._voiced("globe_S_001818")))

    def test_other_voices_do_not(self):
        self.assertNotIn(cb.CREDIT, self.ps._desc_suffix({}, self._mp4("speechify")))

    def test_a_cut_that_lost_its_sidecar_is_credited_for_this_runs_voice(self):
        with mock.patch.dict(os.environ, {"CHATTERBOX_VOICE": "1"}):
            self.assertIn(cb.CREDIT, self.ps._desc_suffix({}, self.tmp / "gone.mp4"))
        with mock.patch.dict(os.environ, {"CHATTERBOX_VOICE": "38"}):
            self.assertNotIn(cb.CREDIT, self.ps._desc_suffix({}, self.tmp / "gone.mp4"))

    def test_every_upload_passes_its_cut(self):
        for f in ("scripts/post_stories.py", "scripts/claim_reviews.py"):
            src = (ROOT / f).read_text()
            # the explainer's own _description: bare in post_stories, `ps.`
            # in claim_reviews (whose `rt._description` is trending's)
            for m in re.finditer(r"(?:\bps\.|(?<![.\w]))_description\(([^)]*)\)", src):
                if "def " in src[max(0, m.start() - 6):m.start()]:
                    continue
                self.assertIn(",", m.group(1), f"{f}: {m.group(0)} has no cut")


class TheWorkflowProvisionsIt(unittest.TestCase):
    def test_the_explainer_installs_the_voice_before_it_renders(self):
        y = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        inst = y.index("python -m engines install chatterbox_tts")
        run = y.index("      - name: Run\n")
        self.assertLess(inst, run)

    def test_its_weights_stay_out_of_actions_cache(self):
        """2-4 GB of weights in the repo's 10 GB cache evicts everything else."""
        for p in (ROOT / ".github" / "workflows").glob("*.yml"):
            self.assertNotIn("cache/models/chatterbox", p.read_text(), p.name)
            self.assertNotIn("cache/venvs/chatterbox", p.read_text(), p.name)

    def test_both_steps_default_to_the_same_model(self):
        y = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        got = set(re.findall(r"CHATTERBOX_MODEL: \$\{\{ vars.CHATTERBOX_MODEL \|\| '(\w+)' \}\}", y))
        self.assertEqual(got, {cb.DEFAULT_MODEL})

class TheChannelHasOneVoice(unittest.TestCase):
    def test_it_is_voice_38_on_the_full_model(self):
        self.assertEqual(cb.DEFAULT_VOICE, "38")
        self.assertEqual(cb.DEFAULT_MODEL, "full")
        with mock.patch.dict(os.environ, {"CHATTERBOX_VOICE": "", "CHATTERBOX_MODEL": ""}):
            self.assertEqual(cb.voice_ref().name, "globe_S_001818.ogg")
            self.assertTrue(cb.voice_ref().is_file())

    def test_its_source_is_written_down(self):
        readme = (ROOT / "assets" / "voice" / "README.md").read_text()
        self.assertIn("globe_S_001818.ogg", readme)
        self.assertIn("CC0", readme)

    def test_both_workflow_steps_default_to_it(self):
        y = (ROOT / ".github" / "workflows" / "explainer.yml").read_text()
        self.assertIn("CHATTERBOX_VOICE: ${{ vars.CHATTERBOX_VOICE || '38' }}", y)

    def test_the_full_model_is_handed_the_energy_it_was_picked_at(self):
        seen = {}
        tmp = Path(tempfile.mkdtemp())

        def run(cmd, **kw):
            import json as _j
            spec = _j.loads(Path(cmd[-1]).read_text())
            seen.update(spec)
            for l in spec["lines"]:
                _wav(Path(l["out"]))
            return mock.Mock(returncode=0, stderr="")
        with mock.patch("subprocess.run", side_effect=run), \
                mock.patch.object(cb, "_trim", lambda a, b: Path(a).replace(b)):
            self.assertTrue(cb._run_worker([("hi there", tmp / "s0.wav", 1)], "full",
                                           tmp / "ref.ogg", 10))
        self.assertEqual(seen["exaggeration"], cb.FULL_STYLE["exaggeration"])
        self.assertEqual(seen["cfg_weight"], cb.FULL_STYLE["cfg_weight"])

    def test_a_long_run_finishes_on_turbo_in_the_same_voice(self):
        with mock.patch.dict(os.environ, {"CHATTERBOX_MODEL": "", "CHATTERBOX_VOICE": ""}), \
                mock.patch.object(cb, "model_verified", lambda m=None: True):
            with mock.patch.object(cb, "_FULL_SPENT_S", 0.0):
                self.assertEqual(cb.model_name(), "full")
            with mock.patch.object(cb, "_FULL_SPENT_S", cb._budget_s() + 1):
                self.assertEqual(cb.model_name(), "turbo")
                self.assertEqual(cb.model_name("full"), "full")   # an explicit ask is kept
                self.assertEqual(cb.voice_ref().name, "globe_S_001818.ogg")

    def test_no_turbo_on_disk_means_it_stays_on_full(self):
        with mock.patch.dict(os.environ, {"CHATTERBOX_MODEL": ""}), \
                mock.patch.object(cb, "model_verified", lambda m=None: False), \
                mock.patch.object(cb, "_FULL_SPENT_S", cb._budget_s() + 1):
            self.assertEqual(cb.model_name(), "full")

    def test_the_cache_keeps_full_model_lines_apart_by_their_energy(self):
        from data_learning import studio_render as R
        import inspect
        self.assertIn("FULL_STYLE", inspect.getsource(R._chatterbox_lines))


if __name__ == "__main__":
    unittest.main()
