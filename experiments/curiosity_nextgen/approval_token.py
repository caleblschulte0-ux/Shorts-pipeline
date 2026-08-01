"""One-time, hash-bound release approval tokens for the dormant lab.

Tokens authorize one exact manifest on one expected channel for a limited time.
They are not connected to publishing and intentionally use only the standard
library so the contract can be reviewed independently.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import MutableSet


@dataclass(frozen=True)
class ApprovalClaims:
    manifest_sha256: str
    channel_id: str
    issued_at: int
    expires_at: int
    nonce: str
    maximum_uploads: int = 1
    purpose: str = "public_canary"

    def __post_init__(self) -> None:
        if len(self.manifest_sha256) < 16:
            raise ValueError("manifest_sha256 must look like a content hash")
        if not self.channel_id.strip() or not self.nonce.strip() or not self.purpose.strip():
            raise ValueError("channel_id, nonce, and purpose must be nonempty")
        if self.expires_at <= self.issued_at:
            raise ValueError("expires_at must be later than issued_at")
        if self.maximum_uploads != 1:
            raise ValueError("prototype approvals are intentionally single-upload only")


@dataclass(frozen=True)
class ApprovalVerification:
    valid: bool
    claims: ApprovalClaims | None
    reasons: tuple[str, ...]


@dataclass
class ApprovalLedger:
    consumed_nonces: MutableSet[str]

    @classmethod
    def empty(cls) -> "ApprovalLedger":
        return cls(set())

    def consume(
        self,
        token: str,
        *,
        secret: bytes,
        expected_manifest_sha256: str,
        expected_channel_id: str,
        now: int | None = None,
    ) -> ApprovalVerification:
        result = verify_approval(
            token,
            secret=secret,
            expected_manifest_sha256=expected_manifest_sha256,
            expected_channel_id=expected_channel_id,
            now=now,
            consumed_nonces=self.consumed_nonces,
        )
        if result.valid and result.claims is not None:
            self.consumed_nonces.add(result.claims.nonce)
        return result


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _canonical_payload(claims: ApprovalClaims) -> bytes:
    return json.dumps(asdict(claims), sort_keys=True, separators=(",", ":")).encode("utf-8")


def issue_approval(claims: ApprovalClaims, *, secret: bytes) -> str:
    if len(secret) < 16:
        raise ValueError("secret must contain at least 16 bytes")
    payload = _canonical_payload(claims)
    signature = hmac.new(secret, payload, hashlib.sha256).digest()
    return f"v1.{_b64encode(payload)}.{_b64encode(signature)}"


def verify_approval(
    token: str,
    *,
    secret: bytes,
    expected_manifest_sha256: str,
    expected_channel_id: str,
    now: int | None = None,
    consumed_nonces: set[str] | MutableSet[str] = frozenset(),
) -> ApprovalVerification:
    reasons: list[str] = []
    try:
        version, payload_part, signature_part = token.split(".", 2)
    except ValueError:
        return ApprovalVerification(False, None, ("malformed_token",))
    if version != "v1":
        reasons.append("unsupported_token_version")

    try:
        payload = _b64decode(payload_part)
        supplied_signature = _b64decode(signature_part)
    except Exception:
        return ApprovalVerification(False, None, ("invalid_base64",))

    expected_signature = hmac.new(secret, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return ApprovalVerification(False, None, ("invalid_signature",))

    try:
        raw = json.loads(payload.decode("utf-8"))
        claims = ApprovalClaims(
            manifest_sha256=str(raw["manifest_sha256"]),
            channel_id=str(raw["channel_id"]),
            issued_at=int(raw["issued_at"]),
            expires_at=int(raw["expires_at"]),
            nonce=str(raw["nonce"]),
            maximum_uploads=int(raw.get("maximum_uploads", 1)),
            purpose=str(raw.get("purpose", "public_canary")),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return ApprovalVerification(False, None, (f"invalid_claims:{type(exc).__name__}",))

    current = int(datetime.now(timezone.utc).timestamp()) if now is None else int(now)
    if claims.manifest_sha256 != expected_manifest_sha256:
        reasons.append("manifest_mismatch")
    if claims.channel_id != expected_channel_id:
        reasons.append("channel_mismatch")
    if current < claims.issued_at:
        reasons.append("token_not_yet_valid")
    if current >= claims.expires_at:
        reasons.append("token_expired")
    if claims.nonce in consumed_nonces:
        reasons.append("token_already_consumed")
    if claims.maximum_uploads != 1:
        reasons.append("upload_limit_not_one")

    return ApprovalVerification(not reasons, claims, tuple(sorted(set(reasons))))
