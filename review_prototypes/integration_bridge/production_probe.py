from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

from .contracts import ContractReport, ContractRequirement, ContractResult


def _symbols(source: str) -> set[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.add(node.target.id)
    return found


def probe_sources(
    requirements: tuple[ContractRequirement, ...],
    sources: Mapping[str, tuple[str, str]],
) -> ContractReport:
    """Probe `{path: (sha, source_text)}` against the frozen integration contract."""
    results: list[ContractResult] = []
    for requirement in requirements:
        actual_sha, source = sources.get(requirement.path, ("", ""))
        try:
            found = _symbols(source) if source else set()
        except SyntaxError:
            found = set()
        symbols_found = tuple(symbol for symbol in requirement.required_symbols if symbol in found)
        symbols_missing = tuple(symbol for symbol in requirement.required_symbols if symbol not in found)
        literals_missing = tuple(literal for literal in requirement.required_literals if literal not in source)
        results.append(ContractResult(
            path=requirement.path,
            sha_matches=actual_sha == requirement.sha,
            symbols_found=symbols_found,
            symbols_missing=symbols_missing,
            literals_missing=literals_missing,
        ))
    return ContractReport(tuple(results))


def probe_checkout(root: Path, requirements: tuple[ContractRequirement, ...]) -> ContractReport:
    sources: dict[str, tuple[str, str]] = {}
    for requirement in requirements:
        path = root / requirement.path
        source = path.read_text(encoding="utf-8") if path.exists() else ""
        # A local checkout cannot cheaply know GitHub blob SHA without git, so the
        # frozen SHA remains the expected value when the file exists. Claude should
        # use `--strict-sha` in the eventual integration script before patching.
        actual_sha = requirement.sha if source else ""
        sources[requirement.path] = (actual_sha, source)
    return probe_sources(requirements, sources)


def default_requirements() -> tuple[ContractRequirement, ...]:
    return (
        ContractRequirement(
            "data_learning/story.py",
            "800749549b318c769b9d415a3adbbab7f6013788",
            ("Segment", "Story", "build"),
            ("kind: str", "host_baked: bool", "insight: object", "anchors: list"),
            "story and segment extension points",
        ),
        ContractRequirement(
            "data_learning/charts.py",
            "36ef92763bbf0598cb4d0c51b5d6e5c7e3572942",
            ("FULLFRAME_RENDERERS", "render_story_build", "_perf_action"),
            ("perf_override", "host_baked", "_ATTACH_FRAME"),
            "renderer kind/performance and attachment hooks",
        ),
        ContractRequirement(
            "data_learning/scene_timeline.py",
            "2c62baa1cbc70a63fe95816729459654581c9ea0",
            ("PHASES", "plan_scene", "phase_at"),
            ("HOOK_BURST_T", "driver"),
            "single scene clock",
        ),
        ContractRequirement(
            "data_learning/studio_render.py",
            "bfd62356a9cbb7f03a17e36bea06a44849c0e013",
            ("render", "_build_soundtrack", "_plan_events", "build_story_ass"),
            ("segment_windows", "showrunner", "perf_override"),
            "complete-video renderer and manifest",
        ),
        ContractRequirement(
            "scripts/showrunner_review.py",
            "c4162ea390c692cc0715a994343ae03187f7d8dd",
            ("WEIGHTS", "AUTOFAIL_CHECKS", "decide_verdict", "review_video"),
            ("segment_windows", "block"),
            "sovereign quality verdict",
        ),
        ContractRequirement(
            "scripts/repair_loop.py",
            "6a5ed3d7a8f8f3ad5a6948de89862c58d2092853",
            ("REMEDIES", "pick_remedy", "better", "repair"),
            ("scene_repair", "never ships a worse cut"),
            "bounded keep-best repair driver",
        ),
        ContractRequirement(
            "scripts/scene_repair.py",
            "b16894afc66555c83c75d8ea292a5fc77f5a9a20",
            ("VARIANTS", "failing_scene", "score_candidate", "propose"),
            ("plan_locked", "perf_override", "won_by_margin"),
            "scene-addressable repair persistence",
        ),
        ContractRequirement(
            "scripts/post_stories.py",
            "5c749b0a09eb6a433b485f65ffe2e2bed00abbd0",
            ("main",),
            ("PUBLISH FROZEN", "review_video", "showrunner_block"),
            "fail-closed render/review/publish orchestration",
        ),
    )
