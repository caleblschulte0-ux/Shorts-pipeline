from __future__ import annotations

import copy
import json
import unittest
from dataclasses import asdict

from .claude_handoff import execution_handoff, markdown_handoff
from .contracts import SUPPORTED_ACTIONS, SUPPORTED_KINDS
from .fixtures import archetype_story
from .manifest_bridge import augment_manifest, showrunner_context
from .patch_blueprints import migration_plan, patch_targets
from .production_probe import default_requirements, probe_sources
from .quality_compiler import compile_bridge
from .scorecard import build_scorecard
from .shadow_apply import apply_to_copy, existing_scene_plan_schema
from .story_adapter import adapt_story, story_to_mapping
from .verdict_router import route_verdict

ARCHETYPES = ("money", "share", "ranking", "comparison", "single")


def good_sources():
    sources = {}
    for req in default_requirements():
        defs = []
        for symbol in req.required_symbols:
            if symbol.isupper():
                defs.append(f"{symbol} = {{}}")
            elif symbol in {"Segment", "Story"}:
                defs.append(f"class {symbol}:\n    pass")
            else:
                defs.append(f"def {symbol}(*args, **kwargs):\n    return None")
        literal_blob = "\n".join(f"# {literal}" for literal in req.required_literals)
        sources[req.path] = (req.sha, "\n".join(defs) + "\n" + literal_blob)
    return sources


class ContractProbeTests(unittest.TestCase):
    def test_all_frozen_contracts_pass(self):
        report = probe_sources(default_requirements(), good_sources())
        self.assertTrue(report.passed)
        self.assertEqual(report.percent, 100.0)

    def test_sha_drift_fails_closed(self):
        sources = good_sources()
        path = default_requirements()[0].path
        _, source = sources[path]
        sources[path] = ("changed", source)
        report = probe_sources(default_requirements(), sources)
        self.assertFalse(report.passed)
        self.assertFalse(report.results[0].sha_matches)

    def test_missing_symbol_is_reported(self):
        sources = good_sources()
        requirement = default_requirements()[1]
        sha, source = sources[requirement.path]
        source = source.replace("def render_story_build", "def removed_render_story_build")
        sources[requirement.path] = (sha, source)
        report = probe_sources(default_requirements(), sources)
        result = next(item for item in report.results if item.path == requirement.path)
        self.assertIn("render_story_build", result.symbols_missing)

    def test_missing_literal_is_reported(self):
        sources = good_sources()
        requirement = default_requirements()[4]
        sha, source = sources[requirement.path]
        source = source.replace("# block", "")
        sources[requirement.path] = (sha, source)
        result = probe_sources(default_requirements(), sources).results[4]
        self.assertIn("block", result.literals_missing)

    def test_empty_sources_are_zero_percent(self):
        report = probe_sources(default_requirements(), {})
        self.assertFalse(report.passed)
        self.assertEqual(report.percent, 0.0)


class StoryAdapterTests(unittest.TestCase):
    def test_adapts_live_shaped_dataclasses(self):
        story = adapt_story(archetype_story("money"))
        self.assertEqual(story.slug, "grocery-bill-jump")
        self.assertEqual(len(story.scenes), 5)
        self.assertEqual(story.scenes[0].values[-1].period, 2026)

    def test_adapts_mapping_shape(self):
        live = archetype_story("comparison")
        raw = {
            "slug": live.slug, "title": live.title, "hook": live.hook, "closing": live.closing,
            "segments": [{
                "sentence": seg.sentence, "topic": seg.topic, "role": seg.role, "kind": seg.kind,
                "insight": {
                    "topic": seg.insight.topic, "unit": seg.insight.unit, "kind": seg.insight.kind,
                    "highlight_label": seg.insight.highlight_label,
                    "items": [asdict(point) for point in seg.insight.items],
                },
            } for seg in live.segments],
        }
        story = adapt_story(raw)
        self.assertEqual(story.scenes[0].current_kind, "comparison")
        self.assertEqual(story.scenes[0].values[0].label, "Option A")

    def test_mapping_export_is_json_serializable(self):
        payload = story_to_mapping(adapt_story(archetype_story("share")))
        json.dumps(payload)
        self.assertEqual(payload["scenes"][0]["role"], "hook")

    def test_missing_values_fails(self):
        live = archetype_story("single")
        live.segments[0].insight.items = []
        live.segments[0].anchors = []
        with self.assertRaises(ValueError):
            adapt_story(live)

    def test_unknown_explicit_role_is_inferred(self):
        live = archetype_story("ranking")
        live.segments[1].role = ""
        story = adapt_story(live)
        self.assertEqual(story.scenes[1].role, "explanation")


class CompilerTests(unittest.TestCase):
    def test_all_archetypes_compile(self):
        for name in ARCHETYPES:
            bundle = compile_bridge(adapt_story(archetype_story(name)))
            bundle.validate()
            self.assertEqual(len(bundle.overrides), 5)

    def test_only_production_supported_kinds_and_actions(self):
        for name in ARCHETYPES:
            bundle = compile_bridge(adapt_story(archetype_story(name)))
            self.assertTrue(all(item.kind in SUPPORTED_KINDS for item in bundle.overrides))
            self.assertTrue(all(item.performance in SUPPORTED_ACTIONS for item in bundle.overrides))

    def test_opening_and_payoff_share_callback(self):
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        self.assertEqual(bundle.overrides[0].callback_token, bundle.callback_token)
        self.assertEqual(bundle.overrides[-1].callback_token, bundle.callback_token)
        self.assertFalse(bundle.overrides[1].callback_token)

    def test_hook_has_motion_before_point_four(self):
        bundle = compile_bridge(adapt_story(archetype_story("ranking")))
        hook = bundle.overrides[0]
        self.assertLessEqual(hook.scene_timeline["events"][0]["t"], 0.4)
        self.assertTrue(any(event["action"] == "hook_burst" for event in hook.scene_timeline["events"]))

    def test_timelines_are_sorted_and_end_at_duration(self):
        bundle = compile_bridge(adapt_story(archetype_story("share")))
        for item in bundle.overrides:
            events = item.scene_timeline["events"]
            self.assertEqual([event["t"] for event in events], sorted(event["t"] for event in events))
            self.assertEqual(events[-1]["t"], item.scene_timeline["duration"])

    def test_consequence_and_payoff_have_landing_audio(self):
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        for index in (3, 4):
            self.assertTrue(any(cue["role"] == "payoff" for cue in bundle.overrides[index].audio_cues))

    def test_payoff_transition_is_callback_return(self):
        bundle = compile_bridge(adapt_story(archetype_story("comparison")))
        self.assertEqual(bundle.overrides[-1].transition_in["kind"], "callback_return")

    def test_compilation_is_deterministic(self):
        story = adapt_story(archetype_story("money"))
        self.assertEqual(compile_bridge(story).to_dict(), compile_bridge(story).to_dict())

    def test_fingerprint_changes_with_story_data(self):
        a = adapt_story(archetype_story("money"))
        live = archetype_story("money")
        live.segments[0].insight.items[-1].value += 1
        b = adapt_story(live)
        self.assertNotEqual(compile_bridge(a).story_fingerprint, compile_bridge(b).story_fingerprint)


class ShadowApplyTests(unittest.TestCase):
    def test_apply_mutates_copy_only(self):
        live = archetype_story("money")
        before = copy.deepcopy(live)
        bundle = compile_bridge(adapt_story(live))
        clone = apply_to_copy(live, bundle)
        self.assertEqual(live, before)
        self.assertTrue(clone.segments[0].insight.plan_locked)
        self.assertEqual(clone.segments[0].insight.perf_override, bundle.overrides[0].performance)

    def test_segment_and_insight_kind_stay_in_sync(self):
        live = archetype_story("share")
        bundle = compile_bridge(adapt_story(live))
        clone = apply_to_copy(live, bundle)
        for segment in clone.segments:
            self.assertEqual(segment.kind, segment.insight.kind)

    def test_scene_count_mismatch_fails(self):
        live = archetype_story("money")
        bundle = compile_bridge(adapt_story(live))
        live.segments.pop()
        with self.assertRaises(ValueError):
            apply_to_copy(live, bundle)

    def test_existing_plan_schema_is_backward_compatible(self):
        bundle = compile_bridge(adapt_story(archetype_story("ranking")))
        schema = existing_scene_plan_schema(bundle)
        self.assertEqual(set(schema["0"]), {"viz", "perf"})
        self.assertEqual(len(schema), 5)


class ManifestTests(unittest.TestCase):
    def test_manifest_preserves_production_fields(self):
        base = {"slug": "x", "total": 20.0, "hook_window": [0, 2], "segment_windows": [[0, 2], [2, 6]], "kinds": ["trend"]}
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        result = augment_manifest(base, bundle)
        for key, value in base.items():
            self.assertEqual(result[key], value)
        self.assertIn("quality_bridge", result)

    def test_manifest_without_windows_fails_closed(self):
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        with self.assertRaises(ValueError):
            augment_manifest({"slug": "x"}, bundle)

    def test_showrunner_context_has_scene_goals(self):
        story = adapt_story(archetype_story("share"))
        context = showrunner_context(story, compile_bridge(story))
        self.assertEqual(len(context["quality_bridge"]["scene_plans"]), 5)
        self.assertTrue(context["quality_bridge"]["scene_plans"][0]["goal"])


class VerdictRoutingTests(unittest.TestCase):
    def test_ship_gets_no_repair(self):
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        self.assertIsNone(route_verdict({"verdict": "ship", "score": 90}, bundle))

    def test_block_is_preserved(self):
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        directive = route_verdict({"verdict": "block", "score": 65, "dimensions": {}}, bundle)
        self.assertEqual(directive.preserve_verdict, "block")
        self.assertIn("never flip", directive.acceptance_rule)

    def test_auto_fail_targets_named_scene(self):
        bundle = compile_bridge(adapt_story(archetype_story("share")))
        verdict = {"verdict": "block", "auto_fails": ["dead_air: seg2 frozen"], "dimensions": {}}
        directive = route_verdict(verdict, bundle)
        self.assertEqual(directive.target_segment, 2)
        self.assertIn("dead_air", directive.target_reason)

    def test_candidates_are_structural(self):
        bundle = compile_bridge(adapt_story(archetype_story("comparison")))
        directive = route_verdict({"verdict": "block", "dimensions": {"mascot": 0}}, bundle)
        self.assertEqual(len(directive.candidates), 3)
        self.assertTrue(any(candidate["structurally_different"] for candidate in directive.candidates))


class MigrationTests(unittest.TestCase):
    def test_patch_targets_reference_exact_production_files(self):
        self.assertEqual({target.path for target in patch_targets()}, {
            "data_learning/story.py", "data_learning/studio_render.py", "scripts/post_stories.py",
            "scripts/scene_repair.py", "scripts/repair_loop.py", "scripts/showrunner_review.py",
        })

    def test_default_plan_is_blocked_before_preview(self):
        plan = migration_plan()
        self.assertEqual(plan.next_phase.name, "Shadow manifest")
        self.assertLess(plan.readiness_percent, 100)

    def test_complete_evidence_unlocks_all_phases(self):
        plan = migration_plan(baseline_preview_saved=True, bridge_preview_saved=True, full_mp4_watched=True, showrunner_two_run_pass=True, real_channel_holdout=True)
        self.assertIsNone(plan.next_phase)
        self.assertEqual(plan.readiness_percent, 100.0)

    def test_showrunner_target_is_high_risk_and_diagnostic_only(self):
        target = next(item for item in patch_targets() if item.path.endswith("showrunner_review.py"))
        self.assertEqual(target.risk, "high")
        self.assertIn("do not alter", target.change)

    def test_publish_freeze_gate_is_present(self):
        self.assertIn("publish freeze", [gate.name for phase in migration_plan().phases for gate in phase.gates])


class HandoffAndScorecardTests(unittest.TestCase):
    def test_handoff_contains_commands_and_boundaries(self):
        contracts = probe_sources(default_requirements(), good_sources())
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        payload = execution_handoff(bundle, contracts, migration_plan())
        self.assertFalse(payload["scope_boundary"]["production_modified"])
        self.assertTrue(payload["first_commands_for_claude"])
        self.assertEqual(payload["production_contracts"]["percent"], 100.0)

    def test_markdown_lists_exact_targets(self):
        contracts = probe_sources(default_requirements(), good_sources())
        bundle = compile_bridge(adapt_story(archetype_story("money")))
        text = markdown_handoff(execution_handoff(bundle, contracts, migration_plan()))
        self.assertIn("data_learning/story.py::build", text)
        self.assertIn("scripts/showrunner_review.py::review_video", text)
        self.assertIn("Showrunner authority changed: **false**", text)

    def test_scorecard_is_honest(self):
        contracts = probe_sources(default_requirements(), good_sources())
        card = build_scorecard(contracts=contracts, migration=migration_plan(), tests_passed=43, tests_total=43, archetypes_proven=5, shadow_story_count=5)
        self.assertEqual(card.dimensions["production_wiring"], 0.0)
        self.assertEqual(card.dimensions["real_channel_performance_proof"], 0.0)
        self.assertGreater(card.review_scope_percent, 95)
        self.assertLess(card.overall_percent, 80)

    def test_handoff_json_roundtrip(self):
        contracts = probe_sources(default_requirements(), good_sources())
        payload = execution_handoff(compile_bridge(adapt_story(archetype_story("single"))), contracts, migration_plan())
        self.assertEqual(json.loads(json.dumps(payload))["status"], payload["status"])


if __name__ == "__main__":
    unittest.main()
