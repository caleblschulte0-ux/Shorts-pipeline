from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Mapping, Sequence

from .contracts import MediaAsset, RequestPlan
from .providers import InternetArchiveAdapter, OpenverseAdapter, PexelsAdapter, WikimediaAdapter


_LICENSE_ALIASES = {"cc0": "CC0-1.0", "public domain": "PDM-1.0", "pdm": "PDM-1.0", "cc-by": "CC-BY", "cc by": "CC-BY", "cc-by-sa": "CC-BY-SA", "cc by-sa": "CC-BY-SA"}


class RightsNormalizer:
    def normalize(self, raw: str) -> str:
        value = re.sub(r"\s+", " ", raw.strip().lower())
        for needle, normalized in _LICENSE_ALIASES.items():
            if needle in value:
                return normalized
        return raw.strip() or "unknown"

    def is_reusable(self, license_code: str, *, allow_attribution: bool = True, allow_share_alike: bool = True) -> bool:
        normalized = self.normalize(license_code).upper()
        if normalized in {"CC0-1.0", "PDM-1.0", "PUBLIC DOMAIN"}:
            return True
        if allow_attribution and normalized.startswith("CC-BY"):
            return allow_share_alike or "SA" not in normalized
        return False


class AssetDeduper:
    @staticmethod
    def exact_digest(data: bytes) -> str:
        return sha256(data).hexdigest()

    @staticmethod
    def hamming_distance(hash_a: str, hash_b: str) -> int:
        if len(hash_a) != len(hash_b):
            raise ValueError("hashes must have equal length")
        return sum(bin(int(a, 16) ^ int(b, 16)).count("1") for a, b in zip(hash_a, hash_b))

    def duplicate_groups(self, assets: Sequence[MediaAsset]) -> tuple[tuple[str, ...], ...]:
        by_hash: dict[str, list[str]] = {}
        for asset in assets:
            if asset.content_hash:
                by_hash.setdefault(asset.content_hash, []).append(asset.asset_id)
        return tuple(tuple(ids) for ids in by_hash.values() if len(ids) > 1)


@dataclass(frozen=True)
class AssetQuality:
    asset_id: str
    score: float
    reasons: tuple[str, ...]


class MediaQualityScorer:
    def score(self, asset: MediaAsset, *, target_ratio: float = 9 / 16, min_width: int = 720, min_height: int = 1280) -> AssetQuality:
        score = 100.0
        reasons: list[str] = []
        if asset.width < min_width or asset.height < min_height:
            score -= 25
            reasons.append("below_target_resolution")
        if asset.aspect_ratio:
            penalty = min(25.0, abs(asset.aspect_ratio - target_ratio) * 40.0)
            score -= penalty
            if penalty > 8:
                reasons.append("poor_portrait_fit")
        if asset.media_type == "video" and asset.duration_seconds < 1.5:
            score -= 10
            reasons.append("too_short")
        if not asset.description.strip():
            score -= 5
            reasons.append("missing_description")
        if asset.license_code.lower() == "unknown":
            score -= 40
            reasons.append("unknown_rights")
        return AssetQuality(asset.asset_id, max(score, 0.0), tuple(reasons))


@dataclass(frozen=True)
class BrollNeed:
    beat_id: str
    narration: str
    visual_goal: str
    preferred_evidence: tuple[str, ...]
    search_phrases: tuple[str, ...]
    forbidden_visuals: tuple[str, ...] = ()


class BrollPlanner:
    _GENERIC_WORDS = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "for", "on", "is", "was", "are"}

    def plan(self, beats: Sequence[Mapping[str, str]]) -> tuple[BrollNeed, ...]:
        results: list[BrollNeed] = []
        for index, beat in enumerate(beats):
            narration = beat.get("narration", "").strip()
            visual_goal = beat.get("visual_goal", "show the concrete subject and evidence").strip()
            terms = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", narration) if token.lower() not in self._GENERIC_WORDS]
            phrase = " ".join(terms[:7]) or visual_goal
            evidence = ("primary_source_capture", "real_event_footage", "diagram", "licensed_stock", "generated_hero_shot")
            results.append(BrollNeed(str(beat.get("id", f"beat_{index}")), narration, visual_goal, evidence, (phrase, visual_goal)))
        return tuple(results)


class MediaSearchRouter:
    def __init__(self) -> None:
        self.pexels = PexelsAdapter()
        self.openverse = OpenverseAdapter()
        self.wikimedia = WikimediaAdapter()
        self.archive = InternetArchiveAdapter()

    def plan(self, query: str, *, include_stock: bool = True, include_open: bool = True, include_archive: bool = True) -> tuple[RequestPlan, ...]:
        plans: list[RequestPlan] = []
        if include_stock:
            plans.append(self.pexels.search_video(query))
        if include_open:
            plans.extend((self.openverse.search_images(query), self.wikimedia.search_files(query)))
        if include_archive:
            plans.append(self.archive.search(query))
        return tuple(plans)
