"""A cache hit must prove itself against TODAY's claim, not just exist.

Doctor finding 7414ad03de3e (2026-08-26): `fetch_media`'s on-disk cache is
keyed only by request_id, and request IDs are content-addressed from
slug/shot/prompt (or, for an authored shot, slug/shot alone) with no date.
An identical ask on a later production day resolves to the same cache
path even though the mutable Drive object behind it may have changed
since. The old code returned any non-empty cached file before it ever
looked at the current response entry's claimed hash, and
`pin_verified_media` then stamped TODAY's Drive URL/hash onto the package
as if today's bytes had actually been the ones checked — a stale file
used as proof that a different, never-downloaded object had verified.

    python -m unittest tests.test_media_cache_attestation -v
"""
from __future__ import annotations

import hashlib
import sys
import unittest
import unittest.mock
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "scripts"))

import exchange_phase_b as pb                             # noqa: E402


def entry_for(blob: bytes, file_id="1abcNEW") -> dict:
    return {
        "status": "fulfilled",
        "drive": {"file_id": file_id,
                  "download_url": f"https://drive.google.com/uc?id={file_id}"},
        "image": {"sha256": hashlib.sha256(blob).hexdigest()},
    }


class TestCacheHitsAreAttested(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_cache = pb.MEDIA_CACHE
        pb.MEDIA_CACHE = Path(self._tmp.name)

    def tearDown(self):
        pb.MEDIA_CACHE = self._orig_cache
        self._tmp.cleanup()

    def _write_cache(self, request_id: str, blob: bytes, ext="png"):
        pb.MEDIA_CACHE.mkdir(parents=True, exist_ok=True)
        p = pb.MEDIA_CACHE / f"{request_id}.{ext}"
        p.write_bytes(blob)
        return p

    def test_cache_matching_current_claim_is_reused_without_network(self):
        blob = b"yesterdays-verified-bytes"
        self._write_cache("shared-rid", blob)
        entry = entry_for(blob)

        with unittest.mock.patch("urllib.request.urlopen") as urlopen:
            got = pb.fetch_media("shared-rid", entry)
        urlopen.assert_not_called()
        self.assertEqual(got.read_bytes(), blob)

    def test_stale_cache_for_a_changed_drive_object_is_not_reused(self):
        try:
            import io
            from PIL import Image
        except Exception:  # noqa: BLE001
            self.skipTest("Pillow not installed")
        # Same request_id (no date in it), but the Drive object behind it
        # changed since the file was cached — a different day's image.
        stale_blob = b"old-file-from-an-earlier-production-day"
        self._write_cache("shared-rid", stale_blob)

        # A real, non-placeholder image (the decode/colour-count checks
        # reject flat single-colour fills, so use a gradient).
        img = Image.new("RGB", (64, 64))
        img.putdata([(x % 256, y % 256, (x + y) % 256)
                     for y in range(64) for x in range(64)])
        buf = io.BytesIO()
        img.save(buf, "PNG")
        new_blob = buf.getvalue()
        entry = entry_for(new_blob, file_id="1abcTODAY")

        fake_resp = unittest.mock.MagicMock()
        fake_resp.read.return_value = new_blob
        fake_resp.headers.get.return_value = "image/png"
        fake_ctx = unittest.mock.MagicMock()
        fake_ctx.__enter__.return_value = fake_resp
        fake_ctx.__exit__.return_value = False

        with unittest.mock.patch("urllib.request.urlopen",
                                 return_value=fake_ctx) as urlopen:
            got = pb.fetch_media("shared-rid", entry)

        urlopen.assert_called()
        self.assertIsNotNone(got)
        self.assertEqual(got.read_bytes(), new_blob)
        self.assertNotEqual(got.read_bytes(), stale_blob)

    def test_cache_with_no_current_claim_is_not_trusted(self):
        # An orphaned cache file with no valid entry to check it against
        # (e.g. the current response never answered this request) must not
        # be handed back as if it were verified.
        self._write_cache("orphan-rid", b"leftover-from-somewhere")
        self.assertIsNone(pb.fetch_media("orphan-rid", None))
        self.assertIsNone(
            pb.fetch_media("orphan-rid", {"status": "unfulfilled"}))


if __name__ == "__main__":
    unittest.main()
