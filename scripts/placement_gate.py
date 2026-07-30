#!/usr/bin/env python3
"""Placement gate — HARD enforcement of the funnel architecture.

The rule (docs/PIPELINE_LAYOUT.md, operator ruling 2026-07-30): new shared
capability goes UP the funnel — media into funnel/, render engines into
engines/, everything else reusable into shared/. Channel folders hold only
what is truly channel-specific, and shared logic is NEVER copied into a
channel. Docs said it; this makes auto-merge refuse PRs that break it.

Three objective checks, no LLM judgment:

  SHADOW  an added channel .py whose basename matches a module in
          funnel//shared//engines/ — a private copy waiting to drift.
  COPY    an added channel .py sharing >= COPY_LINES identical substantive
          lines with a shared-layer module or with ANOTHER channel's module —
          duplicated logic; it belongs up the funnel.
  XIMPORT a channel file importing another channel's code — if two channels
          need it, it moves up; channels never import each other.

Channel groups (imports WITHIN a group are fine):
  daily          make_*.py + reddit_card.py at repo root
  data_learning  data_learning/  (explainer + curiosity share this stack)
  third          third_capture/

Everything else (scripts/, tests/, funnel/, shared/, engines/, docs/, ...)
is out of scope: orchestrators in scripts/ legitimately import channel code.

CI:     python scripts/placement_gate.py --base <sha> --head <sha>
Local:  python scripts/placement_gate.py --tree     # audit the whole tree
Exit 0 = clean. Exit 1 = violation(s), printed as ::error for the Actions UI.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHARED_LAYERS = ("funnel", "shared", "engines")
DAILY_ROOT_FILES = frozenset({
    "make_explainer_stacked.py", "make_graph_race.py", "make_reddit_story.py",
    "make_text_card.py", "make_short.py", "reddit_card.py",
})
EXEMPT_BASENAMES = frozenset({"__init__.py"})
# Identical substantive lines shared with another module before an added
# file counts as a copy. High enough that boilerplate never trips it.
COPY_LINES = 12
_IMPORT = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_.]*)",
                     re.M)


def channel_of(path: str) -> str | None:
    """Channel group for a repo-relative path, or None if out of scope."""
    p = Path(path)
    if len(p.parts) == 1 and p.name in DAILY_ROOT_FILES:
        return "daily"
    if p.parts and p.parts[0] == "data_learning":
        return "data_learning"
    if p.parts and p.parts[0] == "third_capture":
        return "third"
    return None


def _module_channel(mod: str) -> str | None:
    """Channel group a dotted import target belongs to, or None."""
    head = mod.split(".")[0]
    if head == "data_learning":
        return "data_learning"
    if head == "third_capture":
        return "third"
    if f"{head}.py" in DAILY_ROOT_FILES:
        return "daily"
    return None


def _substantive_lines(text: str) -> set[str]:
    """Lines meaty enough that sharing many of them means copied code."""
    out = set()
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 20 or line.startswith("#"):
            continue
        if line.startswith(("import ", "from ", '"""', "'''", '"', "'")):
            continue
        out.add(line)
    return out


def check_shadow(added: list[str]) -> list[str]:
    errs = []
    for f in added:
        p = Path(f)
        if channel_of(f) is None or p.suffix != ".py":
            continue
        if p.name in EXEMPT_BASENAMES:
            continue
        for layer in SHARED_LAYERS:
            if (ROOT / layer / p.name).exists():
                errs.append(
                    f"{f}: SHADOWS {layer}/{p.name} — do not create a channel "
                    f"copy of a shared module; import `from {layer} import "
                    f"{p.stem}` instead")
    return errs


def check_copy(added: list[str]) -> list[str]:
    errs = []
    # Candidate victims: every shared-layer module + every channel module.
    pool: list[tuple[str, Path]] = []
    for layer in SHARED_LAYERS:
        pool += [(None, q) for q in (ROOT / layer).glob("*.py")]
    for f in Path(ROOT).glob("*.py"):
        if f.name in DAILY_ROOT_FILES:
            pool.append(("daily", f))
    for d, grp in (("data_learning", "data_learning"),
                   ("third_capture", "third")):
        pool += [(grp, q) for q in (ROOT / d).glob("*.py")]

    for f in added:
        grp = channel_of(f)
        p = ROOT / f
        if grp is None or p.suffix != ".py" or not p.exists():
            continue
        if p.name in EXEMPT_BASENAMES:
            continue
        mine = _substantive_lines(p.read_text(errors="replace"))
        if not mine:
            continue
        for other_grp, q in pool:
            if q.resolve() == p.resolve() or q.name in EXEMPT_BASENAMES:
                continue
            if other_grp == grp:      # same channel: internal reuse is fine
                continue
            shared_n = len(mine & _substantive_lines(
                q.read_text(errors="replace")))
            if shared_n >= COPY_LINES:
                where = ("the shared layer" if other_grp is None
                         else f"channel '{other_grp}'")
                errs.append(
                    f"{f}: COPIES {shared_n} lines from "
                    f"{q.relative_to(ROOT)} ({where}) — shared logic moves UP "
                    f"the funnel (funnel//shared//engines/), never into a "
                    f"channel")
                break
    return errs


def check_ximport(touched: list[str]) -> list[str]:
    errs = []
    for f in touched:
        grp = channel_of(f)
        p = ROOT / f
        if grp is None or p.suffix != ".py" or not p.exists():
            continue
        for m in _IMPORT.finditer(p.read_text(errors="replace")):
            target = _module_channel(m.group(1))
            if target is not None and target != grp:
                errs.append(
                    f"{f}: imports channel '{target}' code ({m.group(1)}) — "
                    f"channels never import each other; if both need it, it "
                    f"moves up the funnel")
    return errs


def _git_files(base: str, head: str, diff_filter: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"--diff-filter={diff_filter}",
         base, head],
        capture_output=True, text=True, cwd=ROOT, check=True)
    return [l for l in out.stdout.splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base")
    ap.add_argument("--head")
    ap.add_argument("--tree", action="store_true",
                    help="audit the whole tree (no git range)")
    args = ap.parse_args()

    if args.tree:
        everything = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py")
                      if ".git" not in p.parts and "cache" not in p.parts]
        added = [f for f in everything if channel_of(f)]
        touched = added
        # Whole-tree shadow/copy would flag legacy intra-repo history we've
        # accepted; tree mode audits imports (the load-bearing invariant) and
        # shadowing only.
        errs = check_shadow(added) + check_ximport(touched)
    else:
        if not (args.base and args.head):
            ap.error("--base and --head required (or --tree)")
        added = _git_files(args.base, args.head, "A")
        touched = _git_files(args.base, args.head, "AM")
        errs = (check_shadow(added) + check_copy(added)
                + check_ximport(touched))

    for e in errs:
        print(f"::error::placement gate: {e}")
    if errs:
        print(f"placement gate: FAIL ({len(errs)} violation(s)) — "
              f"see docs/PIPELINE_LAYOUT.md")
        return 1
    print("placement gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
