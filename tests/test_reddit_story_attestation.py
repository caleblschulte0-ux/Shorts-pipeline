"""Reddit renderer must render the bytes Phase B verified, or nothing.

Doctor finding 8b6949ab0573: ChatGPT-supplied reddit_story shots carry
media_sha256 / media_bytes beside a MUTABLE Google Drive URL, but the
renderer never read either field — it rendered whatever the URL serves
today, so the shipped image was never proven to be the verified one. The
fix checks byte length and SHA-256 against the attestation BEFORE Pillow
decodes anything; a mismatch makes that panel UNRESOLVED under the
existing media-completeness policy (no panel, gameplay shows through),
and shots without attestation fields keep the old behavior.

Fully offline: `base._fetch_image` is stubbed to serve local files.

    python -m unittest tests.test_reddit_story_attestation -v
"""
from __future__ import annotations

import hashlib
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import make_reddit_story as mrs                         # noqa: E402


def _png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 40, 40)).save(buf, "PNG")
    return buf.getvalue()


class TestShotAttestation(unittest.TestCase):
    def setUp(self):
        try:
            import PIL  # noqa: F401
        except Exception:  # noqa: BLE001
            self.skipTest("Pillow not installed")
        self._td = tempfile.TemporaryDirectory()
        self.workdir = Path(self._td.name)
        # The bytes Phase B "verified" and pinned into the package...
        self.good = _png_bytes()
        self.good_sha = hashlib.sha256(self.good).hexdigest()
        # ...and DIFFERENT (but same-length) bytes the mutable Drive URL
        # serves later — the swapped-asset case a length check alone misses.
        self.swapped = self.good[:-1] + bytes([self.good[-1] ^ 0xFF])
        self.assertEqual(len(self.swapped), len(self.good))
        self.served = self.workdir / "served.png"
        self.served.write_bytes(self.good)
        self._fetch = mrs.base._fetch_image
        mrs.base._fetch_image = lambda url, cache: self.served

    def tearDown(self):
        mrs.base._fetch_image = self._fetch
        self._td.cleanup()

    def _panels(self, shot_extra: dict):
        pkg = {"shots": [{"image_url": "https://drive.google.com/x",
                          **shot_extra}]}
        with redirect_stdout(io.StringIO()) as buf:
            out = mrs._shot_panels(pkg, self.workdir)
        return out, buf.getvalue()

    def test_matching_attestation_is_accepted(self):
        out, log = self._panels({"media_sha256": self.good_sha,
                                 "media_bytes": len(self.good)})
        self.assertIn(0, out)
        self.assertTrue(out[0].exists())
        self.assertNotIn("MISMATCH", log)

    def test_replaced_drive_content_makes_the_panel_unresolved(self):
        # Same length, different bytes: only the hash can catch it.
        self.served.write_bytes(self.swapped)
        out, log = self._panels({"media_sha256": self.good_sha,
                                 "media_bytes": len(self.good)})
        self.assertEqual(out, {})
        self.assertIn("media_sha256", log)
        # The log must name BOTH digests, in full — that is the diagnosis.
        self.assertIn(self.good_sha, log)
        self.assertIn(hashlib.sha256(self.swapped).hexdigest(), log)
        # ...and the panel takes the existing unresolved-media path, which
        # `_visual_track` answers with "no illustration" for a lone shot.
        self.assertIn("skipped", log)

    def test_truncated_download_makes_the_panel_unresolved(self):
        self.served.write_bytes(self.good[: len(self.good) // 2])
        out, log = self._panels({"media_sha256": self.good_sha,
                                 "media_bytes": len(self.good)})
        self.assertEqual(out, {})
        self.assertIn("media_bytes", log)

    def test_sha_alone_is_enforced(self):
        self.served.write_bytes(self.swapped)
        out, _ = self._panels({"media_sha256": self.good_sha})
        self.assertEqual(out, {})

    def test_bytes_alone_is_enforced(self):
        self.served.write_bytes(self.good + b"extra")
        out, _ = self._panels({"media_bytes": len(self.good)})
        self.assertEqual(out, {})

    def test_legacy_shots_without_attestation_are_unchanged(self):
        # No fields = the pre-ChatGPT path: decodable bytes are accepted.
        out, log = self._panels({})
        self.assertIn(0, out)
        self.assertNotIn("MISMATCH", log)

    def test_uppercase_package_digest_still_matches(self):
        out, _ = self._panels({"media_sha256": self.good_sha.upper()})
        self.assertIn(0, out)


if __name__ == "__main__":
    unittest.main()
