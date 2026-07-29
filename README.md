# media-dropbox — ChatGPT asset drop zone

**Orphan branch. No shared history with `main`. Safe to delete and recreate.**

ChatGPT scheduled tasks push generated images/animations here. Nothing on this
branch is ever merged into `main` — `main` carries small JSON only, because
committed media already blew up this repo's history once and had to be purged.

The contract lives on `main`: **`docs/CHATGPT_MEDIA_HANDOFF.md`**.

## Layout

```
drops/<YYYY-MM-DD>/drop_manifest.json      what was made, per request id
drops/<YYYY-MM-DD>/<request_id>/<files>    the assets themselves
```

## Rules

- Write only under `drops/`. Never touch `main`.
- One directory per `request_id`, named exactly as the request's `id`.
- Every drop needs a `drop_manifest.json` — see the handoff doc for the schema.
- An honest `"status": "unsupported"` beats a silently empty drop.

## Verify a drop

From a checkout of `main`:

```bash
python scripts/check_media_dropbox.py --date <YYYY-MM-DD>
```

## Cleanup

This branch is disposable. Once a day's assets are consumed by a render they
can be deleted; if it ever gets heavy, delete the branch outright and push a
fresh orphan — no pipeline history depends on it.
