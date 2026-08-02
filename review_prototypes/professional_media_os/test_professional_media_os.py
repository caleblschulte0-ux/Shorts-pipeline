"""Isolated standard-library tests for the Professional Media OS prototype."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from .cli import build_demo
from .contracts import (
    Candidate,
    ContractError,
    ExperimentSpec,
    ExperimentState,
    FunnelStage,
    Maturity,
    PatternRecord,
    PortfolioConstraints,
    stable_hash,
    to_primitive,
)
from .counterfactual import (
    CounterfactualChange,
    CounterfactualRunner,
    TransparentHeuristicPredictor,
)
from .fixtures import candidate, evidence, genome, outcome, stage_metric
from .governance import (
    AuthorityEvidence,
    AuthorityStage,
    assess_authority_transition,
    assess_learning_eligibility,
    validate_experiment_for_canary,
)
from .knowledge import KnowledgeGraph, KnowledgeNode
from .lab import CandidateTournament, EvaluationContext
from .ledger import FileLedger, LedgerIntegrityError, MemoryLedger
from .operator import OperatorDiagnoser
from .patterns import PatternLibrary
from .portfolio import PortfolioPlanner, ScoredCandidate
from .research import (
    Claim,
    ClaimSupport,
    ResearchCompiler,
    ResearchPolicy,
    SourceRecord,
)


class ContractTests(unittest.TestCase):
    def test_content_genome_rejects_invalid_probability(self) -> None:
        with self.assertRaises(ContractError):
            genome(evidence_completeness=1.1)

    def test_stable_hash_is_order_independent_for_mappings(self) -> None:
        self.assertEqual(stable_hash({"a": 1, "b": 2}), stable_hash({"b": 2, "a": 1}))

    def test_fixture_serializes_without_custom_encoder(self) -> None:
        payload = to_primitive(candidate())
        encoded = json.dumps(payload, sort_keys=True)
        self.assertIn("candidate-consequence-001", encoded)


class LedgerTests(unittest.TestCase):
    def test_memory_ledger_builds_and_verifies_hash_chain(self) -> None:
        ledger = MemoryLedger()
        first = ledger.append("observation.recorded", {"value": 1})
        second = ledger.append("decision.recorded", {"value": 2})
        ledger.verify()
        self.assertEqual(second.previous_hash, first.event_hash)
        self.assertEqual(len(ledger.events()), 2)

    def test_file_ledger_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "institutional_memory.jsonl"
            ledger = FileLedger(path)
            ledger.append("observation.recorded", {"value": 1})
            content = path.read_text(encoding="utf-8")
            path.write_text(content.replace('"value":1', '"value":9'), encoding="utf-8")
            with self.assertRaises(LedgerIntegrityError):
                ledger.verify()


class CreativeLabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = evidence()
        self.context = EvaluationContext(
            evidence={self.evidence.evidence_id: self.evidence},
            allowed_rights_risks=("green",),
            allowed_formats_by_channel={"channel-daily": ("narrated-proof",)},
            recent_hook_structures_by_channel={"channel-daily": ()},
            recent_title_patterns_by_channel={"channel-daily": ()},
        )

    def test_tournament_blocks_unsupported_candidate(self) -> None:
        supported = candidate()
        unsupported = candidate(
            "candidate-unsupported-002",
            genome_value=genome(
                "genome-unsupported-002",
                evidence_completeness=0.20,
                media_feasibility=0.20,
                rights_risk="red",
            ),
            evidence_ids=(),
        )
        bundle = CandidateTournament().run((supported, unsupported), self.context)
        self.assertEqual(bundle.result.selected_candidate_id, supported.candidate_id)
        self.assertIn(unsupported.candidate_id, bundle.result.blocked_candidate_ids)
        self.assertTrue(bundle.result.reasons[unsupported.candidate_id])

    def test_tournament_preserves_evaluator_versions_and_counterfactuals(self) -> None:
        one = candidate()
        two = candidate(
            "candidate-proof-first-002",
            genome_value=genome(
                "genome-proof-first-002",
                hook_structure="proof-first",
                first_subject_ms=0,
                first_proof_ms=0,
                novelty_score=0.95,
            ),
            estimated_value=4.5,
        )
        bundle = CandidateTournament().run((one, two), self.context)
        self.assertEqual(len(bundle.result.ranked_candidate_ids), 2)
        self.assertGreaterEqual(len(bundle.result.evaluator_versions), 5)
        self.assertEqual(set(bundle.result.reasons), {one.candidate_id, two.candidate_id})


class PortfolioTests(unittest.TestCase):
    def test_planner_reserves_exploration_and_respects_cost(self) -> None:
        exploit = candidate(
            "candidate-exploit-001",
            genome_value=genome("genome-exploit-001", estimated_cost=0.50),
        )
        explore = candidate(
            "candidate-explore-001",
            genome_value=genome(
                "genome-explore-001",
                hook_structure="proof-first",
                estimated_cost=0.30,
            ),
            exploration=True,
        )
        too_expensive = candidate(
            "candidate-expensive-001",
            genome_value=genome(
                "genome-expensive-001",
                hook_structure="question-gap",
                estimated_cost=2.00,
            ),
        )
        constraints = PortfolioConstraints(
            target_count=2,
            maximum_total_cost=1.00,
            maximum_total_runtime_seconds=500.0,
            maximum_per_topic=2,
            maximum_per_channel={"channel-daily": 2},
            minimum_exploration=1,
            allowed_rights_risks=("green",),
            minimum_evidence_completeness=0.75,
            minimum_media_feasibility=0.60,
        )
        plan = PortfolioPlanner().plan(
            (
                ScoredCandidate(exploit, 0.95),
                ScoredCandidate(explore, 0.70),
                ScoredCandidate(too_expensive, 0.99),
            ),
            constraints,
        )
        self.assertIn(explore.candidate_id, plan.selected_candidate_ids)
        self.assertEqual(plan.exploration_count, 1)
        self.assertLessEqual(plan.total_cost, 1.00)
        self.assertIn("budget.cost-cap-exceeded", plan.rejected_reasons[too_expensive.candidate_id])


class KnowledgeGraphTests(unittest.TestCase):
    def test_inference_requires_registered_evidence(self) -> None:
        graph = KnowledgeGraph()
        graph.add_node(KnowledgeNode("entity-one", "entity", "Entity One"))
        graph.add_node(KnowledgeNode("pattern-one", "pattern", "Pattern One"))
        with self.assertRaises(ContractError):
            graph.infer(
                source_id="entity-one",
                relation="supports",
                target_id="pattern-one",
                evidence_ids=("evidence-missing-001",),
                confidence=0.8,
                maturity=Maturity.DIRECTIONAL,
            )

    def test_graph_preserves_contradictions_and_lineage(self) -> None:
        graph = KnowledgeGraph()
        first_evidence = evidence("evidence-graph-001")
        second_evidence = evidence("evidence-graph-002", confidence=0.75)
        graph.add_evidence(first_evidence)
        graph.add_evidence(second_evidence)
        graph.add_node(KnowledgeNode("hook-proof", "hook", "Proof first"))
        graph.add_node(KnowledgeNode("audience-daily", "audience", "Daily audience"))
        positive = graph.observe(
            source_id="hook-proof",
            relation="improves_hook",
            target_id="audience-daily",
            evidence_ids=(first_evidence.evidence_id,),
            confidence=0.8,
        )
        negative = graph.observe(
            source_id="hook-proof",
            relation="improves_hook",
            target_id="audience-daily",
            evidence_ids=(second_evidence.evidence_id,),
            confidence=0.7,
            properties={"direction": "negative"},
        )
        graph.mark_contradiction(positive.edge_id, negative.edge_id, "Different topic contexts")
        self.assertEqual(len(graph.contradictions()), 1)
        self.assertEqual(graph.lineage(positive.edge_id)[0].evidence_id, first_evidence.evidence_id)


class ResearchTests(unittest.TestCase):
    def _source(self, source_id: str, publisher: str, primary: bool) -> SourceRecord:
        return SourceRecord(
            source_id=source_id,
            publisher=publisher,
            source_type="official_document" if primary else "reported_analysis",
            canonical_locator=f"fixture://{source_id}",
            published_at="2026-07-26T10:00:00Z",
            retrieved_at="2026-07-26T11:00:00Z",
            primary=primary,
            authority_score=0.90,
            rights_status="green",
            content_hash=stable_hash({"source": source_id}),
        )

    def test_core_claim_fails_closed_without_primary_source(self) -> None:
        claim = Claim(
            claim_id="claim-core-001",
            text="The decision was formally reversed.",
            claim_type="outcome",
            importance="core",
            time_sensitive=True,
            required_for_promise=True,
        )
        source = self._source("source-report-001", "Publisher A", primary=False)
        support = ClaimSupport(
            claim_id=claim.claim_id,
            source_id=source.source_id,
            support_type="supports",
            locator="paragraph-3",
            excerpt_hash=stable_hash("excerpt-1"),
            confidence=0.90,
            observed_at="2026-07-26T11:00:00Z",
        )
        policy = ResearchPolicy(
            allowed_rights_statuses=("green",),
            minimum_authority_score=0.70,
            minimum_support_confidence=0.70,
            minimum_independent_publishers_for_core_claim=1,
            maximum_age_hours_for_time_sensitive_claim=24,
            require_primary_source_for_core_claim=True,
        )
        packet = ResearchCompiler().compile(
            claims=(claim,),
            sources=(source,),
            support=(support,),
            conflicts=(),
            policy=policy,
            now=datetime(2026, 7, 26, 12, tzinfo=timezone.utc),
        )
        self.assertFalse(packet.publishable)
        self.assertTrue(any("primary source" in reason for reason in packet.blocking_reasons))

    def test_core_claim_compiles_with_primary_and_independent_support(self) -> None:
        claim = Claim(
            claim_id="claim-core-002",
            text="The decision was formally reversed.",
            claim_type="outcome",
            importance="core",
            time_sensitive=True,
            required_for_promise=True,
        )
        sources = (
            self._source("source-primary-001", "Agency", primary=True),
            self._source("source-report-002", "Publisher B", primary=False),
        )
        support = tuple(
            ClaimSupport(
                claim_id=claim.claim_id,
                source_id=source.source_id,
                support_type="supports",
                locator="paragraph-3",
                excerpt_hash=stable_hash((source.source_id, "excerpt")),
                confidence=0.90,
                observed_at="2026-07-26T11:00:00Z",
            )
            for source in sources
        )
        policy = ResearchPolicy(
            allowed_rights_statuses=("green",),
            minimum_authority_score=0.70,
            minimum_support_confidence=0.70,
            minimum_independent_publishers_for_core_claim=2,
            maximum_age_hours_for_time_sensitive_claim=24,
            require_primary_source_for_core_claim=True,
        )
        packet = ResearchCompiler().compile(
            claims=(claim,),
            sources=sources,
            support=support,
            conflicts=(),
            policy=policy,
            now=datetime(2026, 7, 26, 12, tzinfo=timezone.utc),
        )
        self.assertTrue(packet.publishable)
        self.assertEqual(len(packet.evidence_refs), 2)


class PatternTests(unittest.TestCase):
    def test_pattern_exclusion_prevents_automatic_ranking(self) -> None:
        record = PatternRecord(
            pattern_id="pattern-proof-first-001",
            name="Proof-first authority reversal",
            applies_to=("authority-conflict", "proof-first"),
            excludes=("channel-daily",),
            structure=("show proof", "explain rule", "deliver reversal"),
            strengths={"hook": "strong"},
            failure_modes=("proof lacks context",),
            evidence_ids=("evidence-primary-001", "evidence-graph-001"),
            maturity=Maturity.ESTABLISHED,
            confidence=0.88,
            version="1.0.0",
            review_after="2026-10-01T00:00:00Z",
        )
        library = PatternLibrary((record,))
        matches = library.match(genome(hook_structure="proof-first"), context_labels=())
        self.assertEqual(len(matches), 1)
        self.assertFalse(matches[0].safe_for_automatic_ranking)
        self.assertIn("channel-daily", matches[0].excluded_context)


class CounterfactualTests(unittest.TestCase):
    def test_counterfactual_preserves_identity_fields_and_uncertainty(self) -> None:
        original = candidate()
        result = CounterfactualRunner(TransparentHeuristicPredictor()).run(
            original,
            (
                CounterfactualChange(
                    name="proof-now",
                    genome_updates={"first_proof_ms": 0},
                    rationale="Move proof forward.",
                ),
            ),
        )[0]
        self.assertEqual(result.changed_prediction.predictor_version, "1.0.0")
        self.assertTrue(result.interval_overlap)
        self.assertIn("hypothesis", result.decision_note)

    def test_counterfactual_rejects_channel_identity_change(self) -> None:
        with self.assertRaises(ContractError):
            CounterfactualRunner(TransparentHeuristicPredictor()).run(
                candidate(),
                (
                    CounterfactualChange(
                        name="wrong-channel",
                        genome_updates={"channel_id": "channel-other"},
                        rationale="Must not be allowed.",
                    ),
                ),
            )


class GovernanceTests(unittest.TestCase):
    def test_learning_eligibility_rejects_small_and_mixed_samples(self) -> None:
        result = assess_learning_eligibility(
            video_view_counts=(50, 120, 500),
            minimum_video_count=3,
            minimum_views_per_video=100,
            metric_definition_versions=("v1", "v2", "v2"),
        )
        self.assertFalse(result.eligible)
        self.assertEqual(result.mature_video_count, 2)
        self.assertFalse(result.metric_definition_consistent)

    def test_authority_cannot_skip_shadow_stage(self) -> None:
        evidence_value = AuthorityEvidence(
            benchmark_cases=100,
            false_rejection_rate=0.05,
            false_approval_rate=0.05,
            shadow_decisions=100,
            completed_canaries=50,
            rollback_tested=True,
            kill_switch_tested=True,
            lineage_complete=True,
            channel_identity_protected=True,
            production_files_modified_by_prototype=0,
            publishing_enabled_by_prototype=False,
        )
        decision = assess_authority_transition(
            AuthorityStage.RECORD_ONLY,
            AuthorityStage.CANARY_RECOMMENDATION,
            evidence_value,
        )
        self.assertFalse(decision.allowed)
        self.assertTrue(any("one step" in reason for reason in decision.reasons))

    def test_canary_experiment_requires_guardrails_and_small_allocation(self) -> None:
        spec = ExperimentSpec(
            experiment_id="experiment-hook-001",
            hypothesis="Proof-first improves the hook stage.",
            channel_ids=("channel-daily",),
            treatment="proof-first",
            control="current-default",
            primary_metric="derived_hook_score",
            guardrail_metrics=(),
            minimum_eligible_videos=2,
            minimum_views_per_video=100,
            maximum_allocation=0.30,
            stop_conditions=(),
            state=ExperimentState.CANARY,
        )
        reasons = validate_experiment_for_canary(spec)
        self.assertGreaterEqual(len(reasons), 3)


class OperatorTests(unittest.TestCase):
    def test_operator_identifies_hook_difference_without_claiming_causality(self) -> None:
        baseline_candidate = candidate()
        current_candidate = candidate(
            "candidate-current-001",
            genome_value=genome(
                "genome-current-001",
                first_subject_ms=1800,
                first_proof_ms=4200,
                hook_structure="chronology",
            ),
        )
        baseline_outcome = outcome("video-baseline-001", baseline_candidate, hook=0.75)
        current_outcome = outcome("video-current-001", current_candidate, hook=0.55)
        report = OperatorDiagnoser().compare(
            current=current_outcome,
            baseline=baseline_outcome,
            current_genome=current_candidate.genome,
            baseline_genome=baseline_candidate.genome,
        )
        hook_findings = [item for item in report.findings if item.stage is FunnelStage.HOOK]
        self.assertEqual(len(hook_findings), 1)
        self.assertTrue(any("first proof time" in item for item in hook_findings[0].plausible_contributors))
        self.assertTrue(any("does not establish causality" in item for item in hook_findings[0].excluded_claims))

    def test_operator_refuses_mixed_metric_definitions(self) -> None:
        baseline_candidate = candidate()
        current_candidate = candidate(
            "candidate-current-002",
            genome_value=genome("genome-current-002"),
        )
        baseline_outcome = outcome(
            "video-baseline-002",
            baseline_candidate,
            metric_definition_version="v1",
        )
        current_outcome = outcome(
            "video-current-002",
            current_candidate,
            metric_definition_version="v2",
        )
        report = OperatorDiagnoser().compare(
            current=current_outcome,
            baseline=baseline_outcome,
            current_genome=current_candidate.genome,
            baseline_genome=baseline_candidate.genome,
        )
        self.assertFalse(report.comparable_stages)
        self.assertTrue(all("definition versions differ" in item for item in report.unknowns))


class DemoTests(unittest.TestCase):
    def test_demo_is_in_memory_and_fail_closed(self) -> None:
        demo = build_demo()
        self.assertFalse(demo["scope"]["production_modified"])
        self.assertFalse(demo["scope"]["publishing_enabled"])
        self.assertTrue(demo["tournament"].blocked_candidate_ids)
        self.assertEqual(len(demo["portfolio"].selected_candidate_ids), 2)


if __name__ == "__main__":
    unittest.main()
