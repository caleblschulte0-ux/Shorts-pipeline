"""Handoff of the finished loop to an always-on encoder.

WHY THIS IS A STUB (and deliberately not faked):
GitHub Actions / cron runners are ephemeral (≤60 min, then destroyed), so they
CANNOT hold an RTMP stream open 24/7. This module's job ends at *producing the
asset and handing it off*. The actual continuous push to YouTube must run on an
always-on encoder you choose later. Until then the default target is `outbox`:
the loop + manifest simply sit in livestream/outbox/ (and are uploaded as a CI
artifact) for a human or encoder to collect.

Select the target with the LIVESTREAM_HANDOFF env var:
    outbox    (default) — leave asset + manifest in the outbox. No push.
    vps       — push to a VPS running an ffmpeg RTMP loop.       [STUB]
    restream  — push/register with a managed loop service.       [STUB]
    obs       — drop into a folder/bucket an OBS box watches.     [STUB]

The three push targets raise NotImplementedError with exactly what to wire, so
a misconfigured run fails loudly instead of pretending it went live.
"""
from __future__ import annotations

import os
from pathlib import Path

TARGET = os.environ.get("LIVESTREAM_HANDOFF", "outbox").strip().lower()


_VPS_STUB = """\
[handoff:vps] NOT WIRED. To go live, implement this push then remove the raise:
  1. Provision an always-on VPS (~$5/mo) with ffmpeg installed.
  2. Copy the loop there:   rsync {loop}  user@HOST:/srv/livestream/loop.mp4
  3. Run a persistent RTMP loop on the box (systemd unit), e.g.:
       ffmpeg -stream_loop -1 -re -i /srv/livestream/loop.mp4 \\
         -c:v libx264 -preset veryfast -b:v 4500k -maxrate 4500k -bufsize 9000k \\
         -g 60 -c:a aac -b:a 128k -f flv \\
         "rtmp://a.rtmp.youtube.com/live2/$YT_STREAM_KEY"
  Needs secret YT_STREAM_KEY on the box (NOT here). The weekly run only
  refreshes /srv/livestream/loop.mp4; the box keeps streaming across swaps.
"""

_RESTREAM_STUB = """\
[handoff:restream] NOT WIRED. To go live with a managed service:
  1. Create a 24/7 "looped video" / "pre-recorded live" event on the service
     (Restream.io, Castr, etc.) pointed at your YouTube channel.
  2. Upload {loop} via their API, or host it and give them the URL.
  3. Store the service API token as a secret on whatever runs this push —
     do not commit it. Implement the upload call here, then remove the raise.
"""

_OBS_STUB = """\
[handoff:obs] NOT WIRED. To go live via an always-on OBS box:
  1. Add a looping Media Source in OBS pointed at a watched folder/bucket.
  2. Publish the loop where OBS can see it, e.g.:
       rclone copy {loop} remote:livestream/loop.mp4
     or scp into the box's watched folder.
  3. Configure OBS -> Stream -> YouTube with your stream key on the box.
  Implement the publish step here, then remove the raise.
"""


def handoff(loop_path: Path, manifest_path: Path) -> None:
    """Dispatch the finished loop to the configured encoder target."""
    if TARGET == "outbox":
        print(f"[handoff] target=outbox — asset ready for pickup:")
        print(f"          loop:     {loop_path}")
        print(f"          manifest: {manifest_path}")
        print("          (no live push: an always-on encoder must collect this)")
        return
    if TARGET == "vps":
        raise NotImplementedError(_VPS_STUB.format(loop=loop_path))
    if TARGET == "restream":
        raise NotImplementedError(_RESTREAM_STUB.format(loop=loop_path))
    if TARGET == "obs":
        raise NotImplementedError(_OBS_STUB.format(loop=loop_path))
    raise ValueError(
        f"unknown LIVESTREAM_HANDOFF={TARGET!r} (use outbox|vps|restream|obs)"
    )
