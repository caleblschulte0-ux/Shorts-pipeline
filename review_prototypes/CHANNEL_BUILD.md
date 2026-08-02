# Executable channel systems — review only

This branch now contains real, standalone implementations for two channel-level needs.

## `content_system/`

- strict dataset/source models;
- fail-closed source auditing;
- deterministic premise generation and editorial scoring;
- exact numerical claim bindings back to source data;
- multi-beat story compilation with semantic visual requirements;
- queue duplicate, domain-cap, dataset-reuse, visual-reuse, and mascot-reuse controls;
- eight standalone tests.

Run:

```bash
python -m unittest review_prototypes.content_system.test_content_system -v
```

## `channel_analytics/`

- validated Shorts observations;
- Bayesian control/treatment evaluation with small-sample shrinkage;
- retention, completion, share, and subscriber guardrails;
- atomic one-active-experiment storage;
- conservative pattern scoring with recent-overuse penalties;
- five standalone tests.

Run:

```bash
python -m unittest review_prototypes.channel_analytics.test_analytics_system -v
```

These packages are not imported by the production renderer, publisher, workflow, or existing quality system. They are implementation code for Claude to review and deliberately adapt later.
