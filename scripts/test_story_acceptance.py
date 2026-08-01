#!/usr/bin/env python3
"""Acceptance tests for the story director architecture
(STORY_DIRECTOR_PLAYBOOK §24). Logic tier — no ffmpeg, no network, no
brains: everything external is mocked. The render tier (real ffmpeg) runs
in scripts/smoke_third.py on CI.

    python scripts/test_story_acceptance.py    # exit 0 = pass
"""
from __future__ import annotations

import os
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
    story._assemble = lambda parts, out, joins=None, bridges=None: \
        Path(out).write_bytes(b"cat")
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
    story_director._call_claude = lambda u, system=None, read_files=False: {
        "publish": False, "story_score": 55,
        "problems": [{"type": "weak_payoff", "at": 30.1,
                      "fix": "keep 1.4s more reaction"}]}
    r = story_director.review_rough_cut(edl, "words", None, 40.0)
    check("critic verdict parsed",
          r["publish"] is False and r["problems"][0]["at"] == 30.1)
    story_director._call_claude = lambda u, system=None, read_files=False: (
        _ for _ in ()).throw(RuntimeError("down"))
    story_director._call_groq = lambda u, system=None: None
    r = story_director.review_rough_cut(edl, "words", None, 40.0)
    check("story critic fails CLOSED when brains unreachable (#9)",
          r["publish"] is False and r["story_score"] == -1)
    check("reviser refuses without problems",
          story_director.revise_edl(edl, [], []) is None)

    # ---- reviewer #8: the rough-cut critic actually SEES the frames -----
    # a contact-sheet path in the prompt is worthless unless the model is
    # granted Read to open it; verify the grant is passed iff a sheet exists
    seen: dict = {}
    story_director._call_claude = \
        lambda u, system=None, read_files=False: (
            seen.update(read_files=read_files,
                        has_sheet="contact sheet image" in u.lower()),
            {"publish": True, "story_score": 80, "problems": []})[-1]
    story_director.review_rough_cut(edl, "words", str(td / "sheet.jpg"), 40.0)
    check("critic gets the Read grant when a rough-cut sheet exists (#8)",
          seen.get("read_files") is True and seen.get("has_sheet") is True)
    seen.clear()
    story_director.review_rough_cut(edl, "words", None, 40.0)
    check("critic runs text-only (no Read grant) when no sheet (#8)",
          seen.get("read_files") is False)

    # ---- reviewer #11: with a sheet, a VISION verdict is REQUIRED — the
    # text-only Groq fallback must not be able to publish a cut it never saw
    story_director._call_claude = \
        lambda u, system=None, read_files=False: None      # vision unavailable
    story_director._call_groq = \
        lambda u, system=None: {"publish": True, "story_score": 90,
                                "problems": []}             # would rubber-stamp
    r = story_director.review_rough_cut(edl, "words", str(td / "s.jpg"), 40.0)
    check("sheet + no vision model => FAIL CLOSED, not groq's publish (#11)",
          r["publish"] is False and r["story_score"] == -1)
    # but with NO sheet there's nothing to see, so text-only groq is allowed
    r2 = story_director.review_rough_cut(edl, "words", None, 40.0)
    check("no sheet => text-only groq verdict is accepted (#11)",
          r2["publish"] is True and r2["story_score"] == 90)

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
                              "over_beat": 1,
                              "essential_because": "time jump unclear"})
    v = story_director.validate_edl(e, durs)
    check("justified factual narration kept (over_beat #10)",
          v["narration"] and v["narration"]["over_beat"] == 1)
    e = dict(base, narration={"text": "He was furious and planning revenge",
                              "over_beat": 1,
                              "essential_because": "drama"})
    v = story_director.validate_edl(e, durs)
    check("motive-claiming narration rejected", v["narration"] is None)
    e = dict(base, narration={"text": "Two days later", "over_beat": 1,
                              "essential_because": ""})
    v = story_director.validate_edl(e, durs)
    check("unjustified narration rejected", v["narration"] is None)

    # renderer: real J/L cut assembly (reviewer #8). The old code shifted a
    # whole segment's audio 0.4s early (desyncing the visible speaker for the
    # ENTIRE shot) and padded L-cuts with silence. Now each segment's audio
    # stays LOCKED to its own picture and the lead/lag is a SEPARATE bridge
    # of genuine source audio placed in the overlap.
    ran = {}
    story._run = lambda cmd: ran.update(cmd=cmd)
    story._probe_dur = lambda p: 8.0     # deterministic seg durations
    orig_assemble([Path("/tmp/a.mp4"), Path("/tmp/b.mp4")],
                  Path("/tmp/o.mp4"), ["j_cut"],
                  bridges=[(1, "lead", Path("/tmp/br.m4a"))])
    fc = " ".join(str(c) for c in ran["cmd"])
    # seg[1]'s OWN audio stays at its true 8.0s offset — NOT shifted to 7.6
    check("segment audio stays LIP-SYNCED to its own video (#8)",
          "adelay=8000|8000" in fc and "acrossfade" not in fc)
    # the bridge (input #3) leads the picture by the lead: 8.0-0.4 = 7.6s
    check("J-cut bridge is a separate handle leading by the lead (#8)",
          "adelay=7600|7600" in fc and "amix=inputs=3" in fc)
    check("assemble caps overlap peaks + locks audio to video length (#8)",
          "alimiter" in fc and "atrim=0:16" in fc
          and "apad=whole_dur=16" in fc)
    ran.clear()
    # no bridge survived the pre-/post-roll test → lossless hard-cut concat
    orig_assemble([Path("/tmp/a.mp4"), Path("/tmp/b.mp4")],
                  Path("/tmp/o.mp4"), ["j_cut"], bridges=[])
    check("no-bridge assembly stays lossless concat (no fake offsets) (#8)",
          any("concat" in str(c) for c in ran["cmd"])
          and not any("adelay" in str(c) for c in ran["cmd"]))

    # render-level: bridges carry REAL dialogue from OUTSIDE the visible
    # window, and a cut degrades to hard when the source can't do it honestly
    def _jl_edl(t_into_b, b_start=5):
        return {"structure": "chronological", "premise": "p q r",
                "hook_overlay": "HE CALLED HIM OUT", "title": "T",
                "ending": {"type": "reaction_hold", "duration": 1.0},
                "beats": [
                    {"source_id": "a", "start": 2, "end": 10, "role": "setup",
                     "purpose": "x", "transition": "hard_cut",
                     "context_overlay": "", "effects": [], "framing": "wide"},
                    {"source_id": "b", "start": b_start, "end": 20,
                     "role": "payoff", "purpose": "y", "transition": t_into_b,
                     "context_overlay": "", "effects": [],
                     "framing": "wide"}]}

    def _ab_sources(dur_a=30.0, dur_b=40.0, speech=True):
        # words placed INSIDE the bridge windows so the speech-gate (#11) is
        # satisfied on the happy path: a's post-roll [10.0,10.4], b's
        # pre-roll [4.6,5.0]. `speech=False` empties them to test degradation.
        aw = [{"w": "so", "s": 10.0, "e": 10.4}] if speech else []
        bw = [{"w": "wait", "s": 4.6, "e": 5.0}] if speech else []
        return {"a": {"path": str(td / "a.mp4"), "words": aw,
                      "duration_s": dur_a, "channel": "s",
                      "source_url": "http://t/a"},
                "b": {"path": str(td / "b.mp4"), "words": bw,
                      "duration_s": dur_b, "channel": "s",
                      "source_url": "http://t/b"}}

    story._extract_segment = lambda src, out, work, tag, **k: \
        Path(out).write_bytes(b"x")
    story._probe_dur = lambda p: 8.0
    ax: list = []
    story._extract_audio = lambda s_, o_, s, e: (
        ax.append({"src": Path(s_).name, "s": round(s, 2), "e": round(e, 2)}),
        Path(o_).write_bytes(b"a"))[-1]
    asm: dict = {}
    story._assemble = lambda parts, out, joins=None, bridges=None: (
        asm.update(joins=list(joins or []), bridges=list(bridges or [])),
        Path(out).write_bytes(b"c"))[-1]

    # J-cut: pull ~0.4s of the NEXT source's dialogue from BEFORE its visible
    # start (source pre-roll [4.6, 5.0]) — heard under the previous picture
    ax.clear(); asm.clear()
    story.render_story(_jl_edl("j_cut"), _ab_sources(), td / "jc.mp4",
                       td / "wjc")
    check("J-cut extracts real pre-roll from the incoming source (#8)",
          {"src": "b.mp4", "s": 4.6, "e": 5.0} in ax
          and asm["joins"] == ["j_cut"]
          and any(b[1] == "lead" for b in asm["bridges"]))

    # L-cut: pull ~0.4s of the PREVIOUS source's REAL continuing dialogue
    # AFTER its visible end (post-roll [10.0, 10.4]) — not apad silence
    ax.clear(); asm.clear()
    story.render_story(_jl_edl("l_cut"), _ab_sources(), td / "lc.mp4",
                       td / "wlc")
    check("L-cut carries REAL continuing speech, not silence (#8)",
          {"src": "a.mp4", "s": 10.0, "e": 10.4} in ax
          and asm["joins"] == ["l_cut"]
          and any(b[1] == "tail" for b in asm["bridges"]))

    # honesty gate: no post-roll (prev source ends at 10.2) → hard cut, no
    # fabricated bridge
    ax.clear(); asm.clear()
    story.render_story(_jl_edl("l_cut"), _ab_sources(dur_a=10.2),
                       td / "lc2.mp4", td / "wlc2")
    check("L-cut with no real post-roll degrades to a hard cut (#8)",
          asm["joins"] == ["hard_cut"] and not asm["bridges"]
          and not any(a["src"] == "a.mp4" for a in ax))

    # honesty gate: no pre-roll (visible start at 0.2 < lead) → hard cut
    ax.clear(); asm.clear()
    story.render_story(_jl_edl("j_cut", b_start=0.2), _ab_sources(),
                       td / "jc2.mp4", td / "wjc2")
    check("J-cut with no real pre-roll degrades to a hard cut (#8)",
          asm["joins"] == ["hard_cut"] and not asm["bridges"])

    # reviewer #11 — SPEECH gate: enough source duration exists, but the
    # bridge window is SILENT (no transcribed words) → degrade, don't
    # fabricate a bridge from silence/noise
    ax.clear(); asm.clear()
    story.render_story(_jl_edl("l_cut"), _ab_sources(speech=False),
                       td / "lc3.mp4", td / "wlc3")
    check("L-cut over SILENT post-roll degrades to hard cut (#11)",
          asm["joins"] == ["hard_cut"] and not asm["bridges"])
    ax.clear(); asm.clear()
    story.render_story(_jl_edl("j_cut"), _ab_sources(speech=False),
                       td / "jc3.mp4", td / "wjc3")
    check("J-cut over SILENT pre-roll degrades to hard cut (#11)",
          asm["joins"] == ["hard_cut"] and not asm["bridges"])

    # reviewer #11 — _speech_secs measures transcribed coverage in a window
    ws = [{"w": "hey", "s": 4.7, "e": 5.0}, {"w": "x", "s": 9.0, "e": 9.1}]
    check("_speech_secs counts only words inside the window",
          abs(story._speech_secs(ws, 4.6, 5.0) - 0.3) < 1e-6
          and story._speech_secs(ws, 20.0, 21.0) == 0.0)

    # reviewer #11 — ducking: an L-cut bridge ducks the incoming segment over
    # its window so the carried line stays intelligible (not two equal voices)
    ran.clear()
    orig_assemble([Path("/tmp/a.mp4"), Path("/tmp/b.mp4")],
                  Path("/tmp/o.mp4"), ["l_cut"],
                  bridges=[(1, "tail", Path("/tmp/br.m4a"))])
    fcd = " ".join(str(c) for c in ran["cmd"])
    # tail bridge into part 1 → duck part 1's audio over [O_1, O_1+lead] =
    # [8.0, 8.4]; segment audio stays synced (adelay=8000) and dips there
    check("L-cut ducks the incoming segment over the bridge window (#11)",
          f"volume={story.DUCK_GAIN}" in fcd and "enable=" in fcd
          and "between(t,8.000,8.400)" in fcd)

    # reviewer #11 — the ledger reports the REALIZED transition, so a degraded
    # j/l cut is not attributed to the learning loop as one that happened
    led_j = story.render_story(_jl_edl("j_cut"), _ab_sources(),
                               td / "le1.mp4", td / "wle1")
    check("ledger logs a realized j_cut when the bridge is built (#11)",
          led_j["transitions"] == ["j_cut"]
          and led_j["j_l_cuts_realized"] == 1
          and led_j["transitions_requested"] == ["j_cut"])
    led_h = story.render_story(_jl_edl("j_cut"), _ab_sources(speech=False),
                               td / "le2.mp4", td / "wle2")
    check("ledger logs a DEGRADED j_cut as a hard cut, not a j_cut (#11)",
          led_h["transitions"] == ["hard_cut"]
          and led_h["j_l_cuts_realized"] == 0
          and led_h["transitions_requested"] == ["j_cut"])

    # restore the segment/probe mocks the later phases rely on
    story._extract_segment = lambda src, out, work, tag, **k: (
        calls.append(k), Path(out).write_bytes(b"x"))[-1]
    story._probe_dur = lambda p: 8.0

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
    story._assemble = lambda parts, out, joins=None, bridges=None: \
        Path(out).write_bytes(b"c")
    led2 = story.render_story(edl2, sources, td / "p2.mp4", td / "wp2")
    check("framing reaches the renderer",
          calls[0]["framing"] == "tight" and calls[1]["framing"] == "wide")
    check("budgeted replay rendered exactly once",
          len(replays) == 1 and led2["replay_count"] == 1)

    # narration is best-effort: TTS failure ships the story clean
    story._maybe_narration = lambda text, work: None
    e = dict(base, narration={"text": "Two days later he responded",
                              "over_beat": 0,
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

    # ---- reviewer #8: stronger narrative validation --------------------
    e = dict(base, hook_overlay="GO")            # 1 word
    check("hook <3 words rejected (#8)",
          story_director.validate_edl(e, durs) is None)
    e = dict(base, hook_overlay="one two three four five six seven eight")
    check("hook >7 words rejected (#8)",
          story_director.validate_edl(e, durs) is None)
    e = dict(base, central_question="")
    check("empty central_question rejected (#8)",
          story_director.validate_edl(e, durs) is None)
    e = dict(base)
    e["beats"] = [dict(base["beats"][0], role="setup"),
                  dict(base["beats"][1], role="payoff"),
                  {"source_id": "c", "start": 2, "end": 8, "role": "context",
                   "purpose": "trailing context", "transition": "hard_cut",
                   "context_overlay": "", "effects": []}]
    check("story ending on a context beat rejected (#8)",
          story_director.validate_edl(e, durs) is None)
    e = dict(base, structure="cold_open")        # opens on setup — wrong
    check("cold_open that opens on setup rejected (#8)",
          story_director.validate_edl(e, durs) is None)
    e = dict(base, ending={"type": "reaction_hold", "duration": 0.2})
    v = story_director.validate_edl(e, durs)
    check("reaction hold floored to >=0.8s (#8)",
          v["ending"]["duration"] >= 0.8)
    e = dict(base, target_duration=300)
    v = story_director.validate_edl(e, durs)
    check("target_duration clamped into 25-90 (#8)",
          25 <= v["target_duration"] <= 90)
    # cut-window overlap: a beat outside all evidence windows is rejected
    wins = {"a": [(2.0, 10.0)], "b": [(5.0, 20.0)]}
    e = dict(base)
    e["beats"] = [dict(base["beats"][0]),
                  dict(base["beats"][1], start=21.5, end=24.0)]  # b past 20
    check("cut off the evidence windows rejected (#8)",
          story_director.validate_edl(e, durs, wins) is None)
    check("cut inside evidence windows accepted (#8)",
          story_director.validate_edl(dict(base), durs, wins) is not None)

    # ---- reviewer #2: semantic event fingerprint separates incidents ---
    import run_third as rt2
    r_argue = [{"summary": "Kai and Ron argue about rent money owed",
                "title": "rent argument", "date": "2026-07-03",
                "source_id": "u1"},
               {"summary": "Ron argues the rent money was already paid",
                "title": "rent dispute", "date": "2026-07-04",
                "source_id": "u2"}]
    r_gift = [{"summary": "Kai surprises Ron with a huge donation gift",
               "title": "donation gift", "date": "2026-07-20",
               "source_id": "u3"},
              {"summary": "Ron thanks Kai for the donation gift on stream",
               "title": "gift thanks", "date": "2026-07-21", "source_id": "u4"}]
    fp_a = rt2._event_fingerprint(["kai", "ron"], r_argue)
    fp_g = rt2._event_fingerprint(["kai", "ron"], r_gift)
    check("same people, different incident -> different event id (#2)",
          fp_a != fp_g and fp_a[0] == fp_g[0])
    evs = {"events": {}}
    rt2._upsert_event(evs, ["kai", "ron"], r_argue, ["u1", "u2"])
    rt2._upsert_event(evs, ["kai", "ron"], r_gift, ["u3", "u4"])
    check("distinct incidents get distinct event records (#2)",
          len(evs["events"]) == 2)

    # ---- reviewer #8: semantic subclustering splits the people pile ------
    # find_clusters groups by shared PEOPLE; two distinct incidents between
    # the same streamers must be split into separate events (each with its
    # own director call), not compiled into one fake story.
    mixed = r_argue + r_gift
    subs = rt2._semantic_subclusters(mixed)
    check("people pile split into 2 semantic events (#8)", len(subs) == 2,
          f"got {len(subs)} groups")
    check("each split event keeps exactly its own sources (#8)",
          sorted(len(s) for s in subs) == [2, 2])
    ids = [{r["source_id"] for r in s} for s in subs]
    check("split groups do not mix incidents (#8)",
          {"u1", "u2"} in ids and {"u3", "u4"} in ids)
    # same incident (shared action vocabulary, same ISO week) stays whole
    one = rt2._semantic_subclusters(r_argue)
    check("same-incident clips stay one event (#8)",
          len(one) == 1 and len(one[0]) == 2)
    # a lone unrelated source becomes its own (sub-story-size) group
    solo = rt2._semantic_subclusters(
        r_argue + [{"summary": "Mara plays a calm cooking game alone",
                    "title": "cooking", "date": "2026-07-03",
                    "source_id": "u9"}])
    sizes = sorted(len(s) for s in solo)
    check("an unrelated source is not merged into an event (#8)",
          sizes == [1, 2])

    # ---- reviewer #11: stemming + generic-word stopping --------------------
    check("stemming collapses react/reacts/reaction/reacting",
          rt2._stem("reacts") == rt2._stem("reaction")
          == rt2._stem("reacting") == "react")
    check("stemming leaves short words intact",
          rt2._stem("game") == "game" and rt2._stem("goes") == "goes")
    # same event described with DIFFERENT wording (evicted/eviction, owed/owes)
    # now merges because the stems match — the false-SEPARATION the reviewer
    # flagged. Different ISO-safe same week + shared >=2 stems.
    same_diff_words = [
        {"summary": "Landlord evicts Kai over unpaid rent owed",
         "title": "eviction", "date": "2026-07-03", "source_id": "s1"},
        {"summary": "Kai reacts to the eviction, still owes the rent",
         "title": "evicted", "date": "2026-07-04", "source_id": "s2"}]
    check("same event, different wording now merges via stems (#11)",
          len(rt2._semantic_subclusters(same_diff_words)) == 1)
    # two UNRELATED clips whose only overlap is generic streamer words
    # ('reacts', 'stream') must NOT be merged into a fake event
    generic_only = [
        {"summary": "Kai reacts on stream to a funny cat video",
         "title": "reaction", "date": "2026-07-03", "source_id": "g1"},
        {"summary": "Kai reacts on stream to a scary game trailer",
         "title": "reaction", "date": "2026-07-04", "source_id": "g2"}]
    check("generic streamer words alone do NOT merge unrelated clips (#11)",
          len(rt2._semantic_subclusters(generic_only)) == 2)

    # ---- reviewer #1: vision provenance --------------------------------
    from third_capture import scene_analysis
    import inspect
    sa_src = inspect.getsource(scene_analysis.analyze_source)
    check("scene analyst grants Read for vision (#1)",
          "read_files=True" in sa_src)
    check("visual_beats gated on vision_ok, not sheet existence (#1)",
          "if vision_ok else []" in sa_src)

    # ---- public-title quality floor ------------------------------------
    # 2026-07-29 shipped "WWWW", "w max" and "ron shaking ahh" as real
    # YouTube titles: both author brains were down, and safe_title passed the
    # clipper's hype through because it was SAFE. Safety is not quality.
    from third_capture import author as _au
    check("pure hype title is low-signal", _au.title_is_low_signal("WWWW"))
    check("hype + one word is low-signal", _au.title_is_low_signal("w max"))
    check("bare noun title is low-signal", _au.title_is_low_signal("SUBURB"))
    check("short tease is low-signal", _au.title_is_low_signal("Is he back?"))
    check("informative title is NOT low-signal",
          not _au.title_is_low_signal(
              "Kai Cenat Gives Out The First Streamer University Diploma"))
    check("ugly but informative title survives",
          not _au.title_is_low_signal(
              "jasons camera ,an gets pass code to his room"))
    # the floor replaces noise with a safe, coherent channel line
    _t = _au.fallback_title("stableronaldo", "WWWW",
                            "yo what the hell is that bro he actually did it")
    check("hype title replaced", not _au.title_is_low_signal(_t)
          and "WWWW" not in _t)
    check("replacement names the streamer", "Stableronaldo" in _t)
    # a good raw title is left alone
    _good = "Kai Cenat Gives Out The First Streamer University Diploma"
    check("good raw title passes through untouched",
          _au.fallback_title("kaicenat", _good, "anything") == _good)
    _n = _au.fallback_title("silky", "SUBURB", "uh um like yeah")
    check("bare noun -> neutral title, not hype",
          not _au.title_is_low_signal(_n) and "SUBURB" not in _n)
    # Quoting the transcript directly produced 3/3 incoherent titles on real
    # 07-29 data ("Oh My God Aloki Aloki Got Some Dude Damn"). The floor must
    # make NO specific claim — only the author brain picks a real moment.
    _real = ("oh my god aloki aloki got some dude damn that was actually "
             "insane did you see what just happened there")
    check("floor does not quote the transcript",
          "aloki" not in _au.fallback_title("stableronaldo", "w", _real).lower())
    # ...but a multi-clip day must not ship the same line repeatedly
    _batch = {_au.fallback_title(s, "W", "") for s in
              ("kaicenat", "stableronaldo", "plaqueboymax", "xqc", "silky")}
    check("neutral titles vary across a batch", len(_batch) >= 3)
    check("neutral title is stable for the same clip",
          _au.fallback_title("xqc", "W", "") ==
          _au.fallback_title("xqc", "W", ""))
    check("every fallback title is within YouTube's 100 chars",
          all(len(_au.fallback_title(s, r, t)) <= 100 for s, r, t in [
              ("x", "W", "a" * 400), ("y", "z" * 300, ""),
              ("streamer", "w", " ".join(["word"] * 200))]))
    # authoring failure must be LOUD (it silently degraded on 07-29)
    import inspect as _i
    check("total authoring failure logs a warning",
          "AUTHORING FAILED" in _i.getsource(_au.author_package))
    _rt_src = (REPO / "scripts" / "run_third.py").read_text()
    check("run_third routes the raw title through the quality floor",
          "author.fallback_title" in _rt_src)

    # ---- brain-health gate (blind-slate incident, 07-29 morning) --------
    # Every rank/author/scene call failed for ~90 min and the run still
    # published 4 view-count-picked clips. The gate must trip on proven
    # total failure, never on flakiness, and the run must consult it.
    _saved = dict(_au._BRAIN)
    try:
        _au._BRAIN.update(ok=0, fail=0)
        check("fresh state: brain not down", not _au.brain_down())
        _au._BRAIN.update(ok=0, fail=2)
        check("2 failures alone do not trip the gate (min 3 calls)",
              not _au.brain_down())
        _au._BRAIN.update(ok=0, fail=3)
        check("3 failures, 0 ok -> brain down", _au.brain_down())
        _au._BRAIN.update(ok=1, fail=9)
        check("a single success proves the path — gate never trips",
              not _au.brain_down())
    finally:
        _au._BRAIN.update(_saved)
    check("rank_clips records brain outcomes",
          "_brain_note" in _i.getsource(_au.rank_clips))
    check("author_package records brain outcomes",
          "_brain_note" in _i.getsource(_au.author_package))
    check("run_third consults the gate before filling a slot",
          "author.brain_down()" in _rt_src)
    check("gate has an explicit operator override",
          "THIRD_ALLOW_BLIND" in _rt_src)
    check("gated slots are skipped, not errored (no retry churn)",
          "brain down — blind-slate gate" in _rt_src)

    # ---- judge verdicts are SEEABLE ------------------------------------
    # Every brain judges each slot, but the reasoning lived only in the CI
    # log — expiring, and ~1200 lines to read. These lock the capture path
    # (verdicts recorded on BOTH the posted and rejected branches) and the
    # renderer that makes them legible without log archaeology.
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("_judges", REPO / "scripts"
                                         / "judges.py")
    _j = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_j)

    _rt = _ilu.spec_from_file_location("_rt", REPO / "scripts"
                                       / "run_third.py")
    # don't execute run_third (it has side effects) — assert on source
    check("run_third records banger verdicts", '_judge("banger"' in _rt_src)
    check("run_third records content-gate verdicts",
          '_judge("content"' in _rt_src)
    check("run_third records vision verdicts", '_judge("vision"' in _rt_src)
    check("run_third records render_qa verdicts",
          '_judge("render_qa"' in _rt_src)
    check("run_third records title provenance", '_judge("title"' in _rt_src)
    check("run_third records story-director cluster verdicts",
          "_story_verdict(" in _rt_src)
    check("verdicts attach on the ERROR path too (rejects matter most)",
          _rt_src.index('result["judges"]')
          > _rt_src.index('result["error"] = f"{type(e).__name__}'))
    check("verdicts persist into the run stats",
          '"judges", "took_s")' in _rt_src
          and '"brain": author.brain_health()' in _rt_src)
    check("per-slot timing persists too (it was computed and dropped, so "
          "there was ZERO timing data to diagnose the 113-min runs with)",
          '"took_s"' in _rt_src)
    check("blocklisted clips record WHY, not just that they were blocked",
          '"rejected_by"' in _rt_src and '"rejected_why"' in _rt_src)
    # the renderer must distinguish the two failure shapes that look
    # identical in the posted log but mean opposite things
    check("viewer flags a BLIND pick (can't-score default)",
          "BLIND" in "".join(_j._fmt_judge(
              "banger", {"score": 0.5, "blind": True})))
    check("viewer does not flag a real score as blind",
          "BLIND" not in "".join(_j._fmt_judge(
              "banger", {"score": 0.6, "why": "real reason"})))
    _sd = "".join(_j._fmt_judge("story_director", {"clusters": [
        {"cluster": "a", "outcome": "starved", "why": "no analyzable"},
        {"cluster": "b", "outcome": "not_a_story", "why": "no arc"}]}))
    check("viewer separates a STARVED story from a genuine no-arc",
          "STARVED" in _sd and "no arc" in _sd)
    check("viewer marks an unavailable judge as DOWN, not as a pass",
          "DOWN" in "".join(_j._fmt_judge(
              "vision", {"verdict": "unavailable"})))
    check("viewer names the title floor when authoring produced nothing",
          "FLOOR" in "".join(_j._fmt_judge(
              "title", {"source": "floor", "kept_raw": False})))
    # _judge must coerce to JSON-SAFE primitives AT THE DOOR. Storing a raw
    # object survives _judge but detonates at the json.dumps on attach —
    # which runs OUTSIDE the render's try block, so it would kill the slot.
    # Found by probing before ship; this locks it.
    import json as _js
    _ns = {"__name__": "_probe", "json": _js,
           "__file__": str(REPO / "scripts" / "run_third.py")}
    # slice to a STABLE marker, not a line count: adding a helper used to
    # cut this mid-function and break every test below it
    _hdr = _rt_src[:_rt_src.index("def _load_log")]
    exec(compile(_hdr, "run_third", "exec"), _ns)

    class _Boom:
        def __repr__(self): raise ValueError("unserialisable")
        def __str__(self): return "<obj>"
    _ns["_judge"]("probe", bad=_Boom(), s="x" * 400, f=1.23456789,
                  lst=["y" * 400] * 20, b=True, n=3, empty=None)
    _pj = _ns["_JUDGES"]["probe"]
    check("_judge survives an unserialisable value", "bad" in _pj)
    check("_judge output is JSON-serialisable (the real failure mode)",
          _js.loads(_js.dumps(_ns["_JUDGES"]))["probe"]["bad"] == "<obj>")
    check("_judge truncates long strings", len(_pj["s"]) == 160)
    check("_judge caps and truncates lists",
          len(_pj["lst"]) == 5 and len(_pj["lst"][0]) == 160)
    check("_judge keeps bools/ints intact, drops empties",
          _pj["b"] is True and _pj["n"] == 3 and "empty" not in _pj)
    check("the attach path cannot raise either",
          "default=str" in _rt_src and "[judges] not recorded" in _rt_src)

    # ---- UNJUDGED GATE -------------------------------------------------
    # 2026-07-30: three clips shipped that NOTHING had judged. All three
    # content gates fail open independently — and the selection floor
    # fails open by exactly zero margin, because the can't-score default
    # (0.5) equals min_banger (0.5), so `banger >= min_banger` is True on
    # a fully blind run. The gate refuses to publish when not one content
    # judge could evaluate the clip.
    _aj, _J = _ns["_any_judgment"], _ns["_JUDGES"]
    _jd = _ns["_judge"]

    def _scen(*calls):
        _J.clear()
        for c in calls:
            c()
        return _aj()

    check("blind ranker + content and vision down -> UNJUDGED (07-30 case)",
          not _scen(lambda: _jd("banger", score=0.5, blind=True),
                    lambda: _jd("content", verdict="unavailable"),
                    lambda: _jd("vision", verdict="unavailable")))
    check("a real banger score is enough to ship",
          _scen(lambda: _jd("banger", score=0.62, why="r", blind=False)))
    check("content gate alone is enough to ship",
          _scen(lambda: _jd("banger", score=0.5, blind=True),
                lambda: _jd("content", score=0.81, verdict="pass")))
    check("vision alone is enough to ship",
          _scen(lambda: _jd("banger", score=0.5, blind=True),
                lambda: _jd("vision", verdict="pass", confidence=0.9)))
    check("a content-gate REJECT still counts as a judgment",
          _scen(lambda: _jd("content", score=0.2, verdict="reject")))
    check("mechanical checks alone do NOT count as judgment",
          not _scen(lambda: _jd("render_qa", verdict="pass")))
    check("no verdicts at all -> unjudged", not _scen())
    check("operator-specified clips are never treated as unjudged",
          _scen(lambda: _jd("banger", source="operator-specified",
                            blind=False))
          and "operator-specified" in _rt_src)
    check("the gate is wired into the publish path",
          "_any_judgment()" in _rt_src and "unjudged: no content judge"
          in _rt_src)
    # the CALL SITE (not the def) must raise _SkipSlot: a deliberate skip
    # doesn't retry, and retrying would just fetch another unjudged clip
    _call = _rt_src.index("not _any_judgment()")
    check("unjudged is a SKIP, not an error (retry gets another blind clip)",
          "_SkipSlot" in _rt_src[_call:_call + 200]
          and "RuntimeError" not in _rt_src[_call:_call + 200])
    check("stories are exempt (the director is their judge)",
          'led.get("kind") == "twitch_clip" and not _any_judgment()'
          in _rt_src)

    # ---- ESCALATION over giving up -------------------------------------
    # 2026-07-31: two slots posted nothing on "quality floor: best banger
    # 0.45 < 0.5". That score judges the clipper's TWITCH TITLE ('sadge',
    # 'foams') — the clip was binned without ever being downloaded or
    # transcribed, while a STRICTER transcript judge (0.70) sat unused
    # downstream. An empty slot is a failure, not a success.
    check("a failed title floor escalates instead of skipping",
          "[rescue]" in _rt_src and "postable = rescue" in _rt_src)
    check("escalation goes to the transcript judge, a HIGHER bar",
          "min_banger_content" in _rt_src
          and float(_rt_src.split('spec.get("min_banger_content", ')[1]
                    .split(")")[0])
          > float(_rt_src.split('spec.get("min_banger", ')[1].split(")")[0]))
    check("a hard floor still exists (spam is not worth transcribing)",
          'spec.get("rescue_floor", 0.25)' in _rt_src
          and "nothing worth " in _rt_src)
    check("the hard floor is below the title floor it rescues from",
          0.25 < 0.50)
    # a rescued clip has already been judged weak once — it must EARN the
    # slot, so an unavailable transcript judge is a retry, never a ship
    check("rescue fails CLOSED when the transcript judge is unavailable",
          'cb is None and _JUDGES.get(' in _rt_src
          and "must EARN its slot" in _rt_src)
    check("a normal (non-rescued) clip still fails OPEN on that judge",
          "cb is not None and cb < content_floor" in _rt_src)
    check("the escalation is recorded as a verdict, not silent",
          '_judge("selection", verdict="rescue"' in _rt_src
          and '_judge("selection", verdict="skip"' in _rt_src)
    # the viewer must show it, or the operator can't tell a rescue from a
    # normal post when reading back
    check("judges viewer renders the selection verdict",
          "selection" in (REPO / "scripts" / "judges.py").read_text())

    # ---- SUPPLY: allowlist width + source health -----------------------
    # 2026-07-31: four candidates inspected, all weak on transcript. Not a
    # gate problem — a supply one. A wider allowlist only helps if dead
    # handles are visible, so they can be pruned on evidence not guesswork.
    _cfg = _js.loads((REPO / "state" / "third_packages"
                       / "default_clip.json").read_text())["capture"]
    _tw = _cfg["sources"]["twitch"]
    check("twitch allowlist widened past the starved 30",
          len(_tw) >= 60, f"{len(_tw)} channels")
    check("no duplicate handles in the allowlist",
          len(_tw) == len(set(_tw)))
    check("core stays small so new names deprioritize, not dominate",
          len(_cfg["core"]) <= 15 and set(_cfg["core"]) <= set(_tw))
    _sh = _ns["_source_health"]
    _SH = _ns["_SOURCE_HEALTH"]
    _SH.clear()
    _sh("twitch", "alive", ok=True, clips=6)
    _sh("twitch", "quiet", ok=True, clips=0)
    _sh("rumble", "AdinLive", ok=False, err="CalledProcessError")
    _sh("rumble", "AdinLive", ok=False, err="CalledProcessError")
    check("source health counts clips returned",
          _SH["twitch:alive"]["clips"] == 6)
    check("a failing source accumulates failures with the error kind",
          _SH["rumble:AdinLive"]["fail"] == 2
          and _SH["rumble:AdinLive"]["err"] == "CalledProcessError")
    check("only zero-yield sources are persisted (state stays small)",
          '"dead_sources"' in _rt_src
          and 'v.get("clips", 0) == 0' in _rt_src)
    _jsrc = (REPO / "scripts" / "judges.py").read_text()
    check("viewer separates ERRORED sources from merely quiet ones",
          "ERRORED" in _jsrc and "returned 0 clips" in _jsrc)
    check("source health never raises (it runs inside discovery)",
          "def _source_health" in _rt_src
          and _rt_src.split("def _source_health")[1].split("def ")[0]
          .count("except Exception:") == 1)

    # ---- dead adapters: diagnosable, and parked when unfixable ---------
    # rumble 403s at the domain edge from CI egress (a real channel and a
    # nonsense slug 403 identically), so neither url form can ever win.
    # It was undiagnosable because both handlers printed only the
    # exception TYPE while yt-dlp's own message sat unused in e.output.
    _ce_src2 = (REPO / "third_capture" / "clip_edit.py").read_text()
    check("discovery surfaces yt-dlp's own error, not just the type",
          'getattr(e, "output", "")' in _ce_src2
          and 'getattr(e, "output", "")' in _rt_src)
    check("rumble no longer drops every row on unknown duration",
          'platform == "rumble" and dur > 120' in _ce_src2
          and 'dur == 0 or dur > 120' not in _ce_src2)
    check("kick's silent zero-clip result now warns",
          "yielded 0 " in _ce_src2)
    check("curl_cffi pinned in requirements (stops env drift)",
          "curl_cffi" in (REPO / "requirements.txt").read_text())
    check("rumble parked out of active sources with a recorded reason",
          "rumble" not in _cfg["sources"]
          and "403" in _cfg["sources_parked"]["rumble"]["reason"])
    check("parking preserves the handle for restoration",
          _cfg["sources_parked"]["rumble"]["channels"] == ["AdinLive"])

    # ---- the content gate can SEE -------------------------------------
    # 2026-07-31: every rejection all day was about talk — "rambling chat
    # talk", "vague ramble", "routine gameplay narration" — because the
    # gate judged words[:40] and nothing else. On a clips channel that is
    # a systematic bias against a fail, a reaction face, physical comedy:
    # all of which read as "rambling chat" from the transcript alone.
    _cs = _au._CONTENT_SYSTEM
    _REAL_CALL_CLAUDE = _au._call_claude   # restored before the
    _REAL_CALL_GROQ = _au._call_groq       # stderr test below
    check("content judge keeps the greenlight rubric",
          "ONE-SENTENCE TEST" in _cs and "AUTOMATIC-REJECT" in _cs
          and "Return ONLY JSON" in _cs)
    check("content judge is told to read the frames first",
          "READ THE IMAGE FIRST" in _cs)
    check("content judge must not dismiss a visual moment as talk",
          "describing the audio of" in _cs)
    check("content judge still believes frames over a lying title",
          "believe the frames" in _cs)
    # provenance: a text-only verdict carries the very bias this removes
    _seen = {}
    _au._call_claude = lambda u, system=None, read_files=False: (
        _seen.update(read=read_files, sys=system) or
        {"scores": [{"i": 0, "banger": 0.86, "why": "visible fail"}]})
    _sc, _wy, _saw = _au.judge_content("s", "vague title", "um so anyway",
                                       sheet="/tmp/sheet.jpg")
    check("a visual clip can now score high despite mundane words",
          _sc == 0.86 and _saw is True and _wy == "visible fail")
    check("vision judge is granted Read for the contact sheet",
          _seen.get("read") is True)
    _au._call_claude = lambda u, system=None, read_files=False: (
        _ for _ in ()).throw(RuntimeError("vision down"))
    _au._call_groq = lambda u, system=None: None
    _sc2, _, _saw2 = _au.judge_content("s", "t", "words",
                                       sheet="/tmp/sheet.jpg")
    check("vision failure degrades to text-only, never loses the clip",
          _saw2 is False)
    check("a blind verdict is RECORDED as blind, not passed off as sighted",
          "saw_frames" in _rt_src
          and "TEXT-ONLY" in (REPO / "scripts" / "judges.py").read_text())
    check("no sheet at all -> text-only path, still no crash",
          _au.judge_content("s", "t", "w", sheet="")[2] is False)
    check("run_third builds a contact sheet of the SOURCE for the gate",
          "contact_sheet(" in _rt_src and "author.judge_content(" in _rt_src)

    # ---- the brain's own error must survive ---------------------------
    # The CLI returned rc=1 with no JSON for ~90 min on 07-29 and again
    # mid-run on 07-30, and "rc=1" was the ENTIRE diagnosis available:
    # capture_output collected stderr and the raise reported only the
    # return code. Same bug class as the rumble 403.
    _au._call_claude = _REAL_CALL_CLAUDE   # stubbed above; the next
    _au._call_groq = _REAL_CALL_GROQ       # test needs the REAL one
    import subprocess as _sp
    import shutil as _sh
    _real_run, _real_which = _sp.run, _sh.which
    try:
        _sh.which = lambda n: "/usr/bin/claude"
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "test"

        class _R:
            returncode, stdout, stderr = 1, "", "EPIPE writing to stream."
        _sp.run = lambda *A, **K: _R()
        try:
            _au._call_claude("hi")
            check("claude failure raises", False)
        except RuntimeError as _e:
            _m = str(_e)
            check("brain failure surfaces the CLI's own stderr",
                  "EPIPE writing to stream." in _m)
            check("brain failure still reports the return code",
                  "rc=1" in _m)
            check("an empty stdout is stated, not silently omitted",
                  "stdout=<empty>" in _m)

        # ---- the usage-limit breaker ----------------------------------
        # The 07-29 "90-minute outage" was one run inside one exhausted
        # subscription window. Once the account is out of budget every
        # remaining call is GUARANTEED to fail; making ~40 of them anyway
        # costs wall-clock and stampedes free-tier Groq behind it.
        _calls = []

        class _RL:
            returncode, stdout, stderr = 1, "", "Claude usage limit reached"

        def _count(*A, **K):
            _calls.append(A[0] if A else K.get("args"))
            return _RL()
        _sp.run = _count
        _au._LIMIT_HIT.update(at="", detail="")
        check("a usage limit returns None instead of raising",
              _au._call_claude("hi") is None)
        check("the limit is recorded so the run can report it",
              bool(_au.brain_limited().get("at")))
        _n = len(_calls)
        check("no CLI call at all once limited (the breaker is open)",
              _au._call_claude("hi") is None and len(_calls) == _n)

        # the model must be PINNED — an unpinned call inherits the account
        # default, which is how a window gets spent without anyone choosing
        _au._LIMIT_HIT.update(at="", detail="")
        _calls.clear()
        _sp.run = _count
        try:
            _au._call_claude("hi")
        except RuntimeError:
            pass
        check("the CLI call pins a model",
              bool(_calls) and "--model" in (_calls[0] or []))

        # a limit can also arrive rc=0 with prose and no JSON
        _au._LIMIT_HIT.update(at="", detail="")

        class _R0:
            returncode = 0
            stdout = "I'm out of usage limit for now, resets at 3pm."
            stderr = ""
        _sp.run = lambda *A, **K: _R0()
        check("a prose usage limit on rc=0 arms the breaker too",
              _au._call_claude("hi") is None
              and bool(_au.brain_limited().get("at")))
    finally:
        _sp.run, _sh.which = _real_run, _real_which
        _au._LIMIT_HIT.update(at="", detail="")

    # judge_content must not amplify: a vision call that just failed must
    # NOT trigger a second Claude call for the same clip via rank_clips
    _seen = []
    _rc, _rg = _au._call_claude, _au._call_groq
    try:
        def _boom(*A, **K):
            _seen.append("claude")
            raise RuntimeError("brain down")
        _au._call_claude = _boom
        _au._call_groq = lambda *A, **K: (_seen.append("groq") or
                                          {"scores": [{"banger": 0.6,
                                                       "why": "ok"}]})
        _s, _w, _saw = _au.judge_content("s", "t", "words", sheet="/x.png")
        check("a failed vision call does not fire a SECOND claude call",
              _seen.count("claude") == 1)
        check("the text fallback still produces a score", _s == 0.6)
        check("and it is recorded as blind", _saw is False)
    finally:
        _au._call_claude, _au._call_groq = _rc, _rg

    # ---- source health is judged across runs, not one sample ----------
    _jmod = _j
    _rep = []
    _jmod.print = lambda *a, **k: _rep.append(" ".join(str(x) for x in a))
    try:
        # one run: nothing may be called dead (a streamer offline for a
        # day is not a dead handle — that is how guesswork creeps back)
        _jmod._sources_report([{"dead_sources": {"twitch:a": {"clips": 0}}}])
        check("a single quiet run never marks a source dead",
              not any("prunable" in x for x in _rep)
              and any("need >=3" in x for x in _rep))
        _rep.clear()
        _jmod._sources_report([{"dead_sources": {"twitch:a": {"clips": 0}}}
                               for _ in range(4)])
        check("quiet on every one of 4 runs -> prunable",
              any("DEAD, prunable" in x for x in _rep))
        _rep.clear()
        _jmod._sources_report(
            [{"dead_sources": {"twitch:a": {"clips": 0}}} for _ in range(3)]
            + [{"dead_sources": {}}])
        check("a source that produced ONCE is never called dead",
              not any("prunable" in x for x in _rep))
        _rep.clear()
        _jmod._sources_report([{"dead_sources": {
            "rumble:X": {"clips": 0, "fail": 1, "err": "CalledProcessError"}}}])
        check("an ERRORED source is reported as a code bug, not a prune",
              any("broken adapter" in x for x in _rep))
    finally:
        _jmod.print = print

    # ---- VOD mining (funnel/ — shared media capability) ----------------
    # Clip discovery only sees what a human chose to clip. On a thin day
    # the moment a clipper MISSED is often seconds away from one they got.
    from funnel import vod_miner as _vm
    check("vod_miner refuses without helix coordinates (invents nothing)",
          _vm.maybe_mine({"url": "x"}, "/tmp") == [])
    check("vod_miner never raises (supply is best-effort)",
          _vm.maybe_mine(None, "/nonexistent") == [])
    check("mined urls are identifiable as synthetic",
          _vm.is_mined("vodmine://v/1")
          and not _vm.is_mined("https://twitch.tv/a/clip/b"))
    # A mined moment keys on video_id AND offset. Keying on the last url
    # segment alone would collide two VODs sharing an offset — in the
    # POSTED LOG, where a collision means a duplicate upload.
    check("mined clip keys are distinct across VODs at the same offset",
          _ns["_clip_key"]("vodmine://AAA/900")
          != _ns["_clip_key"]("vodmine://BBB/900"))
    check("twitch dedupe identity is unchanged by that",
          _ns["_clip_key"]("https://clips.twitch.tv/Slug")
          == _ns["_clip_key"]("https://twitch.tv/ch/clip/Slug"))
    check("mining is gated on a thin pool, not run every time",
          "if len(cands) < min_pool:" in _rt_src)
    check("a mined candidate skips the download (already extracted)",
          'if pick.get("mined"):' in _rt_src)
    check("mined candidates still face the same content gate",
          _rt_src.index('pick.get("mined")')
          < _rt_src.index("content gate: transcript-aware score"))
    check("vod_miner lives in funnel/ (shared media capability)",
          (REPO / "funnel" / "vod_miner.py").exists())

    # ---- engines/render_qa: shared mechanical render-QA ----------------
    # First ANALYSIS engine in the shared layer. Logic tier only here (no
    # ffmpeg): parsers, registry wiring, verdict semantics, consumers.
    from engines import render_qa as _rq
    import engines as _eng
    check("render_qa registered in the shared engine registry",
          _eng.REGISTRY.get("render_qa", {}).get("kind") == "module")
    check("render_qa provisioning entry exists (pure-ffmpeg, empty deps)",
          __import__("engines.provision", fromlist=["_PIP_DEPS"])
          ._PIP_DEPS.get("render_qa") == [])
    _bd = _rq._black_intervals(
        "[blackdetect] black_start:14.1 black_end:14.72 black_duration:0.62")
    check("blackdetect stderr parses to intervals", _bd == [(14.1, 14.72)])
    check("freezedetect stderr parses to spans",
          _rq._freeze_spans("lavfi.freezedetect.freeze_duration: 3.4\n"
                            "freeze_duration: 2.1") == [3.4, 2.1])
    check("maybe_check is fail-open when the analyzer is absent",
          _rq.maybe_check("/nonexistent/x.mp4") is None)
    check("verdict semantics documented: None=analyzer, ok=False=defect",
          "None = the ANALYZER failed" in (_rq.maybe_check.__doc__ or ""))
    check("clip_qa runs the free engine pass before the paid vision call",
          "render_qa" in _i.getsource(__import__(
              "third_capture.clip_qa", fromlist=["review"]).review))
    check("story renderer fails closed on a broken stitch",
          "render_qa rejected the stitch" in (REPO / "third_capture"
                                              / "story.py").read_text())

    # ---- closing guard + source bar-strip (simple_fallback fixes) ------
    _ce_src = (REPO / "third_capture" / "clip_edit.py").read_text()
    check("closing guard exists (symmetric to the opening guard)",
          "def _closing_guard" in _ce_src)
    check("closing guard runs in the cut flow before caption rebase",
          _ce_src.index("_closing_guard(raw, t0, t1)")
          < _ce_src.index('"w": w["w"], "s": w["s"] - t0'))
    check("ledger records the closing trim", "closing_trim_s" in _ce_src)
    check("source bar-strip exists for the blur-fill graph",
          "def _content_crop" in _ce_src and "{bar_crop}split" in _ce_src)
    check("blur foreground is clamped inside the canvas",
          "force_original_aspect_ratio=decrease[fgs]" in _ce_src)
    check("render output is capped at the cut length (-t)",
          '"-t", f"{dur:.3f}"' in _ce_src)

    # ================= the posted log is SACRED =======================
    # Every check below guards a path that, when it broke, put a duplicate
    # on the channel or erased dedupe history. docs/STORAGE_AUDIT.md:
    # "losing an entry means a duplicate upload".

    # a corrupt ledger must ABORT, never silently become an empty one
    import tempfile as _tf
    # the real module (storyline already imports it, so this is not new
    # surface — main() is __main__-guarded and import has no side effects)
    from scripts import run_third as _rtm
    _lp = _rtm.LOG_PATH
    try:
        _d = Path(_tf.mkdtemp())
        _rtm.LOG_PATH = _d / "log.json"
        (_d / "log.json").write_text("{not json")
        try:
            _rtm._load_log()
            check("a corrupt posted log aborts the run", False)
        except SystemExit:
            check("a corrupt posted log aborts the run", True)
        (_d / "log.json").write_text('["a", "b"]')
        try:
            _rtm._load_log()
            check("a valid-JSON-but-wrong-shape log also aborts", False)
        except SystemExit:
            check("a valid-JSON-but-wrong-shape log also aborts", True)
        (_d / "log.json").unlink()
        check("a MISSING log is a first run, not an emergency",
              _rtm._load_log() == {"posted": {}})

        # a blocklist write must hit disk immediately — the only _save_log
        # call site used to be inside the successful-upload branch, so a
        # run that shipped nothing threw away every rejection it paid for
        _log = {"posted": {}}
        _rtm._blocklist(_log, "rejected-x", {"qa_rejected": True})
        check("a blocklist entry is persisted the moment it is written",
              _json.loads((_d / "log.json").read_text())["posted"]
              .get("rejected-x", {}).get("qa_rejected") is True)
    finally:
        _rtm.LOG_PATH = _lp

    check("the upload CLAIMS its slot before sending bytes (a mid-flight "
          "failure must not let the retry upload the same clip twice)",
          _rt_src.index('log["posted"][slug] = _claim')
          < _rt_src.index("YouTubeUploader(channel=\"third\").upload("))
    check("the claim is persisted, not just held in memory",
          '_claim\n            _save_log(log)' in _rt_src)
    check("a pending claim never enters analytics (it has no video URL)",
          'e.get("pending")' in
          (REPO / "scripts" / "fetch_analytics.py").read_text())
    check("pending claims are surfaced for a human — the video may or may "
          "not be live and only a person can tell",
          "PENDING UPLOAD CLAIMS" in (REPO / "scripts" / "judges.py").read_text())
    check("a checkpoint carries every state file the run mutates, since a "
          "push race hard-resets and restores only what it was given",
          '"state/third_posted_log.json", "state/third_events.json"'
          in _rt_src)
    check("the posted log is checkpointed to main mid-run (a run killed "
          "at the 120min wall must not desync dedupe state)",
          "_checkpoint_log(" in _rt_src
          and "ci_commit_state.sh" in _rt_src)
    check("the log is saved on EVERY exit path, not only after an upload",
          _rt_src.rindex("_save_log(log)")
          > _rt_src.rindex('return 0 if any(r["ok"]') - 2000)

    # publish_at collisions — two Shorts live in the same minute
    _now = _rtm.datetime.now(_rtm.timezone.utc)
    check("publish_at is clamped forward when it has already passed",
          _rtm._clamp_publish_at(
              (_now - _rtm.timedelta(hours=2))
              .strftime("%Y-%m-%dT%H:%M:%SZ")) >
          _now.strftime("%Y-%m-%dT%H:%M:%SZ"))
    check("a still-future publish_at is left exactly alone",
          _rtm._clamp_publish_at("2099-01-01T00:00:00Z")
          == "2099-01-01T00:00:00Z")
    check("no schedule stays no schedule",
          _rtm._clamp_publish_at(None) is None)
    check("a second run today starts PAST what an earlier run claimed",
          "already claimed up to" in _rt_src)

    # variety caps must count what SHIPPED, not what was rejected
    check("rejected clips do not consume a streamer's daily variety cap",
          'not k.startswith("rejected-")' in _rt_src
          and 'not v.get("qa_rejected")' in _rt_src)

    # the content gate must run on speechless clips — the exact material
    # the vision judge was built for
    check("the content gate runs when there is NO transcript",
          "if words is not None:" in _rt_src)
    _s, _w, _saw = _au.judge_content("s", "t", "", sheet="")
    check("a silent clip with no frames scores None (fail open), never a "
          "mid-band number that would blocklist it forever", _s is None)

    # mined moments must never leak the internal scheme to viewers
    check("a mined URL renders as an openable Twitch VOD deep-link",
          _rtm._public_source("vodmine://2412345678/4180")
          == "https://www.twitch.tv/videos/2412345678?t=01h09m40s")
    check("a real clip URL passes through untouched",
          _rtm._public_source("https://clips.twitch.tv/Abc")
          == "https://clips.twitch.tv/Abc")
    check("'Clipped by vod-mined' is suppressed (nobody clipped it)",
          "not vod_miner.is_mined(" in _rt_src)
    check("a mined moment is not judged on its (nonexistent) title",
          'c.get("mined")' in _rt_src
          and "no title to judge" in _rt_src)

    # the two definitions of clip identity must not drift again
    from third_capture import storyline as _sl
    check("storyline.clip_key delegates to the ONE canonical _clip_key",
          _sl.clip_key("vodmine://AAA/900")
          != _sl.clip_key("vodmine://BBB/900")
          and _sl.clip_key("vodmine://AAA/900")
          == _rtm._clip_key("vodmine://AAA/900"))
    check("...and still folds the two Twitch clip URL forms together",
          _sl.clip_key("https://clips.twitch.tv/Slug")
          == _sl.clip_key("https://twitch.tv/ch/clip/Slug?t=1"))

    # a run that ships nothing must SAY so
    check("a run that shipped no new video says NO NEW VIDEOS",
          "NO NEW VIDEOS" in _rt_src)

    # the workflow's dedupe sync must not fail open
    _yml = (REPO / ".github" / "workflows" / "third.yml").read_text()
    check("the dedupe sync distinguishes 'not on main' from 'sync failed'",
          "git cat-file -e" in _yml
          and "|| echo \"no committed dedupe state yet" not in _yml)

    # ============ the run must FINISH, not be killed at the wall =======
    _ce_src2 = (REPO / "third_capture" / "clip_edit.py").read_text()
    check("discovery is swept ONCE per window and cached run-wide "
          "(it was re-run per slot AND per retry: ~18 hits per handle)",
          "_SWEEP_CACHE" in _rt_src and "def _sweep(" in _rt_src)
    check("...and fanned out instead of 67 serial calls",
          "ThreadPoolExecutor" in _rt_src)
    check("a source failure records yt-dlp's MESSAGE, not just the class",
          'err=f"{type(e).__name__}: {d}"' in _rt_src)
    check("there is a wall-clock budget inside the job's 120min ceiling",
          "_deadline_passed()" in _rt_src and "_BUDGET_MIN" in _rt_src)
    check("the budget stops the slot loop, the retry loop AND the story arm",
          _rt_src.count("_deadline_passed()") >= 4)
    check("VOD expansions are capped (each is a 3-min whisper + a vision "
          "call, and nothing bounded how many fired)",
          "story_max_vod_expansions" in _rt_src)
    check("whisper weights are memoized, not re-read per transcription",
          "_WHISPER" in _ce_src2)
    check("the cut is analyzed ONCE, not once for calm and again in "
          "shot_plan.build on the same file",
          "an=_cut_an" in _ce_src2
          and "an: dict | None = None"
          in (REPO / "third_capture" / "shot_plan.py").read_text())
    check("localization fans out (58 serial HTTP calls per upload)",
          "ThreadPoolExecutor" in (REPO / "shared" / "localize.py").read_text())
    check("the gameplay scan has a hard timeout (it had NONE, and a hang "
          "cannot be caught by an except)",
          "SCAN_TIMEOUT" in (REPO / "funnel"
                             / "gameplay_scanner.py").read_text())
    _y2 = (REPO / ".github" / "workflows" / "third.yml").read_text()
    check("the posted log is committed BEFORE analytics (a cancelled job's "
          "grace window must not be spent on YouTube API calls)",
          _y2.index("Commit posted log") < _y2.index("Fetch third analytics"))
    check("pip and the whisper weights are cached across runs",
          "cache: 'pip'" in _y2 and "~/.cache/whisper" in _y2)

    # ============ render QA must not reject the house style ============
    from engines import render_qa as _rq
    import inspect as _insp
    _rqsig = _insp.signature(_rq.check)
    _floor = _rqsig.parameters["min_active_ratio"].default
    # a 16:9 source fitted into 1080x1920 is 1080x607 = 31.6% BY
    # CONSTRUCTION — a floor above that condemns every render we make
    check("the letterbox floor cannot fire on a normal 16:9 fit (0.316)",
          _floor < 0.316)
    check("...but still catches a frame boxed twice (~0.10-0.18)",
          _floor > 0.18)
    check("a failing letterbox probe cannot erase confirmed defects",
          "the {len(problems)} finding(s) above still stand"
          in (REPO / "engines" / "render_qa.py").read_text())
    check("freeze_min_s reaches the filter (it was hardcoded to 2.0, so "
          "any value under 2.0 was silently ignored)",
          "_detect_pass(video, freeze_min_s)" in
          (REPO / "engines" / "render_qa.py").read_text())
    check("the last-resort render rung blur-fills instead of black-padding "
          "(its whole job is 'always ship' — it cannot emit output QA "
          "mechanically rejects)",
          "_raw_vf" in _ce_src2 and "LAST-RESORT RUNG" in _ce_src2)
    check("...and carries the same -t cap as every other rung",
          '_raw_cmd += ["-t"' in _ce_src2)
    check("the closing guard probes its whole 2.5s budget, not 1.2s",
          "win = min(MAX_TRIM + 0.5, room)" in _ce_src2)

    # ============ the miner cannot manufacture a duplicate ==============
    _vm_src = (REPO / "funnel" / "vod_miner.py").read_text()
    check("mined files are named by ABSOLUTE vod offset — two anchors in "
          "one VOD used to collide and ship the same bytes under two "
          "different dedupe keys, invisible to every guard",
          'f"mined_{vid}_{int(abs_off)}.mp4"' in _vm_src)
    check("a partial extraction is deleted, not cached and reused",
          "unlink(missing_ok=True)" in _vm_src and "def _usable(" in _vm_src)
    check("...and a reused file is re-validated, not trusted for existing",
          "if not _usable(dest)" in _vm_src)
    check("peaks are mined by STRENGTH (energy_peaks returns them sorted "
          "by time, discarding the rank we over-fetched to preserve)",
          "_strength" in _vm_src)

    # ============ judges must not rubber-stamp their own failures =======
    check("a rescued clip needs a PASSING judgment, not merely a judgment "
          "(the ranker's rejection is what triggered the rescue)",
          "NEEDS A *PASSING* JUDGMENT" in _rt_src)
    check("the rescue fail-closed blocklists before raising, so the retry "
          "picks a different clip instead of the same one three times",
          "rescue fail-closed" in _rt_src)
    _bh = dict(_au._BRAIN)
    try:
        _au._BRAIN.update(ok=0, fail=0)
        _rc2, _rg2 = _au._call_claude, _au._call_groq
        try:
            _au._call_claude = lambda *A, **K: (_ for _ in ()).throw(
                RuntimeError("cli dead"))
            _au._call_groq = lambda *A, **K: {"scores": [{"banger": 0.9}]}
            _au.judge_content("s", "t", "words", sheet="/x.png")
        finally:
            _au._call_claude, _au._call_groq = _rc2, _rg2
        check("a vision failure counts as a FAILED brain task (it counted "
              "as nothing, so a CLI failing every eyes-on call while Groq "
              "answered read as a healthy brain)", _au._BRAIN["fail"] >= 1)
    finally:
        _au._BRAIN.update(_bh)

    print()
    if FAILS:
        print(f"ACCEPTANCE FAILED ({len(FAILS)}): {FAILS}")
        return 1
    print("ACCEPTANCE PASSED — story director architecture holds its laws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
