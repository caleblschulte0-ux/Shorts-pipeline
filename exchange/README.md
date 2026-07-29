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
