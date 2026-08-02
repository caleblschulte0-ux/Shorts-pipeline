from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .audit import AuditLog
from .fixtures import golden_story
from .models import ProofRun
from .proof import ProofStore, evaluate_two_run_proof, verdict_digest
from .release import ReleaseManifest, ReleaseRepository
from .services import SyntheticRenderer


class AuditProofReleaseTests(unittest.TestCase):
    def test_audit_chain_and_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            log = AuditLog(Path(temp) / "audit.jsonl")
            self.assertEqual(log.read(), ())
            log.append("one", {"x": 1})
            log.append("two", {"x": 2})
            log.verify()
            lines = log.path.read_text(encoding="utf-8").splitlines()
            data = json.loads(lines[0])
            data["payload"]["x"] = 9
            lines[0] = json.dumps(data)
            log.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                log.verify()

    def test_audit_sequence_and_link_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            log = AuditLog(Path(temp) / "audit.jsonl")
            log.append("one", {})
            log.append("two", {})
            lines = [json.loads(line) for line in log.path.read_text().splitlines()]
            lines[1]["sequence"] = 9
            log.path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
            with self.assertRaisesRegex(ValueError, "sequence"):
                log.verify()
            lines[1]["sequence"] = 2
            lines[1]["previous_hash"] = "bad"
            log.path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
            with self.assertRaisesRegex(ValueError, "link"):
                log.verify()

    def test_proof_store_and_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            store = ProofStore(Path(temp))
            run1 = ProofRun("r1", "s", "rv", "jv", "v1", "j1", 95, 9, 30, 0.02, True)
            run2 = replace(run1, run_id="r2", video_hash="v2")
            store.record(run1)
            self.assertEqual(store.load("r1"), run1)
            with self.assertRaises(ValueError):
                store.record(run1)
            self.assertTrue(evaluate_two_run_proof((run1, run2)).passed)
            self.assertFalse(evaluate_two_run_proof((run1,)).passed)
            bads = (
                replace(run2, renderer_version="rv2"),
                replace(run2, watched_video=False),
                replace(run2, hard_failures=("clip",)),
                replace(run2, score=80),
                replace(run2, lowest_dimension=5),
                replace(run2, effective_fps=10),
                replace(run2, duplicate_ratio=0.5),
                replace(run2, video_hash=""),
            )
            for bad in bads:
                with self.subTest(bad=bad):
                    self.assertFalse(evaluate_two_run_proof((run1, bad)).passed)
            path = Path(temp) / "r1.json"
            data = json.loads(path.read_text())
            data["score"] = 1
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                store.load("r1")
            self.assertEqual(len(verdict_digest({"a": 1})), 64)

    def test_release_record_promote_verify_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            renderer = SyntheticRenderer()
            story = golden_story()
            repo = ReleaseRepository(root / "releases")
            render1 = renderer.render(story, root / "r1", attempt_id="1")
            m1 = ReleaseManifest("one", story.slug, render1.video_hash, ("p1", "p2"), {"score": 95})
            repo.record(m1, render1.video_path)
            self.assertEqual(repo.load("one"), m1)
            repo.promote("one")
            self.assertEqual(repo.current_release_id(), "one")
            with self.assertRaises(ValueError):
                repo.record(m1, render1.video_path)
            render2 = renderer.render(story, root / "r2", attempt_id="2")
            m2 = ReleaseManifest("two", story.slug, render2.video_hash, ("p3", "p4"), {"score": 96})
            repo.record(m2, render2.video_path)
            repo.promote("two")
            self.assertEqual(repo.rollback(), "one")

    def test_release_failure_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = ReleaseRepository(root / "releases")
            with self.assertRaises(ValueError):
                repo.rollback()
            render = SyntheticRenderer().render(golden_story(), root / "r", attempt_id="1")
            manifest = ReleaseManifest("one", "s", render.video_hash, ("p",), {})
            path = repo.record(manifest, render.video_path)
            data = json.loads((path / "manifest.json").read_text())
            data["story_slug"] = "tamper"
            (path / "manifest.json").write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                repo.load("one")
            data["story_slug"] = "s"
            data["digest"] = manifest.digest
            (path / "manifest.json").write_text(json.dumps(data))
            with patch("review_prototypes.completion_lab.release.os.replace", side_effect=RuntimeError("swap failed")):
                with self.assertRaisesRegex(RuntimeError, "swap failed"):
                    repo.promote("one")
            data["story_slug"] = "s"
            data["digest"] = manifest.digest
            (path / "manifest.json").write_text(json.dumps(data))
            (path / "video.mp4").write_bytes(b"tamper")
            with self.assertRaises(ValueError):
                repo.load("one")
