from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .autonomous_batch_controller import AutonomousBatchController, BatchPolicy
from .autonomous_decision_engine import DecisionPolicy, StageOutcome
from .production_stage_graph import ProductionGraph, StageName, build_default_graph
from .story_intake_contract import IntakePolicy, IntakeReport, StoryBrief, validate_story_batch


@dataclass(frozen=True)
class ProgramPlan:
    intake: IntakeReport
    graph_digest: str
    registered_story_ids: tuple[str, ...]
    initial_admitted_story_ids: tuple[str, ...]
    initial_assignments: tuple[tuple[str, str], ...]
    ready: bool
    blockers: tuple[str, ...]


class AutonomousProgram:
    def __init__(self, controller: AutonomousBatchController, intake: IntakeReport) -> None:
        self.controller = controller
        self.intake = intake

    def cycle(
        self,
        *,
        stage_capacities: dict[StageName, int],
        outcomes: Iterable[StageOutcome] = (),
    ) -> tuple[tuple[str, str], ...]:
        for outcome in outcomes:
            self.controller.record_outcome(outcome)
        self.controller.admit_pending()
        assignments = self.controller.claim_work(stage_capacities)
        return tuple((item.story_id, item.stage.value) for item in assignments)


def compile_autonomous_program(
    briefs: Iterable[StoryBrief],
    *,
    intake_policy: IntakePolicy = IntakePolicy(),
    batch_policy: BatchPolicy = BatchPolicy(),
    decision_policy: DecisionPolicy = DecisionPolicy(),
    graph: ProductionGraph | None = None,
    initial_stage_capacities: dict[StageName, int] | None = None,
) -> tuple[AutonomousProgram, ProgramPlan]:
    intake = validate_story_batch(briefs, intake_policy)
    active_graph = graph or build_default_graph(require_fact_review=True)
    controller = AutonomousBatchController(
        active_graph,
        batch_policy=batch_policy,
        decision_policy=decision_policy,
    )
    controller.register(intake.accepted)
    admitted = controller.admit_pending()
    capacities = initial_stage_capacities or {StageName.INTAKE: batch_policy.maximum_active_stories}
    assignments = controller.claim_work(capacities)

    blockers: list[str] = []
    if not intake.valid:
        blockers.extend(intake.warnings or ("intake_invalid",))
    if not intake.accepted:
        blockers.append("no_accepted_stories")
    blockers.extend(controller.audit_invariants())
    plan = ProgramPlan(
        intake=intake,
        graph_digest=active_graph.digest,
        registered_story_ids=tuple(sorted(item.story_id for item in intake.accepted)),
        initial_admitted_story_ids=tuple(admitted),
        initial_assignments=tuple((item.story_id, item.stage.value) for item in assignments),
        ready=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )
    return AutonomousProgram(controller, intake), plan
