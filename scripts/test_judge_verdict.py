#!/usr/bin/env python3
"""Unit tests for the taste-verdict contract (scripts/judge_verdict.py).

The contract (TASTE_JUDGE.md): {"pass", "reject_labels", "personality" 0-5,
"card_fraction_estimate" 0-1, ...}; pass is DERIVED (no reject_labels AND
personality >= 3) and an agent-supplied pass that contradicts the rule is
refused — the boolean is never taken on faith."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import judge_verdict as jv  # noqa: E402


def expect_ok(name, v, want_pass):
    clean = jv.validate(v)
    assert clean["pass"] is want_pass, (name, clean)
    print(f"ok  {name}")


def expect_refused(name, v, substr):
    try:
        jv.validate(v)
    except jv.InvalidVerdict as e:
        assert substr in str(e), (name, str(e))
        print(f"ok  {name}")
        return
    raise AssertionError(f"{name}: verdict was accepted but must be refused")


def main():
    expect_ok("clean pass (personality 3, no labels)",
              {"personality": 3, "reject_labels": []}, True)
    expect_ok("reject on low personality",
              {"personality": 2.5, "reject_labels": []}, False)
    expect_ok("reject on any label",
              {"personality": 5, "reject_labels": ["SAMENESS"]}, False)
    expect_ok("labels normalized case-insensitively",
              {"personality": 4, "reject_labels": ["sameness "]}, False)
    expect_ok("agreeing explicit pass accepted",
              {"pass": True, "personality": 4, "reject_labels": []}, True)
    expect_refused("contradicting pass=True refused",
                   {"pass": True, "personality": 1, "reject_labels": []},
                   "contradicts")
    expect_refused("contradicting pass=False refused",
                   {"pass": False, "personality": 4, "reject_labels": []},
                   "contradicts")
    expect_refused("unknown label refused",
                   {"personality": 4, "reject_labels": ["MEH"]}, "unknown")
    expect_refused("missing personality refused", {"reject_labels": []},
                   "personality")
    expect_refused("personality out of range refused",
                   {"personality": 7, "reject_labels": []}, "out of range")
    expect_refused("card fraction out of range refused",
                   {"personality": 4, "reject_labels": [],
                    "card_fraction_estimate": 1.4}, "out of range")
    expect_refused("non-dict refused", [1, 2], "object")

    # write() refuses a verdict for a render that never happened (no _pkg).
    with tempfile.TemporaryDirectory() as td:
        ghost = Path(td) / "ghost.mp4"
        try:
            jv.write(ghost, {"personality": 4, "reject_labels": []})
            raise AssertionError("write() accepted a verdict with no package")
        except FileNotFoundError:
            print("ok  write() refuses verdict without an evidence package")
        # and writes atomically when the package exists
        pkg = Path(td) / "ghost_pkg"
        pkg.mkdir()
        dest = jv.write(ghost, {"personality": 4, "reject_labels": []})
        assert dest.exists() and dest.name == "verdict.json"
        print("ok  write() lands verdict.json in the package")
    print("judge verdict contract: 14/14 tests pass")


if __name__ == "__main__":
    main()
