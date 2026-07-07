# LEARNING LOOP — shared doctrine for turning analytics into decisions

Channel-agnostic. Every channel's brain reads this alongside its own playbook.
It defines how analytics become bounded, reversible changes to what the brain
queues and how it writes — **without** turning the channel into a noise-chasing
machine. Destination is a full closed loop (collect → normalize → infer →
adapt); the rule below is that you **earn complexity with views**, you don't
front-load it.

---

## 0. The one rule that overrides everything

> **Do NOT auto-adapt on sub-~100-view samples.** Below ~100 views/video the
> variance dwarfs the signal — a 41-view video did not "beat" a 20-view one, it
> got luckier. At low volume, the OBVIOUS signal (a clean sort of retention by
> topic/hook) plus brain judgment beats every statistical model. Heavy ML
> (survival, bandits, uplift, change-point, hierarchical Bayes) is a **phase-3**
> tool, switched on only when videos reliably clear the volume where its math
> means something.

## 1. Performance is a funnel, not a score

Never hand the brain one opaque "video score." Give it a **staged scorecard**,
because each stage fails differently and each has a different fix:

| Stage | Signal | If it fails, fix… |
|---|---|---|
| **Exposure** | shown-in-feed, impressions, traffic-source breadth | packaging/first-frame, not the topic |
| **Hook** | viewed-vs-swiped, first-3s hold, first hazard time | the opening clause / proof frame |
| **Body** | mid-roll retention slope, per-segment hazard peaks | pacing, filler, weak beat |
| **Ending** | end-retention, replay area | the payoff line |
| **Satisfaction** | likes/comments/shares/subs per engaged view | the promise vs delivery |
| **Expansion** | views/hour residual vs baseline for this size/topic | keep core, mutate packaging |

Decomposition is what makes feedback actionable: *hook wins but body collapses →
rewrite pacing, not topic. Retention high but exposure weak → keep the core,
change packaging. Bad in browse, good in search → it's an evergreen, not a feed
short.*

## 2. The shot-aligned retention map (the highest-value build)

For every upload, log a timeline: hook start/end, each punch timestamp, each
visual swap, each caption event, gameplay-strip changes, payoff, CTA. When
YouTube returns retention (`elapsedVideoTimeRatio` buckets: `audienceWatchRatio`,
`relativeRetentionPerformance`, `startedWatching`, `stoppedWatching`), **join the
buckets to those timestamps.** Now "it didn't retain" becomes "they bailed at the
7s abstract sentence." This is the single best diagnostic; build it as soon as a
video has enough views to *have* a curve.

## 3. What the brain actually reads: `state/brain_context.json`

The whole loop's payload is a **compact, human-and-Claude-readable** artifact —
NOT a warehouse. Keep it ≤ a couple hundred lines:
- rolling per-topic-family and per-hook-family retention + staged scores,
- current winners/losers **after shrinkage** (so small samples don't whipsaw),
- top retention cliffs with a one-line suspected cause each,
- audience-slice notes (traffic source / device / country) when they diverge,
- a handful of curated good-example and bad-example slugs,
- bounded playbook-edit suggestions as a diff.

The brain reads this, adjusts queue scores, and makes **only bounded edits** to
doctrine/examples. It never free-forms strategy from raw numbers.

## 4. Feedback targets, ordered by how safe they are to automate

| Target | Change | Automation |
|---|---|---|
| Scoring weights | topic/hook/mechanic priors in the planner | fully auto |
| Few-shot examples | promote winners / demote anti-patterns | fully auto |
| Mechanic/format priors | raise or lower a family's probability | fully auto |
| **Playbook rules** | add/weaken a doctrine ("no 2 static photo beats in a row") | **human-reviewed or bounded auto-edit only** |

## 5. Guardrails (aggressive in analysis, conservative in deployment)

- Feature-flag every adaptive rule; version playbooks and priors.
- Keep a **last-known-good** snapshot of queue weights + doctrine.
- **Hard caps** on how much one update can shift topic allocation, hook
  distribution, or mechanic usage per day.
- **Canary** a rule change on 1–2 videos before it goes global.
- A **kill switch** that freezes learning and reverts to the last stable prior.
- **Mode-collapse watch:** if novelty drops (the brain clones one winner), the
  drift monitor forces exploration back in. This is the #1 failure mode of
  online creative systems.

## 6. Correctness & compliance (cheap to bake in, expensive to retrofit)

- **Version the metric definitions.** YouTube changed Shorts view counting on
  2025-03-31 (a view now counts on start/replay, no min watch time). Tag every
  row `views_definition_version`; never train one model across the regime break.
- **Keep raw views, engaged views, AVD, and rewatch indicators SEPARATE.**
  `audienceWatchRatio` can exceed 1.0 (rewatches); `averageViewDuration` excludes
  looping traffic. Don't collapse them into one number.
- **Derived-metrics policy:** platforms may restrict metrics that *replace/modify*
  returned API data; namespace your engineered metrics as `derived_*`, log
  provenance, and apply for the analytics/reporting use case if you run this
  long-term.
- **User data:** comment text and identifiable interaction data are protected —
  revalidate OAuth on a 30-day cadence, keep a deletion path, don't hoard.

## 7. Build order (earn each tier)

- **Now (any volume):** the staged scorecard, `brain_context.json`, metric
  versioning, the guardrails, retention→segment join for videos that have curves.
- **At reliable hundreds of views/video:** targeted retention/traffic-source
  queries per winner, simple shrinkage baselines, topic/hook clustering.
- **Phase 3 (thousands/video, clean logging):** local warehouse
  (Parquet + DuckDB), survival models, sequential tests, uplift, then contextual
  bandits for scarce experiment traffic — **last**, never first.

The channel becomes self-improving when analytics stop being a scoreboard and
become **training data for production decisions** — fed in bounded, reversible
doses.
