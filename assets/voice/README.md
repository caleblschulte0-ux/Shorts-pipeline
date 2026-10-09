# Narrator voices (engines/chatterbox_tts.py)

**The channel's voice is Voice 38** (`globe_S_001818.ogg`) on the full
model: caaleb's pick on 2026-10-09 after the finals on two real stories.
One voice for every video.

Ten-second reference clips that Chatterbox clones the explainer's narration
from. The numbers are the ones on the voice lab page; pick one with the repo
variable `CHATTERBOX_VOICE` (and `CHATTERBOX_MODEL`: `turbo` or `full`).

| Voice | File | LibriTTS-R speaker | Utterance |
|---|---|---|---|
| 1 (deep male) | `libritts_r_3000.ogg` | 3000 | `3000_15664_000005_000004` |
| 2 (male) | `libritts_r_2086.ogg` | 2086 | `2086_149220_000047_000003` |
| 3 (male) | `libritts_r_2902.ogg` | 2902 | `2902_9008_000002_000000` |
| 4 (male, lighter) | `libritts_r_3170.ogg` | 3170 | `3170_137482_000002_000000` |
| 5 (female) | `libritts_r_6319.ogg` | 6319 | `6319_64726_000004_000002` |

| Voice | File | GLOBE v2 speaker | Licence |
|---|---|---|---|
| 38 (male, teens, American) | `globe_S_001818.ogg` | `S_001818` | CC0 |

Voice 38 comes from GLOBE v2 (huggingface.co/datasets/MushanW/GLOBE_V2),
an enhanced subset of Mozilla Common Voice released under CC0 1.0: no
credit is required, and none is added. The speaker was found by
voice-print similarity to the lab's earlier favourites and passed an
accent check; the clip is that speaker's longest recordings, silence
trimmed, joined to 10 s (`voice_lab/similar_refs.py` on the `voice-lab`
branch).

Source: LibriTTS-R `dev_clean` (openslr.org/141, tarball SHA-256
`02ea52de47ca670d7ad86e714a6c58b207660a3f8a371ad102156776d2262a0c`), the
first 10 s of each utterance (Chatterbox reads no more than that), mono
Opus 96 kb/s. Cut by `voice_lab/ref_clips.py` on the `voice-lab` branch.

LibriTTS-R is © its authors (Koizumi et al., 2023), licensed CC BY 4.0
(creativecommons.org/licenses/by/4.0/). Every video a LibriTTS-R voice
narrates carries `engines.chatterbox_tts.CREDIT` in its description.
