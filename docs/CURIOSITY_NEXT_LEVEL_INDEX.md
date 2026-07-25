# Curiosity Next-Level Operating System — Index

> Documentation-only handoff. This file changes no runtime behavior.

## Purpose

PR #172 restored the curiosity pipeline's engineering foundation. The remaining challenge is no longer basic survival. It is turning the recovered system into a repeatable creative operation that can produce accurate, distinctive, high-quality videos without drifting back into volume-first behavior.

This package defines the next operating layer for Claude. It does **not** authorize direct changes to production behavior. Claude should review these documents, convert each approved phase into a focused implementation PR, and preserve the existing fail-closed architecture.

## Starting point

The package assumes the code state documented in:

- `docs/CURIOSITY_FINAL_REPORT.md`
- `docs/CLAUDE_CONTINUATION_PLAYBOOK.md`
- `docs/CLAUDE_EXECUTION_CHECKLIST.md`

The known stopping point is PR #172 at commit:

```text
f6419ad574e140bcdd0a052f89b89304b3503e44
```

## Documents in this package

### 1. `CURIOSITY_NORTH_STAR_ARCHITECTURE.md`

Defines what the finished system should become, including its creative, factual, operational, and learning layers.

### 2. `CURIOSITY_90_DAY_EXECUTION_PLAN.md`

Turns the architecture into a staged twelve-week execution program with exit criteria and sequencing rules.

### 3. `CURIOSITY_QUALITY_SCORECARD.md`

Defines the quality contract for individual videos, the channel, and the pipeline itself.

### 4. `CURIOSITY_EXPERIMENTATION_SYSTEM.md`

Defines how the system should learn from real outputs and audience evidence without overfitting or sacrificing editorial standards.

### 5. `CURIOSITY_RELEASE_GOVERNANCE.md`

Defines branch, PR, evidence, release, rollback, incident, and publishing governance.

### 6. `CURIOSITY_NEXT_GENERATION_BACKLOG.md`

Records major future capabilities, organized by value, dependency, risk, and proof requirements.

## Required implementation order

Claude should not start with the most exciting feature. Use this order:

1. Preserve and merge the recovered foundation safely.
2. Add artifact identity and evidence integrity.
3. Strengthen facts and provenance.
4. Formalize visual judgment.
5. Speed up iteration through profiles and caching.
6. Raise the flagship quality bar.
7. Make media selection context-aware.
8. Improve repair specificity.
9. Prove multiple stories.
10. Run controlled public canaries.
11. Add scheduled approval workflows.
12. Build learning and optimization only after the prior stages are stable.

## Prohibited shortcuts

Do not:

- merge unrelated Git histories;
- modify `main` directly;
- enable unattended publishing while evidence is incomplete;
- lower quality gates to make weak stories pass;
- replace difficult visuals with blanket statement cards;
- treat warning-only output as a passing gate;
- trust reports that are not bound to the exact artifact;
- optimize for posting frequency before repeatable quality exists;
- combine unrelated implementation phases in a giant PR;
- claim visual quality from code inspection alone;
- treat one successful flagship as proof of a general system.

## Definition of next-level success

The next-level system is successful when it can repeatedly do all of the following:

```text
strong premise
→ verified claims
→ intentional visual grammar
→ efficient render and repair
→ exact-artifact judgment
→ honest quarantine or approval
→ safe publishing
→ measured audience learning
→ controlled doctrine updates
```

The goal is not maximum automation.

The goal is **reliable creative judgment at scale without losing accuracy, originality, or control**.
