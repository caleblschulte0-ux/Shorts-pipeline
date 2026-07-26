# Claude adoption guide — Professional Media OS prototype

> Review-only instructions. This document does not authorize direct production wiring.

## Goal

Selectively port the isolated `review_prototypes/professional_media_os/` reference contracts into the future shared architecture without changing channel identity, publishing authority, existing fail-closed QA, or the current production path until each adoption gate is satisfied.

## Start here

```bash
python -m unittest review_prototypes.professional_media_os.test_professional_media_os
python -m review_prototypes.professional_media_os.cli demo
cat review_prototypes/professional_media_os/ADOPTION_MANIFEST.json
```

Do not begin integration if the isolated suite fails.

---

# Phase A — contract adoption only

## Objective

Introduce versioned record shapes without changing decisions or behavior.

## Port from the prototype

- `EvidenceRef`
- `ContentGenome`
- `Candidate`
- `CandidateEvaluation`
- `TournamentResult`
- `ExperimentSpec`
- `PatternRecord`
- `DecisionRecord`
- `PortfolioConstraints`
- `PortfolioPlan`
- `StageMetrics`
- `VideoOutcome`

## Rules

1. Put production-owned versions in the future shared contracts package, not inside a channel brain.
2. Keep every channel identity field channel-owned.
3. Use adapters at the boundary. Do not make existing producers immediately emit the full schema.
4. Add `schema_version` to every persisted record.
5. Preserve unknowns as `null` or explicit unknown states. Never replace missing values with zero.
6. Add round-trip serialization and compatibility tests.
7. No ranking, learning, rendering, workflow, or publishing change in this phase.

## Required proof

- all new contracts serialize deterministically;
- older manifests still load;
- no production output changes for the same input;
- no new import from a channel brain to publisher or persistent-state writer;
- all channel identity values remain unique.

---

# Phase B — record-only shadow capture

## Objective

Capture what the existing system already does without letting the new layer influence it.

## Add isolated shadow outputs

For every eligible run, write a separate shadow bundle containing:

```text
shadow_media_os/<channel>/<run_id>/
    content_genome.json
    evidence_refs.json
    candidate_selected.json
    timeline.json
    cost.json
    contract_versions.json
```

The shadow writer must:

- receive normalized data from the shared runtime;
- never be imported by a channel brain;
- never mutate the run manifest after publication finalization;
- never write posted logs, tokens, packages, or production analytics state;
- fail open operationally only by skipping the shadow record, while emitting a visible diagnostic;
- have one kill switch that restores the exact old behavior.

## Required proof

- production artifact hashes match with shadow mode on and off;
- upload requests are byte-for-byte unchanged;
- shadow state paths are physically separate;
- a missing shadow directory cannot fail production;
- no secret value appears in the shadow bundle.

---

# Phase C — institutional ledger

## Objective

Preserve observations, recommendations, operator decisions, reversals, and experiment outcomes as append-only history.

Port the concepts from `ledger.py`, but choose a production store appropriate for concurrency. The prototype file ledger is deliberately single-writer and must not be copied blindly into a concurrent runtime.

## Event families

```text
observation.recorded
candidate.generated
candidate.evaluated
candidate.selected
candidate.rejected
preview.rendered
qa.completed
publication.completed
analytics.matured
experiment.started
experiment.stopped
decision.adopted
decision.reverted
pattern.versioned
```

Each event requires:

- stable event ID;
- exact run, candidate, video, and channel identity where applicable;
- event schema version;
- occurred-at time;
- producer identity and version;
- immutable payload hash;
- predecessor or transaction identity;
- redacted metadata.

## Required proof

- duplicate events are idempotent;
- tampering is detectable;
- replay yields the same derived state;
- an adopted decision can be traced to mature evidence;
- reversals append new history rather than rewriting old history.

---

# Phase D — evidence-first research packet

## Objective

Prevent unsupported premises and promises from entering expensive production.

Adapt `research.py` behind the existing signal and research process.

## Fail-closed requirements

A core promise cannot advance when:

- no acceptable support remains after source policy filters;
- required primary evidence is absent;
- independent-source requirements are not met;
- a time-sensitive source is stale;
- rights status is outside the channel policy;
- an unresolved contradiction changes the promised outcome;
- source lineage cannot be reconstructed.

Do not use the compiler to fetch information. Retrieval and normalization remain separate capabilities.

## Required proof

- every spoken or displayed core factual claim resolves to evidence;
- unsupported claims identify the exact missing support;
- stale evidence becomes ineligible without deleting history;
- source conflicts remain visible;
- narrowing the promise can repair a packet without inventing support.

---

# Phase E — historical benchmark corpus

## Objective

Create a representative evaluation set before granting ranking authority.

The corpus must include:

- strong outputs;
- weak outputs;
- high-hook/weak-body outputs;
- low-exposure/high-satisfaction outputs;
- misleading promises;
- rights or evidence failures;
- visually polished but conceptually weak outputs;
- technically broken outputs;
- unusual winners that a conservative evaluator might reject;
- repeated formats that later fatigued;
- operator-approved and operator-rejected cases.

Each case records:

- original inputs;
- content genome reconstructed from the final artifact;
- stage diagnosis;
- operator judgment;
- evaluator expected verdict;
- whether rejection, repair, or approval was appropriate.

## Required proof

At least 20 representative cases must exist before retrospective benchmark authority. Expand beyond that before shadow ranking. Track false rejection separately from false approval.

---

# Phase F — shadow candidate laboratory

## Objective

Generate and evaluate multiple materially different strategies without controlling publication.

Adapt `lab.py` as an orchestration contract, not as a validated prediction model.

## Candidate diversity requirement

Candidates must differ in at least one major strategic dimension:

- viewer promise;
- narrative order;
- emotional frame;
- proof strategy;
- first visual;
- format;
- payoff timing;
- audience or search intent.

Minor wording changes do not count as separate candidates.

## Evaluator isolation

Keep hard constraints separate from advisory critics. Preserve every finding and evaluator version. Never collapse a BLOCK into an average score.

## Shadow outputs

```text
candidate_set.json
individual_evaluations.json
ranking.json
blocked.json
counterfactuals.json
selection_that_production_actually_used.json
selection_the_lab_would_have_used.json
```

## Required proof

- no lab result changes the selected production candidate;
- every rejected candidate remains available for calibration;
- evaluator confidence is measured against later outcomes;
- false rejection of unusual winners is explicitly tracked;
- no evaluator silently changes channel doctrine.

---

# Phase G — rough-cut selection

## Objective

Let the lab allocate preview cost, not publication authority.

Authority is limited to choosing which eligible candidate receives a cheap rough cut.

## Requirements

- full render and upload remain unchanged;
- a hard-blocked candidate can never receive a rough cut;
- at least one explicit exploration candidate remains eligible within portfolio limits;
- preview cost, runtime, and repair burden are recorded;
- the normal full-output QA still decides whether anything advances;
- kill switch returns rough-cut selection to the last-known-good path.

## Required proof

- at least 30 shadow decisions exist;
- benchmark error rates are known;
- false rejection is within the approved threshold;
- kill switch has been exercised;
- production artifact identity is unaffected when the feature is disabled.

---

# Phase H — bounded canary

## Objective

Allow a small number of lab recommendations through the existing reviewed production path.

## Mandatory experiment fields

- hypothesis;
- treatment and control;
- eligible population;
- primary stage metric;
- guardrails;
- maturity thresholds;
- maximum allocation;
- stop conditions;
- rollback;
- analysis window;
- decision owner.

The reference governance cap is 20%, but the first live canaries should normally be materially smaller.

## Required proof

- rollback tested before allocation;
- publishing remains fail closed;
- no metric-definition mixing;
- no learning from scheduled private uploads as though they were mature public outcomes;
- no rule adoption from tiny samples;
- canary results are compared only with eligible baselines.

---

# Phase I — pattern library

## Objective

Convert repeated mature findings into reusable, scoped knowledge.

A pattern requires:

- stable pattern ID and version;
- applicability labels;
- explicit exclusions;
- structural sequence;
- observed strengths;
- known failure modes;
- evidence references;
- maturity;
- confidence;
- review date;
- supersession history.

Do not store only positive recipes. Preserve negative knowledge and deprecated versions.

## Required proof

- exclusions override positive matches;
- deprecated patterns cannot influence ranking;
- version selection is deterministic;
- every automatically applied pattern is experimental or established;
- every application is visible in the candidate lineage.

---

# Phase J — stage-aware operator intelligence

## Objective

Answer operational questions with comparable evidence rather than generic model commentary.

Adapt `operator.py` only after stage metrics and timeline events are reliable.

The operator layer must:

- compare the same metric and definition version;
- refuse ineligible samples;
- name the failing funnel stage;
- list concrete genome and timeline changes;
- distinguish plausible contributors from causal claims;
- expose unknowns;
- avoid blaming the topic when exposure or packaging is the more likely failure stage.

## Required proof

A query such as “Why did hook performance drop?” returns:

- current and baseline sample sizes;
- metric versions;
- observed delta;
- first-subject, first-proof, and hook-end differences;
- candidate/evaluator lineage;
- explicit statement that comparison does not establish causality.

---

# Phase K — bounded portfolio planner

## Objective

Choose a balanced slate only after individual candidate evaluation is trustworthy.

Adapt the constraint contract from `portfolio.py`; replace the reference greedy strategy if a better auditable solver is needed.

Constraints should include:

- target count;
- channel capacity;
- topic concentration;
- format concentration;
- cost;
- runtime;
- rights risk;
- evidence completeness;
- media feasibility;
- experiment obligations;
- minimum exploration;
- recent repetition;
- provider and render capacity.

## Required proof

- every rejection has an explicit reason;
- the planner cannot exceed channel or budget limits;
- exploration is reserved intentionally;
- a target-count shortfall is reported rather than filled with ineligible content;
- channel identity policies cannot be overridden by portfolio utility.

---

# Production files Claude must not change casually

The adoption work must not directly alter, without a separate reviewed phase:

- uploaders;
- workflow permissions;
- OAuth token selection;
- expected-channel guards;
- posted logs;
- live publishing defaults;
- showrunner scoring authority;
- repair-loop keep-best authority;
- metric definitions;
- production state commit scripts;
- channel playbook doctrine.

Any change to those areas requires a dedicated canary and rollback plan.

---

# Final adoption definition

The professional layer is not considered adopted merely because classes exist in production. It is adopted only when the system can reconstruct:

1. the candidate alternatives;
2. why one was selected;
3. which constraints and evaluator versions applied;
4. which evidence supported the promise;
5. what was expected before publication;
6. what happened at each mature funnel stage;
7. which timeline event aligned with the failure or success;
8. whether a formal experiment was involved;
9. which decision or pattern changed afterward;
10. how to reverse that change safely.

Until then, keep the layer in record-only or shadow mode.
