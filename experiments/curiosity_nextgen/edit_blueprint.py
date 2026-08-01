from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class EditArea(str, Enum):
    RETENTION = "retention"
    COGNITIVE_LOAD = "cognitive_load"
    CAPTIONS = "captions"
    CONTINUITY = "continuity"
    VISUAL_READABILITY = "visual_readability"
    HUMOR = "humor"
    EMOTION = "emotion"
    AUDIO = "audio"
    PAYOFF = "payoff"
    PACKAGING = "packaging"


class EditPass(str, Enum):
    STORY = "story"
    SCRIPT = "script"
    MEDIA = "media"
    ANIMATION = "animation"
    AUDIO = "audio"
    CAPTION = "caption"
    PACKAGE = "package"
    REVIEW = "review"


@dataclass(frozen=True)
class EditIssue:
    issue_id: str
    area: EditArea
    target_id: str
    description: str
    repair: str
    severity: float
    confidence: float
    expected_uplift: float
    effort: float
    edit_pass: EditPass
    start_seconds: float = 0.0
    is_hook: bool = False
    is_payoff: bool = False
    hard_blocker: bool = False
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.issue_id or not self.target_id or not self.description.strip() or not self.repair.strip():
            raise ValueError("edit issue identifiers and text are required")
        for name in ("severity", "confidence", "expected_uplift"):
            value = getattr(self, name)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"{name} must be between 0 and 10")
        if self.effort <= 0:
            raise ValueError("effort must be positive")
        if self.start_seconds < 0:
            raise ValueError("start_seconds cannot be negative")


@dataclass(frozen=True)
class PlannedEdit:
    issue_id: str
    priority_score: float
    cumulative_effort: float
    edit_pass: EditPass
    target_id: str
    repair: str


@dataclass(frozen=True)
class EditBlueprint:
    selected_edits: tuple[PlannedEdit, ...]
    deferred_issue_ids: tuple[str, ...]
    blocked_issue_ids: tuple[str, ...]
    pass_order: tuple[EditPass, ...]
    total_effort: float
    projected_uplift: float
    coverage_by_area: tuple[tuple[EditArea, int], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class StoryEditCandidate:
    story_id: str
    topic_family: str
    format_family: str
    issues: tuple[EditIssue, ...]
    readiness: float
    novelty: float
    strategic_value: float = 5.0

    def __post_init__(self) -> None:
        if not self.story_id.strip() or not self.topic_family.strip() or not self.format_family.strip():
            raise ValueError("story_id, topic_family, and format_family are required")
        if not self.issues:
            raise ValueError("each story candidate requires at least one edit issue")
        for name in ("readiness", "novelty", "strategic_value"):
            value = getattr(self, name)
            if not 0.0 <= value <= 10.0:
                raise ValueError(f"{name} must be between 0 and 10")


@dataclass(frozen=True)
class StoryEditPlan:
    story_id: str
    topic_family: str
    format_family: str
    priority_score: float
    blueprint: EditBlueprint


@dataclass(frozen=True)
class BatchEditProgram:
    selected_plans: tuple[StoryEditPlan, ...]
    deferred_story_ids: tuple[str, ...]
    quarantined_story_ids: tuple[str, ...]
    total_effort: float
    topic_family_counts: tuple[tuple[str, int], ...]
    format_family_counts: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...]


def _priority(issue: EditIssue) -> float:
    value = issue.severity * issue.confidence * max(0.2, issue.expected_uplift) / issue.effort
    if issue.start_seconds <= 15:
        value *= 1.35
    if issue.is_hook:
        value *= 1.3
    if issue.is_payoff:
        value *= 1.2
    if issue.hard_blocker:
        value *= 2.0
    if issue.area in {EditArea.RETENTION, EditArea.CONTINUITY, EditArea.CAPTIONS}:
        value *= 1.08
    return round(value, 4)


def _deduplicate(issues: tuple[EditIssue, ...]) -> tuple[EditIssue, ...]:
    grouped: dict[tuple[EditArea, str, str], EditIssue] = {}
    for issue in issues:
        key = (issue.area, issue.target_id, issue.repair.strip().lower())
        existing = grouped.get(key)
        if existing is None or _priority(issue) > _priority(existing):
            grouped[key] = issue
    return tuple(grouped.values())


def _topological_order(issues: tuple[EditIssue, ...]) -> tuple[EditIssue, ...]:
    by_id = {issue.issue_id: issue for issue in issues}
    if len(by_id) != len(issues):
        raise ValueError("duplicate issue_id")
    for issue in issues:
        unknown = set(issue.depends_on) - set(by_id)
        if unknown:
            raise ValueError(f"unknown dependencies for {issue.issue_id}: {sorted(unknown)}")

    incoming = {issue.issue_id: set(issue.depends_on) for issue in issues}
    ordered: list[EditIssue] = []
    available = [issue for issue in issues if not incoming[issue.issue_id]]

    while available:
        available.sort(key=lambda item: (_priority(item), item.hard_blocker, -item.start_seconds), reverse=True)
        current = available.pop(0)
        ordered.append(current)
        for candidate in issues:
            dependencies = incoming[candidate.issue_id]
            if current.issue_id in dependencies:
                dependencies.remove(current.issue_id)
                if not dependencies and candidate not in ordered and candidate not in available:
                    available.append(candidate)

    if len(ordered) != len(issues):
        raise ValueError("edit issue dependency cycle")
    return tuple(ordered)


def build_edit_blueprint(issues: Iterable[EditIssue], effort_budget: float) -> EditBlueprint:
    if effort_budget <= 0:
        raise ValueError("effort_budget must be positive")
    raw = tuple(issues)
    if not raw:
        raise ValueError("at least one edit issue is required")

    unique_ids = [issue.issue_id for issue in raw]
    if len(unique_ids) != len(set(unique_ids)):
        raise ValueError("duplicate issue_id")

    deduped = _deduplicate(raw)
    ordered = _topological_order(deduped)
    selected: list[PlannedEdit] = []
    selected_ids: set[str] = set()
    deferred: list[str] = []
    cumulative = 0.0

    for issue in ordered:
        if not set(issue.depends_on).issubset(selected_ids):
            deferred.append(issue.issue_id)
            continue
        if cumulative + issue.effort > effort_budget and not issue.hard_blocker:
            deferred.append(issue.issue_id)
            continue
        cumulative += issue.effort
        selected_ids.add(issue.issue_id)
        selected.append(
            PlannedEdit(
                issue_id=issue.issue_id,
                priority_score=_priority(issue),
                cumulative_effort=round(cumulative, 2),
                edit_pass=issue.edit_pass,
                target_id=issue.target_id,
                repair=issue.repair,
            )
        )

    selected_issue_map = {issue.issue_id: issue for issue in deduped}
    blocked = tuple(
        issue.issue_id
        for issue in deduped
        if issue.hard_blocker and issue.issue_id not in selected_ids
    )
    pass_order = tuple(dict.fromkeys(edit.edit_pass for edit in selected))
    projected = round(
        min(
            10.0,
            sum(
                selected_issue_map[edit.issue_id].expected_uplift
                * selected_issue_map[edit.issue_id].confidence
                / 10.0
                for edit in selected
            ),
        ),
        2,
    )
    area_counts: dict[EditArea, int] = {}
    for edit in selected:
        area = selected_issue_map[edit.issue_id].area
        area_counts[area] = area_counts.get(area, 0) + 1

    warnings: list[str] = []
    if blocked:
        warnings.append("one or more hard blockers could not be scheduled within dependency constraints")
    if not any(selected_issue_map[edit.issue_id].is_hook for edit in selected):
        warnings.append("the selected plan contains no hook-focused edit")
    if not any(selected_issue_map[edit.issue_id].is_payoff for edit in selected):
        warnings.append("the selected plan contains no payoff-focused edit")
    if len(area_counts) < min(4, len({issue.area for issue in deduped})):
        warnings.append("the effort budget concentrates work in too few creative areas")

    return EditBlueprint(
        selected_edits=tuple(selected),
        deferred_issue_ids=tuple(deferred),
        blocked_issue_ids=blocked,
        pass_order=pass_order,
        total_effort=round(cumulative, 2),
        projected_uplift=projected,
        coverage_by_area=tuple(sorted(area_counts.items(), key=lambda item: item[0].value)),
        warnings=tuple(warnings),
    )


def _story_priority(candidate: StoryEditCandidate, blueprint: EditBlueprint) -> float:
    readiness_factor = 0.5 + candidate.readiness / 10.0
    novelty_factor = 0.5 + candidate.novelty / 10.0
    strategic_factor = 0.5 + candidate.strategic_value / 10.0
    blocker_factor = 1.25 if any(issue.hard_blocker for issue in candidate.issues) else 1.0
    return round(
        blueprint.projected_uplift
        * readiness_factor
        * novelty_factor
        * strategic_factor
        * blocker_factor
        / max(0.5, blueprint.total_effort),
        4,
    )


def build_batch_edit_program(
    candidates: Iterable[StoryEditCandidate],
    *,
    total_effort_budget: float,
    per_story_effort_cap: float,
    max_stories: int = 50,
    max_per_topic_family: int = 10,
    # None -> no format-family cap beyond max_stories itself: an EXPLICIT
    # 50-story capacity request must not be silently truncated by an
    # implicit default (the cap still binds whenever a caller sets it).
    max_per_format_family: int | None = None,
) -> BatchEditProgram:
    """Plan reusable quality repairs across an autonomous multi-video portfolio."""
    if total_effort_budget <= 0 or per_story_effort_cap <= 0:
        raise ValueError("effort budgets must be positive")
    if not 1 <= max_stories <= 50:
        raise ValueError("max_stories must be between 1 and 50")
    if max_per_format_family is None:
        max_per_format_family = max_stories
    if max_per_topic_family <= 0 or max_per_format_family <= 0:
        raise ValueError("family caps must be positive")

    items = tuple(candidates)
    if not items:
        raise ValueError("at least one story candidate is required")
    story_ids = [candidate.story_id for candidate in items]
    if len(story_ids) != len(set(story_ids)):
        raise ValueError("duplicate story_id")

    planned: list[StoryEditPlan] = []
    quarantined: list[str] = []
    for candidate in items:
        blueprint = build_edit_blueprint(candidate.issues, per_story_effort_cap)
        if blueprint.blocked_issue_ids:
            quarantined.append(candidate.story_id)
            continue
        planned.append(
            StoryEditPlan(
                story_id=candidate.story_id,
                topic_family=candidate.topic_family,
                format_family=candidate.format_family,
                priority_score=_story_priority(candidate, blueprint),
                blueprint=blueprint,
            )
        )

    planned.sort(key=lambda plan: (-plan.priority_score, plan.story_id))
    selected: list[StoryEditPlan] = []
    deferred: list[str] = []
    topic_counts: dict[str, int] = {}
    format_counts: dict[str, int] = {}
    spent = 0.0

    for plan in planned:
        if len(selected) >= max_stories:
            deferred.append(plan.story_id)
            continue
        if topic_counts.get(plan.topic_family, 0) >= max_per_topic_family:
            deferred.append(plan.story_id)
            continue
        if format_counts.get(plan.format_family, 0) >= max_per_format_family:
            deferred.append(plan.story_id)
            continue
        if spent + plan.blueprint.total_effort > total_effort_budget:
            deferred.append(plan.story_id)
            continue

        selected.append(plan)
        spent += plan.blueprint.total_effort
        topic_counts[plan.topic_family] = topic_counts.get(plan.topic_family, 0) + 1
        format_counts[plan.format_family] = format_counts.get(plan.format_family, 0) + 1

    warnings: list[str] = []
    if quarantined:
        warnings.append("one or more stories require quarantine before autonomous repair")
    if deferred:
        warnings.append("one or more stories were deferred by portfolio capacity, diversity, or effort limits")
    if not selected:
        warnings.append("no story repair plans were admitted")

    return BatchEditProgram(
        selected_plans=tuple(selected),
        deferred_story_ids=tuple(sorted(deferred)),
        quarantined_story_ids=tuple(sorted(quarantined)),
        total_effort=round(spent, 2),
        topic_family_counts=tuple(sorted(topic_counts.items())),
        format_family_counts=tuple(sorted(format_counts.items())),
        warnings=tuple(warnings),
    )
