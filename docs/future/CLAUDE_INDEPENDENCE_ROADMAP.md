# Claude independence roadmap

> Review-only roadmap for Claude/Claudio. No production or workflow changes are made
> by this commit.

## Goal

Videos must continue posting when a Claude subscription/session is exhausted, Claude
Code is unavailable, Gemini hits quota, a research endpoint fails, or same-day
generation breaks.

The solution is not merely another model. The solution is operational separation:

```text
asynchronous generation -> complete render -> QA -> approval -> durable queue -> upload
```

The scheduled upload job is forbidden from generating a replacement video.

## Truth about credentials

A consumer Claude subscription is not a credential that GitHub Actions can reliably
use. Production automation may use an Anthropic API adapter only if separately
configured, but the pipeline must function without it. No new secret is required by
this fallback system.

Optional recognized names:

```text
ANTHROPIC_API_KEY
GEMINI_API_KEY
```

Existing research and media keys remain independent:

```text
YOUTUBE_API_KEY
PEXELS_API_KEY
FRED_API_KEY
NOAA_TOKEN
CENSUS_API_KEY
```

## Runtime architecture

### Generation workflow

Runs ahead of schedule and attempts:

1. Claude, if explicitly configured and healthy;
2. Gemini, if configured and healthy;
3. deterministic local evidence template;
4. no new generation, leaving the approved buffer unchanged.

Every successful candidate must still complete rendering, rights checks, factual
checks, finished-video QA, approval, and queue insertion.

### Posting workflow

1. Read the approved queue.
2. Atomically claim the next eligible item.
3. Reserve an upload idempotency key.
4. Verify the MP4 and manifest hashes.
5. Upload once.
6. Persist the external video ID.
7. Mark the queue item posted.
8. On a confirmed pre-upload failure, release the claim.
9. On an ambiguous timeout, inspect the upload ledger/channel before retrying.

The posting workflow must not call a language model, research API, media search,
renderer, or repair loop.

## Buffer policy

Per channel:

- target: 30 READY videos;
- warning: 14;
- emergency: 7;
- empty: 0.

At one post per day, the target provides roughly 30 days of operational runway.
Evergreen inventory should be diversified so a single stale topic does not fill the
entire buffer.

## Degradation ladder

```text
FULL        Claude produced the preferred plan
ACCEPTABLE  Gemini produced a safe substitute
DEGRADED    deterministic evidence template/local visuals were used
BUFFERED    a previously approved evergreen package was selected
BLOCKED     hard QA, rights, factual, duplicate, or credential gate failed
```

DEGRADED and BUFFERED may post only when all normal hard gates pass. Quality labels
must be stored in manifests and analytics so performance can be compared honestly.

## Deterministic writer policy

The local writer may only use structured verified facts. It must not infer unsupported
causes. Every material sentence must map to source metadata. Best topics:

- scheduled FRED/Census/NOAA releases;
- historical comparisons;
- public-domain explainers;
- evergreen rankings from stable datasets;
- previously verified research packets.

Breaking-news templates are prohibited when source freshness cannot be established.

## Visual and narration fallback

Visual chain:

```text
preferred authored scene
-> licensed stock/evidence capture
-> Manim/Blender when appropriate and installed
-> SVG/Matplotlib/Pillow card
-> fail if the claim cannot be communicated honestly
```

Narration chain:

```text
Gemini TTS
-> local Kokoro
-> Edge TTS
```

All outputs still pass the same finished-video checks.

## Production integration sequence

### Phase 0: inventory

Re-run the frozen production probe. Identify:

- where generation is currently coupled to scheduled posting;
- current package/manifest structure;
- uploader retry behavior;
- duplicate prevention;
- existing evergreen artifacts;
- current upload credential failure behavior.

Gate: no behavior changes.

### Phase 1: approved-package contract

Port the immutable `GeneratedPackage` fields into production:

- stable package ID;
- content fingerprint;
- channel/topic;
- provider and degradation;
- source URLs and evidence hashes;
- MP4, thumbnail, caption and manifest paths/hashes;
- QA verdict;
- approval identity/time;
- evergreen and freshness metadata.

Gate: records are written beside current artifacts but ignored by upload.

### Phase 2: queue shadow

Write approved packages into a durable queue while the old uploader continues.
Compare what the queue would have selected with what actually posted.

Gate: no duplicate fingerprints and deterministic selection for 14 days.

### Phase 3: buffer build

Generate ahead until each canary channel has at least seven approved videos, then
fourteen, then thirty. Do not count unrendered scripts as inventory.

Gate: every counted item has a final MP4 and passing QA manifest.

### Phase 4: idempotent posting shadow

Exercise claim, release, reserve, complete, timeout reconciliation and duplicate
blocking without publishing.

Acceptance tests:

- two workers cannot claim the same item;
- a crash after claim can be recovered;
- a timeout after upload cannot create a second upload;
- completed content cannot be reserved for another slot;
- an empty queue does not invoke generation;
- an invalid artifact never advances to upload.

### Phase 5: canary

Enable queue-based posting for one channel. Keep the old path behind a rollback flag,
but do not let both upload in the same scheduled slot.

Suggested flags:

```text
APPROVED_QUEUE_WRITE_ENABLED
APPROVED_QUEUE_POST_ENABLED
TEMPLATE_FALLBACK_ENABLED
CLAUDE_PROVIDER_ENABLED
GEMINI_PROVIDER_ENABLED
UPLOAD_IDEMPOTENCY_ENABLED
```

All default false until their phase gate passes.

### Phase 6: independence test

Deliberately disable Claude and Gemini in a non-publishing rehearsal. Prove:

- deterministic generation can refill the queue;
- posting consumes already approved videos;
- local visual and voice fallbacks work;
- buffer status and provider health are visible;
- no paid provider is silently activated.

### Phase 7: production authority

Only after canary proof:

- scheduled posting consumes the queue;
- generation runs separately and earlier;
- provider failures affect refill rate, not today’s upload;
- empty queue alerts rather than inventing or uploading an unsafe video.

## Monitoring

Record without exposing secrets:

- READY inventory by channel;
- estimated days remaining;
- provider successes/failures and circuit state;
- packages generated by degradation level;
- generation lead time;
- queue claim age;
- upload retries and ambiguous timeouts;
- duplicate blocks;
- stale evergreen rejects.

Alert when inventory crosses 14 and 7. An empty queue is a high-priority operational
failure, not permission to bypass QA.

## Files in the review implementation

```text
review_prototypes/subscription_fallback/
  contracts.py
  provider_router.py
  provider_health.py
  deterministic_writer.py
  approved_queue.py
  buffer_manager.py
  degradation_policy.py
  upload_idempotency.py
  fallback_orchestrator.py
  cli.py
  fixtures.py
  test_subscription_fallback.py
```

## Non-negotiable acceptance criteria

- posting never generates;
- no consumer subscription is required;
- no new mandatory API key;
- queue contains only complete, approved, QA-passed artifacts;
- hard factual, rights, media, duplicate and upload gates remain fail-closed;
- degraded state is explicit;
- uploads are idempotent;
- queue claims are atomic and recoverable;
- every channel retains a local/template and evergreen fallback;
- rollout is shadow -> canary -> minimum authority, with rollback.
