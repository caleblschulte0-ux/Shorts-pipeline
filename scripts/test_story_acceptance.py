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
    orig_assemble = story._assemble

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
    e["beats"] = [dict(base["beats"][0]),
                  dict(base["beats"][1],
                       effects=[{"type": "subtle_punch", "at": 6},
                                  {"type": "subtle_punch", "at": 8},
                                  {"type": "subtle_punch", "at": 9},
                                {"type": "replay"}, {"type": "replay"}])]
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
    story._assemble = lambda parts, out, joins=None: Path(out).write_bytes(b"cat")
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

    # ---- Phase Two: transitions, framing, replay, narration ------------
    e = dict(base)
    e["beats"] = [dict(base["beats"][0], transition="j_cut",
                       framing="tight"),
                  dict(base["beats"][1], transition="spin_wipe",
                       framing="dutch_angle",
                       effects=[{"type": "replay", "at": 12.0}])]
    v = story_director.validate_edl(e, durs)
    check("j_cut accepted, garbage transition -> hard_cut",
          v["beats"][0]["transition"] == "j_cut"
          and v["beats"][1]["transition"] == "hard_cut")
    check("tight framing accepted, garbage framing -> wide",
          v["beats"][0]["framing"] == "tight"
          and v["beats"][1]["framing"] == "wide")
    check("replay carries its timestamp",
          v["beats"][1]["effects"][0].get("at") == 12.0)

    e = dict(base, narration={"text": "Two days later he responded",
                              "after_beat": 1,
                              "essential_because": "time jump unclear"})
    v = story_director.validate_edl(e, durs)
    check("justified factual narration kept",
          v["narration"] and v["narration"]["after_beat"] == 1)
    e = dict(base, narration={"text": "He was furious and planning revenge",
                              "after_beat": 1,
                              "essential_because": "drama"})
    v = story_director.validate_edl(e, durs)
    check("motive-claiming narration rejected", v["narration"] is None)
    e = dict(base, narration={"text": "Two days later", "after_beat": 1,
                              "essential_because": ""})
    v = story_director.validate_edl(e, durs)
    check("unjustified narration rejected", v["narration"] is None)

    # renderer: j_cut join routes to the blended-audio assemble
    ran = {}
    story._run = lambda cmd: ran.update(cmd=cmd)
    orig_assemble([Path("/tmp/a.mp4"), Path("/tmp/b.mp4")],
                  Path("/tmp/o.mp4"), ["j_cut"])
    check("j_cut join uses audio acrossfade assemble",
          any("acrossfade" in str(c) for c in ran["cmd"]))
    ran.clear()
    orig_assemble([Path("/tmp/a.mp4"), Path("/tmp/b.mp4")],
                  Path("/tmp/o.mp4"), ["hard_cut"])
    check("hard-cut-only joins stay lossless concat",
          any("concat" in str(c) for c in ran["cmd"])
          and not any("acrossfade" in str(c) for c in ran["cmd"]))

    # renderer follows framing + appends the budgeted replay
    calls.clear()
    e = dict(base)
    e["beats"] = [dict(base["beats"][0], framing="tight"),
                  dict(base["beats"][1],
                       effects=[{"type": "replay", "at": 8.0}])]
    edl2 = story_director.validate_edl(e, durs)
    story._extract_segment = lambda src, out, work, tag, **k: (
        calls.append(k), Path(out).write_bytes(b"x"))[-1]
    replays = []
    story._render_replay = lambda src, out, **k: (
        replays.append(k), Path(out).write_bytes(b"r"))[-1]
    story._assemble = lambda parts, out, joins=None: Path(out).write_bytes(b"c")
    led2 = story.render_story(edl2, sources, td / "p2.mp4", td / "wp2")
    check("framing reaches the renderer",
          calls[0]["framing"] == "tight" and calls[1]["framing"] == "wide")
    check("budgeted replay rendered exactly once",
          len(replays) == 1 and led2["replay_count"] == 1)

    # narration is best-effort: TTS failure ships the story clean
    story._maybe_narration = lambda text, work: None
    e = dict(base, narration={"text": "Two days later he responded",
                              "after_beat": 0,
                              "essential_because": "time jump"})
    edl3 = story_director.validate_edl(e, durs)
    led3 = story.render_story(edl3, sources, td / "p3.mp4", td / "wp3")
    check("failed TTS ships story without narration",
          led3["used_narration"] is False)

    # ---- Phase Three: guidance is evidence-gated -----------------------
    import json as _json
    sys.path.insert(0, str(REPO / "scripts"))
    import run_third as rt
    rt.ANALYTICS_LATEST = td / "latest.json"
    check("no analytics -> no guidance", rt._story_guidance() == "")
    rt.ANALYTICS_LATEST.write_text(_json.dumps({"summary": {
        "story_structures": {"enough_data": False, "structures": {
            "cold_open": {"n_mature": 3, "median_vph": 1.0}}}}}))
    check("thin data -> no guidance (25-mature gate)",
          rt._story_guidance() == "")
    rt.ANALYTICS_LATEST.write_text(_json.dumps({"summary": {
        "story_structures": {"enough_data": True, "structures": {
            "cold_open": {"n_mature": 14, "median_vph": 2.0,
                          "avg_retention": 71.0},
            "chronological": {"n_mature": 12, "median_vph": 1.1,
                              "avg_retention": 64.0}}}}}))
    g = rt._story_guidance()
    check("mature data -> structure guidance emitted",
          "cold_open" in g and "chronological" in g)

    print()
    if FAILS:
        print(f"ACCEPTANCE FAILED ({len(FAILS)}): {FAILS}")
        return 1
    print("ACCEPTANCE PASSED — story director architecture holds its laws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
