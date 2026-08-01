#!/usr/bin/env python3
"""Dry-run the whole split-worker day, offline, in eight steps.

The 06:00 MEDIA worker and the 07:00 FINALIZER are ChatGPT scheduled tasks —
we cannot run them, and we only find out they misread the contract after a day
of videos has already been lost. This fixture stands in for both of them and
exercises the repository half of the handshake end to end:

    1. Phase A publishes the ask, with a deterministic Drive filename and a
       bundle identity, BEFORE any worker starts.
    2. The media worker claims a request, generates it, verifies the bytes and
       writes a checkpoint.
    3. It then DIES mid-run: request two is uploaded but its checkpoint never
       lands, and its claim is left behind to expire.
    4. The finalizer recovers — reuses checkpoint one, and finds request two
       as an orphan by its exact filename.
    5. Adopting the orphan means downloading and hashing it, then writing the
       checkpoint from what was actually there.
    6. The finalizer authors a package and checkpoints its shot images under
       `authored-<slug>-s<n>` ids.
    7. It writes response.json, then DONE as a separate step.
    8. Phase B validates every pointer against its checkpoint — and a hash
       edited after the fact is refused.

No network, no Drive, no ChatGPT: images are real PNGs served over `file://`,
so the actual download + SHA-256 + decode + placeholder path runs.

    python scripts/exchange_dry_run.py            # human-readable
    python scripts/exchange_dry_run.py --json     # machine-readable

Exit 0 = every step behaved. Exit 1 = the contract is broken somewhere; the
failing step is named.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from funnel import media_judge                       # noqa: E402
from shared import exchange_bundle as xb             # noqa: E402
from shared import media_checkpoint as mc            # noqa: E402

DATE = "29991231"

PKG = {
    "slug": "dry-run-story",
    "title": "A Dry Run",
    "script": ("A raccoon walked into a bank. It left with nothing. The "
               "manager described the incident as unusual."),
    "shots": [
        {"phrase": "A raccoon walked into a bank", "query": "raccoon"},
        {"phrase": "It left with nothing", "query": "empty bank lobby"},
    ],
}

AUTHORED = {
    "slug": "dry-run-authored",
    "subreddit": "pettyrevenge",
    "title": "Authored In The Takeover",
    "script": ("My neighbour kept parking in my spot. So I called the city. "
               "They towed him twice in one week."),
    "shots": [{"phrase": "My neighbour kept parking in my spot",
               "query": "parked car"}],
}


class Fixture:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="exchange-dryrun-"))
        self.saved = (mc.BUNDLE_ROOT, xb.BUNDLE_ROOT)
        mc.BUNDLE_ROOT = xb.BUNDLE_ROOT = self.tmp / "bundles"
        self.drive = self.tmp / "drive"          # stands in for Google Drive
        self.drive.mkdir(parents=True, exist_ok=True)
        self.steps: list[dict] = []

    def close(self):
        mc.BUNDLE_ROOT, xb.BUNDLE_ROOT = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- assertions -------------------------------------------------------
    def step(self, n, name):
        self.steps.append({"step": n, "name": name, "checks": [], "ok": True})
        return self.steps[-1]

    def check(self, step, ok, detail):
        step["checks"].append({"ok": bool(ok), "detail": detail})
        if not ok:
            step["ok"] = False
        return bool(ok)

    # -- the fake Drive ---------------------------------------------------
    def upload(self, filename: str, *, flat: bool = False) -> dict:
        """Write a real PNG under the deterministic name; return a pointer."""
        from PIL import Image
        im = Image.new("RGB", (96, 96))
        if not flat:
            seed = sum(filename.encode()) % 97 + 1
            im.putdata([((x * seed) % 256, (y * 7) % 256, (x + y) % 256)
                        for y in range(96) for x in range(96)])
        path = self.drive / filename
        im.save(path)
        blob = path.read_bytes()
        return {
            "path": path,
            "file_id": hashlib.sha1(filename.encode()).hexdigest()[:16],
            "download_url": f"file://{path}",
            "sha256": hashlib.sha256(blob).hexdigest(),
            "bytes": len(blob),
            "width": 96, "height": 96, "format": "png",
        }

    def listing(self) -> list[dict]:
        return [{"name": p.name, "id": hashlib.sha1(p.name.encode())
                 .hexdigest()[:16]} for p in sorted(self.drive.iterdir())]

    @staticmethod
    def pointer(up: dict, request_id: str) -> dict:
        return {
            "request_id": request_id,
            "status": "fulfilled",
            "drive": {"file_id": up["file_id"],
                      "folder_id": "dry-run-folder",
                      "download_url": up["download_url"],
                      "filename": Path(up["path"]).name,
                      "sharing": "anyone_with_link"},
            "image": {"sha256": up["sha256"], "bytes": up["bytes"],
                      "format": up["format"], "width": up["width"],
                      "height": up["height"]},
        }

    def checkpoint(self, up, request_id, *, bundle_id, prompt, worker,
                   kind="bundle_request", package_id=None, shot_index=None):
        cp = mc.build_checkpoint(
            date=DATE, request_id=request_id, bundle_id=bundle_id,
            request_kind=kind, package_id=package_id, shot_index=shot_index,
            prompt=prompt, prompt_used=prompt, worker=worker,
            drive={"file_id": up["file_id"],
                   "download_url": up["download_url"],
                   "filename": Path(up["path"]).name,
                   "folder_id": "dry-run-folder",
                   "sharing": "anyone_with_link"},
            image={"sha256": up["sha256"], "bytes": up["bytes"],
                   "format": up["format"], "width": up["width"],
                   "height": up["height"]})
        mc.write_checkpoint(DATE, cp)
        return cp


def run(verbose: bool = True) -> dict:              # noqa: C901
    fx = Fixture()
    try:
        # -- 1. Phase A publishes the ask -----------------------------------
        s = fx.step(1, "Phase A publishes filenames and identity up front")
        report = media_judge.judge_package(PKG, None)
        xb.write_bundle(DATE, [PKG], [report])
        bundle = xb.read_bundle(DATE)
        mc.write_bundle_identity(DATE, bundle)
        bid = mc.bundle_identity(DATE)
        reqs = bundle.get("requests") or []
        fx.check(s, len(reqs) >= 2, f"{len(reqs)} request(s) in the bundle")
        fx.check(s, bool(bid), "bundle identity computed from bundle.json")
        fx.check(s, all(r.get("drive_filename") ==
                        mc.deterministic_filename(DATE, r["request_id"])
                        for r in reqs),
                 "every request carries its deterministic Drive filename")
        fx.check(s, bundle.get("media_protocol", {}).get("schema") == mc.SCHEMA,
                 "the media protocol ships inside the bundle")
        r1, r2 = reqs[0], reqs[1]

        # -- 2. The media worker does request one ---------------------------
        s = fx.step(2, "Media worker claims, generates, verifies, checkpoints")
        granted = mc.create_claim(DATE, r1["request_id"], worker="media",
                                  worker_run_id="media-run-1", bundle_id=bid)
        fx.check(s, granted["granted"], "claim granted")
        up1 = fx.upload(r1["drive_filename"])
        fx.checkpoint(up1, r1["request_id"], bundle_id=bid,
                      prompt=r1["prompt_verbatim"], worker="media")
        mc.release_claim(DATE, r1["request_id"])
        fx.check(s, mc.read_checkpoint(DATE, r1["request_id"]) is not None,
                 "checkpoint on disk immediately, not batched to the end")

        # -- 3. …then dies mid-run ------------------------------------------
        s = fx.step(3, "Media worker dies after uploading request two")
        past = mc._utcnow() - timedelta(hours=2)
        mc.create_claim(DATE, r2["request_id"], worker="media",
                        worker_run_id="media-run-1", bundle_id=bid,
                        lease_seconds=300, now=past)
        up2 = fx.upload(r2["drive_filename"])         # uploaded, uncheckpointed
        fx.check(s, mc.read_checkpoint(DATE, r2["request_id"]) is None,
                 "request two has no checkpoint — an orphan on Drive")
        fx.check(s, not mc.claim_active(mc.read_claim(DATE, r2["request_id"])),
                 "its abandoned claim has expired and no longer blocks")

        # -- 3b. PHASE A RE-RUNS MID-FLIGHT ---------------------------------
        # The 2026-08-01 failure. Phase A fires on every auto-merge; that day
        # it rewrote bundle.json six times, the last FIVE HOURS after the
        # media worker finished. When identity was the file's sha256, every
        # checkpoint written before that rewrite was orphaned — and a DONE run
        # requires checkpoints, so all 17 verified images would have been
        # refused. The ask did not change; only the file did.
        s = fx.step(3, "Phase A re-runs mid-flight without orphaning anything")
        s["step"] = 3.5
        before = mc.bundle_identity(DATE)
        rejudged = media_judge.judge_package(PKG, None)
        xb.write_bundle(DATE, [PKG], [rejudged])       # rewrites the file
        mc.write_bundle_identity(DATE, xb.read_bundle(DATE))
        fx.check(s, mc.bundle_identity(DATE) == before,
                 "identity survived a Phase A rewrite (the ask did not change)")
        fx.check(s, mc.checkpoint_reusable(
            mc.read_checkpoint(DATE, r1["request_id"]), date=DATE,
            bundle_id=mc.bundle_identity(DATE),
            request_id=r1["request_id"], prompt=r1["prompt_verbatim"]),
            "the media worker's checkpoint is still valid afterwards")
        bid = mc.bundle_identity(DATE)

        # -- 4. The finalizer recovers --------------------------------------
        s = fx.step(4, "Finalizer recovers instead of regenerating")
        p1 = mc.plan_recovery(date=DATE, request_id=r1["request_id"],
                              bundle_id=bid, prompt=r1["prompt_verbatim"],
                              drive_listing=fx.listing(),
                              worker_run_id="final-run-1")
        p2 = mc.plan_recovery(date=DATE, request_id=r2["request_id"],
                              bundle_id=bid, prompt=r2["prompt_verbatim"],
                              drive_listing=fx.listing(),
                              worker_run_id="final-run-1")
        fx.check(s, p1["action"] == "reuse_checkpoint",
                 f"request one -> {p1['action']} (no wasted generation)")
        fx.check(s, p2["action"] == "adopt_orphan",
                 f"request two -> {p2['action']} (found by exact filename)")

        # -- 5. Adoption verifies bytes, never a filename -------------------
        s = fx.step(5, "Adoption hashes the actual bytes before trusting it")
        blob = Path(fx.drive / r2["drive_filename"]).read_bytes()
        got = hashlib.sha256(blob).hexdigest()
        fx.check(s, got == up2["sha256"],
                 "orphan re-hashed from its bytes on adoption")
        fx.checkpoint(up2, r2["request_id"], bundle_id=bid,
                      prompt=r2["prompt_verbatim"], worker="finalizer")
        fx.check(s, mc.checkpoint_reusable(
            mc.read_checkpoint(DATE, r2["request_id"]), date=DATE,
            bundle_id=bid, request_id=r2["request_id"],
            prompt=r2["prompt_verbatim"]),
            "the adopted orphan is now a first-class checkpoint")

        # -- 6. Authored package shots --------------------------------------
        s = fx.step(6, "Authored shots checkpoint under authored-<slug>-s<n>")
        arid = mc.authored_shot_request_id(AUTHORED["slug"], 0)
        up3 = fx.upload(mc.deterministic_filename(DATE, arid))
        fx.checkpoint(up3, arid, bundle_id=bid, prompt="an authored shot",
                      worker="finalizer", kind="authored_shot",
                      package_id=AUTHORED["slug"], shot_index=0)
        fx.check(s, arid == "authored-dry-run-authored-s0",
                 f"id derived from slug + shot index only: {arid}")

        # -- 7. response.json, then DONE, separately ------------------------
        s = fx.step(7, "response.json first, DONE as a second step")
        authored = json.loads(json.dumps(AUTHORED))
        authored["shots"][0]["media"] = fx.pointer(up3, arid)
        response = {
            "schema": "chatgpt-exchange-response/v1",
            "media": [fx.pointer(up1, r1["request_id"]),
                      fx.pointer(up2, r2["request_id"])],
            "authored": [authored],
            "packages": [{"slug": PKG["slug"], "kept": True,
                          "editor_note": "dry run — no rewrite"}],
        }
        d = mc.bundle_dir(DATE)
        (d / "response.json").write_text(json.dumps(response, indent=2))
        fx.check(s, xb.read_response(DATE) is not None,
                 "response.json parses when read back")
        fx.check(s, not xb.is_done(DATE), "DONE not written yet")
        (d / "DONE").write_text(json.dumps({"date": DATE}))
        fx.check(s, xb.is_done(DATE), "DONE written only after the read-back")

        # -- 8. Phase B validates, and refuses a tampered pointer -----------
        s = fx.step(8, "Phase B validates every pointer against its checkpoint")
        clean = mc.validate_response_media(response, bundle, date=DATE,
                                           bundle_id=bid,
                                           require_checkpoint=True)
        fx.check(s, clean["counts"]["checked"] == 3,
                 f"{clean['counts']['checked']} pointers checked "
                 f"(2 bundle + 1 authored shot)")
        fx.check(s, not clean["rejected"],
                 f"nothing refused: {clean['rejected']}")

        tampered = json.loads(json.dumps(response))
        tampered["media"][0]["image"]["sha256"] = "c" * 64
        bad = mc.validate_response_media(tampered, bundle, date=DATE,
                                         bundle_id=bid)
        fx.check(s, len(bad["rejected"]) == 1
                 and any("image.sha256 disagrees" in p
                         for p in bad["rejected"][0]["problems"]),
                 "a hash edited after the fact is refused")

        # Two requests pointing at one Drive file. Caught twice over: the
        # deterministic filename can only belong to one of them, and the
        # one-file-one-request rule catches whatever slips past that.
        shared = json.loads(json.dumps(response))
        shared["media"][1]["drive"]["file_id"] = \
            shared["media"][0]["drive"]["file_id"]
        dupe = mc.validate_response_media(shared, bundle, date=DATE,
                                          bundle_id=bid)
        fx.check(s, dupe["rejected"],
                 "one Drive file under two request ids is refused")

        private = json.loads(json.dumps(response))
        private["media"][0]["drive"]["sharing"] = "private"
        shut = mc.validate_response_media(private, bundle, date=DATE,
                                          bundle_id=bid)
        fx.check(s, any("sharing disagrees" in p
                        for r in shut["rejected"] for p in r["problems"]),
                 "a pointer that is not link-visible is refused")

        misplaced = json.loads(json.dumps(response))
        misplaced["media"].append(fx.pointer(up3, arid))
        misfiled = mc.validate_response_media(misplaced, bundle, date=DATE,
                                              bundle_id=bid)
        fx.check(s, any("must ride ON THE SHOT" in p
                        for r in misfiled["rejected"] for p in r["problems"]),
                 "an authored shot's image in the top-level array is refused")

        steps = fx.steps
    finally:
        fx.close()

    ok = all(st["ok"] for st in steps)
    out = {"date": DATE, "ok": ok, "steps": steps,
           "passed": sum(1 for st in steps if st["ok"]), "total": len(steps)}
    if verbose:
        for st in steps:
            mark = "PASS" if st["ok"] else "FAIL"
            print(f"[{mark}] step {st['step']}: {st['name']}")
            for c in st["checks"]:
                print(f"        {'ok ' if c['ok'] else 'NO '} {c['detail']}")
        print(f"\n{out['passed']}/{out['total']} steps passed — "
              f"{'contract holds' if ok else 'CONTRACT BROKEN'}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = run(verbose=not args.json)
    if args.json:
        print(json.dumps(out, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
