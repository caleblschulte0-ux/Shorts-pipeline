"""Stage-aware operator diagnostics for the isolated Professional Media OS prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import (
    ContentGenome,
    ContractError,
    FunnelStage,
    StageMetrics,
    VideoOutcome,
)


@dataclass(frozen=True)
class DiagnosticFinding:
    stage: FunnelStage
    severity: str
    observation: str
    plausible_contributors: Tuple[str, ...]
    excluded_claims: Tuple[str, ...]
    evidence: Tuple[str, ...]


@dataclass(frozen=True)
class OperatorReport:
    current_video_id: str
    baseline_video_id: str
    comparable_stages: Tuple[FunnelStage, ...]
    findings: Tuple[DiagnosticFinding, ...]
    unknowns: Tuple[str, ...]
    summary: str


class OperatorDiagnoser:
    """Explain concrete differences without claiming unsupported causality."""

    def compare(
        self,
        *,
        current: VideoOutcome,
        baseline: VideoOutcome,
        current_genome: ContentGenome,
        baseline_genome: ContentGenome,
        material_delta: float = 0.05,
    ) -> OperatorReport:
        if current.channel_id != baseline.channel_id:
            raise ContractError("operator comparison requires the same channel")
        if current.genome_id != current_genome.genome_id:
            raise ContractError("current outcome and genome ids do not match")
        if baseline.genome_id != baseline_genome.genome_id:
            raise ContractError("baseline outcome and genome ids do not match")
        if material_delta <= 0:
            raise ContractError("material_delta must be positive")

        current_stages = {item.stage: item for item in current.stages}
        baseline_stages = {item.stage: item for item in baseline.stages}
        findings: List[DiagnosticFinding] = []
        unknowns: List[str] = []
        comparable: List[FunnelStage] = []

        for stage in FunnelStage:
            current_metric = current_stages.get(stage)
            baseline_metric = baseline_stages.get(stage)
            reason = self._incomparable_reason(current_metric, baseline_metric)
            if reason is not None:
                unknowns.append(f"{stage.value}: {reason}")
                continue

            assert current_metric is not None and baseline_metric is not None
            assert current_metric.value is not None and baseline_metric.value is not None
            comparable.append(stage)
            delta = current_metric.value - baseline_metric.value
            if abs(delta) < material_delta:
                continue

            contributors = self._contributors(
                stage,
                current_genome=current_genome,
                baseline_genome=baseline_genome,
                current_timeline=current.timeline_events_ms,
                baseline_timeline=baseline.timeline_events_ms,
            )
            direction = "lower" if delta < 0 else "higher"
            severity = "high" if abs(delta) >= material_delta * 2 else "medium"
            excluded = (
                "This comparison does not establish causality.",
                "Topic, distribution, audience mix, and platform variance may contribute.",
            )
            findings.append(
                DiagnosticFinding(
                    stage=stage,
                    severity=severity,
                    observation=(
                        f"{current_metric.metric_name} is {abs(delta):.4f} {direction} "
                        f"than baseline using definition "
                        f"{current_metric.metric_definition_version}."
                    ),
                    plausible_contributors=contributors,
                    excluded_claims=excluded,
                    evidence=(
                        f"current sample={current_metric.sample_size}",
                        f"baseline sample={baseline_metric.sample_size}",
                        f"current value={current_metric.value}",
                        f"baseline value={baseline_metric.value}",
                    ),
                )
            )

        findings.sort(
            key=lambda item: (
                0 if item.severity == "high" else 1,
                list(FunnelStage).index(item.stage),
            )
        )
        if findings:
            leading = findings[0]
            summary = (
                f"The clearest eligible difference is at the {leading.stage.value} stage. "
                "Review the listed creative and timeline changes before changing topic policy."
            )
        elif comparable:
            summary = (
                "No comparable funnel stage changed beyond the material threshold. "
                "Do not manufacture a creative diagnosis from normal variance."
            )
        else:
            summary = (
                "No funnel stage is safely comparable. Wait for mature, definition-compatible data."
            )

        return OperatorReport(
            current_video_id=current.video_id,
            baseline_video_id=baseline.video_id,
            comparable_stages=tuple(comparable),
            findings=tuple(findings),
            unknowns=tuple(unknowns),
            summary=summary,
        )

    @staticmethod
    def _incomparable_reason(
        current: Optional[StageMetrics],
        baseline: Optional[StageMetrics],
    ) -> Optional[str]:
        if current is None or baseline is None:
            return "metric missing from one outcome"
        if not current.eligible or not baseline.eligible:
            return "one or both samples are ineligible"
        if current.value is None or baseline.value is None:
            return "eligible value is unexpectedly unknown"
        if current.metric_name != baseline.metric_name:
            return "metric names differ"
        if current.metric_definition_version != baseline.metric_definition_version:
            return "metric definition versions differ"
        return None

    @staticmethod
    def _contributors(
        stage: FunnelStage,
        *,
        current_genome: ContentGenome,
        baseline_genome: ContentGenome,
        current_timeline: Mapping[str, int],
        baseline_timeline: Mapping[str, int],
    ) -> Tuple[str, ...]:
        contributors: List[str] = []

        def changed(label: str, current_value: object, baseline_value: object) -> None:
            if current_value != baseline_value:
                contributors.append(
                    f"{label} changed from {baseline_value!r} to {current_value!r}."
                )

        if stage is FunnelStage.EXPOSURE:
            changed("title pattern", current_genome.title_pattern, baseline_genome.title_pattern)
            changed(
                "first visual type",
                current_genome.first_visual_type,
                baseline_genome.first_visual_type,
            )
            changed("event type", current_genome.event_type, baseline_genome.event_type)

        elif stage is FunnelStage.HOOK:
            changed("hook structure", current_genome.hook_structure, baseline_genome.hook_structure)
            changed(
                "first subject time",
                current_genome.first_subject_ms,
                baseline_genome.first_subject_ms,
            )
            changed(
                "first proof time",
                current_genome.first_proof_ms,
                baseline_genome.first_proof_ms,
            )
            self._timeline_change(contributors, "hook_end", current_timeline, baseline_timeline)
            self._timeline_change(contributors, "first_proof", current_timeline, baseline_timeline)

        elif stage is FunnelStage.BODY:
            changed(
                "narrative structure",
                current_genome.narrative_structure,
                baseline_genome.narrative_structure,
            )
            changed("beat count", current_genome.beat_count, baseline_genome.beat_count)
            changed(
                "average shot seconds",
                current_genome.average_shot_seconds,
                baseline_genome.average_shot_seconds,
            )
            changed("open-loop count", current_genome.open_loop_count, baseline_genome.open_loop_count)

        elif stage is FunnelStage.ENDING:
            changed(
                "reveal position",
                current_genome.reveal_position,
                baseline_genome.reveal_position,
            )
            changed("payoff type", current_genome.payoff_type, baseline_genome.payoff_type)
            self._timeline_change(contributors, "payoff_start", current_timeline, baseline_timeline)

        elif stage is FunnelStage.SATISFACTION:
            changed("viewer question", current_genome.viewer_question, baseline_genome.viewer_question)
            changed("payoff type", current_genome.payoff_type, baseline_genome.payoff_type)
            changed(
                "evidence completeness",
                current_genome.evidence_completeness,
                baseline_genome.evidence_completeness,
            )

        elif stage is FunnelStage.EXPANSION:
            changed("title pattern", current_genome.title_pattern, baseline_genome.title_pattern)
            changed("event type", current_genome.event_type, baseline_genome.event_type)
            changed("novelty score", current_genome.novelty_score, baseline_genome.novelty_score)

        if not contributors:
            contributors.append(
                "No tracked genome or timeline field changed for this stage; investigate distribution and untracked factors."
            )
        return tuple(contributors)

    @staticmethod
    def _timeline_change(
        contributors: List[str],
        event_name: str,
        current_timeline: Mapping[str, int],
        baseline_timeline: Mapping[str, int],
    ) -> None:
        current_value = current_timeline.get(event_name)
        baseline_value = baseline_timeline.get(event_name)
        if current_value != baseline_value:
            contributors.append(
                f"Timeline event '{event_name}' changed from {baseline_value!r} ms to {current_value!r} ms."
            )
