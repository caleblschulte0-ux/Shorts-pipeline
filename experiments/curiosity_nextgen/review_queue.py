from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable


class ReviewRole(str, Enum):
    FACTS = "facts"
    TECHNICAL = "technical"
    EDITORIAL = "editorial"
    RELEASE = "release"


class ReviewState(str, Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ReviewRequest:
    request_id: str
    artifact_sha256: str
    requested_role: ReviewRole
    requested_at: int
    due_at: int
    requester_id: str
    state: ReviewState = ReviewState.PENDING
    reviewer_id: str | None = None
    decision_reason: str | None = None
    escalation_level: int = 0


@dataclass(frozen=True)
class QueueResult:
    requests: tuple[ReviewRequest, ...]
    blockers: tuple[str, ...]


def validate_request(request: ReviewRequest) -> tuple[str, ...]:
    blockers: list[str] = []
    if not request.request_id.strip():
        blockers.append("missing_request_id")
    if len(request.artifact_sha256) != 64:
        blockers.append("invalid_artifact_hash")
    if request.due_at <= request.requested_at:
        blockers.append("invalid_due_time")
    if not request.requester_id.strip():
        blockers.append("missing_requester")
    if request.state in {ReviewState.CLAIMED, ReviewState.APPROVED, ReviewState.REJECTED} and not request.reviewer_id:
        blockers.append("missing_reviewer")
    if request.state in {ReviewState.APPROVED, ReviewState.REJECTED} and not request.decision_reason:
        blockers.append("missing_decision_reason")
    if request.requester_id == request.reviewer_id:
        blockers.append("self_review_forbidden")
    return tuple(blockers)


def enqueue(requests: Iterable[ReviewRequest], request: ReviewRequest) -> QueueResult:
    items = tuple(requests)
    blockers = list(validate_request(request))
    if any(item.request_id == request.request_id for item in items):
        blockers.append("duplicate_request_id")
    if any(
        item.artifact_sha256 == request.artifact_sha256
        and item.requested_role == request.requested_role
        and item.state in {ReviewState.PENDING, ReviewState.CLAIMED, ReviewState.ESCALATED}
        for item in items
    ):
        blockers.append("duplicate_open_review")
    return QueueResult(items if blockers else items + (request,), tuple(sorted(set(blockers))))


def claim(request: ReviewRequest, *, reviewer_id: str, now: int) -> ReviewRequest:
    if request.state not in {ReviewState.PENDING, ReviewState.ESCALATED}:
        raise ValueError("review is not claimable")
    if now > request.due_at:
        return replace(request, state=ReviewState.EXPIRED)
    if reviewer_id == request.requester_id:
        raise ValueError("requester cannot review own request")
    return replace(request, state=ReviewState.CLAIMED, reviewer_id=reviewer_id)


def decide(
    request: ReviewRequest,
    *,
    reviewer_id: str,
    approved: bool,
    reason: str,
    now: int,
) -> ReviewRequest:
    if request.state is not ReviewState.CLAIMED:
        raise ValueError("review must be claimed")
    if request.reviewer_id != reviewer_id:
        raise ValueError("only assigned reviewer may decide")
    if now > request.due_at:
        return replace(request, state=ReviewState.EXPIRED)
    if not reason.strip():
        raise ValueError("decision reason is required")
    return replace(
        request,
        state=ReviewState.APPROVED if approved else ReviewState.REJECTED,
        decision_reason=reason,
    )


def escalate_overdue(requests: Iterable[ReviewRequest], *, now: int, maximum_level: int = 3) -> tuple[ReviewRequest, ...]:
    output: list[ReviewRequest] = []
    for request in requests:
        if request.state in {ReviewState.PENDING, ReviewState.CLAIMED, ReviewState.ESCALATED} and now > request.due_at:
            if request.escalation_level >= maximum_level:
                output.append(replace(request, state=ReviewState.EXPIRED))
            else:
                output.append(
                    replace(
                        request,
                        state=ReviewState.ESCALATED,
                        reviewer_id=None,
                        due_at=now + max(1, request.due_at - request.requested_at),
                        escalation_level=request.escalation_level + 1,
                    )
                )
        else:
            output.append(request)
    return tuple(output)


def artifact_is_fully_approved(requests: Iterable[ReviewRequest], artifact_sha256: str) -> bool:
    approvals = {
        request.requested_role
        for request in requests
        if request.artifact_sha256 == artifact_sha256 and request.state is ReviewState.APPROVED
    }
    return approvals == set(ReviewRole)
