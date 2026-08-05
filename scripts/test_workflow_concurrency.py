#!/usr/bin/env python3
"""A push must not be able to cancel a long render.

WHAT HAPPENED (2026-08-05). `curiosity-ci.yml` had

    concurrency:
      group: curiosity-ci-${{ github.ref }}
      cancel-in-progress: true

so a manually dispatched FOUR-HOUR canary render and a five-minute
push-triggered gate run shared one concurrency group. A canary of shared-air —
render #1 of a measured five-render sprint — was cancelled 5m17s in, before
the render job had even started, by a push of an unrelated commit to the same
branch. The run cost a slot and produced nothing, and the Actions tab says
only "cancelled": there is no message anywhere that names the cause.

Cancelling a superseded GATE run is correct — it is fast and only the newest
commit matters. Cancelling a deliberate expensive render never is. The rule is
therefore about the trigger, not the workflow: a `workflow_dispatch` groups by
its own `run_id`, which is unique, so it cannot collide with anything.

This test enforces that on every workflow that can be dispatched AND cancels
in progress. It is a shape check on YAML text rather than a semantic one,
because the alternative is executing GitHub's expression language.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"


def _group_expr(text: str) -> str:
    """The `group:` value under `concurrency:`, comments stripped.

    Deliberately not `yaml.safe_load`: pyyaml is not among the packages the
    curiosity CI job installs, and a guard that ImportErrors on the runner
    guards nothing. Comments must be stripped first — the fix for this very
    bug added a seven-line explanatory comment inside the block, and a naive
    fixed-width slice of the raw text then found only the comment and failed.
    """
    lines = []
    seen = False
    for ln in text.splitlines():
        bare = ln.split("#", 1)[0].rstrip()
        if not bare.strip():
            continue
        if bare.startswith("concurrency:"):
            seen = True
            continue
        if seen:
            if not bare.startswith((" ", "\t")):
                break                    # dedented out of the block
            lines.append(bare)
    return "\n".join(lines)


def test_a_dispatchable_canceller_groups_by_run_id():
    bad = []
    for f in sorted(WORKFLOWS.glob("*.yml")):
        text = f.read_text()
        if "cancel-in-progress: true" not in text:
            continue                     # queues instead of cancelling: fine
        if "workflow_dispatch" not in text:
            continue                     # nothing expensive to protect
        # The group must vary with the run when the trigger is a dispatch.
        if "github.run_id" not in _group_expr(text):
            bad.append(f.name)
    assert not bad, (
        "these workflows can be dispatched AND cancel in progress, but their "
        f"concurrency group does not vary by run_id: {bad}. A push to the same "
        "ref will cancel a dispatched run mid-render. Group a dispatch by "
        "github.run_id — see the note at the top of curiosity-ci.yml.")
    print("ok  every dispatchable cancelling workflow is safe from a push")


def test_the_two_known_offenders_are_actually_fixed():
    """Named, because a generic sweep can pass by finding nothing to check."""
    for name in ("curiosity-ci.yml", "preview.yml", "preview_explainer.yml"):
        text = (WORKFLOWS / name).read_text()
        assert "concurrency:" in text, name
        block = _group_expr(text)
        assert "workflow_dispatch" in block and "github.run_id" in block, (
            f"{name} lost its dispatch-groups-by-run_id guard — a push will "
            "cancel a render again")
    print("ok  all three preview/canary lanes group a dispatch by run_id")


def test_the_long_publish_lanes_do_not_cancel_at_all():
    """A publishing render must QUEUE behind another, never kill it."""
    for name in ("curiosity.yml", "explainer.yml", "daily.yml", "third.yml"):
        f = WORKFLOWS / name
        if not f.exists():
            continue
        assert "cancel-in-progress: true" not in f.read_text(), (
            f"{name} publishes and must never cancel a run in progress — a "
            "half-rendered publish lane is how a day silently ships nothing")
    print("ok  the publish lanes queue rather than cancel")


if __name__ == "__main__":
    test_a_dispatchable_canceller_groups_by_run_id()
    test_the_two_known_offenders_are_actually_fixed()
    test_the_long_publish_lanes_do_not_cancel_at_all()
    print("all workflow-concurrency checks pass")
