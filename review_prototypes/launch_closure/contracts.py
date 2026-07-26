from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Contract:
    path: str
    sha: str
    required_symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.path or self.path.startswith("/") or ".." in self.path.split("/"):
            raise ValueError("contract path must be repository-relative and safe")
        if len(self.sha) != 40 or any(c not in "0123456789abcdef" for c in self.sha):
            raise ValueError("contract sha must be a lowercase 40-character hex sha")
        if not self.required_symbols:
            raise ValueError("contract must pin at least one symbol")


CONTRACTS: tuple[Contract, ...] = (
    Contract("data_learning/story.py", "800749549b318c769b9d415a3adbbab7f6013788", ("Segment", "Story", "build")),
    Contract("data_learning/viz_director.py", "2dde8b4b40f85b89dd39632a2d55d7a18ff5105e", ("KINDS", "renderable", "assign")),
    Contract("data_learning/charts.py", "36ef92763bbf0598cb4d0c51b5d6e5c7e3572942", ("FULLFRAME_RENDERERS", "FALLBACK", "render_story_build")),
    Contract("data_learning/mascot_director.py", "69022728bead3101f9a34ce60f74ba0387dda068", ("compose_anim", "author_performance", "performance_for")),
    Contract("data_learning/scene_timeline.py", "2c62baa1cbc70a63fe95816729459654581c9ea0", ("PHASES", "plan_scene", "HOOK_BURST_T")),
    Contract("data_learning/studio_render.py", "bfd62356a9cbb7f03a17e36bea06a44849c0e013", ("render", "synth_narration", "_build_soundtrack")),
    Contract("scripts/showrunner_review.py", "c4162ea390c692cc0715a994343ae03187f7d8dd", ("WEIGHTS", "AUTOFAIL_CHECKS", "decide_verdict")),
    Contract("scripts/repair_loop.py", "6a5ed3d7a8f8f3ad5a6948de89862c58d2092853", ("REMEDIES", "pick_remedy", "better", "repair")),
)


def validate_snapshot(rows: Iterable[dict]) -> dict:
    by_path = {row.get("path"): row for row in rows}
    missing = []
    sha_mismatch = []
    symbol_mismatch = []
    for contract in CONTRACTS:
        row = by_path.get(contract.path)
        if row is None:
            missing.append(contract.path)
            continue
        if row.get("sha") != contract.sha:
            sha_mismatch.append(contract.path)
        available = set(row.get("symbols") or ())
        needed = set(contract.required_symbols)
        if not needed.issubset(available):
            symbol_mismatch.append({"path": contract.path, "missing": sorted(needed - available)})
    return {
        "ok": not (missing or sha_mismatch or symbol_mismatch),
        "contracts_total": len(CONTRACTS),
        "contracts_present": len(CONTRACTS) - len(missing),
        "missing": missing,
        "sha_mismatch": sha_mismatch,
        "symbol_mismatch": symbol_mismatch,
    }


def canonical_snapshot() -> list[dict]:
    return [{"path": c.path, "sha": c.sha, "symbols": list(c.required_symbols)} for c in CONTRACTS]
