from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from statistics import mean
from typing import Mapping
import re


@dataclass(frozen=True)
class DataPoint:
    label: str
    value: float
    period: float | None = None


@dataclass(frozen=True)
class StoryBeat:
    role: str
    narration: str
    focus_label: str = ""
    duration: float = 4.0


@dataclass(frozen=True)
class StoryDraft:
    slug: str
    topic: str
    claim: str
    unit: str
    data: tuple[DataPoint, ...]
    beats: tuple[StoryBeat, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "StoryDraft":
        story = cls(
            slug=str(raw.get("slug", "")).strip(),
            topic=str(raw.get("topic", "")).strip(),
            claim=str(raw.get("claim", "")).strip(),
            unit=str(raw.get("unit", "")).strip(),
            data=tuple(
                DataPoint(
                    str(p["label"]).strip(),
                    float(p["value"]),
                    None if p.get("period") is None else float(p["period"]),
                )
                for p in raw.get("data", ())
            ),
            beats=tuple(
                StoryBeat(
                    str(b["role"]).strip(),
                    str(b["narration"]).strip(),
                    str(b.get("focus_label", "")).strip(),
                    float(b.get("duration", 4.0)),
                )
                for b in raw.get("beats", ())
            ),
        )
        story.validate()
        return story

    def validate(self) -> None:
        if not all((self.slug, self.topic, self.claim, self.data)):
            raise ValueError("story requires slug, topic, claim, and data")
        if len(self.beats) < 3 or self.beats[0].role != "hook" or self.beats[-1].role != "payoff":
            raise ValueError("story requires hook, body, and payoff")
        for beat in self.beats:
            if beat.role not in {"hook", "setup", "explanation", "consequence", "payoff"}:
                raise ValueError(f"unsupported role: {beat.role}")
            if not beat.narration or not 1.2 <= beat.duration <= 8:
                raise ValueError("invalid beat")


@dataclass(frozen=True)
class CaptionCue:
    start: float
    end: float
    text: str
    emphasis: tuple[str, ...] = ()


@dataclass(frozen=True)
class PerformanceMoment:
    phase: str
    action: str
    expression: str
    target: str
    consequence: str


@dataclass(frozen=True)
class CompositionSpec:
    hero_zone: str
    occupancy_target: float
    camera_move: str


@dataclass(frozen=True)
class MotionCue:
    at: float
    actor: str
    action: str
    target: str = ""


@dataclass(frozen=True)
class ScenePlan:
    scene_id: str
    role: str
    narration: str
    duration: float
    viz_kind: str
    visual_event: str
    focal_label: str
    composition: CompositionSpec
    performance: tuple[PerformanceMoment, ...]
    motion: tuple[MotionCue, ...]
    captions: tuple[CaptionCue, ...]
    callback_token: str
    engine_fields: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if self.composition.occupancy_target < .68:
            raise ValueError("useful occupancy below 68%")
        if tuple(p.phase for p in self.performance) != ("setup", "effort", "payoff"):
            raise ValueError("performance needs setup, effort, payoff")
        if not self.motion or self.motion[0].at > .4:
            raise ValueError("primary motion must start by .4s")
        for cue in self.captions:
            if not 1 <= len(cue.text.split()) <= 6 or cue.end <= cue.start:
                raise ValueError("invalid caption cue")


@dataclass(frozen=True)
class CreativePlan:
    slug: str
    hook_text: str
    hook_structure: str
    scenes: tuple[ScenePlan, ...]
    ending_callback: str
    visible_quality_score: float

    def validate(self) -> None:
        for scene in self.scenes:
            scene.validate()
        if not self.ending_callback or self.scenes[0].callback_token != self.scenes[-1].callback_token:
            raise ValueError("ending must visually callback to hook")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class HookCandidate:
    structure: str
    text: str
    visual_event: str
    focal_label: str
    score: float


@dataclass(frozen=True)
class VisualChoice:
    viz_kind: str
    visual_event: str
    focal_label: str
    composition: CompositionSpec


@dataclass(frozen=True)
class PlanScore:
    score: float
    dimensions: Mapping[str, float]
    failures: tuple[str, ...] = ()


def _fmt(value: float, unit: str) -> str:
    if unit.lower() in {"$", "usd", "dollars"}:
        return f"${value:,.0f}"
    if unit in {"%", "percent"}:
        return f"{value:g}%"
    return f"{value:g}{(' ' + unit) if unit else ''}"


def generate_hooks(story: StoryDraft) -> tuple[HookCandidate, ...]:
    points = sorted(story.data, key=lambda p: p.value, reverse=True)
    high, low = points[0], points[-1]
    hooks: list[HookCandidate] = []
    time_series = len(points) >= 2 and all(p.period is not None for p in points)
    if time_series:
        ordered = sorted(points, key=lambda p: float(p.period))
        start, end = ordered[0], ordered[-1]
        text = f"{start.label}: {_fmt(start.value, story.unit)}. {end.label}: {_fmt(end.value, story.unit)}."
        hooks.append(HookCandidate(
            "before_after_snap", text,
            "split_screen_values_slam_then_gap_opens", end.label, 98.0,
        ))
        delta = end.value - start.value
        hooks.append(HookCandidate(
            "physical_delta",
            f"It moved {'up' if delta >= 0 else 'down'} {_fmt(abs(delta), story.unit)}—watch the line do it.",
            "mascot_grips_line_and_gets_dragged_by_delta", end.label, 92.0,
        ))
    if len(points) >= 2 and low.value and abs(high.value / low.value) >= 1.5:
        ratio = abs(high.value / low.value)
        hooks.append(HookCandidate(
            "scale_collision", f"{high.label} is {ratio:.1f}× {low.label}.",
            "small_object_hits_giant_object_and_bounces", high.label, 94.0,
        ))
    if story.unit in {"%", "percent"} and 95 <= sum(p.value for p in points) <= 105:
        hooks.append(HookCandidate(
            "share_takeover", f"{high.label} takes {_fmt(high.value, story.unit)} of the whole thing.",
            "waffle_fills_until_mascot_is_squeezed_into_remaining_cells", high.label, 95.0,
        ))
    if len(points) >= 3:
        hooks.append(HookCandidate(
            "race_finish", f"{high.label} wins—but the gap is the real story.",
            "ranked_objects_sprint_to_finish_then_camera_reframes_gap", high.label, 88.0,
        ))
    hooks.append(HookCandidate(
        "claim_collision", story.claim.rstrip("."),
        "claim_words_break_apart_into_the_actual_data_objects", high.label, 74.0,
    ))
    return tuple(sorted(hooks, key=lambda h: h.score, reverse=True))


def _is_time_series(story: StoryDraft) -> bool:
    return len(story.data) >= 2 and all(p.period is not None for p in story.data)


def _kind(story: StoryDraft, role: str) -> str:
    if _is_time_series(story):
        return {"hook": "timeline", "setup": "trend", "explanation": "trend",
                "consequence": "stack", "payoff": "timeline"}[role]
    total = sum(p.value for p in story.data)
    if story.unit in {"%", "percent"} and 95 <= total <= 105:
        return "waffle_grid" if role in {"hook", "explanation"} else "share"
    if len(story.data) == 1:
        return "fill_vessel"
    if len(story.data) == 2:
        return "comparison"
    return "pictorial_race" if role in {"hook", "consequence"} else "rank"


EVENTS = {
    ("timeline", "hook"): "two_dates_snap_apart_then_the_value_gap_opens",
    ("trend", "setup"): "line_enters_flat_then_yanks_mascot_upward",
    ("trend", "explanation"): "line_draws_under_tension_and_labels_land_on_impacts",
    ("stack", "consequence"): "the_total_increase_builds_into_a_physical_stack_the_mascot_must_hold",
    ("timeline", "payoff"): "opening_split_screen_returns_then_the_full_trend_draws_between_both_sides",
    ("comparison", "hook"): "two_columns_drop_in_and_the_winner_shoves_the_loser_aside",
    ("comparison", "explanation"): "mascot_braces_between_values_as_the_gap_physically_expands",
    ("waffle_grid", "hook"): "cells_fill_fast_and_squeeze_the_mascot_into_the_remainder",
    ("share", "payoff"): "the_opening_grid_returns_with_the_takeaway_drawn_inside_it",
    ("fill_vessel", "hook"): "gauge_surges_from_zero_and_lifts_the_mascot_on_the_needle",
    ("pictorial_race", "hook"): "data_objects_sprint_into_rank_and_the_camera_stops_on_the_gap",
    ("rank", "explanation"): "mascot_shoves_each_bar_to_its_true_length",
}


def choose_visual(story: StoryDraft, beat: StoryBeat, index: int, recent_kinds=()) -> VisualChoice:
    kind = _kind(story, beat.role)
    recent = list(recent_kinds)[-2:]
    if recent.count(kind) >= 2:
        kind = {"trend": "timeline", "comparison": "stack", "rank": "pictorial_race",
                "waffle_grid": "share", "fill_vessel": "bubbles"}.get(kind, kind)
    focal = beat.focus_label or max(story.data, key=lambda p: p.value).label
    camera = "snap_push_in" if beat.role == "hook" else (
        "callback_pull_back" if beat.role == "payoff" else
        {"trend": "follow_tip", "stack": "pressure_pull_back", "comparison": "gap_dolly",
         "rank": "row_track", "pictorial_race": "side_track"}.get(kind, "slow_push")
    )
    return VisualChoice(
        kind,
        EVENTS.get((kind, beat.role), f"{kind}_{beat.role}_physical_demonstration"),
        focal,
        CompositionSpec(
            hero_zone={"timeline": "full_width_center", "trend": "center_lower_to_upper_right",
                       "stack": "center_vertical", "comparison": "left_right_split",
                       "rank": "full_width_rows", "pictorial_race": "full_width_rows"}.get(kind, "center"),
            occupancy_target=.78 if beat.role in {"hook", "payoff"} else .72,
            camera_move=camera,
        ),
    )


ACTION_OPTIONS = {
    "trend": ("drag_line", "pull_down_win", "ride"),
    "timeline": ("drag_line", "ride", "point_at"),
    "comparison": ("shoved_bar", "push", "stagger_under"),
    "stack": ("hoist_stack", "stagger_under", "carry"),
    "rank": ("shoved_bar", "push", "point_at"),
    "pictorial_race": ("ride", "push", "point_at"),
    "waffle_grid": ("push", "stagger_under", "sit_on"),
    "share": ("ride", "pull_down_win", "point_at"),
    "fill_vessel": ("ride", "stagger_under", "point_at"),
    "bubbles": ("juggle", "ride", "point_at"),
}


def performance_arc(viz_kind: str, target: str, role: str, recent_actions=()) -> tuple[PerformanceMoment, ...]:
    recent = list(recent_actions)[-3:]
    options = ACTION_OPTIONS.get(viz_kind, ("push", "carry", "point_at"))
    counts = Counter(recent)
    effort = min(options, key=lambda action: (counts[action], options.index(action)))
    return (
        PerformanceMoment("setup", "point_at" if role in {"hook", "explanation"} else "lean_on",
                          "shock" if role == "hook" else "think", target,
                          "the target starts still and establishes scale"),
        PerformanceMoment("effort", effort, "strain", target,
                          "the data object physically drives the mascot's body"),
        PerformanceMoment("payoff", "cheer" if role != "consequence" else "shock",
                          "laugh" if role == "payoff" else "cheer", target,
                          "the final value visibly changes the scene"),
    )


def _emphasis(words: list[str]) -> tuple[str, ...]:
    scored = []
    for word in words:
        clean = re.sub(r"[^\w$%×+-]", "", word)
        score = (4 if any(ch.isdigit() for ch in clean) else 0) + (
            3 if any(ch in clean for ch in "$%×+-") else 0)
        if score:
            scored.append((score, clean))
    return tuple(word for _, word in sorted(scored, reverse=True)[:2])


def chunk_caption(text: str, duration: float) -> tuple[CaptionCue, ...]:
    words = re.findall(r"\$?[\w,.%×+-]+(?:'[\w]+)?|[!?]", text)
    if not words:
        raise ValueError("caption text cannot be empty")
    chunks, current = [], []
    for word in words:
        current.append(word)
        if len(current) >= 5 or (len(current) >= 3 and (word in {"!", "?"} or word.endswith((",", ".")))):
            chunks.append(current)
            current = []
    if current:
        if chunks and len(current) <= 2 and len(chunks[-1]) + len(current) <= 6:
            chunks[-1].extend(current)
        else:
            chunks.append(current)
    total = sum(len(c) for c in chunks)
    start, cues = 0.0, []
    for index, chunk in enumerate(chunks):
        end = duration if index == len(chunks) - 1 else start + duration * len(chunk) / total
        end = max(end, start + .35)
        label = " ".join(chunk).replace(" ,", ",").replace(" .", ".")
        cues.append(CaptionCue(round(start, 2), round(min(duration, end), 2), label, _emphasis(chunk)))
        start = min(duration, end)
    last = cues[-1]
    cues[-1] = CaptionCue(last.start, round(duration, 2), last.text, last.emphasis)
    return tuple(cues)


def build_motion(duration: float, camera: str, event: str, target: str, role: str) -> tuple[MotionCue, ...]:
    setup = min(.18 * duration, .38 if role == "hook" else .72)
    payoff = .74 * duration
    return (
        MotionCue(0.0, "camera", camera, target),
        MotionCue(0.0, "data_object", "enter_with_velocity", target),
        MotionCue(round(setup, 2), "mascot", "make_contact", target),
        MotionCue(round(setup, 2), "data_object", event, target),
        MotionCue(round(duration * .48, 2), "camera", "follow_causal_action", target),
        MotionCue(round(payoff, 2), "data_object", "land_final_value", target),
        MotionCue(round(payoff, 2), "mascot", "payoff_reaction", target),
    )


def _ending(story: StoryDraft, hook: HookCandidate) -> tuple[str, str, str]:
    if hook.structure == "before_after_snap":
        ordered = sorted(story.data, key=lambda p: float(p.period))
        start, end = ordered[0], ordered[-1]
        return (
            f"{start.label}_vs_{end.label}",
            f"The path between {start.label} and {end.label} is the story.",
            "opening_split_screen_returns_then_the_full_trend_draws_between_both_sides",
        )
    return (
        f"{hook.focal_label}_opening_object",
        story.claim.rstrip("."),
        "opening_object_returns_transformed_by_the_complete_data_story",
    )


def _engine_fields(scene: ScenePlan) -> dict:
    effort = scene.performance[1]
    return {
        "kind": scene.viz_kind,
        "perf_override": effort.action,
        "highlight_label": scene.focal_label,
        "host_baked": effort.action in {"drag_line", "shoved_bar", "hoist_stack", "pull_down_win"},
        "scene_plan": {
            "visual_event": scene.visual_event,
            "camera_move": scene.composition.camera_move,
            "occupancy_target": scene.composition.occupancy_target,
            "performance_arc": [asdict(p) for p in scene.performance],
            "motion_events": [asdict(m) for m in scene.motion],
            "caption_cues": [asdict(c) for c in scene.captions],
        },
    }


def compile_creative_plan(story: StoryDraft) -> CreativePlan:
    hook = generate_hooks(story)[0]
    callback, takeaway, ending_event = _ending(story, hook)
    scenes, recent_kinds, recent_actions = [], [], []
    for index, beat in enumerate(story.beats):
        visual = choose_visual(story, beat, index, recent_kinds)
        narration = beat.narration
        event = visual.visual_event
        focal = visual.focal_label
        if beat.role == "hook":
            narration, event, focal = hook.text, hook.visual_event, hook.focal_label
        elif beat.role == "payoff":
            narration, event = takeaway, ending_event
        performance = performance_arc(visual.viz_kind, focal, beat.role, recent_actions)
        scene = ScenePlan(
            scene_id=f"{story.slug}_seg{index:02d}",
            role=beat.role,
            narration=narration,
            duration=beat.duration,
            viz_kind=visual.viz_kind,
            visual_event=event,
            focal_label=focal,
            composition=visual.composition,
            performance=performance,
            motion=build_motion(beat.duration, visual.composition.camera_move, event, focal, beat.role),
            captions=chunk_caption(narration, beat.duration),
            callback_token=callback if beat.role in {"hook", "payoff"} else "",
        )
        scene = replace(scene, engine_fields=_engine_fields(scene))
        scene.validate()
        scenes.append(scene)
        recent_kinds.append(scene.viz_kind)
        recent_actions.append(scene.performance[1].action)
    plan = CreativePlan(story.slug, hook.text, hook.structure, tuple(scenes), callback, 0.0)
    plan = replace(plan, visible_quality_score=score_plan(plan).score)
    plan.validate()
    return plan


def score_plan(plan: CreativePlan) -> PlanScore:
    scenes = plan.scenes
    hook = 100.0 if scenes[0].motion[0].at <= .4 and any(ch.isdigit() for ch in plan.hook_text) else 65.0
    events = 100 * len({s.visual_event for s in scenes}) / len(scenes)
    kinds = 100 * len({s.viz_kind for s in scenes}) / len(scenes)
    actions = 100 * len({s.performance[1].action for s in scenes}) / len(scenes)
    mascot = mean([actions, 100.0 if all("data object" in s.performance[1].consequence for s in scenes) else 0.0])
    captions = 100.0 if all(
        all(1 <= len(c.text.split()) <= 6 for c in s.captions)
        and all(a.end <= b.start for a, b in zip(s.captions, s.captions[1:]))
        for s in scenes
    ) else 0.0
    composition = 100 * mean(min(1.0, s.composition.occupancy_target / .75) for s in scenes)
    payoff = 100.0 if scenes[0].callback_token == scenes[-1].callback_token else 0.0
    dimensions = {
        "hook": hook, "visual_events": mean([events, kinds]), "mascot": mascot,
        "captions": captions, "composition": composition, "payoff": payoff,
    }
    weights = {"hook": .22, "visual_events": .22, "mascot": .20,
               "captions": .12, "composition": .12, "payoff": .12}
    return PlanScore(round(sum(dimensions[k] * weights[k] for k in weights), 1),
                     {k: round(v, 1) for k, v in dimensions.items()})


def baseline_score(scene_count: int) -> PlanScore:
    if scene_count <= 0:
        raise ValueError("scene_count must be positive")
    dimensions = {"hook": 65.0, "visual_events": 35.0, "mascot": 42.0,
                  "captions": 45.0, "composition": 72.0, "payoff": 25.0}
    weights = {"hook": .22, "visual_events": .22, "mascot": .20,
               "captions": .12, "composition": .12, "payoff": .12}
    return PlanScore(round(sum(dimensions[k] * weights[k] for k in weights), 1),
                     dimensions, ("repetitive visual grammar", "weak callback payoff"))
