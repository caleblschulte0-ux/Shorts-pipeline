# exchange/ — ChatGPT ⇄ repo media handoff

The no-API-key path for ChatGPT-generated media. **Bytes go to Google Drive;
only a small pointer JSON comes into git.** That split is deliberate: it
respects the storage rule that `main` carries small JSON only (see
`docs/STORAGE_AUDIT.md` §7 — committed media already forced a history purge
once), and it sidesteps the connector limit that killed every earlier
attempt (the GitHub writer takes inline UTF-8 text only, so a 1.5MB image
can never be committed directly).

```
exchange/requests/<id>.json     we write   — what we need made
        ↓
ChatGPT scheduled task reads it, generates the image
        ↓
Google Drive                    it writes  — the actual bytes
        ↓
exchange/responses/<id>.json    it writes  — verified Drive pointer + sha256
        ↓
scripts/fetch_exchange_media.py            — downloads, verifies, hands to render
```

## Two workers, one day — read this first

The day is worked by **two scheduled tasks an hour apart**, not one:

| | When | Job | Writes | Never writes |
|---|---|---|---|---|
| **MEDIA worker** | 06:00 Central | generate + upload + verify every image | `media-progress/*.json`, `media-progress/claims/*.json` | `response.json`, `DONE`, `authored/` |
| **FINALIZER** | 07:00 Central | recover, fill gaps, punch up, author, ship | everything above **plus** `response.json`, `authored/*.json`, then `DONE` | — |

**`DONE` is the only thing that fires the render.** Not a `response.json`
push, not a checkpoint push, not a package push. The media worker writing
`DONE` at 06:00 would render an hour before anything was authored or punched
up — with every check green.

### The two of you cannot see each other. These files are how you talk.

The 07:00 task does not inherit the 06:00 task's context; it inherits this
repository. So every verified image gets a **checkpoint** written the moment
it verifies:

```
exchange/bundles/<date>/media-progress/<safe_request_id>.json
exchange/bundles/<date>/media-progress/claims/<safe_request_id>.json
```

Full field list, generated from the code that validates it, is in every
bundle at `bundle.json` → `media_protocol`. The schema itself lives in
`shared/media_checkpoint.py`.

**Checkpoint after every single image, not once at the end.** A run that dies
at image 19 of 24 must leave 18 recoverable results behind, not zero. That is
the entire reason this exists.

### Deterministic filenames

Every asset uploads to Drive as:

```
<date>__<safe_request_id>.<ext>          e.g. 20260731__spacex-catch-s2-9f1c4a.png
```

Each bundle request already carries the exact string as `drive_filename` —
**use it verbatim**, it is published before you start. `safe_request_id` is
the request id with anything outside `[A-Za-z0-9._-]` replaced by `-`; if
that changed the string (or it was longer than 72 chars) an 8-hex sha256 of
the original is appended, so two different requests can never land on one
file.

For a shot inside a package **you** authored there is no bundle request, so
build the id yourself:

```
authored-<slug>-s<shot_index>
```

`<slug>` lowercased, anything outside `[a-z0-9-]` replaced by `-`. Derive it
from **slug + shot index only** — never from the prompt, a timestamp, or a
counter. The 07:00 worker recomputes the identical string from the package on
disk, and it cannot do that from a prompt it never saw (and which the
punch-up may have since reworded).

### Recovering an orphan — in this order

An orphan is an image that reached Drive while its checkpoint did not.

1. **Read the checkpoint.** Valid, `verified`, same bundle identity, same
   prompt → **reuse it. Do not regenerate.** Regenerating burns budget *and*
   produces a different picture than the one the checkpoint names.
2. Otherwise search Drive for the **exact** deterministic filename.
3. Exactly one match → **download it, hash the bytes, confirm it decodes**,
   and write the checkpoint from what you actually found. A filename is a
   lookup key; it is never evidence about content.
4. More than one match → **conflicted**. Report it and move on. Drive allows
   duplicate names, and guessing is a coin flip on what ends up in the video.
5. Only when nothing is reusable, generate it.

### Bundle identity

Every checkpoint records `bundle.identity` — the **sha256 of that day's
`bundle.json` file bytes**. Compute it; do not guess. A checkpoint whose
identity does not match the current bundle is refused, which is how an image
made for a prompt that has since changed stays out of the video.

### Claims (so you two never make the same image twice)

Before generating, create `media-progress/claims/<safe_request_id>.json`
**create-only**. If it already exists and `expires_at` is in the future,
someone is on it — skip that request. An **expired** claim is inert: take it
over. A verified checkpoint beats any claim, including a live one. Default
lease is 15 minutes.

### Honesty applies to checkpoints too

A checkpoint asserts *you downloaded these bytes and hashed them*. Writing
one for an image you did not verify is worse than writing nothing, because
the next worker will skip the work believing it is done.

## The bridge (why this works when /mnt/data did not)

The Drive connector will not accept a sandbox path (`/mnt/data/foo.png`) or a
filename. It needs a **connector-native file reference**. The working
sequence is:

1. generate the image with the image tool;
2. call **`files.list`** and read the generated image's real **`file_id`**;
3. pass that exact `file_id` as **`file_uri`** to `Google_Drive.upload_file`.

Do not substitute a `/mnt/data` path, a sandbox URL, or a bare filename at
step 3 — that is the failure mode this whole contract exists to avoid.

## Response schema

`exchange/responses/<request_id>.json`:

```json
{
  "schema": "chatgpt-exchange-response/v1",
  "request_id": "image-20260730-demo-01",
  "status": "fulfilled",
  "drive": {
    "file_id": "1AbC...",
    "name": "demo.png",
    "link": "https://drive.google.com/file/d/1AbC.../view",
    "download_url": "https://drive.google.com/uc?export=download&id=1AbC...",
    "public": true
  },
  "image": {
    "sha256": "…64 hex…",
    "bytes": 1554380,
    "format": "png",
    "width": 1024,
    "height": 1024
  },
  "verified": {
    "read_back": true,
    "note": "read the file back from Drive and confirmed id + link"
  },
  "generated_at": "2026-07-30T12:00:00Z"
}
```

`status` is `fulfilled` | `partial` | `unsupported` | `failed`. **An honest
failure with the blocking step named is a valid response; a fabricated
success is not.** Never write a response describing an upload that did not
happen — an unreachable pointer is worse than no response, because a render
job will wait on it.

`image.sha256` is mandatory on `fulfilled`. The consumer recomputes it after
download and rejects a mismatch — that is how substitution and truncation get
caught (an earlier attempt delivered a corrupt 2-colour placeholder whose
claimed hash did not match its bytes).

## Every package gets an editorial decision — including on a normal day

For each entry in `packages`, return **either** the rewritten fields **or**
`"kept": true` with a one-line `editor_note` saying why it already lands
("hook already 4 words + ?, voice present, kicker names Gary"). An entry
with neither is a skipped job, not a decision.

**`kept` means you read it and it works — not that the guard looked
strict.** The claim guard only protects numbers, entities, and beat
structure. Wording is entirely yours to improve inside those limits, and
that is most of what a punch-up is. Returning a whole slate untouched is a
red flag, not caution; if you keep more than half a slate, every
`editor_note` had better say something specific. Phase B logs a warning
when every script comes back kept.

## Who edits this pipeline — not you

**Claude is the only agent that edits this repository** — meaning every
Claude in the system: the interactive sessions AND the headless brains that
author packages, judge renders, and write story words inside the pipeline.
They are one author on different runtimes.

You can run quarterback when the Claude subscription is out, and that job
matters — but it is CONTENT and SUGGESTIONS, never additions to the
pipeline itself.

| You may write | You may never write |
|---|---|
| `exchange/bundles/<date>/response.json` + `DONE` | any `.py`, `.yml`, `.sh` — anywhere, including inside your own folders |
| `exchange/bundles/<date>/media-progress/**` (checkpoints + claims) | any workflow, gate, validator or test |
| authored packages, words, media pointers | `retro/README.md` or `exchange/README.md` — your own instructions |
| `retro/<date>/proposals/*.json` | anything under `scripts/`, `shared/`, `funnel/`, `engines/`, `docs/` |
| | `state/**` — promotion is our side's job, and it validates first |

Nothing mechanically stops you from breaking this — it is a working
agreement, and it holds because you keep it. If you believe something in
the pipeline should change, that is a PROPOSAL: write it as one and Claude
will decide, implement it properly, and tell you what it thought. A change
you make yourself skips the review that makes the change safe, and skips
the reply that would have taught you why.

## Mode `author` — the takeover (you are the brain today)

`bundle.json` carries a top-level `mode`. Normally it is `"punch_up"` and
your job is media + script editing. When it is **`"author"`**, the channel's
own writing brain (a Claude Routine) did not run and the reserve bank could
not cover the day. **There is no slate. Without you the channel posts
nothing.**

### On a takeover day you own the WHOLE day — words AND pictures

This is the part that is easy to get wrong. On a normal day the pipeline
finds the media first and asks you only to fill the gaps it judged. **On a
takeover day the packages did not exist when that search ran**, so there is
nothing to search for and no `requests` entries for the work you are about
to invent. The next thing that runs after you is the renderer.

So: **every shot of every `reddit_story` you author needs an image you
generated, attached to the shot itself.** Same Drive + sha256 pointer you
already produce, just inline on the shot instead of in the `media` array:

```json
"shots": [
  {"phrase": "the office fridge", "query": "office kitchen",
   "media": {
     "status": "fulfilled",
     "drive": {"file_id": "1AbC…", "public": true,
               "download_url": "https://drive.google.com/uc?export=download&id=1AbC…"},
     "image": {"sha256": "…64 hex of the exact bytes…", "bytes": 1554380,
               "format": "png", "width": 1080, "height": 1080}
   }}
]
```

Each of those images also needs a **checkpoint**, with
`"request_kind": "authored_shot"`, the package slug in `package_id`, the
shot index in `shot_index`, and the request id built as
`authored-<slug>-s<shot_index>` (see *Two workers, one day* above). Upload
the file as `<date>__authored-<slug>-s<shot_index>.png`.

`text_card` and `graph_race` have no `shots` and need no media from you —
the renderer sources their b-roll from `broll_query` and draws the chart.

**Do not put authored-shot images in the top-level `media` array.** That
array is keyed by bundle `request_id`, and there is no bundle request for a
package you invented — Phase B rejects any entry there whose id looks like an
authored shot.

Every pointer is verified on arrival exactly like a normal-day one: SHA-256
recomputed from the downloaded bytes, a full pixel decode, a placeholder
check (≤8 distinct colours is refused), and an HTML permission page from a
non-public Drive file is detected and refused. **A pointer that fails is
dropped and that shot falls back to stock self-fill** — which is the weaker
outcome the takeover exists to avoid.

If you genuinely cannot generate an image for a shot, leave `media` off it
and say so. Honest omission costs one shot. A fabricated pointer or a wrong
hash is worse, because we trust it until it fails.

### `authoring_requests` — one entry per channel that needs a brain

**This is the whole signal.** If Claude did its job, `authoring_requests` is
absent or empty. If a channel appears in it, Claude left that channel
nothing today and you are its brain. Each channel asks for a different
thing, and each has its own array in your `response.json`:

| Channel in `authoring_requests` | `job` | You write | Return in |
|---|---|---|---|
| `trending` | author | 6 packages, 2+2+2 | `authored` |
| `explainer` | `rewrite_words` | title / hook / says / closing per story | `authored_explainer` |
| `curiosity` | `stock_queue` | whole long-form stories | `authored_curiosity` |

`third` never appears — its package is a capture recipe for a Twitch clip
that does not exist until the run happens, so there is nothing to write
ahead of time.

**`explainer` is a REWRITE, not an authoring job.** Those stories already
carry real World Bank numbers; only the words are bad, because they came
from a deterministic template when no brain was reachable. So:

- Change the wording freely. Do **not** change, drop, or invent any number,
  percent, year, country, or named entity. A guard compares every line
  before and after and **rejects the entire story** if one moved — it then
  ships with its original bad words, which helps nobody.
- Return exactly one `says` entry per segment, in the same order.
- The title should name the surprise. The failure this exists to fix is
  *"Congo, Dem. Rep. Beats Everyone On Male primary school age children
  out-of-school"* — a real title this channel shipped.

### If there is no bundle at all, author anyway

The takeover exists for the day everything on the Claude side is dead. On
that day the thing that writes `bundle.json` may itself have failed to run,
so **absence of a bundle is not permission to do nothing.** Decide from the
repo, not from the bundle.

**Count the slate correctly.** Look at
`state/trending_packages/<today UTC, YYYYMMDD>/` and count only real
packages: **skip any filename beginning with `_`** (`_schedule.json` is
config) and skip reports/metadata (`report.json`, `manifest.json`,
`index.json`, `meta.json`, `authored_report.json`, `phase_b_report.json`).
A real package always carries at least one of `script`, `text`, `series`,
`shots`, `subreddit`, or `broll_query`. Getting this wrong cancels the
takeover: five real packages plus `_schedule.json` looks like a full six.

**Write only the shortfall, and restore the 2 + 2 + 2 mix.**

| Real packages present | What you write |
|---|---|
| 0 | all six — 2 reddit_story, 2 text_card, 2 graph_race |
| 1–5 | only the missing ones, choosing formats so the day ends at 2 + 2 + 2 |
| 6 | no **trending** packages — but see below, you are probably not done |

Count what exists by format first, then fill the gaps. If the day already
has 2 reddit_story and 1 text_card, you write 1 text_card and 2 graph_race —
not six of anything.

**A full trending slate does not end your authoring job.** Explainer and
curiosity are separate channels with separate asks, and six trending packages
say nothing about either of them. Check `authoring_requests` for *every*
channel listed, not just `trending`. The bundle spells this out in
`instructions.two_jobs[0]` when trending is full and another channel is not.
With no bundle at all, check both configs yourself: any
`data_learning/niche.config.json` story with `"words_by": "deterministic"`
that has not posted needs a rewrite, and fewer than 3 un-posted stories in
`data_learning/curiosity.config.json` means that queue needs stock.

**With no bundle you also have no spec, so go read it.** The per-format
rules and the media pointer shape normally arrive inside
`bundle.json.authoring_requests`. When there is no bundle, read them from
the repo instead — `shared/authoring_brief.py`, the `FORMAT_SPECS` dict
(required fields and rules per format) and `MEDIA_CONTRACT` (the image
pointer shape and the checks it will face). Do not guess the schema.

**Commit in two separate steps, in this order:**

1. Commit `exchange/bundles/<date>/response.json` to `main`. Then **read it
   back from `main` and confirm it is complete and parses.**
2. Only then, as a **second, separate commit**, create
   `exchange/bundles/<date>/DONE`.

`DONE` is what fires the render. Writing it in the same commit as
`response.json` means a truncated or half-written payload triggers the
render anyway, and on a takeover day that costs the entire day. Two
commits, with a verification between them, is the whole safeguard. (If
`DONE` ever arrives over an unreadable `response.json`, Phase B logs a
hard error naming this rule.)

Phase B reads `authored` whether or not a bundle exists, so a slate you
write with no bundle present still renders and still uploads. Its 12:45 UTC
backstop cron runs regardless of what did or did not fire earlier, so you do
not need anything upstream of you to have worked.

Everything you need is in `bundle.json` → `authoring_request`:

| Field | What it is |
|---|---|
| `write` | how many packages to write |
| `mix` | how many of each format — the slate is **2 + 2 + 2**, never 6 of one |
| `formats` | the complete spec per format: required fields, shape, rules |
| `hard_rules` | the mechanical checks we run on your output |
| `do_not_repeat` | titles the channel posted recently |
| `quality_bar` | the voice to write in |

**Where to put them** — add an `authored` array to the same `response.json`
you already write, one complete package object per entry:

```json
{
  "schema": "chatgpt-exchange-response/v1",
  "authored": [ { "...one full package..." }, { "..." } ],
  "media": [ ... ],
  "packages": [ ... ]
}
```

One file write, no new plumbing. If that fails, the fallback is one file per
package at `exchange/bundles/<date>/authored/NN_slug.json` — both are read.

**Do not write into `state/trending_packages/` yourself.** Everything you
author is validated before promotion. A package that fails is quarantined
with its reasons into `authored_report.json` and simply does not ship — it
does not break the rest of the slate, and it does not silently render either.

What gets a package rejected, mechanically:

- a shot/punch `phrase` that is not an exact substring of its `script`
- a `highlight` that is not an exact substring of its `text`
- a `series.values` whose length differs from `years`
- a `graph_race` whose leader peaks under 1,000 or grows less than 3×
  (the renderer refuses it — see `authoring_request.formats.graph_race`)
- a title that repeats something the channel posted in the last 6 days
- a missing required field for that format

Write fewer good packages rather than more weak ones. Four that land beat six
that don't, and an honest short slate is a valid outcome.

## Run log (what has actually been proven)

| Run | Transport (files.list -> file_uri -> Drive) | Image content | Sharing |
|---|---|---|---|
| `image-20260730-demo-01` | **WORKED** — Drive id `1Va8Rfd5…`, real 1,393,674-byte PNG, readback confirmed | FAILED — drew GitHub screenshots instead of the prompt, 1536x1024 not 1024x1024 | FAILED — folder `shared:false`, unreachable (verified: Drive returns an HTML permission page, not bytes) |

| `image-20260730-demo-02` | **WORKED** — Drive id `1kjaRhMY…`, 604,670-byte PNG | **PASSED** — the requested orange funnel, 1254x1254 | **PASSED** — downloaded with NO credentials, SHA-256 `d6633736…` matched the claim exactly |

**Run 2 closed the loop: the full chain is proven.** ChatGPT read the repo,
generated the right image, uploaded it to Drive, wrote the pointer to git, and
our consumer pulled it down and verified the bytes independently. The remaining
real-world caveat is that ChatGPT's image tool is present in some task runs and
absent in others — which is exactly why Phase B self-fills and a backstop cron
exists (`docs/EXCHANGE_PIPELINE.md`).

This per-request `exchange/requests/` flow is now superseded for the daily run
by the **one-pass bundle** at `exchange/bundles/<date>/bundle.json`, which
carries the day's scripts, media health, and gaps together. This directory
remains valid for one-off manual requests.

**Prompt-following note for any task reading this:** you reach these
instructions by reading a code repository, which biases the image tool toward
screenshots, UIs, terminals, and code. Run 1 failed exactly that way. Use the
request's `prompt_verbatim` word for word and its `negative` list as
exclusions; the repo is where the instruction lives, never the subject. Report
`image.prompt_used` so a prompt miss is distinguishable from a transport
failure.

## Public sharing

The Drive connector may not expose "Anyone with the link". Workaround:
upload into a Drive folder that was **manually made link-visible beforehand**
— files inherit the folder's permission, so the consumer can fetch without
credentials. If that is not in place, the consumer falls back to the
authenticated Drive API path.

## Consuming a response

```bash
python scripts/fetch_exchange_media.py                 # all pending
python scripts/fetch_exchange_media.py --id <req_id>   # one
```

Downloads to `cache/exchange/<request_id>.<ext>` (gitignored), verifies
SHA-256 and image decodability, and prints the local path for the render to
use. Non-zero exit on any unusable response.

## Rules

- Write only under `exchange/responses/`. Never commit image bytes here.
- One response file per `request_id`, named exactly `<request_id>.json`.
- Requests live on `main`; responses are committed to `main` too (they are
  small JSON, which `main` is for).
- Never bypass a login or paywall to obtain source material.
