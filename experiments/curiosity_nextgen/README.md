# Curiosity Next-Generation Prototypes

This directory contains **real but dormant code** for Claude to inspect, test, refine, and selectively integrate later.

## Isolation contract

Nothing in the active pipeline imports this package. This directory does not modify workflows, configuration, scheduling, publishing, rendering, story data, or CI. All modules use the Python standard library only.

## Included prototypes

- `artifact_manifest.py` — SHA-256 package manifests and report binding.
- `quality.py` — weighted quality decisions with mandatory hard floors.
- `media_ranker.py` — auditable candidate ranking and hard rejection rules.
- `story_catalog.py` — explicit story lifecycle and scheduler eligibility.
- `shot_cache.py` — deterministic cache keys and selective repair planning.
- `judge_contract.py` — hash-bound verdict validation and multi-judge consensus.
- `tests/` — isolated unit tests for the prototypes.

## Run locally

```bash
python -m unittest discover experiments/curiosity_nextgen/tests
```

## Adoption rule

Claude should not import these modules into production wholesale. Review each contract, adapt it to the real renderer and artifacts, add production-specific tests and negative controls, and integrate one capability per focused PR.
