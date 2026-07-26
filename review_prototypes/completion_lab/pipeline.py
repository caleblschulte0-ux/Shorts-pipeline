from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
from typing import Any

from .audit import AuditLog
from .faults import apply_story_fault
from .models import Fault, PipelineResult, PipelineStatus, ProofRun, StorySpec, Verdict
from .proof import ProofStore, evaluate_two_run_proof, verdict_digest
from .release import ReleaseManifest, ReleaseRepository
from .services import SyntheticJudge, SyntheticRenderer


class CompletionPipeline:
    def __init__(self, root: Path, *, today: date) -> None:
        self.root = Path(root)
        self.today = today
        self.audit = AuditLog(self.root / "audit.jsonl")
        self.proofs = ProofStore(self.root / "proofs")
        self.releases = ReleaseRepository(self.root / "release_store")

    def run(self, story: StorySpec, *, fault: Fault = Fault.NONE) -> PipelineResult:
        events: list[str] = []
        story = apply_story_fault(story, fault)
        try:
            story.validate(today=self.today)
            self._event(events, "story_validated", {"slug": story.slug, "digest": story.digest})
        except Exception as exc:
            return self._hold(story.slug, events, f"story validation failed: {exc}")

        runs: list[ProofRun] = []
        final_render = None
        final_verdict: Verdict | None = None
        try:
            for index in (1, 2):
                renderer_fault = fault if fault in {Fault.RENDER_CRASH, Fault.MISSING_VIDEO} else Fault.NONE
                judge_fault = fault if fault in {Fault.MALFORMED_VERDICT, Fault.JUDGE_UNWATCHED, Fault.LOW_SCORE} else Fault.NONE
                renderer = SyntheticRenderer(renderer_fault)
                judge = SyntheticJudge(judge_fault)
                run_dir = self.root / "runs" / f"run-{index}"
                render = renderer.render(story, run_dir, attempt_id=f"attempt-{index}")
                render.validate()
                raw_verdict = judge.judge(story, render)
                if not isinstance(raw_verdict, Verdict):
                    raise ValueError("judge returned malformed verdict")
                raw_verdict.validate()
                verdict = raw_verdict
                renderer_version = renderer.version
                judge_version = judge.version
                if fault is Fault.VERSION_DRIFT and index == 2:
                    renderer_version = "synthetic-renderer-v2"
                payload = asdict(verdict)
                payload["hard_failures"] = list(verdict.hard_failures)
                proof = ProofRun(
                    run_id=f"{story.slug}-run-{index}",
                    suite_version=story.suite_version,
                    renderer_version=renderer_version,
                    judge_version=judge_version,
                    video_hash=render.video_hash,
                    verdict_hash=verdict_digest(payload),
                    score=verdict.score,
                    lowest_dimension=verdict.lowest_dimension,
                    effective_fps=verdict.effective_fps,
                    duplicate_ratio=verdict.duplicate_ratio,
                    watched_video=verdict.watched_video,
                    hard_failures=verdict.hard_failures,
                )
                self.proofs.record(proof)
                runs.append(proof)
                final_render = render
                final_verdict = verdict
                self._event(events, "proof_run_recorded", {"run_id": proof.run_id, "digest": proof.digest})
        except Exception as exc:
            return self._hold(story.slug, events, f"render or judge failed: {exc}")

        if fault is Fault.PROOF_TAMPER:
            proof_path = self.root / "proofs" / f"{runs[0].run_id}.json"
            data = json.loads(proof_path.read_text(encoding="utf-8"))
            data["score"] = 1
            proof_path.write_text(json.dumps(data), encoding="utf-8")
            try:
                self.proofs.load(runs[0].run_id)
            except ValueError as exc:
                return self._hold(story.slug, events, f"proof verification failed: {exc}")

        decision = evaluate_two_run_proof(runs)
        if not decision.passed:
            return self._hold(story.slug, events, *decision.reasons)
        self._event(events, "proof_gate_passed", {"runs": [run.run_id for run in runs]})

        assert final_render is not None and final_verdict is not None
        release_id = f"{story.slug}-{story.digest[:10]}"
        manifest = ReleaseManifest(
            release_id=release_id,
            story_slug=story.slug,
            video_hash=final_render.video_hash,
            proof_hashes=tuple(run.digest for run in runs),
            metadata={"score": final_verdict.score, "suite_version": story.suite_version},
        )
        try:
            release_path = self.releases.record(manifest, final_render.video_path)
            if fault is Fault.RELEASE_TAMPER:
                manifest_path = release_path / "manifest.json"
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                data["story_slug"] = "tampered"
                manifest_path.write_text(json.dumps(data), encoding="utf-8")
            self.releases.promote(release_id)
            self._event(events, "release_promoted", {"release_id": release_id})
        except Exception as exc:
            return self._hold(story.slug, events, f"release verification failed: {exc}")

        if fault is Fault.AUDIT_TAMPER:
            lines = self.audit.path.read_text(encoding="utf-8").splitlines()
            data = json.loads(lines[0])
            data["payload"]["slug"] = "tampered"
            lines[0] = json.dumps(data)
            self.audit.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            try:
                self.audit.verify()
            except ValueError as exc:
                return PipelineResult(PipelineStatus.HELD, story.slug, None, final_verdict.score, (f"audit verification failed: {exc}",), tuple(events))

        self.audit.verify()
        return PipelineResult(
            PipelineStatus.SHIPPED,
            story.slug,
            release_id,
            final_verdict.score,
            (),
            tuple(events),
            {"proof_runs": 2, "audit_events": len(self.audit.read())},
        )

    def exercise_rollback(self, first: StorySpec, second: StorySpec, *, fault: Fault = Fault.NONE) -> str:
        first_result = self.run(first)
        if first_result.status is not PipelineStatus.SHIPPED:
            raise ValueError("first release did not ship")
        second_result = self.run(second)
        if second_result.status is not PipelineStatus.SHIPPED:
            raise ValueError("second release did not ship")
        if fault is Fault.ROLLBACK_WITHOUT_TARGET:
            self.releases.history.write_text(json.dumps({"release_id": second_result.canonical_release_id, "previous": None}) + "\n", encoding="utf-8")
        return self.releases.rollback()

    def _event(self, events: list[str], kind: str, payload: dict[str, Any]) -> None:
        self.audit.append(kind, payload)
        events.append(kind)

    def _hold(self, slug: str, events: list[str], *reasons: str) -> PipelineResult:
        self.audit.append("held", {"slug": slug, "reasons": list(reasons)})
        events.append("held")
        return PipelineResult(PipelineStatus.HELD, slug, None, None, tuple(reasons), tuple(events))
