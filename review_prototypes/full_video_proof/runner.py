from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Protocol

from .models import StoryProof, SuiteRunProof
from .store import ProofStore


class StoryProofExecutor(Protocol):
    def execute(self, slug: str, run_id: str) -> StoryProof: ...


@dataclass(frozen=True)
class ProofRunConfig:
    run_id: str
    suite_version: str
    judge_version: str
    renderer_commit: str
    slugs: tuple[str, ...]


class FullVideoProofRunner:
    def __init__(self, executor: StoryProofExecutor, store: ProofStore) -> None:
        self.executor = executor
        self.store = store

    def run(self, config: ProofRunConfig) -> SuiteRunProof:
        stories = tuple(self.executor.execute(slug, config.run_id) for slug in config.slugs)
        manifest_payload = {
            "run_id": config.run_id,
            "suite_version": config.suite_version,
            "judge_version": config.judge_version,
            "renderer_commit": config.renderer_commit,
            "stories": [
                {
                    "slug": story.slug,
                    "video": story.video_sha256,
                    "verdict": story.verdict_sha256,
                }
                for story in stories
            ],
        }
        digest = hashlib.sha256(
            json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        proof = SuiteRunProof(
            run_id=config.run_id,
            suite_version=config.suite_version,
            judge_version=config.judge_version,
            renderer_commit=config.renderer_commit,
            stories=stories,
            artifact_manifest_sha256=digest,
        )
        proof.validate(config.slugs)
        self.store.save(proof)
        return proof
