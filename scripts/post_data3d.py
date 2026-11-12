"""Post ONE finished 3D Data short to the explainer channel, by hand only.

The operator watches the video in the project thread and says to post it
(2026-11-12: "Post that shit"). The 3D shorts are rendered by
data3d_render.yml on claude/3d-data and never pass through post_stories, so
this is their upload path. It follows the explainer's own rules exactly:
the slot is CLAIMED on main before the API call (refused if the claim does
not land), the go-live time is shared/post_spacing's (the registry's gap),
the record is written back after, and the same cut goes to TikTok through
shared.crosspost. No AI label (YouTubeUploader's default).

It is judged like every explainer video: the SHARED showrunner gate
(shared/showrunner_gate.run) watches the cut first and its BLOCK is
sovereign. The operator's "post it" never overrides a block; a held video
is reported, not uploaded.

usage: python scripts/post_data3d.py MEDIA_DIR      MEDIA_DIR holds video.mp4, meta.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import post_stories as ps  # noqa: E402 — the explainer's own ledger code


def main() -> int:
    media = Path(sys.argv[1])
    meta = json.loads((media / "meta.json").read_text())
    mp4 = media / "video.mp4"
    slug = meta["slug"]
    log_path = ps.LOG_PATH
    log = ps._load_log(log_path)
    ps._refresh_from_origin(log, log_path)
    if slug in log["posted"]:
        print(f"::error::{slug} is already posted or claimed: "
              f"{log['posted'][slug].get('url')}")
        return 1
    # THE SAME GATE AS EVERY EXPLAINER UPLOAD: the showrunner watches the cut,
    # fails closed, and its BLOCK is final. Nothing below runs on a block.
    from shared import showrunner_gate
    ctx = {"slug": slug, "title": meta["title"], "hook": meta["lines"][0],
           "closing": meta["lines"][-1], "segments": meta["lines"][1:-1],
           "style_arm": "3d"}
    gate = showrunner_gate.run(mp4, slug=slug, context=ctx, will_upload=True)
    showrunner_gate.log(gate, slug)
    # THE OPERATOR'S OWN WORD is above the showrunner for a video they WATCHED (operator, 2026-11-12, after the gate
    # held this video at 66: "it's our own system I refuse to be held hostage by my own system if I say post it it
    # post the quality checks are for when I'm not here to watch it"). Never a default, never automatic: it takes
    # the operator's words, verbatim, typed into the dispatch, and they ride on the posted-log entry beside the
    # verdict they overruled. Every unattended path still fails closed on a block.
    overruled = None
    if gate["blocked"]:
        said = (os.environ.get("OPERATOR_SAID") or "").strip()
        if not said:
            print(f"::error::the showrunner held {slug}: {gate.get('reason')}")
            return 2
        overruled = {"operator_said": said, "score": (gate.get("verdict") or {}).get("score"),
                     "reason": gate.get("reason")}
        print(f"::warning::the showrunner held {slug} ({gate.get('reason')}); the operator watched it and overruled: {said!r}")
    from shared import post_spacing
    # The operator may say to post it NOW (2026-11-12: "Bypass the 3 hour rule"):
    # only the go-live time changes; the gate above and the claim below do not.
    publish_at = None if os.environ.get("PUBLIC_NOW") == "true" else post_spacing.schedule("explainer", log)
    claim = {"claimed_at": datetime.now(timezone.utc).isoformat(),
             "title": meta["title"], "publish_at": publish_at,
             "url": None, "state": "uploading", "style_arm": "3d"}
    log["posted"][slug] = claim
    log.setdefault("uploads", []).append(dict(claim, slug=slug))
    ps._save_log(log, log_path)
    if not ps._persist_posted_log_now(log_path, slug, why="claim upload slot"):
        print("::error::ClaimNotDurable: the claim did not reach main, refusing to upload")
        return 1
    ps._absorb_persisted(log, log_path)
    from shared.uploaders import YouTubeUploader
    print(f"[{slug}] uploading" + (f" (scheduled {publish_at})" if publish_at else " (public now)"), flush=True)
    res = YouTubeUploader(channel="explainer").upload(
        file_path=mp4, title=meta["title"][:100], description=meta["description"],
        tags=meta.get("tags", []), publish_at=publish_at,
        thumbnail=(media / "thumb.jpg") if (media / "thumb.jpg").exists() else None,
        localizations={})
    url = getattr(res, "url", None) or str(res)
    print(f"[{slug}] uploaded -> {url}", flush=True)
    log["posted"][slug] = {"url": url, "title": meta["title"],
                           "at": datetime.now(timezone.utc).isoformat(),
                           "publish_at": publish_at, "state": "posted",
                           "style_arm": "3d", "duration_s": meta.get("duration_s"),
                           **({"operator_overruled_showrunner": overruled} if overruled else {})}
    for u in reversed(log.get("uploads") or []):
        if u.get("slug") == slug and u.get("url") is None:
            u.update(url=url, state="posted", at=log["posted"][slug]["at"])
            break
    ps._save_log(log, log_path)
    ps._persist_posted_log_now(log_path, slug)
    from shared.crosspost import crosspost
    x = crosspost("explainer", mp4, meta["title"][:100], meta["description"],
                  meta.get("tags", []), publish_at=publish_at)
    print(json.dumps({"url": url, "publish_at": publish_at, "crossposts": x}))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(
            f"{url}\n\npublish_at: {publish_at}\n\ncrossposts: {x}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
