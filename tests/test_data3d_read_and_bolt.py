"""READ and BOLT: what the judge still saw in the lightning remakes after POP, HOLD, FAR and EMPTY all passed.

Round 2, 2026-11-20. Every check was green on the remakes, and the judge failed three of them:
  READ  the truck: sheet frames 9-24 "one pose while the arcs crawl", 25-32 "a dead second"; the jolt, hat hop,
        cower, hand check and shrug "too small to see". HOLD measures 7 cm in the world; the judge reads a phone-sized
        sheet. READ measures his move ON SCREEN, through the shot camera (store/motion.py READ).
  BOLT  the tower: "the copper rod, cab roof and windsock are never in frame, so the bolts ... read as lightning
        striking Data, not the rod"; the ridge: "a near-horizontal bolt streaks along the grass", "a bolt cuts in front
        of his body". staging.far now measures each strike's channel as the viewer sees it (store/motion.py BOLT).

The fixtures (tests/fixtures/data3d_motion/screen_*.json) are the real animation of each judged take, dumped frame by
frame through the harness with no render: the shot camera of every frame, his READ points in the world, and every
strike near him as the viewer sees it (its channel on screen, which of its points pass over his body, how close it
lands to his outline, how steep it falls). The trail (72) and the beach (71) passed the judge; both must pass."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "tools" / "data3d" / "store"
FIX = Path(__file__).resolve().parent / "fixtures" / "data3d_motion"
sys.path.insert(0, str(STORE)); sys.path.insert(0, str(STORE.parent))
import motion as MO  # noqa: E402

PASSING = ["screen_trail_pass72", "screen_beach_pass71"]
FAILING = ["screen_truck_fail52", "screen_tower_fail42", "screen_ridge_fail46"]


def _load(name):
    d = json.loads((FIX / f"{name}.json").read_text())
    d["pts"] = [[None if p is None else tuple(x / 1000 for x in p) for p in fr] for fr in d["pts"]]
    return d


def _holds(d):
    return MO.read_holds(d["cams"], d["pts"], d["asp"])


def _react(d):
    return dict(MO.reactions(d["cams"], d["pts"], d["asp"], [s["start"] for s in d["strikes"]]))


# ---------------------------------------------------------------- READ: still on the judge's sheet
def test_the_passed_beats_never_hold_still_on_screen_longer_than_read_hold():
    longest = {n: max(s for *_, s in _holds(_load(n))) for n in PASSING}
    assert longest["screen_trail_pass72"] == pytest.approx(0.60, abs=0.04)
    assert longest["screen_beach_pass71"] == pytest.approx(0.77, abs=0.04)
    assert max(longest.values()) < MO.READ_HOLD


def test_the_trucks_crawling_arcs_and_dead_second_are_too_small_to_read():
    """judge: sheet frames 9-24 "one pose while the arcs crawl", 25-32 "a dead second": frames 33-93 and 97-125. The
    truck passed HOLD (7 cm in the world, 0.67 s): his hands moved 0.07 of the frame while the rest of him sat still"""
    dead = [s for s in _holds(_load("screen_truck_fail52")) if s[2] > MO.READ_HOLD]
    assert dead, "the truck must fail READ"
    a, b, sec = max(dead, key=lambda s: s[2])
    assert sec == pytest.approx(2.73, abs=0.1)
    assert a <= 60 and b >= 125, (a, b)                      # it covers the judge's 9-24 (from his arm going out) and 25-32


def test_a_mean_not_a_max_one_hand_flicking_is_still_a_still_frame():
    cam = {"mi": [[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, -3]], "rect": [-0.3, 0.3, -0.5, 0.5]}   # a lens 3 m back, looking +y
    still = [(0.0, 0.0, z / 10) for z in range(10)]
    flick = lambda i: [(0.0, 0.0, z / 10) for z in range(9)] + [(0.08 * (i % 2), 0.0, 0.9)]       # one hand of ten
    pts = [flick(i) for i in range(60)]
    assert max(s for *_, s in MO.read_holds([cam] * 60, pts, 0.5625)) > MO.READ_HOLD
    whole = [[(0.12 * (i % 2), 0.0, z / 10) for z in range(10)] for i in range(60)]                # the whole body jolts
    assert not [s for s in MO.read_holds([cam] * 60, whole, 0.5625) if s[2] > MO.READ_HOLD]
    assert MO.read_holds([cam] * 60, [still] * 60, 0.5625)[0][2] == pytest.approx(59 / 30)


def test_a_camera_move_is_not_his_move():
    cams = [{"mi": [[1, 0, 0, -0.01 * i], [0, 0, 1, 0], [0, -1, 0, -3]], "rect": [-0.3, 0.3, -0.5, 0.5]} for i in range(60)]
    pts = [[(0.0, 0.0, z / 10) for z in range(10)]] * 60                 # he is still, the lens trucks sideways 0.6 m
    assert MO.read_holds(cams, pts, 0.5625)[0][2] == pytest.approx(59 / 30)


def test_every_strike_near_him_moves_him_where_the_judge_could_see_it():
    for n in PASSING:
        r = _react(_load(n))
        assert min(r.values()) >= MO.REACT_MIN, (n, r)
    truck = _react(_load("screen_truck_fail52"))
    assert truck[129] < MO.REACT_MIN, "the truck's second strike: 'no big palms-up shrug'"
    tower = _react(_load("screen_tower_fail42"))
    assert tower[61] < MO.REACT_MIN, "the tower's second strike: 'the hot-foot dance barely registers'"
    # calibration: trail 0.136 0.136 0.067, beach 0.090 0.053; truck 0.052 0.026; tower 0.070 0.033 0.114
    assert MO.REACT_MIN < 0.053 and MO.REACT_MIN > 0.033


def test_what_read_does_not_separate_is_written_down():
    """the truck's first jolt moves him as much as the beach's second strike, which passed: READ does not claim it"""
    assert _react(_load("screen_truck_fail52"))[13] == pytest.approx(_react(_load("screen_beach_pass71"))[73], abs=0.005)
    assert "NOT separate" in (STORE / "motion.py").read_text()


# ---------------------------------------------------------------- BOLT: the event's object is in the shot
def _bolts(name):
    d = _load(name); out = {}
    for s in d["strikes"]:
        him = s["to_him_m"] <= MO.TARGET_R
        for fr in s["frames"]:
            flags = ["" if c == "." else c for c in fr["flags"]]
            for p in MO.bolt_problems([tuple(q) if q else None for q in fr["path"]], flags, fr["ring"], him, fr["tilt"]):
                out.setdefault(s["name"], []).append((fr["f"], p))
    return out


def test_the_passed_beats_strikes_all_read():
    for n in PASSING:
        assert _bolts(n) == {}, n


def test_the_towers_bolts_read_as_striking_data_not_the_rod():
    probs = _bolts("screen_tower_fail42")
    assert "s2 bolt 1" in probs and "s2 bolt 2" in probs
    assert any("reads as lightning striking him" in p for _, p in probs["s2 bolt 1"])
    assert any("passes behind his body" in p for _, p in probs["s2 bolt 2"])
    assert any("leaves the frame" in p for _, p in probs["s2 bolt 2"])     # at f97-99, behind him
    assert all(s["to_him_m"] > 1.3 for s in _load("screen_tower_fail42")["strikes"]), "it never strikes him: the rod is 1.4 m behind"


def test_the_ridges_streak_along_the_grass_and_the_bolt_over_his_body():
    probs = _bolts("screen_ridge_fail46")
    assert any("streak along the ground" in p for _, p in probs.get("bolt 3", [])), probs
    assert any(f in (37, 39) and "passes" in p for f, p in probs.get("bolt 2", [])), probs    # sheet frame 10


def test_he_is_the_target_only_when_it_lands_on_him():
    on = {(n, s["name"]): s["to_him_m"] for n in PASSING + FAILING for s in _load(n)["strikes"]}
    struck = [m for (n, _), m in on.items() if n in PASSING]                   # trail 0.09-0.10, beach 0.14-0.19
    beside = [m for (n, _), m in on.items() if n in FAILING]                   # ridge 0.30-0.52, truck 0.53-0.56, tower 1.4
    assert max(struck) <= MO.TARGET_R < min(beside)


def test_bolt_rules_on_their_own():
    down = [(0.5, 1.2 - 0.07 * i) for i in range(10)]                       # from above the frame to y 0.57
    assert MO.bolt_problems(down) == []
    assert any("edge" in p for p in MO.bolt_problems([(0.95, 1.2 - 0.1 * i) for i in range(10)]))
    assert any("leaves the frame" in p for p in MO.bolt_problems(down[:4] + [(1.2, 0.8)] + down[5:]))
    assert any("streak" in p for p in MO.bolt_problems(down, tilt=60))
    flags = [""] * 8 + ["f", ""]
    assert any("in front of" in p for p in MO.bolt_problems(down, flags))
    assert MO.bolt_problems(down, flags, ring=0.01, on_him=True) == [], "a bolt that strikes him may cross him"
    assert any("striking him" in p for p in MO.bolt_problems(down, ring=0.01))
    assert any("not on screen" in p for p in MO.bolt_problems(down, target_seen=False))
    assert MO.bolt_problems([None, (2, 2)]) == ["never in frame"]


# ---------------------------------------------------------------- wired, and it fails the proof before the judge
def test_read_and_bolt_run_in_the_shot_harness_and_stop_a_held_shot():
    src = (STORE / "shots.py").read_text()
    assert "motion.read_check(data, sc.camera, NF, _near" in src
    i = src.index("fails the READ check"); assert "raise SystemExit" in src[i - 120:i]
    assert "_bind" in src[src.index("motion.read_check"):i]
    st = (STORE / "staging.py").read_text()
    far = st[st.index("def far("):]
    assert "MO.bolt_problems(" in far and "near_strikes(data, nf, cutaway)" in far
    loop = (STORE / "proof_loop.py").read_text()
    rx = re.search(r'CHECKS = re\.compile\(r"(.*)"\)', loop).group(1)
    assert re.match(rx, "READ shot 5: x -> FAIL")
    assert "target=None" in (STORE / "storm_kit.py").read_text()
