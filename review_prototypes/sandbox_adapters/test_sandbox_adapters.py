from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from .adapters import SandboxJudgeAdapter, SandboxRendererAdapter
from .execution import SafeExecutor, SandboxPolicy
from .models import CommandSpec, JudgeRequest, RenderRequest, SandboxViolation


FAKE_TOOL = r'''
import json, pathlib, sys
mode, request_path, output_dir = sys.argv[1:4]
request = json.loads(pathlib.Path(request_path).read_text())
out = pathlib.Path(output_dir)
if mode == "render":
    (out / "video.mp4").write_bytes(b"fake-video:" + request["slug"].encode())
    (out / "scene_plan.json").write_text(json.dumps({"slug": request["slug"]}))
elif mode == "judge":
    (out / "verdict.json").write_text(json.dumps({
        "decision": "ship", "score": 91, "dimensions": {"clarity": 9.1},
        "hard_failures": [], "watched_video": True, "judge_version": "fixture-v1"
    }))
'''


class SandboxAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tool = self.root / "fake_tool.py"
        self.tool.write_text(FAKE_TOOL, encoding="utf-8")
        self.policy = SandboxPolicy(self.root, [sys.executable])
        self.executor = SafeExecutor(self.policy)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def spec(self, mode: str, request: Path, output: Path) -> CommandSpec:
        return CommandSpec(
            argv=(sys.executable, str(self.tool), mode, str(request), str(output)),
            cwd=self.root,
        )

    def test_path_escape_is_rejected(self) -> None:
        with self.assertRaises(SandboxViolation):
            self.policy.resolve_inside(self.root.parent / "escape")

    def test_unapproved_executable_is_rejected(self) -> None:
        spec = CommandSpec(argv=("/bin/sh", "-c", "echo nope"), cwd=self.root)
        with self.assertRaises(SandboxViolation):
            self.executor.run(spec)

    def test_renderer_and_judge_execute_without_publish_access(self) -> None:
        renderer = SandboxRendererAdapter(
            self.policy, self.executor, lambda req, out: self.spec("render", req, out)
        )
        rendered = renderer.render(
            RenderRequest("demo", "attempt-0", self.root / "rendered", "baseline")
        )
        judge = SandboxJudgeAdapter(
            self.policy, self.executor, lambda req, out: self.spec("judge", req, out)
        )
        verdict = judge.judge(
            JudgeRequest("demo", "attempt-0", rendered / "video.mp4", self.root / "judged")
        )
        self.assertEqual(verdict.decision, "ship")
        self.assertEqual(verdict.score, 91)
        execution = json.loads((rendered / "render_execution.json").read_text())
        self.assertEqual(execution["returncode"], 0)

    def test_output_directory_must_not_preexist(self) -> None:
        renderer = SandboxRendererAdapter(
            self.policy, self.executor, lambda req, out: self.spec("render", req, out)
        )
        target = self.root / "existing"
        target.mkdir()
        with self.assertRaises(FileExistsError):
            renderer.render(RenderRequest("demo", "attempt", target, "baseline"))


if __name__ == "__main__":
    unittest.main()
