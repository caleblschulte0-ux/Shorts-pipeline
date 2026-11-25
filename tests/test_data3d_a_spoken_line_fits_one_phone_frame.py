"""Every number and named thing in a spoken line can be SEEN in one phone frame, or the story gate refuses the line
(2026-11-25). The lava short failed seven storyboard rounds on lines the gate had passed: "erupted nine times", "a
hundred diggers and trucks", "only about a hundred people moved back". The board judge grades each shot against its
spoken line and no still shows nine eruptions or a hundred of anything. Offline: no brain is called here."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
sys.path.insert(0, str(D3 / "store"))
import story_gate as G  # noqa: E402

# the lava lines as they stood through seven failed board rounds (commit b22987e5d), kept verbatim
ROUND_7 = [
    "A volcano erupted nine times beside one Icelandic town, and everyone had to run.",
    "So Iceland built walls of rock three stories tall, with a hundred diggers and trucks working day and night.",
    "So when the lava came, it hit the wall and turned away from the town.",
    "But then the ground split open inside the wall, and lava poured straight into the streets.",
    "Three houses burned. The wall saved the rest, but only about a hundred people moved back. Would you?",
]
# the lines the shots passed the board under on 2026-11-25, kept verbatim
PASSED = [
    "A volcano keeps erupting right beside one Icelandic town, and everyone had to run.",
    "So Iceland built a wall of rock taller than a house to keep the lava out.",
    "So when the lava came, it hit the wall, and the wall held.",
    "But then the ground split open inside the wall, and lava poured into the streets.",
    "Three houses burned. The wall saved the rest, but almost nobody moved back. Would you?",
]


def test_the_lines_that_cost_seven_rounds_are_refused_by_name():
    probs = G.showable_problems({"lines": ROUND_7})
    assert [p.split(":")[0] for p in probs] == ["line 1", "line 2", "line 5"], probs
    assert "nine times" in probs[0] and "a hundred diggers" in probs[1] and "a hundred people" in probs[2]
    assert all(": SHOWABLE: " in p for p in probs)


def test_the_lines_that_passed_the_board_pass_the_floor():
    assert G.showable_problems({"lines": PASSED}) == []


def test_a_number_is_read_whether_it_is_said_in_words_or_digits():
    val = lambda s: [v for v, _, _, _ in G.numbers(s)]
    assert val("a hundred diggers") == [100]
    assert val("half a million cashier jobs in ten years") == [500000, 10]
    assert val("about twenty-five times") == [25]
    assert val("one hundred forty-nine dollars") == [149]
    assert val("2,500 trucks and 3 million tons") == [2500, 3000000]
    assert val("in the 1950s, and again in 2024") == [], "a year is a date, not a count"
    assert val("Three houses burned. One wall held.") == [3, 1]


def test_what_one_frame_cannot_show():
    for line in ("It erupted nine times.", "A hundred diggers worked.", "Only about a hundred people moved back.",
                 "It gets hit 25 times a year.", "Lightning flashes a hundred times every second.",
                 "Forty percent of the town left.", "40% never came back.", "Thousands of people ran.",
                 "It burns 12 houses a day.", "Dozens of trucks came.", "Half a million jobs went."):
        assert G.line_showable_problems(line), line


def test_what_one_frame_can_show():
    for line in ("Three houses burned.", "A wall three stories tall.", "A wall 30 feet tall, taller than a house.",
                 "One import in seven was fake.", "The jar ends twice as full.", "Almost nobody moved back.",
                 "Everyone had to run.", "Ten lanes, and nine of them are machines.", "It happened in 2023.",
                 "They picked it every day by hand."):
        assert not G.line_showable_problems(line), (line, G.line_showable_problems(line))


def test_the_countable_limit_is_the_most_this_channel_has_shown_as_a_count():
    assert G.COUNTABLE == 10
    assert not G.line_showable_problems("Ten lanes stood in a row.")
    assert G.line_showable_problems("Eleven lanes stood in a row.")


def test_the_gate_reports_an_unshowable_line_like_every_other_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "STORIES", tmp_path); (tmp_path / "new").mkdir()
    s = {"title": "T", "lines": ROUND_7, "links": ["so", "so", "but", "but"]}
    (tmp_path / "new" / G.NAME).write_text(json.dumps({"key": G.key(s), "pass": True}))
    probs = G.problems("new", s)
    assert len(probs) == 3 and all("SHOWABLE" in p for p in probs), "a passing verdict does not carry an unshowable line"
    ok = dict(s, lines=PASSED)
    (tmp_path / "new" / G.NAME).write_text(json.dumps({"key": G.key(ok), "pass": True}))
    assert G.problems("new", ok) == []


def test_the_cold_reader_must_name_the_one_picture_for_every_line():
    assert "pictures" in G.PROMPT and "unshowable" in G.PROMPT and "ONE picture" in G.PROMPT
    base = {"retell": "x", "twist": "y", "payoff": "z", "cut": [], "physical": [], "score": 80, "pass": True}
    good = dict(base, pictures=["a", "b", "c"], unshowable=[])
    assert G.parse(json.dumps(good), lines=3)["pass"]
    assert not G.parse(json.dumps(dict(good, unshowable=[2])), lines=3)["pass"], "a line no frame can show fails the story"
    assert not G.parse(json.dumps(dict(good, pictures=["a", "", "c"])), lines=3)["pass"], "a line with no picture named fails"
    assert not G.parse(json.dumps(dict(good, pictures=["a", "b"])), lines=3)["pass"], "one picture per line"
    v = G.parse(json.dumps(base), lines=3)
    assert not v["pass"] and any("no picture named for line 1" in p for p in v["problems"])
    assert "{title}" in G.PROMPT and G.PROMPT.format(title="t", lines="l", bar=G.PASS), "the brief still formats"


def test_the_judge_asks_about_every_line_of_the_script():
    src = (D3 / "store" / "story_gate.py").read_text()
    assert 'lines=len(script["lines"])' in src[src.index("def judge("):]
    assert "link_problems(script) + showable_problems(script)" in src[src.index("def problems("):]


def test_the_story_on_the_board_today_passes_and_the_bar_did_not_move():
    lava = json.loads((D3 / "stories" / "lava" / "script.json").read_text())
    assert G.showable_problems(lava) == []
    assert G.PASS == 75
