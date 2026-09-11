# Shorts Media — TikTok app-review demo

A user-facing demonstration of the complete TikTok integration flow, built
to answer the reviewer's rejection:

> "The demo video should show the complete end-to-end flow of the
> integrations with TikTok (Please demonstrate with sandbox or provide a
> mockup demo). The video should show the user interaction interface, not
> the code."

## Run it

```bash
python demo/tiktok_review/serve.py
# then open  http://localhost:8770/
```

First run pulls a real vertical Short out of the `preview-renders` branch
into `media/` (gitignored — `docs/STORAGE_AUDIT.md` forbids committing
media). If that branch is not fetched, run `git fetch origin preview-renders`
and restart; the demo still works without it, with a still frame instead of
a playable preview.

## What it is, and is not

It makes **no network calls**. `SANDBOX` in `app.js` is the canned
`creator_info` response a real client receives from
`/v2/post/publish/creator_info/query/`, and publishing is simulated on a
timer. Nothing is posted to any TikTok account.

Every screen that could be mistaken for a real result says so: a banner
across the top, and a line in the success card. **Do not remove them.**
Claiming a simulated post was a real one is a worse failure than the
rejection this exists to fix, and TikTok explicitly permitted a mockup.

## Direct Post requirements, implemented as behaviour

Each of these is a rule a reviewer checks, and each is enforced in
`App.refresh()` rather than merely labelled:

| Requirement | How it is met |
|---|---|
| Creator nickname shown | From `creator_info`, on the header pill and the post screen |
| Preview before posting | Real 1080×1920 `<video controls>` |
| Title/caption editable | Textarea, 2200-char counter |
| Privacy manually selected | Placeholder option, **no default**; publish disabled until chosen |
| Privacy options are the creator's | Built from `privacy_level_options` |
| Comment/Duet/Stitch off by default | All three start unchecked |
| Creator's own restrictions honoured | `*_disabled` locks the toggle off and shows why |
| Commercial disclosure available | Toggle, default **off** |
| Disclosure requires a type | "Your brand" / "Branded content"; publish blocked until one is picked |
| Branded content cannot be private | `SELF_ONLY` disabled, and cleared if already chosen |
| Correct consent copy | Music Usage Confirmation; adds Branded Content Policy when branded |
| Consent immediately above the button | Yes |
| Upload only on explicit action | Nothing happens until **Post to TikTok** is clicked |
| Processing expectations set | Success card explains TikTok may take several minutes |

## Scopes

`SCOPES` in `app.js` drives the consent screen. It currently lists:

- `user.info.basic` (Login Kit) — shows which account you are posting to
- `video.publish` (Content Posting API — Direct Post) — publishes the video

**Confirm this matches your app's Products tab before recording.** TikTok
requires every requested product and scope to be demonstrated; a scope that
never appears in the demo can fail the review on its own, and one you do not
need is worth removing from the application.

The repo's own `shared/uploaders.py` only ever references `video.publish`.

## Files

```
demo/tiktok_review/
  index.html     the interface
  app.js         flow + the Direct Post rules
  styles.css     look tokens derived from shared/look.py
  serve.py       static server + one-time sample-video fetch
  avatar.svg     placeholder creator avatar
  favicon.svg
  media/         gitignored; populated at first run
```

## Isolation

Nothing here is imported by the pipeline, no workflow references it, and it
writes nothing outside its own directory. To remove it entirely:

```bash
git rm -r demo/tiktok_review
```
