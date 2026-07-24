#!/usr/bin/env python3
"""Acceptance tests for the story director architecture
(STORY_DIRECTOR_PLAYBOOK §24). Logic tier — no ffmpeg, no network, no
brains: everything external is mocked. The render tier (real ffmpeg) runs
in scripts/smoke_third.py on CI.

    python scripts/test_story_acceptance.py    # exit 0 = pass
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f" — {detail}"
                                                    if detail else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:  # noqa: C901
    sys.modules.setdefault("whisper", types.ModuleType("whisper"))
    from third_capture import story, story_director, clip_edit

    # ---- §2/§11: title-card prohibition (static architecture check) ----
    src = (REPO / "third_capture" / "story.py").read_text()
    check("no _card function in renderer", "_card" not in src)
    check("no CARD_DUR constant", "CARD_DUR" not in src)
    check("no card mp4 generation", "card_" not in src or
          "card_<" not in src and ".mp4" not in
          "".join(line for line in src.splitlines() if "card_" in line))
    check("no blank-canvas video source", "color=c=" not in src)
    check("no fade-in from black on open", "fade=t=in" not in src)

    # ---- §10 EDL validation: director laws are enforced, not advisory --
    durs = {"a": 30.0, "b": 40.0, "c": 25.0}
    base = {
        "is_story": True, "premise": "A challenges B, B answers",
        "central_question": "who wins", "ending_emotion": "surprise",
        "structure": "chronological", "structure_reason": "timeline works",
        "title": "A Challenges B", "hook_overlay": "HE CALLED HIM OUT",
        "target_duration": 45,
        "beats": [
            {"source_id": "a", "start": 2, "end": 10, "role": "setup",
             "purpose": "show the challenge", "transition": "hard_cut",
             "context_overlay": "", "effects": []},
            {"source_id": "b", "start": 5, "end": 20, "role": "payoff",
             "purpose": "show the answer", "transition": "hard_cut",
             "context_overlay": "THEN HE RESPONDED", "effects": []},
        ],
        "ending": {"type": "reaction_hold", "duration": 1.2},
    }
    ok = story_director.validate_edl(dict(base), durs)
    check("valid EDL passes", ok is not None and len(ok["beats"]) == 2)

    e = dict(base)
    e["beats"] = [dict(b, purpose="") for b in base["beats"]]
    check("segment without purpose rejected",
          story_director.validate_edl(e, durs) is None)

    e = dict(base)
    e["beats"] = [dict(base["beats"][0]),
                  dict(base["beats"][1], source_id="zzz")]
    check("unknown source rejected",
          story_director.validate_edl(e, durs) is None)

    e = dict(base, structure="dramatic_supercut")
    check("unapproved structure rejected",
          story_director.validate_edl(e, durs) is None)

    e = dict(base)
    e["beats"] = [dict(base["beats"][0], role="setup"),
                  dict(base["beats"][1], role="reaction")]
    check("no payoff/climax beat rejected",
          story_director.validate_edl(e, durs) is None)

    e = dict(base)
    e["beats"] = [dict(base["beats"][0],
                       context_overlay="THE STORY BEGINS"),
                  dict(base["beats"][1], context_overlay="")]
    v = story_director.validate_edl(e, durs)
    check("banned meta-overlay dropped",
          v is not None and v["beats"][0]["context_overlay"] == "")

    e = dict(base)
    e["beats"][1] = dict(base["beats"][1],
                         effects=[{"type": "subtle_punch", "at": 6},
                                  {"type": "subtle_punch", "at": 8},
                                  {"type": "subtle_punch", "at": 9},
                                  {"type": "replay"}, {"type": "replay"}])
    v = story_director.validate_edl(e, durs)
    n_p = sum(1 for b in v["beats"] for f in b["effects"]
              if f["type"] == "subtle_punch")
    n_r = sum(1 for b in v["beats"] for f in b["effects"]
              if f["type"] == "replay")
    check("effect budget clamped (<=2 punch, <=1 replay)",
          n_p <= 2 and n_r <= 1, f"punch={n_p} replay={n_r}")

    # ---- §11 renderer follows the EDL; arc integrity on edges ----------
    td = Path(tempfile.mkdtemp())
    calls = []
    story._extract_segment = lambda src, out, work, tag, **k: (
        calls.append({"tag": tag, **k}), Path(out).write_bytes(b"x"))[-1]
    story._assemble = lambda parts, out: Path(out).write_bytes(b"cat")
    edl = story_director.validate_edl(dict(base), durs)
    sources = {sid: {"path": str(td / f"{sid}.mp4"), "words": [
        {"w": "hey", "s": 3.0, "e": 3.4}], "duration_s": durs[sid],
        "channel": "s", "source_url": f"http://t/{sid}"}
        for sid in durs}
    led = story.render_story(edl, sources, td / "o.mp4", td / "w")
    check("renderer follows EDL beats", led["n_beats"] == 2)
    check("hook overlays FIRST beat only",
          bool(calls[0]["hook"]) and not calls[1]["hook"])
    check("context overlay burned on its segment",
          calls[1]["context_overlay"] == "THEN HE RESPONDED")
    check("no narration ever", led["used_narration"] is False)
    check("measurement fields present",
          all(k in led for k in ("story_structure", "n_beats",
                                 "context_overlay_count", "replay_count")))
    missing = {k: v for k, v in sources.items() if k != "a"}
    try:
        story.render_story(edl, missing, td / "o2.mp4", td / "w2")
        check("missing OPENING source aborts", False)
    except RuntimeError as ex:
        check("missing OPENING source aborts", "opening" in str(ex))
    missing = {k: v for k, v in sources.items() if k != "b"}
    try:
        story.render_story(edl, missing, td / "o3.mp4", td / "w3")
        check("missing PAYOFF source aborts", False)
    except RuntimeError as ex:
        check("missing PAYOFF source aborts", "payoff" in str(ex))

    # ---- §6 context recovery: no coordinates -> None, never invented ---
    check("VOD expansion refuses without coordinates",
          clip_edit.maybe_vod_window({"url": "x"}, td) is None)

    # ---- §18/§19 critic + single revision ------------------------------
    # patch the names story_director actually calls (bound at its import)
    story_director._call_claude = lambda u, system=None: {
        "publish": False, "story_score": 55,
        "problems": [{"type": "weak_payoff", "at": 30.1,
                      "fix": "keep 1.4s more reaction"}]}
    r = story_director.review_rough_cut(edl, "words", None, 40.0)
    check("critic verdict parsed",
          r["publish"] is False and r["problems"][0]["at"] == 30.1)
    story_director._call_claude = lambda u, system=None: (
        _ for _ in ()).throw(RuntimeError("down"))
    story_director._call_groq = lambda u, system=None: None
    r = story_director.review_rough_cut(edl, "words", None, 40.0)
    check("critic fails OPEN when brains unreachable",
          r["publish"] is True and r["story_score"] == -1)
    check("reviser refuses without problems",
          story_director.revise_edl(edl, [], []) is None)

    print()
    if FAILS:
        print(f"ACCEPTANCE FAILED ({len(FAILS)}): {FAILS}")
        return 1
    print("ACCEPTANCE PASSED — story director architecture holds its laws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
