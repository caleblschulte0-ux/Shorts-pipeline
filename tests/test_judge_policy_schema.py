"""Judge-policy overrides are validated, atomic, and cannot remove the bar.

Doctor finding 9fe73cb62e3f: `judge_policy.load()` used to copy recognized
config values with no type/range validation and let env vars override every
field. A nonnumeric max_attempts survived load() and crashed the caller at
the later int() conversion; worse, a config could set the development /
owner-review floors to zero and flip autonomous_publish on, and decide()
would then advance a 0/10 film and mark autonomous publishing allowed.

These tests hold the repaired contract:
  * every override is schema-validated BEFORE use;
  * the config block is accepted or refused ATOMICALLY — one bad field and
    the whole block is refused (loudly) and the defaults stand;
  * the safety invariants are immune to config AND env: floors may only be
    raised, and autonomous_publish can never be enabled through load().

    python -m unittest tests.test_judge_policy_schema -v
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_learning import judge_policy as jp   # noqa: E402


class PolicyCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        # Any stray CURIOSITY_JUDGE_* var would contaminate every load().
        self._saved_env = {k: os.environ.pop(k) for k in list(os.environ)
                          if k.startswith(jp._ENV_PREFIX)}

    def tearDown(self):
        for k in list(os.environ):
            if k.startswith(jp._ENV_PREFIX):
                del os.environ[k]
        os.environ.update(self._saved_env)
        self._td.cleanup()

    def _config(self, block: dict) -> Path:
        p = Path(self._td.name) / "config.json"
        p.write_text(json.dumps({"judge_policy": block}))
        return p

    def _load(self, block: dict | None = None):
        """load() with stderr captured, returning (policy, stderr_text)."""
        buf = io.StringIO()
        with redirect_stderr(buf):
            pol = jp.load(self._config(block) if block is not None else None)
        return pol, buf.getvalue()


class TestTypedSchema(PolicyCase):
    def test_nonnumeric_max_attempts_keeps_defaults_and_does_not_crash(self):
        # The literal crash from the finding: 'abc' used to survive the
        # parse and blow up at int() AFTER load returned partial trust.
        pol, err = self._load({"max_attempts": "abc"})
        self.assertEqual(pol["max_attempts"],
                         jp.DEFAULT_POLICY["max_attempts"])
        self.assertIsInstance(pol["max_attempts"], int)
        self.assertIn("REFUSED", err)
        self.assertIn("max_attempts", err)

    def test_nan_and_infinity_are_refused(self):
        for bad in (float("nan"), float("inf")):
            pol, err = self._load({"repair_floor": bad})
            self.assertEqual(pol["repair_floor"],
                             jp.DEFAULT_POLICY["repair_floor"], bad)
            self.assertIn("REFUSED", err)

    def test_out_of_scale_scores_are_refused(self):
        pol, _ = self._load({"owner_floor": 25.0})
        self.assertEqual(pol["owner_floor"], jp.DEFAULT_POLICY["owner_floor"])

    def test_negative_or_zero_attempts_are_refused(self):
        for bad in (0, -3):
            pol, _ = self._load({"max_attempts": bad})
            self.assertEqual(pol["max_attempts"],
                             jp.DEFAULT_POLICY["max_attempts"], bad)

    def test_inverted_bands_are_refused(self):
        # internal_floor above owner_floor inverts the band system even
        # though each number is individually plausible. Raising every band
        # coherently stays above the safety floors, so 9.6/9.2/9.0 is the
        # clean inversion case.
        pol, err = self._load({"repair_floor": 9.6, "internal_floor": 9.2,
                               "owner_floor": 9.0})
        self.assertEqual(pol["repair_floor"],
                         jp.DEFAULT_POLICY["repair_floor"])
        self.assertIn("monotonic", err)

    def test_empty_required_judges_is_refused(self):
        # No required judges = nobody has to speak = everything fails open.
        pol, _ = self._load({"required_judges": []})
        self.assertEqual(pol["required_judges"],
                         jp.DEFAULT_POLICY["required_judges"])

    def test_rejection_is_atomic_the_valid_fields_die_with_the_block(self):
        # One bad field refuses the WHOLE block: applying "the fields that
        # happened to parse" would ship a policy nobody wrote.
        pol, err = self._load({"max_attempts": 5, "repair_floor": "junk"})
        self.assertEqual(pol["max_attempts"],
                         jp.DEFAULT_POLICY["max_attempts"])
        self.assertEqual(pol["repair_floor"],
                         jp.DEFAULT_POLICY["repair_floor"])
        self.assertIn("REFUSED", err)

    def test_a_valid_override_is_applied(self):
        pol, err = self._load({"max_attempts": 5, "repair_floor": 8.0,
                               "development_min_overall": 8.5})
        self.assertEqual(pol["max_attempts"], 5)
        self.assertEqual(pol["repair_floor"], 8.0)
        self.assertEqual(pol["development_min_overall"], 8.5)
        self.assertNotIn("REFUSED", err)

    def test_unknown_fields_are_still_ignored(self):
        pol, _ = self._load({"totally_new_knob": 1})
        self.assertNotIn("totally_new_knob", pol)


class TestSafetyInvariants(PolicyCase):
    """The floors and the publishing switch are LAW, not tunables."""

    def test_floor_lowering_config_is_refused(self):
        pol, err = self._load({"development_min_overall": 0,
                               "owner_review_min_overall": 0})
        self.assertEqual(pol["development_min_overall"],
                         jp.DEFAULT_POLICY["development_min_overall"])
        self.assertEqual(pol["owner_review_min_overall"],
                         jp.DEFAULT_POLICY["owner_review_min_overall"])
        self.assertIn("safety floor", err)
        # ...and the zero-score film the finding demonstrated stays blocked.
        d = jp.decide({"overall_10": 0, "personality": 5, "findings": [],
                       "verdicts": {n: {"status": "ok", "pass": True}
                                    for n in pol["required_judges"]}}, pol)
        self.assertFalse(d["advance"])

    def test_floor_raising_config_is_applied(self):
        # 8.5 stays under owner_review_min_overall (9.0) so the ordering
        # check holds; raising BOTH coherently is also lawful.
        pol, err = self._load({"development_min_overall": 8.5})
        self.assertEqual(pol["development_min_overall"], 8.5)
        self.assertNotIn("REFUSED", err)
        pol, err = self._load({"development_min_overall": 9.5,
                               "owner_review_min_overall": 9.5})
        self.assertEqual(pol["development_min_overall"], 9.5)
        self.assertNotIn("REFUSED", err)

    def test_advancement_floor_above_owner_floor_is_refused(self):
        # The ordering the finding called un-checked: the advancement floor
        # sliding past the owner-review floor is a config typo, not a law.
        pol, err = self._load({"development_min_overall": 9.5})
        self.assertEqual(pol["development_min_overall"],
                         jp.DEFAULT_POLICY["development_min_overall"])
        self.assertIn("REFUSED", err)

    def test_floor_lowering_env_is_refused(self):
        os.environ["CURIOSITY_JUDGE_MIN_PERSONALITY"] = "0"
        pol, err = self._load()
        self.assertEqual(pol["min_personality"],
                         jp.DEFAULT_POLICY["min_personality"])
        self.assertIn("REFUSED", err)

    def test_autonomous_publish_cannot_be_enabled_by_config(self):
        pol, err = self._load({"autonomous_publish": True})
        self.assertFalse(pol["autonomous_publish"])
        self.assertIn("autonomous_publish", err)

    def test_autonomous_publish_cannot_be_enabled_by_env(self):
        os.environ["CURIOSITY_JUDGE_AUTONOMOUS_PUBLISH"] = "true"
        pol, err = self._load()
        self.assertFalse(pol["autonomous_publish"])
        self.assertIn("REFUSED", err)

    def test_the_full_finding_scenario_stays_blocked(self):
        # development_min_overall=0 + owner_review_min_overall=0 +
        # autonomous_publish=true: the config from the finding's evidence.
        # It must load as the untouched default law.
        pol, _ = self._load({"development_min_overall": 0,
                             "owner_review_min_overall": 0,
                             "autonomous_publish": True})
        d = jp.decide({"overall_10": 0, "personality": 5, "findings": [],
                       "verdicts": {n: {"status": "ok", "pass": True}
                                    for n in pol["required_judges"]}}, pol)
        self.assertFalse(d["advance"])
        self.assertFalse(d["autonomous_publish_allowed"])


class TestEnvParsing(PolicyCase):
    def test_nonnumeric_env_var_is_refused_not_crashed(self):
        os.environ["CURIOSITY_JUDGE_MAX_ATTEMPTS"] = "many"
        pol, err = self._load()
        self.assertEqual(pol["max_attempts"],
                         jp.DEFAULT_POLICY["max_attempts"])
        self.assertIn("REFUSED", err)

    def test_valid_env_tuning_is_applied(self):
        os.environ["CURIOSITY_JUDGE_MAX_ATTEMPTS"] = "5"
        pol, _ = self._load()
        self.assertEqual(pol["max_attempts"], 5)
        self.assertIsInstance(pol["max_attempts"], int)


if __name__ == "__main__":
    unittest.main()
