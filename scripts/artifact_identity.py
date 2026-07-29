#!/usr/bin/env python3
"""Content-addressed identity for a rendered curiosity package (PR#173 adoption A).

Adapted from experiments/curiosity_nextgen/artifact_manifest.py into the REAL
package shapes the producer emits. Two jobs:

1. MANIFEST — after a successful render+director run, hash every artifact that
   defines the film (video, story beats, facts registry, captions, thumbnail,
   meta, fallback ledger) into ``<out>_pkg/manifest.json``. The manifest is the
   package's identity: any later mutation of any listed artifact is detectable
   by recomputation, and downstream records (verdicts, approvals) bind to these
   hashes instead of trusting file mtimes.

2. VERIFY — recompute the hashes and report exactly which artifacts are
   missing or changed. Verification is pure and read-only.

The mtime-based stale-verdict guard in produce.evaluate remains as a secondary
(belt-and-braces) check; the hash binding is primary.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1

# artifact key -> path resolver relative to the output mp4
def _artifact_paths(out: Path, story_path: Path | None) -> dict[str, Path]:
    pkg = out.with_name(out.stem + "_pkg")
    paths = {
        "video": out,
        "captions": out.with_suffix(".srt"),
        "thumbnail": out.with_suffix(".jpg"),
        "meta": out.with_suffix(".meta.json"),
        "fallbacks": pkg / "fallbacks.json",
    }
    if story_path is not None:
        paths["story"] = story_path
        facts = story_path.with_name(story_path.name.replace(".beats.json",
                                                             ".facts.json"))
        if facts != story_path and facts.exists():
            paths["facts"] = facts
    return paths


def canonical_json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _renderer_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001 — identity still works without git
        return "unknown"


def manifest_path(out: Path) -> Path:
    return out.with_name(out.stem + "_pkg") / "manifest.json"


def build_manifest(out: Path, story_path: Path | None = None,
                   director_rc: int | None = None,
                   extra: dict | None = None) -> dict:
    """Hash the package and write ``<out>_pkg/manifest.json`` atomically.
    Missing OPTIONAL artifacts are recorded as absent (honest), but a missing
    video is an error — there is no identity without the film."""
    if not out.exists():
        raise FileNotFoundError(f"cannot build a manifest without the video: {out}")
    artifacts = {}
    for key, p in _artifact_paths(out, story_path).items():
        if p.exists():
            artifacts[key] = {"path": str(p.relative_to(REPO) if p.is_relative_to(REPO) else p),
                              "sha256": sha256_file(p),
                              "size_bytes": p.stat().st_size}
        else:
            artifacts[key] = None
    payload = {
        "schema_version": SCHEMA_VERSION,
        "slug": out.stem.replace("curiosity_", ""),
        "renderer_commit": _renderer_commit(),
        "director_rc": director_rc,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
    }
    if extra:
        payload["extra"] = extra
    payload["manifest_sha256"] = sha256(canonical_json_bytes(
        {k: v for k, v in payload.items() if k != "manifest_sha256"})).hexdigest()
    dest = manifest_path(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(dest)
    return payload


def load_manifest(out: Path) -> dict | None:
    p = manifest_path(out)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def verify_manifest(out: Path, story_path: Path | None = None) -> tuple[bool, list[str]]:
    """Recompute every recorded hash. Returns (ok, reasons). Fail closed: a
    missing manifest, a missing recorded artifact, or any changed hash is a
    reason. Artifacts recorded as absent must STILL be absent (a file appearing
    from nowhere is also a change of identity)."""
    m = load_manifest(out)
    if m is None:
        return False, ["no package manifest (pkg/manifest.json)"]
    reasons: list[str] = []
    current = _artifact_paths(out, story_path)
    for key, rec in m.get("artifacts", {}).items():
        p = current.get(key)
        if rec is None:
            if p is not None and p.exists():
                reasons.append(f"{key}: appeared after manifest was written")
            continue
        if p is None or not p.exists():
            reasons.append(f"{key}: recorded but missing on disk")
            continue
        if sha256_file(p) != rec["sha256"]:
            reasons.append(f"{key}: content changed since manifest")
    # integrity of the manifest itself
    recomputed = sha256(canonical_json_bytes(
        {k: v for k, v in m.items() if k != "manifest_sha256"})).hexdigest()
    if recomputed != m.get("manifest_sha256"):
        reasons.append("manifest self-hash mismatch (manifest edited by hand)")
    return (not reasons, reasons)


def mp4_sha256(out: Path) -> str | None:
    return sha256_file(out) if out.exists() else None
