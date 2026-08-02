# Claude Next-Level System Architecture

> **REVIEW-ONLY MATERIAL — NO RUNTIME EFFECT**
>
> This document lives only on `agent/claude-roadmap-review`. It does not change,
> import, invoke, configure, or replace any production pipeline component. Claude
> should review it, reconcile it with the live interfaces, and adopt ideas through
> separate implementation commits with full-render evidence.

## Objective

Move the explainer system from a collection of renderer improvements into an
observable, transactional, learning production system that can demonstrate:

- repeated full-suite quality gains;
- genuine rollback when repairs regress;
- structured diagnosis rather than prose parsing;
- semantic scene selection rather than chart-shape roulette;
- independent objective, vision, and adversarial judging;
- controlled diversity rather than one mascot gag repeated everywhere;
- promotion based on complete artifacts, not remembered scores;
- reproducible evidence for every quality claim;
- a stable path from phase 1 to consistent 90+ performance.

The system should be designed around one principle:

> **Nothing becomes canonical because code ran. It becomes canonical because a
> complete, reproducible candidate beat the incumbent under unchanged gates.**

---

# 1. System Planes

The target architecture has nine separate planes. Keeping them separate prevents
one subsystem from grading its own homework.

## 1.1 Story-intent plane

Produces a machine-readable description of what the scene must communicate.

Minimum contract:

```json
{
  "claim": "Coal remains the largest source in this comparison.",
  "data_shape": "part_to_whole",
  "relationship": "dominance",
  "direction": "stable_high",
  "viewer_question": "How dominant is it?",
  "emotional_read": "overwhelming",
  "required_takeaway": "One category outweighs the rest combined.",
  "forbidden_distortions": [
    "implying a time trend",
    "changing category order",
    "hiding the denominator"
  ]
}
```

This contract must exist before choosing a chart or mascot action.

## 1.2 Candidate-compiler plane

Transforms story intent into several structurally different candidate plans.

A candidate includes:

- visualization grammar;
- mascot performance family;
- attachment requirements;
- timeline phases;
- camera purpose;
- caption ownership;
- payoff mechanism;
- semantic compatibility explanation;
- expected failure risks.

A candidate is not allowed into rendering unless it passes semantic validation.

## 1.3 Render plane

Renders candidates in isolated attempt directories. It must not write directly to
canonical outputs or shared scene-plan state.

Each attempt owns:

```text
attempt_N/
  manifest.json
  scene_plan.json
  scene.mp4
  full_video.mp4
  objective_metrics.json
  vision_verdict.json
  adversarial_verdict.json
  combined_verdict.json
  provenance.json
```

## 1.4 Objective-evidence plane

Measures what code can verify reliably:

- actual frame rate;
- effective frame rate;
- duplicate runs;
- static holds;
- clipping;
- text overflow;
- safe-area violations;
- attachment metadata continuity;
- audio presence;
- render completeness;
- source and plan hashes.

Objective evidence may reject a candidate. It may not declare it entertaining.

## 1.5 Vision-taste plane

Reviews actual rendered pixels and motion. It evaluates:

- whether contact looks real;
- whether cause and consequence read clearly;
- whether the action supports the claim;
- whether the scene is understandable without reading implementation metadata;
- whether composition and pacing work;
- whether the mascot contributes rather than distracts;
- whether the ending lands.

## 1.6 Adversarial plane

Attempts to prove that a candidate is gaming known checks.

Questions include:

- Is motion present but meaningless?
- Are start/middle/end technically different without a coherent action?
- Does the mascot touch the chart but add no explanation?
- Is the scene full only because elements are oversized?
- Is the payoff merely the final chart with a reaction pose?
- Does a repeated primitive make the suite feel templated?

A candidate with a strong normal verdict but a credible adversarial objection is
held for review or repaired.

## 1.7 Transaction plane

Compares complete attempts and promotes exactly one immutable winner.

Promotion must include the entire reproducible state:

- video;
- scene plan;
- verdicts;
- metrics;
- source hashes;
- generation configuration;
- candidate lineage.

If a repair loses, its plan must never remain active accidentally.

## 1.8 Benchmark plane

Runs a fixed, versioned suite of complete stories. The benchmark plane owns:

- suite version;
- judge version;
- story fixtures;
- two-run consistency requirements;
- phase gates;
- regression thresholds;
- artifact retention;
- score and failure history.

A renderer change is evaluated against the suite, not one favored story.

## 1.9 Learning-memory plane

Stores high-performing structures and rejected patterns.

It should learn abstractions such as:

- “resisted growth with reversal”;
- “balance metaphor for competing shares”;
- “scale reveal through camera retreat”;
- “failed carry action for overload.”

It must not blindly clone exact layouts, copy captions, or overuse one primitive.

---

# 2. Required Contracts

## 2.1 Structured weakest-scene verdict

Every blocked full video should identify one primary repair target:

```json
{
  "scene_id": "segment_1",
  "scene_index": 1,
  "start_seconds": 7.2,
  "end_seconds": 12.8,
  "failure_class": "decorative_mascot",
  "visible_evidence": "The mascot tracks the bar edge without a readable goal.",
  "root_cause": "Position following was mistaken for performance.",
  "repair_goal": "Create effort, reversal, and visible consequence while preserving the comparison."
}
```

Natural-language `segN` parsing should be removed from the normal path.

## 2.2 Candidate manifest

```json
{
  "candidate_id": "segment_1.balance_overload.v2",
  "story_intent_hash": "...",
  "visualization": "balance",
  "performance_family": "overwhelmed_balance",
  "supported_relationships": ["dominance", "imbalance"],
  "timeline_phases": [
    "setup",
    "commitment",
    "effort",
    "reversal",
    "consequence",
    "payoff",
    "recovery"
  ],
  "contact_requirements": ["left_hand_to_beam", "feet_to_platform"],
  "camera_purpose": "reveal how far the dominant side drops",
  "payoff": "mascot loses footing as the dominant side slams down",
  "risk_flags": ["caption_collision", "overly_comedic"]
}
```

## 2.3 Complete attempt manifest

```json
{
  "attempt_id": "run_20260725_001/attempt_2",
  "parent_attempt_id": "run_20260725_001/attempt_0",
  "story_slug": "world-power-mix",
  "candidate_ids": ["segment_1.balance_overload.v2"],
  "renderer_commit": "...",
  "suite_version": "explainer-v2",
  "judge_version": "taste-v4",
  "created_at": "...",
  "artifacts": {
    "video": {"path": "full_video.mp4", "sha256": "..."},
    "plan": {"path": "scene_plan.json", "sha256": "..."},
    "verdict": {"path": "combined_verdict.json", "sha256": "..."}
  }
}
```

## 2.4 Promotion decision

```json
{
  "incumbent": "attempt_0",
  "challenger": "attempt_2",
  "winner": "attempt_2",
  "decision_order": [
    "publishability",
    "hard_failures",
    "total_score",
    "lowest_dimension",
    "temporal_quality",
    "duplicate_ratio"
  ],
  "reason": "Both ship; challenger scores higher with no dimension regression.",
  "canonical_manifest_sha256": "..."
}
```

---

# 3. Multi-Judge Adjudication

No single judge should have unilateral positive authority.

## 3.1 Objective gate

The objective gate can return only:

- `reject`;
- `eligible_for_vision`.

It cannot return `ship`.

## 3.2 Primary vision judge

Scores the candidate using the unchanged creative rubric and supplies timestamped
evidence.

## 3.3 Adversarial vision judge

Looks specifically for rubric gaming, repetitive templates, semantic mismatch,
and technical checks that do not read visually.

## 3.4 Combined decision

Recommended logic:

1. Objective rejection always blocks.
2. Missing vision evidence blocks.
3. Primary score below phase floor blocks.
4. Any hard-failure label blocks.
5. A high-confidence adversarial objection blocks or requires human review.
6. Otherwise the candidate may challenge the incumbent.
7. Promotion still requires a complete full-video comparison.

Judge disagreement should be saved, not averaged away invisibly.

---

# 4. Diversity Control

A system can pass scene-level tests and still become boring at channel scale.

Track at least these windows:

- within one video;
- last six benchmark videos;
- last 20 produced videos;
- last 50 published videos.

Metrics:

- performance-family concentration;
- chart-grammar concentration;
- hook-mechanism concentration;
- ending-mechanism concentration;
- repeated camera move rate;
- repeated caption structure rate;
- semantic-to-performance diversity.

Initial constraints:

```text
No performance family in >50% of scenes within one video.
No performance family in >25% of benchmark scenes.
No hook mechanism in >33% of the six-story suite.
No identical chart+performance+payoff signature repeated in adjacent videos.
```

Diversity constraints should never force a semantically wrong choice. When no
valid diverse candidate exists, hold the story and generate better candidates.

---

# 5. Benchmark Laboratory

## 5.1 Suite structure

Use at least six fixed stories spanning:

- trend;
- ranking;
- part-to-whole;
- direct comparison;
- geographic or physical scale;
- money or cost transformation.

Each suite entry should declare:

- expected takeaway;
- forbidden distortions;
- minimum visual requirements;
- permitted chart grammars;
- known historical failures;
- reference score history.

## 5.2 Repeated runs

A phase is not passed by one batch.

Require two consecutive runs with:

- identical suite version;
- identical judge version;
- fixed narration and source data;
- no manual file edits between runs;
- artifact hashes retained;
- phase thresholds met in both runs.

## 5.3 Regression budget

A system-wide improvement must not hide severe local regressions.

Recommended constraints:

```text
Median improves or stays within 1 point.
Lowest story may not fall by more than 2 points.
No dimension may regress by more than 1 point on two or more stories.
No new hard-failure class may appear.
No temporal metric may cross a hard threshold.
```

---

# 6. Quality State Machine

The phase should be a calculated state, not an environment variable someone can
raise manually.

## Phase 0 — structural safety

- complete renders;
- no missing artifacts;
- no clipping or text overflow hard failures;
- deterministic attempt manifests.

## Phase 1 — stable 70s

- six complete stories;
- two consecutive runs;
- median at least 70;
- lowest score at least 65;
- no hard failures;
- effective FPS at least 24 in active scenes;
- transactional rollback verified.

## Phase 2 — stable 80s

- median at least 80;
- lowest score at least 75;
- hook and payoff dimensions meet floors;
- candidate vision ranking active;
- diversity constraints pass;
- no repeated decorative-mascot failures.

## Phase 3 — consistent 90s

- median at least 90;
- lowest score at least 85;
- zero hard failures;
- unchanged judge strictness;
- no random rerolls;
- two consecutive passing runs;
- all canonical outputs reproducible from manifests.

## Phase 4 — post-90 production intelligence

- shadow evaluation on unseen stories;
- drift detection;
- performance-family saturation alerts;
- holdout benchmark suite;
- automatic rollback after quality regression;
- exemplar retrieval with anti-copy checks;
- calibrated human-review sampling.

A failed new benchmark should lower the eligible production phase until the
regression is understood.

---

# 7. Post-90 Next Step

After the system reaches consistent 90s, do not simply increase complexity.
Build reliability around unseen stories.

## 7.1 Holdout suite

Maintain stories never used during renderer development. Run them only at phase
promotion points to detect benchmark overfitting.

## 7.2 Shadow production

For real incoming stories:

1. Produce the current canonical version.
2. Produce one experimental challenger in isolation.
3. Judge both blindly.
4. Never publish the challenger automatically during the shadow period.
5. Track whether experimental wins transfer beyond the benchmark suite.

## 7.3 Drift monitoring

Detect changes in:

- story-topic distribution;
- data-shape distribution;
- average narration length;
- source availability;
- judge-score distribution;
- mascot-family use;
- failure-class frequency.

## 7.4 Calibrated human sampling

Even with strong automated judges, periodically sample:

- high-confidence ships;
- close decisions;
- judge disagreements;
- new performance families;
- unseen story shapes.

The purpose is to audit the judge, not to replace structured automation.

---

# 8. Implementation Waves for Claude

## Wave A — transactional truth

1. Isolate attempts.
2. Hash all artifacts.
3. Promote complete states only.
4. Restore the incumbent after a losing repair.
5. Prove rollback with integration tests.

## Wave B — structured diagnosis

1. Emit exact scene IDs and timestamps.
2. Remove prose scene parsing.
3. Store scene-level verdicts.
4. Require visible evidence for every failure.

## Wave C — candidate intelligence

1. Add semantic story-intent contracts.
2. Generate structurally distinct candidates.
3. Reject incompatible chart/performance combinations.
4. Enforce timeline and attachment requirements.

## Wave D — independent judging

1. Separate objective and vision gates.
2. Add adversarial evaluation.
3. Preserve disagreements.
4. Compare complete full-video attempts.

## Wave E — benchmark discipline

1. Version the suite and judges.
2. Run complete videos twice.
3. Enforce regression budgets.
4. Calculate the quality phase from evidence.

## Wave F — channel-scale intelligence

1. Add diversity windows.
2. Build exemplar and rejection memory.
3. Add holdout stories.
4. Run shadow challengers.
5. Detect drift and auto-demote on regression.

---

# 9. Mandatory Report After Each Wave

```text
Completed:
Partially completed:
Not completed:
Existing runtime files changed:
New runtime wiring:
Tests run:
Complete renders run:
Suite and judge versions:
Before scores:
After scores:
Regressions:
Artifacts:
Known limitations:
Next bounded wave:
```

No wave is complete because classes or files exist. It is complete only after the
actual operational path and full-render evidence satisfy its acceptance criteria.
