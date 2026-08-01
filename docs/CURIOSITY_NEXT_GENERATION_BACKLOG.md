# Curiosity Next-Generation Backlog

> Documentation only. This file changes no runtime behavior.

## Purpose

This backlog captures the large-scale capabilities that could move the curiosity system beyond safe production into a differentiated creative platform.

The backlog is intentionally prioritized by dependency and proof requirement. Claude should not implement the most ambitious items first.

---

# Priority Framework

Each initiative is labeled by:

- **Value** — expected creative or operational benefit;
- **Dependency** — what must exist first;
- **Risk** — likelihood of quality, safety, or complexity regression;
- **Proof** — evidence required before promotion.

Priority bands:

```text
P0 — required for trustworthy production
P1 — required for repeatable high quality
P2 — major efficiency or differentiation
P3 — advanced research and long-term leverage
```

---

# P0 — Trustworthy Production Foundation

## 1. Exact Artifact Identity

Value: prevents stale or mismatched approvals.

Dependencies: recovered producer and package structure.

Risk: medium migration complexity.

Proof:

- tamper tests;
- old-verdict rejection;
- manifest compatibility report.

## 2. Mandatory Factual Modes

Value: prevents accidental factual bypass.

Dependencies: claim registry and facts gate.

Risk: may quarantine many existing stories.

Proof:

- nonnumeric claim detection;
- negative controls;
- migrated flagship.

## 3. Formal Judge Workflow

Value: removes manual verdict-file handling.

Dependencies: exact artifact identity.

Risk: model availability and judge inconsistency.

Proof:

- pass, borderline, reject fixtures;
- disagreement quarantine;
- schema validation.

## 4. Exact-Manifest Publishing Approval

Value: ensures the approved video is the uploaded video.

Dependencies: manifest and release contract.

Risk: operational complexity.

Proof:

- dry-run approval;
- rerender invalidation;
- one-video canary.

## 5. Catalog Readiness State

Value: prevents runtime quarantine from acting as ordinary scheduling logic.

Dependencies: story-status manifest.

Risk: low.

Proof:

- scheduler excludes incomplete stories;
- three production candidates.

---

# P1 — Repeatable High Quality

## 6. Draft, Review, and Production Profiles

Value: faster iteration without weakening final output.

Dependencies: stable renderer.

Risk: profile confusion or approving draft artifacts.

Proof:

- clear artifact labeling;
- quality comparison;
- publish gate rejects non-production profiles.

## 7. Shot-Level Cache

Value: selective rerendering and lower repair cost.

Dependencies: deterministic shot contract and input hashing.

Risk: stale-cache defects.

Proof:

- cache invalidation tests;
- one-beat repair benchmark;
- corruption recovery.

## 8. Comparative Media Ranking

Value: fewer wrong or generic assets.

Dependencies: asset metadata and visual checking.

Risk: provider latency and ranking errors.

Proof:

- wrong-region controls;
- candidate ledger;
- improved visual-relevance score.

## 9. Visual-Family Scoring from Rendered Frames

Value: detects repetition from actual output, not intended labels.

Dependencies: contact sheets and frame embeddings or visual comparison.

Risk: false positives on deliberate motifs.

Proof:

- repeated-template fixture;
- intentional-motif exception;
- correlation with blind judge notes.

## 10. Defect-Specific Repair Engine

Value: repairs creative problems instead of only metric symptoms.

Dependencies: beat attribution and judge defect schema.

Risk: endless repair complexity.

Proof:

- two-round cap;
- before/after evidence;
- successful repairs across multiple defect types.

## 11. Multi-Story Generalization Suite

Value: proves the system is not overfit to `money-goes`.

Dependencies: stable contracts.

Risk: story work may obscure system defects.

Proof:

- three structurally different stories;
- consistent gates;
- comparable evidence packages.

## 12. Cross-Video Repetition Ledger

Value: protects channel identity from template fatigue.

Dependencies: normalized shot and story metadata.

Risk: discouraging useful recurring motifs.

Proof:

- rolling 10-video analysis;
- exceptions policy;
- planner warnings.

---

# P2 — Major Efficiency and Differentiation

## 13. Story Portfolio Optimizer

Purpose:

Balance upcoming stories across:

- subject area;
- emotional tone;
- factual complexity;
- visual grammar;
- production cost;
- novelty;
- audience learning value.

Value: prevents a queue of similar stories.

Dependencies: catalog metadata and quality memory.

Risk: over-automating editorial taste.

Proof:

- transparent ranking reasons;
- human override;
- diversity improvement.

## 14. Premise Quality Judge

Purpose:

Reject weak story ideas before expensive research and rendering.

Evaluate:

- viewer question;
- surprise;
- payoff strength;
- visual potential;
- factual tractability;
- catalog novelty.

Value: saves cost upstream.

Dependencies: portfolio context.

Risk: prematurely rejecting unconventional ideas.

Proof:

- compare predicted strength with later performance;
- preserve exploration lane.

## 15. Visual Journey Planner

Purpose:

Plan the entire video as a continuous progression rather than isolated beat cards.

Capabilities:

- spatial continuity;
- recurring object transformation;
- transition direction;
- color progression;
- scale escalation;
- chapter motifs.

Value: stronger cinematic coherence.

Dependencies: visual-family and transition metadata.

Risk: planner complexity and render constraints.

Proof:

- one continuous-journey flagship;
- higher coherence score;
- no clarity regression.

## 16. Character State Machine

Purpose:

Track character emotion, pose, knowledge, and position across the story.

Value: more believable personality and progression.

Dependencies: scene metadata and continuity.

Risk: repetitive acting or overuse.

Proof:

- visible state progression;
- continuity tests;
- higher personality score.

## 17. Evidence Visualization Compiler

Purpose:

Turn claims into appropriate evidence forms:

- comparison;
- timeline;
- map;
- calculation;
- scale model;
- mechanism;
- uncertainty range.

Value: reduces generic text cards.

Dependencies: structured claims.

Risk: misleading automated chart selection.

Proof:

- claim-to-visual mapping tests;
- factual reviewer approval;
- readability checks.

## 18. Cost-Aware Planning

Purpose:

Estimate render and media cost during planning.

Value: prevents expensive plans from failing late.

Dependencies: historical performance metadata.

Risk: favoring cheap visuals over strong visuals.

Proof:

- cost estimates versus actuals;
- quality guardrails;
- budget-aware alternatives.

## 19. Automated Accessibility Review

Evaluate:

- caption readability;
- color contrast;
- text duration;
- rapid flashing;
- audio clarity;
- visual reliance without narration.

Value: broader usability and safer output.

Dependencies: final artifact package.

Risk: low.

Proof:

- accessibility fixtures;
- independent review.

## 20. Localization-Ready Story Contracts

Purpose:

Separate claims, narration, text overlays, units, and visuals so future localization is possible.

Value: long-term channel expansion.

Dependencies: mature story schema.

Risk: early abstraction cost.

Proof:

- one translated review package;
- preserved factual mappings;
- layout adaptation.

---

# P3 — Advanced Research Capabilities

## 21. Multi-Agent Editorial Room

Roles:

- premise advocate;
- skeptic;
- factual editor;
- visual director;
- audience advocate;
- cost reviewer.

Purpose:

Surface tradeoffs before production.

Risk: expensive discussion without better decisions.

Proof:

- compare decision quality against single-agent planning;
- cap deliberation cost;
- preserve final accountability.

## 22. Counterfactual Story Testing

Generate alternate versions of:

- hook;
- chapter order;
- visual grammar;
- payoff.

Judge low-cost review packages before full production.

Value: choose stronger direction earlier.

Risk: combinatorial explosion.

Proof:

- fixed candidate count;
- measurable improvement over first draft.

## 23. Learned Media Relevance Model

Purpose:

Learn from accepted and rejected media candidates.

Value: improve retrieval ranking over time.

Dependencies: large candidate ledger.

Risk: embedding historical bias and mistakes.

Proof:

- holdout evaluation;
- explicit geography and era controls;
- human-auditable reasons.

## 24. Render-Cost Predictor

Purpose:

Predict shot time, memory, and failure risk before rendering.

Value: smarter scheduling and planning.

Dependencies: substantial performance history.

Risk: inaccurate predictions suppressing creative scenes.

Proof:

- calibrated prediction intervals;
- no automatic rejection solely from cost.

## 25. Audience Segment Learning

Purpose:

Understand whether different viewer groups respond to different story structures.

Value: richer editorial strategy.

Dependencies: sufficient channel scale and privacy-safe analytics.

Risk: over-segmentation and loss of channel identity.

Proof:

- stable segment evidence;
- editorial guardrails.

## 26. Long-Term Catalog Graph

Connect:

- topics;
- claims;
- sources;
- visual metaphors;
- audience reactions;
- recurring concepts;
- corrections;
- experiments.

Value: enables sequels, updates, and cross-video continuity.

Dependencies: normalized metadata.

Risk: data maintenance burden.

Proof:

- useful retrieval examples;
- duplicate-premise prevention;
- source update alerts.

## 27. Source Freshness Monitor

Purpose:

Detect when published and queued claims need review because sources or statistics changed.

Value: protects long-lived factual quality.

Dependencies: source registry.

Risk: noisy alerts.

Proof:

- date-sensitive fixtures;
- meaningful change detection;
- correction workflow.

## 28. Post-Publication Correction System

Purpose:

Create a formal path for:

- factual corrections;
- description updates;
- pinned clarification;
- replacement or removal;
- internal doctrine updates.

Value: accountability.

Dependencies: source and artifact identity.

Risk: operational complexity.

Proof:

- simulated correction drill;
- public-impact decision tree.

## 29. Creative Signature Model

Purpose:

Measure whether output feels recognizably like the channel without becoming repetitive.

Signals:

- pacing;
- visual motifs;
- character behavior;
- narrative shape;
- information design;
- humor style.

Value: brand distinctiveness.

Risk: optimizing creativity into a formula.

Proof:

- distinguish channel work from generic controls;
- maintain diversity thresholds.

## 30. Autonomous Production Window

Purpose:

Allow tightly constrained autonomous publishing during approved windows.

Dependencies:

- all P0 controls;
- stable multi-story proof;
- successful HOLD runs;
- public canaries;
- automatic freeze;
- incident response.

Risk: highest operational risk in the backlog.

Proof:

- repeated scheduled HOLD success;
- exact-manifest approval;
- one-failure freeze;
- owner-defined limits.

---

# Backlog Selection Rules

Select the next initiative using:

1. current blocking risk;
2. dependency readiness;
3. measurable value;
4. ability to test safely;
5. implementation scope;
6. rollback clarity;
7. effect on creative quality.

Do not select work because it sounds advanced.

---

# Suggested Sequence After the 90-Day Plan

## Quarter 2

- cross-video repetition ledger;
- premise quality judge;
- visual journey planner;
- character state machine;
- evidence visualization compiler.

## Quarter 3

- cost-aware planning;
- accessibility review;
- catalog graph;
- source freshness monitor;
- controlled portfolio optimizer.

## Quarter 4

- alternate-story testing;
- learned media ranking;
- render-cost prediction;
- creative signature research;
- limited autonomous production window.

The dates should move when dependencies are not ready. Dependency order matters more than calendar ambition.

---

# Final Backlog Principle

The next level is not reached by adding the largest number of features.

It is reached by building a system where every new capability:

- improves a named weakness;
- respects existing safety contracts;
- produces evidence;
- can be rolled back;
- generalizes across stories;
- increases quality without turning the channel into a template factory.
