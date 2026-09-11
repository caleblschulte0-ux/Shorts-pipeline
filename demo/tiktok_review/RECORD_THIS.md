# Directions for the recording agent

You are recording a screen-capture video for a **TikTok Developer app
review**. TikTok rejected the Shorts Media application with this note:

> "The demo video should show the complete end-to-end flow of the
> integrations with TikTok (Please demonstrate with sandbox or provide a
> mockup demo). The video should show the user interaction interface, not
> the code."

Your job is to produce that video. One take, roughly 60–90 seconds, showing
a person using the app.

---

## 0. What must never appear in the frame

The reviewer is checking that this is a real user interface. Any of these
in shot can fail the review on its own:

- terminal / shell / the server output
- code, an editor, GitHub, file explorers
- browser dev tools, the network tab, JSON, API logs
- the TikTok developer dashboard
- your own agent UI, chat window, or cursor overlays
- OS notifications, other browser tabs, bookmarks bar

Record **only** the browser window showing the app. Full-screen the browser
(F11 / macOS full screen) so no tabs or address bar are visible, or crop to
the page area afterwards. Turn on Do Not Disturb before you start.

---

## 1. Setup (do this off-camera)

```bash
cd <repo>
git fetch origin
git checkout claude/tiktok-review-demo
git fetch origin preview-renders          # the sample video lives here
python demo/tiktok_review/serve.py        # leave running
```

It prints `OPEN THIS: http://localhost:8770/`. First run downloads a ~10 MB
sample video; wait for `sample video ready` before recording.

**Check before you record:**

- Browser window **1440×900 or larger**, full-screened.
- Page zoom at 100%.
- Load `http://localhost:8770/` and confirm the first card shows a chart
  thumbnail (not a grey placeholder). If it is grey, the sample video did
  not download — fix that first, the video preview is a required part of
  the demo.
- Hard-refresh (Ctrl/Cmd-Shift-R) so the app starts disconnected. The
  header must show a red **Connect TikTok** button, not an account.

**Recording settings:** 1080p or higher, 30fps, MP4 (H.264). No audio
needed — no narration, no music. Do not add captions or overlays.

---

## 2. The take

Move the mouse deliberately. Pause where marked so the reviewer can read
the control before it changes. Approximate timings in brackets.

| # | Action | Pause after |
|---|---|---|
| 1 | Start on the dashboard. Do nothing. | **3s** |
| 2 | Click **Connect TikTok** (top right) | — |
| 3 | Authorization screen appears listing the permissions | **4s** — must be readable |
| 4 | Click **Authorize** | **3s** — account appears top right |
| 5 | Click the **first video card** ("Urban Growth Just Hit A 50-Year Low") | **2s** |
| 6 | Click **play** on the video preview, let it run | **4s**, then pause it |
| 7 | Click into the **Caption** box, type ` #shorts` at the end | **2s** |
| 8 | Open **"Who can view this video"**, pause on the open list, choose **Everyone** | **3s** — the Post button visibly enables here; let that land |
| 9 | Toggle **Comment** on. Leave Duet and Stitch off. | **2s** |
| 10 | Toggle **Disclose video content** on | **3s** — the two options appear |
| 11 | Tick **Branded content** | **3s** — the consent line above the button gains a Branded Content Policy link |
| 12 | Untick **Branded content**, then toggle **Disclose video content** back off | **2s** |
| 13 | Click **Post to TikTok** | — |
| 14 | Let the status run: Uploading → Processing → Submitted | **4s** on the final note |
| 15 | Click **Done** | **4s** on "Recent posts" showing the video as Posted |
| 16 | Stop recording. | |

Steps 8, 10 and 11 are the ones TikTok specifically looks for — privacy
being chosen manually, the commercial disclosure existing, and the consent
text responding to it. Do not rush them.

---

## 3. If something goes wrong

- **Post button stays greyed out** — a required choice is missing. The grey
  line under the button says which. Usually privacy (step 8).
- **Video preview is black** — the sample did not download. Stop, run
  `git fetch origin preview-renders`, restart the server, start over.
- **You clicked something out of order** — hard-refresh and start the take
  again. A clean single take is worth more than a patched one.
- **Anything unexpected on screen** — start over rather than editing it
  out.

---

## 4. Deliver

- One MP4, 60–90 seconds, no audio.
- Name it `shorts-media-tiktok-review.mp4`.
- Report back: the file path, its duration, and confirmation that no
  terminal, code, dev tools or developer dashboard appeared in any frame.

---

## 5. Two things you must not do

1. **Do not narrate or caption the video claiming a real TikTok post
   occurred.** The app states on screen that it is a sandbox demonstration
   and that nothing reaches a live account. That disclosure is deliberate —
   TikTok's reviewer explicitly permitted a mockup, so the mockup is
   legitimate, but presenting it as a live post would not be. Leave the
   banner and the success-card note in frame.
2. **Do not edit the app to make it look better mid-recording.** If
   something is wrong with the interface, report it instead of changing it.
