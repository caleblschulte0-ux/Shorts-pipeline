"""The 3D judge refuses to run without a real STORY (2026-11-20: two paid judge runs graded lightning shots against
the checkout story's briefs because STORY was unset and silently defaulted)."""
import os
import subprocess
import sys
from pathlib import Path

JUDGE = Path(__file__).resolve().parents[1] / "tools" / "data3d" / "store" / "judge3d.py"


def _run(story, tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "STORY"}
    env["PATH"] = "/usr/bin:/bin"          # no claude CLI: a passing STORY check then stops at "no claude CLI"
    if story is not None:
        env["STORY"] = story
    return subprocess.run([sys.executable, str(JUDGE), str(tmp_path), str(tmp_path / "v.json")],
                          env=env, capture_output=True, text=True, cwd=str(JUDGE.parent))


def test_unset_story_is_refused(tmp_path):
    r = _run(None, tmp_path)
    assert r.returncode == 1 and "STORY=" in r.stdout, r.stdout + r.stderr


def test_unknown_story_is_refused(tmp_path):
    r = _run("no_such_story", tmp_path)
    assert r.returncode == 1 and "STORY=" in r.stdout, r.stdout + r.stderr


def test_real_story_gets_past_the_check(tmp_path):
    r = _run("lightning", tmp_path)
    assert "STORY=" not in r.stdout, r.stdout + r.stderr
