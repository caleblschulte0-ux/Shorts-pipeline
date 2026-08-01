# Curiosity Release Governance

> Documentation only. This file changes no runtime behavior.

## Purpose

A powerful production system needs operational discipline. The largest risks are not limited to broken code. They include weak review, accidental publishing, stale evidence, oversized PRs, unclear ownership, and silent quality regression.

This document defines how implementation work should move from idea to production.

---

# 1. Branch and PR Policy

## 1.1 Protected production base

Do not develop directly on `main`.

Every runtime change should begin from the current approved base and use a focused branch.

Recommended naming:

```text
feature/curiosity-<capability>
fix/curiosity-<defect>
perf/curiosity-<optimization>
docs/curiosity-<topic>
```

## 1.2 One dominant purpose

A PR should answer one primary question.

Good examples:

- Can verdicts be bound to exact artifacts?
- Can one beat be rerendered without rebuilding the full film?
- Can media selection reject wrong-region imagery?

Bad example:

- Improve renderer, rewrite three stories, change scheduling, add analytics, and refactor workflows.

## 1.3 Required PR sections

Every implementation PR should include:

```text
Problem
Root cause
Scope
Out of scope
Behavior before
Behavior after
Failure behavior
Evidence
Negative controls
Performance impact
Publishing impact
Rollback
Known limitations
```

## 1.4 Draft by default

Use draft PRs until:

- scope is stable;
- tests exist;
- artifacts exist;
- known failures are documented;
- publishing impact is understood.

---

# 2. Review Roles

A single reviewer may cover multiple roles, but the questions must remain separate.

## 2.1 Architecture reviewer

Checks:

- responsibility boundaries;
- duplicated logic;
- hidden coupling;
- migration behavior;
- long-term maintainability.

## 2.2 Safety reviewer

Checks:

- fail-closed behavior;
- publishing controls;
- secret exposure;
- channel guard;
- rollback;
- irreversible actions.

## 2.3 Factual reviewer

Checks:

- claim schema;
- source requirements;
- uncertainty;
- modeled values;
- stale-source behavior.

## 2.4 Visual-quality reviewer

Checks:

- evidence package;
- judge calibration;
- media relevance;
- repetition;
- actual rendered output.

## 2.5 Performance reviewer

Checks:

- benchmarks;
- resource usage;
- cache invalidation;
- process cleanup;
- cost regression.

---

# 3. Evidence Requirements

## 3.1 Code evidence

Required as applicable:

- unit tests;
- integration tests;
- contract tests;
- negative controls;
- static validation.

## 3.2 Artifact evidence

Required for visual or rendering work:

- before/after clips;
- contact sheets;
- manifests;
- performance reports;
- verdicts;
- fallback ledgers.

## 3.3 Operational evidence

Required for publishing or workflow work:

- dry-run output;
- exact environment state;
- channel verification;
- permission table;
- rollback rehearsal;
- demonstration that cron remains safe.

## 3.4 Claim discipline

Do not write:

> Production ready.

Write:

> Passed unit, smoke, and one controlled full-canary run on commit X; public upload path remains untested.

Claims should name the evidence and the untested boundary.

---

# 4. Merge Gates

A runtime PR should not merge until:

- exact head SHA is reviewed;
- required CI is green;
- tests include failure behavior;
- artifacts match the current SHA;
- no unresolved critical or high defect remains;
- publishing impact is explicitly stated;
- rollback is practical;
- documentation reflects the final behavior.

A docs-only PR may skip runtime tests when it changes no executable or configuration behavior, but must clearly state that limitation.

---

# 5. Release Environments

## 5.1 Development

Purpose:

- local iteration;
- fixtures;
- unit testing;
- draft rendering.

Rules:

- no live upload credentials required;
- outputs clearly labeled non-production;
- synthetic fixtures permitted when labeled.

## 5.2 Review

Purpose:

- full timeline review;
- visual judgment;
- package verification;
- performance measurement.

Rules:

- upload disabled;
- exact artifacts retained;
- verdicts hash-bound;
- real media licensing checked.

## 5.3 Canary

Purpose:

- validate exact production and upload path.

Rules:

- one approved artifact;
- explicit owner authorization;
- exact channel verification;
- immediate post-upload inspection;
- publishing refrozen afterward.

## 5.4 Production

Purpose:

- approved publishing only.

Rules:

- scheduler sees only production candidates;
- exact-manifest authorization;
- no unjudged artifact;
- automatic freeze on systemic failure.

---

# 6. Publishing Authorization

Authorization should identify:

```json
{
  "manifest_sha256": "...",
  "video_sha256": "...",
  "story_id": "...",
  "channel_id": "...",
  "visibility": "public",
  "publish_at": "...",
  "approved_by": "...",
  "approved_at": "..."
}
```

Do not authorize publishing by slug alone.

A rerender must require a new authorization.

---

# 7. Automatic Freeze Conditions

Publishing should freeze when:

- channel verification fails;
- manifest mismatch occurs;
- factual gate fails;
- verdict is missing or contradictory;
- upload verification fails;
- two consecutive candidates quarantine for the same systemic cause;
- media provider failures produce widespread degradation;
- performance exceeds the hard budget;
- captions or thumbnail are missing;
- a published factual correction is required;
- secrets or permissions appear compromised.

Freeze should be the default response to uncertainty near publishing.

---

# 8. Incident Severity

## Severity 0 — Publishing safety incident

Examples:

- wrong channel;
- wrong artifact uploaded;
- unsupported factual claim published;
- credential exposure;
- unauthorized upload.

Response:

- freeze immediately;
- preserve evidence;
- remove or correct public artifact when appropriate;
- rotate secrets if needed;
- perform root-cause review before re-enabling.

## Severity 1 — Production-quality escape

Examples:

- wrong-region image;
- broken captions;
- missing chapter data;
- serious visual defect missed by judges.

Response:

- freeze if systemic;
- document why gates missed it;
- add negative control;
- repair before next release.

## Severity 2 — Candidate pipeline failure

Examples:

- render crash;
- repeated cache invalidation;
- judge outage;
- media retrieval failure.

Response:

- quarantine affected candidate;
- continue only if failure is isolated and safe.

## Severity 3 — Development defect

Examples:

- fixture failure;
- non-production benchmark regression;
- documentation mismatch.

Response:

- fix through normal PR process.

---

# 9. Incident Review Template

```text
Incident ID:
Severity:
Detected at:
Affected artifact:
Public impact:
Detection mechanism:
What happened:
Why existing gates missed it:
Immediate containment:
Root cause:
Corrective action:
Negative control added:
Rollback or repair:
Publishing state:
Owner:
Follow-up date:
```

Blameless does not mean vague. The review should identify the failed contract.

---

# 10. Rollback Policy

Every implementation PR should define:

- commit or PR to revert;
- data or manifest compatibility impact;
- cache invalidation needs;
- workflow state after rollback;
- publishing state after rollback;
- whether rendered artifacts remain valid.

Do not assume reverting code makes old artifacts safe.

Artifact validity must be checked independently.

---

# 11. Dependency and Secret Governance

## Dependencies

For new dependencies, document:

- purpose;
- license;
- version pinning;
- update strategy;
- failure behavior;
- security implications;
- replacement plan.

## Secrets

Rules:

- minimum permissions;
- channel-specific tokens;
- no secrets in artifacts or logs;
- no broad secret inheritance into unrelated jobs;
- explicit expected-channel verification;
- rotation process documented.

---

# 12. Documentation Freshness

Every major contract should name:

- owner;
- last reviewed date;
- implementation reference;
- tests that enforce it;
- known exceptions.

Documentation that contradicts code should be treated as a defect.

---

# 13. Quarterly Operating Review

Review:

- publishing incidents;
- quality score trends;
- factual corrections;
- judge disagreement;
- PR size and review time;
- render cost;
- catalog diversity;
- repeated fallbacks;
- dependency risk;
- documentation drift;
- rollback readiness.

The review should produce a short list of system-level priorities, not dozens of disconnected tasks.

---

# 14. Governance Success Condition

Governance is working when:

- a reviewer can understand what a PR changes and what it does not;
- every approval points to exact evidence;
- unsafe uncertainty freezes publishing;
- incidents produce stronger contracts and negative controls;
- large, mixed, unverifiable changes become culturally unacceptable;
- the project can move quickly without relying on memory or trust alone.
