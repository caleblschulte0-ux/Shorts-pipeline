"""THE JUDGE OF LAST RESORT IS A MAILBOX CHATGPT ANSWERS.

Operator, 2026-09-21: *"this should fall back to chatgpt which should
always be available."*

What happened that day, read off the run logs: the explainer rendered four
stories at 17:00 UTC and the showrunner failed CLOSED on every one —

    showrunner BLOCK score=None — showrunner failed on a publish run
    (fail-closed): no vision judge available. ["headless-claude[0]: claude
    CLI rc=1: You've hit your session limit · resets 5:50pm (UTC)",
    "gemini: HTTP Error 429: Too Many Requests"]

The gate was right to hold: a video nobody watched is not a video that
passed. But "nobody available to watch" had exactly two names on the list,
both on quotas that ran out on the same afternoon, and the renders died
with the runner. The fleet's third brain — the ChatGPT subscription that
already answers this repo's media and authoring mailboxes every morning,
and that voices Aletheia — was never asked.

So: when the in-run judges are gone, the RENDER IS KEPT (a workflow
artifact) and a REVIEW REQUEST is filed here, carrying exactly what the
headless judge would have been given — the labelled frames (published as a
contact sheet + individual images on the `preview-renders` branch, never in
`main`), the verbatim grade prompt with the rubric, the measured
motion/temporal evidence, and the video's sha256. ChatGPT answers with the
SAME JSON the judge emits, into `<id>.verdict.json`. The next run reads it
back through the SAME validator, the SAME code-computed score, the SAME
fail-closed `decide()`, and — only on an explicit ship — downloads the kept
artifact, checks its hash, and publishes it through the ordinary upload
path. Held today becomes late, not lost.

WHAT DOES NOT MOVE. ChatGPT grades anchors; CODE decides ship or block,
with the same floor and the same auto-fails as for any judge. A verdict
that names the wrong request, the wrong video hash, or fails the schema is
refused, not repaired. A request is answered once; a settled request is
never re-opened. Nothing here can ship a video the gate has not approved.

WHY A MAILBOX AND NOT A CALL. The ChatGPT subscription has no API; it
works the way the exchange already works — it reads raw files from this
repo on a schedule and commits answers back. That is also how it attaches
to Aletheia's intercom, so the same ChatGPT Project that speaks as Thea can
take the review round without a single change to Aletheia
(`docs/REVIEW_MAILBOX.md`).

Layout (all under `exchange/reviews/<YYYYMMDD>/`):

    <id>.request.json    filed by the render run; the ask
    <id>.verdict.json    written by ChatGPT; the graded anchors
    <id>.done.json       written by the claim step; what code decided

Media (never in main): `preview-renders` branch, `reviews/<date>/<id>/`.
The kept render: workflow artifact `held-renders-<run_id>`, file `<id>.mp4`.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REVIEWS_DIR = REPO / "exchange" / "reviews"
#: Where the render run stages media for `scripts/publish_review_media.sh`
#: to push to the `preview-renders` orphan branch. Mirrors the branch layout
#: so the published path is the staged path.
MEDIA_STAGE = REPO / "output" / "review_media"
#: Where the render run parks a held mp4 for `actions/upload-artifact`.
HELD_DIR = REPO / "output" / "held"
PREVIEW_BRANCH = "preview-renders"
SCHEMA = "shorts-review-request/v1"
VERDICT_SCHEMA = "shorts-review-verdict/v1"

#: The answer's exact shape, restated in the request so the grader never
#: has to guess it — the judge's own contract from `_GRADE_PROMPT`.
ANSWER_SCHEMA = {
    "schema": VERDICT_SCHEMA,
    "request_id": "<the request's id, copied exactly>",
    "video_sha256": "<the request's video_sha256, copied exactly>",
    "by": "chatgpt",
    "graded_at": "<ISO-8601 UTC>",
    "grades": "<the JSON object the prompt asks for: dimensions, checks, "
              "weakest_scene, depictions, one_line, problems, fixes>",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_slug() -> str:
    return os.environ.get("GITHUB_REPOSITORY") or "caleblschulte0-ux/Shorts-pipeline"


def request_id(slug: str, video_sha: str) -> str:
    return f"{slug}__{video_sha[:10]}"


def raw_url(rel: str) -> str:
    """A raw.githubusercontent URL on the preview branch — what ChatGPT can
    open from a scheduled task."""
    return (f"https://raw.githubusercontent.com/{repo_slug()}/"
            f"{PREVIEW_BRANCH}/{rel}")


def build_sheet(labeled, out: Path, cols: int = 4, tile: int = 300) -> Path:
    """One contact sheet of every labelled frame, label printed on the tile.
    The judge Reads frames one at a time; a scheduled ChatGPT task opens
    URLs, and one image it can hold in view beats twelve it has to
    cross-reference."""
    from PIL import Image, ImageDraw, ImageFont
    frames = list(labeled)
    if not frames:
        raise ValueError("no frames to sheet")
    th = int(tile * 16 / 9)
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * (th + 34)), (12, 16, 24))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    for i, (p, lab, ts) in enumerate(frames):
        x, y = (i % cols) * tile, (i // cols) * (th + 34)
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((tile, th))
            sheet.paste(im, (x + (tile - im.width) // 2, y))
        except Exception:  # noqa: BLE001 — a missing frame is a blank tile
            pass
        d.text((x + 6, y + th + 8), f"{lab} t={float(ts):.1f}s",
               fill=(255, 255, 255), font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "JPEG", quality=82)
    return out


def file_request(*, mp4: Path, slug: str, labeled, prompt: str, motion: dict,
                 temporal: dict, ctx: dict, mailbox: dict,
                 reviews_dir: Path | None = None, media_stage: Path | None = None,
                 held_dir: Path | None = None) -> str | None:
    """Keep the render, stage its frames, file the ask. Returns the request
    id, or None if anything went wrong — this runs on the failure path of a
    live publish and must never turn a held video into a crashed run."""
    try:
        mp4 = Path(mp4)
        reviews_dir = Path(reviews_dir or REVIEWS_DIR)
        media_stage = Path(media_stage or MEDIA_STAGE)
        held_dir = Path(held_dir or HELD_DIR)
        date = _today()
        sha = sha256_of(mp4)
        rid = request_id(slug, sha)
        day_dir = reviews_dir / date
        day_dir.mkdir(parents=True, exist_ok=True)
        req_path = day_dir / f"{rid}.request.json"
        if req_path.exists():
            return rid                      # same render, already asked
        # 1. the kept render — an artifact the claim step can fetch by name
        held_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mp4, held_dir / f"{rid}.mp4")
        for side in (".manifest.json", ".showrunner.json"):
            sp = mp4.with_suffix(side)
            if sp.exists():
                shutil.copy2(sp, held_dir / f"{rid}{side}")
        # 2. the frames + a contact sheet, staged for the preview branch
        rel_dir = f"reviews/{date}/{rid}"
        stage = media_stage / rel_dir
        stage.mkdir(parents=True, exist_ok=True)
        frames = []
        for i, (p, lab, ts) in enumerate(labeled):
            name = f"f{i:02d}.jpg"
            shutil.copy2(p, stage / name)
            frames.append({"label": lab, "t": round(float(ts), 2),
                           "url": raw_url(f"{rel_dir}/{name}")})
        build_sheet(labeled, stage / "sheet.jpg")
        # 3. the ask
        run_id = str(mailbox.get("run_id") or os.environ.get("GITHUB_RUN_ID") or "")
        req = {
            "schema": SCHEMA, "id": rid, "filed": _now(), "status": "open",
            "channel": str(mailbox.get("channel") or ctx.get("channel") or ""),
            "slug": slug, "title": ctx.get("title"),
            "video_sha256": sha, "video_bytes": mp4.stat().st_size,
            "video": {"artifact_run_id": run_id,
                      "artifact_name": str(mailbox.get("artifact")
                                           or f"held-renders-{run_id}"),
                      "file": f"{rid}.mp4"},
            "sheet_url": raw_url(f"{rel_dir}/sheet.jpg"),
            "frames": frames,
            "prompt": prompt,
            "motion": motion, "temporal": temporal,
            "ctx": {k: v for k, v in ctx.items() if k != "mailbox"},
            "answer_path": f"exchange/reviews/{date}/{rid}.verdict.json",
            "answer_schema": ANSWER_SCHEMA,
            "how_to_answer": (
                "Open sheet_url (and any frame url you need to look closer). "
                "Grade EXACTLY as the prompt says — anchors and hard checks "
                "only; you never output ship or block, the code decides. "
                "Write answer_path as one JSON object matching answer_schema, "
                "with request_id and video_sha256 copied from this file, and "
                "commit it. Do not edit this request. Do not touch anything "
                "else."),
        }
        req_path.write_text(json.dumps(req, indent=1, ensure_ascii=False) + "\n")
        print(f"[mailbox] review request filed: {req_path.relative_to(REPO)} "
              f"(render kept as {req['video']['artifact_name']}/{rid}.mp4)",
              flush=True)
        write_index(reviews_dir)
        return rid
    except Exception as e:  # noqa: BLE001
        print(f"[mailbox] could not file a review request: {type(e).__name__}: {e}",
              flush=True)
        return None


def open_requests(reviews_dir: Path | None = None) -> list[dict]:
    """Every request with no `.done.json` beside it, oldest first."""
    reviews_dir = Path(reviews_dir or REVIEWS_DIR)
    out = []
    if not reviews_dir.exists():
        return out
    for rp in sorted(reviews_dir.glob("*/*.request.json")):
        rid = rp.name[:-len(".request.json")]
        if (rp.parent / f"{rid}.done.json").exists():
            continue
        try:
            req = json.loads(rp.read_text())
        except Exception:  # noqa: BLE001
            continue
        if req.get("schema") != SCHEMA or req.get("id") != rid:
            continue
        req["_path"] = str(rp)
        out.append(req)
    return out


def verdict_for(req: dict) -> tuple[dict | None, str]:
    """The grades ChatGPT wrote for this request — or (None, why not).

    Refused, never repaired: a verdict for another request id, for another
    video hash, or without a grades object is not a verdict for this video.
    """
    vp = Path(req["_path"]).parent / f"{req['id']}.verdict.json"
    if not vp.exists():
        return None, "no verdict yet"
    try:
        v = json.loads(vp.read_text())
    except Exception as e:  # noqa: BLE001
        return None, f"verdict unreadable: {e}"
    if not isinstance(v, dict):
        return None, "verdict is not an object"
    if str(v.get("request_id")) != req["id"]:
        return None, f"verdict names request {v.get('request_id')!r}, not {req['id']!r}"
    if str(v.get("video_sha256")) != req["video_sha256"]:
        return None, "verdict names a different video hash"
    grades = v.get("grades")
    if not isinstance(grades, dict):
        return None, "verdict has no grades object"
    return grades, "ok"


def write_index(reviews_dir: Path | None = None) -> Path | None:
    """`exchange/reviews/OPEN.json` — every open request, with the one URL
    ChatGPT needs per request. A scheduled task cannot list a directory;
    it opens a known file. Rewritten on every file/settle."""
    reviews_dir = Path(reviews_dir or REVIEWS_DIR)
    try:
        reqs = open_requests(reviews_dir)
        idx = {"schema": "shorts-review-index/v1", "updated": _now(),
               "open": [{"id": r["id"], "channel": r.get("channel"),
                         "slug": r["slug"], "title": r.get("title"),
                         "filed": r.get("filed"),
                         "request": str(Path(r["_path"]).relative_to(REPO)),
                         "sheet_url": r.get("sheet_url"),
                         "answer_path": r.get("answer_path")} for r in reqs],
               "how": "For each entry open `request` (raw), grade as it says, "
                      "commit `answer_path`. Never edit a request."}
        reviews_dir.mkdir(parents=True, exist_ok=True)
        ip = reviews_dir / "OPEN.json"
        ip.write_text(json.dumps(idx, indent=1, ensure_ascii=False) + "\n")
        return ip
    except Exception as e:  # noqa: BLE001
        print(f"[mailbox] index not written: {e}", flush=True)
        return None


def settle(req: dict, outcome: dict) -> Path:
    """Record what CODE decided, beside the request. Append-only: a settled
    request is never reopened, and the verdict file is left as written."""
    dp = Path(req["_path"]).parent / f"{req['id']}.done.json"
    rec = {"id": req["id"], "settled": _now(), **outcome}
    dp.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    write_index(dp.parent.parent)
    return dp
