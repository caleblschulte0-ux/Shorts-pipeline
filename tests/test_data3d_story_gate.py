"""A 3D short's script is judged as a STORY before a shot is built (caaleb 2026-11-23: "Ok but why do our scripts
suck"). Lightning's payoff did not pay off its title and honey's first draft was three beats of trivia; every gate we
had looked at the picture. Offline: no brain is called here."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "tools" / "data3d" / "store"
sys.path.insert(0, str(STORE))
import story_gate as G  # noqa: E402

S = {"title": "T", "lines": ["hook", "a", "b", "c"], "links": ["so", "but", "so"]}


def test_a_line_must_follow_from_the_one_before():
    assert G.link_problems(S) == []
    assert G.link_problems(dict(S, links=["so", "and then", "so"]))
    assert G.link_problems(dict(S, links=["so", "but"])), "one link per line after the hook"
    assert G.link_problems({k: v for k, v in S.items() if k != "links"})


def test_no_verdict_or_a_stale_one_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "STORIES", tmp_path); (tmp_path / "new").mkdir()
    assert any("no story verdict" in p for p in G.problems("new", S))
    (tmp_path / "new" / G.NAME).write_text(json.dumps({"key": G.key(S), "pass": True}))
    assert G.problems("new", S) == []
    assert any("older script" in p for p in G.problems("new", dict(S, lines=["hook", "a", "b", "changed"])))
    (tmp_path / "new" / G.NAME).write_text(json.dumps({"key": G.key(S), "pass": False, "score": 60, "cut": [3]}))
    assert any("failed" in p for p in G.problems("new", S))


def test_a_pass_needs_a_twist_the_bar_and_nothing_to_cut():
    good = '{"retell": "x", "twist": "y", "payoff": "z", "cut": [], "score": 80, "pass": true}'
    assert G.parse(good)["pass"]
    assert not G.parse(good.replace('"twist": "y"', '"twist": ""'))["pass"]
    assert not G.parse(good.replace('"cut": []', '"cut": [3]'))["pass"]
    assert not G.parse(good.replace('"score": 80', '"score": 70'))["pass"]
    assert G.parse("no json") is None


def test_shots_refuse_to_build_a_script_that_is_not_a_story():
    src = (STORE / "shots.py").read_text()
    assert "story_gate.problems(STORY, SCRIPT)" in src
    assert src.index("story_gate.problems(STORY, SCRIPT)") < src.index("# ---------------------------------------------------------------- timing from the voice")


def test_only_old_stories_are_grandfathered_and_the_list_only_shrinks():
    have = {p.name for p in (ROOT / "tools" / "data3d" / "stories").iterdir() if (p / "script.json").exists()}
    assert G.GRANDFATHERED <= have, "a grandfathered story that no longer exists comes off the list"
    assert "honey" not in G.GRANDFATHERED


def test_a_line_that_cannot_be_a_physical_event_fails_the_story():
    """2026-11-23: honey's lab tests and prices could only be props on tables, and the board failed every shot"""
    good = '{"retell": "x", "twist": "y", "payoff": "z", "cut": [], "physical": [], "score": 80, "pass": true}'
    assert G.parse(good)["pass"]
    assert not G.parse(good.replace('"physical": []', '"physical": [3]'))["pass"]
    assert "big physical event in a real place" in G.PROMPT
