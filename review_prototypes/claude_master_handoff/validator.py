from __future__ import annotations

import json
import shlex
from dataclasses import asdict
from pathlib import Path

from .catalog import SAFE_TEST_PREFIXES, build_master_handoff
from .models import HandoffValidationError, MasterHandoff


UNSAFE_COMMAND_TOKENS = {
    "--publish",
    "PUBLISH_ENABLED=1",
    "mark_pull_request_ready_for_review",
    "merge_pull_request",
    "enable_auto_merge",
    "git push origin main",
    "git push --force",
}

SACRED_PRODUCTION_PATH_PARTS = (
    "state/posted_log",
    "explainer_posted_log",
    ".github/workflows",
    "uploaders/",
    "oauth",
    "token",
)


class ValidationReport(dict):
    @property
    def ok(self) -> bool:
        return bool(self.get("ok"))


def validate_commands(handoff: MasterHandoff) -> list[str]:
    errors: list[str] = []
    commands = list(handoff.first_session_commands)
    for phase in handoff.phases:
        commands.extend(phase.commands)
    for component in handoff.components:
        commands.extend(component.test_commands)

    for command in commands:
        lowered = command.lower()
        for token in UNSAFE_COMMAND_TOKENS:
            if token.lower() in lowered:
                errors.append(f"unsafe command token {token!r}: {command}")
        if command.startswith("python ") and not command.startswith(SAFE_TEST_PREFIXES):
            if "apply patch" not in command and "render the same slug" not in command \
                    and "run the sovereign showrunner" not in command \
                    and "run a frozen" not in command \
                    and "run a bounded" not in command \
                    and "follow docs/" not in command \
                    and "port identifiers" not in command \
                    and "add physically separate" not in command \
                    and "adopt one provider" not in command:
                errors.append(f"unrecognized Python command shape: {command}")
        try:
            shlex.split(command)
        except ValueError as exc:
            errors.append(f"unparseable command {command!r}: {exc}")
    return errors


def validate_production_boundaries(handoff: MasterHandoff) -> list[str]:
    errors: list[str] = []
    for component in handoff.components:
        root = component.root.lower()
        if any(part in root for part in SACRED_PRODUCTION_PATH_PARTS):
            errors.append(f"component root touches sacred production path: {component.root}")
    for phase in handoff.phases:
        if phase.authority_ceiling == "none" and phase.production_files:
            errors.append(f"read-only phase names production files: {phase.phase_id}")
    return errors


def validate_repo_paths(handoff: MasterHandoff, repo: Path) -> list[str]:
    errors: list[str] = []
    required = {component.root for component in handoff.components}
    required.update(claim.source_path for claim in handoff.evidence)
    required.update(
        {
            "review_prototypes/launch_closure/fixtures/CLAUDE_LAUNCH.md",
            "review_prototypes/launch_closure/fixtures/claude_launch_manifest.json",
            "review_prototypes/professional_media_os/ADOPTION_MANIFEST.json",
            "docs/future/CLAUDE_PROFESSIONAL_MEDIA_OS_ADOPTION.md",
        }
    )
    for relative in sorted(required):
        if not (repo / relative).exists():
            errors.append(f"missing referenced path: {relative}")
    return errors


def validate_master_handoff(repo: Path | None = None) -> ValidationReport:
    errors: list[str] = []
    handoff = build_master_handoff()
    try:
        handoff.validate()
    except HandoffValidationError as exc:
        errors.append(str(exc))
    errors.extend(validate_commands(handoff))
    errors.extend(validate_production_boundaries(handoff))
    if repo is not None:
        errors.extend(validate_repo_paths(handoff, repo))

    verified = [e for e in handoff.evidence if e.status == "verified"]
    declared = [e for e in handoff.evidence if e.status == "declared_unverified"]
    not_claimed = [e for e in handoff.evidence if e.status == "not_claimed"]
    report = ValidationReport(
        ok=not errors,
        schema_version=handoff.schema_version,
        components=len(handoff.components),
        phases=len(handoff.phases),
        risks=len(handoff.risks),
        sacred_guards=len(handoff.sacred_guards),
        decision_routes=len(handoff.decision_routes),
        evidence_verified=len(verified),
        evidence_declared_unverified=len(declared),
        evidence_not_claimed=len(not_claimed),
        errors=errors,
    )
    return report


def manifest_as_dict() -> dict:
    return asdict(build_master_handoff())


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
