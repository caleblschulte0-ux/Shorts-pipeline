from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .contracts import CommandPlan, ScoreCard


class VisionCommandPlanner:
    def clip_score(self, image_paths: Sequence[str], prompt: str, output_json: str, *, model: str = "openai/clip-vit-base-patch32") -> CommandPlan:
        if not image_paths:
            raise ValueError("at least one image is required")
        return CommandPlan(
            tool="clip",
            argv=("python", "-m", "review_prototypes.capability_studio.free_workers", "clip-score", "--model", model, "--prompt", prompt, "--output", output_json, *image_paths),
            inputs=tuple(image_paths), outputs=(output_json,),
            notes=("Runs locally with optional transformers, torch, and Pillow dependencies.",),
        )

    def perceptual_hashes(self, image_paths: Sequence[str], output_json: str) -> CommandPlan:
        if not image_paths:
            raise ValueError("at least one image is required")
        return CommandPlan(
            tool="pillow",
            argv=("python", "-m", "review_prototypes.capability_studio.free_workers", "dhash", "--output", output_json, *image_paths),
            inputs=tuple(image_paths), outputs=(output_json,),
        )

    def sam2_mask(self, image: str, checkpoint: str, config: str, output_mask: str, *, prompt_json: str) -> CommandPlan:
        return CommandPlan(
            tool="sam2",
            argv=("python", "-m", "review_prototypes.capability_studio.free_workers", "sam2-mask", "--image", image, "--checkpoint", checkpoint, "--config", config, "--prompt-json", prompt_json, "--output", output_mask),
            inputs=(image, checkpoint, config, prompt_json), outputs=(output_mask,),
            notes=("SAM 2 model weights are downloaded separately and may have their own license terms.",),
        )

    def mediapipe_track(self, video: str, output_json: str, *, mode: str = "pose") -> CommandPlan:
        if mode not in {"pose", "face", "hands"}:
            raise ValueError("mode must be pose, face, or hands")
        return CommandPlan(
            tool="mediapipe",
            argv=("python", "-m", "review_prototypes.capability_studio.free_workers", "mediapipe-track", "--mode", mode, "--video", video, "--output", output_json),
            inputs=(video,), outputs=(output_json,),
        )


@dataclass(frozen=True)
class VisualCandidateMetrics:
    candidate_id: str
    semantic_match: float
    legibility: float
    contrast: float
    novelty: float
    safe_area: float
    duplicate_similarity: float = 0.0


class LocalVisualRanker:
    WEIGHTS: Mapping[str, float] = {"semantic_match": 0.32, "legibility": 0.24, "contrast": 0.16, "novelty": 0.16, "safe_area": 0.12}

    def score(self, candidate: VisualCandidateMetrics) -> ScoreCard:
        values = {
            "semantic_match": candidate.semantic_match,
            "legibility": candidate.legibility,
            "contrast": candidate.contrast,
            "novelty": candidate.novelty,
            "safe_area": candidate.safe_area,
        }
        hard_failures: list[str] = []
        if candidate.safe_area < 0.55:
            hard_failures.append("unsafe_text_or_subject_placement")
        if candidate.duplicate_similarity > 0.96:
            hard_failures.append("near_duplicate")
        if any(not 0.0 <= value <= 1.0 for value in values.values()):
            hard_failures.append("metric_out_of_range")
        return ScoreCard(candidate.candidate_id, values, tuple(hard_failures), (f"duplicate_similarity={candidate.duplicate_similarity:.3f}",))

    def winner(self, candidates: Sequence[VisualCandidateMetrics]) -> VisualCandidateMetrics:
        if not candidates:
            raise ValueError("at least one candidate is required")
        scored = [(self.score(candidate).weighted_total(self.WEIGHTS), candidate) for candidate in candidates]
        eligible = [item for item in scored if item[0] != float("-inf")]
        if not eligible:
            raise ValueError("all visual candidates failed hard gates")
        return max(eligible, key=lambda item: item[0])[1]
