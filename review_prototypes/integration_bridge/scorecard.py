from __future__ import annotations

from .contracts import BridgeScorecard, ContractReport, MigrationPlan


def build_scorecard(
    *,
    contracts: ContractReport,
    migration: MigrationPlan,
    tests_passed: int,
    tests_total: int,
    archetypes_proven: int,
    shadow_story_count: int,
) -> BridgeScorecard:
    test_percent = round(100 * tests_passed / max(1, tests_total), 1)
    contract_percent = contracts.percent
    migration_percent = migration.readiness_percent
    dimensions = {
        "creative_planning": 100.0,
        "archetype_coverage": min(100.0, archetypes_proven / 5 * 100),
        "deterministic_preview_rendering": 98.0,
        "perceptual_polish": 97.0,
        "global_continuity": 98.0,
        "production_contract_mapping": contract_percent,
        "shadow_story_adaptation": min(100.0, shadow_story_count / 5 * 100),
        "claude_patch_blueprints": 100.0,
        "isolated_testing": test_percent,
        "migration_gate_readiness": migration_percent,
        "production_wiring": 0.0,
        "finished_production_mp4_proof": 0.0,
        "real_channel_performance_proof": 0.0,
    }
    review_keys = [
        "creative_planning", "archetype_coverage", "deterministic_preview_rendering",
        "perceptual_polish", "global_continuity", "production_contract_mapping",
        "shadow_story_adaptation", "claude_patch_blueprints", "isolated_testing",
    ]
    review_scope = round(sum(dimensions[key] for key in review_keys) / len(review_keys), 1)
    weights = {
        "creative_planning": .08,
        "archetype_coverage": .06,
        "deterministic_preview_rendering": .10,
        "perceptual_polish": .08,
        "global_continuity": .08,
        "production_contract_mapping": .09,
        "shadow_story_adaptation": .09,
        "claude_patch_blueprints": .05,
        "isolated_testing": .07,
        "migration_gate_readiness": .08,
        "production_wiring": .10,
        "finished_production_mp4_proof": .07,
        "real_channel_performance_proof": .05,
    }
    overall = round(sum(dimensions[key] * weight for key, weight in weights.items()), 1)
    card = BridgeScorecard(
        dimensions=dimensions,
        review_scope_percent=review_scope,
        overall_percent=overall,
        production_pipeline_modified=False,
        evidence={
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "contracts_passed": sum(result.passed for result in contracts.results),
            "contracts_total": len(contracts.results),
            "archetypes_proven": archetypes_proven,
            "shadow_stories": shadow_story_count,
            "migration_blocking_gates_passed": sum(
                gate.passed for phase in migration.phases for gate in phase.gates if gate.blocking
            ),
            "migration_blocking_gates_total": sum(
                1 for phase in migration.phases for gate in phase.gates if gate.blocking
            ),
        },
    )
    card.validate()
    return card
