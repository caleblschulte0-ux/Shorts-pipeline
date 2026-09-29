# Shorts Media — the TikTok app site (shorts-media.netlify.app)

The site that links TikTok accounts to this pipeline. It is TikTok's
approved app ("Shorts Media"), with Login Kit and the Content Posting API.

    connect at /app/  ──►  TikTok consent  ──►  /auth/tiktok/callback/
         account + refresh token saved in Netlify Blobs (store
         "shorts-media-tiktok-accounts"), refreshed by the site
    GitHub Actions job on main (id-token: write)
         ──► POST /api/tiktok/token  (GitHub OIDC JWT; repo id, main only)
         ◄── fresh access token  ──►  shared/uploaders.TikTokUploader

No TikTok token is kept in GitHub secrets. Which linked account a channel
posts to is `channels.<id>.tiktok.handle` in `config/channel_registry.json`
(override: repo variable `TIKTOK_HANDLE_<CHANNEL>`); a channel with no handle
does not post. Every publishing channel cross-posts through
`shared/crosspost.py` after its gated YouTube upload succeeds. To see what is
linked, run the `tiktok_accounts` workflow on main.

| channel | TikTok |
|---|---|
| trending (Baller Bro 2.0) | @ballerbro2.1 |
| third (Thirdbraindown) | @third.brain.down |
| explainer (short_explainer67) | @shortexplainer1 |

## Build and deploy

The static pages and demo media are not in git (media), so the build takes
the last deployed drop as its base. Secrets come from a local JSON — never
commit it, this repo is public.

```bash
python scripts/build_tiktok_drop.py --base <last-drop>.zip \
    --config <local>/config.json --out Shorts-Media-Drop.zip
unzip Shorts-Media-Drop.zip -d drop && cd drop
netlify deploy --prod --dir . --functions netlify/functions
```

Check: `https://shorts-media.netlify.app/app/` shows "Connect TikTok". If it
is a 404, the function did not deploy.

## Why the earlier builds did not link anything

- v4 (sandbox): worked, but carried the sandbox client key, so only sandbox
  users could connect and the token lived in a 24h cookie nobody could use.
- 2026-09 ChatGPT build: right design, but a Lambda-compat function must call
  `connectLambda(event)` before any Blobs call and cannot do strong reads. It
  did neither, so every callback failed with "The environment has not been
  configured to use Netlify Blobs". And nothing in the pipeline ever asked
  the site for a token.

`node tiktok_app/test_site.js` runs the whole flow offline (fake Blobs, fake
TikTok, real signed OIDC tokens); `tests/test_tiktok_site.py` runs it in CI.
