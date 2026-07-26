"""Hash-bound visual-judge verdict and consensus prototype."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class JudgeDecision(str, Enum):
    PASS = "pass"
    SECOND_REVIEW = "second_review"
    REJECT = "reject"
    QUARANTINE = "quarantine"


@dataclass(frozen=True)
class JudgeVerdict:
    judge_id: str
    judge_version: str
    manifest_sha256: str
    overall_score: float
    personality: float
    hook: float
    visual_relevance: float
    payoff: float
    pass_boolean: bool
    reject_labels: tuple[str, ...] = ()
    required_repairs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("overall_score", "personality", "hook", "visual_relevance", "payoff"):
            value = getattr(self, name)
            if not 0 <= value <= 10:
                raise ValueError(f"{name} must be between 0 and 10")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "JudgeVerdict":
        return cls(
            judge_id=str(raw["judge_id"]),
            judge_version=str(raw["judge_version"]),
            manifest_sha256=str(raw["manifest_sha256"]),
            overall_score=float(raw["overall_score"]),
            personality=float(raw["personality"]),
            hook=float(raw["hook"]),
            visual_relevance=float(raw["visual_relevance"]),
            payoff=float(raw["payoff"]),
            pass_boolean=bool(raw["pass"]),
            reject_labels=tuple(str(v) for v in raw.get("reject_labels", ())),
            required_repairs=tuple(str(v) for v in raw.get("required_repairs", ())),
        )


@dataclass(frozen=True)
class JudgePolicy:
    pass_score: float = 7.5
    second_review_score: float = 6.5
    minimum_personality: float = 4.0
    minimum_visual_relevance: float = 7.0
    maximum_disagreement: float = 1.25


@dataclass(frozen=True)
class ConsensusResult:
    decision: JudgeDecision
    score: float
    reasons: tuple[str, ...]
    repairs: tuple[str, ...]
    verdict_count: int


def validate_verdict(verdict: JudgeVerdict, *, expected_manifest_sha256: str,
                     policy: JudgePolicy | None = None) -> tuple[bool, tuple[str, ...]]:
    policy = policy or JudgePolicy()
    reasons: list[str] = []
    if verdict.manifest_sha256 != expected_manifest_sha256:
        reasons.append("verdict is bound to a different manifest")
    if verdict.reject_labels and verdict.pass_boolean:
        reasons.append("pass=true contradicts reject labels")
    expected_pass = (
        verdict.overall_score >= policy.pass_score
        and verdict.personality >= policy.minimum_personality
        and verdict.visual_relevance >= policy.minimum_visual_relevance
        and not verdict.reject_labels
    )
    if verdict.pass_boolean != expected_pass:
        reasons.append("pass boolean contradicts scored policy")
    return not reasons, tuple(reasons)


def decide_consensus(verdicts: Iterable[JudgeVerdict], *, expected_manifest_sha256: str,
                     policy: JudgePolicy | None = None) -> ConsensusResult:
    policy = policy or JudgePolicy()
    items = list(verdicts)
    if not items:
        return ConsensusResult(JudgeDecision.QUARANTINE, 0.0,
                               ("no visual verdicts supplied",), (), 0)

    reasons: list[str] = []
    repairs: set[str] = set()
    valid: list[JudgeVerdict] = []
    for verdict in items:
        ok, verdict_reasons = validate_verdict(
            verdict, expected_manifest_sha256=expected_manifest_sha256, policy=policy
        )
        if not ok:
            reasons.extend(f"{verdict.judge_id}: {reason}" for reason in verdict_reasons)
        else:
            valid.append(verdict)
            repairs.update(verdict.required_repairs)

    if len(valid) != len(items):
        return ConsensusResult(JudgeDecision.QUARANTINE, 0.0, tuple(reasons),
                               tuple(sorted(repairs)), len(items))

    scores = [item.overall_score for item in valid]
    average = sum(scores) / len(scores)
    spread = max(scores) - min(scores)
    labels = sorted({label for item in valid for label in item.reject_labels})

    if spread > policy.maximum_disagreement:
        reasons.append(f"judge disagreement {spread:.2f} exceeds limit")
        decision = JudgeDecision.QUARANTINE
    elif labels:
        reasons.append("reject labels: " + ", ".join(labels))
        decision = JudgeDecision.REJECT
    elif average >= policy.pass_score and all(item.pass_boolean for item in valid):
        decision = JudgeDecision.PASS
    elif average >= policy.second_review_score and len(valid) == 1:
        reasons.append("borderline score requires a second independent review")
        decision = JudgeDecision.SECOND_REVIEW
    elif average >= policy.second_review_score:
        reasons.append("borderline consensus did not reach pass threshold")
        decision = JudgeDecision.REJECT
    else:
        reasons.append("average score below review floor")
        decision = JudgeDecision.REJECT

    return ConsensusResult(decision, round(average, 3), tuple(reasons),
                           tuple(sorted(repairs)), len(items))
