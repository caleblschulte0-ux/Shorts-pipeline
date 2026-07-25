# Curiosity Experimentation and Learning System

> Documentation only. This file changes no runtime behavior.

## Purpose

The pipeline should eventually improve from real audience behavior, but it must not become a system that chases noisy metrics, copies accidental winners, or lowers factual and visual standards for short-term gains.

This document defines a controlled learning system.

---

# 1. Learning Principles

## 1.1 Quality gates remain independent

Audience performance cannot override:

- factual accuracy;
- artifact integrity;
- licensing;
- channel safety;
- visual relevance;
- required judge verdicts.

A popular but misleading video is still a failure.

## 1.2 One major experiment per video

A video may contain routine improvements, but only one major variable should be treated as the primary experiment.

Examples:

- hook structure;
- opening visual family;
- chapter rhythm;
- character presence;
- evidence-card frequency;
- payoff construction;
- narration density.

## 1.3 Pre-register hypotheses

Before publishing, record:

```json
{
  "experiment_id": "hook-contradiction-001",
  "hypothesis": "Showing the contradiction visually before explaining it will improve first-30-second retention.",
  "primary_metric": "retention_30s",
  "secondary_metrics": ["rewatch_rate", "shares_per_view"],
  "guardrails": ["factual_confidence", "visual_relevance", "comment_sentiment"],
  "comparison_set": ["video-a", "video-b"],
  "decision_rule": "repeat only after two directionally consistent results"
}
```

Do not invent the hypothesis after seeing the result.

## 1.4 Require repeated evidence

One successful video should create a candidate lesson, not a permanent rule.

Recommended promotion ladder:

```text
observation
→ candidate pattern
→ repeated pattern
→ controlled experiment
→ provisional rule
→ doctrine update
```

## 1.5 Preserve creative exploration

Not every video should be optimized around the current best-performing formula.

Reserve a percentage of output for exploration.

Suggested portfolio:

```text
60% proven structures
25% adjacent experiments
15% high-variance creative exploration
```

This ratio should be adjusted only after enough production history exists.

---

# 2. Measurement Layers

## 2.1 Video-level metadata

Track:

- story ID;
- premise type;
- factual mode;
- duration;
- hook type;
- chapter count;
- dominant visual families;
- personality score;
- overall judge score;
- fallback count;
- production cost;
- publication date.

## 2.2 Beat-level metadata

Track:

- beat ID;
- beat purpose;
- narration length;
- shot duration;
- visual family;
- text density;
- character presence;
- claim IDs;
- transition type;
- repair history.

## 2.3 Shot-level metadata

Track:

- shot ID;
- scene kind;
- media source;
- camera behavior;
- composition family;
- motion intensity;
- cache status;
- render cost;
- judge defects;
- fallback status.

## 2.4 Audience signals

Where available, track:

- impressions;
- click-through rate;
- average view duration;
- retention curve;
- first-30-second retention;
- chapter-level drop-off;
- rewatch behavior;
- likes per qualified view;
- comments per qualified view;
- shares per qualified view;
- subscriber conversion;
- returning viewers;
- negative feedback.

Use `qualified view` definitions consistently.

---

# 3. Metric Hierarchy

## Primary outcome metrics

- meaningful watch time;
- shares;
- subscriber conversion;
- returning viewers;
- viewer satisfaction.

## Diagnostic metrics

- click-through rate;
- first-30-second retention;
- chapter drop-off;
- rewatch peaks;
- comment topics;
- visual judge scores.

## Guardrail metrics

- factual corrections;
- misleading-comment rate;
- wrong-media incidents;
- visual-relevance score;
- quarantine rate;
- production cost;
- duplicate-format rate.

A change that improves a primary metric but violates a guardrail should not be promoted.

---

# 4. Experiment Types

## 4.1 Hook experiments

Variables:

- contradiction first;
- consequence first;
- visual scale first;
- question first;
- character reaction first;
- evidence first.

Guardrails:

- no misleading tease;
- payoff must match promise;
- factual framing must remain accurate.

## 4.2 Pacing experiments

Variables:

- shorter first chapter;
- fewer chapter cards;
- longer mechanism explanation;
- faster media cadence;
- delayed payoff reveal.

Guardrails:

- clarity score;
- information density;
- visual judge score.

## 4.3 Visual grammar experiments

Variables:

- more mechanism animation;
- more real-media contrast;
- stronger character anchoring;
- alternate chapter-transition families;
- object metaphors;
- continuous spatial journey.

Guardrails:

- visual relevance;
- originality;
- render cost;
- accessibility.

## 4.4 Personality experiments

Variables:

- stronger reactions;
- recurring visual motifs;
- controlled humor;
- narrator-character interaction;
- more expressive payoff.

Guardrails:

- factual tone;
- distraction;
- repetition across videos.

## 4.5 Packaging experiments

Variables:

- thumbnail framing;
- title specificity;
- chapter wording;
- description opening;
- source presentation.

Guardrails:

- title honesty;
- exact-video relevance;
- no misleading thumbnail.

---

# 5. Comparison Rules

## 5.1 Use comparable videos

Compare videos with similar:

- topic breadth;
- duration;
- audience size;
- publication timing;
- traffic source;
- channel maturity;
- factual complexity.

Do not compare a broad cultural topic directly with a niche technical topic and call the difference causal.

## 5.2 Minimum observation window

Do not make major decisions from the first few hours unless investigating a technical failure.

Use staged windows:

```text
24 hours — technical and packaging check
7 days — early audience behavior
28 days — durable catalog behavior
90 days — long-tail behavior
```

## 5.3 Effect size matters

A tiny metric increase may not justify added complexity or production cost.

Record:

- absolute difference;
- relative difference;
- uncertainty;
- sample size;
- cost increase;
- quality impact.

## 5.4 Negative results are valuable

Store failed experiments with:

- hypothesis;
- implementation;
- result;
- likely confounders;
- recommendation;
- whether the idea should be retried.

Do not quietly delete failed experiments.

---

# 6. Learning Memory

The quality memory should distinguish:

## Observations

Raw findings from individual videos.

## Patterns

Repeated observations across comparable cases.

## Rules

Operational guidance supported by repeated evidence.

## Doctrine

Stable principles that require stronger proof and formal review.

Example:

```json
{
  "type": "pattern",
  "statement": "Mechanism-first openings performed better than title-card openings in three comparable science videos.",
  "evidence": ["video-12", "video-17", "video-19"],
  "confidence": 0.74,
  "exceptions": ["historical mystery stories"],
  "status": "provisional"
}
```

---

# 7. Doctrine Change Process

A doctrine change proposal must include:

- current rule;
- proposed rule;
- supporting videos;
- counterexamples;
- estimated benefit;
- risks;
- implementation cost;
- rollback plan;
- expiration or review date.

Required review questions:

- Is the evidence causal or correlational?
- Could topic choice explain the result?
- Did packaging change simultaneously?
- Did audience composition change?
- Does the rule reduce originality?
- Does the rule create factual or quality risk?

---

# 8. Anti-Overfitting Controls

Do not:

- copy one viral video's structure across the whole catalog;
- optimize every opening to the same pattern;
- reduce story depth merely to increase early retention;
- remove difficult factual material to simplify production;
- reward misleading packaging;
- promote rules from small samples;
- hide failed experiments;
- change multiple major variables and attribute the result to one;
- optimize against judge scores until outputs become formulaic.

---

# 9. Experiment Review Template

```text
Experiment ID:
Video ID:
Hypothesis:
Primary variable:
Primary metric:
Guardrails:
Comparison set:
Observed result:
Confidence:
Confounders:
Creative impact:
Factual impact:
Cost impact:
Decision:
Next test:
```

Allowed decisions:

```text
reject
retry
continue gathering evidence
promote to provisional pattern
promote to rule proposal
```

---

# 10. Initial Experiment Backlog

Recommended early experiments after stable multi-story production:

1. contradiction-first hook versus explanation-first hook;
2. mechanism animation in first 20 seconds versus real media first;
3. three chapter-transition families versus one recurring family;
4. character-present mechanism explanation versus character-free explanation;
5. evidence card after visual demonstration versus before demonstration;
6. shorter first chapter with unchanged total depth;
7. payoff callback to exact opening image;
8. fewer but stronger real-media shots;
9. continuous visual journey versus modular chapter construction;
10. explicit uncertainty framing versus source-only framing.

---

# 11. Success Condition

The learning system is mature when it can make a recommendation like:

> In three comparable mechanism-driven videos, visually demonstrating the contradiction before naming it improved first-30-second retention and shares without reducing clarity, factual confidence, or originality. Test once more before promoting it to a general hook rule.

That is substantially stronger than:

> This video did well, so copy it.
