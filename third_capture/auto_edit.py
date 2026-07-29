#!/usr/bin/env python3
"""Auto-editor: turn a cut Twitch clip into a dynamically edited program.

This is Stage 1 of the two-stage clip render (see clip_edit.edit). From the
cut clip + whisper word timings it:
  1. analyzes motion energy (tblend, via gameplay_scanner) + speech density
     to locate the "money moment",
  2. picks a per-clip STYLE from the series label (discretion — not every
     effect on every clip),
  3. builds an Edit Decision List (segments: punch-in zoom, dead-air
     speed-up, slow-mo money moment, instant replay, impact shake/flash),
  4. renders each segment and concats them into program.mp4,
  5. mixes CC0 impact SFX onto the effect beats,
  6. remaps the word timings onto the edited timeline for captions.

IRONCLAD DOCTRINE: nothing here raises to the caller. Every effect, every
segment, and the whole stage degrade gracefully — worst case `build()`
returns the untouched cut so the simple render still ships. All fallbacks
are recorded in the returned ledger.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SFX_DIR = REPO / "assets" / "sfx"
MODELS_DIR = REPO / "assets" / "models"
CANVAS_W, CANVAS_H = 1080, 1920
FPS = 30
_SEG_TIMEOUT = 120          # per-segment encode ceiling
_MINTERP_TIMEOUT = 180      # slow-mo is the one heavy op


def _run(cmd: list[str], timeout: int = _SEG_TIMEOUT) -> str:
    return subprocess.check_output(cmd, text=True,
                                   stderr=subprocess.STDOUT, timeout=timeout)


def _probe_wh(path: Path) -> tuple[int, int]:
    out = _run(["ffprobe", "-v", "quiet", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0",
                str(path)], timeout=30)
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


# ---------------------------------------------------------------- analysis

def motion_energy(cut: Path, fps: float = 8.0) -> list[tuple[float, float]]:
    """(t, energy) frame-diff motion samples via the existing tblend scorer."""
    try:
        import gameplay_scanner as gs
        rows = gs._scan(cut, scan_mode="full", fps=fps)
        return [(t, yavg) for (t, yavg, _ymax, _yr) in rows]
    except Exception:  # noqa: BLE001
        return []


def _norm(vals: list[float]) -> list[float]:
    if not vals:
        return []
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-6:
        return [0.0] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


def speech_curve(words: list[dict], dur: float, step: float = 0.25) -> \
        list[tuple[float, float]]:
    """Speech intensity sampled every `step`s: word density + '!/?' & shout
    bonus, over a 1.5s window."""
    n = max(1, int(dur / step))
    out = []
    for i in range(n):
        t = i * step
        score = 0.0
        for w in words:
            mid = (w["s"] + w["e"]) / 2
            if abs(mid - t) <= 0.75:
                tok = w["w"].strip()
                score += 1.0
                if tok[-1:] in "!?":
                    score += 1.2
                if len(tok) >= 6 and tok.isupper():
                    score += 0.6
        out.append((t, score))
    return out


def money_moment(motion, speech, dur) -> tuple[float, float, float]:
    """Fuse normalized motion+speech, return (t_peak, win_start, win_end)."""
    grid_step = 0.25
    n = max(1, int(dur / grid_step))
    m = _resample(motion, n, grid_step)
    s = _resample(speech, n, grid_step)
    mn, sn = _norm(m), _norm(s)
    fused = [0.6 * a + 0.4 * b for a, b in zip(mn, sn)]
    if not fused:
        return dur * 0.6, dur * 0.5, min(dur, dur * 0.5 + 2.0)
    peak_i = max(range(len(fused)), key=lambda i: fused[i])
    t_peak = peak_i * grid_step
    thresh = 0.55 * fused[peak_i]
    lo = hi = peak_i
    while lo > 0 and fused[lo - 1] >= thresh:
        lo -= 1
    while hi < len(fused) - 1 and fused[hi + 1] >= thresh:
        hi += 1
    ws, we = lo * grid_step, (hi + 1) * grid_step
    # clamp window to [1.2, 4.0]s around the peak
    we = max(we, ws + 1.2)
    if we - ws > 4.0:
        ws = max(0.0, t_peak - 2.0)
        we = min(dur, ws + 4.0)
    return t_peak, max(0.0, ws), min(dur, we)


def energy_peaks(motion, speech, dur, n: int = 3,
                 min_gap: float = 2.5) -> list[tuple[float, float, float]]:
    """Top-`n` well-separated (t_peak, ws, we) energy peaks, chronological.
    Generalizes `money_moment` for the montage "edit" arm: same fused
    motion+speech curve, but greedily picks several non-overlapping peaks
    (each suppresses a ±`min_gap`s window) so the edit can cut+hit on more
    than one moment. Empty/flat clip → []. Pure function (unit-tested)."""
    grid_step = 0.25
    ncells = max(1, int(dur / grid_step))
    m = _resample(motion, ncells, grid_step)
    s = _resample(speech, ncells, grid_step)
    mn, sn = _norm(m), _norm(s)
    fused = [0.6 * a + 0.4 * b for a, b in zip(mn, sn)]
    if not fused:
        return []
    gap = max(1, int(min_gap / grid_step))
    taken = [False] * len(fused)
    peaks: list[tuple[float, float, float]] = []
    for i in sorted(range(len(fused)), key=lambda i: -fused[i]):
        if len(peaks) >= n:
            break
        if taken[i] or fused[i] <= 0.0:
            continue
        for j in range(max(0, i - gap), min(len(fused), i + gap + 1)):
            taken[j] = True
        t_peak = i * grid_step
        thresh = 0.55 * fused[i]
        lo = hi = i
        while lo > 0 and fused[lo - 1] >= thresh:
            lo -= 1
        while hi < len(fused) - 1 and fused[hi + 1] >= thresh:
            hi += 1
        ws, we = lo * grid_step, (hi + 1) * grid_step
        we = max(we, ws + 0.8)
        if we - ws > 3.0:
            ws = max(0.0, t_peak - 1.5)
            we = min(dur, ws + 3.0)
        peaks.append((t_peak, max(0.0, ws), min(dur, we)))
    return sorted(peaks, key=lambda p: p[0])


def _resample(samples: list[tuple[float, float]], n: int, step: float) -> \
        list[float]:
    """Nearest-value resample of (t,v) onto an n-point grid of spacing step."""
    if not samples:
        return [0.0] * n
    out, j = [], 0
    for i in range(n):
        t = i * step
        while j + 1 < len(samples) and samples[j + 1][0] <= t:
            j += 1
        out.append(samples[j][1])
    return out


def dead_air(words, dur, gap=1.4) -> list[tuple[float, float]]:
    """Speech gaps > `gap`s → candidate speed-up ranges (trimmed 0.2s each
    side so we don't clip a word)."""
    if not words:
        return []
    ranges, prev_e = [], 0.0
    for w in sorted(words, key=lambda w: w["s"]):
        if w["s"] - prev_e > gap:
            ranges.append((prev_e + 0.2, w["s"] - 0.2))
        prev_e = max(prev_e, w["e"])
    if dur - prev_e > gap:
        ranges.append((prev_e + 0.2, dur))
    return [(a, b) for a, b in ranges if b - a > 0.6]


# ---------------------------------------------------------------- style

# series -> reaction emoji asset (assets/emoji/<name>.png) popped on the
# money moment by the overlay layer. Unknown series fall to mindblown.
SERIES_EMOJI = {
    "fail": "skull", "rage": "rage", "jumpscare": "scream",
    "clutch": "fire", "win": "fire", "wholesome": "pleading",
    "argument": "eyes", "chat-betrayal": "eyes", "funny": "joy",
    "chaos": "mindblown", "drama": "eyes", "beef": "rage",
}

# series -> big word that SLAMS on screen at the money moment (generic hype
# exclamations — always safe, never invents a claim about the clip).
SERIES_WORD = {
    "fail": "BROOO", "rage": "NO WAY", "jumpscare": "AHHH",
    "clutch": "INSANE", "win": "LETS GO", "wholesome": "AWW",
    "argument": "OHHH", "chat-betrayal": "SNAKE", "funny": "LMAOO",
    "chaos": "WAIT", "drama": "OHHH", "beef": "NAHH",
}


@dataclass
class Style:
    punch: bool = True          # gentle zoom-in on the reaction beat
    slowmo: bool = True         # slow the money moment (time effect, not camera)
    replay: bool = True         # instant replay of the money moment
    shake: bool = True          # brief impact hit on the peak (kept subtle)
    speedup_dead: bool = True   # compress dead air
    sfx: bool = True
    zoom_to: float = 1.08
    slow_speed: float = 0.5
    shake_intensity: float = 0.35
    # --- montage "edit" arm (A/B): only consulted when edit_mode is True.
    # Purely additive — default False leaves every existing clip untouched.
    edit_mode: bool = False     # punch+hit on MULTIPLE peaks, graded, snappy
    edit_pace: float = 1.22     # connective-tissue speed-up (montage feel)
    grade: str = ""             # global color-grade filter string (edit look)


def choose_style(series: str, dur: float, peak_strength: float,
                 calm: bool = False) -> Style:
    """Discretion: pick effects that fit the clip. `series` is the author's
    label (rage/fail/clutch/win/wholesome/argument/jumpscare/chaos).

    Camera moves are deliberately gentle — the operator wants the footage to
    mostly hold still and the energy to live in the overlay effect layer
    (emoji pops, emphasis hits). Punch/shake are brief emphasis on the peak,
    never a constant push; the time effects (slow-mo, replay, dead-air) carry
    the pacing."""
    s = (series or "chaos").lower()
    st = Style()
    if s in ("wholesome",):
        st.shake = False
        st.slowmo = True
        st.replay = False
        st.zoom_to = 1.06
        st.shake_intensity = 0.0
    elif s in ("argument", "chat-betrayal"):
        st.slowmo = False           # keep the back-and-forth snappy
        st.replay = False
        st.shake_intensity = 0.25
    elif s in ("fail", "rage", "jumpscare"):
        st.zoom_to = 1.12
        st.shake_intensity = 0.5
        st.slow_speed = 0.45
    elif s in ("clutch", "win"):
        st.zoom_to = 1.10
        st.shake_intensity = 0.4
    # weak/flat clips: minimal — barely any camera move at all
    if peak_strength < 0.25:
        st.slowmo = st.replay = st.shake = False
        st.zoom_to = min(st.zoom_to, 1.04)
    # very short clips can't spare a replay
    if dur < 8.0:
        st.replay = False
    # CALM MODE — chaotic / no-stable-subject footage (IRL, party, crowd).
    # Slow-mo blend smears on fast unanchored motion, replay + impact make it
    # worse, and a punch-in on a wide crowd frame lands on nothing. Kill every
    # time/camera effect and let the clip play straight (captions + overlays
    # still carry it). This is the fix for the IRL QA-rejects.
    if calm:
        st.slowmo = st.replay = st.shake = False
        st.zoom_to = 1.0
    return st


# ---------------------------------------------------------------- EDL

@dataclass
class Segment:
    src_s: float
    src_e: float
    speed: float = 1.0          # >1 faster (dead air), <1 slow-mo
    kind: str = "normal"        # normal|deadair|punch|money|replay
    zoom_to: float = 1.0        # 1.0 = no zoom
    minterp: bool = False
    impact_t: float | None = None   # rel time in the OUTPUT segment for the hit
    stamp: str = ""
    mute: bool = False
    grade: str = ""             # optional per-segment color-grade filter (edit)
    trans_in: bool = False      # punch-cut flourish at the head (edit arm)

    def out_dur(self) -> float:
        return (self.src_e - self.src_s) / self.speed


@dataclass
class EDL:
    src_dur: float
    t_peak: float
    money: tuple[float, float]
    style: Style
    segments: list[Segment] = field(default_factory=list)
    sfx_cues: list[tuple[float, str]] = field(default_factory=list)  # (out_t, name)

    def out_dur(self) -> float:
        return sum(s.out_dur() for s in self.segments)


def build_edl(words, dur, style: Style, motion) -> EDL:
    """Assemble the chronological segment timeline + SFX cues."""
    speech = speech_curve(words, dur)
    t_peak, ws, we = money_moment(motion, speech, dur)
    dead = dead_air(words, dur) if style.speedup_dead else []

    # reaction beat for the punch: strongest speech point BEFORE the money win
    punch_t = None
    if style.punch:
        pre = [(t, v) for (t, v) in speech if t < ws - 0.3]
        if pre:
            punch_t = max(pre, key=lambda x: x[1])[0]

    # Build boundary list, then walk left→right emitting typed segments.
    edl = EDL(src_dur=dur, t_peak=t_peak, money=(ws, we), style=style)

    def is_dead(a, b):
        return any(a >= d0 - 0.05 and b <= d1 + 0.05 for d0, d1 in dead)

    # cut points: money window edges, punch window, dead-air edges
    cuts = {0.0, dur, ws, we}
    for d0, d1 in dead:
        cuts.add(max(0.0, d0)); cuts.add(min(dur, d1))
    if punch_t is not None:
        cuts.add(max(0.0, punch_t - 0.3)); cuts.add(min(dur, punch_t + 1.0))
    bounds = sorted(b for b in cuts if 0.0 <= b <= dur)
    out_t = 0.0
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 0.15:
            continue
        seg = Segment(src_s=a, src_e=b)
        in_money = a >= ws - 0.05 and b <= we + 0.05
        in_punch = (punch_t is not None
                    and a >= punch_t - 0.35 and b <= punch_t + 1.05)
        # the hit lands only on the sub-segment that actually contains t_peak
        has_peak = a <= t_peak < b
        if in_money and style.slowmo:
            seg.kind = "money"
            seg.speed = style.slow_speed
            seg.minterp = True
            # DO NOT mute — muting the slow-mo dropped the payoff audio right
            # as the overlays land ("sound cuts off"). Keep it and time-stretch
            # (atempo) so the moment is heard, slowed, not silenced.
            seg.mute = False
            if has_peak and style.shake and style.shake_intensity > 0:
                seg.impact_t = max(0.0, (t_peak - a) / seg.speed)
                edl.sfx_cues.append((out_t + seg.impact_t, "boom"))
        elif in_money:
            seg.kind = "money"
            if has_peak and style.shake and style.shake_intensity > 0:
                seg.impact_t = max(0.0, t_peak - a)
                edl.sfx_cues.append((out_t + seg.impact_t, "boom"))
        elif in_punch:
            seg.kind = "punch"
            seg.zoom_to = style.zoom_to
            if style.sfx:
                edl.sfx_cues.append((out_t, "whoosh"))
        elif is_dead(a, b):
            seg.kind = "deadair"
            seg.speed = 1.8
        edl.segments.append(seg)
        out_t += seg.out_dur()

    # instant replay: clone the money window, slower + stamped. Keep its audio
    # (time-stretched) so the moment is heard again rather than going silent —
    # a whoosh marks the cut into it instead of a riser under the dialogue.
    if style.replay:
        rs = Segment(src_s=ws, src_e=we, speed=min(style.slow_speed, 0.55),
                     kind="replay", minterp=True, mute=False, stamp="REPLAY")
        edl.segments.append(rs)
        if style.sfx:
            edl.sfx_cues.append((out_t, "whoosh"))

    # keep edits tight: if slow-mo + replay overran, drop the replay first,
    # then ease the slow-mo toward real time until under the cap.
    max_out = 52.0
    if edl.out_dur() > max_out and any(s.kind == "replay" for s in edl.segments):
        edl.segments = [s for s in edl.segments if s.kind != "replay"]
        edl.sfx_cues = [c for c in edl.sfx_cues if c[1] != "riser"]
    if edl.out_dur() > max_out:
        for s in edl.segments:
            if s.speed < 1.0:
                s.speed = min(1.0, s.speed + 0.2)
    return edl


# Cinematic "designed" grade for the montage "edit" look — the part of the
# edit arm that lands even on chaotic/no-subject footage (it needs no stable
# subject, so calm mode keeps it while dropping the punch/shake). Lifted
# contrast + saturation, a warm lift, fine film grain, and a soft vignette to
# frame the subject and give the flat stream capture a graded, intentional
# feel. All cheap, headless, commercial-safe (no LUT asset). The `unsharp`
# pass was dropped — it was the expensive filter behind the slow batch, and
# grain+vignette carry the look better. Applied to every segment in edit mode
# only; the default clip arm is never graded (keeps the A/B a clean control).
EDIT_GRADE = ("eq=contrast=1.12:saturation=1.30:brightness=0.010:gamma_r=1.03,"
              "noise=alls=7:allf=t,vignette=PI/4.2")


def build_edl_edit(words, dur, style: Style, motion) -> EDL:
    """Montage "edit" EDL (the A/B experiment arm). Cuts + a punch-zoom +
    impact hit (RGB-split/flash/shake — the proven `impact` render path) on
    EACH of the top energy peaks, connective tissue sped up for pace, and a
    global color grade. Snappy: no slow-mo, no replay. Purely additive — only
    reached when style.edit_mode; the default `build_edl` is never touched."""
    speech = speech_curve(words, dur)
    npeaks = 4 if dur >= 24 else (3 if dur >= 14 else 2)
    peaks = energy_peaks(motion, speech, dur, n=npeaks, min_gap=2.5)
    dead = dead_air(words, dur) if style.speedup_dead else []
    t0 = peaks[0][0] if peaks else dur * 0.5
    money0 = (peaks[0][1], peaks[0][2]) if peaks else (0.0, min(dur, 2.0))
    edl = EDL(src_dur=dur, t_peak=t0, money=money0, style=style)

    def is_dead(a, b):
        return any(a >= d0 - 0.05 and b <= d1 + 0.05 for d0, d1 in dead)

    # Boundaries: a tight hit window [peak-0.25, peak+0.9] and a short punch
    # lead-in [peak-1.1, peak-0.25] per peak (keeps the shake brief, exactly
    # like the tested single-peak path), plus dead-air edges.
    cuts = {0.0, dur}
    for tp, ws, we in peaks:
        cuts.add(max(0.0, tp - 1.1))
        cuts.add(max(0.0, tp - 0.25))
        cuts.add(min(dur, tp + 0.9))
    for d0, d1 in dead:
        cuts.add(max(0.0, d0)); cuts.add(min(dur, d1))
    bounds = sorted(b for b in cuts if 0.0 <= b <= dur)
    peak_ts = [p[0] for p in peaks]
    out_t = 0.0
    first_emitted = False
    for a, b in zip(bounds, bounds[1:]):
        if b - a < 0.15:
            continue
        seg = Segment(src_s=a, src_e=b, grade=style.grade)
        # PUNCH-CUT transition on every cut except the opening — the flash +
        # chromatic hit that makes a jump cut read as a deliberate edit. A
        # whoosh rides each one so the cut is heard as well as seen.
        if first_emitted:
            seg.trans_in = True
            if style.sfx:
                edl.sfx_cues.append((out_t, "whoosh"))
        first_emitted = True
        has_hit = next((tp for tp in peak_ts if a - 0.05 <= tp < b), None)
        in_leadin = any(tp - 1.15 <= a and b <= tp - 0.2 for tp in peak_ts)
        if has_hit is not None:
            seg.kind = "money"        # reuse the hit render (impact + zoom)
            seg.zoom_to = style.zoom_to
            if style.shake and style.shake_intensity > 0:
                seg.impact_t = max(0.0, has_hit - a)
                edl.sfx_cues.append((out_t + seg.impact_t, "boom"))
        elif in_leadin:
            seg.kind = "punch"
            seg.zoom_to = style.zoom_to
            if style.sfx:
                edl.sfx_cues.append((out_t, "whoosh"))
        elif is_dead(a, b):
            seg.kind = "deadair"
            seg.speed = 1.9
        else:
            seg.kind = "normal"       # connective tissue — tighten the pace
            seg.speed = style.edit_pace
        edl.segments.append(seg)
        out_t += seg.out_dur()

    # Length cap: ease the connective speed up until under the montage cap.
    max_out = 55.0
    while edl.out_dur() > max_out and any(
            s.kind == "normal" and s.speed < 1.9 for s in edl.segments):
        for s in edl.segments:
            if s.kind == "normal" and s.speed < 1.9:
                s.speed = min(1.9, s.speed + 0.15)
    return edl


def remap_words(words, edl: EDL) -> list[dict]:
    """Rebuild caption timings on the edited timeline. Replay/stamped
    segments contribute no captions."""
    out, out_t = [], 0.0
    for seg in edl.segments:
        if seg.kind != "replay":
            for w in words:
                if seg.src_s <= w["s"] < seg.src_e:
                    ns = out_t + (w["s"] - seg.src_s) / seg.speed
                    ne = out_t + (min(w["e"], seg.src_e) - seg.src_s) / seg.speed
                    out.append({"w": w["w"], "s": ns, "e": ne})
        out_t += seg.out_dur()
    return sorted(out, key=lambda w: w["s"])


# ---------------------------------------------------------------- render

def _atempo_chain(speed: float) -> str:
    """atempo is valid 0.5–2.0; chain factors for extremes."""
    if abs(speed - 1.0) < 1e-3:
        return "anull"
    parts, k = [], speed
    while k > 2.0:
        parts.append("atempo=2.0"); k /= 2.0
    while k < 0.5:
        parts.append("atempo=0.5"); k /= 0.5
    parts.append(f"atempo={k:.4f}")
    return ",".join(parts)


def _render_segment(cut: Path, seg: Segment, wh: tuple[int, int],
                    out: Path) -> Path:
    """Render one segment with its effects. On any failure, fall back to a
    plain re-encode of the source range so the segment always exists."""
    W, H = wh
    try:
        # ---- video filter chain (single linear chain from [0:v] to [v]) ----
        steps = []
        if seg.minterp:
            # mi_mode=BLEND, not mci. Motion-compensated interpolation
            # (mci:aobmc) invents in-between frames from motion vectors and
            # MELTS on real streamer footage (faces, hands, busy scenes) — the
            # "heavily glitched / corrupted-looking motion blur" the vision QA
            # kept rejecting at the replay's end-of-clip time range. blend
            # cross-dissolves adjacent real frames: smooth, and it can never
            # warp geometry. On any failure the ladder still drops to clean
            # setpts (frame-duplication) via _render_plain.
            steps.append("minterpolate=fps=60:mi_mode=blend")
        if seg.zoom_to > 1.001:
            # Animated crop-zoom (NOT zoompan — zoompan's d= multiplies each
            # input frame and balloons a video segment). zt ramps 1→zoom_to
            # across the segment's own time, then we upscale back to WxH.
            rate = (seg.zoom_to - 1) / max(seg.out_dur(), 0.1)
            zt = f"min(1+{rate:.5f}*t\\,{seg.zoom_to})"
            steps.append(
                f"crop='iw/({zt})':'ih/({zt})':"
                f"'(iw-iw/({zt}))/2':'(ih-ih/({zt}))/2',scale={W}:{H}")
        if seg.impact_t is not None:
            it = seg.impact_t
            steps.append(
                f"crop=iw-20:ih-20:'10+6*sin(80*t)':'10+6*cos(80*t)'")
            steps.append(f"scale={W}:{H}")
            steps.append(
                f"rgbashift=rh=6:bh=-6:"
                f"enable='between(t,{it:.2f},{it+0.12:.2f})'")
            steps.append(
                f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.5:t=fill:"
                f"enable='between(t,{it:.2f},{it+0.05:.2f})'")
        if seg.grade:
            # global color grade (edit arm only) — applied last so it colours
            # the composited zoom/impact result uniformly.
            steps.append(seg.grade)
        if seg.trans_in:
            # PUNCH-CUT transition at the segment head (edit arm): a 1-frame
            # white flash + a brief chromatic-aberration (RGB-split) hit on the
            # first ~80ms. These are OVERLAYS (no crop), so they never conflict
            # with the zoom/impact crops on the same segment — the classic
            # "pro editor" hard-cut punch that reads as an intentional edit
            # instead of a raw jump cut. Rendered in the segment's own local
            # time, so concat placement is automatic.
            steps.append(r"rgbashift=rh=6:bh=-6:enable='lt(t,0.08)'")
            steps.append(r"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.30:t=fill:"
                         r"enable='lt(t,0.045)'")
        steps.append(f"setpts=PTS/{seg.speed:.5f}")
        # NB: the segment's stamp (e.g. REPLAY) is deliberately NOT burned
        # here — a source-centered overlay gets cropped away by the Stage-2
        # face-follow reframe. Stage 2 draws it centered in the final 1080
        # frame instead (build() exports the window as `overlays`).
        vchain = "[0:v]" + ",".join(steps) + "[v]"

        cmd = ["ffmpeg", "-y", "-v", "error",
               "-ss", f"{seg.src_s}", "-to", f"{seg.src_e}", "-i", str(cut)]
        if seg.mute:
            # silent track sized to the segment so concat stays a/v aligned
            cmd += ["-f", "lavfi", "-t", f"{seg.out_dur():.3f}",
                    "-i", "anullsrc=r=48000:cl=stereo"]
            fc = vchain
            amap = "1:a"
        else:
            fc = vchain + f";[0:a]{_atempo_chain(seg.speed)}[a]"
            amap = "[a]"
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", amap,
                "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-b:a", "160k",
                "-shortest", str(out)]
        _run(cmd, timeout=_MINTERP_TIMEOUT if seg.minterp else _SEG_TIMEOUT)
        return out
    except Exception:  # noqa: BLE001 — degrade this segment, never fail
        return _render_plain(cut, seg, out)


def _render_plain(cut: Path, seg: Segment, out: Path) -> Path:
    """Bulletproof fallback: plain re-encode of the source range, no effects,
    speed only (via setpts/atempo), always succeeds."""
    fc = f"[0:v]setpts=PTS/{seg.speed:.5f}[v];[0:a]{_atempo_chain(seg.speed)}[a]"
    _run(["ffmpeg", "-y", "-v", "error",
          "-ss", f"{seg.src_s}", "-to", f"{seg.src_e}", "-i", str(cut),
          "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
          "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
          "-crf", "18", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-ar", "48000", "-b:a", "160k", str(out)],
         timeout=_SEG_TIMEOUT)
    return out


def _probe_dur(path: Path) -> float:
    """Actual container duration in seconds, 0.0 on any failure."""
    try:
        return float(_run(["ffprobe", "-v", "error", "-show_entries",
                           "format=duration", "-of", "csv=p=0", str(path)],
                          timeout=30).strip())
    except Exception:  # noqa: BLE001
        return 0.0


def _concat(parts: list[Path], out: Path) -> None:
    lst = out.with_suffix(".txt")
    lst.write_text("\n".join(f"file '{p.name}'" for p in parts))
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
          "-i", str(lst), "-c", "copy", str(out)], timeout=120)


def _mix_sfx(program: Path, cues, out: Path) -> Path:
    """Overlay SFX one-shots onto the program audio at cue times. Missing
    assets or any failure → return the program unchanged."""
    usable = [(t, SFX_DIR / f"{name}.wav") for t, name in cues
              if (SFX_DIR / f"{name}.wav").exists()]
    if not usable:
        return program
    try:
        # §12 mixing rules: dialogue always stays intelligible. All SFX mix
        # into one bed which is then DUCKED by the dialogue (sidechain) —
        # a boom can never bury what the streamer is saying.
        inputs, filt, tags = ["-i", str(program)], [], []
        for i, (t, p) in enumerate(usable, start=1):
            inputs += ["-i", str(p)]
            ms = int(max(0.0, t) * 1000)
            filt.append(f"[{i}:a]adelay={ms}|{ms},volume=0.6[s{i}]")
            tags.append(f"[s{i}]")
        if len(usable) > 1:
            filt.append(f"{''.join(tags)}amix=inputs={len(usable)}:"
                        f"normalize=0:dropout_transition=0[sbed]")
        else:
            filt.append(f"{tags[0]}anull[sbed]")
        filt.append("[0:a]asplit=2[dlg][key]")
        filt.append("[sbed][key]sidechaincompress=threshold=0.06:ratio=6:"
                    "attack=5:release=250[sduck]")
        filt.append("[dlg][sduck]amix=inputs=2:normalize=0:"
                    "dropout_transition=0[aout]")
        _run(["ffmpeg", "-y", "-v", "error", *inputs,
              "-filter_complex", ";".join(filt),
              "-map", "0:v", "-map", "[aout]",
              "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-b:a", "160k",
              str(out)], timeout=120)
        return out
    except Exception:  # noqa: BLE001
        return program


def build(cut: Path, words: list[dict], dur: float, series: str,
          work: Path, direct: dict | None = None, calm: bool = False,
          edit_mode: bool = False) -> dict:
    """Stage-1 entry. Returns a dict with program path, remapped words, new
    duration, and a ledger. NEVER raises — on any failure returns the
    untouched cut so the simple render still ships.

    `direct` is the author brain's EDIT DIRECTION (validated upstream in
    author._postprocess): {"slam": word-actually-said, "emoji": whitelisted
    name, "replay_worthy": bool}. Content-aware judgement layered over the
    signal heuristics — absent/empty fields fall back to the heuristics."""
    result = {"program": cut, "words": words, "dur": dur,
              "auto_edit": False, "fallback_reason": None,
              "effects": [], "edl": None, "overlays": [],
              "edit_mode": bool(edit_mode)}
    direct = direct or {}
    try:
        wh = _probe_wh(cut)
        motion = motion_energy(cut)
        # peak strength gates the style (weak clips get minimal treatment)
        speech = speech_curve(words, dur)
        _tp, ws, we = money_moment(motion, speech, dur)
        mvals = _norm([v for _t, v in motion]) if motion else [0.0]
        peak_strength = max(mvals) if mvals else 0.0
        style = choose_style(series, dur, peak_strength, calm=calm)
        # the director can veto a replay (talking head, nothing visual) —
        # it can only remove drama, never force it onto a weak clip
        if direct.get("replay_worthy") is False:
            style.replay = False
        if edit_mode:
            # A/B EDIT ARM: montage treatment on the SAME selection/packaging.
            # Graded, multi-peak cut+hit, snappy. On chaotic footage (calm) we
            # keep the cuts+grade+pace but drop the punch-zoom/shake (they land
            # on nothing without a stable subject) — it degrades more gracefully
            # than the slow-mo path, which is why edit can run where clip goes
            # calm.
            style.edit_mode = True
            style.grade = EDIT_GRADE
            if not calm:
                style.zoom_to = max(style.zoom_to, 1.10)
                style.shake = True
            edl = build_edl_edit(words, dur, style, motion)
        else:
            edl = build_edl(words, dur, style, motion)
        if not edl.segments:
            raise RuntimeError("empty EDL")

        parts = []
        for i, seg in enumerate(edl.segments):
            parts.append(_render_segment(cut, seg, wh, work / f"seg{i:02d}.mp4"))
        program = work / "program.mp4"
        _concat(parts, program)
        if style.sfx and edl.sfx_cues:
            program = _mix_sfx(program, edl.sfx_cues, work / "program_sfx.mp4")

        # Overlay cues on the OUTPUT timeline, drawn by Stage 2 on the final
        # frame: REPLAY-style text stamps, plus a contextual reaction EMOJI
        # that pops on the money moment (the overlay-effect layer the camera
        # now stays still for). Both ride the output timeline so retiming and
        # the static crop can't misplace them.
        overlays, _tcur, money_out = [], 0.0, None
        for seg in edl.segments:
            od = seg.out_dur()
            if seg.stamp:
                overlays.append({"type": "text", "text": seg.stamp,
                                 "s": round(_tcur, 3),
                                 "e": round(_tcur + od, 3)})
            if seg.kind == "money" and money_out is None:
                money_out = _tcur
            _tcur += od
        # director's picks win (a slam actually said in the clip beats a
        # generic hype word); heuristics fill anything the director left blank
        s = (series or "chaos").lower()
        emoji = direct.get("emoji") or SERIES_EMOJI.get(s, "mindblown")
        word = direct.get("slam") or SERIES_WORD.get(s, "WAIT")
        if money_out is not None:
            m = round(money_out, 3)
            # speed-lines flash first (behind), emoji burst, then the word slam
            overlays.append({"type": "lines", "s": m, "e": round(m + 0.45, 3)})
            overlays.append({"type": "emoji", "name": emoji, "x": 0.30,
                             "s": m, "e": round(m + 1.4, 3)})
            overlays.append({"type": "emoji", "name": emoji, "x": 0.70,
                             "s": round(m + 0.08, 3), "e": round(m + 1.4, 3)})
            overlays.append({"type": "word", "text": word,
                             "s": m, "e": round(m + 1.2, 3)})

        # The concat's REAL duration drifts ~1% from the predicted
        # edl.out_dur() (minterpolate/setpts frame rounding). Rescale every
        # overlay cue + the caption times to the actual timeline so the
        # REPLAY stamp and emoji/word land on-frame, and report the real
        # duration so Stage-2's afade-out isn't a silent no-op.
        pred = edl.out_dur()
        rwords = remap_words(words, edl)
        actual = _probe_dur(program) or pred
        if pred > 0 and abs(actual - pred) > 0.02:
            sc = actual / pred
            for o in overlays:
                o["s"] = round(o["s"] * sc, 3)
                o["e"] = round(o["e"] * sc, 3)
            for w in rwords:
                w["s"] = round(w["s"] * sc, 3)
                w["e"] = round(w["e"] * sc, 3)

        result.update(
            program=program,
            words=rwords,
            dur=actual,
            overlays=overlays,
            auto_edit=True,
            effects=sorted({s.kind for s in edl.segments if s.kind != "normal"}),
            edl={"t_peak": round(edl.t_peak, 2),
                 "money": [round(edl.money[0], 2), round(edl.money[1], 2)],
                 "n_segments": len(edl.segments),
                 "kinds": [s.kind for s in edl.segments],
                 "out_dur": round(edl.out_dur(), 2),
                 "src_dur": round(dur, 2),
                 "style": series or "chaos",
                 "sfx": [c[1] for c in edl.sfx_cues]})
        return result
    except Exception as e:  # noqa: BLE001
        result["fallback_reason"] = f"{type(e).__name__}: {e}"[:180]
        return result


# The face-crop reframe moved to third_capture/shot_plan.py — the
# shot-plan layer (analyze -> classify layout -> plan -> render)
# supersedes the old single-subject crop that lived here.
