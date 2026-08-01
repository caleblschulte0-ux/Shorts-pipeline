from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable


class StageName(str, Enum):
    INTAKE = "intake"
    RESEARCH = "research"
    CLAIMS = "claims"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    MEDIA = "media"
    DRAFT_RENDER = "draft_render"
    TECHNICAL_REVIEW = "technical_review"
    EDITORIAL_REVIEW = "editorial_review"
    FACT_REVIEW = "fact_review"
    GATE_AGGREGATION = "gate_aggregation"
    REPAIR = "repair"
    FINAL_RENDER = "final_render"
    PACKAGE = "package"
    APPROVAL = "approval"
    PUBLISH = "publish"


@dataclass(frozen=True)
class StageSpec:
    name: StageName
    prerequisites: tuple[StageName, ...] = ()
    required_artifacts: tuple[str, ...] = ()
    maximum_attempts: int = 2
    optional: bool = False

    def __post_init__(self) -> None:
        if self.name in self.prerequisites:
            raise ValueError("stage cannot depend on itself")
        if len(self.prerequisites) != len(set(self.prerequisites)):
            raise ValueError("duplicate stage prerequisite")
        if len(self.required_artifacts) != len(set(self.required_artifacts)):
            raise ValueError("duplicate required artifact")
        if self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be positive")


@dataclass(frozen=True)
class ProductionGraph:
    stages: tuple[StageSpec, ...]

    def __post_init__(self) -> None:
        names = [stage.name for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("duplicate stage definition")
        by_name = {stage.name: stage for stage in self.stages}
        for stage in self.stages:
            unknown = set(stage.prerequisites) - set(by_name)
            if unknown:
                raise ValueError(f"unknown prerequisites for {stage.name.value}: {sorted(item.value for item in unknown)}")
        self.topological_order()
        if StageName.INTAKE not in by_name or StageName.PUBLISH not in by_name:
            raise ValueError("graph requires intake and publish stages")
        if any(StageName.PUBLISH in stage.prerequisites for stage in self.stages):
            raise ValueError("publish must be terminal")
        required_gates = {
            StageName.TECHNICAL_REVIEW,
            StageName.EDITORIAL_REVIEW,
            StageName.GATE_AGGREGATION,
            StageName.PACKAGE,
            StageName.APPROVAL,
        }
        if not required_gates.issubset(by_name):
            raise ValueError("graph is missing mandatory release gates")

    def topological_order(self) -> tuple[StageName, ...]:
        by_name = {stage.name: stage for stage in self.stages}
        incoming = {name: set(spec.prerequisites) for name, spec in by_name.items()}
        ordered: list[StageName] = []
        ready = sorted((name for name, deps in incoming.items() if not deps), key=lambda item: item.value)
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for name, deps in incoming.items():
                if current in deps:
                    deps.remove(current)
                    if not deps and name not in ordered and name not in ready:
                        ready.append(name)
                        ready.sort(key=lambda item: item.value)
        if len(ordered) != len(self.stages):
            raise ValueError("production stage graph contains a cycle")
        return tuple(ordered)

    def ready_stages(
        self,
        completed: Iterable[StageName],
        in_progress: Iterable[StageName] = (),
        quarantined: bool = False,
    ) -> tuple[StageName, ...]:
        if quarantined:
            return ()
        completed_set = set(completed)
        in_progress_set = set(in_progress)
        ready = [
            stage.name
            for stage in self.stages
            if stage.name not in completed_set
            and stage.name not in in_progress_set
            and set(stage.prerequisites).issubset(completed_set)
        ]
        order = {name: index for index, name in enumerate(self.topological_order())}
        return tuple(sorted(ready, key=lambda name: order[name]))

    def descendants(self, stage: StageName) -> tuple[StageName, ...]:
        descendants: set[StageName] = set()
        changed = True
        while changed:
            changed = False
            for spec in self.stages:
                if spec.name in descendants:
                    continue
                if stage in spec.prerequisites or any(dep in descendants for dep in spec.prerequisites):
                    descendants.add(spec.name)
                    changed = True
        order = {name: index for index, name in enumerate(self.topological_order())}
        return tuple(sorted(descendants, key=lambda name: order[name]))

    @property
    def digest(self) -> str:
        payload = [
            {
                "name": stage.name.value,
                "prerequisites": [item.value for item in stage.prerequisites],
                "required_artifacts": list(stage.required_artifacts),
                "maximum_attempts": stage.maximum_attempts,
                "optional": stage.optional,
            }
            for stage in sorted(self.stages, key=lambda item: item.name.value)
        ]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(canonical).hexdigest()


def build_default_graph(*, require_fact_review: bool = True) -> ProductionGraph:
    review_dependencies = [StageName.TECHNICAL_REVIEW, StageName.EDITORIAL_REVIEW]
    stages = [
        StageSpec(StageName.INTAKE, required_artifacts=("story_brief",)),
        StageSpec(StageName.RESEARCH, (StageName.INTAKE,), ("source_set",), 3),
        StageSpec(StageName.CLAIMS, (StageName.RESEARCH,), ("claim_registry",), 3),
        StageSpec(StageName.SCRIPT, (StageName.CLAIMS,), ("script",), 3),
        StageSpec(StageName.STORYBOARD, (StageName.SCRIPT,), ("beat_plan", "visual_intents"), 3),
        StageSpec(StageName.MEDIA, (StageName.STORYBOARD,), ("media_manifest",), 3),
        StageSpec(StageName.DRAFT_RENDER, (StageName.MEDIA,), ("draft_video", "draft_manifest"), 2),
        StageSpec(StageName.TECHNICAL_REVIEW, (StageName.DRAFT_RENDER,), ("technical_verdict",), 2),
        StageSpec(StageName.EDITORIAL_REVIEW, (StageName.DRAFT_RENDER,), ("editorial_verdict",), 2),
    ]
    if require_fact_review:
        stages.append(StageSpec(StageName.FACT_REVIEW, (StageName.CLAIMS, StageName.DRAFT_RENDER), ("factual_verdict",), 2))
        review_dependencies.append(StageName.FACT_REVIEW)
    stages.extend(
        [
            StageSpec(StageName.GATE_AGGREGATION, tuple(review_dependencies), ("gate_report",), 1),
            StageSpec(StageName.REPAIR, (StageName.GATE_AGGREGATION,), ("repair_report",), 3),
            StageSpec(StageName.FINAL_RENDER, (StageName.REPAIR,), ("final_video", "artifact_manifest"), 2),
            StageSpec(StageName.PACKAGE, (StageName.FINAL_RENDER,), ("release_package",), 2),
            StageSpec(StageName.APPROVAL, (StageName.PACKAGE,), ("approval_token",), 1),
            StageSpec(StageName.PUBLISH, (StageName.APPROVAL,), ("publish_receipt",), 1),
        ]
    )
    return ProductionGraph(tuple(stages))
