from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CreativeSignature:
    video_id: str
    hook_type: str
    closing_pattern: str
    chapter_transition_families: tuple[str, ...] = ()
    character_actions: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()
    visual_families: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepetitionPolicy:
    history_window: int = 10
    hook_limit_in_five: int = 2
    closing_limit_in_five: int = 2
    transition_family_limit_per_video: int = 3
    character_action_limit_per_video: int = 2
    visual_family_share_warning: float = 0.45
    forbid_asset_reuse: bool = True


@dataclass(frozen=True)
class RepetitionResult:
    valid: bool
    diversity_score: float
    hard_blocks: tuple[str, ...]
    warnings: tuple[str, ...]


def evaluate_repetition(
    candidate: CreativeSignature,
    history: Iterable[CreativeSignature],
    *,
    policy: RepetitionPolicy = RepetitionPolicy(),
) -> RepetitionResult:
    recent = tuple(history)[-policy.history_window:]
    last_five = recent[-5:]
    hard_blocks: list[str] = []
    warnings: list[str] = []
    penalty = 0.0

    hook_count = sum(item.hook_type == candidate.hook_type for item in last_five)
    if hook_count >= policy.hook_limit_in_five:
        warnings.append(f"hook_type_overused:{candidate.hook_type}")
        penalty += 15

    closing_count = sum(item.closing_pattern == candidate.closing_pattern for item in last_five)
    if closing_count >= policy.closing_limit_in_five:
        warnings.append(f"closing_pattern_overused:{candidate.closing_pattern}")
        penalty += 15

    transition_counts = Counter(candidate.chapter_transition_families)
    for family, count in transition_counts.items():
        if count > policy.transition_family_limit_per_video:
            warnings.append(f"transition_family_repeated:{family}:{count}")
            penalty += min(20, (count - policy.transition_family_limit_per_video) * 5)

    action_counts = Counter(candidate.character_actions)
    for action, count in action_counts.items():
        if count > policy.character_action_limit_per_video:
            warnings.append(f"character_action_repeated:{action}:{count}")
            penalty += min(15, (count - policy.character_action_limit_per_video) * 4)

    if candidate.visual_families:
        dominant_family, dominant_count = Counter(candidate.visual_families).most_common(1)[0]
        share = dominant_count / len(candidate.visual_families)
        if share > policy.visual_family_share_warning:
            warnings.append(f"dominant_visual_family:{dominant_family}:{share:.2f}")
            penalty += min(20, (share - policy.visual_family_share_warning) * 50)

    historical_assets = {asset for item in recent for asset in item.asset_ids}
    reused_assets = sorted(set(candidate.asset_ids) & historical_assets)
    if reused_assets:
        message = "asset_reuse:" + ",".join(reused_assets)
        if policy.forbid_asset_reuse:
            hard_blocks.append(message)
        else:
            warnings.append(message)
        penalty += min(30, len(reused_assets) * 10)

    score = max(0.0, round(100.0 - penalty, 1))
    return RepetitionResult(not hard_blocks, score, tuple(hard_blocks), tuple(sorted(set(warnings))))
