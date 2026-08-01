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
          '"judges")' in _rt_src and '"brain": author.brain_health()'
          in _rt_src)
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
    exec(compile("\n".join(_rt_src.splitlines()[:130]), "run_third", "exec"),
         _ns)

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

    print()
    if FAILS:
        print(f"ACCEPTANCE FAILED ({len(FAILS)}): {FAILS}")
        return 1
    print("ACCEPTANCE PASSED — story director architecture holds its laws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
