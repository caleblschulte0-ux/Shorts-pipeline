# Curiosity 90-Day Execution Plan

> Documentation only. This file changes no runtime behavior.

## Purpose

This plan converts the continuation roadmap into a twelve-week execution sequence. It assumes PR #172 is the recovered engineering base and that all subsequent implementation happens in focused PRs.

The plan is deliberately staged. Later phases depend on evidence produced by earlier phases.

---

# Program Rules

## Rule 1 — One dominant purpose per PR

Each implementation PR must have one primary outcome, one acceptance checklist, and one rollback path.

## Rule 2 — No publishing expansion before evidence integrity

Do not increase automation or enable unattended publishing until artifact identity, factual provenance, and independent judgment are reliable.

## Rule 3 — No learning system before repeatable production

Audience analytics should not steer doctrine until at least three different stories can pass the same production contract.

## Rule 4 — Preserve the recovered fail-closed behavior

Every phase must maintain quarantine on missing or contradictory evidence.

## Rule 5 — Every week ends with inspectable proof

Proof may include:

- passing tests;
- negative controls;
- rendered artifacts;
- benchmark reports;
- judge packages;
- manifests;
- PR review notes.

A status paragraph alone is not proof.

---

# Week 1 — Foundation Lock and Merge Readiness

## Goal

Stabilize the recovered branch against current `main` and create a clean implementation baseline.

## Tasks

- update PR #172 against current `main`;
- verify normal merge base;
- rerun all CI on the exact candidate SHA;
- audit workflow permissions;
- verify cron cannot enable publishing;
- verify `--force` cannot bypass gates;
- document current environment variables and secrets;
- identify large or mixed changes that deserve follow-up PR separation.

## Deliverables

- merge-readiness report;
- workflow permission table;
- exact-SHA CI evidence;
- publish-freeze verification;
- rollback instructions.

## Exit criteria

- exact head SHA is green;
- publishing remains disabled by default;
- no unresolved merge conflict;
- no unreviewed runtime behavior hidden inside documentation-only commits.

---

# Week 2 — Artifact Identity and Manifest Contract

## Goal

Replace timestamp trust with cryptographic artifact identity.

## Tasks

- define manifest schema;
- hash video, story, facts, captions, thumbnail, and evidence package;
- bind all reports to manifest hashes;
- reject stale or mismatched verdicts;
- add negative controls for artifact replacement;
- define manifest versioning.

## Deliverables

- manifest specification;
- implementation PR;
- tamper tests;
- compatibility notes;
- migration behavior for existing packages.

## Exit criteria

- replacing an MP4 invalidates approval;
- editing a story invalidates its facts and visual reports;
- an old verdict cannot approve a new render;
- mismatch reasons are machine-readable.

---

# Week 3 — Mandatory Factual Modes

## Goal

Make factual provenance a default contract rather than an opt-in feature.

## Tasks

- add required `factual_mode`;
- define allowed modes;
- block missing modes;
- expand claim detection beyond digits;
- map claims to beat IDs;
- add uncertainty and modeled-value rules;
- create migration plan for existing stories.

## Deliverables

- factual-mode schema;
- enhanced facts gate;
- upgraded claim registries;
- negative-control stories;
- factual review guide.

## Exit criteria

- omission of factual mode blocks;
- unsourced superlatives and comparisons are detected;
- modeled claims cannot appear as universal facts;
- every factual beat has a claim mapping.

---

# Week 4 — Formal Visual Judge Package

## Goal

Create a standardized evidence package that can be judged without reading the code.

## Tasks

- generate opening clip;
- generate payoff clip;
- generate contact sheet;
- generate chapter-transition reel;
- generate random motion samples;
- include thumbnail and transcript;
- bind package to manifest;
- define technical and editorial judge schemas.

## Deliverables

- judge-package specification;
- reproducible package generator;
- verdict schemas;
- sample packages for pass, borderline, and reject cases.

## Exit criteria

- a judge can evaluate the finished work without code context;
- every package identifies the exact video hash;
- missing package elements quarantine;
- contradictory verdicts are rejected.

---

# Week 5 — Autonomous and Dual Judgment

## Goal

Move from manually written verdict files to a controlled judge workflow.

## Tasks

- automate verdict request and ingestion;
- record judge model/version;
- validate schema;
- add second-judge policy for borderline scores;
- quarantine disagreement;
- preserve blindness from author intent and repair history;
- add judge outage behavior.

## Deliverables

- automated judge workflow;
- dual-review policy;
- failure-mode tests;
- verdict provenance record;
- operator override policy.

## Exit criteria

- no one manually edits verdict JSON;
- missing vision capability quarantines;
- borderline videos receive a second review;
- disagreement cannot silently pass.

---

# Week 6 — Render Profiles and Measurement

## Goal

Separate fast iteration from final production rendering.

## Tasks

- define draft profile;
- define review profile;
- define production profile;
- measure each stage separately;
- establish performance budgets;
- identify the most expensive scene families;
- distinguish media lookup, scene generation, assembly, and packaging time.

## Deliverables

- render profile specification;
- benchmark report;
- per-stage timing report;
- quality comparison across profiles;
- recommended defaults.

## Exit criteria

- draft and review artifacts are clearly labeled;
- only production artifacts may be approved for publishing;
- performance reports distinguish major cost centers;
- quality gates know which profile they are judging.

---

# Week 7 — Shot Cache and Selective Repair

## Goal

Avoid rerendering the full video when only one beat changes.

## Tasks

- define deterministic shot cache key;
- store input hashes and renderer version;
- reuse unaffected segments;
- invalidate dependent transitions;
- report cache hit rate;
- add cache corruption tests;
- benchmark single-beat repair.

## Deliverables

- cache contract;
- selective rerender implementation;
- cache-integrity tests;
- before/after benchmark;
- cache cleanup policy.

## Exit criteria

- one-beat repair does not rerender all shots;
- stale cache entries cannot survive input changes;
- corrupted cache entries quarantine or regenerate;
- cache reuse is visible in performance reports.

---

# Week 8 — Flagship Quality Uplift

## Goal

Raise `money-goes` from acceptable to strong.

## Tasks

- replace wrong-region transport imagery;
- improve degraded bill-counting visual;
- diversify chapter-transition families;
- restore strongest hook composition;
- break up repeated real-media clusters;
- improve character personality and emotional progression;
- rerun both judges.

## Deliverables

- before/after evidence package;
- defect-by-defect repair log;
- new verdict;
- updated quality scorecard;
- unresolved craft notes.

## Exit criteria

- overall score at least 7.5/10;
- personality at least 4/5;
- no known relevance error;
- no reject labels;
- chapter transitions show at least three distinct families.

---

# Week 9 — Media Intelligence

## Goal

Move from first-acceptable media retrieval to comparative candidate selection.

## Tasks

- retrieve multiple candidates;
- record metadata and licensing;
- score semantic relevance;
- score geography and era;
- inspect visible text and currency;
- penalize duplicate framing;
- preserve rejected-candidate reasons;
- add candidate contact sheets.

## Deliverables

- candidate-ranking specification;
- selection ledger;
- wrong-region negative controls;
- duplicate-use report;
- asset provenance report.

## Exit criteria

- important beats compare candidates;
- wrong geography loses automatically;
- selected media can be traced to query, source, and score;
- repeated assets are visible before rendering.

---

# Week 10 — Repair Intelligence

## Goal

Make repairs respond to specific creative defects rather than only proxy metrics.

## Tasks

- define repair taxonomy;
- attribute defects to beat IDs;
- preserve natural-language evidence;
- define repair recipes by defect type;
- compare before/after scores;
- retain two-round cap;
- distinguish re-authoring from mechanical repair.

## Deliverables

- repair taxonomy;
- repair decision schema;
- before/after evidence;
- failed-repair examples;
- human-escalation criteria.

## Exit criteria

- repairs name the defect and affected beat;
- repeated failed repair quarantines;
- a weak premise is escalated for re-authoring rather than patched forever;
- score changes are recorded.

---

# Week 11 — Multi-Story Proof

## Goal

Demonstrate that the system generalizes beyond one flagship.

## Tasks

- create story-status manifest;
- complete `kola-deepest-hole` pro story;
- re-author `sitting-still-speed`;
- re-author `hurricane-engine`;
- choose three structurally different candidates;
- run complete pipeline for all three;
- compare visual grammar and performance.

## Deliverables

- catalog status file;
- three full packages;
- three judge verdicts;
- three facts reports;
- comparative performance report;
- generalization review.

## Exit criteria

- at least three stories pass;
- each scores at least 7.5/10;
- each uses meaningfully different visual grammar;
- scheduler selects only production candidates.

---

# Week 12 — Controlled Canary and Operating Review

## Goal

Validate the exact upload path without enabling broad autonomous publishing.

## Tasks

- select one approved manifest;
- verify channel identity;
- verify title, description, chapters, captions, and thumbnail;
- enable publishing for one exact artifact;
- upload one video;
- verify public watch page;
- freeze publishing immediately afterward;
- conduct a twelve-week retrospective.

## Deliverables

- canary approval record;
- uploaded artifact hash;
- public verification checklist;
- post-canary incident review;
- next-quarter roadmap.

## Exit criteria

- one exact reviewed artifact publishes successfully;
- no second upload occurs;
- public artifact matches approved manifest;
- publishing is disabled again;
- unresolved risks are documented.

---

# Program Scoreboard

Track weekly:

- open blocking defects;
- implementation PRs merged;
- negative controls passing;
- artifacts generated;
- average review score;
- render time by profile;
- cache hit rate;
- number of production candidates;
- number of quarantines and reasons;
- publishing state;
- known factual gaps;
- known media-relevance defects.

---

# Stop Conditions

Pause the program and investigate when:

- fail-closed behavior is weakened;
- a report is accepted without matching artifact identity;
- visual scores decline for two consecutive candidate stories;
- facts regress;
- a pipeline change causes silent fallback;
- branch scope becomes mixed and unreviewable;
- publishing becomes enabled outside explicit canary control;
- multiple stories fail for the same systemic reason.

---

# 90-Day Outcome

At the end of twelve weeks, the expected result is not a fully autonomous content factory.

The expected result is a controlled, evidence-driven creative system that can:

- produce multiple strong videos;
- verify factual claims;
- judge exact artifacts;
- repair efficiently;
- avoid obvious media mistakes;
- publish one approved artifact safely;
- provide a trustworthy base for later automation and learning.
