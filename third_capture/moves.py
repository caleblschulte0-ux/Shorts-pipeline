"""The repost editor's moves, placed on the second they belong to.

Operator, 2026-10-09, after the grey-and-piano sad edit: *"you have to add
stuff other clippers do not we can't just do the sad grey thing"*. The big
Twitch repost channels cut every clip with the same small kit, each move
on one moment, never as a filter over the whole video:

  zoom     a hard punch-in on the reaction or the punchline, a bass boom
           under it, back out a second later
  shake    the frame shakes on a yell, a jump scare, a slam, with the boom
  awkward  a slow push-in on the face during a cringe silence, crickets
  sad      from here the picture goes grey and a sad piano comes in
           (third_capture/mood.py)
  hype     from here the colour pops and a hard 808 beat comes in
           (a W, a clutch, a win, a crowd going off)
  line2    the line of text changes at the turn ("Then chat noticed 💀")

The author (`third_capture/author.py`) names the moves and the seconds,
from the transcript; `plan` validates them and the renderer applies them.
None of this changes the clip's speed: the slow-mo, replay and speed-ramp
the operator called "that weird slowdown thing" stay retired.

Every hit and the hype beat are SYNTHESISED here: a boom on every clip
would otherwise be a Content ID claim on every clip. The one exception is
the sad turn, which carries a REAL song the author picks (operator,
2026-10-17: "an actual like wistful sad song people might recognize"),
funnel/songs.py; the synthesised piano is its fallback. Made once
per run into cache/ (gitignored); nothing binary is committed.
"""
from __future__ import annotations

import wave
from pathlib import Path

from third_capture import mood as mood_mod

REPO = Path(__file__).resolve().parent.parent
MUSIC = REPO / "cache" / "music"
RATE = 44100

HITS = {"zoom", "whoa", "shake", "awkward"}
BEDS = {"sad", "hype"}
MOVES = HITS | BEDS
MAX_HITS = 3
#: The Vine boom is EMPHASIS, one per clip at most (operator, 2026-10-11:
#: "not on every zoom. You just use it in certain moments ... it's an
#: emphasis. It's like a whoa.")
MAX_WHOA = 1
HIT_GAP = 2.0          # seconds between two hits: more is a seizure
HYPE_LOOK = "eq=saturation=1.35:contrast=1.08"
#: a mastered record is far louder than the synthesised beds; this sits it
#: under the voices before the ducking
SONG_GAIN = 0.22

# (rise, hold, fall) seconds and peak zoom per hit
_SHAPE = {"zoom": (0.10, 1.3, 0.22, 0.24),
          "whoa": (0.05, 1.1, 0.20, 0.30),
          "shake": (0.04, 0.55, 0.12, 0.09),
          "awkward": (2.8, 0.9, 0.3, 0.15)}
#: Only the "whoa" booms, and it is the REAL Vine boom
#: (assets/sfx/vine_boom.ogg, fetched by scripts/fetch_sfx.py): the
#: operator heard two synthesised look-alikes and said "that's not it".
#: A zoom or a shake is silent; a boom on every zoom stops meaning "whoa".
_SFX = {"whoa": ("vine_boom", 0.9), "awkward": ("crickets", 0.55)}
VINE_BOOM = REPO / "assets" / "sfx" / "vine_boom.ogg"


# ---------------------------------------------------------------- plan --

def plan(edit: dict | None, dur: float, offset: float = 0.0) -> dict:
    """{"hits": [{"move","at"}], "bed": {"move","at"} | None,
    "line2": {"text","at"} | None} — only what this clip can carry.
    The author's seconds are CLIP time; `offset` is where the cut starts,
    so a move lands on the same moment in the cut. A hit before the cut is
    dropped; a bed or line already under way starts with the cut."""
    edit = edit or {}
    out = {"hits": [], "bed": None, "line2": None}
    if dur <= 2.0:
        return out
    lo, hi = 0.3, max(0.3, dur - 1.0)

    def _at(v, keep_early: bool = True) -> float | None:
        try:
            t = float(v) - float(offset or 0.0)
        except (TypeError, ValueError):
            return None
        if t < 0 and not keep_early:
            return None
        return round(min(max(t, lo), hi), 2)

    raw = list(edit.get("moves") or [])
    m = str(edit.get("mood", "")).strip().lower()
    if m in BEDS:  # the older single-mood field
        raw.append({"move": m, "at": edit.get("mood_at", 0)})
    hits = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        mv = str(r.get("move", "")).strip().lower()
        at = _at(r.get("at"), keep_early=mv in BEDS)
        if mv not in MOVES or at is None:
            continue
        if mv in BEDS:
            if out["bed"] is None:
                out["bed"] = {"move": mv, "at": at}
        else:
            hits.append({"move": mv, "at": at})
    for h in sorted(hits, key=lambda h: h["at"]):
        if len(out["hits"]) >= MAX_HITS:
            break
        if h["move"] == "whoa" and sum(
                k["move"] == "whoa" for k in out["hits"]) >= MAX_WHOA:
            continue
        if all(abs(h["at"] - k["at"]) >= HIT_GAP for k in out["hits"]):
            out["hits"].append(h)
    # the REAL song under a sad turn (operator, 2026-10-17: "an actual
    # like wistful sad song people might recognize"): funnel/songs.py
    if out["bed"] and out["bed"]["move"] == "sad":
        from funnel import songs
        if songs.clean(edit.get("song")):
            out["bed"]["song"] = songs.clean(edit.get("song"))
    # NO MUSIC UNDER A VOICE (operator, 2026-10-28, of a Baller Bro clip:
    # "It played loud music over the guy talking the whole time ... that's
    # so annoying"). An edit with music=False keeps the bed's LOOK (the
    # grey, the colour pop) and drops its sound: a song or a beat under
    # someone talking is noise, however well it is ducked.
    if out["bed"] and edit.get("music") is False:
        out["bed"].pop("song", None)
        out["bed"]["silent"] = True
    l2 = edit.get("line2") or {}
    text = str(l2.get("text", "")).strip() if isinstance(l2, dict) else ""
    at = _at(l2.get("at")) if isinstance(l2, dict) else None
    if text and at is not None and at >= 1.5:
        out["line2"] = {"text": text[:80], "at": at}
    return out


def summary(p: dict) -> list:
    """What the ledger records: ["zoom@3.2", "sad@7.0", "line2@9.1"]."""
    s = [f"{h['move']}@{h['at']}" for h in p.get("hits", [])]
    if p.get("bed"):
        s.append(f"{p['bed']['move']}@{p['bed']['at']}"
                 + (f"({p['bed']['song']})" if p["bed"].get("song") else "")
                 + ("(silent)" if p["bed"].get("silent") else ""))
    if p.get("line2"):
        s.append(f"line2@{p['line2']['at']}")
    return s


# --------------------------------------------------------------- video --

def _env(a: float, rise: float, hold: float, fall: float) -> str:
    """0 -> 1 over `rise` from second a, held, back to 0 over `fall`."""
    return (f"clip((it-{a:.2f})/{rise},0,1)"
            f"*clip(({a + rise + hold + fall:.2f}-it)/{fall},0,1)")


def look(p: dict) -> str:
    """The colour from the bed's second on (grey or pop), or ''."""
    b = p.get("bed")
    if not b:
        return ""
    vf = mood_mod.GREY if b["move"] == "sad" else HYPE_LOOK
    return f"{vf}:enable='gte(t,{b['at']:.2f})'"


def camera(p: dict, w: int, h: int) -> str:
    """One zoompan for every hit (it is time-driven, one output frame per
    input frame at 30fps), or '' when the clip has no hits."""
    if not p.get("hits"):
        return ""
    z, sx, sy = ["1"], ["0"], ["0"]
    for k in p["hits"]:
        rise, hold, fall, peak = _SHAPE[k["move"]]
        e = _env(k["at"], rise, hold, fall)
        z.append(f"{peak}*{e}")
        if k["move"] == "shake":
            sx.append(f"26*sin(it*53)*{e}")
            sy.append(f"18*sin(it*41+1)*{e}")
    zz = "+".join(z)
    x = f"clip(iw/2-iw/zoom/2+{'+'.join(sx)},0,iw-iw/zoom)"
    y = f"clip(ih/2-ih/zoom/2+{'+'.join(sy)},0,ih-ih/zoom)"
    return (f"fps=30,zoompan=z='{zz}':x='{x}':y='{y}':d=1:"
            f"s={w}x{h}:fps=30")


# --------------------------------------------------------------- sound --

def _write(path: Path, samples) -> Path:
    import numpy as np
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype("<i2")
                      .tobytes())
    tmp.replace(path)
    return path


def _norm(x, peak=0.9):
    import numpy as np
    return x / (np.abs(x).max() or 1.0) * peak


def _crickets():
    """Two crickets in an empty room, ~3.5s."""
    import numpy as np
    n = int(3.6 * RATE)
    t = np.arange(n) / RATE
    out = np.zeros(n)
    for f0, period, off in ((4600, 0.72, 0.0), (4150, 0.95, 0.31)):
        tone = np.sin(2 * np.pi * f0 * t)
        local = np.mod(t - off, period)
        chirp = (local < 0.16) * (t >= off)
        pulses = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 28 * local))
        out += tone * chirp * pulses
    fade = np.minimum(1, t / 0.2) * np.minimum(1, (t[-1] - t) / 0.4)
    return _norm(out * fade, 0.6)


def _hype():
    """A hard 140bpm 808 loop (kick, clap, hats, sliding bass, cowbell
    hook in A minor), 8 bars."""
    import numpy as np
    beat = 60 / 140
    bars = 8
    n = int(bars * 4 * beat * RATE) + RATE
    mix = np.zeros(n)
    rng = np.random.default_rng(3)

    def add(sig, at, g=1.0):
        s = int(at * RATE)
        k = min(len(sig), n - s)
        if k > 0:
            mix[s:s + k] += g * sig[:k]

    def tt(secs):
        return np.arange(int(secs * RATE)) / RATE

    t = tt(0.45)
    kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-t * 28)) / RATE)
    kick *= np.exp(-t * 7)
    t = tt(0.25)
    clap = rng.standard_normal(len(t)) * np.exp(-t * 22)
    clap = np.diff(clap, prepend=0)
    t = tt(0.05)
    hat = np.diff(rng.standard_normal(len(t)), prepend=0) * np.exp(-t * 90)

    def bass(f, secs):
        t = tt(secs)
        return np.tanh(2.5 * np.sin(2 * np.pi * f * t)) * np.exp(-t * 1.6)

    def bell(f, secs=0.22):
        t = tt(secs)
        sq = (np.sign(np.sin(2 * np.pi * f * t))
              + np.sign(np.sin(2 * np.pi * f * 1.48 * t)))
        return sq * np.exp(-t * 14)

    roots = [55.0, 43.65, 49.0, 41.2]      # A1 F1 G1 E1
    hook = [880, 1046.5, 880, 784, 659.3, 784, 880, 659.3]
    for b in range(bars):
        t0 = b * 4 * beat
        for k in (0, 1.5, 2.5):
            add(kick, t0 + k * beat, 0.9)
        for k in (1, 3):
            add(clap, t0 + k * beat, 0.5)
        for k in range(8):
            add(hat, t0 + k * beat / 2, 0.22)
        if b % 2:
            for k in range(6):
                add(hat, t0 + 3 * beat + k * beat / 6, 0.15)
        add(bass(roots[(b // 2) % 4], 4 * beat), t0, 0.6)
        for k, f in enumerate(hook):
            add(bell(f), t0 + k * beat / 2, 0.12)
    return _norm(mix)


_VERSION: dict = {}
_MAKERS = {"crickets": _crickets, "hype": _hype}


def sound(name: str) -> Path:
    """cache/music/<name>_v<N>.wav, made once (N moves when a sound is
    remade, so a cached old one is never played again)."""
    if name == "sad":
        return mood_mod.bed()
    if name == "vine_boom":
        return VINE_BOOM
    path = MUSIC / f"{name}_v{_VERSION.get(name, 1)}.wav"
    if path.exists() and path.stat().st_size > 1000:
        return path
    return _write(path, _MAKERS[name]())


def audio_graph(p: dict, voice: str, first_input: int, dur: float,
                out: str) -> tuple[str, list]:
    """(filter_complex fragment ending in [out], the sound files it reads
    as inputs first_input, first_input+1, ...). The bed is ducked under
    the voices; the hits land on top of them."""
    parts, files, cur = [], [], voice
    b = p.get("bed")
    if b and b.get("silent"):
        b = None                         # the look only: no sound under it
    if b:
        song = None
        if b.get("song"):
            from funnel import songs
            song = songs.get(b["song"])
            if song is None:
                print(f"::warning::[moves] song {b['song']} not fetched — "
                      "the piano instead", flush=True)
        files.append(song or sound(b["move"]))
        idx = first_input + len(files) - 1
        t = {"at": b["at"], "fade": 1.2 if b["move"] == "sad" else 0.3}
        gain = (SONG_GAIN if song else mood_mod.BED_GAIN
                if b["move"] == "sad" else 0.26)
        frag = mood_mod.audio_graph(t, cur, f"{idx}:a", dur, "abed")
        parts.append(frag.replace(f"volume={mood_mod.BED_GAIN}",
                                  f"volume={gain}"))
        cur = "abed"
    sfx = []
    for i, k in enumerate(p.get("hits", [])):
        if k["move"] not in _SFX:
            continue                     # a silent hit: picture only
        name, gain = _SFX[k["move"]]
        files.append(sound(name))
        idx = first_input + len(files) - 1
        ms = int(k["at"] * 1000)
        parts.append(f"[{idx}:a]volume={gain},adelay={ms}|{ms},"
                     f"aformat=channel_layouts=stereo[sfx{i}]")
        sfx.append(f"[sfx{i}]")
    if sfx:
        parts.append(f"[{cur}]{''.join(sfx)}amix=inputs={1 + len(sfx)}:"
                     f"duration=first:normalize=0[{out}]")
    elif parts:
        parts.append(f"[{cur}]anull[{out}]")
    else:
        parts.append(f"[{voice}]anull[{out}]")
    return ";".join(parts), files
