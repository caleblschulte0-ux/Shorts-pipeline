#!/usr/bin/env python3
"""NO DULL BEATS — the pipeline may not ship a dull beat.

The judges (interest, cool) can already TELL when a beat is dull or dead. This
director does something about it automatically: render → judge → for every dull
beat, ESCALATE its treatment (land it on MOTION of its subject instead of a flat
card or a still) → re-render → re-judge, looping until no beat is dull (or we run
out of escalations, which is reported, never hidden).

"Dull" is judged on PIXELS, not intent:
  - appeal below DULL_APPEAL (a flat card nobody stops scrolling for), OR
  - the cool judge flagged it DULL / LOW_MOTION / STILL_WHEN_MOTION_EXISTS, OR
  - it sits inside an interest-judge boring stretch AND isn't a high-appeal beat.
The HOOK is exempt when its appeal is high — a designed slam is allowed to hold.

Escalation (per beat, one level per round):
  a flat/designed card or a still  ->  `_force_motion`: the planner re-emits the
  beat as a depict shot, so the motion-first gate puts a MOVING clip of the
  subject under the text (still fallback only if no clip clears the bar).

    python scripts/no_dull_beats.py <story.beats.json> <out.mp4> [--rounds 3]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

DULL_APPEAL = 0.55        # below this a beat is dull on looks alone
SOFT_APPEAL = 0.68        # inside a boring stretch, below this counts as dull
# EVERY cool-judge hand that means "this beat is not carrying its weight" drives a
# fix (escalate to motion of the subject). Nothing gets flagged and then ignored:
# a fragment of the spectacle and a too-long hold are as fixable as a dull card.
DULL_FLAGS = {"DULL", "LOW_MOTION", "STILL_WHEN_MOTION_EXISTS",
              "FRAGMENT_OF_THE_SPECTACLE", "LONG_HOLD"}
_STOP = {"the", "a", "an", "of", "and", "in", "on", "at", "from", "to", "with",
         "it", "its", "is", "are", "that", "this", "as", "by", "for", "into",
         "every", "you", "your", "they", "their", "— ", "even", "more", "own"}


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


# the render logs subjects via repr(): single-quoted normally, but DOUBLE-quoted
# when the subject itself contains an apostrophe ("Earth's night ..."). Match both.
_WON_RE = re.compile(r"""MOTION WINS for (['"])(.+?)\1""")
_MISS_RE = re.compile(r"""no moving clip cleared the bar for (['"])(.+?)\1""")


def _motion_outcomes(render_stderr: str) -> tuple[set[str], set[str]]:
    """From a render's log, which escalation subjects actually GOT motion vs fell
    back. An escalation that missed must revert to the beat's ORIGINAL treatment
    (a designed card with real motion), never a dead still — that would be a
    downgrade, not a repair."""
    won = {m.group(2) for m in _WON_RE.finditer(render_stderr)}
    missed = {m.group(2) for m in _MISS_RE.finditer(render_stderr)}
    return won, missed


def _judge(render: Path, beatmap: Path, out: Path) -> tuple[dict, list[dict]]:
    out.mkdir(parents=True, exist_ok=True)
    _run([sys.executable, str(REPO / "scripts" / "interest_judge.py"),
          str(render), "--out", str(out / "interest")])
    _run([sys.executable, str(REPO / "scripts" / "cool_judge.py"), str(render),
          "--beatmap", str(beatmap), "--out", str(out / "cool")])
    interest = json.loads((out / "interest" / "interest.json").read_text())
    cool = json.loads((out / "cool" / "cool_prescreen.json").read_text())
    return interest, cool


def _in_boring(t: str, boring: list) -> bool:
    try:
        a, z = (float(x) for x in str(t).split("-"))
    except (ValueError, IndexError):
        return False
    return any(not (z < bs[0] or a > bs[1]) for bs in boring)


def _is_designed(beat: dict) -> bool:
    """A deliberate motion-graphic beat (comparison, orbit, number, zoom, title).
    These are CLEAN by design — dark background, legible type — so they score low
    on photographic-richness appeal even when they animate beautifully. They are a
    DESIRED treatment, not a grey-cloud snooze; the dullness rule must not condemn
    them for not looking like a photo."""
    if beat.get("mode") == "designed_2d" or beat.get("flat"):
        return True
    return str(beat.get("mode", "")).startswith("flat")


# a designed card only ACTUALLY reads dull if the picture literally sits still —
# these are the flags that mean "not animating," as opposed to "not photographic".
STATIC_FLAGS = {"LOW_MOTION", "STILL_WHEN_MOTION_EXISTS", "LONG_HOLD"}


def dull_beats(interest: dict, cool: list[dict],
               beats: list[dict] | None = None) -> list[dict]:
    """Return the cool rows that are dull, each with a WHY and a fix KIND.
    A DESIGNED motion-graphic is dull only if it is genuinely static (STATIC_FLAGS)
    — never for low photographic appeal — and its fix is `animate`, never footage.
    A footage/photo beat is dull on low appeal or a dead stretch; its fix is
    `motion`."""
    boring = interest.get("boring_stretches", [])
    beats = beats or []
    out = []
    for r in cool:
        job = str(r.get("job", "")).upper()
        appeal = r.get("appeal", 1.0)
        suspects = set(r.get("suspect", []))
        bi = r.get("beat")
        designed = _is_designed(beats[bi]) if isinstance(bi, int) and \
            bi < len(beats) else False
        why, kind = None, "motion"
        if "HOOK" in job and appeal >= 0.72:
            continue                                  # a bright hook may hold
        if designed:
            # a clean graphic is dull ONLY if it isn't moving; polish (animate)
            # it — do NOT replace the explainer the viewer needs with footage.
            if suspects & STATIC_FLAGS:
                why, kind = "static designed card (" + "+".join(
                    sorted(suspects & STATIC_FLAGS)) + ")", "animate"
        elif appeal < DULL_APPEAL:
            why = f"appeal {appeal} < {DULL_APPEAL}"
        elif suspects & DULL_FLAGS:
            why = "+".join(sorted(suspects & DULL_FLAGS))
        elif _in_boring(r.get("t", ""), boring) and appeal < SOFT_APPEAL:
            why = f"dead stretch, appeal {appeal}"
        if why:
            out.append({"beat": bi, "job": job, "why": why, "kind": kind})
    return out


def _subject(beat: dict) -> str:
    """A REAL subject to search motion for — declared by the author, never a
    keyword-salad guessed from prose (that just fetches off-topic junk). A beat
    with no declared subject cannot be auto-escalated to footage; the director
    reports it instead of shipping a bad clip."""
    for q in (beat.get("motion_query"), beat.get("subject"),
              (beat.get("image") or {}).get("query"),
              (beat.get("footage") or {}).get("query"),
              (beat.get("footage") or {}).get("intent")):
        if q and len(str(q).split()) >= 2:
            return str(q)
    return ""


def _beat_sig(render: Path, t: str):
    """A small perceptual signature of a beat — the mid-beat frame downscaled to
    12x12 grayscale. Two beats that LOOK alike (five Earth-from-orbit clips) have
    near-identical signatures no matter what their subject labels say."""
    import subprocess
    import numpy as np
    from io import BytesIO
    from PIL import Image
    try:
        a, z = (float(x) for x in str(t).split("-"))
        mid = (a + z) / 2.0
    except (ValueError, IndexError):
        mid = 1.0
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{mid:.2f}", "-i",
                        str(render), "-frames:v", "1", "-f", "image2pipe",
                        "-vcodec", "png", "-"], capture_output=True)
    if not r.stdout:
        return None
    im = Image.open(BytesIO(r.stdout)).resize((12, 12)).convert("L")
    return np.asarray(im, dtype="float32")


# subject FAMILIES — the coarse "what am I looking at" bucket. Five different
# Earth-from-orbit clips are five members of one family; that is the monotony the
# owner means by "a bunch of cloud videos," not pixel-identical frames.
_FAMILIES = {
    "earth_space": ("earth", "orbit", "space station", "iss", "planet",
                    "continent", "city lights", "aurora", "night surface",
                    "atmosphere", "limb", "globe"),
    "sky_clouds": ("cloud", "sky", "sunrise", "sunset", "haze", "horizon"),
    "sun": ("sun", "solar", "sunspot", "corona", "flare"),
    "sea": ("ocean", "sea", "wave", "water", "coast"),
    "storm": ("hurricane", "storm", "cyclone", "typhoon"),
}


def _family(beat: dict) -> str:
    """Which coarse subject family a beat's footage/subject belongs to."""
    txt = " ".join(str(x) for x in (
        beat.get("subject", ""), (beat.get("footage") or {}).get("intent", ""),
        (beat.get("footage") or {}).get("query", ""),
        (beat.get("image") or {}).get("query", ""))).lower()
    for fam, keys in _FAMILIES.items():
        if any(k in txt for k in keys):
            return fam
    return ""


def variety_check(beats: list, beatmap: Path, render: Path,
                  sim_thresh: float = 7.0, family_cap: int = 2) -> list[int]:
    """The '5 clouds' catch. The cool judge grades each beat ALONE, so a reel of
    space clips passes — each one moves. This looks ACROSS beats two ways:
      1. SUBJECT FAMILY: > family_cap footage beats in the same family (all Earth,
         all sky) is monotony — the primary, label-based signal.
      2. PERCEPTUAL: near-identical mid-beat frames (a backstop for un-labelled
         look-alikes).
    Returns the EXCESS beat indices (keep the first `family_cap` of each group,
    diversify the rest). Designed cards are exempt — variety across footage is the
    point; more designed graphics is the cure, not the disease."""
    import numpy as np
    try:
        bm = json.loads(Path(beatmap).read_text())
        rows = bm if isinstance(bm, list) else bm.get("beats", [])
    except Exception:
        return []
    # the HOOK and the PAYOFF are the bookends — the opening and its return-to-
    # opening callback. They carry the footage on purpose; never convert them.
    bookend = {"HOOK", "PAYOFF", "ENDING", "COLD_OPEN"}
    excess = set()
    # 1. subject-family monotony (footage beats only; designed cards don't count)
    seen: dict[str, int] = {}
    for i in range(min(len(beats), len(rows))):
        if _is_designed(beats[i]) or beats[i].get("_prefer_designed"):
            continue
        fam = _family(beats[i])
        if not fam:
            continue
        seen[fam] = seen.get(fam, 0) + 1               # bookends still COUNT ...
        if seen[fam] > family_cap and \
                str(beats[i].get("job", "")).upper() not in bookend:
            excess.add(i)                              # ... but are never converted
    # 2. perceptual backstop for look-alikes the labels missed
    sigs = [(_beat_sig(render, r.get("t", "")), i) for i, r in enumerate(rows)
            if not (_is_designed(beats[i]) if i < len(beats) else False)]
    sigs = [(s, i) for s, i in sigs if s is not None]
    used = set()
    for a in range(len(sigs)):
        if sigs[a][1] in used:
            continue
        cluster = [sigs[a][1]]
        for b in range(a + 1, len(sigs)):
            if sigs[b][1] not in used and \
                    float(np.abs(sigs[a][0] - sigs[b][0]).mean()) < sim_thresh:
                cluster.append(sigs[b][1])
        if len(cluster) >= 3:
            used.update(cluster)
            excess.update(j for j in sorted(cluster)[2:]
                          if str(beats[j].get("job", "")).upper() not in bookend)
    return sorted(excess)


# a ground / human-scale SUBJECT named in the narration must not play over Earth-
# from-orbit — the "talking about Usain Bolt over a picture of the planet" bug.
_GROUND_SUBJECTS = ("sprinter", "usain", "bolt", "runner", "car", "jet", "plane",
                    "bus", "person", "people", "athlete", "cheetah", "train",
                    "motorcycle", "highway", "crowd", "stadium", "street")
_SPACE_FAMS = {"earth_space", "sun"}
# comparison / relation clauses — a subject named HERE is a yardstick, not the
# beat's topic ("faster THAN a bullet", "AROUND the sun"). Strip before judging.
_COMPARE_RE = re.compile(
    r"\b(than|like|as fast as|compared to|around the|orbit\w*|beyond)\b[^.,;]*",
    re.I)


def pacing_check(beats: list) -> list[dict]:
    """The pacing / sync director. Catches the beat whose PICTURE doesn't match the
    WORDS under it: narration whose SUBJECT is a sprinter/jet playing over Earth-
    from-orbit. Conservative on purpose — a subject named inside a comparison
    ('faster than a bullet') or a relation ('around the Sun') is a yardstick, not
    the topic, so those clauses are stripped first (they were false positives that
    would wrongly convert a correct Earth-spin beat). A designed card always
    illustrates the words, so it is exempt. The definitive 'does the picture match'
    call is the vision judge; this is the cheap, high-precision pre-screen."""
    out = []
    for i, b in enumerate(beats):
        if _is_designed(b) or b.get("_prefer_designed"):
            continue
        fam = _family(b)
        if fam not in _SPACE_FAMS:         # only the space-over-ground case here
            continue
        narr = _COMPARE_RE.sub("", str(b.get("narration", "")).lower())
        hits = [k for k in _GROUND_SUBJECTS if re.search(rf"\b{k}\b", narr)]
        if hits:
            out.append({"beat": i, "job": str(b.get("job", "")).upper(),
                        "why": f"narration subject is {hits[0]!r} (ground/human) "
                        f"but the visual is {fam} — wrong picture for the words"})
    return out


def _hook_gate(beats: list, beatmap: Path, render: Path):
    """Grade the opening with the hook director (metric pre-screen). Uses the
    hook beat's true duration so the sustained-motion / HELD_STATIC check spans
    the whole hook, not just the first frames."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import hook_director
    except Exception:
        return None
    line = str(beats[0].get("narration", "")).split(".")[0]
    secs = 6.0
    try:
        bm = json.loads(Path(beatmap).read_text())
        b0 = bm[0] if isinstance(bm, list) else bm.get("beats", [{}])[0]
        a, b = str(b0.get("t", "0-6")).split("-")
        secs = max(2.0, float(b) - float(a))
    except Exception:
        pass
    try:
        return hook_director.grade(line, Path(render), hook_seconds=secs)
    except Exception:
        return None


def _gate_report(verdict: str, hv, interest, dull, escalated, beats,
                 excess=None) -> None:
    """The DIRECTOR's ordered scorecard — proves every gate RAN, in order of
    importance, and shows what each did (passed / fixed / stuck). No gate can be
    silently skipped: if it isn't on this list, it wasn't run."""
    print("\n=== DIRECTOR — gate report (order of importance) ===")
    # 1. HOOK (the opening decides retention — nothing matters more)
    if hv is None:
        print(" 1. HOOK       : (not graded)")
    elif hv["pass"]:
        print(f" 1. HOOK       : PASS ({hv['total']}/10)"
              + ("  [fixed: opened on motion]" if 0 in escalated else ""))
    else:
        print(f" 1. HOOK       : WEAK ({hv['total']}/10) "
              f"visual_gates={hv['visual'].get('gates')} "
              f"line_gates={hv['line'].get('gates')}")
    # 2. DEAD-TIME / DULL beats (interest + cool)
    nd = len(dull) if dull is not None else "?"
    if interest:
        print(f" 2. DEAD-TIME  : dead={interest.get('dead_fraction')} "
              f"appeal={interest.get('mean_appeal')} — {nd} dull beat(s) remain")
    for d in (dull or []):
        print(f"      · beat {d['beat']} {d['job']}: {d['why']}")
    # 3. FIXES the director applied this run
    fixed = sorted(i for i in escalated if beats[i].get("_force_motion"))
    print(f" 3. FIXES      : {len(fixed)} beat(s) escalated to motion: {fixed}"
          if fixed else " 3. FIXES      : none needed")
    # 3b. VARIETY (the 5-clouds catch) + designed-animation count
    designed = sorted(i for i, b in enumerate(beats)
                      if _is_designed(b) or b.get("_prefer_designed"))
    ex = excess or []
    print(f" 3b. VARIETY   : {len(ex)} look-alike beat(s) remain {ex}; "
          f"{len(designed)} designed animation(s): {designed}")
    mism = pacing_check(beats)
    sync_msg = ("all visuals match their narration" if not mism
                else f"{len(mism)} mismatch(es): {[m['beat'] for m in mism]}")
    print(f" 3c. SYNC      : {sync_msg}")
    print(f" VERDICT: {verdict}")
    print("   (cool/visual TASTE verdicts are the vision judges' call — the "
          "orchestrator spawns them; this loop runs the metric pre-screens.)")


def _record_memory(slug: str, work: Path, rnd: int, stderr: str) -> None:
    """Feed this render's verdicts into the showrunner memory so lessons compound
    (ledger.jsonl -> rules.json). Best-effort: never fail the run over telemetry."""
    jd = work / f"judge_r{rnd}"
    if not (jd / "interest").exists():
        return
    log = work / f"render_r{rnd}.log"
    try:
        log.write_text(stderr or "")
        _run([sys.executable, "-m", "data_learning.showrunner", "record",
              "--slug", slug, "--label", "director",
              "--interest", str(jd / "interest"), "--cool", str(jd / "cool"),
              "--log", str(log)])
    except Exception as e:  # noqa: BLE001
        print(f"[ndb] memory record skipped ({str(e)[:50]})")


def run(story_path: Path, out: Path, rounds: int = 3) -> int:
    story = json.loads(story_path.read_text())
    beats = story["beats"]
    work = out.parent / f"{out.stem}_ndb_work"
    escalated: set[int] = set()
    for rnd in range(1, rounds + 1):
        tmp_story = work / f"story_r{rnd}.json"
        work.mkdir(parents=True, exist_ok=True)
        tmp_story.write_text(json.dumps(story))
        print(f"\n=== NO-DULL-BEATS round {rnd} — render ===")
        proc = _run([sys.executable, "-m", "data_learning.pro_render",
                     str(tmp_story), str(out), "--work", str(work)],
                    capture_output=True, text=True)
        # REVERT-ON-MISS: any beat we escalated whose motion probe FELL BACK to a
        # still keeps a designed card that had motion — reverting is a repair, a
        # dead still is a downgrade. Restore its original treatment.
        _, missed = _motion_outcomes(proc.stderr or "")
        reverted = 0
        for i in list(escalated):
            if (i < len(beats) and beats[i].get("_force_motion")
                    and beats[i].get("subject", "") in missed):
                beats[i].pop("_force_motion", None)
                reverted += 1
                print(f"[ndb] revert beat {i}: no dynamic clip for "
                      f"{beats[i].get('subject')!r} — keeping its designed card")
        if reverted:                        # a revert changed the story: re-render
            continue
        beatmap = out.parent / f"{out.stem}_pkg" / "beatmap.json"
        # HOOK GATE — the opening is the whole ballgame. Grade it EVERY round and
        # never let a weak hook ship silently. (This judge existed but was never
        # wired into the loop — the reason a 10s calm Earth open reached preview.)
        hv = _hook_gate(beats, beatmap, out)
        if hv and not hv["pass"]:
            vg = set(hv["visual"].get("gates", []))
            print(f"[ndb] HOOK WEAK ({hv['total']}/10) visual={hv['visual']} "
                  f"line_gates={hv['line'].get('gates')}")
            if vg and 0 not in escalated and _subject(beats[0]):
                beats[0]["_force_motion"] = True
                beats[0]["subject"] = _subject(beats[0])
                escalated.add(0)
                print(f"[ndb] escalate HOOK (beat 0) -> dynamic motion of "
                      f"{beats[0]['subject']!r} ({'+'.join(sorted(vg))})")
                continue                # re-render with a moving hook, then re-grade
            if not vg:                  # visual ok but LINE weak — author must fix
                print(f"[ndb] HOOK LINE weak {hv['line'].get('gates')} — needs a "
                      "re-authored opening line (cannot auto-fix a line).")
        # PACING / SYNC GATE — the picture must match the words under it. A beat
        # narrating a sprinter over Earth-from-orbit is fixed by making it the
        # designed explainer that actually illustrates the words.
        synced = 0
        for m in pacing_check(beats):
            i = m["beat"]
            if not beats[i].get("_prefer_designed") and (
                    (beats[i].get("number") or {}).get("text")
                    or beats[i].get("text") or beats[i].get("flat")):
                beats[i]["_prefer_designed"] = True
                beats[i].pop("_force_motion", None)
                synced += 1
                print(f"[ndb] SYNC: beat {i} {m['why']} -> designed explainer")
            else:
                print(f"[ndb] SYNC (report only): beat {i} {m['why']}")
        if synced:
            continue                       # re-render with the visuals matched to VO
        # VARIETY GATE — the '5 clouds' catch. Look ACROSS beats for a cluster
        # that all look alike; convert the excess (numbered) beats to designed
        # number cards so the video isn't a reel of near-identical clips.
        excess = variety_check(beats, beatmap, out)
        diversified = 0
        for i in excess:
            if (i < len(beats) and not beats[i].get("_prefer_designed")
                    and not _is_designed(beats[i])
                    and ((beats[i].get("number") or {}).get("text")
                         or beats[i].get("text"))):
                beats[i]["_prefer_designed"] = True
                beats[i].pop("_force_motion", None)   # designed beats aren't footage
                diversified += 1
                print(f"[ndb] VARIETY: beat {i} looks like earlier beats — "
                      "converting to a designed number card (breaks the monotony)")
        if excess:
            print(f"[ndb] variety: {len(excess)} look-alike beat(s) {excess}; "
                  f"diversified {diversified}")
        if diversified:
            continue                       # re-render with the monotony broken up
        interest, cool = _judge(out, beatmap, work / f"judge_r{rnd}")
        dull = dull_beats(interest, cool, beats)
        print(f"[ndb] round {rnd}: dead={interest.get('dead_fraction')} "
              f"appeal={interest.get('mean_appeal')} — {len(dull)} dull beat(s)")
        for d in dull:
            print(f"      beat {d['beat']} {d['job']}: {d['why']} [fix={d['kind']}]")
        if not dull and (not hv or hv["pass"]):
            _record_memory(story_path.stem, work, rnd, proc.stderr or "")
            _gate_report("CLEAN — hook passes, no dull beats", hv, interest,
                         dull, escalated, beats, excess=excess)
            return 0
        # fix each dull beat we haven't already handled — by the RIGHT method:
        #  designed card (kind=animate) -> make it more fluid, NEVER footage
        #  footage/photo   (kind=motion) -> escalate to motion of its subject
        progressed = False
        for d in dull:
            i = d["beat"]
            if i in escalated or not isinstance(i, int) or i >= len(beats):
                continue
            if d.get("kind") == "animate":
                if not beats[i].get("_animate_more"):
                    beats[i]["_animate_more"] = True   # boost the card's motion
                    escalated.add(i)
                    progressed = True
                    print(f"[ndb] animate beat {i}: designed card too static — "
                          "boosting its motion (keeping the graphic, NOT footage)")
                continue
            subj = _subject(beats[i])
            if not subj:
                continue
            beats[i]["_force_motion"] = True
            beats[i]["subject"] = subj
            escalated.add(i)
            progressed = True
            print(f"[ndb] escalate beat {i} -> motion of {subj!r}")
        if not progressed:
            _record_memory(story_path.stem, work, rnd, proc.stderr or "")
            _gate_report("STUCK — unfixable flags remain (likely stock/motion "
                         "access-gated). Reported, not hidden.",
                         hv, interest, dull, escalated, beats, excess=excess)
            return 2
    _record_memory(story_path.stem, work, rnd, proc.stderr or "")
    _gate_report(f"ROUND-LIMIT ({rounds}) — some beats may remain dull",
                 hv, interest, dull, escalated, beats, excess=excess)
    return 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("story", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--rounds", type=int, default=3)
    a = ap.parse_args(argv)
    return run(a.story, a.out, a.rounds)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
