"""DATA IS ALIVE BETWEEN HIS MOVES (caaleb, 2026-11-14, of the saffron short: "Data facial expressions and the like,
making him feel like a real character in a real world instead of just like a series of animations").

Measured on that cut: one or two hand-placed blinks a shot and pupils that only moved when a scripted look moved
them. character.Data._live runs on EVERY shot in finish(): his own blink cadence, a blink with each big head turn,
and small held saccades of the pupils layered on whatever the shot keyed."""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "tools" / "data3d" / "character.py").read_text()


def test_finish_runs_the_life_pass_on_every_shot():
    cls = next(n for n in ast.parse(SRC).body if isinstance(n, ast.ClassDef) and n.name == "Data")
    fin = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "finish")
    assert "self._live(n)" in ast.unparse(fin)
    assert 'os.environ.get("DATA_LIFE", "1")' in SRC


def _plan(turns=(), blinks=(), n=30 * 12):
    pytest.importorskip("bpy")
    sys.path.insert(0, str(ROOT / "tools" / "data3d"))
    import character
    D = character.Data
    fake = type("F", (), {k: getattr(D, k) for k in ("BLINK_GAP", "BLINK_TURN", "SACCADE", "SACCADE_GAP")})()
    fake._turns = list(turns); fake._blinks = list(blinks)
    return D.life_plan(fake, n)


def test_he_blinks_like_a_person_over_a_whole_shot():
    blinks, darts = _plan()
    gaps = [b - a for a, b in zip(blinks, blinks[1:])]
    assert 12 / 4.8 - 1 <= len(blinks) <= 12 / 2.2 + 1
    assert min(gaps) >= 0.6
    assert len(darts) >= 12 / 1.4


def test_a_big_turn_brings_a_blink_and_a_small_one_does_not():
    big, _ = _plan(turns=[(1.0, 0.3, 0.0, 0.0), (5.0, 0.3, 30.0, 0.0)], n=30 * 6)
    small, _ = _plan(turns=[(1.0, 0.3, 0.0, 0.0), (5.0, 0.3, 5.0, 0.0)], n=30 * 6)
    assert any(abs(b - (5.0 - 0.18)) < 0.01 for b in big)
    assert not any(abs(b - (5.0 - 0.18)) < 0.01 for b in small)


def test_his_own_blinks_keep_clear_of_the_shots_blinks():
    blinks, _ = _plan(blinks=[2.0, 6.0])
    assert all(abs(b - s) >= 0.6 for b in blinks for s in (2.0, 6.0))
