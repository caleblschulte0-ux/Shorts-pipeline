# Media Acquisition Doctrine

*Adopted 2026-07-10 (operator directive, distilled from an external draft —
adapted to this repo's reality). Governs how every channel finds, admits,
and documents images/video. Companion docs: `docs/ENGINE_REGISTRY.md`
(rendering capabilities), `docs/STORAGE_AUDIT.md` (where files live).*

**The standard:** the viewer should see the real evidence when the real
evidence materially improves the explanation. Generic licensed media is for
interchangeable decoration; relevant copyrighted evidence is NOT replaced
with weak stock merely to avoid all risk. The goal is not zero copyright
risk — it is confident, deliberate, proportionate, well-documented use.

---

## 1. Source classes

Every funnel candidate carries a `source_class` (set in
`media_funnel._prefilter`, recorded in the audit sidecar):

| Class | Meaning | Current members |
|---|---|---|
| `open_or_licensed` | License expressly permits the use | Openverse, iNaturalist, GBIF, NASA, DVIDS, LoC, Met, Wikidata/Commons, Pexels, Pixabay, Wikimedia, Internet Archive |
| `primary_source` | Published by the org/person involved | (lane exists; discovery adapters are tickets M2/M3) |
| `transformative_evidence` | Copyrighted media used AS evidence in commentary/reporting | news-API photos + og:image heroes; `TOPIC_VIDEO_ALLOW_STRIKES=1` YouTube lane |
| `permission_granted` | Owner said yes, in writing | (workflow is ticket M8) |
| `unverified` | Provenance unclear | Imgur, social providers — lowest base scores |

## 2. Admission rules for copyrighted media (condensed)

Copyrighted ≠ rejected. An asset without a license may air when ALL hold:
1. **Direct engagement** — the script substantively discusses the specific
   thing shown (not loose thematic vibes).
2. **Real function** — proves it happened / shows what was said / compares
   works. Never filler, atmosphere, or decoration.
3. **Proportionate amount** — shortest excerpt that makes the point; still
   frame when motion adds nothing; stop showing it when narration moves on.
4. **Transformative purpose** — new meaning from the editorial treatment
   (cropping/subtitles/gameplay-underneath do NOT count by themselves).
5. **No market substitution** — never reproduce the original's payoff or
   its best-moments compilation.
6. **Extra caution** for high-creativity works (film/TV/music/sports); music
   is never background — only when the music itself is the subject.
7. **Documented** — source URL, owner-if-known, amount, narration lines it
   supports, why proportionate, why non-substitutive (audit sidecar).

Uncertainty alone doesn't reject valuable media; weak editorial connection,
decorative use, excessive amount, unknown provenance, or substitution risk
does. Fallback order on rejection: licensed exact media → official primary
source → still frame → procedural/engine visual → AI recreation →
permission request → generic stock last.

## 3. Risk classes

- **GREEN (auto-use + document):** statements being discussed, post
  screenshots as evidence, ad claims being examined, incident footage being
  reported on, official demos.
- **YELLOW (mitigate or flag):** film/TV, sports, recognizable music,
  premium documentary, creator entertainment. Mitigations: shorten, still-
  frame, mute original audio, interleave analysis, crop to the evidence.
- **RED (reject):** unrelated copyrighted B-roll, scenes-for-atmosphere,
  song hooks for listening value, highlight compilations, provenance-less
  assets, anything acquired by bypassing DRM/paywalls/rate limits.

**Acquisition rule:** discoverability ≠ permission. Never bypass access
controls; when a platform has no clean path, store the candidate URL for
operator review instead of building circumvention.

## 4. Search priority by story function

- **Specific event/statement/product:** exact primary source → official
  account → licensed version of the exact media → copyrighted evidence tied
  to the script → permission → engine/AI reconstruction → stock last.
- **Interchangeable B-roll:** open/licensed → internal cache → procedural →
  AI-gen → stock. Copyrighted evidence is never used just because it's
  prettier.
- **Historical:** LoC → Internet Archive → Commons → Met/museums →
  newsreels (rights-lane checked).
- **Science/space:** NASA/agency → labs/papers → Commons → engines
  (Manim/Blender) → documentary footage only when the documentary itself is
  the subject.
- **Breaking news:** official source → original eyewitness uploader →
  reputable publisher → (ticketed: YouTube evidence lane, social lanes).

## 5. Current provider inventory (funnel, 2026-07-10)

18 parallel providers in `media_funnel.py`: 5 news APIs (keyed) + Imgur +
Vimeo/YouTube thumbs + **10 licensed-lane sources**: Openverse,
iNaturalist, NASA, **Wikidata P18 (canonical entity image), Library of
Congress, Met Museum (CC0), GBIF, Pexels-images, Pixabay-images,
DVIDS-images** (the last three reuse keys already in CI). Plus og:image
expansion with Wayback fallback, URL dedup, verification, entity gate,
freshness/host boosts, cross-video repetition penalty, LLM rerank.
`topic_media` adds Wikipedia hero + full article image set + Commons +
Openverse + GDELT.

## 6. Implementation status (nothing left as an unowned ticket — items are
either DONE or BLOCKED on a specific operator action, per operator ruling
2026-07-10: "no one is coming to fix them")

**Done (2026-07-10):**
- **M1 — Admission documentation.** Every sub-cut in the audit sidecar now
  records `source_class`, `license`, and source `url` alongside the
  existing tier/sources fields (`make_explainer_stacked` audit block).
- **M2 v1 — Official-source detection on YouTube.** `p_youtube` marks
  results whose channel name matches the entity as `primary_source`
  ("official channel upload"). Full timestamped-excerpt lane remains
  governed by the existing `TOPIC_VIDEO_ALLOW_STRIKES` opt-in.
- **M3 v1 — Government primary-source lane.** Any candidate whose page or
  image host is `.gov`/`.mil` is classified `primary_source`, licensed
  "US government media", and score-boosted +0.10 — regardless of which
  provider surfaced it. (A dedicated GDELT gov-domain provider was probed
  and returned zero usable articles — not built, on evidence.)
- **M7 v1 — Art Institute of Chicago** (`p_artic`): keyless, CC0-only,
  IIIF URLs. In the fan-out now (19 providers).
- **M8 — Permission workflow tool.** `scripts/request_permission.py`
  drafts the ask, tracks pending/granted/denied in
  `state/permission_requests.json`, and only a recorded GRANT admits the
  asset. The human reply is the one step a machine can't do.
- **M9 — Evidence-URL ingestion.** Packages may set per-shot
  `evidence_url`/`evidence_urls`; the renderer pulls the page's hero
  image via `og_scrape` (Wayback fallback included) as the shot's
  trusted still. The brain browses — when it finds THE post/article
  showing the event, it pins it. Documented in
  CLAUDE_ROUTINE_INSTRUCTIONS.md.

**Pre-wired — code is DONE and fail-closed; each lights up the moment its
secret appears in repo Settings → Secrets → Actions (no code change):**
- **Smithsonian Open Access** (`p_smithsonian`, CC0): secret
  `SMITHSONIAN_KEY` — free instant key at https://api.data.gov/signup
- **National Park Service** (`p_nps`, PD): secret `NPS_KEY` — same
  api.data.gov key works.
- **Europeana** (`p_europeana`, open-reusability filter): secret
  `EUROPEANA_KEY` — free at https://pro.europeana.eu/get-api
- **Reddit eyewitness lane** (authed `p_reddit` via OAuth
  client-credentials — works from CI IPs where anonymous 403s): secrets
  `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` — create a "script" app at
  https://www.reddit.com/prefs/apps
- **Bluesky lane** (authed `p_bluesky` via app password): secrets
  `BLUESKY_HANDLE` + `BLUESKY_APP_PASSWORD` — bsky.app → Settings →
  App Passwords.
All seven secrets are already plumbed through daily.yml/preview.yml env.

**Still blocked (no clean automatable path — revisit on a real trigger):**
- **M5 — Ad libraries.** Meta Ad Library API needs identity-verified
  developer access AND its ads_archive endpoint returns snapshot HTML,
  not image URLs — needs rendering R&D, not just a key. Google Ads
  Transparency has no public API. Revisit if a marketing-claims story
  format actually launches.
- **M6 — Academic/patent figures.** No keyless API serves usable figure
  images (arXiv og:images are logos; PMC figure extraction is real R&D).
  Build against real stories when a science-paper format exists.
- **Mastodon** stays behind `MEDIA_FUNNEL_SOCIAL=1` (needs an
  instance-specific account token; low expected yield).

## 7. Anti-fear rule (permanent)

Do not optimize for avoiding all copyrighted material. Optimize for the
strongest material with a real editorial purpose, defensible source,
proportionate excerpt, new context, documentation, and controlled claim
risk. Approve strong uses confidently; reject weak uses confidently.
