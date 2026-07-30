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

## Mode `author` — the takeover (you are the brain today)

`bundle.json` carries a top-level `mode`. Normally it is `"punch_up"` and
your job is media + script editing. When it is **`"author"`**, the channel's
own writing brain (a Claude Routine) did not run and the reserve bank could
not cover the day. **There is no slate. Without you the channel posts
nothing.**

### If there is no bundle at all, author anyway

The takeover exists for the day everything on the Claude side is dead. On
that day the thing that writes `bundle.json` may itself have failed to run,
so **absence of a bundle is not permission to do nothing.** Decide from the
repo, not from the bundle:

1. Look at `state/trending_packages/<today UTC, YYYYMMDD>/`.
2. **Fewer than 6 package files (or the folder does not exist)?** That is a
   takeover day. Write the shortfall as a 2 + 2 + 2 slate per the format
   specs below, and put them in `authored` in
   `exchange/bundles/<date>/response.json` — creating that folder and file
   yourself if they do not exist. Write `DONE` next to it when finished.
3. **6 files already there?** Nothing to author. Do your normal jobs.

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
