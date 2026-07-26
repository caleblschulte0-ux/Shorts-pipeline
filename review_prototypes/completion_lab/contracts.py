from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import RenderBundle, StorySpec, Verdict


class RendererContract(Protocol):
    version: str

    def render(self, story: StorySpec, destination: Path, *, attempt_id: str) -> RenderBundle: ...


class JudgeContract(Protocol):
    version: str

    def judge(self, story: StorySpec, render: RenderBundle) -> Verdict: ...


@dataclass(frozen=True)
class ContractCheck:
    name: str
    passed: bool
    detail: str


def validate_renderer_contract(renderer: RendererContract, story: StorySpec, destination: Path) -> tuple[ContractCheck, ...]:
    checks: list[ContractCheck] = []
    try:
        bundle = renderer.render(story, destination, attempt_id="contract")
        bundle.validate()
        checks.append(ContractCheck("renderer_returns_complete_bundle", True, bundle.attempt_id))
    except Exception as exc:  # pragma: no cover - exercised through explicit failing renderer
        checks.append(ContractCheck("renderer_returns_complete_bundle", False, str(exc)))
    checks.append(ContractCheck("renderer_exposes_version", bool(getattr(renderer, "version", "")), str(getattr(renderer, "version", ""))))
    return tuple(checks)


def validate_judge_contract(judge: JudgeContract, story: StorySpec, render: RenderBundle) -> tuple[ContractCheck, ...]:
    checks: list[ContractCheck] = []
    try:
        verdict = judge.judge(story, render)
        verdict.validate()
        checks.append(ContractCheck("judge_returns_valid_verdict", True, f"score={verdict.score}"))
    except Exception as exc:  # pragma: no cover - exercised through explicit failing judge
        checks.append(ContractCheck("judge_returns_valid_verdict", False, str(exc)))
    checks.append(ContractCheck("judge_exposes_version", bool(getattr(judge, "version", "")), str(getattr(judge, "version", ""))))
    return tuple(checks)
