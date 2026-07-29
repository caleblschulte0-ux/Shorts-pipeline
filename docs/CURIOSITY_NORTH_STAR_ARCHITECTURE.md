# Curiosity North-Star Architecture

> Documentation only. This document does not change production behavior.

## Purpose

The recovered curiosity pipeline now has the beginnings of a reliable production system. The next step is to define the mature architecture before more implementation work accumulates in disconnected modules.

The system should evolve from a renderer with gates into a **creative operating system** with explicit responsibility boundaries.

The north-star architecture is:

```text
editorial strategy
→ research and evidence
→ story design
→ visual planning
→ asset selection
→ rendering
→ repair
→ independent judgment
→ packaging
→ controlled release
→ audience learning
→ doctrine updates
```

Each stage must produce machine-readable evidence and must be independently inspectable.

---

# 1. System Principles

## 1.1 Fail closed at irreversible boundaries

Failures during ideation may produce retries.

Failures near publishing must produce quarantine.

The closer a stage is to publishing, the stricter its behavior should become.

## 1.2 Separate creation from judgment

The component that generates a scene should not be the final authority on whether that scene is good.

The component that writes the story should not be the only component deciding whether its claims are supported.

## 1.3 Bind evidence to exact artifacts

Every report should identify:

- story version;
- source registry version;
- media assets;
- renderer version;
- video hash;
- judge version;
- decision timestamp.

## 1.4 Prefer explicit state over inferred state

Do not infer readiness from the existence of an MP4.

Use explicit lifecycle states:

```text
idea
researching
fact_checked
authoring
renderable
reviewing
needs_repair
quarantined
production_candidate
approved
published
retired
```

## 1.5 Optimize for reusable quality, not one-off heroics

A system is not mature because one video succeeds after extensive manual intervention.

It is mature when three or more structurally different stories can pass using the same contracts.

---

# 2. Layered Architecture

## Layer A — Editorial Portfolio

Responsibilities:

- define channel identity;
- select themes;
- maintain a balanced story portfolio;
- avoid repeated premises;
- define why a story deserves to exist;
- decide which stories are worth expensive production.

Required outputs:

```json
{
  "story_id": "...",
  "premise": "...",
  "viewer_question": "...",
  "promised_payoff": "...",
  "why_now": "...",
  "novelty_against_catalog": "...",
  "status": "researching"
}
```

Key gate:

A story should not enter research merely because it is possible to render.

It should enter research because it has a compelling viewer question and a concrete payoff.

## Layer B — Research and Claim Registry

Responsibilities:

- gather primary and high-quality secondary sources;
- extract claims;
- record dates, geography, population, assumptions, and uncertainty;
- distinguish observed facts from derived models;
- identify disputed claims;
- map claims to story beats.

Required outputs:

- claim registry;
- source registry;
- research memo;
- uncertainty notes;
- freshness status.

Key gate:

No factual story proceeds without a complete factual mode and claim map.

## Layer C — Story Architecture

Responsibilities:

- transform research into a narrative sequence;
- define hook, escalation, mechanism, consequence, and payoff;
- control information density;
- create beat-level purpose;
- define emotional progression;
- define chapter rhythm.

Each beat should contain:

```json
{
  "beat_id": "...",
  "purpose": "mechanism",
  "narration": "...",
  "viewer_state_before": "confused",
  "viewer_state_after": "understands cause",
  "claim_ids": ["..."],
  "visual_job": "show pressure difference causing motion",
  "duration_target": 8.0
}
```

Key gate:

Every beat must either advance understanding, emotion, scale, consequence, or payoff.

## Layer D — Visual Strategy

Responsibilities:

- choose the visual family for each beat;
- define transitions;
- maintain visual contrast;
- prevent card-reel behavior;
- define character use;
- define evidence presentation;
- plan visual escalation.

Approved visual families may include:

- mechanism animation;
- spatial comparison;
- character consequence;
- real media;
- evidence card;
- object metaphor;
- map or geography;
- timeline;
- environment transformation;
- scale reveal;
- kinetic typography used sparingly.

Key gate:

No three consecutive beats should use the same visual family without an explicit reason.

## Layer E — Asset Intelligence

Responsibilities:

- retrieve multiple candidates;
- classify geography, era, language, currency, action, and subject;
- score relevance and composition;
- enforce licensing rules;
- reject duplicate or misleading assets;
- maintain provenance.

Required outputs:

- candidate ledger;
- selected asset record;
- rejected candidate reasons;
- license record;
- media hash.

Key gate:

A visually attractive but contextually wrong asset must lose to a less glamorous but accurate asset.

## Layer F — Rendering Engine

Responsibilities:

- render deterministic shot outputs;
- support draft, review, and production profiles;
- produce per-shot metadata;
- support cache reuse;
- preserve exact timing;
- produce complete sidecars.

Required outputs:

- shot segments;
- assembled video;
- captions;
- thumbnail;
- metadata;
- performance report;
- package manifest.

Key gate:

A render process must never silently replace an intended visual with an unlogged fallback.

## Layer G — Director and Repair

Responsibilities:

- detect stale spans;
- detect visual-family repetition;
- detect weak hooks;
- detect poor beat attribution;
- detect media mismatch;
- detect information overload;
- propose defect-specific repairs;
- cap automated repair rounds.

Required outputs:

- defect list;
- beat attribution;
- repair plan;
- before/after evidence;
- unresolved defects.

Key gate:

After two failed repair rounds, quarantine instead of continuing indefinitely.

## Layer H — Independent Judgment

Responsibilities:

- judge the exact finished artifact;
- evaluate technical quality;
- evaluate editorial taste;
- evaluate visual relevance;
- evaluate hook and payoff;
- identify reject labels;
- produce a hash-bound verdict.

Judges should be separated into:

1. technical visual judge;
2. editorial taste judge;
3. factual/provenance judge;
4. package integrity judge.

Key gate:

No single judge should be able to approve a video when another mandatory judge fails.

## Layer I — Release Control

Responsibilities:

- verify exact artifact identity;
- verify expected channel;
- verify publishing status;
- verify title, description, chapters, captions, and thumbnail;
- enforce one-video canaries;
- maintain rollback and freeze controls.

Key gate:

Publishing authorization should approve a specific manifest, not merely a slug.

## Layer J — Learning System

Responsibilities:

- connect audience behavior to story and shot metadata;
- distinguish signal from noise;
- run controlled experiments;
- update quality memory;
- prevent overfitting;
- track cross-video repetition;
- recommend doctrine changes.

Key gate:

No doctrine change should be accepted from one video or one weakly observed correlation.

---

# 3. Core Data Contracts

## 3.1 Story contract

Must identify:

- story ID;
- factual mode;
- premise;
- hook;
- payoff;
- beat IDs;
- claim IDs;
- visual jobs;
- intended emotional arc;
- status.

## 3.2 Asset contract

Must identify:

- source;
- query;
- license;
- media hash;
- geography;
- era;
- visible text;
- selected and rejected reasons.

## 3.3 Render contract

Must identify:

- renderer commit;
- profile;
- scene parameters;
- input hashes;
- output hashes;
- cache status;
- fallback status;
- timing.

## 3.4 Verdict contract

Must identify:

- exact video hash;
- story hash;
- judge version;
- evidence package hash;
- score dimensions;
- reject labels;
- required repairs;
- pass or quarantine.

## 3.5 Release contract

Must identify:

- approved manifest hash;
- destination channel;
- visibility;
- schedule;
- uploader identity;
- post-upload verification;
- rollback state.

---

# 4. Target Quality Characteristics

The mature system should produce videos that are:

- factually defensible;
- visually specific;
- narratively coherent;
- emotionally legible;
- mechanically varied;
- efficient to revise;
- honest about degradation;
- independently judged;
- safe to publish;
- capable of learning without losing identity.

The system should not merely avoid bad output.

It should create a repeatable path toward excellent output.

---

# 5. Maturity Levels

## Level 0 — Renderable

A video file can be produced.

## Level 1 — Safe

Bad or incomplete output is quarantined.

## Level 2 — Reviewable

Every decision has inspectable evidence.

## Level 3 — Repeatable

Multiple stories pass through the same contracts.

## Level 4 — Efficient

Repairs and rerenders are selective and fast.

## Level 5 — Distinctive

The channel has recognizable quality and avoids formulaic repetition.

## Level 6 — Learning

The system improves from controlled evidence without destabilizing itself.

PR #172 primarily moves the system from Level 0 toward Levels 1 and 2.

The next program should target Levels 3 through 6 in order.

---

# 6. Final North-Star Test

The architecture is working when the following statement is true:

> A new factual curiosity story can enter as a researched premise, become a visually intentional film, survive independent artifact-bound judgment, receive targeted repairs without a full rebuild, publish only after explicit exact-artifact approval, and contribute trustworthy evidence to future decisions.

Until that is repeatable across multiple story types, the system is still in development.
