# livestream/ — weekly themed background-loop generator

Builds a **themed, seamless background loop** for a 24/7 YouTube livestream and
hands it off to an always-on encoder. Runs **weekly**, low-frequency.

Fully isolated from the daily money-maker:
- own entry point (`build_loop.py`), own trigger (`.github/workflows/livestream.yml`),
- writes only under `livestream/outbox/` (gitignored),
- never imports or touches `make_short.py`, the daily orchestrator, `state/`,
  the catalog, or the `PAUSED` switch. A crash here cannot affect the daily run.

## What it does

1. Picks a **theme** by date (`themes.py`; override with `--theme`). December
   rotates to a holiday palette; other months map to their season.
2. Calls the shared visual-gen (`shared.visualgen.generate_abstract_clip`) to
   render a themed abstract animated gradient — **no external media, no APIs.**
3. Assembles a **seamless loop** (`shared.visualgen.make_seamless_loop`,
   boomerang: forward + reverse, so the wrap returns to exactly the first frame).
4. Writes `loop_<theme>_<date>.mp4` + a `.manifest.json` to `outbox/` and calls
   the handoff.

```bash
python livestream/build_loop.py                    # seasonal theme, 30s base -> 60s loop
python livestream/build_loop.py --theme holiday
python livestream/build_loop.py --base-seconds 60  # -> 120s seamless loop
```

## The encoder handoff (deliberately a STUB, not faked)

GitHub Actions / cron runners are ephemeral (≤60 min) and **cannot hold an RTMP
stream open**. So this module ends at *producing the asset*. The continuous push
runs on an **always-on encoder you choose later**. Select via `LIVESTREAM_HANDOFF`:

| value | behavior |
|---|---|
| `outbox` (default) | leave loop + manifest in `outbox/` (uploaded as a CI artifact). No push. |
| `vps` | push to a VPS running `ffmpeg -stream_loop -1 ... -f flv rtmp://...youtube...`. **stub — raises with wiring steps** |
| `restream` | upload/register with a managed loop service (Restream/Castr). **stub** |
| `obs` | drop into a folder/bucket an OBS box watches. **stub** |

The three push targets raise `NotImplementedError` with exactly what to wire, so
a misconfigured run fails loudly instead of pretending it went live. The YouTube
stream key lives on the encoder, **never in this repo**.

To go live: pick a target, implement its push in `handoff.py` (remove the
`raise`), and point the encoder at the weekly-refreshed loop file.
