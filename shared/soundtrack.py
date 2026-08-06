"""THE MUSIC BED — one implementation, for every renderer that scores a film.

THE DEFECT. `data_learning/pro_render.py` — the canonical producer, the thing
that renders every curiosity film — has carried this since it was written:

    def _music_track():
        for p in sorted((REPO / "data_learning" / "music").glob("*.mp3")):
            return p
        return None

and its module docstring says "a music bed sits ducked under the voice".

Neither is true. `scripts/fetch_music.py` writes to `data_learning/music/
<vibe>/*.mp3` — one directory deeper than that glob reaches — so the pro
renderer would find nothing even on a runner that had fetched the library.
`.github/workflows/curiosity-ci.yml`, which is where every pro canary renders,
never called the fetcher at all. **Every film this channel has produced
through the pro path is narration over silence**, and the ducking filter chain
downstream of that `None` has never once run.

The blind judges say BORING in 5 of 5 judged renders and LOW_ENERGY in 4 of 5.

WHAT WAS ALREADY HERE. `data_learning/studio_render.py` — the LEGACY renderer
— has the whole thing and always has: four synthesized vibes, a real
royalty-free library selected by vibe and rotated by slug so two films never
share a track, a synthesized fallback when the library is absent, a ducked mix
and a synthesized SFX kit. CLAUDE.md's rule is explicit about this case: *look
for the duplicate before you write the caller*. So nothing here is new work.
It is `studio_render`'s sound design lifted into `shared/` unchanged, so the
pro path can call the same code instead of a second, broken copy of the idea.

The consolidation test is EQUIVALENCE (`scripts/test_soundtrack.py`, the
pattern `tests/test_captions.py` set): the originals are kept verbatim as
oracles and compared against these over generated input. A cleanup that
quietly re-scores every video is not a cleanup.

THE ONE DECISION THAT IS NEW. `vibe_for()` — the vibe was a per-story constant
typed by hand in a table, and the pro stories have no such table. It is now
derived from the film's own dominant chapter mood, which is a value the
planner already sets per shot and nothing read.

    from shared import soundtrack
    trk = soundtrack.build_music(total, out, soundtrack.vibe_for(moods), slug)
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MUSIC_DIR = REPO / "data_learning" / "music"

# Verbatim from studio_render._VIBES. Synthesized beds — no asset files, no
# network, so a runner with no music library still scores its film.
VIBES = {
    # Gentle pad + slow heartbeat kick — the default teaching vibe.
    "calm": dict(
        drone="0.22*sin(2*PI*98*t)+0.10*sin(2*PI*196*t)",
        kick="0.30*sin(2*PI*55*t)*exp(-5*mod(t,1.0))",
        pad="0.12*sin(2*PI*294*t)*sin(2*PI*0.1*t)"),
    # Sub drone + 90bpm pulse — for the doom-ier money topics.
    "dark": dict(
        drone="0.26*sin(2*PI*55*t)+0.14*sin(2*PI*110*t)",
        kick="0.40*sin(2*PI*58*t)*exp(-7*mod(t,0.667))",
        pad="0.10*sin(2*PI*220*t)*sin(2*PI*0.125*t)"),
    # Low swell, sparse 60bpm pulse — space/nature awe.
    "cinematic": dict(
        drone="0.26*sin(2*PI*49*t)+0.10*sin(2*PI*98*t)",
        kick="0.34*sin(2*PI*55*t)*exp(-5*mod(t,1.0))",
        pad="0.10*sin(2*PI*196*t)*sin(2*PI*0.0625*t)"),
    # Brighter 120bpm tick — tech/behavior energy.
    "pulse": dict(
        drone="0.18*sin(2*PI*82*t)",
        kick="0.38*sin(2*PI*65*t)*exp(-9*mod(t,0.5))",
        pad="0.09*sin(2*PI*330*t)*sin(2*PI*0.2*t)"),
}

# A film's colour world already says what it feels like. `scenes.MOODS` names
# eight of them and the planner sets one per shot; nothing downstream read it.
# This is the only judgement call in the module, and it is deliberately coarse
# — four vibes, mapped by what the chapter is ABOUT, not by a score.
MOOD_VIBE = {
    "cash": "pulse",        # the opening, money arriving
    "tax": "dark",          # the state taking it
    "housing": "calm",
    "transport": "pulse",
    "food": "calm",
    "leaks": "dark",        # invisible drains
    "trap": "dark",         # lifestyle creep
    "payoff": "cinematic",  # what is yours
}


def vibe_for(moods) -> str:
    """One vibe for the whole film, from its dominant chapter mood.

    ONE, not one per chapter. A music bed that changes with the colour grade
    sounds like four films spliced together — the cut is the only place a
    viewer forgives a hard music change, and this pipeline dissolves. The bed
    is the film's floor; the grade, the cut and the camera carry the variation
    above it.
    """
    counts: dict[str, int] = {}
    for m in moods or ():
        v = MOOD_VIBE.get(str(m or "").strip().lower())
        if v:
            counts[v] = counts.get(v, 0) + 1
    if not counts:
        return "calm"
    # Ties break alphabetically so the choice is reproducible across runs —
    # a film that rescores itself differently on a re-render is not a film
    # anyone can compare against its own previous verdict.
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def music_track(vibe: str, slug: str, root: Path | None = None) -> Path | None:
    """A real royalty-free track for this vibe, rotated by slug, or None.

    Verbatim behaviour from `studio_render._music_track`, including the
    fallback to ANY vibe so a partially-fetched library still yields real
    music, and the md5-of-slug rotation so two films do not share a track.
    """
    d = (root or MUSIC_DIR)
    vd = d / str(vibe or "")
    files = sorted(vd.glob("*.mp3")) if vd.is_dir() else []
    if not files:
        files = sorted(d.glob("*/*.mp3")) if d.is_dir() else []
    if not files:
        return None
    h = int(hashlib.md5(str(slug).encode()).hexdigest(), 16)
    return files[h % len(files)]


def synth_bed(total: float, out: Path, vibe: str, run=_run) -> Path:
    """The synthesized bed — no assets, no network. Verbatim from studio."""
    v = VIBES.get(vibe, VIBES["calm"])
    d = max(8.0, total + 1.0)
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"aevalsrc='{v['drone']}':d={d}:s=44100",
         "-f", "lavfi", "-i", f"aevalsrc='{v['kick']}':d={d}:s=44100",
         "-f", "lavfi", "-i", f"aevalsrc='{v['pad']}':d={d}:s=44100",
         "-filter_complex",
         "[0][1][2]amix=inputs=3:duration=longest:weights=1 1.3 0.6,"
         "highpass=f=30,lowpass=f=3500,"
         "acompressor=threshold=0.4:ratio=4[m]",
         "-map", "[m]", "-ac", "2", "-ar", "44100",
         "-c:a", "pcm_s16le", str(out)])
    return out


def build_music(total: float, out: Path, vibe: str, slug: str,
                root: Path | None = None, run=_run) -> Path:
    """Real looped track, loudness-normalized; else the synthesized bed.

    ALWAYS RETURNS A BED. That is the difference from the pro renderer's old
    `_music_track`, which returned None whenever the library was missing and
    left the film silent — which, given the library was fetched into a
    directory that glob never reached, was always.
    """
    trk = music_track(vibe, slug, root=root)
    if trk:
        run(["ffmpeg", "-y", "-loglevel", "error",
             "-stream_loop", "-1", "-i", str(trk), "-t", f"{total + 1:.2f}",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=30,"
             "lowpass=f=14000",
             "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(out)])
        return out
    return synth_bed(total, out, vibe, run=run)


def synth_sfx(work: Path, run=_run) -> dict:
    """Small synthesized one-shot library (no asset files needed).

    Verbatim from `studio_render._synth_sfx`. Available to any renderer; where
    each one-shot LANDS is the caller's editorial decision, not this module's.
    """
    recipes = {
        # Chart sweep-in: short filtered noise whoosh.
        "whoosh": ("anoisesrc=duration=0.22:color=brown:amplitude=0.6",
                   "highpass=f=400,lowpass=f=6000,volume=0.6"),
        # Ring lands on a number — tone keyed to the punch color.
        "pos": ("aevalsrc='0.45*sin(2*PI*880*t)*exp(-8*t)+"
                "0.25*sin(2*PI*1320*t)*exp(-10*t)':d=0.35:s=44100",
                "highpass=f=400,lowpass=f=8000"),
        "warn": ("aevalsrc='0.5*sin(2*PI*420*t)*exp(-7*t)+"
                 "0.3*sin(2*PI*660*t)*exp(-10*t)':d=0.33:s=44100",
                 "highpass=f=200,lowpass=f=5000"),
        "shock": ("aevalsrc='0.8*sin(2*PI*40*t)*exp(-5*t)+"
                  "0.45*sin(2*PI*55*t)*exp(-8*t)':d=0.40:s=44100",
                  "highpass=f=25,lowpass=f=2200"),
        "money": ("aevalsrc='0.4*sin(2*PI*1480*t)*exp(-12*t)+"
                  "0.28*sin(2*PI*2100*t)*exp(-14*t)+"
                  "0.4*sin(2*PI*1480*(t-0.095))*exp(-12*(t-0.095))*gt(t,0.095)':"
                  "d=0.4:s=44100",
                  "highpass=f=600"),
        "neutral": ("aevalsrc='0.6*sin(2*PI*70*t)*exp(-10*t)+"
                    "0.3*sin(2*PI*45*t)*exp(-6*t)':d=0.30:s=44100", None),
        # Closing bubble pops in.
        "pop": ("aevalsrc='0.5*sin(2*PI*620*t)*exp(-9*t)+"
                "0.3*sin(2*PI*930*t)*exp(-12*t)':d=0.30:s=44100",
                "highpass=f=300"),
    }
    sfx: dict = {}
    for name, (src, af) in recipes.items():
        p = Path(work) / f"sfx_{name}.wav"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src]
        if af:
            cmd += ["-af", af]
        run(cmd + [str(p)])
        sfx[name] = p
    return sfx


def has_library(root: Path | None = None) -> bool:
    d = root or MUSIC_DIR
    return bool(d.is_dir() and any(d.glob("*/*.mp3")))


def summary(vibe: str, slug: str, root: Path | None = None) -> str:
    trk = music_track(vibe, slug, root=root)
    return (f"vibe {vibe} · "
            + (f"track {trk.name}" if trk else "synthesized bed"))


__all__ = ["VIBES", "MOOD_VIBE", "vibe_for", "music_track", "synth_bed",
           "build_music", "synth_sfx", "has_library", "summary", "MUSIC_DIR"]
