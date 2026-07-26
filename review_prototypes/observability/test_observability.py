from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from .event_log import HashChainedEventLog
from .incidents import DeadLetterQueue, IncidentClassifier, IncidentSeverity
from .summary import RunSummaryBuilder


class ObservabilityTests(unittest.TestCase):
    def test_hash_chain_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            log = HashChainedEventLog(path)
            log.append(run_id="r1", stage="render", kind="render_completed", payload={"attempt_id": "a0"}, timestamp="2026-01-01T00:00:00+00:00")
            log.append(run_id="r1", stage="judge", kind="judge_completed", payload={"artifact_ref": "verdict.json"}, timestamp="2026-01-01T00:00:01+00:00")
            self.assertEqual(log.verify(), (True, None))
            lines = path.read_text().splitlines()
            item = json.loads(lines[0])
            item["payload"]["attempt_id"] = "tampered"
            lines[0] = json.dumps(item)
            path.write_text("\n".join(lines) + "\n")
            ok, reason = log.verify()
            self.assertFalse(ok)
            self.assertIn("hash mismatch", reason)

    def test_classifier_marks_publish_corruption_critical(self) -> None:
        incident = IncidentClassifier().classify(
            run_id="r1", stage="release", error=RuntimeError("publish manifest corrupt")
        )
        self.assertEqual(incident.severity, IncidentSeverity.CRITICAL)
        self.assertFalse(incident.retryable)

    def test_timeout_is_retryable_and_dead_letter_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            incident = IncidentClassifier().classify(
                run_id="r1", stage="judge", error=TimeoutError("judge timeout")
            )
            self.assertTrue(incident.retryable)
            queue = DeadLetterQueue(Path(temp))
            first = queue.enqueue(incident, {"slug": "demo"})
            second = queue.enqueue(incident, {"slug": "changed"})
            self.assertEqual(first, second)
            self.assertEqual(len(list(Path(temp).glob("*.json"))), 1)

    def test_summary_collects_stage_and_artifact_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "events.jsonl"
            log = HashChainedEventLog(path)
            log.append(run_id="r1", stage="render", kind="render_completed", payload={"attempt_id": "a0"})
            log.append(run_id="r1", stage="judge", kind="judge_failed", payload={"artifact_ref": "stderr.txt"})
            summary = RunSummaryBuilder().from_jsonl(path, "r1")
            self.assertEqual(summary.completed_stages, ("render",))
            self.assertEqual(summary.failed_stages, ("judge",))
            self.assertEqual(summary.attempt_ids, ("a0",))


if __name__ == "__main__":
    unittest.main()
