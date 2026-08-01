# Curiosity Quality Scorecard

> Documentation only. This file changes no runtime behavior.

## Purpose

The pipeline needs one shared definition of quality. Without a scorecard, each subsystem can claim success using its own local metric while the finished video remains merely acceptable.

This scorecard separates:

1. **hard gates** — any failure quarantines;
2. **quality dimensions** — scored for improvement and release thresholds;
3. **channel-level health** — measured across multiple videos;
4. **pipeline health** — measured independently of audience performance.

---

# 1. Hard Gates

A video cannot pass when any required item fails.

## 1.1 Artifact integrity

Required:

- valid manifest;
- exact video hash match;
- exact story hash match;
- facts report bound to the same manifest;
- visual verdict bound to the same manifest;
- required sidecars present;
- no stale verdict.

## 1.2 Factual integrity

Required for factual stories:

- declared factual mode;
- complete claim mapping;
- acceptable sources;
- uncertainty disclosed;
- derived values reproducible;
- no stale time-sensitive source;
- no unsupported factual narration.

## 1.3 Technical integrity

Required:

- valid playable video;
- correct dimensions;
- acceptable duration;
- audio present and intelligible;
- captions parse and align;
- no broken frames;
- no missing or corrupt media;
- no unreaped render processes;
- no unlogged unacceptable fallback.

## 1.4 Publishing integrity

Required:

- expected channel verified;
- exact approved manifest selected;
- title and description present;
- chapters valid when used;
- thumbnail valid;
- publish authorization explicit;
- no duplicate upload;
- publishing state recorded.

## 1.5 Independent judgment

Required:

- technical visual verdict;
- editorial taste verdict;
- no contradictory verdict state;
- no unresolved reject label;
- second review completed when borderline.

---

# 2. Video Quality Dimensions

Use a 1–10 scale for each dimension.

## 2.1 Premise Strength

Questions:

- Is there a clear viewer question?
- Does the story promise a specific payoff?
- Is the premise more interesting than a generic fact list?
- Does the viewer understand why the subject matters?

Scoring guide:

- 1–3: vague or disposable;
- 4–5: understandable but ordinary;
- 6–7: compelling and specific;
- 8–9: highly distinctive and naturally shareable;
- 10: exceptional premise with immediate cultural or emotional pull.

Minimum production candidate score: **7**.

## 2.2 Hook

Questions:

- Does the first eight seconds create a question or contradiction?
- Is the visual immediately legible?
- Is the payoff implied?
- Is unnecessary setup removed?

Minimum: **7**.

Target: **8+**.

## 2.3 Narrative Clarity

Questions:

- Does each beat logically follow the previous beat?
- Are causal relationships clear?
- Does the viewer know what changed and why?
- Is the conclusion earned?

Minimum: **7**.

## 2.4 Visual Relevance

Questions:

- Does every major visual support the narration?
- Are geography, era, language, currency, and subject correct?
- Are evidence visuals distinguishable from decorative visuals?
- Is stock media contextually appropriate?

Minimum: **8**.

A known wrong-region or wrong-era image is a hard defect even when the average score is high.

## 2.5 Visual Variety

Questions:

- Are visual families meaningfully varied?
- Are transitions repeated too often?
- Are consecutive shots compositionally distinct?
- Does variety serve understanding rather than random novelty?

Minimum: **7**.

## 2.6 Information Design

Questions:

- Is text readable?
- Are numbers introduced at a manageable pace?
- Are comparisons visually clear?
- Are cards used only when they are the strongest format?

Minimum: **7**.

## 2.7 Character and Personality

Questions:

- Does the visual system feel authored rather than generic?
- Do character reactions evolve?
- Is humor or personality specific to the story?
- Does the piece have a recognizable voice?

Minimum: **4/5** when using a five-point personality scale.

Equivalent ten-point minimum: **8**.

## 2.8 Pacing

Questions:

- Are there stale spans?
- Are transitions purposeful?
- Does visual activity match narration density?
- Are important moments given enough time?

Minimum: **7**.

## 2.9 Emotional Progression

Questions:

- Does the viewer's emotional state change?
- Is there surprise, tension, wonder, concern, relief, or humor?
- Does the ending feel larger than the opening?

Minimum: **6**.

Target: **7+**.

## 2.10 Payoff

Questions:

- Does the ending answer the opening question?
- Is the conclusion visually demonstrated?
- Does the final image feel memorable?
- Is there a reason to share or discuss the result?

Minimum: **7**.

## 2.11 Factual Confidence

Score based on:

- source quality;
- source freshness;
- claim coverage;
- uncertainty treatment;
- reproducibility of calculations;
- absence of misleading framing.

Minimum: **9** for verified factual stories.

## 2.12 Originality

Questions:

- Does the story use a fresh visual metaphor?
- Does it avoid repeating recent videos?
- Does it feel like this channel rather than a generic template?
- Is the structure tailored to the premise?

Minimum: **7**.

---

# 3. Weighted Overall Score

Recommended weighting:

```text
Premise strength       10%
Hook                   10%
Narrative clarity      10%
Visual relevance       15%
Visual variety          8%
Information design      8%
Personality              8%
Pacing                   8%
Emotional progression    5%
Payoff                  10%
Factual confidence       5%
Originality              3%
```

The weighting may evolve only after controlled review.

## Release thresholds

```text
Below 6.5     reject or re-author
6.5–7.4       borderline; second judge required
7.5–8.4       production candidate
8.5–9.2       strong flagship
Above 9.2     exceptional; verify judge calibration
```

No weighted average may override a hard-gate failure.

---

# 4. Defect Severity

## Critical

Examples:

- wrong channel;
- unsupported factual claim;
- artifact mismatch;
- corrupted output;
- contradictory approval;
- legal or licensing issue.

Result: immediate quarantine.

## High

Examples:

- wrong-region imagery;
- unreadable core evidence;
- missing payoff;
- severe visual mismatch;
- repeated fallback in opening section.

Result: repair required before approval.

## Medium

Examples:

- repeated chapter template;
- weak transition;
- minor pacing sag;
- generic supporting image;
- limited character variation.

Result: repair when score is below threshold or when clustered.

## Low

Examples:

- minor composition refinement;
- optional sound-design improvement;
- small stylistic inconsistency.

Result: track for future improvement.

---

# 5. Channel-Level Scorecard

Measure over rolling windows of 5, 10, and 20 videos.

## 5.1 Creative diversity

Track:

- hook types;
- chapter-transition families;
- visual metaphors;
- character actions;
- chart types;
- closing structures;
- media reuse;
- music profiles.

## 5.2 Accuracy

Track:

- factual corrections;
- source freshness failures;
- claim-coverage failures;
- disputed claims;
- post-publication corrections.

## 5.3 Audience quality

Track:

- qualified views;
- meaningful comments;
- shares;
- subscriber conversion;
- rewatch behavior;
- satisfaction signals;
- retention by chapter.

Do not treat raw views as the sole measure of quality.

## 5.4 Production reliability

Track:

- pass rate;
- quarantine rate;
- quarantine reasons;
- repair success rate;
- average repair rounds;
- media fallback rate;
- judge disagreement rate;
- upload verification failures.

---

# 6. Pipeline Health Scorecard

Measure independently from the creative score.

## Reliability

- deterministic tests passing;
- failure modes quarantined;
- no silent fallbacks;
- no process leaks;
- no report mismatch.

## Efficiency

- draft render time;
- review render time;
- production render time;
- cache hit rate;
- single-beat repair time;
- media retrieval latency;
- judge turnaround.

## Maintainability

- focused PR size;
- module ownership clarity;
- test coverage for contracts;
- number of orphaned modules;
- duplicated logic;
- documentation freshness.

## Operational safety

- publishing disabled by default;
- exact-manifest approval;
- channel guard success;
- rollback tested;
- incident freeze available;
- secret permissions minimized.

---

# 7. Scorecard Review Cadence

## Per render

- hard gates;
- quality score;
- defect list;
- required repairs.

## Per candidate story

- comparison against previous version;
- judge agreement;
- facts confidence;
- performance cost.

## Weekly

- pipeline reliability;
- open high-severity defects;
- catalog readiness;
- benchmark trends.

## Monthly

- channel creative diversity;
- audience learning;
- doctrine change proposals;
- judge calibration review;
- threshold review.

---

# 8. Anti-Gaming Rules

Do not improve the score by:

- removing difficult beats;
- shortening videos until the premise is underexplained;
- replacing visuals with cards merely because cards score reliably;
- writing narration to evade claim detection;
- selecting only easy stories;
- teaching judges the intended answer;
- excluding failed runs from reports;
- changing thresholds after seeing a result.

---

# 9. Production Candidate Contract

A story may be marked `production_candidate` only when:

- all hard gates pass;
- weighted score is at least 7.5;
- visual relevance is at least 8;
- factual confidence is at least 9 when factual;
- personality is at least 4/5;
- no unresolved critical or high defect remains;
- exact artifact identity is verified;
- the story is not excessively repetitive against the recent catalog.

This contract should remain stricter than the minimum technical ability to render.
