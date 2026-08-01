# Claude Continuation Playbook — Curiosity Pipeline

## Purpose

This document is a documentation-only handoff. It changes no runtime behavior.

Start from PR #172 at commit `f6419ad574e140bcdd0a052f89b89304b3503e44`.

PR #172 completed the recovery scope:

- recovered the pro curiosity renderer onto a branch with a normal merge base;
- made the pro producer the canonical curiosity path;
- made legacy rendering explicit-only;
- froze publishing by default;
- added layered CI, performance instrumentation, expression tests, factual checks, fail-closed visual judgment, and a full `money-goes` canary;
- demonstrated stable memory and no unreaped subprocesses;
- produced a dry-run package that was publish-eligible but held.

The recovery is real. The next phase is not another recovery. It is a quality, integrity, autonomy, speed, and catalog-readiness phase.

Do not merely report this document back. Execute the work in focused PRs and prove each claim.

---

# 1. Non-negotiable rules

1. Preserve fail-closed behavior.
2. Do not enable scheduled publishing during this work.
3. Do not weaken gates to make stories pass.
4. Do not replace unavailable visuals with generic cards unless the fallback is explicitly classified and approved.
5. Do not use file modification time as final artifact identity.
6. Do not create another giant mixed PR.
7. Do not claim production readiness from one passing story.
8. Do not commit rendered MP4 files to Git.
9. Keep all implementation branches based on current `main` or on a clearly documented stacked-PR base.
10. Every completion claim must point to tests, workflow runs, reports, and rendered evidence.

---

# 2. Exact stopping point

The recovered system currently has these strengths:

- `scripts/post_curiosity.py` defaults to `CURIOSITY_RENDERER=pro`;
- missing pro stories quarantine rather than silently using legacy;
- `scripts/produce.py` is the canonical producer;
- director, fallback, sidecar, facts, and vision failures quarantine;
- stale visual verdicts are rejected using mtime;
- `money-goes` completed a full canary;
- CI and expression workflows passed;
- measured performance did not show progressive degradation;
- publishing remains frozen unless explicitly enabled.

Known remaining weaknesses from the final report:

- `money-goes` was judged about 6/10 overall and personality 3/5;
- repeated dark-starfield chapter cards reduce variety;
- a Japanese gas-station image is contextually wrong for the transport beat;
- one photo beat degraded to a statement card;
- three real-media beats occur consecutively;
- the hook dropped from 8/10 to 7/10 after a resize change;
- provenance is opt-in through `require_provenance`;
- factual detection is primarily numeric-pattern based;
- verdict freshness is based on mtime rather than content hashes;
- the blind visual verdict still requires an external agent to write the file;
- a full render takes roughly 31.8 minutes for roughly 4 minutes of video;
- `kola-deepest-hole` has no pro story;
- `sitting-still-speed` and `hurricane-engine` remain quarantined;
- only one flagship has passed end to end;
- cross-video repetition and learning remain incomplete.

---

# 3. Required PR sequence

## PR 1 — Merge safety and current-main reconciliation

### Work

- Update the recovery integration work against the latest `main`.
- Resolve conflicts without restoring unrelated or rejected work.
- Rerun all CI on the exact proposed merge SHA.
- Audit workflow permissions and secret exposure.
- Prove that cron, `--force`, auto-merge, and default environment values cannot enable publishing.
- Preserve `CURIOSITY_RENDERER=legacy` as explicit emergency mode only.

### Required tests

- routing tests;
- producer-evaluation tests;
- workflow validation;
- scheduled-run HOLD test;
- `--force` non-bypass test;
- missing-story fail-closed test;
- wrong-channel guard test where safely mockable.

### Done when

- exact merge SHA is green;
- publishing remains frozen;
- current `main` is incorporated;
- no quality gate can be bypassed by ordinary CLI flags.

---

## PR 2 — Cryptographic artifact manifest

### Problem

Current verdict freshness uses modification time. Modification time is not reliable artifact identity.

### Work

Generate `output/<slug>_pkg/manifest.json` containing at least:

```json
{
  "slug": "money-goes",
  "video_sha256": "...",
  "story_sha256": "...",
  "facts_sha256": "...",
  "captions_sha256": "...",
  "thumbnail_sha256": "...",
  "renderer_commit": "...",
  "producer_version": "...",
  "render_profile": "production",
  "generated_at": "..."
}
```

Bind these reports to the manifest hash and video hash:

- visual verdict;
- facts report;
- fallback report;
- performance report;
- technical gate report;
- editorial verdict;
- publishing approval.

Update `produce.evaluate()` to recalculate and compare hashes.

### Negative controls

- replace MP4 after judgment;
- copy an old verdict to a new package;
- alter story JSON after rendering;
- alter facts JSON after facts evaluation;
- replace thumbnail;
- alter captions.

Every control must quarantine.

### Done when

No approval relies solely on timestamps and every report can be proven to belong to the exact rendered package.

---

## PR 3 — Mandatory factual modes and semantic claim coverage

### Problem

Provenance currently depends on an opt-in flag and numeric-pattern detection.

### Work

Require every story to declare one factual mode:

- `verified`;
- `illustrative_model`;
- `historical_reconstruction`;
- `fictional`;
- `pure_visualization`.

Missing mode must quarantine.

For factual modes, require structured claims tied to beat IDs. Expand detection beyond numbers to cover:

- superlatives;
- rankings;
- comparisons;
- dates;
- ratios and percentages;
- causal claims;
- geographic claims;
- scientific and health claims;
- historical claims;
- named institutions;
- phrases such as “most,” “largest,” “fastest,” “more likely,” and “experts say.”

Modeled values must include inputs, assumptions, calculation, uncertainty, and explicit presentation language.

### Negative controls

- remove factual mode;
- make a superlative claim without a claim record;
- make a geographic claim with no geography;
- present a modeled number as universal fact;
- cite “studies” or “research” without a concrete source;
- reuse a claim on an unrelated beat.

### Done when

Deleting the old opt-in flag cannot make an unsourced factual story pass.

---

## PR 4 — Autonomous hash-bound visual review

### Problem

The producer safely quarantines without a verdict, but a separate agent still has to create `verdict.json`.

### Work

Generate a formal evidence package automatically:

- `contact_sheet.png`;
- `opening_10s.mp4`;
- payoff clip;
- chapter-transition reel;
- three sampled motion clips;
- thumbnail;
- transcript;
- beat map;
- package manifest.

Use two review roles:

1. Technical visual reviewer: clipping, unreadable text, broken motion, missing media, subtitle failures, mismatches, frozen frames, repeated templates, wrong aspect ratio.
2. Editorial taste reviewer: hook, curiosity, personality, specificity, pacing, progression, payoff, memorability, genericness, willingness to keep watching.

The judge must not receive implementation intent, code, previous verdicts, repair history, or developer justification.

Suggested policy:

- score at least 7.5: pass;
- score 6.5–7.4: second judge;
- below 6.5: reject;
- material disagreement: quarantine.

Record judge model/version and bind the verdict to the manifest SHA and video SHA.

### Done when

A headless run can finish with a schema-valid PASS or REJECT without manually editing a verdict file.

---

## PR 5 — Draft, review, and production profiles plus shot cache

### Problem

A roughly four-minute production render takes about 31.8 minutes, and small repairs can require expensive rerenders.

### Work

Add profiles:

- `draft`: fast planning and repair preview;
- `review`: judge-compatible timing and visuals;
- `production`: final upload quality.

Create deterministic shot cache keys from:

- scene kind;
- scene parameters;
- narration timing;
- media hashes;
- character state;
- renderer version;
- render profile;
- resolution and frame rate.

On one-beat repair, rerender only the changed beat and dependent transitions, then reassemble.

Report:

- cache hit rate;
- cached seconds reused;
- shots reused;
- shots rerendered;
- assembly time;
- media lookup time;
- judge-package creation time.

Initial targets:

- draft under 5 minutes;
- review under 10 minutes;
- production under 20 minutes;
- single-beat repair under 2 minutes.

Targets may be revised only with measured justification.

### Done when

Changing one beat no longer causes an unnecessary full-film rerender.

---

## PR 6 — `money-goes` visual-quality uplift

### Required repairs

- Replace the Japanese gas-station image with geographically appropriate or neutral media.
- Replace the degraded “hands counting bills” statement-card fallback with stronger footage, a licensed still, a designed mechanism, or a character interaction.
- Create at least three chapter-transition families instead of repeating the dark-starfield template.
- Compare the earlier 8/10 hook with the current 7/10 hook and restore the useful composition, scale, contrast, readability, or motion.
- Break the run of three consecutive real-media beats with a meaningful mechanism, character consequence, or evidence transformation.
- Raise character personality with clearer emotional progression and more specific setup/action/payoff behavior.

### Acceptance floor

- blind overall score at least 7.5/10;
- personality at least 4/5;
- no reject labels;
- no known media-relevance error;
- no degraded fallback in the opening 30 seconds;
- no single chapter-card family dominating the film.

Do not lower judge thresholds to reach these values.

---

## PR 7 — Comparative media retrieval and ranking

### Work

For important beats, retrieve several candidates where provider availability permits. Save candidate metadata and rejection reasons.

Rank on:

- semantic relevance;
- geography;
- historical era;
- visible action;
- subject identity;
- composition and overlay room;
- resolution;
- continuity;
- license quality;
- duplicate use;
- brand risk;
- signage and text risk.

Automatically penalize or reject:

- unexpected foreign signage;
- wrong currency;
- wrong era;
- missing required subject;
- text-dominated media;
- duplicate recent assets;
- dominant branding;
- geography conflicting with the narration.

Create a candidate contact sheet and run a vision-based semantic check before final selection.

### Done when

Every important selected asset can be traced to its query, candidate set, score, and rejection history.

---

## PR 8 — Defect-specific repair system

### Work

Expand repair beyond stale-span and card-budget metrics.

Support defect classes:

- weak hook;
- media relevance;
- visual repetition;
- emotional flatness;
- information overload;
- narration/visual mismatch;
- weak payoff;
- chapter-template repetition;
- continuity and direction errors.

Each repair record must include:

- beat ID;
- defect type;
- evidence;
- chosen repair;
- before asset or frame;
- after asset or frame;
- resulting score change.

Keep a maximum of two automated repair rounds. Then quarantine for re-authoring.

### Done when

Repair decisions explain the visual defect rather than merely reporting a proxy metric.

---

## PR 9 — Story catalog status and three-story proof

### Work

Add a story-status manifest with states such as:

- idea;
- researching;
- authoring;
- renderable;
- needs_rewrite;
- quarantined;
- production_candidate;
- published;
- retired.

The scheduler may select only `production_candidate` stories.

Complete or re-author:

- `kola-deepest-hole`;
- `sitting-still-speed`;
- `hurricane-engine`.

They must use meaningfully different visual grammars and subject matter.

### Acceptance floor

At least three different stories must each have:

- valid factual package;
- full render;
- hash-bound manifest;
- visual verdict;
- fallback report;
- performance report;
- publishing package;
- overall score at least 7.5/10.

### Done when

Production readiness is demonstrated across three stories, not inferred from `money-goes` alone.

---

## PR 10 — Cross-video repetition control

### Work

Track across a rolling window of at least ten videos:

- hook type;
- opening composition;
- transition family;
- character actions;
- visual metaphors;
- chart types;
- media sources;
- closing structure;
- music profile;
- color treatment;
- camera direction;
- fallback use.

Feed recent-history context into planning before render.

Suggested soft limits:

- same hook type no more than twice in five videos;
- same transition family no more than three times in one video;
- same character action no more than twice in one story;
- same closing pattern no more than twice in five videos;
- no accidental stock-asset reuse.

Document deliberate exceptions.

---

## PR 11 — Public canary and controlled rollout

### Preconditions

Do not run a public canary until:

- integration is merged and green on the exact SHA;
- artifact hashing is active;
- headless visual judgment works;
- `money-goes` or another candidate scores at least 7.5;
- known relevance defects are gone;
- expected-channel guard passes;
- publishing remains disabled by default.

### Canary

- render production artifact;
- generate manifest;
- run all gates;
- verify title, description, chapters, captions, thumbnail, channel, and video hash;
- explicitly enable publishing for one artifact only;
- upload one video;
- verify the public watch page;
- immediately disable publishing again.

### Then

Run at least three scheduled HOLD simulations before considering approval-required or limited autonomous publishing.

Automatic freeze conditions must include:

- artifact mismatch;
- wrong channel;
- invalid or missing verdict;
- factual failure;
- systemic media failure;
- performance budget violation;
- consecutive quarantines;
- upload verification failure.

---

## PR 12 — Controlled learning loop

Only begin after the system is stable across multiple stories.

Store shot-level metadata and connect it to retention, rewatch, click-through rate, comments, shares, likes, and subscriber gain where available.

Use one major experiment per video. Do not rewrite doctrine from a single result. Require repeated evidence, enough views, meaningful effect size, and comparable context.

Never optimize solely for upload volume, low cost, retention, or click-through rate. Preserve factual reliability, originality, shares, comments, subscriber conversion, and viewer satisfaction as independent objectives.

---

# 4. Global definition of done

Do not say the continuation is complete until all are true:

## Repository

- focused PRs;
- exact merge SHAs green;
- current `main` incorporated;
- publishing frozen by default.

## Integrity

- all important reports are cryptographically bound to the exact package;
- old verdicts cannot approve new renders;
- tampering quarantines.

## Facts

- factual mode is mandatory;
- nonnumeric claims receive coverage;
- modeled and reconstructed claims are labeled honestly;
- negative controls fail.

## Judgment

- headless technical and editorial review works;
- borderline policy and disagreement quarantine work;
- verdicts are schema-valid and hash-bound.

## Performance

- render profiles exist;
- shot caching exists;
- selective rerender works;
- performance targets are measured.

## Quality

- flagship is at least 7.5/10 and personality at least 4/5;
- no known wrong-region asset;
- chapter visuals vary;
- important media is comparatively ranked.

## Catalog

- three distinct stories pass the complete pipeline;
- scheduler selects only production candidates;
- weak stories remain quarantined rather than weakening gates.

## Publishing

- one exact reviewed artifact completes a successful public canary;
- publishing is refrozen afterward;
- three scheduled HOLD simulations pass before autonomous rollout.

## Learning

- shot metadata maps to audience results;
- experiments are controlled;
- quality standards remain independent of growth metrics.

---

# 5. Required final report

When finished, report:

## A. Repository state

- main SHA;
- merged PRs;
- open PRs;
- exact tested SHA.

## B. Integrity

- manifest fields;
- report bindings;
- negative-control results.

## C. Facts

- factual modes;
- semantic claim coverage;
- story registries;
- negative controls.

## D. Visual judgment

- judge package;
- judge versions;
- threshold policy;
- disagreement policy;
- headless result.

## E. Performance

- draft time;
- review time;
- production time;
- cache hit rate;
- one-beat repair time;
- peak RSS;
- child-process count.

## F. Visual quality

- overall score;
- personality;
- hook;
- reject labels;
- remaining visible defects.

## G. Catalog

- production candidates;
- quarantined stories;
- complete results for at least three stories.

## H. Public canary

- approved manifest SHA;
- uploaded video;
- channel verification;
- captions, chapters, and thumbnail verification;
- proof publishing was disabled again.

## I. Remaining work

Separate blocking, non-blocking, and future-enhancement items.

## J. Confidence

Provide evidence-backed percentages for implementation correctness, artifact integrity, factual reliability, visual quality, performance stability, autonomous judging, and unattended publishing safety.

---

# Final instruction

The recovery phase established that the system can render, evaluate, quarantine, and hold a curiosity video safely.

The continuation phase must establish that it can repeatedly create several accurate, distinctive, high-quality videos; bind every decision to the exact artifacts; judge them autonomously; repair them efficiently; publish only approved packages; and learn from real results without lowering standards.

Execute the PR sequence. Do not weaken the recovered safety model. Do not substitute documentation for implementation. Return only after the evidence exists.