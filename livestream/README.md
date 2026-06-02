# livestream/ — Cabin Hours background-loop generator

The visual engine for **Cabin Hours**, a cozy lo-fi channel (*cozy lofi to
study, work & sleep*). Builds a **seamless, branded background loop** for a 24/7
YouTube livestream and hands it off to an always-on encoder. Runs **weekly**,
low-frequency. See **[BRAND.md](BRAND.md)** for the full brand playbook.

Fully isolated from the daily money-maker:
- own entry point (`build_loop.py`), own trigger (`.github/workflows/livestream.yml`),
- writes only under `livestream/outbox/` (gitignored),
- never imports or touches `make_short.py`, the daily orchestrator, `state/`,
  the catalog, or the `PAUSED` switch. A crash here cannot affect the daily run.

## What it does

1. Picks a **visual world** by date (`themes.py`; override with `--theme`). Each
   world shares the brand's cabin-by-a-frozen-pond anchor and carries
   context-first packaging (`title`/`task`/`palette`/`playlists`). December
   rotates to *Cabin Holidays*; other months map to their season's world.
2. Calls `shared.visualgen.generate_scene_clip` to render the world — a detailed
   stylized scene (sky, aurora, mist, the cabin homestead, skating pond with
   string lights, particles) **seamless by construction, no external media, no APIs.**
3. Pins the channel logo (`branding.py`) on every frame.
4. Writes `loop_<theme>_<date>.mp4` + a `.manifest.json` (with the ready-to-use
   upload title and playlist tags) to `outbox/` and calls the handoff.

```bash
python livestream/build_loop.py                    # world by date, 60s loop
python livestream/build_loop.py --theme holiday    # force a world
python livestream/build_loop.py --loop-seconds 90  # slower, calmer drift
python livestream/build_loop.py --render-scale 0.5 # faster render, slightly softer
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
