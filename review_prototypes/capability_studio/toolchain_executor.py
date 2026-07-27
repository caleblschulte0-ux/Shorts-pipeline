from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import json
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

from .contracts import CommandPlan


class ExecutionMode(str, Enum):
    PLAN_ONLY = "plan_only"
    EXPLICIT_LOCAL = "explicit_local"


ALLOWED_EXECUTABLES = frozenset({
    "python", "python3", "ffmpeg", "ffprobe", "yt-dlp", "manim", "blender",
    "magick", "convert", "libreoffice", "dot", "neato", "fdp", "mmdc",
    "cairosvg", "scenedetect", "otioconvert", "ocrmypdf", "pdftoppm",
    "tesseract", "demucs", "rubberband", "audacity", "rembg",
})


@dataclass(frozen=True)
class ExecutionResult:
    command_id: str
    returncode: int | None
    executed: bool
    stdout_path: str
    stderr_path: str
    reason: str = ""


class ReviewToolExecutor:
    """Workspace-scoped executor. Default mode records plans and executes nothing."""

    def __init__(self, workspace: Path, *, mode: ExecutionMode = ExecutionMode.PLAN_ONLY, timeout_seconds: int = 900) -> None:
        self.workspace = workspace.resolve()
        self.mode = mode
        self.timeout_seconds = timeout_seconds
        self.workspace.mkdir(parents=True, exist_ok=True)

    def validate(self, plan: CommandPlan) -> tuple[str, ...]:
        failures: list[str] = []
        if not plan.argv:
            failures.append("argv_empty")
            return tuple(failures)
        executable = Path(plan.argv[0]).name
        if executable not in ALLOWED_EXECUTABLES:
            failures.append("executable_not_allowlisted")
        for output in plan.outputs:
            if self._looks_like_pattern(output):
                continue
            target = (self.workspace / output).resolve() if not Path(output).is_absolute() else Path(output).resolve()
            if self.workspace != target and self.workspace not in target.parents:
                failures.append(f"output_escapes_workspace:{output}")
        for name in plan.env_names:
            if name not in {"GEMINI_API_KEY", "FRED_API_KEY", "NOAA_TOKEN", "CENSUS_API_KEY", "YOUTUBE_API_KEY", "PEXELS_API_KEY"}:
                failures.append(f"env_not_allowlisted:{name}")
        return tuple(failures)

    def run(self, plan: CommandPlan, *, env: Mapping[str, str] | None = None) -> ExecutionResult:
        failures = self.validate(plan)
        log_dir = self.workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = log_dir / f"{plan.command_id}.stdout.log"
        stderr_path = log_dir / f"{plan.command_id}.stderr.log"
        record_path = log_dir / f"{plan.command_id}.plan.json"
        record_path.write_text(json.dumps(asdict(plan), indent=2, sort_keys=True), encoding="utf-8")
        if failures:
            return ExecutionResult(plan.command_id, None, False, str(stdout_path), str(stderr_path), ";".join(failures))
        if self.mode == ExecutionMode.PLAN_ONLY:
            return ExecutionResult(plan.command_id, None, False, str(stdout_path), str(stderr_path), "plan_only")

        child_env = {"PATH": os.environ.get("PATH", "")}
        supplied = env or {}
        for name in plan.env_names:
            if name in supplied:
                child_env[name] = supplied[name]
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            completed = subprocess.run(
                list(plan.argv),
                cwd=self.workspace,
                env=child_env,
                stdout=stdout,
                stderr=stderr,
                timeout=self.timeout_seconds,
                check=False,
            )
        return ExecutionResult(plan.command_id, completed.returncode, True, str(stdout_path), str(stderr_path))

    @staticmethod
    def _looks_like_pattern(value: str) -> bool:
        return any(token in value for token in ("%03d", "%04d", "*", "{frame}"))


def run_many(executor: ReviewToolExecutor, plans: Sequence[CommandPlan]) -> tuple[ExecutionResult, ...]:
    results: list[ExecutionResult] = []
    for plan in plans:
        result = executor.run(plan)
        results.append(result)
        if result.executed and result.returncode != 0:
            break
        if not result.executed and result.reason not in {"plan_only"}:
            break
    return tuple(results)
