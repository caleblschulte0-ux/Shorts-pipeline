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

## 6. Tickets (implementation order — one per session, opt-in, no channel
breakage; mirror of the external draft's phases minus what shipped today)

- **M1 — Admission-decision output.** Extend the audit sidecar to a per-
  asset manifest with the §2 documentation fields + an
  `APPROVED_*/REVIEW/REJECTED` verdict string per visual.
- **M2 — YouTube evidence lane.** Data-API discovery + channel/official-
  source verification + timestamped excerpt selection under §2 rules.
  Builds on the existing `TOPIC_VIDEO_ALLOW_STRIKES` opt-in; keeps it
  opt-in per package.
- **M3 — Official press-room/government discovery.** Company newsrooms,
  agency pressrooms, gov YouTube channels → `primary_source` lane.
- **M4 — Social evidence lanes (Bluesky/Mastodon/Reddit).** Providers exist
  but are gated off (CI IPs get 403s) — needs authed access; capture
  poster/original-source metadata per §2.7.
- **M5 — Ad libraries** (Meta Ad Library, Google Ads Transparency) for
  marketing-claim stories → `primary_source`/`transformative_evidence`.
- **M6 — Academic/patent sources** (arXiv, PMC figures, USPTO/Google
  Patents diagrams) with per-figure licenses.
- **M7 — More open collections:** Smithsonian OA, Europeana, Art Institute
  of Chicago, NYPL, BHL, NPS/USFWS, CDC PHIL (mostly free keys — needs
  operator signups; wire like the keyless providers).
- **M8 — Creator-permission workflow** → `permission_granted` registry.
- **M9 — TikTok/Instagram/X candidate ingestion** (operator- or
  research-supplied URLs only; no scraping around platform terms).

## 7. Anti-fear rule (permanent)

Do not optimize for avoiding all copyrighted material. Optimize for the
strongest material with a real editorial purpose, defensible source,
proportionate excerpt, new context, documentation, and controlled claim
risk. Approve strong uses confidently; reject weak uses confidently.
