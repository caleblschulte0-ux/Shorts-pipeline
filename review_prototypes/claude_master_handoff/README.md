# Claude master handoff

This directory is the **canonical starting point** for Claude on draft PR #174.

It consolidates the review-only work that accumulated across the branch: safety and quality contracts, content and analytics, visible-quality render labs, production-shaped shadow integration, launch rehearsal, free capability expansion, subscription fallback, and the Professional Media OS reference platform.

## Safety boundary

- Nothing here authorizes production wiring.
- Nothing here authorizes publishing.
- Nothing here weakens the sovereign showrunner.
- Every adoption phase is separate, gated, reversible, and bounded.
- The branch must remain draft until a human explicitly changes that status.

## Start

```bash
cat review_prototypes/claude_master_handoff/PLAYBOOK.md
python -m review_prototypes.claude_master_handoff.cli summary
python -m review_prototypes.claude_master_handoff.cli validate --repo .
python -m unittest -v review_prototypes.claude_master_handoff.test_master_handoff
```

Then run the critical launch preflight:

```bash
python -m unittest -v review_prototypes.integration_bridge.test_integration_bridge
python -m unittest -v review_prototypes.launch_closure.test_launch_closure
python -m review_prototypes.launch_closure.cli --out /tmp/shorts-launch-rehearsal
```

## Files

- `PLAYBOOK.md` — complete human execution playbook.
- `FIRST_SESSION_PROMPT.md` — ready-to-paste Claude session prompt.
- `catalog.py` — canonical component, phase, risk, evidence, and guard catalog.
- `models.py` — strict immutable handoff contracts.
- `validator.py` — fail-closed consistency, command-safety, boundary, and path checks.
- `cli.py` — summary, validation, and manifest emission.
- `fixtures/master_handoff_manifest.json` — machine-readable full handoff.
- `fixtures/validation_report.json` — frozen validator result.
- `fixtures/final_scorecard.json` — final handoff and honest system percentages.
- `fixtures/risk_register.json` — machine-readable risk, mitigation, and rollback map.
- `fixtures/adoption_graph.json` — ordered phase graph and authority ceilings.
- `test_master_handoff.py` — tests that keep the handoff honest.

## Meaning of complete

The handoff, review system, and migration rehearsal are complete. Production adoption is not. Claude must selectively port one bounded phase at a time and must stop on drift, regression, missing evidence, reviewer disagreement, or any publishing escape.
