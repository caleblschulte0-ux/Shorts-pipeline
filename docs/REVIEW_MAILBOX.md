# The judge of last resort — ChatGPT answers a mailbox

Operator ruling, 2026-09-21: *"this should fall back to chatgpt which
should always be available but also it needs to be able to use aletheia
but don't mess with it — you should just attach like a sucker fish."*

## What broke, exactly

At 17:00 UTC on 2026-09-21 the explainer rendered four stories and the
showrunner failed CLOSED on every one:

```
showrunner BLOCK score=None — showrunner failed on a publish run (fail-closed):
no vision judge available. ["headless-claude[0]: claude CLI rc=1: You've hit
your session limit · resets 5:50pm (UTC)", "gemini: HTTP Error 429"]
```

The gate was right. But the judge list had two names on it, both on
quotas that ran out the same afternoon, the four renders died with the
runner, and the editorial gate held 83 more stories pre-render because
every text backend (`groq` 404, `gemini` 429, `anthropic` unset,
`claude_cli` limit) was gone too. Nothing was broken and nothing posted.

## What exists now

Two mailboxes in this repo, one reader (ChatGPT), and code that decides.

### 1. Reviews — `exchange/reviews/` (`shared/review_mailbox.py`)

When `showrunner_review._judge` cannot reach any judge on a **publish**
run, `review_video`:

1. keeps the render — copied to `output/held/<id>.mp4`, uploaded by the
   workflow as artifact `held-renders-<run_id>` (14 days);
2. stages the labelled frames plus one contact sheet under
   `output/review_media/reviews/<date>/<id>/`, which
   `scripts/publish_review_media.sh` pushes to the `preview-renders`
   orphan branch (never `main`);
3. files `exchange/reviews/<date>/<id>.request.json` carrying the
   **verbatim** grade prompt with the rubric, the measured motion and
   temporal evidence, the frame URLs, the sheet URL, the video's sha256
   and the artifact coordinates;
4. rewrites `exchange/reviews/OPEN.json`, the one URL ChatGPT opens.

The gate still holds the video in that run. `<id>` is
`<slug>__<sha256[:10]>`, so a verdict is bound to one exact render.

ChatGPT writes `exchange/reviews/<date>/<id>.verdict.json`:

```json
{"schema": "shorts-review-verdict/v1",
 "request_id": "<copied>", "video_sha256": "<copied>",
 "by": "chatgpt", "graded_at": "2026-09-22T12:00:00Z",
 "grades": { ...the JSON object the prompt asks for... }}
```

`scripts/claim_reviews.py` (workflow `claim_reviews.yml`, fired by the
verdict landing on `main`) then:

- refuses a verdict naming another request id or another video hash;
- runs the grades through `showrunner_review.assemble_verdict` — the
  **same** function every judge's grades go through (schema check,
  code-computed score, motion override, `decide_verdict`);
- runs that through `showrunner_gate.decide(will_upload=True)` — the same
  fail-closed policy and the same floor;
- appends the verdict to `state/showrunner_verdicts.jsonl` with
  `judge: chatgpt-mailbox`;
- on an explicit ship, downloads the artifact, **verifies its sha256
  against the request**, and uploads through the channel's ordinary
  uploader, recording the posted log the way that channel does;
- settles the request beside itself (`<id>.done.json`). A hold is settled
  too; the story stays in its queue and re-renders normally.

ChatGPT grades anchors. It never outputs ship or block, and nothing it
writes can publish a video the code did not approve.

### 2. Asks — `exchange/asks/` (`shared/llm_mailbox.py`)

The last entry in `script_generator._LLM_CHAIN`. A question no backend
could answer is appended to `exchange/asks/<date>.json` keyed by a hash
of (system, user); the caller gets the same "unavailable" it always got.
ChatGPT answers into `exchange/asks/<date>.answers.json`; the next run
that asks the same question gets the answer as if a model had just said
it, and parses it exactly as strictly (the thesis judge still accepts
only an exact `true`). `exchange/asks/OPEN.json` lists what is pending.

On by default in CI (`LLM_MAILBOX=0` to disable), off on a laptop unless
`LLM_MAILBOX=1`.

### 3. Rewrites — `exchange/rewrites/` (`shared/rewrite_mailbox.py`)

Operator, 2026-09-22: *"ChatGPT is supposed to render videos if nothing
else is available. And ChatGPT is always available."* The explainer had no
re-author loop: the deterministic gate held 312 of 337 stories, almost all
for WORD reasons (no number in the title or hook, a noun-phrase title, a
segment topic with no keyword bridge to the headline, a spoken number the
beat's data cannot show), and a story held on Monday was held identically
on Tuesday. Now:

- every story a run holds for word reasons, or the judge blocks, is filed
  as `exchange/rewrites/<date>/<slug>__<hash>.request.json` with its
  current words, **every segment's real data points**, the exact rules the
  gate applies, the exact hold reasons, and (for a judge block) the judge's
  own problems/fixes; `exchange/rewrites/OPEN.json` lists what is open;
- ChatGPT writes `<id>.answer.json`: title, hook, closing, question, and
  one `{topic, say}` per segment;
- `scripts/claim_rewrites.py claim` (in `claim_reviews.yml`, and at the
  start of every explainer run) **validates by code**: same segment
  count; every spoken quantity derivable from that beat's data through the
  gate's own matcher (`shared.beat_match`); no named entity the data does
  not name; topics ≤ 4 words, says ≤ 40; and the same deterministic gate
  the run applies must PASS on the rewritten story. Only then does
  `niche.config.json` change (`words_by: chatgpt-rewrite`), the slug's old
  scene plan is dropped, and the persist commit goes out **without**
  `[skip ci]` so the explainer's push trigger renders it within the hour.
  A refused rewrite is settled with its reasons and re-filed carrying them.

`python scripts/claim_rewrites.py sweep` files the whole backlog.

## The ChatGPT round — nothing to paste

Operator ruling 2026-09-22: *"I should not have to paste anything in a
ChatGPT."* The round is **section 7 of `doctor/PROMPTS.md`**, which every
ChatGPT firing already reads fresh from `main` (sections 4, 5 and 6 end by
executing it). One roll-up index, `exchange/OPEN.json`, tells it whether
any of the three mailboxes has work. Change section 7 and every firing
changes; no app prompt is ever touched again.

## The sucker fish — how this uses Aletheia without touching it

Aletheia (`caleblschulte0-ux/aletheia`) is Caleb's local-first OS; its
voice is the ChatGPT Project ("Thea") that reads Aletheia's truth from
its repo and relays commands. That same ChatGPT subscription is the
reader here. Nothing in Aletheia changes:

- **Same reader.** The review round above is one more paragraph in the
  Thea Project's instructions. No new account, no API key, no code in
  Aletheia. Caleb can also just say "do the shorts review round" to Thea.
- **Same truth.** Aletheia's fleet registry already watches this repo's
  `state/showrunner_verdicts.jsonl` and every publishing workflow. A
  mailbox verdict lands in that file with `judge: chatgpt-mailbox`, so
  the pulse, the sentinel and the morning brief see it with no change.
- **Not the local models.** Aletheia's own `eyes.py` measured local
  vision on the PC at 157–178 s per screenshot and ruled it out; its
  cloud worker runs on the same Claude subscription that hit the limit.
  Neither is a judge. What Aletheia contributes is the always-on ChatGPT
  reader and the fleet view — which is exactly what a remora needs from
  its shark.
- **Never the intercom.** Aletheia's `exchange/commands/` contract says a
  command relays the operator's words. This pipeline does not file
  commands there and never will; that would be messing with it.

## What does not move

- The showrunner's BLOCK is sovereign; the mailbox only ADDS a judge.
- `validate_judge_response`, `compute_score`, `decide_verdict` and
  `showrunner_gate.decide` are the same code for every judge.
- A request is answered once; a settled request is never reopened.
- Media never enters `main` (frames on `preview-renders`, video as an
  artifact). The request JSON is text.
- `review_proposals.py` still refuses anything that weakens the gate.

Held by `tests/test_the_judge_of_last_resort_is_chatgpt.py`.
