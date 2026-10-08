# Narrator voices (engines/chatterbox_tts.py)

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

Source: LibriTTS-R `dev_clean` (openslr.org/141, tarball SHA-256
`02ea52de47ca670d7ad86e714a6c58b207660a3f8a371ad102156776d2262a0c`), the
first 10 s of each utterance (Chatterbox reads no more than that), mono
Opus 96 kb/s. Cut by `voice_lab/ref_clips.py` on the `voice-lab` branch.

LibriTTS-R is © its authors (Koizumi et al., 2023), licensed CC BY 4.0
(creativecommons.org/licenses/by/4.0/). Every video one of these voices
narrates carries `engines.chatterbox_tts.CREDIT` in its description.
