# The exchange pipeline — ChatGPT inside one day's run

The daily run is split so ChatGPT can contribute **before** anything renders.
Rendering first would be wasted work: ChatGPT changes both the scripts and the
visuals, and we are not re-rendering.

```
09:45  Phase A   author'd packages -> resolve media -> JUDGE every shot
                 writes ONE bundle: scripts + media health + gap requests,
                 each with its DETERMINISTIC Drive filename
                 commits, then STOPS.  Nothing renders.
         │
06:00  ChatGPT MEDIA worker (Central)
                 reads exchange/bundles/<date>/bundle.json
                 · generates the requested images -> Google Drive, under the
                   filename the bundle already published
                 · verifies bytes, writes ONE CHECKPOINT PER IMAGE to
                   exchange/bundles/<date>/media-progress/
                 · NEVER writes response.json.  NEVER writes DONE.
         │
07:00  ChatGPT FINALIZER (Central)
                 · reads media-progress/ FIRST — reuses every verified image,
                   adopts orphans by exact filename, generates only the rest
                 · punches up the scripts, authors anything Claude left undone
                   (including explainer/curiosity even when trending is full)
                 · commits response.json, reads it back, THEN commits DONE
         │
   ↓ the DONE push fires Phase B (and DONE alone — a checkpoint push must not)
         │
       Phase B   validate every pointer against its checkpoint
                 verified Drive pull -> pin media -> SELF-FILL the rest
                 apply punch-ups that survive the claim guard
                 packages now final -> render
```

## The split (2026-07-31) — two workers, one day

The exchange used to be one ChatGPT task doing everything in one pass. It is
now **two tasks an hour apart**, and they cannot see each other's context —
only this repository. So the repo carries their shared memory.

| | 06:00 Central | 07:00 Central |
|---|---|---|
| | **MEDIA worker** | **FINALIZER** |
| Job | generate + upload + verify images | recover, fill gaps, punch up, author, ship |
| Writes | `media-progress/*.json`, `media-progress/claims/*.json` | all of that **plus** `response.json`, `authored/*.json`, then `DONE` |
| Never writes | `response.json`, `DONE`, `authored/` | — |

Three mechanisms make that work, all in `shared/media_checkpoint.py`:

**1. A checkpoint per image, written the moment it verifies.** One small JSON
at `exchange/bundles/<date>/media-progress/<safe_request_id>.json` recording
the Drive file, the exact bytes' SHA-256, the prompt that produced it, and the
bundle it belongs to. A worker that dies at image 19 of 24 leaves 18
recoverable results, not zero. The full field list ships inside every bundle
at `bundle.json` → `media_protocol`, generated from the same constants the
validator enforces.

**2. Deterministic filenames, published before anyone starts.** Every asset
uploads as `<date>__<safe_request_id>.<ext>`, and every bundle request already
carries the exact string as `drive_filename`. That ordering is the whole
reason an orphan is recoverable: a file can only be found by name if the name
was agreed on in advance. `safe_request_id` appends an 8-hex digest of the
original whenever sanitizing changed it, so `a/b` and `a:b` can never collapse
onto one file.

For a shot inside a package ChatGPT authored there is no bundle request, so
the id is built from **slug + shot index only**: `authored-<slug>-s<n>`. Not
content-addressed, deliberately — the finalizer's punch-up rewords prompts,
and a content-addressed id would orphan every authored image the moment it
did.

**3. Recovery order, and a filename is never proof.**

1. Valid + `verified` + same bundle identity + same prompt → **reuse**.
2. Otherwise search Drive for the **exact** deterministic filename.
3. One match → **download it, hash the bytes**, and write the checkpoint from
   what was actually there.
4. Two or more matches → **conflicted**. Report; never guess.
5. Only when nothing is reusable, generate.

`plan_recovery()` takes the Drive listing as **data**, supplied by the worker.
Nothing in the pipeline talks to Drive — we gained a validator, not a
dependency.

**Bundle identity** is the SHA-256 of the day's `bundle.json` bytes. Every
checkpoint records it; a checkpoint whose identity does not match the current
bundle is refused. Re-run Phase A with different prompts and yesterday's
checkpoints stop matching — which is exactly right.

**Claims** are create-only leases at `media-progress/claims/<id>.json` with a
15-minute default. A live claim by another run means "skip this one". An
**expired** claim is inert — a crashed worker must not leave a tombstone that
costs one image per crash, forever. A verified checkpoint beats any claim.

### What Phase B refuses

Every media pointer in `response.json` is a *claim*; the checkpoint is the
record of the moment those bytes were verified. Where both exist they must
agree exactly. `validate_response_media()` rejects:

- a `request_id` that is not in the bundle, or does not match the request it
  is attached to
- a checkpoint from a different day or a different bundle identity
- a prompt that changed since the image was made
- a missing, short, or non-hex `image.sha256`
- **any disagreement with the checkpoint** across `drive.filename`,
  `drive.file_id`, `drive.folder_id`, `image.sha256`, `image.bytes`,
  `image.format`, `image.width`, `image.height`, and the sharing state — hash
  and byte count alone say the *content* matches, and say nothing about
  whether the pointer names the same asset the worker verified
- a sharing state other than `anyone_with_link` on either side: Drive serves
  an HTML permission page instead of bytes for anything else, so "uploaded"
  and "fetchable" are separate claims
- a `drive.filename` that is not the deterministic name, is dated wrong, or
  names a different request
- duplicate `request_id`s in one response
- **one Drive `file_id` under more than one `request_id` — both sides are
  refused**, even when the hashes are identical. Two requests are two lines
  of script; one image answering both is a shot doing double duty. Nothing
  can say which request owns the file, and guessing is the same coin flip
  `plan_recovery` refuses on duplicate filenames.
- an authored shot's image attached to the wrong package or the wrong shot
- an authored shot's image placed in the **top-level** `media` array (that
  array is keyed by bundle `request_id`, and there is no bundle request for a
  package ChatGPT invented)

### Checkpoints are mandatory on any DONE-triggered run

`DONE` is ChatGPT's assertion that both workers ran to completion. If they
did, every image it points at has a checkpoint — writing one is the media
worker's whole job. So on a DONE run **a pointer with no checkpoint is
refused** and that shot self-fills from stock. Accepting it with a warning
would be the exact failure this contract was built to end: green everywhere,
unverified media on screen.

The single exception is the **no-DONE emergency backstop**. On that path
ChatGPT never finished — often never started — so there are no checkpoints to
require, and demanding them would turn "ChatGPT was late" into "the channel
posts nothing". Policy A still holds where it was meant to.
`--require-checkpoints` / `EXCHANGE_REQUIRE_CHECKPOINTS=1` forces strictness
on that path too.

## Mode `author` — ChatGPT takes over the writing

The bundle carries a top-level `mode`. Normally `"punch_up"`. When Phase A
finds the day short of packages — the Claude Routine did not run and the
reserve bank could not cover it — it flips to **`"author"`** and adds an
`authoring_request` (`shared/authoring_brief.py`). ChatGPT then writes the
day's slate itself into `response.json`'s `authored` array, and Phase B
validates and promotes it before doing anything else.

```
Phase A  0 packages, bank empty  ->  mode:"author", write + mix resolved
                                     from config/channel_registry.json
ChatGPT  reads authoring_request, writes response.json.authored[] + DONE
Phase B  ingest_authored.py: validate -> promote -> quarantine failures
         cover media for the new packages, then the normal Phase B work
```

The brief hands ChatGPT the complete per-format spec as DATA, generated from
the same constants the validator enforces — so what we ask for and what we
accept cannot drift. Promotion runs
`package_buffer.structural_problems()`, the same gate the reserve bank uses.
A package that fails is quarantined into `authored_report.json` with its
reasons; the rest of the slate ships. Full trace: `docs/FALLBACKS.md` §6.

## Why one bundle, not two asks

The punch-up is better when the writer can see what will be on screen, and
media/line pairings cannot drift if the script and the visuals are decided in
the same breath. One round trip, one wait.

## The pieces

| Piece | Job |
|---|---|
| `funnel/media_judge.py` | Script-aware scoring: "the line says X, this is the image — does it land?" Returns `strong`/`weak`/`missing` + the AI prompt for gaps. |
| `shared/exchange_bundle.py` | Builds the day's bundle; reads the response; owns the READY/DONE markers. |
| `shared/punchup_guard.py` | Mechanically enforces that a rewrite changed *wording*, never *claims* or beat structure. |
| `shared/media_checkpoint.py` | The split-worker contract: checkpoint schema, deterministic filenames, bundle identity, claims/leases, orphan recovery, worker boundaries, and the Phase B response validator. |
| `scripts/exchange_dry_run.py` | The 8-step offline fixture that stands in for both ChatGPT workers. |
| `scripts/exchange_phase_a.py` | Phase A entrypoint. Resolves media, judges, writes the bundle. **Never renders.** |
| `scripts/exchange_phase_b.py` | Phase B entrypoint. Pulls media, self-fills, applies guarded punch-ups. |
| `scripts/fetch_exchange_media.py` | The paranoid downloader (hash + full pixel decode + placeholder detection). |

## The judge — when do we call ChatGPT?

Not only when we find nothing. A shot is a gap when the media is:

- **missing** — nothing found, or
- **weak** — little term overlap with the line, a *generic stand-in* for a
  named subject (line says "Starship", image is a stock rocket), below the
  720px target edge, unverified provenance, or recently reused.

`weak` is the important one: it's the difference between "only when desperate"
and "whenever we could do better".

## Policy A — a no-show never costs us the day

Operator decision, 2026-07-30. When Phase B finds a request unfulfilled it runs
a **self-fill** pass: the funnel again with the gloves off (wider providers,
lower floor, accept the weak-but-real candidates the judge rejected). Worst
case a shot ships weaker than we wanted; we never ship nothing.

The **backstop schedule** (`exchange_phase_b.yml`) exists for the same reason:
if ChatGPT never writes DONE, the push trigger never fires, and without the
backstop the day would never render at all. It no-ops when Phase B already ran
for that date, and — see the DST note below — it runs at **08:30 Central in
both seasons**, never on top of a live finalizer.

**Pollinations is retired as the AI-image path.** Every AI-generated image
comes from ChatGPT; the self-fill pass finds *real* media instead.

## The punch-up guard — non-negotiable

ChatGPT may rewrite `script`, `title`, `hook`, `hashtags` and shot `phrase`
text. It may not:

- change, drop, or invent any number, percent, money amount, date or year;
- add or remove a named entity;
- change the shot count or any shot's `query` (media is already chosen
  against those);
- move outside ~0.5×–1.8× the original word count.

A rewrite that breaks any rule is **rejected and the original ships**. This
exists because PR #168 found 519 of 546 explainer datasets were LLM-invented
"illustrative" numbers — a punch-up pass is a fresh chance to manufacture more,
so it is checked, not trusted. The guard errs toward rejection: a false reject
costs a missed improvement, a false accept ships a fabricated fact.

Re-casing an existing word for emphasis (`caught` → `CAUGHT`) is explicitly
allowed — entity comparison runs against the other text's full word set.

## Knobs

| Setting | Default | Effect |
|---|---|---|
| `CHATGPT_ANIM_BUDGET` (repo var) | `0` | How many of the day's gaps are requested as **animation** instead of a still. `0` = stills only. |
| `CHATGPT_MAX_REQUESTS` (repo var) | `24` | Hard cap on daily requests. Gaps are spent worst-first. |
| `--no-self-fill` | off | Skip the gloves-off pass (leaves gaps unfilled). |
| `--no-punchup` | off | Ignore script rewrites entirely. |
| `--require-done` | off | Phase B defers instead of proceeding without ChatGPT. |
| `--require-checkpoints` / `EXCHANGE_REQUIRE_CHECKPOINTS=1` | off | Force checkpoint enforcement on a **no-DONE** backstop run. A DONE-triggered run always requires them. |
| `--backstop` | off | Scheduled runs only: no-op unless the 07:00 Central finalizer has had its full 90-minute window. |

## Wiring (LIVE as of 2026-07-30)

| Step | Fires on |
|---|---|
| **Phase A** | `workflow_run` on **Auto-merge claude PRs** (the Routine's packages landing) + `45 9 * * *` backstop, `push` on packages + dispatch |
| **ChatGPT MEDIA** | its own **6:00 AM Central** task (11:00 UTC summer / 12:00 UTC winter), reading `exchange/bundles/<date>/bundle.json`. Writes checkpoints only. |
| **ChatGPT FINALIZER** | its own **7:00 AM Central** task (12:00 UTC summer / 13:00 UTC winter). Writes `response.json`, then `DONE`. |
| **Phase B** | `push` on `exchange/bundles/*/DONE` **and nothing else** + backstop candidates `30 13 * * *` / `30 14 * * *` (gated to 08:30 Central) + dispatch |
| **Render** (`daily.yml`) | `workflow_run` on **Exchange Phase B** + manual `.github/triggers/daily` |

### The trigger that had to MOVE — read before changing any of this

`daily.yml` used to fire on `workflow_run: Auto-merge claude PRs` **and** on a
`state/trending_packages/**` push. Both meant "render the instant the Routine's
packages land". With the exchange in place that **races and always wins**: the
render would finish long before ChatGPT's 10:00 task, using pre-ChatGPT media
and the un-punched scripts, every single day — while everything still looked
green. Nothing would have alerted us.

So Phase A **took over** the auto-merge slot, the package-push path was
**removed**, and `daily.yml` now renders only when Phase B completes. If you
ever see `daily.yml` triggering on package landing again, the exchange is dead
and you are shipping the old media.

Consequence worth knowing: `third.yml` and the explainer chain off "Daily
Shorts", so they now run roughly 1.5–2h later in the morning as well.

### Times, and why an earlier chain is free

| Step | UTC |
|---|---|
| Claude Routine authors | ~09:19 (observed) |
| Phase A (auto on auto-merge; 09:45 cron backstop) | ~09:20 |
| ChatGPT task | **6:00 AM Central** = 11:00 UTC (CDT) / 12:00 UTC (CST) |
| Phase B (auto on DONE; backstop 08:30 CENTRAL, both seasons) | ~12:20 |
| Render (~60-70 min) | ~11:25-12:35 |
| **Uploads** | **8:00, 9:30, 11:00, 12:30, 2:00, 3:30 CENTRAL — fixed wall-clock, unaffected** |

The chain's timing is decoupled from posting: publish slots are
fixed CENTRAL wall-clock times (`DEFAULT_PUBLISH_SLOTS_CENTRAL` in
`scripts/run_trending_daily.py`, DST-correct via zoneinfo) and `schedule_times()` simply takes the next
free ones. An earlier render does not move a single upload — it only widens the
margin before the 08:00 Central first slot. The one real trade is **topic freshness**:
authoring earlier means less overnight news has accumulated for the Routine's
"happened today / just announced" rule.

**The DST trap, and how it is handled.** These crons are UTC; ChatGPT Tasks
are LOCAL time. The **finalizer** runs 7:00 AM Central, which is 12:00 UTC in
summer (CDT) and 13:00 UTC in winter (CST) — it moves an hour twice a year and
a fixed UTC cron does not.

A single UTC cron cannot solve this and the first attempt proved it. The
backstop sat at **12:45 UTC**, which is 7:45 Central in summer — 45 minutes
*into* the finalizer's run — and **6:45 Central in winter, fifteen minutes
before the finalizer even starts**. For half the year it would have rendered a
day with no punch-up and no authored packages, silently, with every workflow
green.

The fix is to stop trusting UTC. Two candidate crons fire (`30 13` and
`30 14` UTC) and `--backstop` decides in **America/Chicago** which one is
real:

| | 13:30 UTC | 14:30 UTC |
|---|---|---|
| summer (CDT) | 8:30 Central — **runs** | 9:30 Central — no-ops (already applied) |
| winter (CST) | 7:30 Central — too early, no-ops | 8:30 Central — **runs** |

So the backstop always lands 90 minutes after the finalizer *starts*, in both
halves of the year. It also defers if `response.json` landed in the last 20
minutes without a `DONE` — that is a finalizer mid-commit, and reading it then
gets a half-written day.

If the operator ever moves the ChatGPT finalizer, move
`FINALIZER_HOUR_CENTRAL` in `scripts/exchange_phase_b.py`; the crons are only
the two candidate wake-ups. `tests/test_split_worker.py` asserts both seasons.

### Post-mortem 2026-07-30 — the first live day, and why it silently did nothing

Worth reading before touching any trigger here. The chain was fully deployed
and every workflow was green, yet the exchange contributed nothing:

```
02:58  exchange workflows land on main
07:12  Phase A runs (its 04:30 cron fired 2h42m LATE) — succeeds in 10s
       because state/trending_packages/20260730/ does not exist yet
09:19  the Routine's packages land (PR #198, auto-merged)
       -> Phase A does NOT re-run
10:32  render + upload, no bundle, no ChatGPT media, no punch-ups
```

Three failures, each individually enough to kill the day:

1. **The cron was scheduled BEFORE the thing it depends on.** 04:30 was a
   guess at the Routine's time; the Routine actually authors ~09:19. Phase A
   looked for packages five hours before they existed. Now 09:45.
2. **The event trigger that should have saved it never fired.** Phase A had
   `workflow_run: {workflows: [Auto-merge claude PRs], branches: [main]}`.
   For `workflow_run`, `branches` matches the **triggering run's** head
   branch — and auto-merge.yml runs in the pull request's context, so its
   head_branch is the PR branch, never `main`. The filter excluded the only
   event it existed to catch. **Do not add `branches:` back.**
3. **GitHub cron drift is hours, not minutes.** The 04:30 cron fired at
   07:12. Crons are a backstop; the event trigger must be the primary path.

The failure mode to internalise: **a Phase A that finds no packages exits 0.**
That is correct behaviour (a day with no gaps is a valid successful Phase A),
but it means this class of bug is invisible in the Actions tab — everything is
green and the exchange is simply absent. If you want to know whether the
exchange actually ran on a given day, check for
`exchange/bundles/<date>/bundle.json`, not for a green checkmark.

### What the operator's Claude Routine must do

**Author packages, push, stop.** It must NOT dispatch `daily.yml` — that is now
the last step of the chain, not the next one. Full note at the top of
`CLAUDE_ROUTINE_INSTRUCTIONS.md`.

## Testing

```bash
python -m unittest tests.test_exchange           # judge + bundle + guard
python -m unittest tests.test_media_checkpoint   # the split-worker contract
python -m unittest tests.test_split_worker       # end-to-end + takeover matrix
python scripts/exchange_dry_run.py               # the 8-step fixture, offline
python scripts/exchange_phase_a.py --date <D> --channel trending --dry-run
python scripts/exchange_phase_b.py --date <D> --channel trending --dry-run
```

`scripts/exchange_dry_run.py` stands in for both ChatGPT workers and walks the
whole day: Phase A publishes the filenames, the media worker checkpoints one
image and then **dies** mid-run, the finalizer reuses the first and adopts the
second as an orphan by exact filename, an authored shot gets its own
checkpoint, `response.json` lands before `DONE`, and Phase B refuses a hash
edited after the fact. Exit 0 means the contract holds; a failure names the
step.

The full handshake was simulated end-to-end before shipping: Phase A wrote a
bundle for 2 gaps, a faked ChatGPT response fulfilled one and offered a
punch-up, Phase B pinned the media with `media_origin: chatgpt`, and the
punch-up was correctly rejected for an invented entity.
