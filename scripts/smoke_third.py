#!/usr/bin/env python3
"""Smoke suite for the clip pipeline — catches "worked on my one clip" bugs.

Every failure we hit in production was an unusual INPUT breaking an
assumption, found only after it wasted a slot: an apostrophe hook crashing
the filtergraph, a near-silent clip collapsing to a 2s cut, a portrait
source. This runs the REAL edit() + preflight + QA on synthetic fixtures
that deliberately carry those tricky inputs, so a regression goes red here
(seconds, no network, no upload) instead of on the channel.

Run locally before pushing; runs in CI on every push to the third pipeline.
Exit 0 = all green, 1 = a case failed.

    python scripts/smoke_third.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from third_capture import clip_edit, clip_qa, story  # noqa: E402


def _fixture(path: Path, dur: int = 12, w: int = 1280, h: int = 720) -> None:
    """A moving-pattern + tone clip: animated (no freeze), audible (no
    silence), 16:9 — a stand-in for a real streamer clip."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"testsrc2=s={w}x{h}:r=30:d={dur}",
         "-f", "lavfi", "-i", f"sine=frequency=300:duration={dur}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(path)], check=True, timeout=120)


def _dur(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], text=True, timeout=30)
    return float(out.strip() or 0)


def _stream_dur(path: Path, kind: str) -> float:
    """Duration of the first video ('v') or audio ('a') stream."""
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-select_streams", kind,
             "-show_entries", "stream=duration", "-of", "csv=p=0",
             str(path)], text=True, timeout=30)
        return float((out.strip().splitlines() or ["0"])[0] or 0)
    except Exception:  # noqa: BLE001
        return 0.0


CASES = [
    # (name, words, hook, series) — words are cut-relative {w,s,e}
    ("apostrophe_hook",
     [{"w": "CAN'T", "s": 1.0, "e": 1.4}, {"w": "believe", "s": 1.5, "e": 2.0},
      {"w": "it", "s": 2.1, "e": 2.3}, {"w": "happened", "s": 2.4, "e": 3.0},
      {"w": "bro", "s": 3.1, "e": 3.4}, {"w": "no", "s": 5.0, "e": 5.3},
      {"w": "way", "s": 5.4, "e": 5.8}],
     "HE CAN'T BELIEVE IT", "fail"),
    # near-silent reaction: 1 word — the cut must NOT collapse to ~2s
    ("sparse_speech",
     [{"w": "yo", "s": 1.0, "e": 1.3}],
     "", "chaos"),
    # empty transcript (screaming/crowd moment)
    ("no_speech", [], "WAIT FOR IT", "rage"),
]


def run_case(name, words, hook, series, work: Path,
             edit_mode: bool = False) -> list[str]:
    fails = []
    src = work / f"{name}_src.mp4"
    out = work / f"{name}_out.mp4"
    _fixture(src)

    if clip_qa.preflight(src):
        return [f"{name}: a valid fixture failed preflight"]

    try:
        led = clip_edit.edit(src, out, credit="twitch.tv/test", hook=hook,
                             words=list(words), auto=True, series=series,
                             edit_mode=edit_mode)
    except Exception as e:  # noqa: BLE001
        return [f"{name}: edit() RAISED {type(e).__name__}: {e}"]

    if not out.exists():
        return [f"{name}: no output file produced"]
    d = _dur(out)
    if not (4.0 <= d <= 62.0):
        fails.append(f"{name}: output duration {d:.1f}s out of bounds")
    # the sparse/no-speech cases must keep a real clip, not a 2s sliver
    if name in ("sparse_speech", "no_speech") and d < 8.0:
        fails.append(f"{name}: cut collapsed to {d:.1f}s (sparse guard)")
    qa = clip_qa.review(out, led, work)
    mech = [p for p in qa["problems"] if not p.startswith("vision:")]
    if mech:
        fails.append(f"{name}: QA mechanical problems {mech}")
    print(f"  [{name}] dur={d:.1f}s render_level={led.get('render_level')} "
          f"qa={qa['verdict']} mech_ok={not mech}", flush=True)
    return fails


def run_story_case(work: Path) -> list[str]:
    """The story DIRECTOR render path on two synthetic sources: a real
    validated EDL through the real dedicated renderer (extract + reframe +
    captions + overlays + loudnorm + concat). Also enforces the §2 card
    prohibition at the artifact level: no card files may exist."""
    from third_capture import story_director
    fails: list[str] = []
    b1, b2 = work / "story_b1.mp4", work / "story_b2.mp4"
    _fixture(b1)
    _fixture(b2)
    edl = story_director.validate_edl({
        "is_story": True,
        "premise": "The beef starts, then they make up.",
        "central_question": "Do they squash it?",
        "ending_emotion": "relief",
        "structure": "chronological",
        "structure_reason": "the natural timeline compels",
        "title": "The Beef Ends In A Hug",
        "hook_overlay": "IT ENDED IN A HUG",
        "target_duration": 20,
        "beats": [
            {"source_id": "http://x/beef", "start": 1.0, "end": 8.0,
             "role": "setup", "purpose": "show the beef start",
             "transition": "hard_cut", "context_overlay": "", "effects": []},
            {"source_id": "http://x/makeup", "start": 2.0, "end": 10.0,
             "role": "payoff", "purpose": "show the makeup",
             "transition": "j_cut",
             "context_overlay": "SIX DAYS LATER",
             "effects": [{"type": "subtle_punch", "at": 5.0}]},
        ],
        "ending": {"type": "reaction_hold", "duration": 1.0},
    }, {"http://x/beef": 12.0, "http://x/makeup": 12.0})
    if not edl:
        return ["story: smoke EDL failed validation"]
    sources = {
        # words include speech INSIDE the J/L bridge windows so the speech
        # gate (#11) is satisfied: beef's l_cut post-roll [8.0,8.4] and
        # makeup's j_cut pre-roll [1.6,2.0] both carry a real word.
        "http://x/beef": {"path": str(b1), "duration_s": 12.0,
                          "channel": "stableronaldo",
                          "source_url": "http://x/beef",
                          "words": [{"w": "SQUARE", "s": 2.0, "e": 2.4},
                                    {"w": "UP", "s": 2.5, "e": 2.8},
                                    {"w": "listen", "s": 7.9, "e": 8.4}]},
        "http://x/makeup": {"path": str(b2), "duration_s": 12.0,
                            "channel": "cudi",
                            "source_url": "http://x/makeup",
                            "words": [{"w": "okay", "s": 1.6, "e": 2.0},
                                      {"w": "my", "s": 3.0, "e": 3.2},
                                      {"w": "bad", "s": 3.3, "e": 3.6}]},
    }
    out = work / "story_out.mp4"
    story_work = work / "story_work"
    try:
        led = story.render_story(edl, sources, out, story_work)
        if not out.exists():
            return ["story: no output produced"]
        d = _dur(out)
        if not (8.0 <= d <= 60.0):
            fails.append(f"story: duration {d:.1f}s out of bounds")
        if led.get("n_beats") != 2:
            fails.append(f"story: expected 2 beats, got {led.get('n_beats')}")
        # §2 card prohibition, artifact level
        cards = list(story_work.glob("card_*.mp4"))
        if cards:
            fails.append(f"story: CARD FILES GENERATED: {cards}")
        # reviewer #4: the j_cut path must keep audio and video aligned
        # (the old acrossfade drifted 0.3s per join). Assert real A/V
        # durations match after the genuine J-cut render.
        vdur = _stream_dur(out, "v")
        adur = _stream_dur(out, "a")
        if vdur and adur and abs(vdur - adur) > 0.35:
            fails.append(f"story: A/V drift {abs(vdur - adur):.2f}s "
                         f"(v={vdur:.2f} a={adur:.2f}) after j_cut")
        print(f"  [story] dur={d:.1f}s beats={led.get('n_beats')} "
              f"structure={led.get('story_structure')} "
              f"overlays={led.get('context_overlay_count')} cards=0 "
              f"av_drift={abs((vdur or 0) - (adur or 0)):.2f}s",
              flush=True)
    except Exception as e:  # noqa: BLE001
        fails.append(f"story: render_story RAISED {type(e).__name__}: {e}")

    # reviewer #8: prove the L-cut path renders end to end, builds a REAL
    # audio bridge from the previous source's post-roll (not apad silence),
    # and stays A/V aligned. beat1 ends at 8.0 in a 12s source → the
    # [8.0, 8.4] post-roll genuinely exists, so a bridge file must appear.
    l_edl = story_director.validate_edl({
        "is_story": True, "premise": "The beef starts, then they make up.",
        "central_question": "Do they squash it?", "ending_emotion": "relief",
        "structure": "chronological",
        "structure_reason": "the natural timeline compels",
        "title": "The Beef Ends In A Hug", "hook_overlay": "IT ENDED IN A HUG",
        "target_duration": 20,
        "beats": [
            {"source_id": "http://x/beef", "start": 1.0, "end": 8.0,
             "role": "setup", "purpose": "show the beef start",
             "transition": "hard_cut", "context_overlay": "", "effects": []},
            {"source_id": "http://x/makeup", "start": 2.0, "end": 10.0,
             "role": "payoff", "purpose": "show the makeup",
             "transition": "l_cut", "context_overlay": "SIX DAYS LATER",
             "effects": []},
        ],
        "ending": {"type": "reaction_hold", "duration": 1.0},
    }, {"http://x/beef": 12.0, "http://x/makeup": 12.0})
    l_out = work / "story_lcut.mp4"
    l_work = work / "story_lcut_work"
    try:
        led_l = story.render_story(l_edl, sources, l_out, l_work)
        bridges = list(l_work.glob("bridge_l_*.m4a"))
        if not bridges:
            fails.append("story: l_cut built NO real audio bridge "
                         "(silence regression)")
        elif not all(b.stat().st_size > 200 for b in bridges):
            fails.append("story: l_cut bridge is empty/near-empty")
        vdur = _stream_dur(l_out, "v")
        adur = _stream_dur(l_out, "a")
        if vdur and adur and abs(vdur - adur) > 0.35:
            fails.append(f"story: A/V drift {abs(vdur - adur):.2f}s after "
                         "l_cut")
        print(f"  [story-lcut] dur={_dur(l_out):.1f}s "
              f"beats={led_l.get('n_beats')} bridges={len(bridges)} "
              f"av_drift={abs((vdur or 0) - (adur or 0)):.2f}s", flush=True)
    except Exception as e:  # noqa: BLE001
        fails.append(f"story: l_cut render RAISED {type(e).__name__}: {e}")
    return fails


def main() -> int:
    print("smoke_third: pipeline self-test on synthetic tricky inputs")
    all_fails: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        # preflight negatives
        (work / "corrupt.mp4").write_bytes(b"not a video")
        if not clip_qa.preflight(work / "corrupt.mp4"):
            all_fails.append("preflight: corrupt file passed (should fail)")
        _fixture(work / "tiny.mp4", dur=3, w=320, h=240)
        if not clip_qa.preflight(work / "tiny.mp4"):
            all_fails.append("preflight: 3s/320p passed (should fail)")
        for name, words, hook, series in CASES:
            all_fails += run_case(name, words, hook, series, work)
        # A/B EDIT ARM: the montage render path must also survive the tricky
        # inputs (it's what the 3 daily edit-arm slots use). Re-run the base
        # case with edit_mode=True and hold it to the same mechanical bar.
        base = CASES[0]
        all_fails += run_case("edit_" + base[0], base[1], base[2], base[3],
                              work, edit_mode=True)
        # STORY COMPILATION: the multi-clip stitch must survive the tricky
        # inputs too. Mock only the network download (hand back local
        # fixtures); the real per-beat render + chapter cards + normalize +
        # concat run, and the stitched output is held to the same bounds.
        all_fails += run_story_case(work)
    if all_fails:
        print("\nSMOKE FAILED:")
        for f in all_fails:
            print("  -", f)
        return 1
    print("\nSMOKE PASSED — pipeline healthy on tricky inputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
