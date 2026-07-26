from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from review_prototypes.full_video_proof.acceptance import assess_runs
from review_prototypes.full_video_proof.models import ProofAssessment, SuiteRunProof
from review_prototypes.observability.event_log import HashChainedEventLog
from review_prototypes.release_safety.controller import ReleaseController, ReleaseDecision
from review_prototypes.release_safety.models import ReleaseCandidate


@dataclass(frozen=True)
class ControlPlaneResult:
    proof: ProofAssessment
    releases: tuple[ReleaseDecision, ...]
    event_log_verified: bool
    event_log_failure: str | None


class ReviewControlPlane:
    """Composes proof, audit logging, and release safety without production I/O."""

    def __init__(
        self,
        event_log: HashChainedEventLog,
        release_controller: ReleaseController,
    ) -> None:
        self.event_log = event_log
        self.release_controller = release_controller

    def execute(
        self,
        *,
        runs: Sequence[SuiteRunProof],
        phase: int,
        expected_slugs: Sequence[str],
        candidates: Sequence[ReleaseCandidate],
    ) -> ControlPlaneResult:
        proof = assess_runs(runs, phase, expected_slugs)
        self.event_log.append(
            run_id=runs[-1].run_id if runs else "missing",
            stage="proof",
            kind="proof_completed" if proof.passed else "proof_failed",
            payload={"phase": phase, "reasons": list(proof.reasons)},
        )
        decisions: list[ReleaseDecision] = []
        for candidate in candidates:
            if not proof.passed:
                decision = ReleaseDecision(
                    promoted=False,
                    release_id=candidate.release_id,
                    reasons=("full-video proof gate did not pass",),
                    state=self.release_controller.repository.state(),
                )
            else:
                decision = self.release_controller.submit(candidate)
            decisions.append(decision)
            self.event_log.append(
                run_id=runs[-1].run_id if runs else "missing",
                stage="release",
                kind="release_completed" if decision.promoted else "release_failed",
                payload={
                    "release_id": candidate.release_id,
                    "artifact_ref": candidate.video_sha256,
                    "reasons": list(decision.reasons),
                },
            )
        verified, failure = self.event_log.verify()
        return ControlPlaneResult(proof, tuple(decisions), verified, failure)
