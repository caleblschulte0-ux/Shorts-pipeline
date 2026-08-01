"""media_suitability — a HARD gate on whether an asset belongs in a film.

Shared by every channel. Licence was always checked; suitability never was.
The result, measured across four renders: a gentle film about sleep, work and
screens was illustrated with a police bodycam carrying a visible "POLICE
ACTIVITY" burn-in and an `AXON BODY 3` timecode (twice), a broadcaster's news
memorial with hard-coded subtitles, and a 1938 arms-factory newsreel. Two
independent blind judges named those exact clips as the reason the film reads
as amateur.

Three rules, in the order they matter:

1. BRANDED — the asset carries someone else's identity: a broadcaster or
   agency watermark, a chyron, a bodycam/dashcam timecode, burned-in
   subtitles. No colour grade removes a burn-in, so this is a hard reject
   regardless of how well the clip matches the query.
2. OFF-REGISTER — the subject is tonally incompatible with the film's
   register (violence, arrest, disaster, war footage in a calm explanatory
   piece). Rejected unless the film is explicitly ABOUT that subject, which
   the caller declares through `register`.
3. SCRIPT — burned-in non-Latin text on a clip destined for an English film
   collides with the film's own typography (observed: Chinese subtitles
   overlapping English titles at 150s).

This is a title/metadata heuristic, deliberately conservative, and it is a
FILTER not a classifier: it removes candidates from the pool before selection
so a branded clip can never win a beat. `explain()` returns the reason, which
rides into the audit sidecar — a rejection is always accountable.

Nothing here reads a slug, title or topic to select behavior; the same rules
apply to every film.
"""
from __future__ import annotations

import re

# Someone else's identity burned into the frame. No grade removes these.
BRANDED = (
    "bodycam", "body cam", "body-worn", "dashcam", "dash cam", "axon",
    "newsreel", "news reel", "broadcast", "news report", "newscast",
    "cctv", "surveillance camera", "security camera", "livestream",
    "watermark", "getty", "reuters", "associated press", "ap archive",
    "bbc news", "cnn", "fox news", "nbc news", "abc news", "sky news",
    "press conference", "b-roll package", "vnr", "chyron", "lower third",
)

# Tonally incompatible with a calm explanatory film. Not "bad" footage —
# wrong-register footage, which is a different and correctable judgement.
OFF_REGISTER = (
    "arrest", "attack", "assault", "shooting", "shooter", "riot", "protest",
    "war", "combat", "airstrike", "bombing", "missile", "casualt", "corpse",
    "funeral", "memorial", "mourning", "vigil", "disaster", "massacre",
    "execution", "autopsy", "wounded", "injury", "crash victim", "terror",
    "unconscious", "overdose", "weapon", "gun ", "rifle", "arms factory",
)

# Non-Latin script in a title usually means burned-in non-Latin text in frame.
_NON_LATIN = re.compile(
    r"[Ѐ-ӿ֐-׿؀-ۿऀ-ॿ"
    r"぀-ヿ㐀-䶿一-鿿가-힯]")


def _hits(text: str, vocab) -> list[str]:
    low = str(text).lower()
    return [t for t in vocab if t in low]


def explain(candidate: dict, register: str = "calm",
            script: str = "latin") -> str | None:
    """Why this asset does not belong, or None if it does.

    `register` is the film's tonal register. Anything other than "calm"
    (e.g. "news", "conflict") disables the off-register rule, because a film
    ABOUT an arrest legitimately shows one. `script` is the film's typography;
    "latin" rejects burned-in non-Latin text.
    """
    title = str(candidate.get("title", "") or "")
    attribution = str(candidate.get("attribution", "") or "")
    blob = f"{title} {attribution}"

    b = _hits(blob, BRANDED)
    if b:
        return (f"branded/press material ({', '.join(b[:3])}) — a third-party "
                "burn-in survives any grade")

    if str(register).lower() == "calm":
        o = _hits(blob, OFF_REGISTER)
        if o:
            return (f"off-register subject ({', '.join(o[:3])}) for a calm "
                    "explanatory film")

    if str(script).lower() == "latin" and _NON_LATIN.search(title):
        return ("non-Latin burned-in text likely — it collides with the "
                "film's own typography")
    return None


def is_suitable(candidate: dict, register: str = "calm",
                script: str = "latin") -> bool:
    return explain(candidate, register, script) is None


def filter_candidates(cands: list[dict], register: str = "calm",
                      script: str = "latin"):
    """(kept, rejected) where rejected is [(title, reason), ...].

    NEVER empties the pool to nothing when that would leave a beat with no
    media at all: if every candidate is unsuitable the caller still gets an
    empty list, because a text card is a better outcome than a police bodycam
    — the honest fallback is the point, not a last-resort acceptance.
    """
    kept, rejected = [], []
    for c in cands or []:
        why = explain(c, register, script)
        if why:
            rejected.append((str(c.get("title", ""))[:80], why))
        else:
            kept.append(c)
    return kept, rejected
