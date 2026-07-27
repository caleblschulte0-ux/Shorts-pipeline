from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from .approved_queue import ApprovedQueue
from .buffer_manager import BufferManager, BufferPolicy, BufferState
from .contracts import DegradationLevel, ProviderKind, QueueStatus
from .degradation_policy import DegradationPolicy
from .deterministic_writer import DeterministicWriter
from .fallback_orchestrator import FallbackOrchestrator
from .fixtures import approve, sample_request
from .provider_health import ProviderHealthEvent, ProviderHealthStore
from .provider_router import ProviderRouter
from .upload_idempotency import UploadLedger


class SubscriptionFallbackTests(unittest.TestCase):
    def test_template_writer_is_evidence_bound(self) -> None:
        package = DeterministicWriter().write(sample_request())
        self.assertEqual(package.provider, ProviderKind.TEMPLATE)
        self.assertIn("Example public dataset", package.script)
        self.assertEqual(package.degradation, DegradationLevel.DEGRADED)
        self.assertFalse(package.postable())

    def test_template_rejects_missing_evidence(self) -> None:
        request = replace(sample_request(), facts=())
        with self.assertRaises(ValueError):
            DeterministicWriter().write(request)

    def test_router_skips_unconfigured_ai(self) -> None:
        route = ProviderRouter().route(sample_request(), {}, {
            ProviderKind.CLAUDE: False,
            ProviderKind.GEMINI: False,
            ProviderKind.TEMPLATE: True,
            ProviderKind.BUFFER: True,
        })
        self.assertEqual(route.order, (ProviderKind.TEMPLATE, ProviderKind.BUFFER))

    def test_generation_falls_back_to_template_and_enqueues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = FallbackOrchestrator(Path(tmp))
            result = orchestrator.build_into_buffer(sample_request(), approval=approve)
            self.assertTrue(result.enqueued)
            self.assertEqual(result.package.provider, ProviderKind.TEMPLATE)
            self.assertEqual(len(orchestrator.queue.items()), 1)

    def test_posting_does_not_generate(self) -> None:
        calls = {"count": 0}
        def claude(_request):
            calls["count"] += 1
            raise AssertionError("posting must not generate")
        with tempfile.TemporaryDirectory() as tmp:
            orchestrator = FallbackOrchestrator(Path(tmp), providers={ProviderKind.CLAUDE: claude})
            claim = orchestrator.claim_next_upload("daily-data")
            self.assertIsNone(claim.item)
            self.assertEqual(calls["count"], 0)

    def test_queue_only_accepts_postable_packages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ApprovedQueue(Path(tmp))
            package = DeterministicWriter().write(sample_request())
            with self.assertRaises(ValueError):
                queue.enqueue(package)

    def test_queue_claim_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ApprovedQueue(Path(tmp))
            package = approve(DeterministicWriter().write(sample_request()))
            queue.enqueue(package)
            claim = queue.claim_next("daily-data")
            self.assertEqual(claim.item.status, QueueStatus.CLAIMED)
            posted = queue.mark_posted(claim.claim_token, "youtube-123")
            self.assertEqual(posted.status, QueueStatus.POSTED)

    def test_queue_duplicate_fingerprint_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ApprovedQueue(Path(tmp))
            package = approve(DeterministicWriter().write(sample_request()))
            queue.enqueue(package)
            with self.assertRaises(ValueError):
                queue.enqueue(replace(package, package_id="different-id"))

    def test_released_claim_becomes_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue = ApprovedQueue(Path(tmp))
            queue.enqueue(approve(DeterministicWriter().write(sample_request())))
            claim = queue.claim_next("daily-data")
            item = queue.release_claim(claim.claim_token)
            self.assertEqual(item.status, QueueStatus.READY)

    def test_buffer_thresholds(self) -> None:
        manager = BufferManager(BufferPolicy(target_ready=30, warning_ready=14, emergency_ready=7))
        report = manager.report("daily-data", ())
        self.assertEqual(report.state, BufferState.EMPTY)
        self.assertEqual(report.replenish_by, 30)

    def test_health_circuit_opens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProviderHealthStore(Path(tmp) / "health.jsonl", failure_threshold=3, cooldown_minutes=60)
            for index in range(3):
                store.record(ProviderHealthEvent(ProviderKind.CLAUDE, False, f"2026-07-27T12:0{index}:00+00:00", "limit"))
            status = store.status(ProviderKind.CLAUDE, now=datetime(2026, 7, 27, 12, 30, tzinfo=timezone.utc))
            self.assertTrue(status.circuit_open)

    def test_success_resets_consecutive_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProviderHealthStore(Path(tmp) / "health.jsonl")
            store.record(ProviderHealthEvent(ProviderKind.GEMINI, False, "2026-07-27T11:00:00+00:00", "quota"))
            store.record(ProviderHealthEvent(ProviderKind.GEMINI, True, "2026-07-27T12:00:00+00:00"))
            self.assertEqual(store.status(ProviderKind.GEMINI).consecutive_failures, 0)

    def test_degradation_policy_blocks_missing_checks(self) -> None:
        package = approve(DeterministicWriter().write(sample_request()))
        decision = DegradationPolicy().evaluate(package, {"valid_mp4": True})
        self.assertFalse(decision.postable)
        self.assertEqual(decision.level, DegradationLevel.BLOCKED)

    def test_degraded_package_can_post_when_all_gates_pass(self) -> None:
        package = approve(DeterministicWriter().write(sample_request()))
        checks = {name: True for name in DegradationPolicy.REQUIRED_CHECKS}
        decision = DegradationPolicy().evaluate(package, checks)
        self.assertTrue(decision.postable)
        self.assertEqual(decision.level, DegradationLevel.DEGRADED)

    def test_upload_ledger_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = UploadLedger(Path(tmp) / "uploads.json")
            reservation = ledger.reserve("daily-data", "abc", "2026-07-27")
            again = ledger.reserve("daily-data", "abc", "2026-07-27")
            self.assertEqual(reservation.idempotency_key, again.idempotency_key)
            completed = ledger.complete(reservation.idempotency_key, "youtube-1")
            self.assertEqual(completed.state, "completed")

    def test_completed_content_cannot_reserve_new_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = UploadLedger(Path(tmp) / "uploads.json")
            reservation = ledger.reserve("daily-data", "abc", "2026-07-27")
            ledger.complete(reservation.idempotency_key, "youtube-1")
            with self.assertRaises(ValueError):
                ledger.reserve("daily-data", "abc", "2026-07-28")


if __name__ == "__main__":
    unittest.main()
