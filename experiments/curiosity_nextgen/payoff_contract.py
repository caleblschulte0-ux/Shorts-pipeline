from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StoryQuestion:
    question_id: str
    text: str
    opened_at_seconds: float
    importance: float
    promised_visual: str = ""
    promised_consequence: str = ""

    def __post_init__(self) -> None:
        if not self.question_id.strip() or not self.text.strip():
            raise ValueError("question_id and text are required")
        if self.opened_at_seconds < 0:
            raise ValueError("opened_at_seconds cannot be negative")
        if not 0 <= self.importance <= 10:
            raise ValueError("importance must be between 0 and 10")


@dataclass(frozen=True)
class StoryAnswer:
    question_id: str
    answered_at_seconds: float
    answer_text: str
    visual_evidence: str = ""
    consequence_shown: str = ""
    callback_shown: bool = False
    specificity: float = 5.0

    def __post_init__(self) -> None:
        if not self.question_id.strip() or not self.answer_text.strip():
            raise ValueError("question_id and answer_text are required")
        if self.answered_at_seconds < 0:
            raise ValueError("answered_at_seconds cannot be negative")
        if not 0 <= self.specificity <= 10:
            raise ValueError("specificity must be between 0 and 10")


@dataclass(frozen=True)
class PayoffPolicy:
    minimum_specificity: float = 7.0
    maximum_open_duration_seconds: float = 180.0
    require_visual_evidence_for_major: bool = True
    require_consequence_for_major: bool = True
    require_callback_for_major: bool = True
    major_importance_threshold: float = 7.5


@dataclass(frozen=True)
class PayoffDefect:
    code: str
    question_id: str
    explanation: str
    suggested_change: str


@dataclass(frozen=True)
class PayoffReport:
    score: float
    answered_rate: float
    weighted_answered_rate: float
    defects: tuple[PayoffDefect, ...]
    strongest_payoffs: tuple[str, ...]


def evaluate_payoffs(
    questions: Iterable[StoryQuestion],
    answers: Iterable[StoryAnswer],
    *,
    policy: PayoffPolicy | None = None,
) -> PayoffReport:
    policy = policy or PayoffPolicy()
    question_list = tuple(questions)
    answer_list = tuple(answers)
    if len({item.question_id for item in question_list}) != len(question_list):
        raise ValueError("duplicate question_id")
    answer_map: dict[str, StoryAnswer] = {}
    for answer in answer_list:
        if answer.question_id in answer_map:
            raise ValueError("duplicate answer for question_id")
        answer_map[answer.question_id] = answer

    known_ids = {question.question_id for question in question_list}
    unknown = sorted(set(answer_map) - known_ids)
    if unknown:
        raise ValueError("answers reference unknown questions: " + ", ".join(unknown))

    defects: list[PayoffDefect] = []
    answered_count = 0
    weighted_answered = 0.0
    total_weight = sum(max(0.1, question.importance) for question in question_list) or 1.0
    payoff_strengths: list[tuple[float, str]] = []

    for question in question_list:
        answer = answer_map.get(question.question_id)
        if answer is None:
            defects.append(PayoffDefect(
                "unanswered_question",
                question.question_id,
                "the video opens or sustains a question that never receives a clear answer",
                "add a direct answer, visible proof, and consequence before the ending",
            ))
            continue

        answered_count += 1
        weighted_answered += max(0.1, question.importance)
        open_duration = answer.answered_at_seconds - question.opened_at_seconds
        major = question.importance >= policy.major_importance_threshold
        strength = answer.specificity

        if open_duration < 0:
            defects.append(PayoffDefect(
                "answer_precedes_question",
                question.question_id,
                "the answer timing precedes the question opening",
                "correct the beat map so setup and payoff order are explicit",
            ))
            strength -= 3.0
        elif open_duration > policy.maximum_open_duration_seconds:
            defects.append(PayoffDefect(
                "payoff_arrives_too_late",
                question.question_id,
                f"the question remains unresolved for {open_duration:.1f} seconds",
                "insert progress markers, partial answers, escalating consequences, or an earlier payoff",
            ))
            strength -= 1.0

        if answer.specificity < policy.minimum_specificity:
            defects.append(PayoffDefect(
                "vague_answer",
                question.question_id,
                "the answer does not feel more concrete than the setup",
                "name the exact mechanism, result, comparison, or consequence",
            ))
            strength -= 1.25

        if major and policy.require_visual_evidence_for_major and not answer.visual_evidence.strip():
            defects.append(PayoffDefect(
                "major_payoff_without_visual_proof",
                question.question_id,
                "a major question is answered only in narration or text",
                "show the mechanism, transformed object, comparison, result, or before-and-after evidence",
            ))
            strength -= 1.5
        if major and policy.require_consequence_for_major and not answer.consequence_shown.strip():
            defects.append(PayoffDefect(
                "major_payoff_without_consequence",
                question.question_id,
                "the viewer gets an answer but not why it matters",
                "show what changes for a person, object, system, risk, cost, or decision",
            ))
            strength -= 1.25
        if major and policy.require_callback_for_major and not answer.callback_shown:
            defects.append(PayoffDefect(
                "missing_setup_callback",
                question.question_id,
                "the ending does not visibly return to the object, image, or action promised by the hook",
                "repeat or transform the opening visual so the ending feels earned",
            ))
            strength -= 1.0

        if question.promised_visual and answer.visual_evidence and question.promised_visual.lower() not in answer.visual_evidence.lower():
            defects.append(PayoffDefect(
                "visual_promise_mismatch",
                question.question_id,
                "the payoff uses different evidence from the visual promise in the setup",
                "resolve the exact visual object or comparison introduced by the hook",
            ))
            strength -= 0.75
        if question.promised_consequence and answer.consequence_shown and question.promised_consequence.lower() not in answer.consequence_shown.lower():
            defects.append(PayoffDefect(
                "consequence_promise_mismatch",
                question.question_id,
                "the ending does not resolve the consequence implied by the setup",
                "show the promised cost, benefit, danger, surprise, or decision outcome",
            ))
            strength -= 0.75

        payoff_strengths.append((max(0.0, strength), question.question_id))

    answered_rate = 1.0 if not question_list else answered_count / len(question_list)
    weighted_rate = weighted_answered / total_weight
    specificity_score = (
        sum(answer.specificity for answer in answer_list) / len(answer_list)
        if answer_list else 0.0
    )
    score = weighted_rate * 6.0 + min(4.0, specificity_score * 0.4) - min(4.0, len(defects) * 0.45)

    return PayoffReport(
        score=round(max(0.0, min(10.0, score)), 3),
        answered_rate=round(answered_rate, 3),
        weighted_answered_rate=round(weighted_rate, 3),
        defects=tuple(defects),
        strongest_payoffs=tuple(question_id for _, question_id in sorted(payoff_strengths, key=lambda item: (-item[0], item[1]))[:5]),
    )
