from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .models import ProofRun


@dataclass(frozen=True)
class ProofDecision:
    passed: bool
    reasons: tuple[str, ...]


class ProofStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def record(self, run: ProofRun) -> Path:
        path = self.root / f"{run.run_id}.json"
        if path.exists():
            raise ValueError("proof run is immutable")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {**run.canonical_payload(), "digest": run.digest}
        path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return path

    def load(self, run_id: str) -> ProofRun:
        data = json.loads((self.root / f"{run_id}.json").read_text(encoding="utf-8"))
        digest = data.pop("digest")
        run = ProofRun(
            run_id=data["run_id"],
            suite_version=data["suite_version"],
            renderer_version=data["renderer_version"],
            judge_version=data["judge_version"],
            video_hash=data["video_hash"],
            verdict_hash=data["verdict_hash"],
            score=data["score"],
            lowest_dimension=data["lowest_dimension"],
            effective_fps=data["effective_fps"],
            duplicate_ratio=data["duplicate_ratio"],
            watched_video=data["watched_video"],
            hard_failures=tuple(data["hard_failures"]),
        )
        if run.digest != digest:
            raise ValueError("proof digest mismatch")
        return run


def evaluate_two_run_proof(runs: Iterable[ProofRun]) -> ProofDecision:
    items = tuple(runs)
    reasons: list[str] = []
    if len(items) != 2:
        reasons.append("exactly two proof runs are required")
        return ProofDecision(False, tuple(reasons))
    versions = {(run.suite_version, run.renderer_version, run.judge_version) for run in items}
    if len(versions) != 1:
        reasons.append("proof versions drifted")
    for run in items:
        if not run.watched_video:
            reasons.append(f"{run.run_id}: video was not watched")
        if run.hard_failures:
            reasons.append(f"{run.run_id}: hard failures present")
        if run.score < 90 or run.lowest_dimension < 8.5:
            reasons.append(f"{run.run_id}: quality threshold missed")
        if run.effective_fps < 24 or run.duplicate_ratio > 0.10:
            reasons.append(f"{run.run_id}: temporal threshold missed")
        if not run.video_hash or not run.verdict_hash:
            reasons.append(f"{run.run_id}: evidence hash missing")
    return ProofDecision(not reasons, tuple(reasons))


def verdict_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
