from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
from typing import Iterable

from .models import CommandSpec, ExecutionResult, SandboxViolation


class SandboxPolicy:
    """Path and executable allow-list for review-only external adapters."""

    def __init__(self, root: Path, allowed_executables: Iterable[Path | str]) -> None:
        self.root = Path(root).resolve()
        self.allowed_executables = frozenset(str(Path(item).resolve()) for item in allowed_executables)
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_inside(self, path: Path) -> Path:
        candidate = Path(path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise SandboxViolation(f"path escapes sandbox: {candidate}") from exc
        return candidate

    def validate_command(self, spec: CommandSpec) -> None:
        spec.validate()
        executable = str(Path(spec.argv[0]).resolve())
        if executable not in self.allowed_executables:
            raise SandboxViolation(f"executable is not allowed: {executable}")
        self.resolve_inside(spec.cwd)


class SafeExecutor:
    """Runs argv directly, never through a shell, with a minimal environment."""

    BASE_ENV_KEYS = ("PATH", "SYSTEMROOT", "WINDIR", "TMP", "TEMP")

    def __init__(self, policy: SandboxPolicy) -> None:
        self.policy = policy

    def run(self, spec: CommandSpec) -> ExecutionResult:
        self.policy.validate_command(spec)
        cwd = self.policy.resolve_inside(spec.cwd)
        env = {key: os.environ[key] for key in self.BASE_ENV_KEYS if key in os.environ}
        env.update({str(key): str(value) for key, value in spec.env.items()})
        env["PUBLISH_ENABLED"] = "0"
        env["CHANNEL_SANDBOX_ROOT"] = str(self.policy.root)
        started = time.monotonic()
        completed = subprocess.run(
            list(spec.argv),
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=spec.timeout_seconds,
            shell=False,
            check=False,
        )
        return ExecutionResult(
            argv=spec.argv,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            elapsed_seconds=time.monotonic() - started,
        )
