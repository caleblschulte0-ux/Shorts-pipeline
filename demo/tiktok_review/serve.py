#!/usr/bin/env python3
"""Serve the TikTok app-review demo, and fetch its sample video first.

    python demo/tiktok_review/serve.py        # then open http://localhost:8770

WHY A SCRIPT AND NOT `python -m http.server`. The demo needs a real vertical
Short to preview, and `docs/STORAGE_AUDIT.md` forbids committing media to
this repo (mp4/png renders, anything over 256KB). So the video is not in the
tree: it is pulled out of the `preview-renders` orphan branch at first run
into `media/`, which is gitignored. That keeps the storage rule intact and
still gives the reviewer a genuine channel video rather than a placeholder.

If the branch is not available (a fresh clone that has not fetched it), the
demo still runs — the player falls back to a poster frame — and this prints
the one command needed to get the video.

This touches nothing in the production pipeline. It is a static file server
on a high port plus one `git show`.
"""
from __future__ import annotations

import http.server
import shutil
import socketserver
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MEDIA = HERE / "media"
PORT = 8770

# A real explainer Short (1080x1920), living on the preview-renders branch.
BRANCH = "origin/preview-renders"
VIDEO_IN_BRANCH = ("output/repair_runs/urban-growth-just-hit-a-50-year-low-of-1-36/"
                   "20260824T154110Z/attempt_1/video.mp4")
POSTER_IN_BRANCH = ("blocked/story_urban-growth-just-hit-a-50-year-low-of-1-36"
                    ".frame30.png")


def _extract(path_in_branch: str, dest: Path) -> bool:
    """Copy one blob out of the preview branch. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        out = subprocess.run(
            ["git", "show", f"{BRANCH}:{path_in_branch}"],
            cwd=REPO, capture_output=True, timeout=120)
    except Exception:                                    # noqa: BLE001
        return False
    if out.returncode != 0 or not out.stdout:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(out.stdout)
    return True


def fetch_sample() -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    have_video = _extract(VIDEO_IN_BRANCH, MEDIA / "sample-short.mp4")
    _extract(POSTER_IN_BRANCH, MEDIA / "sample-poster.png")

    if have_video:
        mb = (MEDIA / "sample-short.mp4").stat().st_size / 1e6
        print(f"  sample video ready ({mb:.1f} MB)")
    else:
        print("  NOTE: sample video not found locally. The demo still runs,")
        print("        but the preview will be a still frame. To get it:")
        print("          git fetch origin preview-renders")
        print("        then restart this script.")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def end_headers(self):
        # No caching: re-recording after an edit should never serve a stale page.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):        # quiet: this gets screen-recorded
        pass


def main() -> int:
    print("Shorts Media — TikTok review demo")
    fetch_sample()
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
            print(f"\n  OPEN THIS:  http://localhost:{PORT}/\n")
            print("  Ctrl-C to stop.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    except OSError as e:
        print(f"could not bind port {PORT}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
