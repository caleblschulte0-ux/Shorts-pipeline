"""Guardrail for externally rewritten scripts — wording may change, claims may not.

ChatGPT gets to punch up hooks, pacing and phrasing. It does not get to invent
facts or reshuffle beats. This module is the mechanical enforcement of that,
because trust is not a control:

  * every number, percentage, money amount, date and year in the original must
    still be present, unchanged, in the rewrite;
  * the rewrite may not introduce a numeric claim that was not in the original;
  * named entities (proper nouns) may not be dropped or invented;
  * beat structure is preserved — same shot count, same subject per shot — so
    media chosen for the original script still lines up with the rewrite.

Why the fact rule matters here specifically: PR #168 found 519 of 546 explainer
datasets were LLM-invented "illustrative" numbers. A punch-up pass is a fresh
opportunity to manufacture more, so it gets checked, not trusted.

    from shared import punchup_guard
    ok, problems = punchup_guard.check(original_pkg, rewritten_pkg)
    pkg = punchup_guard.apply(original_pkg, rewritten_pkg)   # None if rejected

Fails CLOSED: on any doubt the rewrite is rejected and the original ships.
"""
from __future__ import annotations

import re

# Numeric claims, most specific first so money/percent win over bare digits.
_MONEY = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?\s*(?:[kmbt]|thousand|million|billion|trillion)?", re.I)
_PERCENT = re.compile(r"\d[\d,]*(?:\.\d+)?\s?%")
_YEAR = re.compile(r"\b(?:1[6-9]|20)\d{2}\b")
_NUMBER = re.compile(r"\b\d[\d,]*(?:\.\d+)?\b")
# Catches Capitalized words, ALL-CAPS acronyms (NASA, FBI) and CamelCase
# brands (SpaceX, YouTube) — an earlier version missed the last two, which
# let an invented "NASA confirmed it" through the guard.
_PROPER = re.compile(r"\b([A-Z][A-Za-z0-9]+)\b")

# Words that start with a capital without naming anything. Anything NOT in
# here counts as an entity even at the start of a sentence: a false reject
# only costs us a missed punch-up (the original ships), while a false accept
# ships a fabricated fact. The guard deliberately errs toward rejection.
_COMMON_CAPS = frozenset(w.lower() for w in """
The This That These Those And But For With From When Where What Why How
Then Than There Their They Them She Her His Him Its It Was Were Are Is Am
Some Most More Every Each All Any Now New Just Only Also Here After Before
We You Our Your Us Me My If So As At By In On To Of Or Not No Nor Both
Because While During Since Until About Over Under Into Out Up Down Off
Nobody Everyone Someone Anyone Nothing Everything Something Anything
Meanwhile However Instead Still Even Once Again Today Tomorrow Yesterday
Turns Look Watch Imagine Think Meet Say Said Says Here's There's That's
""".split())


def _norm_num(tok: str) -> str:
    return tok.lower().replace(",", "").replace(" ", "").rstrip(".")


def numeric_claims(text: str) -> set[str]:
    """Every quantitative claim in a piece of text, normalized."""
    text = text or ""
    found: set[str] = set()
    consumed: list[tuple[int, int]] = []
    for pat in (_MONEY, _PERCENT, _YEAR):
        for m in pat.finditer(text):
            found.add(_norm_num(m.group(0)))
            consumed.append(m.span())
    for m in _NUMBER.finditer(text):
        if any(s <= m.start() < e for s, e in consumed):
            continue
        found.add(_norm_num(m.group(0)))
    return found


_ANYWORD = re.compile(r"\b([A-Za-z][A-Za-z0-9'\-]*)\b")


def _all_words(text: str) -> set[str]:
    """Every word, lowercased — used so re-casing an existing word is never
    mistaken for inventing an entity."""
    return {m.group(1).lower() for m in _ANYWORD.finditer(text or "")}


def proper_nouns(text: str) -> set[str]:
    """Named entities in the text.

    Sentence position is NOT used to excuse a capitalized word — only the
    `_COMMON_CAPS` list is. That means a sentence-opening name like "SpaceX
    just caught…" is correctly counted, at the cost of occasionally counting
    an ordinary opener as an entity. That trade is deliberate: see the note
    on `_COMMON_CAPS`."""
    out: set[str] = set()
    for m in _PROPER.finditer(text or ""):
        word = m.group(1)
        if word.lower() in _COMMON_CAPS:
            continue
        out.add(word.lower())
    return out


def check(original: dict, rewritten: dict, *,
          allow_shot_text_edits: bool = True) -> tuple[bool, list[str]]:
    """Verify a rewritten package preserves claims and structure.

    Returns (ok, problems). ok=False means ship the original."""
    problems: list[str] = []
    try:
        if not isinstance(rewritten, dict):
            return False, ["rewrite is not an object"]

        o_script = str(original.get("script") or "")
        r_script = str(rewritten.get("script") or "")
        if not r_script.strip():
            return False, ["rewrite has an empty script"]

        # --- claims -------------------------------------------------------
        o_nums = numeric_claims(o_script)
        r_nums = numeric_claims(r_script)
        dropped = sorted(o_nums - r_nums)
        invented = sorted(r_nums - o_nums)
        if dropped:
            problems.append("dropped numeric claim(s): " + ", ".join(dropped[:6]))
        if invented:
            problems.append("INVENTED numeric claim(s): " + ", ".join(invented[:6]))

        # Compare entities against the other text's FULL word set, not just
        # its proper nouns — otherwise emphasis capitalization ("caught" ->
        # "CAUGHT") reads as an invented entity, which is a legitimate
        # punch-up move being rejected for no reason.
        o_props = proper_nouns(o_script)
        r_props = proper_nouns(r_script)
        o_words = _all_words(o_script)
        r_words = _all_words(r_script)
        lost = sorted(o_props - r_props - r_words)
        added = sorted(r_props - o_props - o_words)
        if lost:
            problems.append("dropped named entity(ies): " + ", ".join(lost[:6]))
        if added:
            problems.append("INVENTED named entity(ies): " + ", ".join(added[:6]))

        # --- beat structure (keeps media pairings valid) -------------------
        o_shots = original.get("shots") or []
        r_shots = rewritten.get("shots") or []
        if r_shots and len(r_shots) != len(o_shots):
            problems.append(f"shot count changed {len(o_shots)} -> "
                            f"{len(r_shots)} — media pairings would drift")
        elif r_shots:
            for i, (os_, rs) in enumerate(zip(o_shots, r_shots)):
                o_q = str(os_.get("query") or "").strip().lower()
                r_q = str(rs.get("query") or "").strip().lower()
                if o_q and r_q and o_q != r_q:
                    problems.append(f"shot {i} subject changed "
                                    f"({o_q!r} -> {r_q!r}) — media no longer matches")
                if not allow_shot_text_edits:
                    o_p = str(os_.get("phrase") or "").strip()
                    r_p = str(rs.get("phrase") or "").strip()
                    if o_p and r_p and o_p != r_p:
                        problems.append(f"shot {i} phrase edited but "
                                        f"allow_shot_text_edits=False")

        # --- sanity: not a wholesale replacement --------------------------
        o_len, r_len = len(o_script.split()), len(r_script.split())
        if o_len and not (0.5 * o_len <= r_len <= 1.8 * o_len):
            problems.append(f"length changed too much ({o_len} -> {r_len} "
                            f"words) — looks like a rewrite, not a punch-up")

        return (not problems), problems
    except Exception as exc:                             # noqa: BLE001
        return False, [f"guard failed: {exc}"]


# Fields a punch-up is allowed to touch at all.
PUNCHUP_FIELDS = ("script", "title", "hook", "hashtags", "punches")


def apply(original: dict, rewritten: dict, **kw) -> dict | None:
    """Merge an approved punch-up onto the original. Returns the new package,
    or None if the rewrite was rejected (caller ships the original).

    Only PUNCHUP_FIELDS are taken from the rewrite, plus per-shot `phrase`
    when the shot subject is unchanged — so nothing structural, and nothing
    the guard did not inspect, can ride along."""
    ok, problems = check(original, rewritten, **kw)
    if not ok:
        return None
    merged = dict(original)
    for key in PUNCHUP_FIELDS:
        if rewritten.get(key):
            merged[key] = rewritten[key]
    o_shots = original.get("shots") or []
    r_shots = rewritten.get("shots") or []
    if r_shots and len(r_shots) == len(o_shots):
        new_shots = []
        for os_, rs in zip(o_shots, r_shots):
            shot = dict(os_)
            if rs.get("phrase"):
                shot["phrase"] = rs["phrase"]
            new_shots.append(shot)
        merged["shots"] = new_shots
    merged["punched_up"] = True
    return merged
