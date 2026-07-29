# exchange/ — the shared drop box between the GitHub agent and ChatGPT

A tiny, dumb, file-based mailbox. No server, no API between the two agents: the
repo IS the channel. One side writes a request, the other reads it off GitHub,
does the work, and writes an answer back.

Assets themselves never live here — only pointers. Images go to Google Drive;
this folder holds the paperwork.

## The loop

1. **GitHub side asks.** Writes `requests/<id>.json` — "I need an image of X."
2. **ChatGPT reads it** on GitHub (just look at this folder on the branch).
3. **ChatGPT makes the image** and uploads it to Google Drive.
4. **ChatGPT answers.** Writes `responses/<id>.json` with the Drive link/file id.
5. **GitHub side looks at the image** — resolves the pointer, pulls the file
   down into `cache/exchange/` (gitignored), and uses it.

A request is OPEN until a response file with the same id exists. That is the
entire state machine — no status field to get out of sync.

## Files

    exchange/requests/<id>.json     what is needed
    exchange/responses/<id>.json    where it ended up

Request:

    {"id": "...", "created_at": "...", "from": "...", "to": "...",
     "kind": "image", "brief": "what to make", "purpose": "why we want it",
     "constraints": {"aspect": "16:9", "style": "photographic, no text"}}

Response:

    {"id": "...", "answered_at": "...", "by": "...",
     "drive_url": "https://drive.google.com/file/d/FILEID/view",
     "drive_file_id": "FILEID", "filename": "thing.png", "notes": "..."}

Either side may write either file by hand or by committing it — the tooling
just produces the same JSON. Nothing here is magic.

## Using it

    python3 scripts/exchange.py request --brief "empty wallet on a table" \
        --purpose "payoff beat" --push
    python3 scripts/exchange.py list                 # what is still open
    python3 scripts/exchange.py show <id>
    python3 scripts/exchange.py respond <id> --drive-url "<link>" --push
    python3 scripts/exchange.py fetch <id>           # pull it down to cache/

## Drive sharing

`fetch` downloads over plain HTTPS, so the Drive file must be shared as
**"anyone with the link can view"**. If it is not, fetch says so plainly
instead of writing a broken file.

## Rules

- Never commit the images themselves. `cache/` is gitignored; keep it that way.
- Ids are timestamp-based and unique; do not reuse one for a different ask.
- A response with no reachable file is worse than no response — check the link
  before writing it.
