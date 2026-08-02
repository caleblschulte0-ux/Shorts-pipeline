# Professional Media OS prototype

This package is a **review-only, dependency-free reference implementation** for the future knowledge, creative-intelligence, portfolio, and operator layers described in `docs/future/PROFESSIONAL_MEDIA_OS.md`.

## Safety boundary

The package:

- imports only the Python standard library;
- imports no production pipeline modules;
- has no network, uploader, renderer, workflow, OAuth, or secret access;
- writes only to a caller-supplied prototype directory;
- defaults to in-memory operation;
- uses synthetic fixtures in tests;
- exposes no production entrypoint;
- claims no predictive performance.

Nothing under this directory should be wired directly into production. Claude should port individual contracts or algorithms through separate reviewed changes after mapping the live production contract.

## Modules

- `contracts.py` — immutable records for evidence, genomes, candidates, evaluations, experiments, patterns, decisions, outcomes, and portfolio plans.
- `ledger.py` — append-only, hash-chained JSONL institutional memory with integrity verification.
- `knowledge.py` — lightweight temporal knowledge graph with explicit observation/inference separation and contradiction preservation.
- `lineage.py` — exact artifact, transformation, metric-definition, and decision lineage.
- `research.py` — fail-closed research packets for source quality, freshness, primary evidence, and claim support.
- `lab.py` — deterministic hard gates, independent evaluations, candidate tournament, and calibration records.
- `counterfactual.py` — transparent, uncertainty-preserving preview comparisons that make no predictive claim.
- `patterns.py` — semantically versioned creative patterns with applicability, exclusions, maturity, and failure modes.
- `governance.py` — learning eligibility, authority-stage transitions, canary constraints, and reversible rule proposals.
- `portfolio.py` — bounded slate selection under diversity, channel, risk, cost, capacity, and exploration constraints.
- `operator.py` — stage-aware diagnostics that map outcome changes to concrete creative and timeline differences.
- `fixtures.py` — synthetic test and demo builders only.
- `cli.py` — local demonstration commands only.
- `test_professional_media_os.py`, `test_lineage.py`, and `test_patterns_version.py` — isolated standard-library tests.
- `ADOPTION_MANIFEST.json` — machine-readable scope, maturity, limitations, and Claude adoption gates.

## Quick isolated checks

```bash
python -m unittest \
  review_prototypes.professional_media_os.test_professional_media_os \
  review_prototypes.professional_media_os.test_lineage \
  review_prototypes.professional_media_os.test_patterns_version
python -m review_prototypes.professional_media_os.cli demo
python -m review_prototypes.professional_media_os.cli verify-ledger --state-dir /tmp/pro-media-os
```

The demo writes only when `--state-dir` is provided. Without it, the package operates in memory and prints a synthetic result.

## Design principles

1. **No opaque master score.** Hard constraints, evaluator findings, and ranking utility remain visible.
2. **Unknown is not zero.** Missing evidence blocks or lowers confidence instead of silently becoming a neutral value.
3. **Observation is not inference.** Raw outcomes and interpretations are separate record classes.
4. **Counterfactuals survive.** Rejected candidates and their reasons remain available for later calibration.
5. **Every rule expires or is reviewed.** Temporal validity and maturity are first-class fields.
6. **Authority grows slowly.** Record-only → benchmark → shadow → rough-cut → canary → bounded portfolio.
7. **Channel identity remains sovereign.** The shared layer cannot rewrite channel doctrine.
8. **All adopted learning is reversible.** Decision records include scope, exclusions, evidence, and rollback.
9. **Lineage is exact.** Metrics and decisions retain raw artifact hashes, transform versions, filters, and policy snapshots.
10. **Negative knowledge is valuable.** Failures, contradictions, exclusions, and deprecated patterns remain queryable.

## Suggested Claude use

Claude should begin by reading the adoption manifest and `docs/future/CLAUDE_PROFESSIONAL_MEDIA_OS_ADOPTION.md`, then run all three test modules. The safest first production adaptation is the identifier and record-contract layer only. Record-only data collection and lineage should precede ranking authority.
