"""Doctor 75af24a46374: an over-cap EDL drops the replay segment; the whoosh
that marked the cut into it must go too, not fire past the end of the edit."""
import unittest

from third_capture import auto_edit


class OverCapReplayCue(unittest.TestCase):
    def _edl(self, dur):
        style = auto_edit.Style()
        style.replay = True
        style.sfx = True
        style.slowmo = False
        style.punch = False
        style.speedup_dead = False
        motion = [(i * 0.5, 1.0 if 20 <= i * 0.5 <= 22 else 0.1)
                  for i in range(int(dur * 2))]
        return auto_edit.build_edl([], dur, style, motion)

    def test_replay_kept_under_cap_keeps_its_cue(self):
        edl = self._edl(20.0)
        if any(s.kind == "replay" for s in edl.segments):
            self.assertTrue(any(c[1] == "whoosh" for c in edl.sfx_cues))

    def test_overcap_drops_replay_and_its_whoosh(self):
        edl = self._edl(60.0)
        self.assertFalse(any(s.kind == "replay" for s in edl.segments))
        end = edl.out_dur()
        self.assertFalse(
            [c for c in edl.sfx_cues if c[1] == "whoosh" and c[0] >= end - 1e-6],
            edl.sfx_cues)


if __name__ == "__main__":
    unittest.main()
