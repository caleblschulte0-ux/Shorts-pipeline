# drops/

One directory per day: `drops/<YYYY-MM-DD>/`.

Inside each day:
- `drop_manifest.json` — required, one entry per request id
- `<request_id>/` — the generated files for that request

Requests come from `state/media_requests/<date>.json` on `main`.
Schema and rules: `docs/CHATGPT_MEDIA_HANDOFF.md` on `main`.
