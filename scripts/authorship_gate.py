#!/usr/bin/env python3
"""Authorship gate — CLAUDE is the only agent that edits this pipeline.

Operator ruling: ChatGPT can run quarterback when the Claude subscription is
out, but it **never makes additions, only suggestions**. It may write the
day's CONTENT (packages, words, media pointers) and its retro PROPOSALS.
It may never edit the pipeline itself — no code, no workflows, no gates, no
contracts, no docs. Every change to how this thing works goes through
Claude, deliberately, through a reviewed branch.

That rule is worthless if it only lives in a README, because the agent it
constrains is the one reading the README. So it is enforced from the other
side: this classifies changed paths and refuses the combination that should
never happen.

TWO CHECKS.

  SMUGGLING   a code file inside an agent-writable area — a `.py` dropped
              into `retro/<date>/proposals/`, a workflow into
              `exchange/bundles/`. Agent areas hold DATA only, and this is
              the shape an "addition" would actually take.
  DIRECT      pipeline code changed on main without going through a PR.
              PRs run the sanity gate and the placement gate; a direct push
              of code skips both, which is exactly what an agent with repo
              write access would do.

    python scripts/authorship_gate.py --base <sha> --head <sha>
    python scripts/authorship_gate.py --base <sha> --head <sha> --pr
    python scripts/authorship_gate.py --paths a/b.py c/d.json

Exit 0 clean, 1 violation. Prints ::error:: lines for the Actions UI.
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Paths automation may write: the pipeline's own DATA and the agents' drop
# zones. Everything here is produced by a run or by a reviewer's suggestion;
# nothing here changes behaviour on its own.
AGENT_WRITABLE = (
    "state/**",                       # posted logs, analytics, packages
    "exchange/bundles/**",            # the day's ask + ChatGPT's answer
    "retro/*/**",                     # briefs, proposals, triage
    "retro/state/**",                 # ledger, agenda, experiments
    "daily_report.md", "daily_report.json",
    "data_learning/data/**",          # story_forge datasets (real numbers)
    "data_learning/niche.config.json",
    "data_learning/curiosity.config.json",
    "output/**", "cache/**",
)
# Contracts live INSIDE agent areas but are Claude's to write — they are the
# instructions the agent follows, and an agent editing its own instructions
# is the loop closing on itself.
CONTRACT_FILES = (
    "retro/README.md", "exchange/README.md",
)
# Extensions that mean "this changes behaviour", not "this is a result".
CODE_SUFFIXES = (".py", ".yml", ".yaml", ".sh", ".bash", ".js", ".ts",
                 ".toml", ".cfg", ".ini", ".mk", "Makefile", ".dockerfile")


def _match(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, p) for p in patterns)


def is_agent_writable(path: str) -> bool:
    if path in CONTRACT_FILES:
        return False
    return _match(path, AGENT_WRITABLE)


def is_code(path: str) -> bool:
    p = Path(path)
    return p.suffix in CODE_SUFFIXES or p.name in ("Makefile", "Dockerfile")


def check_smuggling(files: list[str]) -> list[str]:
    """Code hidden inside an agent's drop zone."""
    out = []
    for f in files:
        if is_agent_writable(f) and is_code(f):
            out.append(
                f"{f}: a code file inside an agent-writable area. Those "
                f"folders hold DATA and SUGGESTIONS only — proposals are "
                f"JSON, never scripts. Claude implements; agents propose.")
    return out


def check_contract_edits(files: list[str], *, pr: bool = False) -> list[str]:
    """An agent editing its own instructions is the loop closing on itself.

    Gated on `pr` for the same reason code is: Claude WROTE these contracts
    and must be able to revise them — that is the whole point of the rule.
    Caught by dogfooding, when the first version of this gate refused the
    very commit that introduced it."""
    if pr:
        return []
    return [f"{f}: an agent's own contract changed outside a reviewed PR — "
            f"only Claude edits the instructions an agent follows"
            for f in files if f in CONTRACT_FILES]


def claude_only(files: list[str]) -> list[str]:
    return [f for f in files if not is_agent_writable(f)]


def _git(base: str, head: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        capture_output=True, text=True, cwd=ROOT, check=True)
    return [l for l in out.stdout.splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base")
    ap.add_argument("--head")
    ap.add_argument("--paths", nargs="*", default=None,
                    help="classify these paths instead of a git range")
    ap.add_argument("--pr", action="store_true",
                    help="this change is on a reviewed PR branch, so "
                         "pipeline edits are expected and allowed")
    args = ap.parse_args()

    if args.paths is not None:
        files = args.paths
    elif args.base and args.head:
        files = _git(args.base, args.head)
    else:
        ap.error("need --base/--head or --paths")

    errs = (check_smuggling(files)
            + check_contract_edits(files, pr=args.pr))

    # A PR is where pipeline edits belong — that is the reviewed path, and
    # the sanity + placement gates run there. Outside a PR, a code change on
    # main skipped both, which is what an agent with write access would do.
    code_on_main = [f for f in claude_only(files) if is_code(f)]
    if code_on_main and not args.pr:
        errs.append(
            f"pipeline code changed outside a reviewed PR: "
            f"{', '.join(code_on_main[:6])}"
            f"{'…' if len(code_on_main) > 6 else ''}. Every change to how "
            f"this pipeline works goes through Claude on a branch, where the "
            f"sanity and placement gates run. A direct push of code skips "
            f"both.")

    for e in errs:
        print(f"::error::authorship gate: {e}")
    if errs:
        print(f"authorship gate: FAIL ({len(errs)} violation(s)) — "
              f"see retro/README.md and CLAUDE.md")
        return 1
    agent = [f for f in files if is_agent_writable(f)]
    print(f"authorship gate: PASS ({len(agent)} data/suggestion file(s), "
          f"{len(claude_only(files))} pipeline file(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
