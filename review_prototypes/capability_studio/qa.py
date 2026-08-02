from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .contracts import Verdict


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    verdict: Verdict
    detail: str


@dataclass(frozen=True)
class GateReport:
    format_name: str
    verdict: Verdict
    checks: tuple[CheckResult, ...]


class FinalVideoGate:
    REQUIRED_BY_FORMAT = {
        "text_card": ("valid_mp4", "portrait", "text_in_bounds", "phone_readable", "reading_time", "clip_relevance"),
        "graph_race": ("valid_mp4", "portrait", "labels_visible", "no_overlap", "source_specific", "scale_honest", "final_values_visible"),
        "narrated": ("valid_mp4", "portrait", "audio_present", "captions_synced", "speech_intelligible", "visual_match", "hook_payoff_delivered"),
        "clip": ("valid_mp4", "portrait", "context_present", "no_dead_opening", "payoff_present", "captions_safe", "no_frozen_frames"),
    }

    def evaluate(self, format_name: str, observations: Mapping[str, bool | None | str]) -> GateReport:
        required = self.REQUIRED_BY_FORMAT.get(format_name)
        if required is None: raise KeyError(f"unknown format: {format_name}")
        results: list[CheckResult] = []
        for check_id in required:
            value = observations.get(check_id)
            if value is True: verdict, detail = Verdict.PASS, "observed pass"
            elif value is False: verdict, detail = Verdict.BLOCK, "observed failure"
            else: verdict, detail = Verdict.UNKNOWN, "missing observation"
            results.append(CheckResult(check_id, verdict, detail))
        if any(result.verdict == Verdict.BLOCK for result in results): verdict = Verdict.BLOCK
        elif any(result.verdict == Verdict.UNKNOWN for result in results): verdict = Verdict.WARN
        else: verdict = Verdict.PASS
        return GateReport(format_name, verdict, tuple(results))


@dataclass(frozen=True)
class ThumbnailCandidate:
    candidate_id: str
    text: str
    subject_count: int
    text_area_ratio: float
    contrast_score: float
    face_or_subject_salience: float
    promise_clarity: float
    novelty_score: float


@dataclass(frozen=True)
class ThumbnailScore:
    candidate_id: str
    total: float
    failures: tuple[str, ...]


class ThumbnailJudge:
    def score(self, candidate: ThumbnailCandidate) -> ThumbnailScore:
        failures: list[str] = []
        if len(candidate.text.split()) > 7: failures.append("too_many_words")
        if candidate.subject_count > 3: failures.append("too_many_subjects")
        if candidate.text_area_ratio > 0.34: failures.append("text_dominates_frame")
        total = candidate.contrast_score * 0.22 + candidate.face_or_subject_salience * 0.24 + candidate.promise_clarity * 0.34 + candidate.novelty_score * 0.20 - len(failures) * 15
        return ThumbnailScore(candidate.candidate_id, total, tuple(failures))

    def tournament(self, candidates: Sequence[ThumbnailCandidate]) -> tuple[ThumbnailScore, ...]:
        return tuple(sorted((self.score(candidate) for candidate in candidates), key=lambda item: item.total, reverse=True))
