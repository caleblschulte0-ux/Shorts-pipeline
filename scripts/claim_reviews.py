#!/usr/bin/env python3
"""Claim ChatGPT's mailbox verdicts: CODE decides, then the kept render ships.

The other half of `shared/review_mailbox.py`. A render run that had no
judge kept its mp4 as a workflow artifact and filed a request; ChatGPT
graded the frames into `<id>.verdict.json`. This step:

  1. reads each open request that has a verdict — refusing one that names
     another request or another video hash (`review_mailbox.verdict_for`);
  2. assembles the verdict with `showrunner_review.assemble_verdict`, the
     SAME function every judge's grades go through: schema check, code-
     computed score, motion override, `decide_verdict`;
  3. hands it to `showrunner_gate.decide(will_upload=True, ...)` — the same
     fail-closed policy, the same floor. Only an explicit ship proceeds;
  4. appends the verdict to the showrunner ledger with
     `judge: chatgpt-mailbox`, so the retro and Aletheia's pulse (which
     already watches that file) can see who judged what;
  5. with `--publish` and a ship: downloads the artifact, verifies its
     sha256 against the request, and uploads through the channel's
     ordinary uploader, recording the posted log the way the channel does.
     A hash mismatch is refused, not retried.
  6. settles the request beside itself (`<id>.done.json`), append-only.

With `--rejudge`, a request nobody has answered is first shown to the
SHOWRUNNER ITSELF once it can watch again (2026-10-07, operator: *"I
thought between ChatGPT and Aletheia, we could never have the issue of no
judge available"*). "No judge" was meant to DELAY a video, never lose it,
but the mailbox only helps if somebody answers it, and from 09-21 to
10-07 nobody did: the held renders sat there after the headless brain's
weekly limit reset. So the claim run asks the same `_judge` the render
run asked, with the request's own verbatim prompt and frames, writes the
answer as `by: showrunner:<backend>`, and lets the ordinary claim decide
it. Nothing about the bar moves: the same prompt, the same grades, the
same `assemble_verdict` + `showrunner_gate.decide`, and a judge that is
still out leaves the request open. A request that can never publish (its
story already posted or gone, its trending package gone) is WITHDRAWN
first, so no judge is spent on it.

A hold is settled too: the story stays in its queue and the next render
run tries it fresh — the 48h block memory in `post_stories` rotates it to
the back of the line like any other block.

    python scripts/claim_reviews.py --channel all            # decide + log
    python scripts/claim_reviews.py --channel explainer --publish
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from shared import review_mailbox as rm                     # noqa: E402

JUDGE = "chatgpt-mailbox"
API = "https://api.github.com"
#: The `by` a re-judged verdict carries (`showrunner:headless-claude`).
REJUDGE_BY = "showrunner"
#: At most this many re-judges per claim run: the claim cron is hourly and
#: the judge's budget is the same subscription the morning's renders use.
MAX_REJUDGE = int(os.environ.get("CLAIM_MAX_REJUDGE", "2"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """GitHub answers an artifact download with a 302 to a signed blob URL
    that must be fetched WITHOUT the Authorization header (forwarding it
    fails the request). Capture the Location instead of following."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        raise _Redirect(newurl)


class _Redirect(Exception):
    def __init__(self, url):
        super().__init__(url)
        self.url = url


def _gh(path: str, token: str) -> dict:
    req = urllib.request.Request(
        API + path, headers={"Authorization": f"Bearer {token}",
                             "Accept": "application/vnd.github+json",
                             "User-Agent": "shorts-pipeline-claim"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def download_artifact(run_id: str, name: str, member: str, dest: Path,
                      token: str | None = None) -> Path:
    """Fetch `member` out of the named artifact of `run_id` into `dest`."""
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to download the kept render")
    repo = rm.repo_slug()
    arts = _gh(f"/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100", token)
    art = next((a for a in arts.get("artifacts", []) if a.get("name") == name), None)
    if not art:
        raise RuntimeError(f"artifact {name!r} not found on run {run_id} "
                           f"(expired, or the run never uploaded it)")
    if art.get("expired"):
        raise RuntimeError(f"artifact {name!r} has expired")
    opener = urllib.request.build_opener(_NoRedirect())
    req = urllib.request.Request(
        art["archive_download_url"],
        headers={"Authorization": f"Bearer {token}",
                 "User-Agent": "shorts-pipeline-claim"})
    try:
        with opener.open(req, timeout=60) as r:
            blob = r.read()
    except _Redirect as rd:
        with urllib.request.urlopen(
                urllib.request.Request(rd.url, headers={"User-Agent": "shorts-pipeline-claim"}),
                timeout=600) as r:
            blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        if member not in zf.namelist():
            raise RuntimeError(f"{member!r} is not in artifact {name!r}: {zf.namelist()[:8]}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zf.read(member))
        for side in (".manifest.json", ".showrunner.json"):
            sm = member[:-4] + side
            if sm in zf.namelist():
                dest.with_suffix(side).write_bytes(zf.read(sm))
    return dest


def decide_request(req: dict, grades: dict,
                   judge: str = JUDGE) -> tuple[dict, dict]:
    """(verdict, gate) — the judge's grades through the judge's own code.
    `judge` names who graded (provenance only): every grader's grades go
    through this same code."""
    from scripts import showrunner_review as sr
    from shared import showrunner_gate as gate_mod
    verdict = sr.assemble_verdict(grades, motion=req.get("motion") or {},
                                  temporal=req.get("temporal") or {}, backend=judge)
    gate = gate_mod.decide(will_upload=True, gate_on=True, verdict=verdict)
    gate["slug"] = req["slug"]
    return verdict, gate


def _publish_explainer(req: dict, mp4: Path, verdict: dict,
                       judge: str = JUDGE) -> str:
    from scripts import post_stories as ps
    from shared.uploaders import YouTubeUploader
    cfg = json.loads(ps.CONFIG.read_text())
    sc = next((s for s in cfg.get("stories", []) if s.get("slug") == req["slug"]), None)
    if not sc:
        raise RuntimeError(f"story {req['slug']!r} is no longer in niche.config.json")
    log = ps._load_log(ps.LOG_PATH)
    prev = (log.get("posted") or {}).get(req["slug"])
    if isinstance(prev, dict) and prev.get("state") == "posted" and prev.get("url"):
        raise RuntimeError(f"{req['slug']} is already posted: {prev['url']}")
    claim = {"title": sc.get("title"), "publish_at": None, "url": None,
             "state": "uploading", "claimed_at": _now(), "via": judge}
    log.setdefault("posted", {})[req["slug"]] = claim
    log.setdefault("uploads", []).append(dict(claim, slug=req["slug"]))
    ps._save_log(log, ps.LOG_PATH)
    ps._persist_posted_log_now(ps.LOG_PATH, req["slug"], why="claim upload slot (mailbox)")
    res = YouTubeUploader(channel="explainer").upload(
        file_path=mp4, title=sc.get("title", req["slug"])[:100],
        description=ps._description(sc), tags=ps._merged_tags(sc), publish_at=None)
    url = getattr(res, "url", None) or str(res)
    log = ps._load_log(ps.LOG_PATH)
    log["posted"][req["slug"]] = {
        "url": url, "title": sc.get("title"), "at": _now(), "publish_at": None,
        "state": "posted", "via": judge,
        **ps._creative_facts(req["slug"], sc, mp4, verdict)}
    for u in reversed(log.get("uploads") or []):
        if u.get("slug") == req["slug"] and u.get("state") == "uploading":
            u.update({"url": url, "state": "posted", "at": log["posted"][req["slug"]]["at"]})
            break
    ps._save_log(log, ps.LOG_PATH)
    ps._persist_posted_log_now(ps.LOG_PATH, req["slug"])
    from shared.crosspost import crosspost
    crosspost("explainer", mp4, sc.get("title", req["slug"])[:100],
              ps._description(sc), ps._merged_tags(sc))
    return url


def _publish_trending(req: dict, mp4: Path, judge: str = JUDGE) -> str:
    from scripts import run_trending_daily as rt
    from shared.uploaders import YouTubeUploader
    pkg_path = (req.get("ctx") or {}).get("package")
    if not pkg_path or not (REPO / pkg_path).exists():
        raise RuntimeError(f"the request's package {pkg_path!r} is gone")
    pkg = json.loads((REPO / pkg_path).read_text())
    topic = (req.get("ctx") or {}).get("topic") or pkg.get("topic") or req["slug"]
    channel = (pkg.get("channel") or "").strip().lower()
    title = (req.get("title") or pkg.get("title") or topic)[:100]
    # The same claim -> upload -> record path every trending upload takes,
    # so a mailbox ship can never race a render run into a duplicate (the
    # 2026-09-28/29 double uploads). It raises on a topic already posted.
    url = rt._guarded_upload(
        title=title, topic=topic, fmt=pkg.get("format"), publish_at=None,
        do_upload=lambda: (lambda r: getattr(r, "url", None) or str(r))(
            YouTubeUploader(channel=channel).upload(
                file_path=mp4, title=title, description=rt._description(pkg),
                tags=rt._tags(pkg), publish_at=None)))
    log = rt.load_log()
    for e in reversed(log.get("posted") or []):
        if e.get("video_url") == url:
            e["via"] = judge
            break
    rt.save_log(log)
    from shared.crosspost import crosspost
    crosspost("trending", mp4, (req.get("title") or pkg.get("title") or topic)[:100],
              rt._description(pkg), rt._tags(pkg))
    return url


def claim(req: dict, *, publish: bool, workdir: Path) -> dict:
    """One request, start to finish. Returns the settlement record (also
    written beside the request when the request is settled)."""
    from scripts import showrunner_review as sr
    from shared import showrunner_gate as gate_mod
    grades, why = rm.verdict_for(req)
    if grades is None:
        return {"id": req["id"], "state": "open", "why": why}
    judge = rm.grader_of(rm.verdict_by(req))
    verdict, gate = decide_request(req, grades, judge)
    gate_mod.log(gate, req["slug"])
    try:
        sr.append_ledger(req["slug"], verdict)
    except Exception:  # noqa: BLE001
        pass
    if gate["blocked"]:
        out = {"decision": "hold", "reason": gate["reason"], "score": verdict.get("score"),
               "judge": judge}
        rm.settle(req, out)
        return {"id": req["id"], "state": "settled", **out}
    if not publish:
        return {"id": req["id"], "state": "ship-pending-publish",
                "score": verdict.get("score")}
    v = req["video"]
    try:
        mp4 = download_artifact(v["artifact_run_id"], v["artifact_name"], v["file"],
                                workdir / v["file"])
        got = rm.sha256_of(mp4)
        if got != req["video_sha256"]:
            raise RuntimeError(f"kept render hash {got[:10]} != request {req['video_sha256'][:10]}")
        if req.get("channel") == "trending":
            url = _publish_trending(req, mp4, judge)
        else:
            url = _publish_explainer(req, mp4, verdict, judge)
    except Exception as e:  # noqa: BLE001
        out = {"decision": "ship", "published": False, "score": verdict.get("score"),
               "judge": judge, "error": f"{type(e).__name__}: {e}"[:300]}
        # settled: a ship that could not be published is not retried
        # forever against an expired artifact; the story re-renders normally
        rm.settle(req, out)
        print(f"[claim] {req['id']}: ship, but could not publish: {out['error']}",
              flush=True)
        return {"id": req["id"], "state": "settled", **out}
    out = {"decision": "ship", "published": True, "url": url,
           "score": verdict.get("score"), "judge": judge}
    rm.settle(req, out)
    print(f"[claim] {req['id']}: SHIPPED -> {url}", flush=True)
    return {"id": req["id"], "state": "settled", **out}


def unpublishable(req: dict) -> str | None:
    """Why this request could never be uploaded even on a ship, or None.
    The same facts `_publish_*` would raise on, checked BEFORE a judge is
    asked: grading a video that cannot post only spends the judge."""
    if req.get("channel") == "trending":
        pkg = (req.get("ctx") or {}).get("package")
        if not pkg or not (REPO / pkg).exists():
            return f"its trending package {pkg!r} is gone"
        return None
    from scripts import post_stories as ps
    try:
        cfg = json.loads(ps.CONFIG.read_text())
    except Exception:  # noqa: BLE001
        return None                       # cannot tell: let the claim decide
    if not any(s.get("slug") == req["slug"] for s in cfg.get("stories", [])):
        return f"story {req['slug']!r} is no longer in niche.config.json"
    prev = (ps._load_log(ps.LOG_PATH).get("posted") or {}).get(req["slug"])
    if isinstance(prev, dict) and prev.get("state") == "posted" and prev.get("url"):
        return f"{req['slug']} is already posted: {prev['url']}"
    return None


def _fetch(url: str, dest: Path) -> Path:
    with urllib.request.urlopen(url, timeout=60) as r:
        dest.write_bytes(r.read())
    return dest


def rejudge(req: dict, workdir: Path) -> str:
    """Ask the showrunner to grade an unanswered request now; write its
    grades as the request's verdict. Returns the backend that graded.
    Raises when no judge can watch (the request stays open)."""
    from scripts import showrunner_review as sr
    d = workdir / f"rejudge-{req['id']}"
    d.mkdir(parents=True, exist_ok=True)
    labeled = []
    for i, f in enumerate(req.get("frames") or []):
        labeled.append((_fetch(f["url"], d / f"f{i:02d}.jpg"),
                        str(f.get("label") or f"f{i}"), float(f.get("t") or 0.0)))
    if not labeled:
        raise RuntimeError("the request has no frames")
    grades, backend = sr._judge(req["prompt"], labeled)
    vp = Path(req["_path"]).parent / f"{req['id']}.verdict.json"
    vp.write_text(json.dumps({
        "schema": rm.VERDICT_SCHEMA, "request_id": req["id"],
        "video_sha256": req["video_sha256"], "by": f"{REJUDGE_BY}:{backend}",
        "graded_at": _now(), "grades": grades}, indent=1) + "\n")
    return backend


def rejudge_open(reqs: list[dict], workdir: Path,
                 limit: int = MAX_REJUDGE) -> list[dict]:
    """Withdraw what can never publish; re-judge up to `limit` of the rest,
    newest first (only the newest cut of a story is worth a judge). Stops
    at the first judge failure: a judge that is out is not asked again."""
    left = []
    for req in reqs:
        if rm.has_verdict(req):
            left.append(req)
            continue
        why = unpublishable(req)
        if why:
            rm.settle(req, {"decision": "withdrawn", "judge": None,
                            "reason": f"cannot publish: {why}"})
            print(f"[claim] withdrawn {req['id']}: {why}", flush=True)
            continue
        left.append(req)
    asked = 0
    for req in sorted(left, key=lambda r: str(r.get("filed") or ""), reverse=True):
        if asked >= limit:
            break
        if rm.has_verdict(req):
            continue
        asked += 1
        try:
            backend = rejudge(req, workdir)
            print(f"[claim] re-judged {req['id']} with {backend}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[claim] {req['id']}: no judge yet ({str(e)[:160]}); "
                  "left open", flush=True)
            break
    return left


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--channel", default="all", choices=["all", "explainer", "trending"])
    ap.add_argument("--publish", action="store_true",
                    help="upload a shipped kept render (needs GITHUB_TOKEN + "
                         "the channel's YouTube secrets)")
    ap.add_argument("--reviews-dir", type=Path, default=None)
    ap.add_argument("--withdraw-stage", type=Path, default=None,
                    help="settle as WITHDRAWN every open request whose frames "
                         "were staged here but never published (the workflow "
                         "calls this when the preview-renders push fails)")
    ap.add_argument("--rejudge", action="store_true",
                    help="show unanswered requests to the showrunner itself "
                         "(up to CLAIM_MAX_REJUDGE a run) and withdraw the "
                         "ones that could never publish")
    args = ap.parse_args()
    if args.withdraw_stage is not None:
        ids = rm.withdraw_staged(
            args.withdraw_stage,
            reason=("unreviewable: the frames never reached preview-renders "
                    "(publish failed) and the render dies with its runner"),
            reviews_dir=args.reviews_dir)
        for rid in ids:
            print(f"[claim] withdrawn {rid}: frames never published", flush=True)
        print(f"[claim] withdrawn {len(ids)}", flush=True)
        return 0
    reqs = rm.open_requests(args.reviews_dir)
    if args.channel != "all":
        reqs = [r for r in reqs if r.get("channel") == args.channel]
    print(f"[claim] {len(reqs)} open request(s)", flush=True)
    settled = 0
    with tempfile.TemporaryDirectory() as td:
        if args.rejudge:
            reqs = rejudge_open(reqs, Path(td))
        for req in reqs:
            res = claim(req, publish=args.publish, workdir=Path(td))
            print(f"[claim] {res['id']}: {res['state']}"
                  + (f" ({res.get('why')})" if res.get("why") else ""), flush=True)
            settled += res["state"] == "settled"
    rm.write_index(args.reviews_dir)
    # After claiming (so an answered older cut is still decided), retire
    # every unanswered request a newer render of the same story replaced.
    for rid in rm.supersede_stale(args.reviews_dir):
        print(f"[claim] superseded {rid}: a newer render was filed", flush=True)
    print(f"[claim] settled {settled}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
