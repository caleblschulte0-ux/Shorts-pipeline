#!/usr/bin/env python3
"""Does this diff touch the expression contract?

The merge gate needs the expression suite to be a REQUIRED job (doctor
finding 808fcf2f9b8e: it ran as a neighbouring workflow, so a PR changing
`data_learning/pro_render.py` squash-merged before any measured render — a
proof that runs after the merge is a report, not a gate). But it is a
25-minute render, and an ordinary package PR should not pay for it.

So the job is skipped when nothing it covers changed, and this decides that.

The path list is READ FROM `expression-tests.yml`'s own `pull_request:
paths:` rather than restated here. A second copy is how the two drift, and
drift is already half of this finding: that workflow's PR paths were a
subset of its push paths, missing the production renderer the whole contract
is about.

    python3 scripts/expression_paths_touched.py <base-sha> <head-sha>

Writes `touched=true|false` to $GITHUB_OUTPUT when set, and prints what
matched. FAILS OPEN — an unreadable workflow or an unusable diff answers
"true", because running the suite unnecessarily costs 25 minutes and
skipping it wrongly costs the gate.
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "expression-tests.yml"


def contract_globs() -> list[str]:
    wf = yaml.safe_load(WF.read_text())
    on = wf.get(True, wf.get("on", {}))
    return list(on["pull_request"]["paths"])


def changed_files(base: str, head: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"],
                         capture_output=True, text=True, check=True,
                         cwd=str(ROOT))
    return [f for f in out.stdout.split() if f]


def matches(files, globs) -> list[str]:
    return sorted(f for f in files
                  if any(fnmatch.fnmatch(f, g) for g in globs))


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        base, head = argv[0], argv[1]
        globs = contract_globs()
        hit = matches(changed_files(base, head), globs)
        touched = bool(hit)
        print("expression contract files changed: " + (", ".join(hit) or "none"))
    except Exception as exc:                             # noqa: BLE001
        # Fail OPEN: run the suite. See the module docstring.
        print(f"::warning::could not decide from the diff ({exc}) — "
              f"running the expression suite anyway")
        touched = True
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"touched={'true' if touched else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
