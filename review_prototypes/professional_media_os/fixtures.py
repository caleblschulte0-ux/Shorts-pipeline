"""Synthetic fixtures for isolated demos and tests only."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping, Optional, Sequence, Tuple

from .contracts import (
    Candidate,
    ContentGenome,
    EvidenceRef,
    FunnelStage,
    Maturity,
    StageMetrics,
    VideoOutcome,
)


def evidence(
    evidence_id: str = "evidence-primary-001",
    *,
    confidence: float = 0.95,
    rights_status: str = "green",
) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        source_type="primary_document",
        locator="fixture://source/1#paragraph-2",
        observed_at="2026-07-26T12:00:00Z",
        confidence=confidence,
        rights_status=rights_status,
        excerpt_hash="a" * 64,
        maturity=Maturity.ANECDOTE,
    )


def genome(
    genome_id: str = "genome-candidate-001",
    *,
    channel_id: str = "channel-daily",
    event_type: str = "authority-conflict",
    hook_structure: str = "consequence-first",
    title_pattern: str = "entity-plus-consequence",
    first_subject_ms: int = 100,
    first_proof_ms: Optional[int] = 650,
    evidence_completeness: float = 0.95,
    media_feasibility: float = 0.90,
    rights_risk: str = "green",
    estimated_cost: float = 0.25,
    estimated_runtime_seconds: float = 120.0,
    novelty_score: float = 0.80,
    presentation_format: str = "narrated-proof",
) -> ContentGenome:
    return ContentGenome(
        genome_id=genome_id,
        schema_version="content-genome/v1",
        channel_id=channel_id,
        subject_entities=("fixture-entity",),
        event_type=event_type,
        viewer_question="What happened when the rule was followed exactly?",
        emotional_driver="justice",
        payoff_type="reversal",
        hook_structure=hook_structure,
        first_visual_type="primary-proof-frame",
        first_subject_ms=first_subject_ms,
        first_proof_ms=first_proof_ms,
        narrative_structure="setup-escalation-reversal",
        beat_count=5,
        reveal_position=0.72,
        open_loop_count=2,
        presentation_format=presentation_format,
        caption_style="word-emphasis",
        average_shot_seconds=1.4,
        visual_sources=("primary", "licensed"),
        title_pattern=title_pattern,
        duration_seconds=38.0,
        evidence_completeness=evidence_completeness,
        media_feasibility=media_feasibility,
        rights_risk=rights_risk,
        estimated_cost=estimated_cost,
        estimated_runtime_seconds=estimated_runtime_seconds,
        novelty_score=novelty_score,
        tags=("fixture", "review-only"),
        created_at="2026-07-26T12:00:00Z",
    )


def candidate(
    candidate_id: str = "candidate-consequence-001",
    *,
    genome_value: Optional[ContentGenome] = None,
    hypothesis_id: str = "hypothesis-fixture-001",
    evidence_ids: Sequence[str] = ("evidence-primary-001",),
    estimated_value: float = 4.0,
    exploration: bool = False,
    opening_line: str = "His own rule got him removed.",
    payoff_line: str = "Following it exactly exposed the contradiction and reversed the decision.",
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        hypothesis_id=hypothesis_id,
        genome=genome_value or genome(),
        promise="The authority figure's own rule creates the final reversal.",
        opening_line=opening_line,
        payoff_line=payoff_line,
        evidence_ids=tuple(evidence_ids),
        estimated_value=estimated_value,
        exploration=exploration,
        created_at="2026-07-26T12:00:00Z",
    )


def stage_metric(
    stage: FunnelStage,
    value: Optional[float],
    *,
    eligible: bool = True,
    sample_size: int = 1000,
    metric_definition_version: str = "youtube-shorts/v2",
) -> StageMetrics:
    return StageMetrics(
        stage=stage,
        eligible=eligible,
        sample_size=sample_size,
        value=value if eligible else None,
        metric_name=f"derived_{stage.value}_score",
        metric_definition_version=metric_definition_version,
        observed_at="2026-07-27T12:00:00Z",
    )


def outcome(
    video_id: str,
    candidate_value: Candidate,
    *,
    hook: float = 0.70,
    body: float = 0.65,
    ending: float = 0.62,
    satisfaction: float = 0.08,
    expansion: float = 0.55,
    exposure: float = 0.60,
    metric_definition_version: str = "youtube-shorts/v2",
) -> VideoOutcome:
    values = {
        FunnelStage.EXPOSURE: exposure,
        FunnelStage.HOOK: hook,
        FunnelStage.BODY: body,
        FunnelStage.ENDING: ending,
        FunnelStage.SATISFACTION: satisfaction,
        FunnelStage.EXPANSION: expansion,
    }
    return VideoOutcome(
        video_id=video_id,
        candidate_id=candidate_value.candidate_id,
        channel_id=candidate_value.genome.channel_id,
        genome_id=candidate_value.genome.genome_id,
        stages=tuple(
            stage_metric(
                stage,
                value,
                metric_definition_version=metric_definition_version,
            )
            for stage, value in values.items()
        ),
        timeline_events_ms={
            "hook_end": 2500,
            "first_proof": candidate_value.genome.first_proof_ms or 0,
            "payoff_start": 27000,
        },
        production_cost=candidate_value.genome.estimated_cost,
        production_runtime_seconds=candidate_value.genome.estimated_runtime_seconds,
        observed_at="2026-07-27T12:00:00Z",
    )
