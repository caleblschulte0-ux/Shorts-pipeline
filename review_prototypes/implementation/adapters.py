from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .engine import PreviewRanker
from .models import (
    Decision,
    SceneCandidate,
    SceneDiagnosis,
    TemporalMetrics,
    Verdict,
)


class AdapterError(ValueError):
    pass


class ShowrunnerVerdictAdapter:
    """Convert showrunner JSON into the strict repair-runtime Verdict.

    This adapter is fail-closed. A blocked result without a structured
    weakest-scene diagnosis cannot drive targeted repair and is invalid.
    """

    STATUS_MAP = {
        "ship": Decision.SHIP,
        "pass": Decision.SHIP,
        "hold": Decision.HOLD,
        "block": Decision.HOLD,
        "reject": Decision.REJECT,
        "fail": Decision.REJECT,
    }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> Verdict:
        raw_status = str(
            payload.get(
                "decision",
                payload.get("verdict", payload.get("status", "")),
            )
        ).strip().lower()
        if raw_status not in cls.STATUS_MAP:
            raise AdapterError(
                f"unsupported showrunner status: {raw_status!r}"
            )

        hard_failures = cls._strings(
            payload.get(
                "hard_failures",
                payload.get("auto_fails", ()),
            )
        )
        decision = cls.STATUS_MAP[raw_status]
        if decision is Decision.HOLD and hard_failures:
            decision = Decision.REJECT

        score_value = payload.get("score")
        if not isinstance(score_value, (int, float)):
            raise AdapterError(
                "showrunner verdict requires a numeric score"
            )

        dimensions_value = payload.get("dimensions")
        if (
            not isinstance(dimensions_value, Mapping)
            or not dimensions_value
        ):
            raise AdapterError(
                "showrunner verdict requires dimensions"
            )

        diagnosis_payload = (
            payload.get("weakest_scene")
            or payload.get("diagnosis")
        )
        diagnosis = (
            cls._diagnosis(diagnosis_payload)
            if isinstance(diagnosis_payload, Mapping)
            else None
        )

        temporal_payload = payload.get("temporal")
        if temporal_payload is None:
            temporal_payload = {
                "effective_fps": payload.get("effective_fps", 0.0),
                "duplicate_ratio": payload.get(
                    "duplicate_ratio",
                    1.0,
                ),
                "longest_duplicate_run": payload.get(
                    "longest_duplicate_run",
                    0,
                ),
                "longest_unmarked_static_seconds": payload.get(
                    "longest_unmarked_static_seconds",
                    0.0,
                ),
            }

        verdict = Verdict(
            decision=decision,
            score=float(score_value),
            dimensions={
                str(k): float(v)
                for k, v in dimensions_value.items()
            },
            hard_failures=hard_failures,
            temporal=TemporalMetrics.from_dict(temporal_payload),
            weakest_scene=diagnosis,
            watched_video=cls._watched_video(payload),
            judge_version=str(
                payload.get("judge_version", "showrunner-unknown")
            ),
            adversarial_objections=cls._strings(
                payload.get("adversarial_objections", ())
            ),
        )
        try:
            verdict.validate()
        except ValueError as exc:
            raise AdapterError(str(exc)) from exc
        return verdict

    @classmethod
    def from_file(cls, path: Path) -> Verdict:
        try:
            payload = json.loads(
                Path(path).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise AdapterError(
                f"cannot read showrunner verdict {path}: {exc}"
            ) from exc
        if not isinstance(payload, Mapping):
            raise AdapterError(
                "showrunner verdict must be a JSON object"
            )
        return cls.from_payload(payload)

    @staticmethod
    def _diagnosis(value: Mapping[str, Any]) -> SceneDiagnosis:
        aliases = {
            "scene_id": value.get("scene_id", value.get("id")),
            "scene_index": value.get(
                "scene_index",
                value.get("index"),
            ),
            "start_seconds": value.get(
                "start_seconds",
                value.get("start"),
            ),
            "end_seconds": value.get(
                "end_seconds",
                value.get("end"),
            ),
            "failure_class": value.get(
                "failure_class",
                value.get("class"),
            ),
            "visible_evidence": value.get(
                "visible_evidence",
                value.get("evidence"),
            ),
            "root_cause": value.get(
                "root_cause",
                value.get("cause"),
            ),
            "repair_goal": value.get(
                "repair_goal",
                value.get("goal"),
            ),
        }
        missing = [
            name for name, item in aliases.items() if item is None
        ]
        if missing:
            raise AdapterError(
                "structured weakest_scene is incomplete; missing="
                + ",".join(missing)
            )
        try:
            return SceneDiagnosis.from_dict(aliases)
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterError(
                f"invalid weakest_scene diagnosis: {exc}"
            ) from exc

    @staticmethod
    def _watched_video(payload: Mapping[str, Any]) -> bool:
        if payload.get("watched_video") is True:
            return True
        evidence = payload.get("vision_evidence")
        return bool(
            isinstance(evidence, Mapping)
            and evidence.get("watched_video") is True
            and evidence.get("backend")
        )

    @staticmethod
    def _strings(value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        if isinstance(value, Sequence):
            return tuple(str(item) for item in value)
        raise AdapterError(
            f"expected a string sequence, got {type(value).__name__}"
        )


class JsonFileJudge:
    """Judge adapter for renderers that write a showrunner sidecar."""

    def __init__(self, *, filename: str = "showrunner.json") -> None:
        if not filename or "/" in filename or "\\" in filename:
            raise ValueError(
                "filename must be a simple relative file name"
            )
        self.filename = filename

    def judge(self, slug: str, rendered_dir: Path) -> Verdict:
        return ShowrunnerVerdictAdapter.from_file(
            Path(rendered_dir) / self.filename
        )


class VisionRankingAdapter(PreviewRanker):
    """Select from a previously generated vision-ranking payload."""

    def __init__(
        self,
        payloads: Mapping[str, Mapping[str, Any]],
    ) -> None:
        self.payloads = payloads

    def select(
        self,
        slug: str,
        diagnosis: SceneDiagnosis,
        candidates: Sequence[SceneCandidate],
    ) -> SceneCandidate:
        payload = self.payloads.get(diagnosis.scene_id)
        if not isinstance(payload, Mapping):
            raise AdapterError(
                "missing vision ranking for scene "
                f"{diagnosis.scene_id!r}"
            )
        if payload.get("watched_previews") is not True:
            raise AdapterError(
                "candidate ranking lacks watched_previews=true"
            )
        ordered = (
            payload.get("ordered_candidate_ids")
            or payload.get("ranking")
        )
        if (
            not isinstance(ordered, Sequence)
            or isinstance(ordered, str)
        ):
            raise AdapterError(
                "candidate ranking must contain an ordered ID list"
            )
        by_id = {
            candidate.candidate_id: candidate
            for candidate in candidates
        }
        for candidate_id in ordered:
            candidate = by_id.get(str(candidate_id))
            if candidate is not None:
                return candidate
        raise AdapterError(
            "vision ranking did not name an eligible candidate"
        )
