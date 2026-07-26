from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from experiments.curiosity_nextgen.autonomous_simulator import (
    InjectedFault,
    SimulatedStory,
    SimulationPolicy,
    simulate_batch,
)
from experiments.curiosity_nextgen.execution_ledger import ExecutionLedger, replay_events
from experiments.curiosity_nextgen.idea_funnel import IdeaCandidate, IdeaFunnelPolicy, run_idea_funnel
from experiments.curiosity_nextgen.provider_pool import (
    ProviderRecord,
    RoutingRequest,
    independent_judge_routes,
    route_provider,
)
from experiments.curiosity_nextgen.stage_artifact_contract import (
    ArtifactRecord,
    StageArtifactSpec,
    validate_stage_artifacts,
)


def idea(candidate_id: str, *, duplicate_key: str | None = None, topic: str = "science", format_family: str = "explainer", exploration: bool = False, audience: float = 0.8, evidence: float = 0.8, visual: float = 0.8, risk: float = 0.1, cost: float = 2.0, sources: int = 3) -> IdeaCandidate:
    return IdeaCandidate(candidate_id, f"Premise {candidate_id}", topic, format_family, duplicate_key or candidate_id, audience, 0.8, evidence, visual, risk, cost, sources, exploration)


def provider(provider_id: str, family: str, model: str, *, capabilities: frozenset[str] = frozenset({"render"}), healthy: bool = True, deterministic: bool = True, cost: float = 1.0, latency: float = 10.0, error: float = 0.01, quota: int = 100) -> ProviderRecord:
    return ProviderRecord(provider_id, family, model, capabilities, healthy, deterministic, cost, latency, error, quota)


def request(*, capability: str = "render", cost: float = 10.0, latency: float = 100.0, deterministic: bool = False) -> RoutingRequest:
    return RoutingRequest("render", frozenset({capability}), cost, latency, deterministic)


def artifact(artifact_id: str, story_id: str, stage: str, kind: str, digest: str, *, inputs: tuple[str, ...] = (), schema: int = 1, size: int = 10) -> ArtifactRecord:
    return ArtifactRecord(artifact_id, story_id, stage, kind, schema, digest, "provider-a", inputs, size)


class IdeaFunnelTests(unittest.TestCase):
    def test_selects_valid_candidate(self) -> None:
        result = run_idea_funnel([idea("a")], IdeaFunnelPolicy(minimum_exploration_slots=0))
        self.assertTrue(result.valid)
        self.assertEqual([item.candidate_id for item in result.selected], ["a"])

    def test_rejects_low_audience_value(self) -> None:
        result = run_idea_funnel([idea("a", audience=0.1)], IdeaFunnelPolicy(minimum_exploration_slots=0))
        self.assertIn(("a", "low_audience_value"), result.rejected)

    def test_rejects_duplicate_premise(self) -> None:
        result = run_idea_funnel([idea("a", duplicate_key="same"), idea("b", duplicate_key="same")], IdeaFunnelPolicy(minimum_exploration_slots=0))
        self.assertEqual(len(result.selected), 1)
        self.assertTrue(any(reason == "duplicate_premise" for _, reason in result.rejected))

    def test_policy_refuses_more_than_fifty(self) -> None:
        with self.assertRaises(ValueError):
            IdeaFunnelPolicy(maximum_selected=51)

    def test_topic_family_cap_defers(self) -> None:
        policy = IdeaFunnelPolicy(maximum_per_topic_family=1, minimum_exploration_slots=0)
        result = run_idea_funnel([idea("a"), idea("b")], policy)
        self.assertEqual(len(result.selected), 1)
        self.assertTrue(any(reason == "topic_family_capacity" for _, reason in result.deferred))

    def test_exploration_quota_blocks_invalid_portfolio(self) -> None:
        result = run_idea_funnel([idea("a")], IdeaFunnelPolicy(minimum_exploration_slots=1))
        self.assertFalse(result.valid)
        self.assertIn("exploration_quota_unmet", result.blockers)

    def test_budget_capacity_defers(self) -> None:
        result = run_idea_funnel([idea("a", cost=5), idea("b", cost=5)], IdeaFunnelPolicy(maximum_total_cost=5, minimum_exploration_slots=0))
        self.assertEqual(len(result.selected), 1)
        self.assertTrue(any(reason == "budget_capacity" for _, reason in result.deferred))

    def test_duplicate_candidate_id_is_blocker(self) -> None:
        result = run_idea_funnel([idea("a", duplicate_key="x"), idea("a", duplicate_key="y")], IdeaFunnelPolicy(minimum_exploration_slots=0))
        self.assertIn("duplicate_candidate_id", result.blockers)


class ProviderPoolTests(unittest.TestCase):
    def test_selects_highest_fitness_provider(self) -> None:
        decision = route_provider([provider("a", "fa", "ma"), provider("b", "fb", "mb", error=0.4)], request(), fallback_count=0)
        self.assertEqual(decision.selected_provider_id, "a")
        self.assertTrue(decision.valid)

    def test_rejects_capability_mismatch(self) -> None:
        decision = route_provider([provider("a", "fa", "ma")], request(capability="judge"), fallback_count=0)
        self.assertIn(("a", "capability_mismatch"), decision.rejected)

    def test_rejects_unhealthy_provider(self) -> None:
        decision = route_provider([provider("a", "fa", "ma", healthy=False)], request(), fallback_count=0)
        self.assertIn(("a", "unhealthy"), decision.rejected)

    def test_rejects_cost_limit(self) -> None:
        decision = route_provider([provider("a", "fa", "ma", cost=20)], request(cost=10), fallback_count=0)
        self.assertIn(("a", "cost_limit"), decision.rejected)

    def test_fallbacks_use_independent_families(self) -> None:
        decision = route_provider([provider("a", "fa", "ma"), provider("b", "fb", "mb"), provider("c", "fc", "mc")], request(), fallback_count=2)
        self.assertEqual(len(decision.fallback_provider_ids), 2)
        self.assertTrue(decision.valid)

    def test_insufficient_fallbacks_block(self) -> None:
        decision = route_provider([provider("a", "fa", "ma")], request(), fallback_count=1)
        self.assertIn("insufficient_independent_fallbacks", decision.blockers)

    def test_independent_judges_use_different_families(self) -> None:
        providers = [
            provider("a", "fa", "ma", capabilities=frozenset({"technical"})),
            provider("b", "fb", "mb", capabilities=frozenset({"editorial"})),
            provider("c", "fc", "mc", capabilities=frozenset({"technical", "editorial"})),
            provider("d", "fd", "md", capabilities=frozenset({"technical", "editorial"})),
        ]
        technical, editorial = independent_judge_routes(providers, request(capability="technical"), request(capability="editorial"))
        self.assertIsNotNone(technical.selected_provider_id)
        self.assertIsNotNone(editorial.selected_provider_id)
        self.assertNotEqual(technical.selected_provider_id, editorial.selected_provider_id)


class ArtifactContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = StageArtifactSpec("render", frozenset({"script"}), frozenset({"video"}), maximum_output_bytes=100)
        self.input = artifact("i", "s", "script", "script", "a" * 64)
        self.output = artifact("o", "s", "render", "video", "b" * 64, inputs=("a" * 64,))

    def test_valid_bundle_is_hash_bound(self) -> None:
        result = validate_stage_artifacts(self.spec, "s", [self.input], [self.output])
        self.assertTrue(result.valid)
        self.assertEqual(len(result.bundle_digest or ""), 64)

    def test_missing_input_blocks(self) -> None:
        result = validate_stage_artifacts(self.spec, "s", [], [self.output])
        self.assertIn("missing_input:script", result.blockers)

    def test_missing_output_blocks(self) -> None:
        result = validate_stage_artifacts(self.spec, "s", [self.input], [])
        self.assertIn("missing_output:video", result.blockers)

    def test_cross_story_artifact_blocks(self) -> None:
        wrong = artifact("o2", "other", "render", "video", "c" * 64, inputs=("a" * 64,))
        result = validate_stage_artifacts(self.spec, "s", [self.input], [wrong])
        self.assertIn("cross_story_artifact", result.blockers)

    def test_stale_output_binding_blocks(self) -> None:
        stale = artifact("o2", "s", "render", "video", "c" * 64, inputs=("d" * 64,))
        result = validate_stage_artifacts(self.spec, "s", [self.input], [stale])
        self.assertTrue(any(value.startswith("stale_or_unbound_output") for value in result.blockers))

    def test_output_size_limit_blocks(self) -> None:
        large = artifact("o2", "s", "render", "video", "c" * 64, inputs=("a" * 64,), size=101)
        result = validate_stage_artifacts(self.spec, "s", [self.input], [large])
        self.assertIn("output_size_limit", result.blockers)

    def test_schema_mismatch_blocks(self) -> None:
        wrong = artifact("o2", "s", "render", "video", "c" * 64, inputs=("a" * 64,), schema=2)
        result = validate_stage_artifacts(self.spec, "s", [self.input], [wrong])
        self.assertIn("output_schema_mismatch", result.blockers)


class ExecutionLedgerTests(unittest.TestCase):
    def test_append_builds_valid_chain(self) -> None:
        ledger = ExecutionLedger()
        ledger.append("registered", "s", stage=None, idempotency_key="1")
        ledger.append("claimed", "s", stage="research", idempotency_key="2")
        self.assertEqual(ledger.validate_chain(), ())

    def test_duplicate_idempotency_key_rejected(self) -> None:
        ledger = ExecutionLedger()
        ledger.append("registered", "s", stage=None, idempotency_key="1")
        with self.assertRaises(ValueError):
            ledger.append("registered", "s", stage=None, idempotency_key="1")

    def test_active_lease_blocks_second_worker(self) -> None:
        ledger = ExecutionLedger()
        now = datetime.now(timezone.utc)
        ledger.claim("s", "render", "a", now=now)
        with self.assertRaises(ValueError):
            ledger.claim("s", "render", "b", now=now)

    def test_stale_lease_expires(self) -> None:
        ledger = ExecutionLedger()
        now = datetime.now(timezone.utc)
        ledger.claim("s", "render", "a", lease_seconds=1, now=now)
        expired = ledger.expire_stale_leases(now=now + timedelta(seconds=2))
        self.assertEqual(len(expired), 1)

    def test_materialize_tracks_attempts_spend_and_artifacts(self) -> None:
        ledger = ExecutionLedger()
        ledger.append("registered", "s", stage=None, idempotency_key="1")
        ledger.append("claimed", "s", stage="render", idempotency_key="2")
        ledger.append("advanced", "s", stage="render", idempotency_key="3", payload={"cost": 2.5, "artifact_hashes": ["a" * 64]})
        state = ledger.materialize("s")
        self.assertEqual(state.attempts["render"], 1)
        self.assertEqual(state.spend, 2.5)
        self.assertEqual(state.artifact_hashes, ("a" * 64,))

    def test_replay_preserves_valid_chain(self) -> None:
        ledger = ExecutionLedger()
        ledger.append("registered", "s", stage=None, idempotency_key="1")
        replayed = replay_events(ledger.events)
        self.assertEqual(replayed.validate_chain(), ())
        self.assertEqual(replayed.events[-1].event_hash, ledger.events[-1].event_hash)

    def test_unknown_release_token_raises(self) -> None:
        with self.assertRaises(KeyError):
            ExecutionLedger().release("missing")


class SimulatorTests(unittest.TestCase):
    def test_exact_fifty_story_batch_completes(self) -> None:
        stories = [SimulatedStory(f"s{i}", f"topic{i % 10}", f"format{i % 5}", "low") for i in range(50)]
        result = simulate_batch(stories, [], SimulationPolicy(("research", "script")))
        self.assertTrue(result.valid)
        self.assertEqual(result.completed_count, 50)

    def test_fifty_one_story_batch_rejected(self) -> None:
        stories = [SimulatedStory(f"s{i}", "topic", "format", "low") for i in range(51)]
        with self.assertRaises(ValueError):
            simulate_batch(stories, [], SimulationPolicy(("research",)))

    def test_fatal_fault_quarantines_and_fails_batch(self) -> None:
        stories = [SimulatedStory("s", "topic", "format", "low")]
        result = simulate_batch(stories, [InjectedFault("s", "research", "fatal")], SimulationPolicy(("research",)))
        self.assertEqual(result.quarantined_count, 1)
        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()
