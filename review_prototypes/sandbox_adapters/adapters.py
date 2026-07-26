from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .execution import SafeExecutor, SandboxPolicy
from .models import AdapterVerdict, CommandSpec, JudgeRequest, RenderRequest


class AdapterExecutionError(RuntimeError):
    pass


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class SandboxRendererAdapter:
    REQUIRED_OUTPUTS = ("video.mp4", "scene_plan.json")

    def __init__(
        self,
        policy: SandboxPolicy,
        executor: SafeExecutor,
        command_factory: Callable[[Path, Path], CommandSpec],
    ) -> None:
        self.policy = policy
        self.executor = executor
        self.command_factory = command_factory

    def render(self, request: RenderRequest) -> Path:
        request.validate()
        output_dir = self.policy.resolve_inside(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=False)
        request_path = output_dir / "render_request.json"
        _write_json(
            request_path,
            {
                "slug": request.slug,
                "attempt_id": request.attempt_id,
                "mode": request.mode,
                "candidate": request.candidate_payload,
                "publish_enabled": False,
            },
        )
        result = self.executor.run(self.command_factory(request_path, output_dir))
        _write_json(output_dir / "render_execution.json", result.__dict__)
        if not result.ok:
            raise AdapterExecutionError(
                f"renderer failed ({result.returncode}): {result.stderr.strip()}"
            )
        missing = [name for name in self.REQUIRED_OUTPUTS if not (output_dir / name).is_file()]
        if missing:
            raise AdapterExecutionError(f"renderer omitted required outputs: {missing}")
        return output_dir


class SandboxJudgeAdapter:
    def __init__(
        self,
        policy: SandboxPolicy,
        executor: SafeExecutor,
        command_factory: Callable[[Path, Path], CommandSpec],
    ) -> None:
        self.policy = policy
        self.executor = executor
        self.command_factory = command_factory

    def judge(self, request: JudgeRequest) -> AdapterVerdict:
        request.validate()
        output_dir = self.policy.resolve_inside(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=False)
        request_path = output_dir / "judge_request.json"
        _write_json(
            request_path,
            {
                "slug": request.slug,
                "attempt_id": request.attempt_id,
                "video_path": str(self.policy.resolve_inside(request.video_path)),
            },
        )
        result = self.executor.run(self.command_factory(request_path, output_dir))
        _write_json(output_dir / "judge_execution.json", result.__dict__)
        if not result.ok:
            raise AdapterExecutionError(
                f"judge failed ({result.returncode}): {result.stderr.strip()}"
            )
        verdict_path = output_dir / "verdict.json"
        if not verdict_path.is_file():
            raise AdapterExecutionError("judge omitted verdict.json")
        payload = json.loads(verdict_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AdapterExecutionError("verdict payload must be an object")
        return AdapterVerdict.from_mapping(payload)
