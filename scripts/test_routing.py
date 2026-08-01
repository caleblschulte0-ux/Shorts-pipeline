#!/usr/bin/env python3
"""Unit tests for the Phase-3 routing law (scripts/post_curiosity.py).

The law under test:
  1. CURIOSITY_RENDERER defaults to "pro"; a slug with NO pro story FAILS
     CLOSED (quarantine) — it must NEVER silently run the legacy renderer.
  2. CURIOSITY_RENDERER=legacy is the only way to reach longform_render.
  3. An unknown renderer value refuses to run at all.
  4. The structured result (§8.4) carries the required keys, and
     publish_eligible is false whenever blocking reasons exist.

No rendering happens here: legacy is stubbed with a tripwire module and the
pro path is exercised only through its fail-closed branch (a slug that has no
beat story), so the suite runs in milliseconds with no network.
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import post_curiosity  # noqa: E402


class LegacyTripwire:
    """Stands in for data_learning.longform_render; records any call."""

    def __init__(self):
        self.calls = []

    def render(self, slug, out, config_path=None):
        self.calls.append(slug)


def _install_tripwire() -> LegacyTripwire:
    trip = LegacyTripwire()
    mod = types.ModuleType("data_learning.longform_render")
    mod.render = trip.render
    sys.modules["data_learning.longform_render"] = mod
    return trip


def test_pro_default_fails_closed_without_story():
    os.environ.pop("CURIOSITY_RENDERER", None)
    trip = _install_tripwire()
    r = post_curiosity._render_story(
        "no-such-story-xyz", REPO / "output" / "t.mp4", post_curiosity.CONFIG)
    assert r["engine"] == "pro", r
    assert r["produce"]["status"] == "quarantine", r
    assert "fail-closed" in r["produce"]["reasons"][0], r
    assert trip.calls == [], f"LEGACY WAS CALLED SILENTLY: {trip.calls}"
    print("ok  1. missing pro story -> quarantine, legacy NOT invoked")


def test_explicit_legacy_env_reaches_legacy():
    os.environ["CURIOSITY_RENDERER"] = "legacy"
    try:
        trip = _install_tripwire()
        r = post_curiosity._render_story(
            "kola-deepest-hole", REPO / "output" / "t.mp4", post_curiosity.CONFIG)
        assert r["engine"] == "legacy", r
        assert trip.calls == ["kola-deepest-hole"], trip.calls
        print("ok  2. CURIOSITY_RENDERER=legacy -> explicit legacy render")
    finally:
        os.environ.pop("CURIOSITY_RENDERER", None)


def test_unknown_renderer_refuses():
    os.environ["CURIOSITY_RENDERER"] = "wat"
    try:
        try:
            post_curiosity._render_story(
                "kola-deepest-hole", REPO / "output" / "t.mp4",
                post_curiosity.CONFIG)
        except SystemExit as e:
            assert "wat" in str(e)
            print("ok  3. unknown CURIOSITY_RENDERER refuses to run")
            return
        raise AssertionError("unknown renderer did not refuse")
    finally:
        os.environ.pop("CURIOSITY_RENDERER", None)


def test_structured_result_schema():
    blocked = post_curiosity._structured_result(
        "x", REPO / "output" / "does-not-exist.mp4",
        {"engine": "pro", "produce": None}, 0.0, ["reason A"])
    for key in ("ok", "slug", "video_path", "duration_seconds", "render_report",
                "performance_report", "fallback_report", "facts_report",
                "visual_verdict", "publish_eligible", "blocking_reasons"):
        assert key in blocked, f"missing {key}"
    assert blocked["publish_eligible"] is False and blocked["ok"] is False
    assert blocked["video_path"] is None          # honest: file absent
    clean = post_curiosity._structured_result(
        "x", REPO / "output" / "does-not-exist.mp4",
        {"engine": "pro", "produce": None}, 240.0, [])
    assert clean["publish_eligible"] is True and clean["ok"] is True
    print("ok  4. structured result schema + publish_eligible semantics")


if __name__ == "__main__":
    test_pro_default_fails_closed_without_story()
    test_explicit_legacy_env_reaches_legacy()
    test_unknown_renderer_refuses()
    test_structured_result_schema()
    print("routing law: 4/4 tests pass")
