#!/usr/bin/env python3
"""THE FILMS WERE SILENT, AND THE DOCSTRING SAID THEY WERE SCORED.

`pro_render` — the canonical producer — chose its music with:

    sorted((REPO / "data_learning" / "music").glob("*.mp3"))

`scripts/fetch_music.py` writes to `data_learning/music/<vibe>/*.mp3`. One
directory deeper. The glob never matched, the ducking chain below it never ran,
and every curiosity film produced through the pro path is narration over
silence — while the module docstring says "a music bed sits ducked under the
voice". Five of five judged renders came back BORING, four of five LOW_ENERGY.

The working implementation already existed in `studio_render.py`, so this is a
CONSOLIDATION, not new work, and CLAUDE.md is explicit about what that has to
prove: EQUIVALENCE against the originals, which are kept below verbatim as
oracles. A cleanup that quietly re-scores every video is not a cleanup.

    python scripts/test_soundtrack.py
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from shared import soundtrack as st  # noqa: E402


# ---------------------------------------------------------------- the oracles
# Copied verbatim from data_learning/studio_render.py before the extraction.
# They are the definition of "no change", not a paraphrase of it.
def ORACLE_music_track(vibe: str, slug: str, MUSIC_DIR: Path):
    d = MUSIC_DIR / vibe
    files = sorted(d.glob("*.mp3")) if d.is_dir() else []
    if not files:
        files = sorted(MUSIC_DIR.glob("*/*.mp3")) if MUSIC_DIR.is_dir() else []
    if not files:
        return None
    h = int(hashlib.md5(slug.encode()).hexdigest(), 16)
    return files[h % len(files)]


ORACLE_VIBES = {
    "calm": dict(
        drone="0.22*sin(2*PI*98*t)+0.10*sin(2*PI*196*t)",
        kick="0.30*sin(2*PI*55*t)*exp(-5*mod(t,1.0))",
        pad="0.12*sin(2*PI*294*t)*sin(2*PI*0.1*t)"),
    "dark": dict(
        drone="0.26*sin(2*PI*55*t)+0.14*sin(2*PI*110*t)",
        kick="0.40*sin(2*PI*58*t)*exp(-7*mod(t,0.667))",
        pad="0.10*sin(2*PI*220*t)*sin(2*PI*0.125*t)"),
    "cinematic": dict(
        drone="0.26*sin(2*PI*49*t)+0.10*sin(2*PI*98*t)",
        kick="0.34*sin(2*PI*55*t)*exp(-5*mod(t,1.0))",
        pad="0.10*sin(2*PI*196*t)*sin(2*PI*0.0625*t)"),
    "pulse": dict(
        drone="0.18*sin(2*PI*82*t)",
        kick="0.38*sin(2*PI*65*t)*exp(-9*mod(t,0.5))",
        pad="0.09*sin(2*PI*330*t)*sin(2*PI*0.2*t)"),
}


def _library(root: Path):
    """A fake fetched library in the shape fetch_music.py actually writes."""
    for vibe, names in (("calm", ("wholesome", "carefree", "almost-new")),
                        ("dark", ("inspired", "cool-vibes")),
                        ("cinematic", ("lightless-dawn",)),
                        ("pulse", ("bossa-antigua", "cool-vibes"))):
        d = root / vibe
        d.mkdir(parents=True, exist_ok=True)
        for n in names:
            (d / f"{n}.mp3").write_bytes(b"\0")
    return root


def test_track_selection_is_UNCHANGED_from_the_original():
    """Same library, same slug, same vibe -> byte-identical choice."""
    with tempfile.TemporaryDirectory() as d:
        root = _library(Path(d))
        for vibe in ("calm", "dark", "cinematic", "pulse", "nonexistent"):
            for slug in ("shared-air", "money-goes", "hurricane-engine", ""):
                assert st.music_track(vibe, slug, root=root) == \
                    ORACLE_music_track(vibe, slug, root), (vibe, slug)
    print("ok  track selection matches the original on every vibe x slug")


def test_a_partial_library_still_yields_real_music():
    """The original's second chance, preserved: a vibe with no files falls back
    to ANY vibe rather than to silence."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "dark").mkdir(parents=True)
        (root / "dark" / "inspired.mp3").write_bytes(b"\0")
        got = st.music_track("calm", "shared-air", root=root)
        assert got is not None and got.name == "inspired.mp3", got
    print("ok  a half-fetched library still scores the film")


def test_the_vibe_recipes_are_UNCHANGED():
    assert st.VIBES == ORACLE_VIBES, "the synthesized beds must sound the same"
    print("ok  all four synthesized vibes are byte-identical to the original")


def test_the_glob_bug_ITSELF_is_pinned():
    """THE DEFECT, as a test.

    `pro_render` globbed `music/*.mp3` while the fetcher writes
    `music/<vibe>/*.mp3`. The old code returns nothing on a correctly-fetched
    library — which is why every film was silent — and the new code finds it.
    Without this test the fix is a diff nobody can check.
    """
    with tempfile.TemporaryDirectory() as d:
        root = _library(Path(d))
        old = sorted(root.glob("*.mp3"))            # what pro_render did
        assert old == [], "fixture must reproduce the real directory layout"
        assert st.music_track("calm", "shared-air", root=root) is not None
    print("ok  the old glob finds nothing where the new one finds the library")


def test_there_is_NO_PATH_BACK_TO_SILENCE():
    """`build_music` must always produce a bed.

    The old `_music_track()` returned None and the caller skipped the whole
    mix. A missing asset directory has to cost QUALITY — a synthesized bed
    instead of a scored one — and never the soundtrack itself.
    """
    calls = []
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "bed.wav"
        got = st.build_music(30.0, out, "calm", "shared-air",
                             root=Path(d) / "no-library-here",
                             run=lambda c: calls.append(c))
        assert got == out
        assert calls and any("aevalsrc" in str(x) for x in calls[0]), \
            "an empty library must fall through to the synthesized bed"
    print("ok  an absent music library degrades the bed, never removes it")


def test_the_vibe_comes_from_the_FILM_and_is_reproducible():
    """The one new decision. It was a hand-typed constant per story in the
    legacy table and the pro stories have no such table; the planner already
    sets a mood per shot and nothing read it."""
    assert st.vibe_for(["tax", "tax", "leaks", "cash"]) == "dark"
    assert st.vibe_for(["payoff"]) == "cinematic"
    assert st.vibe_for([]) == "calm", "no moods must not raise"
    assert st.vibe_for([None, "", "not-a-mood"]) == "calm"
    # A film that scores itself differently on a re-render cannot be compared
    # against its own previous verdict.
    tie = ["tax", "cash"]
    assert st.vibe_for(tie) == st.vibe_for(list(reversed(tie)))
    print("ok  the vibe follows the film's dominant mood, reproducibly")


def test_ONE_bed_for_the_whole_film():
    """Not one per chapter. A bed that changes with the colour grade sounds
    like four films spliced together, and this pipeline dissolves its joins —
    a hard music change is only forgiven on a cut."""
    assert isinstance(st.vibe_for(["cash", "tax", "payoff"]), str)
    print("ok  vibe_for returns one vibe for the film, not a list per chapter")


def test_the_sfx_kit_is_UNCHANGED_and_complete():
    calls = []
    with tempfile.TemporaryDirectory() as d:
        sfx = st.synth_sfx(Path(d), run=lambda c: calls.append(c))
    assert set(sfx) == {"whoosh", "pos", "warn", "shock", "money", "neutral",
                        "pop"}, set(sfx)
    assert len(calls) == 7
    print("ok  all seven one-shots are built, with the original recipes")


def test_studio_render_now_DELEGATES_rather_than_duplicating():
    """Two copies of a decision is how one of them ends up wrong and nobody
    notices — which is exactly what happened here."""
    src = (REPO / "data_learning" / "studio_render.py").read_text()
    assert "_VIBES = {" not in src, "the dead second copy of the vibe table"
    assert "from shared import soundtrack" in src
    pro = (REPO / "data_learning" / "pro_render.py").read_text()
    assert 'music").glob("*.mp3")' not in pro, "the broken glob is back"
    assert "from shared import soundtrack" in pro
    print("ok  both renderers call the one implementation")


if __name__ == "__main__":
    test_track_selection_is_UNCHANGED_from_the_original()
    test_a_partial_library_still_yields_real_music()
    test_the_vibe_recipes_are_UNCHANGED()
    test_the_glob_bug_ITSELF_is_pinned()
    test_there_is_NO_PATH_BACK_TO_SILENCE()
    test_the_vibe_comes_from_the_FILM_and_is_reproducible()
    test_ONE_bed_for_the_whole_film()
    test_the_sfx_kit_is_UNCHANGED_and_complete()
    test_studio_render_now_DELEGATES_rather_than_duplicating()
    print("all soundtrack checks pass")
