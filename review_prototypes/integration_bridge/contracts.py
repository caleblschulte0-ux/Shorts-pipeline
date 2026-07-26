from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

SUPPORTED_KINDS = frozenset({
    "trend", "timeline", "pictorial_race", "rank", "comparison",
    "waffle_grid", "share", "fill_vessel", "bubbles", "stack",
    "pictograph", "geo_us", "geo_world", "geo_city",
})
SUPPORTED_ACTIONS = frozenset({
    "drag_line", "pull_down_win", "shoved_bar", "hoist_stack",
    "ride_line_arc", "push_bar_arc", "lift_arc", "climb_arc",
})
ROLES = frozenset({"hook", "setup", "explanation", "consequence", "payoff"})


@dataclass(frozen=True)
class DataValue:
    label: str
    value: float
    period: float | None = None

    def validate(self) -> None:
        if not self.label:
            raise ValueError("data label is required")


@dataclass(frozen=True)
class ProductionScene:
    index: int
    role: str
    sentence: str
    topic: str
    unit: str
    current_kind: str
    values: tuple[DataValue, ...]
    punches: tuple[Mapping[str, Any], ...] = ()
    source_footer: str = ""
    host_baked: bool = False
    highlight_label: str = ""

    def validate(self) -> None:
        if self.index < 0:
            raise ValueError("scene index must be non-negative")
        if self.role not in ROLES:
            raise ValueError(f"unsupported role: {self.role}")
        if not self.sentence or not self.topic:
            raise ValueError("scene sentence and topic are required")
        if not self.values:
            raise ValueError("scene needs at least one data value")
        for value in self.values:
            value.validate()


@dataclass(frozen=True)
class ProductionStory:
    slug: str
    title: str
    hook: str
    closing: str
    scenes: tuple[ProductionScene, ...]
    question: str = ""
    sources: tuple[str, ...] = ()

    def validate(self) -> None:
        if not all((self.slug, self.title, self.hook, self.closing)):
            raise ValueError("story identity and bookends are required")
        if not self.scenes:
            raise ValueError("story requires scenes")
        for scene in self.scenes:
            scene.validate()


@dataclass(frozen=True)
class SceneOverride:
    segment_index: int
    kind: str
    performance: str
    role: str
    target: str
    goal: str
    callback_token: str
    scene_timeline: Mapping[str, Any]
    audio_cues: tuple[Mapping[str, Any], ...]
    transition_in: Mapping[str, Any] | None = None
    rationale: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.segment_index < 0:
            raise ValueError("segment index must be non-negative")
        if self.kind not in SUPPORTED_KINDS:
            raise ValueError(f"kind not supported by production: {self.kind}")
        if self.performance not in SUPPORTED_ACTIONS:
            raise ValueError(f"performance not supported by production: {self.performance}")
        if self.role not in ROLES:
            raise ValueError(f"unsupported role: {self.role}")
        if not self.target or not self.goal:
            raise ValueError("target and goal are required")
        if not self.scene_timeline.get("events"):
            raise ValueError("scene timeline requires events")
        times = [float(event.get("t", -1)) for event in self.scene_timeline["events"]]
        if times != sorted(times) or times[0] < 0:
            raise ValueError("timeline events must be sorted and non-negative")
        for cue in self.audio_cues:
            if float(cue.get("at", -1)) < 0:
                raise ValueError("audio cue time must be non-negative")


@dataclass(frozen=True)
class QualityBridgeBundle:
    slug: str
    version: str
    story_fingerprint: str
    overrides: tuple[SceneOverride, ...]
    callback_token: str
    supported_by_contracts: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.slug or not self.version or not self.story_fingerprint:
            raise ValueError("bundle identity is incomplete")
        if not self.overrides:
            raise ValueError("bundle has no scene overrides")
        expected = list(range(len(self.overrides)))
        actual = [item.segment_index for item in self.overrides]
        if actual != expected:
            raise ValueError("overrides must cover segments in order")
        for override in self.overrides:
            override.validate()
        if not self.callback_token:
            raise ValueError("callback token is required")
        if self.overrides[0].callback_token != self.callback_token:
            raise ValueError("opening callback token mismatch")
        if self.overrides[-1].callback_token != self.callback_token:
            raise ValueError("payoff callback token mismatch")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContractRequirement:
    path: str
    sha: str
    required_symbols: tuple[str, ...]
    required_literals: tuple[str, ...] = ()
    purpose: str = ""


@dataclass(frozen=True)
class ContractResult:
    path: str
    sha_matches: bool
    symbols_found: tuple[str, ...]
    symbols_missing: tuple[str, ...]
    literals_missing: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.sha_matches and not self.symbols_missing and not self.literals_missing


@dataclass(frozen=True)
class ContractReport:
    results: tuple[ContractResult, ...]

    @property
    def passed(self) -> bool:
        return bool(self.results) and all(result.passed for result in self.results)

    @property
    def percent(self) -> float:
        if not self.results:
            return 0.0
        return round(100 * sum(result.passed for result in self.results) / len(self.results), 1)


@dataclass(frozen=True)
class PatchTarget:
    phase: int
    path: str
    symbol: str
    change: str
    guard: str
    acceptance: tuple[str, ...]
    rollback: str
    risk: str = "medium"

    def validate(self) -> None:
        if self.phase < 0 or not all((self.path, self.symbol, self.change, self.guard, self.rollback)):
            raise ValueError("patch target is incomplete")
        if not self.acceptance:
            raise ValueError("patch target requires acceptance checks")
        if self.risk not in {"low", "medium", "high"}:
            raise ValueError("invalid risk")


@dataclass(frozen=True)
class MigrationGate:
    name: str
    passed: bool
    evidence: str
    blocking: bool = True


@dataclass(frozen=True)
class MigrationPhase:
    index: int
    name: str
    purpose: str
    targets: tuple[PatchTarget, ...]
    gates: tuple[MigrationGate, ...]

    @property
    def ready(self) -> bool:
        return all((not gate.blocking) or gate.passed for gate in self.gates)


@dataclass(frozen=True)
class MigrationPlan:
    phases: tuple[MigrationPhase, ...]

    def validate(self) -> None:
        if [phase.index for phase in self.phases] != list(range(len(self.phases))):
            raise ValueError("migration phases must be contiguous")
        for phase in self.phases:
            for target in phase.targets:
                target.validate()

    @property
    def next_phase(self) -> MigrationPhase | None:
        return next((phase for phase in self.phases if not phase.ready), None)

    @property
    def readiness_percent(self) -> float:
        gates = [gate for phase in self.phases for gate in phase.gates if gate.blocking]
        if not gates:
            return 0.0
        return round(100 * sum(gate.passed for gate in gates) / len(gates), 1)


@dataclass(frozen=True)
class BridgeScorecard:
    dimensions: Mapping[str, float]
    review_scope_percent: float
    overall_percent: float
    production_pipeline_modified: bool
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.production_pipeline_modified:
            raise ValueError("shadow bridge must not modify production")
        for name, value in self.dimensions.items():
            if not 0 <= float(value) <= 100:
                raise ValueError(f"invalid percentage for {name}")
        if not 0 <= self.review_scope_percent <= 100:
            raise ValueError("invalid review scope percent")
        if not 0 <= self.overall_percent <= 100:
            raise ValueError("invalid overall percent")
