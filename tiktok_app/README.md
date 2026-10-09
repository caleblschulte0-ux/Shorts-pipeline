# Shorts Media — the TikTok app site (shorts-media.netlify.app)

Shorts Media is a library for videos you already keep somewhere public —
the release assets of a GitHub repository, or any direct https link to a
video file — from which you post to a TikTok account you authorized, one
video at a time, with the settings you choose. It is TikTok's approved app
("Shorts Media"), with Login Kit and the Content Posting API.

    connect at /app/  ──►  TikTok consent  ──►  /auth/tiktok/callback/
         account + refresh token saved in Netlify Blobs (store
         "shorts-media-tiktok-accounts"), refreshed by the site
    add a source at /app/  (POST /app/sources)
         GitHub: api.github.com/repos/<owner>/<repo>/releases → every
         .mp4/.mov/.webm asset; direct link: one HEAD request.
         The library (sources + the videos found) is saved per TikTok
         account in Blobs store "shorts-media-libraries". No video is copied.
    post at /app/post/<video id>  ──►  POST /app/posting
         TikTok FILE_UPLOAD in 5 MB chunks: the first chunk goes with the
         post, the status page (/app/status, meta-refresh) moves the rest —
         one chunk per request, so any size fits Netlify's 10 s limit — then
         polls TikTok until PUBLISH_COMPLETE. /app/draft/<id> is the inbox
         (draft) flow on the same machinery.
    GitHub Actions job on main (id-token: write)
         ──► POST /api/tiktok/token  (GitHub OIDC JWT; repo id, main only)
         ◄── fresh access token  ──►  shared/uploaders.TikTokUploader

No TikTok token is kept in GitHub secrets. Which linked account a channel
posts to is `channels.<id>.tiktok.handle` in `config/channel_registry.json`
(override: repo variable `TIKTOK_HANDLE_<CHANNEL>`); a channel with no handle
does not post, and `channels.<id>.tiktok.post: false` switches a channel off
even with a handle (only explainer posts for now). Every publishing channel cross-posts through
`shared/crosspost.py` after its gated YouTube upload succeeds. To see what is
linked, run the `tiktok_accounts` workflow on main.

| channel | TikTok | posting |
|---|---|---|
| trending (Baller Bro 2.0) | @ballerbro2.1 | off |
| third (Thirdbraindown) | @third.brain.down | off |
| explainer (short_explainer67) | @shortexplainer1 | on |

## What is in git, what is not

- `netlify/functions/app.js` — the one self-contained function (the
  `@netlify/blobs` client is vendored at the top; the app starts at
  `// livev2/netlify/functions/app.js`).
- `site/` — the public pages and the app stylesheet, plain HTML/CSS.
- NOT in git: media (`app-assets/media/*`, icons, favicon). Those come from
  the last deployed drop, which the build takes as its base.
- NOT in git: the TikTok client secret. The function reads
  `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` and `SM_COOKIE_SECRET` from
  the site's Netlify environment variables first, so a drop built with
  `--placeholders` carries no secret at all. (`--config local.json` still
  fills them in for a drag-and-drop deploy.)
- Optional: `GITHUB_TOKEN` in the Netlify environment raises the GitHub
  API rate limit for reading releases (public data only, no scopes).

## Build and deploy

```bash
python scripts/build_tiktok_drop.py --base <last-drop>.zip --placeholders \
    --out Shorts-Media-Drop.zip
unzip Shorts-Media-Drop.zip -d drop && cd drop
netlify deploy --prod --dir . --functions netlify/functions --site shorts-media
```

Check: `https://shorts-media.netlify.app/app/` shows "Connect TikTok". If it
is a 404, the function did not deploy. If connecting fails with "Client key
or secret is incorrect", the Netlify environment variables are missing.

## Tests

`node tiktok_app/test_site.js` runs the whole flow offline (fake Blobs with
eventual consistency, fake TikTok, fake GitHub, a fake video host that
serves byte ranges, real signed OIDC tokens); `tests/test_tiktok_site.py`
runs it in CI together with the build script and the workflow checks.

## Why the earlier builds did not link anything

- v4 (sandbox): worked, but carried the sandbox client key, so only sandbox
  users could connect and the token lived in a 24h cookie nobody could use.
- 2026-09 ChatGPT build: right design, but a Lambda-compat function must call
  `connectLambda(event)` before any Blobs call and cannot do strong reads. It
  did neither, so every callback failed with "The environment has not been
  configured to use Netlify Blobs". And nothing in the pipeline ever asked
  the site for a token.
- v9 (2026-09-29) and earlier showed one hard-coded sample video: TikTok's
  Content Posting API audit does not approve a tool that only posts its
  owner's own files, so the library above replaced it (2026-09-30).
