# Shorts-pipeline

Turn any video (Reddit, TikTok, X, Instagram, YouTube, Twitch, local file) into
a 9:16 YouTube Short stacked over a random gameplay loop, with optional
edge-tts voiceover and burned-in TikTok-style auto-captions.

## Setup

```bash
sudo apt-get install -y ffmpeg                 # or: brew install ffmpeg
pip install -r requirements.txt
python seed_gameplay.py                        # downloads ~2 long gameplay clips
```

`seed_gameplay.py` pulls one Subway Surfers + one Minecraft parkour
compilation into `gameplay/`. Drop any other long no-copyright clips in
there too — files are picked by filename substring (`subway`, `minecraft`,
or `random`).

## Usage

```bash
python make_short.py <url_or_file> [--script "voiceover text"] [--gameplay subway|minecraft|random]
```

Examples:

```bash
# Reddit video, no voiceover
python make_short.py https://v.redd.it/ipd4vkvp8m3h1/CMAF_720.mp4

# With voiceover + force Subway Surfers
python make_short.py https://v.redd.it/ipd4vkvp8m3h1/CMAF_720.mp4 \
  --script "Bro just rewrote the laws of physics. Watch his feet barely touch." \
  --gameplay subway

# Local file
python make_short.py ./clips/dunk.mp4 --script "He had to."
```

Output lands in `output/short_YYYYMMDD-HHMMSS.mp4`.

## How it works

1. `yt-dlp` downloads the source (or copies the local file).
2. A random clip from `gameplay/` matching the `--gameplay` tag is trimmed
   to the source length.
3. If `--script` is given, `edge-tts` synthesizes a voiceover; the source
   audio is ducked to 25% and the voiceover mixed in.
4. `openai-whisper` (model from `$WHISPER_MODEL`, default `base`)
   transcribes with word-level timestamps.
5. Words are grouped into 3-word chunks and written to an ASS subtitle
   file styled white/Impact/thick-black-outline, anchored just below the
   stack seam.
6. `ffmpeg` scales+crops both inputs to `1080x960`, vstacks them to
   `1080x1920`, burns the ASS captions, and muxes the mixed audio.

## Notes

- First whisper run downloads the model (~140MB for `base`); export
  `WHISPER_MODEL=tiny` for faster iteration or `small`/`medium` for
  better captions.
- `--keep-temp` leaves the working directory in `/tmp` so you can
  inspect intermediate files.
- The Shorts limit is 60s; longer sources are truncated.
