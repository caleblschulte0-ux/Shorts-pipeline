"""NO PATH UPLOADS WITHOUT THE SHOWRUNNER.

CLAUDE.md: the showrunner is the permanent quality authority, explainer and
trending fail CLOSED, and "any workflow that publishes MUST carry
CLAUDE_CODE_OAUTH_TOKEN (or GEMINI_API_KEY as the fallback judge) on the
render step, and say so in its preflight."

Found live 2026-09-09: scripts/render_cinematic.py took `--upload` and
published to the EXPLAINER channel while referencing the showrunner zero
times, from explainer_cinematic.yml, which carried neither judge secret. An
ungated publish path is exactly what let trending ship six months of
unwatched videos while explainer was gated (docs/SYSTEM_AUDIT.md §B).

This is written as a SWEEP, not a spot-check on that one file: the next one
grows somewhere else.

    python -m unittest tests.test_no_ungated_publish -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"

# Scripts that construct an uploader purely to READ the API (analytics,
# pulling metadata). They never call .upload(), which the test verifies
# rather than taking on trust.
READ_ONLY_HINT = re.compile(r"_service\(\)")


def _uploads(src: str) -> bool:
    """Does this source actually publish, as opposed to building a client?"""
    if "YouTubeUploader" not in src and "TikTokUploader" not in src:
        return False
    return bool(re.search(r"\.upload\s*\(", src))


class TestEveryUploaderIsGated(unittest.TestCase):
    def _publishing_scripts(self) -> list[Path]:
        out = []
        for f in sorted((ROOT / "scripts").glob("*.py")):
            if f.name.startswith("test_"):
                continue
            if _uploads(f.read_text(errors="ignore")):
                out.append(f)
        return out

    def test_there_are_publishing_scripts_to_check(self):
        """A sweep that matches nothing passes vacuously forever."""
        self.assertTrue(self._publishing_scripts())

    def test_every_EXPLAINER_publisher_uses_the_SHARED_gate(self):
        """Scoped deliberately. The showrunner gates explainer and trending;
        third runs its own quality chain (content gate, render_qa, vision
        critic) and forcing the showrunner onto it would be a rearchitecture,
        not a fix. What must never happen is an explainer publisher with no
        gate — and 'has its own checks' is not good enough either, because a
        second copy of the policy is exactly how trending drifted away from
        explainer for six months (docs/SYSTEM_AUDIT.md §B)."""
        ungated = []
        for f in self._publishing_scripts():
            src = f.read_text(errors="ignore")
            if 'channel", default="explainer"' not in src.replace(
                    '"channel",default="explainer"',
                    '"channel", default="explainer"'):
                continue
            if "showrunner_gate" not in src:
                ungated.append(f.name)
        self.assertEqual(
            ungated, [],
            "these publish to the fail-closed explainer channel without the "
            "shared showrunner gate: " + ", ".join(ungated))

    def test_no_publisher_ships_with_NO_quality_gate_at_all(self):
        """The weaker, universal rule: whatever the channel, something must
        judge the cut before it goes out. render_story_v2.py had zero gate
        references and defaulted to --channel explainer."""
        naked = []
        for f in self._publishing_scripts():
            src = f.read_text(errors="ignore")
            if not any(k in src for k in ("showrunner", "clip_qa", "video_qa",
                                          "judge_content", "quality")):
                naked.append(f.name)
        self.assertEqual(naked, [],
                         "these upload with no pre-publish judgement at all: "
                         + ", ".join(naked))

    def test_the_cinematic_path_blocks_before_it_uploads(self):
        """Order matters: consulting the gate after uploading is theatre."""
        src = (ROOT / "scripts" / "render_cinematic.py").read_text()
        self.assertIn("showrunner_gate", src)
        self.assertLess(src.index('gate["blocked"]'),
                        src.index("YouTubeUploader(channel=a.channel)"))

    def test_a_block_returns_nonzero_rather_than_falling_through(self):
        src = (ROOT / "scripts" / "render_cinematic.py").read_text()
        held = src[src.index('if gate["blocked"]'):][:400]
        self.assertIn("return 1", held)


class TestEveryPublishingWorkflowCarriesAJudge(unittest.TestCase):
    """A fail-closed gate with no judge holds everything, green the whole
    way — the failure mode is silence, so the preflight must be loud."""

    def _publishing_workflows(self) -> list[Path]:
        """Workflows that can actually publish through a FAIL-CLOSED gate.

        Three conditions, all required, because each one alone is wrong:
        naming a publishing script is not enough (preview.yml and
        third-smoke.yml run them in dry-run and carry no token), and
        carrying a YouTube token is not enough either (pull_videos and the
        analytics jobs hold one purely to READ). The rule only binds where a
        held render means a published nothing — i.e. where the script routes
        through shared/showrunner_gate. Third runs its own quality chain and
        degrades to Groq rather than holding, so a hard preflight failure
        there would turn a degradation into an outage."""
        gated = {f.name for f in (ROOT / "scripts").glob("*.py")
                 if "showrunner_gate" in f.read_text(errors="ignore")}
        out = []
        for wf in sorted(WF.glob("*.yml")):
            body = wf.read_text()
            if "YOUTUBE_TOKEN_JSON" not in body:
                continue
            if any(name in body for name in gated):
                out.append(wf)
        return out

    def test_the_sweep_finds_the_publishing_workflows(self):
        self.assertTrue(self._publishing_workflows())

    def test_each_carries_a_judge_secret(self):
        missing = [wf.name for wf in self._publishing_workflows()
                   if "CLAUDE_CODE_OAUTH_TOKEN" not in wf.read_text()
                   and "GEMINI_API_KEY" not in wf.read_text()]
        self.assertEqual(
            missing, [],
            "these can publish but carry no showrunner judge, so the gate "
            "would hold every render while the run stays green: "
            + ", ".join(missing))

    def test_each_says_so_in_its_preflight(self):
        """CLAUDE.md requires the preflight to check, not just the env to
        carry it — an unset secret is silent otherwise."""
        silent = []
        for wf in self._publishing_workflows():
            body = wf.read_text()
            if not re.search(r'-z "\$CLAUDE_CODE_OAUTH_TOKEN"', body):
                silent.append(wf.name)
        self.assertEqual(
            silent, [],
            "these publish but never check for a judge in their preflight: "
            + ", ".join(silent))


if __name__ == "__main__":
    unittest.main(verbosity=2)
