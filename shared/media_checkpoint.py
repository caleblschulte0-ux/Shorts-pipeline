"""Media checkpoints — durable, per-request memory for the split ChatGPT day.

The exchange used to be one task doing everything in one pass. It is now TWO
scheduled workers an hour apart:

    06:00 Central   MEDIA worker      generate + upload + verify images
    07:00 Central   FINALIZER worker  recover, fill gaps, punch up, author,
                                      write response.json, then DONE

Two workers sharing one job need shared memory, because the second one cannot
see the first one's chat context — only the repo. Without it the finalizer
either re-generates everything the media worker already made (burning the
budget and producing different images than the ones on Drive) or trusts a
filename it never verified. Both have happened.

This module is that memory. One small JSON per request:

    exchange/bundles/<date>/media-progress/<safe_request_id>.json

plus a create-only lease so the two workers never generate the same image at
the same moment:

    exchange/bundles/<date>/media-progress/claims/<safe_request_id>.json

Three properties do the real work:

  * **Deterministic filenames.** `20260731__<safe_request_id>.png` is computed
    from the request alone and is published IN THE BUNDLE before either worker
    starts. That is what makes an orphan recoverable: if a checkpoint is lost
    but the file reached Drive, the finalizer can find it by name.
  * **A filename is never proof.** Adopting an orphan means downloading it,
    hashing the bytes, and writing the checkpoint from what was actually
    there. A name is a lookup key, not evidence.
  * **Bundle identity.** Every checkpoint records the sha256 of the exact
    `bundle.json` it was made for. Re-run Phase A with different prompts and
    yesterday's checkpoints stop matching — no silent reuse of an image made
    for a line that no longer exists.

Nothing here touches Google Drive. `plan_recovery()` takes a listing as DATA
so the WORKER (which already holds the Drive connector) does the API calls;
the production pipeline gains no Drive dependency, only a validator.

    from shared import media_checkpoint as mc
    rid  = mc.authored_shot_request_id("kangaroo-court", 3)
    name = mc.deterministic_filename("20260731", rid)
    cp   = mc.read_checkpoint("20260731", rid)
    ok   = mc.checkpoint_reusable(cp, date="20260731", bundle_id=bid,
                                  request_id=rid, prompt=prompt)

Never raises on bad input: every reader returns None/[] so a corrupt
checkpoint degrades to "generate it again", never to a crashed run.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from shared.fsutil import atomic_write_json

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = ROOT / "exchange" / "bundles"

SCHEMA = "chatgpt-media-checkpoint/v1"
CLAIM_SCHEMA = "chatgpt-media-claim/v1"
SCHEMA_VERSION = 1

PROGRESS_DIRNAME = "media-progress"
CLAIMS_DIRNAME = "claims"

#: A lease is a courtesy, not a lock. 15 minutes is longer than any single
#: image generation and far shorter than the hour between the two workers, so
#: a crashed media worker never blocks the finalizer.
DEFAULT_LEASE_SECONDS = 900

REQUEST_KINDS = ("bundle_request", "authored_shot")
STATUSES = ("in_progress", "verified", "failed", "skipped")
SHARING_STATES = ("anyone_with_link", "domain", "private", "unknown")
#: The only sharing state we can actually consume. Drive serves an HTML
#: permission page instead of bytes for anything else, so "we uploaded it" and
#: "you can fetch it" are different claims and only this one covers both.
PUBLIC_SHARING = "anyone_with_link"

#: Every field a response pointer and its checkpoint must agree on, exactly.
#: Hash + bytes alone is not enough: an image that verifies byte-for-byte can
#: still be sitting in the wrong folder, under the wrong name (so nobody can
#: recover it), or private (so nobody can fetch it). Agreement on the bytes is
#: agreement about content; these are agreement about the ASSET.
AGREEMENT_FIELDS = (
    ("drive", "filename"), ("drive", "file_id"), ("drive", "folder_id"),
    ("image", "sha256"), ("image", "bytes"), ("image", "format"),
    ("image", "width"), ("image", "height"),
)

#: Extensions we will accept as a generated asset. `jpeg` normalizes to `jpg`
#: so one image cannot occupy two filenames.
_EXT_ALIASES = {"jpeg": "jpg", "jpe": "jpg", "tif": "tiff"}
ALLOWED_EXTS = ("png", "jpg", "webp", "gif", "tiff", "mp4", "svg")

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# --------------------------------------------------------------------------
# time
# --------------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    dt = dt or _utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text) -> datetime | None:
    try:
        s = str(text or "").strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:                                    # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# ids, filenames, paths
# --------------------------------------------------------------------------
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_SLUGGY = re.compile(r"[^a-z0-9-]+")
_MAX_SAFE = 72


def normalize_date(date) -> str:
    """`2026-07-31` and `20260731` are the same day. Filenames use the latter."""
    return re.sub(r"[^0-9]", "", str(date or ""))[:8]


def safe_request_id(request_id) -> str:
    """A filename-safe id that NEVER collapses two different requests into one.

    Sanitizing alone is not injective — `a/b` and `a:b` both become `a-b`, and
    then two different prompts write the same checkpoint and the same Drive
    file. So whenever sanitizing changed anything (or had to truncate), an
    8-hex digest of the ORIGINAL string is appended. Distinct inputs therefore
    keep distinct outputs, and an already-safe id is left exactly as it was so
    the common case stays readable.

    ChatGPT output is untrusted input and this string becomes a path, so `..`,
    leading dots and separators are all gone by construction."""
    raw = str(request_id or "")
    cleaned = _UNSAFE.sub("-", raw)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._")
    truncated = cleaned[:_MAX_SAFE]
    if cleaned == raw and cleaned and len(cleaned) <= _MAX_SAFE:
        return cleaned
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    stem = truncated or "req"
    return f"{stem}-{digest}"


def _norm_package_id(package_id) -> str:
    """The same normalization `authoring_brief.safe_slug` applies on promotion.

    It has to match: ChatGPT computes the shot's request id from the slug it
    WROTE, and `ingest_authored` rewrites that slug through `safe_slug` before
    the package lands on disk. If the two normalizations disagreed, every
    authored-shot checkpoint would be orphaned the moment the package was
    promoted. `tests/test_media_checkpoint.py` fails if they drift."""
    s = _SLUGGY.sub("-", str(package_id or "").lower()).strip("-")
    return (s or "authored")[:60]


def authored_shot_request_id(package_id, shot_index) -> str:
    """Stable id for a shot inside a package ChatGPT authored itself.

    Derived from `<package_id> + <shot_index>` ONLY — no prompt, no timestamp,
    no counter. That is the point: the media worker computes it at 06:00 from
    the package it just wrote, and the finalizer recomputes the identical
    string at 07:00 from the package on disk. A content-addressed id (like
    `exchange_bundle.request_key`) could not survive a re-worded prompt, and a
    re-worded prompt is exactly what the finalizer's punch-up produces."""
    try:
        idx = int(shot_index)
    except Exception:                                    # noqa: BLE001
        idx = 0
    return f"authored-{_norm_package_id(package_id)}-s{max(0, idx)}"


_AUTHORED_RE = re.compile(r"^authored-(?P<pkg>.+)-s(?P<idx>\d+)$")


def parse_authored_shot_request_id(request_id) -> tuple[str, int] | None:
    m = _AUTHORED_RE.match(str(request_id or ""))
    if not m:
        return None
    return m.group("pkg"), int(m.group("idx"))


def is_authored_shot_request(request_id) -> bool:
    return parse_authored_shot_request_id(request_id) is not None


def normalize_ext(fmt) -> str:
    ext = str(fmt or "png").strip().lower().lstrip(".")
    ext = _EXT_ALIASES.get(ext, ext)
    return ext if ext in ALLOWED_EXTS else "png"


def deterministic_filename(date, request_id, fmt: str = "png") -> str:
    """`20260731__<safe_request_id>.png` — computable by anyone, before anyone.

    Published in the bundle so it exists BEFORE the media worker runs. That
    ordering is the whole reason orphan recovery works: a file can only be
    found by name if the name was agreed on in advance."""
    return (f"{normalize_date(date)}__{safe_request_id(request_id)}"
            f".{normalize_ext(fmt)}")


_FILENAME_RE = re.compile(r"^(?P<date>\d{8})__(?P<rid>[A-Za-z0-9._-]+)"
                          r"\.(?P<ext>[A-Za-z0-9]+)$")


def parse_filename(name) -> dict | None:
    """Split a deterministic filename back apart, or None if it is not one."""
    m = _FILENAME_RE.match(str(name or "").strip())
    if not m:
        return None
    return {"date": m.group("date"), "safe_request_id": m.group("rid"),
            "ext": m.group("ext").lower()}


def sharing_of(drive) -> str:
    """Normalized sharing state, tolerating the older `public: true` shape."""
    if not isinstance(drive, dict):
        return "unknown"
    state = str(drive.get("sharing") or "").strip().lower()
    if state in SHARING_STATES:
        return state
    if drive.get("public") is True:
        return PUBLIC_SHARING
    if drive.get("public") is False:
        return "private"
    return "unknown"


def prompt_sha256(prompt) -> str:
    """Hash of the exact prompt text. A changed prompt means a stale image —
    this is what stops yesterday's picture riding a re-worded line."""
    return hashlib.sha256(str(prompt or "").encode("utf-8")).hexdigest()


def bundle_dir(date) -> Path:
    return BUNDLE_ROOT / str(date)


def progress_dir(date) -> Path:
    return bundle_dir(date) / PROGRESS_DIRNAME


def claims_dir(date) -> Path:
    return progress_dir(date) / CLAIMS_DIRNAME


def checkpoint_path(date, request_id) -> Path:
    return progress_dir(date) / f"{safe_request_id(request_id)}.json"


def claim_path(date, request_id) -> Path:
    return claims_dir(date) / f"{safe_request_id(request_id)}.json"


# --------------------------------------------------------------------------
# bundle identity
# --------------------------------------------------------------------------
def identity_of_bytes(blob: bytes) -> str:
    return hashlib.sha256(blob or b"").hexdigest()


IDENTITY_FILE = "BUNDLE_ID"


def _editorial_signature_of(bundle) -> str:
    """Canonical snapshot of the EDITORIAL content a worker acts on: each
    package's script and shot phrasing/queries, plus every channel's
    authoring brief (the takeover work order).

    Deliberately excludes anything Phase A derives from media availability
    on a re-judge — `media_health`, `verdict`, `has_media`,
    `strong_fraction`, `requested` — those change on every run and are
    exactly the noise this identity must NOT react to (see the 2026-08-01
    incident this function's sibling docstring describes). A script
    rewrite, a shot phrase edit, or a changed authoring brief is not that
    noise: it silently reassigns what a worker already claimed against the
    same bundle identity, so it must move the fingerprint."""
    pkgs = []
    for pkg in bundle.get("packages") or []:
        if not isinstance(pkg, dict) or not pkg.get("slug"):
            # No slug means nothing downstream can attribute this entry to a
            # real package either — same as absent, never a false "changed".
            continue
        shots = [
            {"phrase": s.get("phrase"), "query": s.get("query")}
            for s in (pkg.get("shots") or []) if isinstance(s, dict)
        ]
        pkgs.append({"slug": pkg.get("slug"), "title": pkg.get("title"),
                     "script": pkg.get("script"), "shots": shots})
    pkgs.sort(key=lambda p: str(p.get("slug") or ""))
    briefs = {"authoring_request": bundle.get("authoring_request") or None,
              "authoring_requests": bundle.get("authoring_requests") or None}
    return json.dumps({"packages": pkgs, "briefs": briefs},
                      sort_keys=True, default=str)


def ask_fingerprint(bundle) -> str:
    """Hash of WHAT WE ASKED FOR, not of the file that carries it.

    The identity used to be the sha256 of `bundle.json`'s raw bytes. That
    broke on 2026-08-01 in a way nothing could see: Phase A runs on every
    auto-merge, it re-judges media each time, and it rewrote `bundle.json`
    SIX times that day — the last one five hours after the 06:00 worker had
    finished. Every one of the 17 checkpoints then read as "made for a
    DIFFERENT bundle", and because a DONE run now requires checkpoints, all
    17 verified images would have been refused.

    The fix is to hash the ASK: request ids, their prompts, their agreed
    filenames, the registry snapshot the day is contracted to, AND the
    editorial content a worker actually acts on (package scripts, shot
    phrasing, authoring briefs — see `_editorial_signature_of`). Without
    that last piece a rerun that changes package scripts or a takeover brief
    read as "unchanged" and rewrote bundle.json underneath a worker already
    acting on the prior editorial assignment. A re-judge that changes
    nothing a worker acts on leaves this untouched, so the checkpoints
    survive. Change a prompt, a script, a shot phrase, an authoring brief,
    add a request, or migrate the contract and it moves — which is exactly
    when they should die."""
    if not isinstance(bundle, dict):
        return ""
    reqs = []
    for r in bundle.get("requests") or []:
        if not isinstance(r, dict):
            continue
        reqs.append("|".join(str(r.get(k) or "") for k in
                             ("request_id", "prompt_sha256", "drive_filename",
                              "kind", "slug", "shot_index")))
    contract = bundle.get("contract") or {}
    parts = [
        f"date={normalize_date(bundle.get('date'))}",
        f"registry={contract.get('registry_sha256') or ''}",
        f"revision={contract.get('registry_revision') or ''}",
        f"commit={contract.get('source_commit') or ''}",
        "requests=" + "\n".join(sorted(reqs)),
        "editorial=" + _editorial_signature_of(bundle),
    ]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def bundle_identity(date) -> str | None:
    """The day's identity — read from the `BUNDLE_ID` sidecar Phase A writes.

    A sidecar rather than a hash the workers compute themselves, for two
    reasons. It is stable across the cosmetic `bundle.json` rewrites that
    used to invalidate every checkpoint (see `ask_fingerprint`), and a worker
    that only has to COPY a string cannot get the hashing wrong.

    Falls back to hashing `bundle.json` for bundles written before the
    sidecar existed, so old days stay readable."""
    d = bundle_dir(date)
    # Added by ChatGPT 2026-08-03: a late mechanical Phase A bundle must not
    # steal identity from an already-claimed ChatGPT takeover.  The takeover
    # state records the exact identity used by its durable media checkpoints;
    # prefer it while that owner remains authoritative for the date.
    try:
        takeover = json.loads((d / "takeover.json").read_text())
        takeover_id = str(takeover.get("checkpoint_identity") or "").strip()
        if (takeover.get("owner") == "chatgpt"
                and takeover.get("mode") == "takeover"
                and takeover_id):
            return takeover_id
    except Exception:                                    # noqa: BLE001
        pass
    try:
        text = (d / IDENTITY_FILE).read_text().strip()
        if _HEX64.match(text.lower()):
            return text.lower()
    except Exception:                                    # noqa: BLE001
        pass
    try:
        return identity_of_bytes((d / "bundle.json").read_bytes())
    except Exception:                                    # noqa: BLE001
        return None


def write_bundle_identity(date, bundle) -> str | None:
    """Publish the day's identity, keeping it STABLE while the ask is.

    Returns the identity in force after the call. Only rewrites the sidecar
    when `ask_fingerprint` actually moved — that stability is the whole
    point."""
    try:
        d = bundle_dir(date)
        d.mkdir(parents=True, exist_ok=True)
        want = ask_fingerprint(bundle)
        path = d / IDENTITY_FILE
        try:
            if path.read_text().strip().lower() == want:
                return want                  # unchanged — leave it alone
        except Exception:                                # noqa: BLE001
            pass
        tmp = path.with_suffix(".tmp")
        tmp.write_text(want + "\n")
        os.replace(tmp, path)
        return want
    except Exception:                                    # noqa: BLE001
        return None


# --------------------------------------------------------------------------
# checkpoints
# --------------------------------------------------------------------------
def build_checkpoint(*, date, request_id, bundle_id, request_kind="bundle_request",
                     package_id=None, shot_index=None, prompt=None,
                     prompt_used=None, status="verified", attempt=1,
                     worker="media", drive=None, image=None, error=None,
                     retryable=False, verified_at=None) -> dict:
    """Assemble a checkpoint. Pure — no IO, so it is trivial to test."""
    rid = str(request_id or "")
    fmt = normalize_ext((image or {}).get("format") if image else "png")
    drive = dict(drive or {})
    drive.setdefault("filename", deterministic_filename(date, rid, fmt))
    # Normalized, never defaulted to a guess: an unrecorded sharing state
    # stays "unknown" and fails validation, because assuming a file is
    # link-visible is how an HTML permission page ends up being treated as an
    # image. `public: true` is the older way of saying the same thing.
    drive["sharing"] = sharing_of(drive)
    cp = {
        "schema": SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "date": normalize_date(date),
        "bundle": {"identity": str(bundle_id or ""),
                   "path": f"exchange/bundles/{normalize_date(date)}/bundle.json"},
        "request_id": rid,
        "safe_request_id": safe_request_id(rid),
        "request_kind": (request_kind if request_kind in REQUEST_KINDS
                         else "bundle_request"),
        "package_id": (_norm_package_id(package_id)
                       if package_id is not None else None),
        "shot_index": (int(shot_index) if shot_index is not None else None),
        "prompt_sha256": prompt_sha256(prompt if prompt is not None
                                       else prompt_used),
        "prompt_used": (str(prompt_used) if prompt_used is not None
                        else (str(prompt) if prompt is not None else "")),
        "status": status if status in STATUSES else "failed",
        "attempt": max(1, int(attempt or 1)),
        "worker": str(worker or "media"),
        "drive": drive,
        "image": dict(image or {}),
        "verified_at": verified_at or iso(),
        "error": error,
        "retryable": bool(retryable),
    }
    return cp


def write_checkpoint(date, checkpoint: dict) -> Path | None:
    try:
        rid = checkpoint.get("request_id")
        path = checkpoint_path(date, rid)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, checkpoint)
        return path
    except Exception:                                    # noqa: BLE001
        return None


def read_checkpoint(date, request_id) -> dict | None:
    try:
        return json.loads(checkpoint_path(date, request_id).read_text())
    except Exception:                                    # noqa: BLE001
        return None


def all_checkpoints(date) -> dict[str, dict]:
    """Every checkpoint for the day, keyed by its declared `request_id`."""
    out: dict[str, dict] = {}
    d = progress_dir(date)
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            cp = json.loads(p.read_text())
        except Exception:                                # noqa: BLE001
            continue
        if isinstance(cp, dict) and cp.get("request_id"):
            out[str(cp["request_id"])] = cp
    return out


def checkpoint_problems(cp, *, date, bundle_id=None, request_id=None,
                        prompt=None, require_verified: bool = True) -> list[str]:
    """Why this checkpoint may NOT be trusted. Empty list means it may.

    Fails closed on every axis that could let a stale or foreign asset in:
    wrong schema, wrong day, wrong bundle, wrong request, changed prompt,
    unverified status, or a Drive/image record too thin to act on."""
    problems: list[str] = []
    if not isinstance(cp, dict):
        return ["no checkpoint"]
    if cp.get("schema") != SCHEMA:
        problems.append(f"wrong schema {cp.get('schema')!r} "
                        f"(want {SCHEMA!r})")
    try:
        if int(cp.get("schema_version") or 0) != SCHEMA_VERSION:
            problems.append(f"schema_version {cp.get('schema_version')!r} "
                            f"!= {SCHEMA_VERSION}")
    except Exception:                                    # noqa: BLE001
        problems.append("schema_version is not an integer")

    if normalize_date(cp.get("date")) != normalize_date(date):
        problems.append(f"checkpoint is for {cp.get('date')!r}, "
                        f"not {normalize_date(date)!r}")
    if bundle_id:
        got = str((cp.get("bundle") or {}).get("identity") or "")
        if got != str(bundle_id):
            problems.append(
                "made for a DIFFERENT bundle "
                f"({got[:12] or 'none'}… vs {str(bundle_id)[:12]}…) — the ask "
                "changed after this image was made")
    if request_id is not None and str(cp.get("request_id")) != str(request_id):
        problems.append(f"request_id {cp.get('request_id')!r} "
                        f"!= {str(request_id)!r}")
    if prompt is not None:
        want = prompt_sha256(prompt)
        if str(cp.get("prompt_sha256") or "") != want:
            problems.append("prompt changed since this image was generated")

    if cp.get("request_kind") not in REQUEST_KINDS:
        problems.append(f"unknown request_kind {cp.get('request_kind')!r}")

    if require_verified:
        # A checkpoint asserts "these bytes exist, at this address, and I can
        # fetch them". All three parts get checked: the hash covers the bytes,
        # the folder/filename cover recoverability, and the sharing state
        # covers whether anyone downstream can actually read it. A verified
        # checkpoint missing any of them is a claim we cannot act on.
        if cp.get("status") != "verified":
            problems.append(f"status is {cp.get('status')!r}, not 'verified'")
        drive, image = cp.get("drive") or {}, cp.get("image") or {}
        if not str(drive.get("file_id") or "").strip():
            problems.append("no drive.file_id")
        if not str(drive.get("folder_id") or "").strip():
            problems.append("no drive.folder_id — without it a lost "
                            "checkpoint cannot be recovered by listing")
        share = sharing_of(drive)
        if share != PUBLIC_SHARING:
            problems.append(
                f"drive sharing is {share!r}, not {PUBLIC_SHARING!r} — Drive "
                f"serves an HTML permission page instead of bytes for "
                f"anything else, so this asset is not actually fetchable")
        problems += _filename_problems(drive.get("filename"),
                                       date=cp.get("date") or date,
                                       request_id=cp.get("request_id"),
                                       fmt=image.get("format"))
        problems += _image_problems(image)
    return problems


def _filename_problems(name, *, date, request_id, fmt=None) -> list[str]:
    """Is this the deterministic name, for THIS request, on THIS day?

    Checked field by field rather than by string equality against one
    candidate: the extension has to be allowed to follow the actual bytes
    (a generator that returns webp instead of png is a format surprise, not
    an identity mismatch), while the date and the request id are identity and
    must be exact."""
    if not str(name or "").strip():
        return ["no drive.filename — the deterministic name is what makes an "
                "orphaned upload recoverable"]
    parsed = parse_filename(name)
    if not parsed:
        return [f"drive.filename {str(name)!r} is not the deterministic "
                f"<date>__<safe_request_id>.<ext> shape"]
    problems = []
    if parsed["date"] != normalize_date(date):
        problems.append(f"drive.filename is dated {parsed['date']}, "
                        f"not {normalize_date(date)}")
    want = safe_request_id(request_id)
    if parsed["safe_request_id"] != want:
        problems.append(f"drive.filename names request "
                        f"{parsed['safe_request_id']!r}, not {want!r}")
    if fmt and parsed["ext"] != normalize_ext(fmt):
        problems.append(f"drive.filename ends .{parsed['ext']} but the image "
                        f"is {normalize_ext(fmt)}")
    return problems


def checkpoint_reusable(cp, *, date, bundle_id=None, request_id=None,
                        prompt=None) -> bool:
    return not checkpoint_problems(cp, date=date, bundle_id=bundle_id,
                                   request_id=request_id, prompt=prompt)


# --------------------------------------------------------------------------
# orphan reconciliation
# --------------------------------------------------------------------------
#: Recovery decisions, in the order they are considered.
RECOVERY_ORDER = ("reuse_checkpoint", "adopt_orphan", "conflicted",
                  "claimed", "generate")


def plan_recovery(*, date, request_id, bundle_id=None, prompt=None,
                  fmt: str = "png", checkpoint=None, drive_listing=None,
                  claim=None, worker_run_id=None, now=None) -> dict:
    """What should happen to this request — decided from data, not from Drive.

    Order is deliberate and each step exists because the alternative burned us:

      1. **A valid checkpoint wins outright**, even over an active claim. A
         verified result is stronger evidence than somebody's intent to
         produce one.
      2. **Search Drive for the exact deterministic filename.** This is the
         orphan case: the image was made and uploaded, then the checkpoint was
         lost (crash, context limit, uncommitted write).
      3. **Adopting an orphan means downloading and hashing it.** The action
         returned is `adopt_orphan`, which OBLIGES the worker to verify bytes
         and write the checkpoint from what it actually found. A filename is a
         lookup key; it is never evidence about content.
      4. **Two files with the same name is `conflicted`.** Drive permits
         duplicate names. Guessing between them means a coin flip on what ends
         up in the video, so it refuses and reports instead.
      5. **Someone else holds a live claim** → `claimed`; come back later.
      6. Only when nothing is reusable does it say `generate`.

    `drive_listing` is a list of `{"name": ..., "id": ...}` dicts supplied BY
    THE WORKER. Nothing here talks to Drive — the pipeline stays free of that
    dependency and gains only a validator."""
    rid = str(request_id or "")
    filename = deterministic_filename(date, rid, fmt)
    out = {"request_id": rid, "safe_request_id": safe_request_id(rid),
           "filename": filename, "action": "generate", "reason": "",
           "candidates": []}

    if checkpoint is None:
        checkpoint = read_checkpoint(date, rid)
    problems = checkpoint_problems(checkpoint, date=date, bundle_id=bundle_id,
                                   request_id=rid, prompt=prompt)
    if not problems:
        out["action"] = "reuse_checkpoint"
        out["reason"] = "a verified checkpoint for this exact ask already exists"
        out["checkpoint"] = checkpoint
        return out
    out["checkpoint_problems"] = problems

    matches = [f for f in (drive_listing or [])
               if isinstance(f, dict)
               and str(f.get("name") or "").strip() == filename]
    out["candidates"] = matches
    if len(matches) == 1:
        out["action"] = "adopt_orphan"
        out["reason"] = (f"{filename} is already on Drive but has no usable "
                         f"checkpoint — download it, hash the BYTES, and write "
                         f"the checkpoint from what you actually got. Do not "
                         f"trust the name.")
        out["drive_file_id"] = matches[0].get("id")
        return out
    if len(matches) > 1:
        out["action"] = "conflicted"
        out["reason"] = (f"{len(matches)} Drive files are named {filename} — "
                         f"refusing to guess which one belongs to this "
                         f"request. Report it; do not pick one.")
        return out

    if claim is None:
        claim = read_claim(date, rid)
    if claim_active(claim, now=now) and (
            worker_run_id is None
            or str(claim.get("worker_run_id")) != str(worker_run_id)):
        out["action"] = "claimed"
        out["reason"] = (f"another worker ({claim.get('worker')}) holds a "
                         f"lease until {claim.get('expires_at')}")
        out["claim"] = claim
        return out

    out["action"] = "generate"
    out["reason"] = ("no usable checkpoint and nothing on Drive under "
                     f"{filename}")
    return out


# --------------------------------------------------------------------------
# claims / leases
# --------------------------------------------------------------------------
def build_claim(*, date, request_id, worker, worker_run_id=None,
                bundle_id=None, lease_seconds=DEFAULT_LEASE_SECONDS,
                now=None) -> dict:
    now = now or _utcnow()
    lease = max(60, int(lease_seconds or DEFAULT_LEASE_SECONDS))
    return {
        "schema": CLAIM_SCHEMA,
        "date": normalize_date(date),
        "bundle": {"identity": str(bundle_id or "")},
        "request_id": str(request_id or ""),
        "safe_request_id": safe_request_id(request_id),
        "worker": str(worker or "media"),
        "worker_run_id": str(worker_run_id or ""),
        "created_at": iso(now),
        "expires_at": iso(now + timedelta(seconds=lease)),
        "lease_seconds": lease,
    }


def read_claim(date, request_id) -> dict | None:
    try:
        return json.loads(claim_path(date, request_id).read_text())
    except Exception:                                    # noqa: BLE001
        return None


def claim_active(claim, now=None) -> bool:
    """A claim only counts while its lease is unexpired.

    An expired claim is INERT, not sticky. A worker that dies mid-image would
    otherwise leave a tombstone that blocks that shot forever, and the failure
    mode — one silently missing image per crash, permanently — is exactly the
    kind of thing nobody notices for a month."""
    if not isinstance(claim, dict):
        return False
    exp = parse_iso(claim.get("expires_at"))
    if exp is None:
        return False
    return exp > (now or _utcnow())


def create_claim(date, request_id, *, worker="media", worker_run_id=None,
                 bundle_id=None, lease_seconds=DEFAULT_LEASE_SECONDS,
                 now=None) -> dict:
    """Optimistic create-only lease. Returns
    `{"granted": bool, "claim": {...}, "reason": str, "reclaimed": bool}`.

    Create-only (`O_CREAT|O_EXCL`) rather than read-then-write: two workers
    racing on the same request cannot both see "no claim" and both proceed.
    The loser is told who holds it.

    Three ways to still get it: the file does not exist; the existing lease
    has expired (reclaimed, and said so); or it is our own run re-entering
    after a retry (idempotent — a worker retrying its own step must not
    deadlock against itself)."""
    claim = build_claim(date=date, request_id=request_id, worker=worker,
                        worker_run_id=worker_run_id, bundle_id=bundle_id,
                        lease_seconds=lease_seconds, now=now)
    path = claim_path(date, request_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(claim, f, indent=2)
            f.write("\n")
        return {"granted": True, "claim": claim, "reason": "created",
                "reclaimed": False}
    except FileExistsError:
        pass
    except Exception as exc:                             # noqa: BLE001
        return {"granted": False, "claim": None,
                "reason": f"could not create claim: {exc}", "reclaimed": False}

    existing = read_claim(date, request_id)
    mine = (worker_run_id is not None and isinstance(existing, dict)
            and str(existing.get("worker_run_id")) == str(worker_run_id))
    if claim_active(existing, now=now) and not mine:
        return {"granted": False, "claim": existing,
                "reason": (f"held by {(existing or {}).get('worker')} until "
                           f"{(existing or {}).get('expires_at')}"),
                "reclaimed": False}

    # Expired, unparseable, or ours. Take it — atomically, so a concurrent
    # reader never sees a half-written lease.
    try:
        atomic_write_json(path, claim)
    except Exception as exc:                             # noqa: BLE001
        return {"granted": False, "claim": existing,
                "reason": f"could not reclaim: {exc}", "reclaimed": False}
    return {"granted": True, "claim": claim,
            "reason": ("re-entered our own claim" if mine
                       else "previous lease had expired"),
            "reclaimed": not mine}


def release_claim(date, request_id) -> bool:
    try:
        claim_path(date, request_id).unlink()
        return True
    except Exception:                                    # noqa: BLE001
        return False


def expired_claims(date, now=None) -> list[dict]:
    out = []
    d = claims_dir(date)
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            c = json.loads(p.read_text())
        except Exception:                                # noqa: BLE001
            continue
        if not claim_active(c, now=now):
            out.append(c)
    return out


# --------------------------------------------------------------------------
# worker boundaries
# --------------------------------------------------------------------------
# The split only works if each worker knows where its job STOPS. The media
# worker writing `DONE` at 06:00 would fire the render an hour before the
# finalizer had authored anything — a green pipeline shipping half a day.
_NEVER = (
    "*.py", "*.yml", "*.yaml", "*.sh", "*.toml", "*.cfg", "*.ini",
    "scripts/*", "scripts/**", "shared/*", "shared/**", "funnel/*",
    "funnel/**", "engines/*", "engines/**", "docs/*", "docs/**",
    "tests/*", "tests/**", ".github/*", ".github/**",
    "state/*", "state/**", "data_learning/*", "data_learning/**",
    "exchange/README.md", "retro/README.md", "CLAUDE.md",
    "CLAUDE_ROUTINE_INSTRUCTIONS.md",
)

WORKERS = {
    "media": {
        "role": "MEDIA worker",
        "runs_at": "06:00 America/Chicago",
        "job": ("Generate, upload and VERIFY every image the day needs, and "
                "record each one as a checkpoint the moment it verifies."),
        "may_write": [
            f"exchange/bundles/*/{PROGRESS_DIRNAME}/*.json",
            f"exchange/bundles/*/{PROGRESS_DIRNAME}/{CLAIMS_DIRNAME}/*.json",
        ],
        "must_never_write": [
            "exchange/bundles/*/response.json",
            "exchange/bundles/*/DONE",
            "exchange/bundles/*/authored/*.json",
        ],
        "rules": [
            "Checkpoint after EVERY verified image, one file per request — "
            "not one batch at the end. A run that dies at image 19 of 24 must "
            "leave 18 recoverable results behind, not zero.",
            "Never write response.json. Never write DONE. DONE fires the "
            "render, and at 06:00 nothing has been authored or punched up "
            "yet — writing it would ship half a day with everything green.",
            "Work the deterministic filename from the bundle. Uploading under "
            "any other name makes the image unrecoverable if your checkpoint "
            "is lost.",
        ],
    },
    "finalizer": {
        "role": "FINALIZER worker",
        "runs_at": "07:00 America/Chicago",
        "job": ("Recover what the media worker did, fill whatever it missed, "
                "punch up the scripts, author anything the Claude side left "
                "undone, then write response.json and — separately — DONE."),
        "may_write": [
            "exchange/bundles/*/response.json",
            "exchange/bundles/*/DONE",
            "exchange/bundles/*/authored/*.json",
            f"exchange/bundles/*/{PROGRESS_DIRNAME}/*.json",
            f"exchange/bundles/*/{PROGRESS_DIRNAME}/{CLAIMS_DIRNAME}/*.json",
            "retro/*/proposals/*.json",
        ],
        "must_never_write": [],
        "rules": [
            "START by reading media-progress/. Every verified checkpoint is an "
            "image that already exists on Drive — re-generating it burns the "
            "budget AND produces a different picture than the one the "
            "checkpoint names.",
            "Fill the gaps the media worker left, checkpointing each one the "
            "same way. You are the second attempt, not a separate pipeline.",
            "Do the explainer and curiosity work even when trending already "
            "has six packages. Those are separate channels with separate "
            "asks; a full trending slate says nothing about either of them.",
            "Commit response.json, READ IT BACK from main and confirm it "
            "parses, and only THEN commit DONE as a second commit. DONE is "
            "the only thing that fires the render.",
        ],
    },
}


def worker_may_write(worker: str, path) -> tuple[bool, str]:
    """May `worker` write `path`? Returns (allowed, why not).

    This is a contract check, not a security control — nothing mechanically
    stops a worker from committing anything. It exists so the boundary is
    encoded in CODE and covered by a test, instead of living only in prose
    that a future task may or may not read."""
    rel = str(path or "").strip().lstrip("./")
    rel = rel.replace("\\", "/")
    spec = WORKERS.get(str(worker or "").lower())
    if not spec:
        return False, f"unknown worker {worker!r}"
    for pat in spec["must_never_write"]:
        if fnmatch.fnmatch(rel, pat):
            return False, f"{spec['role']} must never write {rel}"
    for pat in spec["may_write"]:
        if fnmatch.fnmatch(rel, pat):
            return True, ""
    for pat in _NEVER:
        if fnmatch.fnmatch(rel, pat):
            return False, (f"{rel} is pipeline code/config — Claude is the "
                           f"only agent that edits this repository")
    return False, f"{rel} is outside the {spec['role']}'s lane"


# --------------------------------------------------------------------------
# Phase B: validating a response against the checkpoints
# --------------------------------------------------------------------------
def _image_problems(img) -> list[str]:
    problems = []
    if not isinstance(img, dict):
        return ["no `image` block"]
    sha = str(img.get("sha256") or "").strip().lower()
    if not sha:
        problems.append("image.sha256 missing — every fulfilled pointer must "
                        "carry the hash of the exact bytes")
    elif not _HEX64.match(sha):
        problems.append(f"image.sha256 is not 64 hex ({sha[:16]!r}) — a "
                        "fabricated or truncated hash")
    try:
        if int(img.get("bytes") or 0) <= 0:
            problems.append("image.bytes missing or zero")
    except Exception:                                    # noqa: BLE001
        problems.append("image.bytes is not a number")
    if not str(img.get("format") or "").strip():
        problems.append("image.format missing")
    for dim in ("width", "height"):
        try:
            if int(img.get(dim) or 0) <= 0:
                problems.append(f"image.{dim} missing or zero")
        except Exception:                                # noqa: BLE001
            problems.append(f"image.{dim} is not a number")
    return problems


def media_entry_problems(entry, *, date, bundle_id=None, request_id=None,
                         prompt=None, checkpoint=None,
                         expect_kind="bundle_request", package_id=None,
                         shot_index=None,
                         require_checkpoint: bool = False) -> list[str]:
    """Everything wrong with ONE media pointer in ChatGPT's response.

    The pointer alone is a claim; the checkpoint is the record of the moment
    the bytes were verified. When both exist they must agree exactly — a
    pointer that disagrees with its own checkpoint means either the response
    was edited after the fact or two different images are in play, and neither
    is something to render."""
    problems: list[str] = []
    if not isinstance(entry, dict):
        return ["media entry is not an object"]

    claimed_rid = entry.get("request_id")
    if request_id is not None:
        # Added by ChatGPT 2026-08-03: an authored-shot pointer rides on the
        # shot itself, so its id is already unambiguously derived from
        # package slug + shot index.  The authoring brief intentionally omits
        # this redundant field.  Bundle-request entries remain strict.
        if claimed_rid is None and expect_kind != "authored_shot":
            problems.append(f"no request_id (expected {request_id!r})")
        elif claimed_rid is not None and str(claimed_rid) != str(request_id):
            problems.append(f"request_id {str(claimed_rid)!r} does not match "
                            f"the request it is attached to ({request_id!r})")

    status = str(entry.get("status") or "").strip()
    if status not in ("fulfilled", "partial"):
        # Not a defect — an honest failure is a valid answer. Say so and stop.
        return [f"status {status or 'missing'!r} — not a delivered asset"]

    problems += _image_problems(entry.get("image"))

    drive = entry.get("drive") or {}
    if not str(drive.get("file_id") or "").strip() and \
            not str(drive.get("download_url") or "").strip():
        problems.append("drive.file_id and drive.download_url both missing — "
                        "nothing to fetch")

    rid = str(request_id if request_id is not None else claimed_rid or "")
    if checkpoint is None and rid:
        checkpoint = read_checkpoint(date, rid)

    if checkpoint is None:
        msg = (f"no checkpoint at exchange/bundles/{normalize_date(date)}/"
               f"{PROGRESS_DIRNAME}/{safe_request_id(rid)}.json — the media "
               f"worker never recorded this image as verified")
        if require_checkpoint:
            problems.append(msg)
        else:
            problems.append("WARN: " + msg)
        return problems

    problems += [f"checkpoint: {p}" for p in
                 checkpoint_problems(checkpoint, date=date,
                                     bundle_id=bundle_id, request_id=rid,
                                     prompt=prompt)]

    # EXACT AGREEMENT, field by field. Hash and byte count alone say the
    # CONTENT matches; they say nothing about whether the response points at
    # the same asset the worker verified. An image can hash correctly and
    # still be named something unrecoverable, live in the wrong folder, or be
    # private — and "private" means Drive hands the renderer an HTML
    # permission page. Any disagreement means the response and the checkpoint
    # are describing two different things, and we do not get to pick.
    problems += _filename_problems(drive.get("filename"), date=date,
                                   request_id=rid,
                                   fmt=(entry.get("image") or {}).get("format"))
    for section, field in AGREEMENT_FIELDS:
        want = (checkpoint.get(section) or {}).get(field)
        got = (entry.get(section) or {}).get(field)
        if want in (None, "") and got in (None, ""):
            continue                    # already reported as a missing field
        if got in (None, ""):
            problems.append(f"{section}.{field} missing from the response "
                            f"but recorded on the checkpoint")
            continue
        if str(want).strip().lower() != str(got).strip().lower():
            problems.append(
                f"{section}.{field} disagrees with its checkpoint "
                f"({str(got)[:24]!r} vs {str(want)[:24]!r}) — the response "
                f"and the verified asset are not the same file")

    ent_share, cp_share = sharing_of(drive), sharing_of(checkpoint.get("drive"))
    if ent_share != cp_share:
        problems.append(f"drive sharing disagrees with its checkpoint "
                        f"({ent_share!r} vs {cp_share!r})")
    elif ent_share != PUBLIC_SHARING:
        problems.append(f"drive sharing is {ent_share!r}, not "
                        f"{PUBLIC_SHARING!r} — not fetchable")

    if checkpoint.get("request_kind") != expect_kind:
        problems.append(f"checkpoint request_kind "
                        f"{checkpoint.get('request_kind')!r} but this is a "
                        f"{expect_kind}")
    if package_id is not None:
        want = _norm_package_id(package_id)
        got = str(checkpoint.get("package_id") or "")
        if got != want:
            problems.append(f"checkpoint belongs to package {got!r}, not "
                            f"{want!r} — authored media attached to the wrong "
                            f"package")
    if shot_index is not None:
        try:
            if int(checkpoint.get("shot_index")) != int(shot_index):
                problems.append(f"checkpoint is for shot "
                                f"{checkpoint.get('shot_index')}, not "
                                f"{shot_index}")
        except Exception:                                # noqa: BLE001
            problems.append(f"checkpoint has no usable shot_index "
                            f"(expected {shot_index})")
    return problems


def contract_problems(response, bundle) -> list[str]:
    """Was this response written against THIS bundle's contract snapshot?

    A response may declare which contract it answered — `registry_revision`,
    `registry_sha256`, `source_commit`, `production_date`. When it does, the
    values must match the bundle's frozen snapshot. A worker that read a
    newer registry, or yesterday's bundle, is answering a different question
    than the one this day asked, and its counts and formats will be wrong in
    ways nothing downstream can see.

    Silence is tolerated (an older worker simply does not declare it), but a
    WRONG declaration is refused outright — a mismatch is evidence, not noise.
    """
    problems: list[str] = []
    if not isinstance(response, dict) or not isinstance(bundle, dict):
        return problems
    contract = bundle.get("contract")
    if not isinstance(contract, dict):
        return problems
    declared = response.get("contract") or response.get("answered_contract")
    if not isinstance(declared, dict):
        return problems
    for field in ("registry_revision", "registry_sha256", "source_commit",
                  "production_date"):
        want, got = contract.get(field), declared.get(field)
        if got in (None, "") or want in (None, ""):
            continue
        if str(got) != str(want):
            problems.append(
                f"response answers contract {field}={str(got)[:16]!r} but "
                f"this bundle froze {str(want)[:16]!r} — the worker read a "
                f"different plan than the one this day was built on")
    return problems


def validate_response_media(response, bundle, *, date, bundle_id=None,
                            require_checkpoint: bool = False) -> dict:
    """Walk EVERY media pointer in a response and say which ones may be used.

    Covers both places media can appear:

      * the top-level `media` array, keyed by a bundle `request_id`;
      * `authored[i].shots[j].media`, keyed implicitly by package + shot.

    Cross-entry checks (duplicate request ids, one Drive file claimed by two
    different requests) can only be done with the whole response in view,
    which is why this exists rather than only the per-entry function."""
    out = {"date": normalize_date(date), "ok": [], "rejected": [],
           "warnings": [], "counts": {}, "contract_problems": []}
    if not isinstance(response, dict):
        out["counts"] = {"checked": 0, "ok": 0, "rejected": 0}
        return out

    # A response written against the WRONG contract taints every pointer in
    # it, so this is checked once up front rather than per entry.
    out["contract_problems"] = contract_problems(response, bundle)

    reqs = {str(r.get("request_id")): r
            for r in (bundle or {}).get("requests") or []
            if isinstance(r, dict) and r.get("request_id")}
    if bundle_id is None:
        bundle_id = bundle_identity(date)

    seen_rids: dict[str, str] = {}
    file_ids: dict[str, tuple[str, str]] = {}
    checked = 0

    def _reject(rid, where, problems):
        out["rejected"].append({"request_id": rid, "where": where,
                                "problems": problems})

    def _record(rid, where, problems, entry):
        nonlocal checked
        checked += 1
        hard = [p for p in problems if not p.startswith("WARN: ")]
        soft = [p[6:] for p in problems if p.startswith("WARN: ")]
        for s in soft:
            out["warnings"].append({"request_id": rid, "where": where,
                                    "problem": s})
        if hard:
            _reject(rid, where, hard)
            return
        out["ok"].append(rid)

        # ONE DRIVE FILE, ONE REQUEST. Matching hashes are not a licence to
        # share a file: two requests are two different lines of script, and an
        # image that answers both is one shot doing double duty — which is how
        # a slate ends up visually repeating itself. It is also how a mistake
        # hides, because the second pointer looks perfectly verified.
        #
        # BOTH sides are rejected, not just the later one. We cannot tell
        # which request legitimately owns the file, and guessing here is the
        # same coin flip `plan_recovery` refuses to make on duplicate
        # filenames. Both fall through to self-fill.
        fid = str((entry.get("drive") or {}).get("file_id") or "")
        if not fid:
            return
        prev = file_ids.get(fid)
        if prev and prev[0] != rid:
            why = (f"drive.file_id {fid[:12]}… is claimed by TWO requests "
                   f"({prev[0]!r} and {rid!r}) — one Drive file cannot answer "
                   f"two different asks, and we cannot tell which one owns it")
            _reject(rid, where, [why])
            out["ok"].remove(rid)
            if prev[0] in out["ok"]:
                out["ok"].remove(prev[0])
                _reject(prev[0], prev[1], [why])
            return
        file_ids.setdefault(fid, (rid, where))

    top = response.get("media") or response.get("results") or []
    if not isinstance(top, list):
        top = []
    for entry in top:
        where = "response.media"
        if not isinstance(entry, dict):
            _record("", where, ["media entry is not an object"], {})
            continue
        rid = str(entry.get("request_id") or "")
        if not rid:
            _record("", where, ["no request_id"], entry)
            continue
        if rid in seen_rids:
            _record(rid, where,
                    [f"duplicate request_id — already answered in "
                     f"{seen_rids[rid]}"], entry)
            continue
        seen_rids[rid] = where
        if is_authored_shot_request(rid):
            _record(rid, where,
                    ["an authored shot's image must ride ON THE SHOT "
                     "(authored[i].shots[j].media), not in the top-level "
                     "`media` array — the top-level array is keyed by bundle "
                     "request_id and there is no bundle request for a package "
                     "you invented"], entry)
            continue
        req = reqs.get(rid)
        if req is None:
            _record(rid, where,
                    ["no such request_id in this bundle"], entry)
            continue
        _record(rid, where, media_entry_problems(
            entry, date=date, bundle_id=bundle_id, request_id=rid,
            prompt=req.get("prompt_verbatim"), expect_kind="bundle_request",
            require_checkpoint=require_checkpoint), entry)

    authored = response.get("authored") or []
    for pkg in (authored if isinstance(authored, list) else []):
        if not isinstance(pkg, dict):
            continue
        pid = pkg.get("slug") or pkg.get("package_id") or ""
        shots = pkg.get("shots") or []
        for i, shot in enumerate(shots if isinstance(shots, list) else []):
            entry = shot.get("media") if isinstance(shot, dict) else None
            if not isinstance(entry, dict):
                continue
            rid = authored_shot_request_id(pid, i)
            where = f"authored[{_norm_package_id(pid)}].shots[{i}].media"
            if rid in seen_rids:
                _record(rid, where,
                        [f"duplicate request_id — already answered in "
                         f"{seen_rids[rid]}"], entry)
                continue
            seen_rids[rid] = where
            _record(rid, where, media_entry_problems(
                entry, date=date, bundle_id=bundle_id, request_id=rid,
                prompt=None, expect_kind="authored_shot", package_id=pid,
                shot_index=i, require_checkpoint=require_checkpoint), entry)

    out["counts"] = {"checked": checked, "ok": len(out["ok"]),
                     "rejected": len(out["rejected"]),
                     "warnings": len(out["warnings"])}
    return out


# --------------------------------------------------------------------------
# what goes in the bundle
# --------------------------------------------------------------------------
def protocol_block(date) -> dict:
    """The media protocol, as DATA inside the day's bundle.

    Handed to the workers rather than left in a markdown file they may not
    open — the same reason `authoring_brief.FORMAT_SPECS` ships inline. This
    is generated from the same constants the validator enforces, so what we
    ask for and what we accept cannot drift apart."""
    d = normalize_date(date)
    return {
        "schema": SCHEMA,
        "why": ("Two scheduled workers share this day and cannot see each "
                "other's context — only this repo. These files ARE the shared "
                "memory."),
        "checkpoint_dir": f"exchange/bundles/{d}/{PROGRESS_DIRNAME}/",
        "claims_dir": f"exchange/bundles/{d}/{PROGRESS_DIRNAME}/"
                      f"{CLAIMS_DIRNAME}/",
        "checkpoint_path": f"exchange/bundles/{d}/{PROGRESS_DIRNAME}/"
                           f"<safe_request_id>.json",
        "filename_rule": (f"Upload every asset to Drive as "
                          f"`{d}__<safe_request_id>.<ext>`. Each bundle "
                          f"request already carries its exact "
                          f"`drive_filename` — use that string verbatim."),
        "safe_request_id": (
            "The request_id with anything outside [A-Za-z0-9._-] replaced by "
            "`-`; if that changed the string (or it exceeded 72 chars), an "
            "8-hex sha256 of the ORIGINAL is appended so two different "
            "requests can never share one file. Bundle requests publish "
            "theirs as `safe_request_id`."),
        "authored_shot_request_id": (
            "For a shot inside a package YOU authored there is no bundle "
            "request, so build the id yourself: "
            "`authored-<slug>-s<shot_index>`, where <slug> is the package's "
            "slug lowercased with anything outside [a-z0-9-] replaced by `-`. "
            "It must be derived from slug + shot index ONLY — never from the "
            "prompt, a timestamp, or a counter — so the 07:00 worker "
            "recomputes the identical string from the package on disk."),
        "bundle_identity": (
            f"READ IT FROM exchange/bundles/{d}/{IDENTITY_FILE} — a single "
            f"line of 64 hex. Copy that string into every checkpoint's "
            f"`bundle.identity`. Do NOT hash bundle.json yourself: Phase A "
            f"re-runs and rewrites that file through the day, and on "
            f"2026-08-01 it did so five hours after the media worker "
            f"finished, which would have invalidated all 17 of its verified "
            f"images. The sidecar only changes when the ASK changes — a new "
            f"request, a changed prompt, a contract migration — which is "
            f"exactly when a checkpoint should stop being valid."),
        "checkpoint_fields": {
            "schema": SCHEMA, "schema_version": SCHEMA_VERSION,
            "date": d, "bundle": {"identity": "<sha256 of bundle.json>",
                                  "path": f"exchange/bundles/{d}/bundle.json"},
            "request_id": "<the id from the bundle, or the authored-shot id>",
            "safe_request_id": "<as above>",
            "request_kind": "bundle_request | authored_shot",
            "package_id": "<authored_shot only: the package slug>",
            "shot_index": "<authored_shot only: integer>",
            "prompt_sha256": "<sha256 of the prompt text you actually used>",
            "prompt_used": "<that prompt, verbatim>",
            "status": "verified | failed | in_progress | skipped",
            "attempt": 1,
            "worker": "media | finalizer",
            "drive": {"folder_id": "…", "file_id": "…",
                      "filename": f"{d}__<safe_request_id>.png",
                      "download_url": "…",
                      "sharing": "anyone_with_link | domain | private | unknown"},
            "image": {"sha256": "<64 hex of the exact bytes>", "bytes": 0,
                      "format": "png", "width": 1080, "height": 1080},
            "verified_at": "<ISO8601 Z>",
            "error": {"code": "…", "step": "…", "message": "…"},
            "retryable": False,
        },
        "recovery_order": [
            "1. Read the checkpoint. Valid + verified + same bundle identity "
            "+ same prompt -> REUSE it. Do not re-generate.",
            "2. Otherwise search Drive for the EXACT deterministic filename.",
            "3. Exactly one match -> download it, hash the bytes, confirm it "
            "decodes, and write the checkpoint from what you actually found. "
            "A filename is a lookup key, never evidence about content.",
            "4. More than one match -> CONFLICTED. Report it and move on; do "
            "not guess which file belongs to the request.",
            "5. Only when nothing is reusable, generate it.",
        ],
        "claims": {
            "path": f"exchange/bundles/{d}/{PROGRESS_DIRNAME}/"
                    f"{CLAIMS_DIRNAME}/<safe_request_id>.json",
            "semantics": ("Create-only. If the file already exists and its "
                          "`expires_at` is in the future, someone else is on "
                          "it — skip that request. An EXPIRED claim is inert: "
                          "take it over and say so. A verified checkpoint "
                          "supersedes any claim, including a live one."),
            "lease_seconds": DEFAULT_LEASE_SECONDS,
            "fields": ["schema", "date", "bundle.identity", "request_id",
                       "safe_request_id", "worker", "worker_run_id",
                       "created_at", "expires_at", "lease_seconds"],
        },
        "workers": WORKERS,
        "honesty": ("A checkpoint is a claim that you verified bytes. Writing "
                    "one for an image you did not download and hash is worse "
                    "than writing nothing, because the next worker will skip "
                    "the work believing it is done."),
    }


def pointer_from_checkpoint(cp: dict) -> dict | None:
    """A verified checkpoint, expressed as a response-shaped media pointer.

    THE CHECKPOINT IS ALREADY THE PROOF. It carries every field a pointer
    does — drive.file_id, download_url, sha256, bytes, format, dimensions,
    sharing — because the media worker writes it at the moment those bytes
    verify. `response.json` was never the evidence; it was only the envelope
    the finalizer put the evidence in.

    That distinction cost the channel real videos. From 2026-08-09 the 6:00
    media worker delivered 14-16 verified images a day and the 7:00 finalizer
    stopped writing `response.json`, so Phase B — which read pointers ONLY
    from the response — threw every one of them away and self-filled the day
    with unrelated stock. That stock is exactly what the showrunner then
    blocked trending's reddit stories for, two days running. The work existed,
    was verified, and was discarded for want of an envelope.

    Returns None when the checkpoint is not a usable record. This is only
    the SHAPE check (status + the minimum fields to build a pointer at all);
    it is not the trust check. `recovered_media` below is the caller that
    also runs `checkpoint_problems` before ever handing one back, so a
    checkpoint this function accepts can still be refused for being stale,
    for the wrong bundle, or for the wrong day.
    """
    if not isinstance(cp, dict):
        return None
    if str(cp.get("status") or "").lower() != "verified":
        return None
    rid = cp.get("request_id")
    drive = cp.get("drive") or {}
    image = cp.get("image") or {}
    if not rid or not drive.get("file_id") or not image.get("sha256"):
        return None
    return {
        "request_id": str(rid),
        "status": "fulfilled",
        "drive": dict(drive),
        "image": dict(image),
        "recovered_from_checkpoint": True,
    }


def recovered_media(date, *, have: set | None = None, bundle: dict | None = None,
                    bundle_id: str | None = None,
                    refused_out: dict[str, list[str]] | None = None,
                    ) -> dict[str, dict]:
    """Pointers rebuilt from the day's checkpoints for requests the response
    did not already answer. `have` is the set of request_ids the response
    covers, which always wins — recovery fills gaps, it never overrides.

    Recovery grants NO extra trust: every candidate is put through
    `checkpoint_problems` — the identical schema / date / bundle-identity /
    prompt / sharing / filename / image checks a response pointer's own
    checkpoint gets inside `validate_response_media` — before it is ever
    handed back. A checkpoint made for a different bundle revision, the
    wrong day, or missing the fields that make it fetchable is dropped
    exactly like a refused response pointer, never silently promoted.
    Pass `bundle` (for prompt-agreement checks on bundle requests) and
    `bundle_id` (for the identity check) whenever they are known; a caller
    that omits them only loses those two axes, it never loses the rest.
    Refused candidates are reported via `refused_out` (rid -> problems)
    when the caller passes a dict, purely for logging."""
    have = have or set()
    prompts = {
        str(r.get("request_id")): r.get("prompt_verbatim")
        for r in (bundle or {}).get("requests") or []
        if isinstance(r, dict) and r.get("request_id")
    }
    out: dict[str, dict] = {}
    for rid, cp in all_checkpoints(date).items():
        if rid in have:
            continue
        # TYPE-AWARE: this is the BUNDLE-REQUEST lane. An authored-shot
        # checkpoint recovered here used to be memory no consumer read
        # (doctor ee3bb63e4024): Phase B merges this map into idx["media"],
        # which only the bundle.requests loop walks — and there is no bundle
        # request for a package ChatGPT invented, so the pointer sat in the
        # map while the shot self-filled with stock. Authored-shot
        # checkpoints belong to `recovered_authored_media` below, keyed the
        # way their consumer (cover_authored) actually addresses shots.
        if (str((cp or {}).get("request_kind") or "") == "authored_shot"
                or is_authored_shot_request(rid)):
            continue
        ptr = pointer_from_checkpoint(cp)
        if not ptr:
            continue
        problems = checkpoint_problems(cp, date=date, bundle_id=bundle_id,
                                       request_id=rid, prompt=prompts.get(rid))
        if problems:
            if refused_out is not None:
                refused_out[rid] = problems
            continue
        out[rid] = ptr
    return out


def recovered_authored_media(date, *, have: set | None = None,
                             bundle_id: str | None = None,
                             refused_out: dict[str, list[str]] | None = None,
                             ) -> dict[tuple[str, int], dict]:
    """Authored-shot pointers rebuilt from the day's checkpoints, keyed by
    `(package_id, shot_index)` — the address their consumer actually uses.

    The second half of the recovery story `recovered_media` tells: a media
    worker on a takeover day checkpoints images for shots inside packages
    ChatGPT authored itself, and if the finalizer then omits the matching
    `shot.media` pointer from its response, that verified work must still
    reach the shot instead of falling to stock self-fill (doctor
    ee3bb63e4024 — the durable memory existed, was verified, and was then
    ignored for want of an envelope).

    Recovery grants NO extra trust — never fewer checks than an explicit
    authored pointer's checkpoint gets inside `validate_response_media`:

      * the full `checkpoint_problems` contract (schema, date, bundle
        identity, verified status, sharing, deterministic filename, image
        fields), with `prompt=None` exactly as `media_entry_problems` uses
        for authored shots;
      * `request_kind` must be `authored_shot` — a bundle-request checkpoint
        cannot back an authored shot, and vice versa;
      * package/shot IDENTITY: the checkpoint's declared `package_id` and
        `shot_index` must agree with the ones its own request_id encodes.
        A mismatch is a refusal, never a guess about which one is right.

    `have` is a set of `(package_id, shot_index)` keys the response already
    covered — the response always wins where it spoke; recovery fills
    silence. Refused candidates land in `refused_out` (rid -> problems)
    when the caller passes a dict, purely for logging."""
    have = have or set()
    out: dict[tuple[str, int], dict] = {}
    for rid, cp in all_checkpoints(date).items():
        if not isinstance(cp, dict):
            continue
        parsed = parse_authored_shot_request_id(rid)
        kind = str(cp.get("request_kind") or "")
        if parsed is None and kind != "authored_shot":
            continue                    # the bundle-request lane's business
        if parsed is not None and parsed in have:
            continue                    # the response spoke — it wins
        problems: list[str] = []
        if parsed is None:
            problems.append(
                "request_kind is 'authored_shot' but the request_id is not "
                "the authored-<slug>-s<index> shape — cannot tell which "
                "package/shot this claims to back")
        elif kind != "authored_shot":
            problems.append(
                f"request_id names an authored shot but request_kind is "
                f"{kind!r} — a bundle-request checkpoint cannot back an "
                f"authored shot")
        else:
            pkg_id, idx = parsed
            got_pkg = str(cp.get("package_id") or "")
            if got_pkg != pkg_id:
                problems.append(
                    f"checkpoint declares package {got_pkg!r} but its "
                    f"request_id encodes {pkg_id!r} — identity mismatch, "
                    f"refusing rather than guessing which is right")
            try:
                if int(cp.get("shot_index")) != idx:
                    problems.append(
                        f"checkpoint declares shot {cp.get('shot_index')} "
                        f"but its request_id encodes shot {idx}")
            except Exception:                            # noqa: BLE001
                problems.append(
                    f"checkpoint has no usable shot_index (its request_id "
                    f"encodes shot {idx})")
        ptr = pointer_from_checkpoint(cp)
        if ptr is None:
            problems.append("checkpoint is not a usable pointer (not "
                            "verified, or missing file_id/sha256)")
        problems += checkpoint_problems(cp, date=date, bundle_id=bundle_id,
                                        request_id=rid, prompt=None)
        if problems:
            if refused_out is not None:
                refused_out[rid] = problems
            continue
        out[parsed] = ptr
    return out
