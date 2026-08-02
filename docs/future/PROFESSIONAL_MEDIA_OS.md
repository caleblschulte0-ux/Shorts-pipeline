# Professional Media OS — isolated future architecture

> **Status:** review-only design and prototype specification
>
> **Production impact:** none
>
> **Allowed adoption path:** Claude may selectively port contracts and modules through separate, reviewed, fail-closed production changes.

## Purpose

The production pipeline should eventually become more than a reliable video factory. The professional-level advantage is a system that preserves evidence, creative decisions, experiments, failures, and audience learning as durable institutional knowledge.

This document defines that target without wiring any of it into production.

The design assumes the earlier shared-runtime, channel-brain separation, run-manifest, resumability, asset-catalog, evidence, QA, repair, analytics-contract, and capability-health work has already been adopted. It does not replace those systems.

## Non-negotiable boundaries

1. Channel brains keep their own identity, doctrine, allowed formats, package schema, learning policy, posted log, token suffix, and expected-channel guard.
2. Shared systems may advise and rank, but may not silently rewrite channel doctrine.
3. No automatic adaptation from immature samples.
4. Observations, inferences, recommendations, experiments, and adopted decisions remain distinct records.
5. Every adopted rule is reversible, versioned, attributable, and tied to evidence.
6. Publishing remains outside this prototype.
7. This architecture fails closed when evidence, rights, identity, or evaluation maturity is insufficient.

---

# 1. The professional moat

Most content automation systems can generate scripts, assemble media, render, and upload. Those capabilities become commodities.

The defensible system is the accumulated memory of:

- which creative choices were made;
- what evidence supported each claim;
- what the system expected to happen;
- what actually happened at every funnel stage;
- which changes were tested rather than guessed;
- where a pattern applies and where it does not;
- why an operator accepted or rejected a recommendation;
- which production paths repeatedly fail;
- how confidence changed as evidence matured.

The pipeline therefore needs six professional layers:

1. **Content genome** — a structured creative fingerprint for every candidate and published video.
2. **Creative intelligence lab** — multiple strategies, cheap previews, independent critics, and tournaments.
3. **Institutional memory** — append-only observations, decisions, reversals, and rationale.
4. **Knowledge graph** — entities, events, claims, assets, sources, videos, experiments, and relationships.
5. **Portfolio intelligence** — choose a balanced slate under opportunity, diversity, cost, rights, and capacity constraints.
6. **Operator intelligence** — explain failures and recommendations in terms of concrete stage and timeline evidence.

---

# 2. Canonical record types

## 2.1 Content genome

A content genome records the decisions that made a piece of content what it is.

Required categories:

- subject and event class;
- viewer promise and unresolved question;
- emotional driver;
- hook structure and first proof timing;
- narrative structure and reveal position;
- visual grammar and asset strategy;
- title and packaging pattern;
- format, duration, and channel identity;
- evidence completeness and rights state;
- expected production cost and failure risk;
- novelty against recent channel output.

A genome is descriptive. It must not contain outcome metrics that were unavailable when the candidate was created.

## 2.2 Evidence reference

Every claim or recommendation can point to evidence references containing:

- immutable source identifier;
- source type;
- retrieval or observation time;
- exact locator or excerpt hash;
- rights or usage status;
- confidence;
- maturity state;
- optional expiration or review date.

## 2.3 Candidate

A candidate is a complete creative strategy, not a minor wording variant. Candidates for one event should differ materially in promise, narrative order, proof strategy, emotional frame, or format.

## 2.4 Evaluation

Evaluations remain independent records. The system should never collapse all criticism into a single unexplained score.

Minimum evaluator families:

- hard constraints;
- evidence and claim integrity;
- channel identity;
- historical analog retrieval;
- hook and narrative criticism;
- visual and production feasibility;
- rights and policy risk;
- novelty and portfolio fit;
- cost and expected repair burden.

## 2.5 Experiment

An experiment records:

- explicit hypothesis;
- eligible population;
- treatment and control;
- primary metric;
- guardrail metrics;
- minimum maturity and sample rules;
- maximum allocation;
- stop conditions;
- result and confidence;
- adoption decision.

## 2.6 Decision record

A decision record answers:

- What changed?
- Why did it change?
- What evidence justified it?
- Where does it apply?
- Where does it not apply?
- Who or what approved it?
- How is it rolled back?
- When must it be reviewed?

---

# 3. Information architecture

```text
Signals and sources
        ↓
Evidence normalization
        ↓
Entity/event/claim graph
        ↓
Channel brain creates hypotheses
        ↓
Candidate factory creates distinct strategies
        ↓
Creative intelligence lab
  hard gates → critics → feasibility → novelty
        ↓
Preview ladder
  plan → storyboard → rough cut → final candidate
        ↓
Portfolio planner
        ↓
Existing shared runtime and production QA
        ↓
Published outcome + shot-aligned analytics
        ↓
Observation ledger
        ↓
Experiment analysis and decision records
        ↓
Pattern library / world model / operator answers
```

The knowledge platform does not bypass channel brains or production safety. It supplies context and preserves learning.

---

# 4. Maturity model

Every learned statement has a maturity state.

## Anecdote

One or a few immature examples. May inspire a hypothesis. May not change automatic allocation.

## Directional

Repeated evidence with consistent direction, but not enough maturity or control for doctrine changes. May influence candidate ranking within strict caps.

## Experimental

A defined test is active or completed, but confidence or generalizability remains limited.

## Established

Repeated mature evidence supports a bounded, versioned rule in a defined context.

## Deprecated

The rule no longer applies, was contradicted, or was superseded. It remains in history.

The system must preserve contradictory evidence rather than deleting it.

---

# 5. Shadow-first authority ladder

## Stage 0 — record only

Capture genomes, evidence, timelines, costs, and outcomes. No ranking authority.

## Stage 1 — retrospective benchmark

Run evaluators against known strong, weak, misleading, failed, and unusual outputs. Measure false rejection and false approval.

## Stage 2 — shadow recommendation

Generate candidates and rankings beside the existing process. Store what the lab would have selected.

## Stage 3 — bounded preview selection

Allow the lab to decide which candidate receives a rough cut. No publishing authority.

## Stage 4 — canary recommendation

Permit a small number of lab-selected outputs through the normal reviewed production path.

## Stage 5 — bounded portfolio authority

The planner may choose a limited slate subject to explicit channel, diversity, rights, cost, and exploration constraints.

At every stage, rollback is immediate and the last-known-good process remains available.

---

# 6. Professional differentiators

## 6.1 Decision provenance

Every recommendation must expose its inputs, evidence, policy version, evaluator versions, and rejected alternatives.

## 6.2 Counterfactual logging

Store not only what was selected, but what credible alternatives were rejected and why. This enables later calibration instead of survivor-biased learning.

## 6.3 Evaluation calibration

Track whether each evaluator's confidence predicts its eventual correctness. A critic that sounds persuasive but has poor calibration loses authority.

## 6.4 Negative knowledge

Record known failure regions: unsupported formats, weak source classes, repeated visual patterns, unreliable providers, misleading title structures, and channel combinations that should not be attempted.

## 6.5 Temporal validity

Facts, policies, audience behavior, providers, and platform metrics change. Knowledge records require observed-at, valid-from, valid-until, and review-after fields where applicable.

## 6.6 Data lineage

A metric used in a decision must be traceable to its raw source, metric-definition version, transformation, eligibility filters, and maturity window.

## 6.7 Uncertainty preservation

Unknown values remain unknown. The system may not convert missing evidence into neutral scores or invent precise confidence.

## 6.8 Portfolio-level exploration

Exploration is reserved intentionally instead of appearing accidentally through model randomness.

## 6.9 Cost-aware intelligence

Candidates are judged on expected audience value per publishing opportunity, production minute, provider cost, and repair burden—not views alone.

## 6.10 Institutional continuity

A future operator or model can reconstruct why the pipeline behaves as it does without reading old chats or reverse-engineering code history.

---

# 7. Prototype package in this PR

The isolated package at `review_prototypes/professional_media_os/` provides dependency-free reference code for:

- immutable domain contracts;
- evidence and maturity validation;
- deterministic candidate tournaments;
- append-only hash-chained institutional memory;
- a lightweight knowledge graph;
- bounded portfolio planning;
- operator-facing stage diagnostics;
- machine-readable adoption gates;
- unit tests using only synthetic fixtures.

It intentionally does not:

- import production code;
- call network services;
- modify workflows;
- render video;
- upload content;
- read secrets;
- write production state;
- claim predictive validity.

---

# 8. Adoption gates for Claude

Claude should not wire any module into production until all of the following are true:

1. The target production contract is frozen and mapped.
2. The prototype behavior is covered by deterministic tests.
3. Production and prototype state paths are physically separate.
4. Publishing is frozen for integration tests.
5. A baseline artifact and shadow artifact exist for the same slug.
6. Complete output is reviewed, not only still frames.
7. Existing fail-closed QA remains authoritative.
8. The new path can be disabled with one flag.
9. No channel identity value becomes shared accidentally.
10. The first live use is a bounded canary with an explicit rollback.

---

# 9. Suggested implementation sequence

1. Adopt only the record schemas and identifiers.
2. Populate genomes and evidence references without changing decisions.
3. Add append-only observation and decision ledgers.
4. Build benchmark fixtures from real historical outputs.
5. Run evaluators in shadow mode.
6. Measure evaluator calibration and false-rejection rates.
7. Enable rough-cut selection only.
8. Add one canary per eligible channel cadence.
9. Distill established patterns into versioned decision records.
10. Add portfolio selection after individual candidate ranking is trustworthy.
11. Add operator queries after lineage and evidence are complete.
12. Consider advanced statistical models only after sample maturity supports them.

---

# 10. Definition of professional readiness

This layer is professionally ready only when the system can answer, with evidence:

- Why was this candidate selected over the alternatives?
- Which claim depends on which source?
- Which evaluator objected, and was that evaluator historically reliable?
- What exact timeline event corresponds to the retention failure?
- Which rule changed because of this result?
- What contexts are excluded from that rule?
- What is the rollback path?
- How much did the decision cost?
- Was the result mature enough to learn from?
- What would the system do differently next time?

Until those questions have traceable answers, the platform may be sophisticated, but it is not yet institutionalized.
