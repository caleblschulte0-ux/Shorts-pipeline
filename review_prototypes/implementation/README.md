# Standalone Repair Runtime

This directory contains actual, executable Python code rather than architecture-only notes.

It is still **review-only and completely unwired**:

- no production module imports it;
- no workflow runs it;
- no renderer, publisher, or live state path is referenced;
- it cannot alter the current pipeline unless Claude deliberately adapts and integrates it later.

Implemented here:

- strict typed verdict and weakest-scene models;
- immutable attempt identities and structural scene candidates;
- SHA-256 artifact manifests;
- tamper detection;
- append-only attempt recording;
- per-story filesystem locks;
- atomic canonical promotion with rollback;
- complete-attempt ranking;
- bounded repair orchestration;
- rejection of duplicate or structurally identical candidates;
- standalone end-to-end tests.

Run from the repository root:

```bash
python -m unittest -v review_prototypes.implementation.test_runtime
```

The implementation intentionally uses injected renderer, judge, candidate-generator, and preview-ranker interfaces. Claude should write adapters to the real pipeline only after reviewing the contracts and adding integration tests on a separate implementation branch.
