# Review Prototypes — No Runtime Effect

Everything under `review_prototypes/` is intentionally isolated.

These files are **not imported by production code**, **not called by a workflow**, and **not authoritative implementations**. They are executable design sketches for Claude to review, test independently, and either reject or deliberately adapt.

Rules:

1. Do not wire these files into production without reviewing the live interfaces.
2. Do not copy them wholesale merely because they compile.
3. Preserve transactional semantics if adapting the attempt-store prototype.
4. Preserve structured diagnosis if adapting the verdict contracts.
5. Add integration tests before connecting any prototype to `repair_loop.py`, `showrunner_review.py`, or the preview workflow.

Included prototypes:

- `attempt_store.py` — isolated, filesystem-backed attempt snapshots and transactional promotion.
- `quality_contracts.py` — typed contracts and validation helpers for structured diagnosis, candidate evaluation, and benchmark summaries.
- `test_attempt_store.py` — standalone tests demonstrating rollback and winner promotion semantics.

Run locally without touching production state:

```bash
python -m unittest review_prototypes.test_attempt_store
python review_prototypes/quality_contracts.py
```
