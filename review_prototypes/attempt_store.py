#!/usr/bin/env python3
"""Isolated design prototype for transactional repair attempts.

NOT WIRED INTO THE PIPELINE.

This module demonstrates the state guarantees the production repair controller
should eventually provide:

- each attempt owns an immutable plan, verdict, and rendered artifact set;
- a candidate never overwrites the incumbent before comparison;
- promotion copies one complete attempt into a canonical directory atomically;
- a losing candidate cannot leave a worse scene plan active;
- missing or malformed verdicts are never promotable.

Claude should adapt the ideas to the live data model rather than importing this
prototype directly.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping


@dataclass(frozen=True)
class AttemptRef:
    slug: str
    run_id: str
    attempt_id: str
    path: Path


class AttemptStoreError(RuntimeError):
    """Raised when an attempt cannot be safely recorded or promoted."""


class AttemptStore:
    """Filesystem-backed, append-only attempt storage.

    Directory layout::

        root/<slug>/<run_id>/attempt_0/
            scene_plan.json
            verdict.json
            video.mp4
            scenes/
        root/<slug>/<run_id>/winner.json
        canonical/<slug>/
            scene_plan.json
            verdict.json
            video.mp4
            scenes/

    Attempt directories are immutable after ``record_attempt`` returns.
    Canonical state changes only through ``promote``.
    """

    REQUIRED_FILES = ("scene_plan.json", "verdict.json", "video.mp4")

    def __init__(self, root: Path, canonical_root: Path) -> None:
        self.root = Path(root)
        self.canonical_root = Path(canonical_root)

    def record_attempt(
        self,
        *,
        slug: str,
        run_id: str,
        attempt_id: str,
        scene_plan: Mapping[str, Any],
        verdict: Mapping[str, Any],
        video_path: Path,
        scenes_path: Path | None = None,
    ) -> AttemptRef:
        """Create one immutable attempt from complete input artifacts."""
        destination = self.root / slug / run_id / attempt_id
        if destination.exists():
            raise AttemptStoreError(f"attempt already exists: {destination}")
        if not Path(video_path).is_file():
            raise AttemptStoreError(f"video is missing: {video_path}")
        self._validate_verdict(verdict)

        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{attempt_id}-", dir=destination.parent))
        try:
            self._write_json(staging / "scene_plan.json", scene_plan)
            self._write_json(staging / "verdict.json", verdict)
            shutil.copy2(video_path, staging / "video.mp4")
            if scenes_path is not None and Path(scenes_path).exists():
                shutil.copytree(scenes_path, staging / "scenes")
            self._fsync_tree(staging)
            os.replace(staging, destination)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

        return AttemptRef(slug=slug, run_id=run_id, attempt_id=attempt_id, path=destination)

    def load_verdict(self, attempt: AttemptRef) -> dict[str, Any]:
        path = attempt.path / "verdict.json"
        try:
            verdict = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AttemptStoreError(f"invalid verdict at {path}: {exc}") from exc
        self._validate_verdict(verdict)
        return verdict

    def choose_better(self, incumbent: AttemptRef, candidate: AttemptRef) -> AttemptRef:
        """Return the better attempt using deterministic full-video ordering."""
        left = self._rank(self.load_verdict(incumbent))
        right = self._rank(self.load_verdict(candidate))
        return candidate if right > left else incumbent

    def promote(self, winner: AttemptRef) -> Path:
        """Atomically replace canonical state with one complete attempt.

        Promotion copies into a sibling staging directory and then swaps the
        complete directory. At no point is a partial candidate canonical.
        """
        self._assert_complete(winner.path)
        canonical = self.canonical_root / winner.slug
        canonical.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{winner.slug}-promote-", dir=canonical.parent))
        backup = canonical.with_name(f".{canonical.name}.previous")
        try:
            shutil.rmtree(staging)
            shutil.copytree(winner.path, staging)
            self._fsync_tree(staging)
            if backup.exists():
                shutil.rmtree(backup)
            if canonical.exists():
                os.replace(canonical, backup)
            os.replace(staging, canonical)
            shutil.rmtree(backup, ignore_errors=True)
        except Exception:
            if not canonical.exists() and backup.exists():
                os.replace(backup, canonical)
            shutil.rmtree(staging, ignore_errors=True)
            raise

        winner_file = self.root / winner.slug / winner.run_id / "winner.json"
        self._write_json(
            winner_file,
            {
                "slug": winner.slug,
                "run_id": winner.run_id,
                "attempt_id": winner.attempt_id,
                "canonical_path": str(canonical),
            },
        )
        return canonical

    @staticmethod
    def _rank(verdict: Mapping[str, Any]) -> tuple[int, int, float, float, float, float]:
        """Rank complete-video verdicts from safety to craft.

        Ordering:
        1. known verdict beats unknown;
        2. ship beats block;
        3. zero hard failures beats any hard failure;
        4. higher total score;
        5. higher weakest dimension;
        6. higher effective FPS and lower duplicate ratio.
        """
        status = str(verdict.get("verdict", "unknown")).lower()
        known = int(status in {"ship", "block"})
        ships = int(status == "ship")
        hard_failures = verdict.get("hard_failures") or verdict.get("auto_fails") or []
        no_hard_failures = int(len(hard_failures) == 0)
        score = float(verdict.get("score") or 0.0)
        dimensions = verdict.get("dimensions") or {}
        weakest = min((float(v) for v in dimensions.values()), default=0.0)
        temporal = verdict.get("temporal") or {}
        effective_fps = float(temporal.get("effective_fps") or 0.0)
        duplicate_ratio = float(temporal.get("duplicate_ratio") or 1.0)
        return (known, ships, no_hard_failures, score, weakest, effective_fps - duplicate_ratio)

    @classmethod
    def _assert_complete(cls, path: Path) -> None:
        missing = [name for name in cls.REQUIRED_FILES if not (path / name).is_file()]
        if missing:
            raise AttemptStoreError(f"attempt is incomplete; missing {missing}: {path}")

    @staticmethod
    def _validate_verdict(verdict: Mapping[str, Any]) -> None:
        status = verdict.get("verdict")
        if status not in {"ship", "block", "unknown"}:
            raise AttemptStoreError(f"unsupported verdict: {status!r}")
        if status != "unknown" and not isinstance(verdict.get("score"), (int, float)):
            raise AttemptStoreError("known verdict requires numeric score")

    @staticmethod
    def _write_json(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
        path.write_text(payload, encoding="utf-8")
        with path.open("rb") as handle:
            os.fsync(handle.fileno())

    @staticmethod
    def _fsync_tree(path: Path) -> None:
        for item in path.rglob("*"):
            if item.is_file():
                with item.open("rb") as handle:
                    os.fsync(handle.fileno())


__all__ = ["AttemptRef", "AttemptStore", "AttemptStoreError"]
