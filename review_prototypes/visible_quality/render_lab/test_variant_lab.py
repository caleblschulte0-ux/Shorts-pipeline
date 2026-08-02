from __future__ import annotations

import unittest

from .variant_effects import VARIANT_RENDERERS, render_variant
from .variant_lab import choose_variant, compile_transition, generate_variants, render_variant_keyframes, transition_sequence

MONEY_STORY = {
    "topic": "Grocery prices",
    "claim": "The same basket got much more expensive.",
    "unit": "$",
    "data": [
        {"label": "2019", "value": 680, "period": 2019},
        {"label": "2022", "value": 860, "period": 2022},
        {"label": "2026", "value": 1030, "period": 2026},
    ],
}
SHARE_STORY = {
    "topic": "Electricity mix",
    "claim": "One source dominates the grid.",
    "unit": "%",
    "data": [
        {"label": "Fossil", "value": 62},
        {"label": "Clean", "value": 38},
    ],
}


class VariantSelectionTests(unittest.TestCase):
    def test_money_time_series_has_receipt_and_cart_options(self):
        names = [v.name for v in generate_variants(MONEY_STORY)]
        self.assertIn("receipt_roll", names)
        self.assertIn("cart_overflow", names)

    def test_recent_variant_gets_novelty_penalty(self):
        normal = choose_variant(MONEY_STORY)
        repeated = generate_variants(MONEY_STORY, recent=(normal.name,))
        self.assertNotEqual(repeated[0].name, normal.name)

    def test_share_story_selects_share_squeeze(self):
        self.assertEqual(choose_variant(SHARE_STORY).name, "share_squeeze")

    def test_all_variants_have_high_first_frame_energy(self):
        self.assertTrue(all(v.first_frame_energy >= 88 for v in generate_variants(MONEY_STORY)))


class VariantRenderTests(unittest.TestCase):
    def test_every_variant_renderer_returns_vertical_svg(self):
        data = tuple(MONEY_STORY["data"])
        for name in VARIANT_RENDERERS:
            story_data = tuple(SHARE_STORY["data"]) if name == "share_squeeze" else data
            svg = render_variant(name, .55, story_data, "Test")
            self.assertIn("<svg", svg)
            self.assertIn('width="1080"', svg)
            self.assertIn('height="1920"', svg)

    def test_receipt_contains_both_prices(self):
        svg = render_variant("receipt_roll", 1.0, tuple(MONEY_STORY["data"]), "Receipt")
        self.assertIn("$680", svg)
        self.assertIn("$1,030", svg)

    def test_cart_turns_delta_into_consequence(self):
        svg = render_variant("cart_overflow", 1.0, tuple(MONEY_STORY["data"]), "Cart")
        self.assertIn("THE EXTRA $350", svg)
        self.assertIn("doesn&#x27;t fit quietly", svg)

    def test_keyframe_pack_has_frame_one_effort_payoff(self):
        pack = render_variant_keyframes(MONEY_STORY, "receipt_roll")
        self.assertEqual(set(pack), {"frame_one", "effort", "payoff"})


class TransitionTests(unittest.TestCase):
    def test_same_focus_uses_object_match_cut(self):
        plan = compile_transition({"focus_label": "2026"}, {"focus_label": "2026"})
        self.assertEqual(plan.kind, "object_match_cut")

    def test_line_to_stack_uses_data_morph(self):
        plan = compile_transition(
            {"visual_event": "line_draws", "focus_label": "2026"},
            {"visual_event": "burden_stack", "focus_label": "household"},
        )
        self.assertEqual(plan.kind, "data_morph")

    def test_impact_scene_gets_fast_cut(self):
        plan = compile_transition({"visual_event": "scale_collision"}, {"visual_event": "reaction"})
        self.assertEqual(plan.kind, "impact_cut")
        self.assertLessEqual(plan.duration, .12)

    def test_callback_token_returns_opening_object(self):
        plan = compile_transition({"callback_token": "2019_vs_2026"}, {"callback_token": "2019_vs_2026"})
        self.assertEqual(plan.kind, "callback_return")

    def test_sequence_has_one_less_transition_than_scenes(self):
        scenes = ({"focus_label": "a"}, {"focus_label": "b"}, {"focus_label": "c"})
        self.assertEqual(len(transition_sequence(scenes)), 2)


if __name__ == "__main__":
    unittest.main()
