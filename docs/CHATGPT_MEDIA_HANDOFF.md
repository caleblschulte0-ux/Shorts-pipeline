# ChatGPT media handoff — the landing zone

ChatGPT (no API key, running as a **scheduled task** with a GitHub connector)
generates images/animations for the day's videos and pushes them back here.
This doc is the contract. It is the only file a ChatGPT task needs to read.

**Status: CONNECTIVITY TEST.** Nothing here is wired into a channel renderer
yet. The first job is to prove ChatGPT can (a) read a request out of this repo
and (b) push finished assets back into it. Everything else waits on that.

---

## The loop

```
this repo  ──►  state/media_requests/<date>.json   (what we need today)
                          │
                          ▼
                   ChatGPT task reads it, generates the assets
                          │
                          ▼
repo branch  ◄──  media-dropbox : drops/<date>/<request_id>/…  + drop_manifest.json
                          │
                          ▼
       our render job pulls the drop, uses the assets, never merges them to main
```

## Instructions for the ChatGPT task

Paste this as the scheduled-task prompt:

> Go to the GitHub repo `caleblschulte0-ux/Shorts-pipeline`. Read
> `docs/CHATGPT_MEDIA_HANDOFF.md`, then read the newest file in
> `state/media_requests/` whose `status` is `open`. For each entry in
> `requests`, generate the asset described by its `prompt` at the given size
> and in one of its `accepts` formats. Then commit the files to the
> **`media-dropbox`** branch under `drops/<date>/<request_id>/`, and write a
> `drops/<date>/drop_manifest.json` following the schema in the handoff doc.
> Do not push to `main`. Do not modify any file outside `drops/`.
> If you cannot produce a given asset type at all, still write the manifest
> and mark that request `"status": "unsupported"` with a reason.

## Where things go

| What | Where | Branch |
|---|---|---|
| Requests (we write) | `state/media_requests/<date>.json` | `main` |
| Assets (ChatGPT writes) | `drops/<date>/<request_id>/<files>` | **`media-dropbox`** |
| Drop manifest (ChatGPT writes) | `drops/<date>/drop_manifest.json` | **`media-dropbox`** |

**Assets never land on `main`.** `main` carries small JSON only — that rule
exists because committed media already blew up this repo's history once and
had to be surgically purged (`docs/STORAGE_AUDIT.md` §7). The `media-dropbox`
branch is an orphan (no shared history with `main`), so it can be deleted and
recreated at any time without touching the pipeline's real history.

## Drop manifest schema

`drops/<date>/drop_manifest.json`:

```json
{
  "schema": "chatgpt-media-drop/v1",
  "date": "2026-07-29",
  "source_request": "state/media_requests/2026-07-29-test.json",
  "generated_by": "chatgpt-scheduled-task",
  "generated_at": "2026-07-29T14:00:00Z",
  "results": [
    {
      "request_id": "test-image-001",
      "status": "fulfilled",
      "format": "png",
      "files": ["drops/2026-07-29/test-image-001/hero.png"],
      "notes": ""
    },
    {
      "request_id": "test-animation-001",
      "status": "unsupported",
      "format": null,
      "files": [],
      "notes": "why it could not be produced"
    }
  ]
}
```

`status` is one of `fulfilled` | `partial` | `unsupported` | `failed`.
An honest `unsupported` is a **passing** test result — it tells us what the
connector can actually do. A silently-empty drop is a failing one.

## Rules for the generated assets

- No text, watermarks, logos, or signatures baked into images unless the
  request explicitly asks for them.
- Respect `width`/`height` and `max_bytes` from the request.
- Only the formats listed in that request's `accepts`.
- One directory per `request_id`. No files outside `drops/`.
- Animations: **numbered PNG frames are the preferred delivery.** We compose
  them into video with ffmpeg ourselves, which sidesteps whether the task can
  emit real video at all.

## Checking a drop

```bash
python scripts/check_media_dropbox.py --date 2026-07-29
```

Fetches the `media-dropbox` branch, matches the drop manifest against the
request manifest, and reports per-request status, file presence, and sizes.
Exit code is non-zero if a drop is malformed or missing.

## Open question this test answers

Whether a ChatGPT scheduled task can commit to a **non-default branch** at all.
If it can only write to `main`, the test will show that, and the fallback is a
GitHub Release or an artifact upload instead of a branch — same manifest
contract either way.
