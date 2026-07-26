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
            sum(selected_issue_map[edit.issue_id].expected_uplift * selected_issue_map[edit.issue_id].confidence / 10.0 for edit in selected),
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


def money_goes_retention_blueprint() -> tuple[EditIssue, ...]:
    return (
        EditIssue("restore_hook", EditArea.RETENTION, "opening", "The current opening underperforms the earlier cut.", "Compare hook candidates and rebuild the first 8 seconds around the strongest visual contradiction.", 8.5, 8.0, 1.0, 3.0, EditPass.STORY, 0.0, is_hook=True),
        EditIssue("reduce_opening_load", EditArea.COGNITIVE_LOAD, "opening", "The opening introduces the mechanism before the question is fully established.", "Delay secondary explanation until after the first visible paycheck split.", 7.5, 8.0, 0.6, 1.5, EditPass.SCRIPT, 3.0, depends_on=("restore_hook",)),
        EditIssue("replace_wrong_region_media", EditArea.CONTINUITY, "gas_station_media", "The gas-station image implies the wrong region.", "Replace it with region-correct evidence or clearly labeled illustrative media.", 9.0, 10.0, 0.7, 1.5, EditPass.MEDIA, 92.0, hard_blocker=True),
        EditIssue("replace_statement_card", EditArea.VISUAL_READABILITY, "bill_counting", "The bill-counting fallback is a statement card instead of visible action.", "Show hands separating the paycheck into concrete destinations with one focal stack at a time.", 8.0, 9.0, 0.8, 3.0, EditPass.ANIMATION, 118.0),
        EditIssue("caption_safe_area", EditArea.CAPTIONS, "all_captions", "Caption placement has not been audited against mobile controls and focal evidence.", "Reflow cues by phrase, enforce two lines, and reserve a protected caption zone in every shot.", 7.0, 7.5, 0.5, 2.5, EditPass.CAPTION, 0.0),
        EditIssue("character_specific_humor", EditArea.HUMOR, "middle_character", "Personality is weak and generic.", "Add one fast character-specific reaction tied to the paycheck misunderstanding rather than a detached joke.", 5.5, 6.5, 0.35, 1.5, EditPass.SCRIPT, 70.0),
        EditIssue("human_consequence", EditArea.EMOTION, "paycheck_consequence", "The mechanism is explained more strongly than its human consequence.", "Show what the missing amount changes for the character before resolving the flow.", 7.0, 7.0, 0.6, 2.0, EditPass.STORY, 55.0),
        EditIssue("final_paycheck_callback", EditArea.PAYOFF, "ending", "The ending does not fully return to the opening paycheck image.", "Reassemble the same paycheck image with every destination visible and the character's consequence resolved.", 8.5, 8.5, 0.9, 3.0, EditPass.ANIMATION, 220.0, is_payoff=True, depends_on=("restore_hook", "human_consequence")),
    )
