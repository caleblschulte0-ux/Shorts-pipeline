"""Recursive evidence, payload, and log leak-scanning prototype."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Mapping, Sequence


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class FindingKind(str, Enum):
    SECRET = "secret"
    CREDENTIAL_FIELD = "credential_field"
    PRIVATE_KEY = "private_key"
    BEARER_TOKEN = "bearer_token"
    EMAIL = "email"
    PHONE = "phone"
    INTERNAL_INSTRUCTION = "internal_instruction"
    UNSAFE_URL = "unsafe_url"


@dataclass(frozen=True)
class SecurityFinding:
    path: str
    kind: FindingKind
    severity: FindingSeverity
    excerpt: str


@dataclass(frozen=True)
class SecurityReport:
    valid: bool
    findings: tuple[SecurityFinding, ...]
    blocking_paths: tuple[str, ...]
    redaction_count: int


_CREDENTIAL_KEYS = re.compile(r"(?:api[_-]?key|secret|token|password|authorization|credential)", re.I)
_INTERNAL_KEYS = re.compile(r"(?:developer[_-]?notes|planner[_-]?reasoning|approval[_-]?hint|system[_-]?prompt|hidden[_-]?rubric)", re.I)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*", re.I)
_PRIVATE_KEY = re.compile(r"-----BEGIN(?: [A-Z]+)? PRIVATE KEY-----")
_GENERIC_SECRET = re.compile(r"\b(?:sk|pk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{12,}\b")
_URL = re.compile(r"https?://[^\s)\]}>,]+", re.I)


def _excerpt(value: str, match: re.Match[str] | None = None) -> str:
    if match is None:
        text = value[:80]
    else:
        start = max(0, match.start() - 12)
        end = min(len(value), match.end() + 12)
        text = value[start:end]
    return text.replace("\n", " ")


def _scan_string(path: str, value: str, *, allowed_hosts: frozenset[str]) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    for pattern, kind in (
        (_PRIVATE_KEY, FindingKind.PRIVATE_KEY),
        (_BEARER, FindingKind.BEARER_TOKEN),
        (_GENERIC_SECRET, FindingKind.SECRET),
    ):
        for match in pattern.finditer(value):
            findings.append(SecurityFinding(path, kind, FindingSeverity.BLOCKING, _excerpt(value, match)))
    for match in _EMAIL.finditer(value):
        findings.append(SecurityFinding(path, FindingKind.EMAIL, FindingSeverity.WARNING, _excerpt(value, match)))
    for match in _PHONE.finditer(value):
        findings.append(SecurityFinding(path, FindingKind.PHONE, FindingSeverity.WARNING, _excerpt(value, match)))
    for match in _URL.finditer(value):
        url = match.group(0)
        host = url.split("/", 3)[2].split("@")[-1].split(":")[0].lower()
        if allowed_hosts and host not in allowed_hosts:
            findings.append(SecurityFinding(path, FindingKind.UNSAFE_URL, FindingSeverity.WARNING, _excerpt(value, match)))
    return findings


def scan_payload(
    payload: object,
    *,
    allowed_hosts: frozenset[str] = frozenset(),
) -> SecurityReport:
    findings: list[SecurityFinding] = []

    def walk(value: object, path: str) -> None:
        if isinstance(value, Mapping):
            for raw_key, child in value.items():
                key = str(raw_key)
                child_path = f"{path}.{key}" if path else key
                if _CREDENTIAL_KEYS.fullmatch(key):
                    findings.append(
                        SecurityFinding(child_path, FindingKind.CREDENTIAL_FIELD, FindingSeverity.BLOCKING, key)
                    )
                if _INTERNAL_KEYS.fullmatch(key):
                    findings.append(
                        SecurityFinding(child_path, FindingKind.INTERNAL_INSTRUCTION, FindingSeverity.BLOCKING, key)
                    )
                walk(child, child_path)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
        elif isinstance(value, str):
            findings.extend(_scan_string(path or "$", value, allowed_hosts=allowed_hosts))

    walk(payload, "")
    ordered = tuple(sorted(findings, key=lambda item: (item.path, item.kind.value, item.excerpt)))
    blocking = tuple(sorted({item.path for item in ordered if item.severity is FindingSeverity.BLOCKING}))
    return SecurityReport(not blocking, ordered, blocking, len(ordered))


def redact_payload(payload: object, *, replacement: str = "[REDACTED]") -> object:
    if isinstance(payload, Mapping):
        redacted: dict[str, object] = {}
        for raw_key, value in payload.items():
            key = str(raw_key)
            if _CREDENTIAL_KEYS.fullmatch(key) or _INTERNAL_KEYS.fullmatch(key):
                redacted[key] = replacement
            else:
                redacted[key] = redact_payload(value, replacement=replacement)
        return redacted
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return [redact_payload(value, replacement=replacement) for value in payload]
    if isinstance(payload, str):
        text = _PRIVATE_KEY.sub(replacement, payload)
        text = _BEARER.sub(replacement, text)
        text = _GENERIC_SECRET.sub(replacement, text)
        text = _EMAIL.sub(replacement, text)
        text = _PHONE.sub(replacement, text)
        return text
    return payload
