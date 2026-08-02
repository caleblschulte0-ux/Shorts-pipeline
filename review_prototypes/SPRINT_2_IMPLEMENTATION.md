# Isolated Channel Build Sprint 2

This sprint adds executable review-only code. Nothing here is imported by the production pipeline.

## Added systems

### `retention_system/`

- generates four structurally different hook candidates;
- enforces action by 0.5 seconds and core reveal by 1.5 seconds;
- detects long beats, static holds, repeated mascot actions, caption overload, and weak tension progression;
- generates and selects endings that add synthesis, consequence, mascot resolution, and visual payoff;
- compiles the selected hook, body beats, and ending into one validated retention package.

### `channel_operations/`

- fails closed on missing source, retention, showrunner, score, dimension, or artifact evidence;
- selects diverse release batches rather than only highest raw scores;
- limits a batch to one active experiment;
- spaces releases into UTC slots rather than dumping them simultaneously.

### `system_scorecard/`

- calculates separate design, implementation, unit-test, integration-test, production-wiring, and production-proof percentages;
- prevents isolated prototypes from being reported as nearly complete;
- identifies critical capabilities whose implementation outruns integration or production evidence.

### `integration_lab/`

- composes retention, readiness, portfolio selection, and scheduling with fake story inputs;
- proves unverified sources are held and competing experiments cannot both enter one release batch.

## Local verification

```bash
python -m unittest discover -s review_prototypes -p 'test_*.py' -v
```

Result for these newly added packages: **16 tests passed**.

## Safety

- production files modified: 0
- workflow files modified: 0
- runtime imports added: 0
- uploader or renderer calls added: 0
