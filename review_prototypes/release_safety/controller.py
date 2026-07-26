from __future__ import annotations

from dataclasses import dataclass

from .models import ReleaseCandidate, ReleaseState
from .repository import ReleaseRepository


@dataclass(frozen=True)
class ReleaseDecision:
    promoted: bool
    release_id: str
    reasons: tuple[str, ...]
    state: ReleaseState


class ReleaseController:
    def __init__(self, repository: ReleaseRepository, minimum_score: float = 70.0) -> None:
        self.repository = repository
        self.minimum_score = minimum_score

    def submit(self, candidate: ReleaseCandidate) -> ReleaseDecision:
        reasons: list[str] = []
        try:
            candidate.validate()
        except ValueError as exc:
            reasons.append(str(exc))
        if candidate.score < self.minimum_score:
            reasons.append(f"score {candidate.score:.1f} below release floor {self.minimum_score:.1f}")
        if reasons:
            return ReleaseDecision(False, candidate.release_id, tuple(reasons), self.repository.state())
        self.repository.record(candidate)
        state = self.repository.promote(candidate.release_id)
        return ReleaseDecision(True, candidate.release_id, (), state)
