"""The music sits well under the voice (caaleb, 2026-10-17: "The music is
to loud"). MEASURED: the bed alone, as the soundtrack mixes it under a
narration, is at least 17 LU quieter than the narration."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import studio_render as SR  # noqa: E402


def _lufs(p: Path) -> float:
    out = subprocess.run(["ffmpeg", "-i", str(p), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return float([l for l in out.splitlines() if l.strip().startswith("I:")][-1].split()[1])


def _ff(*a):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *a], check=True)


class TheBedIsUnderTheVoice(unittest.TestCase):
    def test_the_ducked_bed_is_far_under_the_narration(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            voice = d / "voice.wav"          # speech-like: bursts with breaths
            _ff("-f", "lavfi", "-i",
                "aevalsrc='0.5*sin(2*PI*180*t)*sin(2*PI*3*t)*gt(mod(t,2),0.3)':d=20:s=24000",
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(voice))
            music = d / "music_src.wav"
            _ff("-f", "lavfi", "-i", "anoisesrc=color=pink:d=21:a=0.3",
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ac", "2", "-ar", "44100", str(music))
            silent_music = d / "silent_music.wav"
            _ff("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "21",
                str(silent_music))
            saved = SR._build_music
            mix = {}
            try:
                for name, src in (("full", music), ("voice", silent_music)):
                    w = d / name
                    w.mkdir()
                    SR._build_music = (lambda total, out, *a, _s=src, **k:
                                       _ff("-i", str(_s), str(out)))
                    mix[name] = SR._build_soundtrack(voice, [(0, 10), (10, 20)], [],
                                                     20.0, "calm", w, "slug")
            finally:
                SR._build_music = saved
            # the same graph twice, the second with a silent bed: what the
            # first has more of is the bed, exactly as it plays
            bed = d / "bed_only.wav"
            _ff("-i", str(mix["full"]), "-i", str(mix["voice"]), "-filter_complex",
                "[1:a]volume=-1[n];[0:a][n]amix=inputs=2:normalize=0[b]",
                "-map", "[b]", str(bed))
            self.assertGreaterEqual(_lufs(mix["voice"]) - _lufs(bed), 17.0)


if __name__ == "__main__":
    unittest.main()
