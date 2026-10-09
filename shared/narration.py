"""THE NARRATION TELLS A STORY — it does not read the data out.

Operator, 2026-10-09: *"sometimes our stuff doesn't make sense ... instead of
saying the organization's name, we can just say the experts ... unless it's a
really famous one, like WHO or the White House ... this whole thing is just
us reading off numbers to people ... they're hard to follow."*

The recycling story said "Only 9% recycles, 50% lands in dumps, 22%
disappears elsewhere" and then "Best-case OECD forecast reaches just 17%
recycling by 2060": three numbers in four seconds, and a name nobody knows.
The plastic story said "100 percent of placentas, 77 percent of blood, 58
percent of artery plaque". Each line is true; none of them is a story.

  `problems(sc)` — what code can see: a beat that reads off more than
      `MAX_NUMBERS` numbers, and a group named by an acronym most viewers do
      not know (`FAMOUS` is the short list a viewer does).
  `retell(sc)`   — the brain rewrites the beats as a story a friend tells:
      one number a beat, said with what it MEANS, the experts instead of an
      acronym, each line following from the last. The rewrite is validated
      by the rewrite mailbox's own rules (every number derivable from that
      beat's data, no new name, the gate still passes), must clear
      `problems`, and a LISTENER must prefer it to the old narration as
      the one a viewer follows. Only then is it persisted, once
      (`RETOLD`). Nothing here holds a story: a failed retell keeps the
      old words and the story posts as before.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: A then-and-now is two numbers and still a story; three is a table.
MAX_NUMBERS = 2
#: Bumped when the retell doctrine changes, so stories retold under an older
#: one are heard again.
RETOLD = "retell/v1"
WORDS_BY = "claude-retell"

#: Names a viewer knows without being told. Anything else in capitals is a
#: group the narration should describe ("the experts", "scientists", "the
#: government"), not name.
FAMOUS = {"WHO", "NASA", "FBI", "CIA", "UN", "US", "USA", "UK", "EU", "CDC",
          "FDA", "NATO", "IRS", "NFL", "NBA", "MLB", "NHL", "FIFA", "AI",
          "DNA", "GPS", "CEO", "CEOs", "TV", "COVID", "HIV", "AIDS", "ADHD",
          "NYC", "LA", "DC", "ISS", "IVF", "SUV", "EV", "EVs", "PhD", "IQ",
          "ER", "ICU", "MRI", "CPR", "ATM", "PC", "IT", "OK", "SpaceX",
          "F1", "IBM", "BMW", "UFO", "SIDS", "ID", "SAT", "GPA", "MRSA",
          "CO2", "AC", "AM", "FM", "DJ", "DMV", "UAE", "HPV", "GPU", "AB",
          "S&P", "USS", "GDP"}

_FIGURE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s*%?")
_ACRONYM = re.compile(r"\b[A-Z][A-Z0-9&]{1,6}s?\b")
#: Capitals that are words or emphasis, not names of anything.
_NOT_ACRONYMS = {"I", "A", "OK", "ALL", "ONE", "YOU", "YOUR", "NOT", "NO",
                 "NOW", "THIS", "FULL", "MILLION", "BILLION", "ONLY", "EVERY"}


def _figures(say: str) -> list:
    """The numbers a line says, a year counted as a number only when it is
    the thing measured (a year that dates another number is not read OUT)."""
    out = []
    text = re.sub(r"\b1 in (?=\d)", "", str(say or ""))   # "1 in 15" is one number: odds
    for m in _FIGURE.finditer(text):
        tok = m.group(0).strip().rstrip(",")
        if re.fullmatch(r"(1[5-9]|20)\d\d", tok):
            continue                            # "in 2016" dates, it does not count
        out.append(tok)
    return out


def obscure_names(text: str) -> list:
    """Acronyms in `text` a viewer would not know."""
    return [m.group(0) for m in _ACRONYM.finditer(str(text or ""))
            if m.group(0) not in FAMOUS and m.group(0).rstrip("s") not in FAMOUS
            and m.group(0) not in _NOT_ACRONYMS and not m.group(0).isdigit()]


def problems(sc: dict) -> list:
    """Why this narration reads as data, not a story. Empty = it reads."""
    out = []
    for i, seg in enumerate(sc.get("segments") or []):
        say = str(seg.get("say") or "")
        n = len(_figures(say))
        if n > MAX_NUMBERS:
            out.append(f"beat {i + 1} reads off {n} numbers: say one, and what "
                       "it means")
        for name in dict.fromkeys(obscure_names(say)):
            out.append(f"beat {i + 1} names {name}: say what that is in plain "
                       "words ('the experts', 'scientists', 'a space telescope')")
    for k in ("closing",):
        for name in dict.fromkeys(obscure_names(sc.get(k))):
            out.append(f"{k} names {name}: say what that is in plain words")
    return out


DOCTRINE = """\
THE NARRATION is the story a friend tells you after they read something \
wild. It is NOT the data read out loud.

  - ONE number a beat, and say what it MEANS: not "9% recycles, 50% lands in \
dumps, 22% disappears" but "Only about one bottle in ten ever gets \
recycled." Two numbers only for a then-and-now ("it was 3,300; now it's \
4,900"). Never a list.
  - Every number you keep must be one that beat's DATA shows, written the \
way the data has it or as its share or change. Keep the beat's headline \
number.
  - No organisation names a viewer would not know. "The OECD forecast" is \
"the experts' best guess". Name it only if everyone knows it: the WHO, \
NASA, the White House, the FBI.
  - Each beat follows from the last: the setup, the turn, the payoff. A \
viewer who hears it once, at full speed, with no picture, knows what is \
happening and why it matters to them.
  - Plain words. No units a person has to think about when a plain one \
works ("tons", not "megatonnes CO2e"). No jargon, no hedging, no \
throat-clearing ("It's worth noting").
  - Exaggerate nothing. A link is not a cause; a forecast is not a fact.
"""

_PROMPT = """{doctrine}
{pace}

TITLE (keep it): {title}
HOOK (keep it): {hook}
{beats}
CLOSING: {closing}
{refused}
Rewrite the {n} beats and the closing so the video tells this story. Return \
STRICT JSON: {{"segments": [{{"say": str}}, ...], "closing": str}} with \
exactly {n} segments in the same order."""

_LISTEN = """You are a viewer and a fact-checker. Two narrations for the same \
YouTube Short follow, with the data each beat is drawn from. A narration \
FAILS if it says anything the data does not support (a cause, a "never", a \
number, a comparison), or if heard once at full speed it does not make \
sense. Of the ones that pass, which would a viewer FOLLOW and keep watching: \
a story, not a list of numbers?

DATA:
{data}

A:
{a}

B:
{b}

Return STRICT JSON: {{"pick": "A" | "B" | "neither", "why": "<one line>"}}"""


def _data_text(sc: dict) -> str:
    from shared import rewrite_mailbox as rw
    rows = []
    for i, seg in enumerate(sc.get("segments") or []):
        d = rw._dataset(seg) or {}
        pts = ", ".join(f"{p.get('label')}={p.get('value')}"
                        for p in (d.get("points") or [])[:rw.MAX_POINTS])
        rows.append(f"BEAT {i + 1} DATA ({d.get('title') or ''}, "
                    f"{d.get('unit') or ''}): {pts}")
    return "\n".join(rows)


def _script(sc: dict) -> str:
    return "\n".join([f"HOOK: {sc.get('hook') or ''}"]
                     + [f"BEAT {i + 1}: {s.get('say') or ''}"
                        for i, s in enumerate(sc.get("segments") or [])]
                     + [f"CLOSING: {sc.get('closing') or ''}"])


def _parse(raw) -> dict | None:
    m = re.search(r"\{.*\}", str(raw or ""), re.S)
    try:
        got = json.loads(m.group(0)) if m else None
    except Exception:  # noqa: BLE001
        return None
    return got if isinstance(got, dict) else None


def _default_brain(prompt: str):
    try:
        from data_learning import scene_author as sa
        return sa.ask_brain(prompt, model="sonnet", timeout=150)
    except Exception:  # noqa: BLE001
        return None


def retell(sc: dict, *, config_path: Path | None = None, brain=None,
           log=print, tries: int = 3) -> dict:
    """Retell a story whose narration reads as data, in place and on disk.
    Returns {"changed": bool, "reasons": [...]}. A story already retold
    under this doctrine, or with nothing to fix, costs no brain call."""
    if sc.get("retold") == RETOLD:
        return {"changed": False, "reasons": []}
    found = problems(sc)
    if not found:
        return {"changed": False, "reasons": []}
    from shared import pacing
    from shared import rewrite_mailbox as rw
    held = rw.word_holds(sc)
    if held:
        # The gate holds this story for its words already; the mailbox
        # re-authors it, and a retell that must also clear those is not one.
        return {"changed": False, "reasons": ["held by the gate: " + held[0]]}
    brain = brain or _default_brain
    data = _data_text(sc)
    refused = ""
    reasons = found
    for attempt in range(tries):
        beats = "\n".join(
            f"BEAT {i + 1}: {s.get('say') or ''}\n  {line}"
            for i, (s, line) in enumerate(zip(sc.get("segments") or [],
                                              data.splitlines())))
        raw = brain(_PROMPT.format(
            doctrine=DOCTRINE, pace=pacing.rule(pacing.budget()),
            title=sc.get("title") or "", hook=sc.get("hook") or "",
            beats=beats, closing=sc.get("closing") or "",
            n=len(sc.get("segments") or []),
            refused=(f"\nYOUR LAST REWRITE WAS REFUSED — fix exactly this: "
                     f"{refused}\n" if refused else "")))
        ans = _parse(raw)
        if not ans:
            reasons = ["no answer" if not raw else "the answer was not JSON"]
            if not raw:
                break
            refused = "return STRICT JSON only"
            continue
        segs = sc.get("segments") or []
        new = [{"say": str((x or {}).get("say") or "").strip(),
                "topic": s.get("topic")}       # printed on the video; the gate passed it
               for s, x in zip(segs, ans.get("segments") or [])]
        full = {"title": sc.get("title"), "hook": sc.get("hook"),
                "closing": str(ans.get("closing") or sc.get("closing") or ""),
                "question": sc.get("question"), "segments": new}
        cand, probs = rw.validate(sc, full)
        if cand is not None:
            probs = problems(cand)
        if cand is None or probs:
            reasons = probs
            refused = "; ".join(probs)[:400]
            log(f"[retell] {sc.get('slug')}: rewrite {attempt + 1} refused: "
                f"{refused[:160]}")
            continue
        verdict = _parse(brain(_LISTEN.format(data=data, a=_script(sc),
                                              b=_script(cand)))) or {}
        if str(verdict.get("pick", "")).strip().upper() != "B":
            reasons = [f"the listener kept the old narration: "
                       f"{verdict.get('why') or 'no verdict'}"]
            log(f"[retell] {sc.get('slug')}: {reasons[0][:160]}")
            break
        cand["retold"] = RETOLD
        _apply(sc, cand, config_path, log)
        return {"changed": True, "reasons": []}
    return {"changed": False, "reasons": reasons}


def _apply(sc: dict, cand: dict, config_path, log) -> None:
    from shared import rewrite_mailbox as rw
    sc["closing"] = cand.get("closing")
    for a, c in zip(sc.get("segments") or [], cand.get("segments") or []):
        a["say"] = c.get("say")
    sc["retold"] = RETOLD
    sc["words_by"] = WORDS_BY
    path = Path(config_path or REPO / "data_learning" / "niche.config.json")
    try:
        cfg = json.loads(path.read_text())
        if rw.apply(cfg, cand, by=WORDS_BY):
            from shared.fsutil import write_json_if_changed
            write_json_if_changed(path, cfg, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — the in-memory story is retold either way
        log(f"[retell] {sc.get('slug')}: persist skipped: {e}")
    log(f"[retell] {sc.get('slug')}: retold — "
        + " / ".join(s.get("say") or "" for s in sc.get("segments") or []))
