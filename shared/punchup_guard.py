"""Guardrail for externally rewritten scripts — wording may change, claims may not.

ChatGPT gets to punch up hooks, pacing and phrasing. It does not get to invent
facts or reshuffle beats. This module is the mechanical enforcement of that,
because trust is not a control:

  * every number, percentage, money amount, date and year in the original must
    still be present, unchanged, in the rewrite — and as OFTEN as it appeared
    (a repeated stat is a repeated beat; dropping one copy is dropping a claim);
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
from collections import Counter

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
Monday Tuesday Wednesday Thursday Friday Saturday Sunday
""".split()) | frozenset(w.lower() for w in """
Officials Official Authorities Authority Police Officers Investigators
Residents Neighbors Witnesses Crews Firefighters Deputies Detectives
Researchers Scientists Experts Analysts Engineers Doctors Nurses
Employees Workers Customers Passengers Drivers Students Teachers
Reports Sources Records Documents Video Footage Photos Images
Company Officials State Federal Local County City Town Department
""".split()) | frozenset(w.lower() for w in """
Back Ahead Away Together Alone Around Along Through Beyond Behind
Across Between Within Without Against Toward Towards Beside Besides
Despite Although Though Unless Whether Whenever Wherever Whatever
Nearly Almost Barely Hardly Roughly Exactly Simply Clearly Obviously
Suddenly Eventually Finally Initially Originally Previously Recently
Worse Better Bigger Smaller Faster Slower Higher Lower Fewer Half
Everywhere Anywhere Nowhere Somewhere Elsewhere Otherwise Likewise
""".split())
# ^ Two groups. Generic ROLE nouns, then ordinary SENTENCE OPENERS —
# adverbs, prepositions and comparatives that are only ever capitalized
# because a sentence starts with them. A rewrite that opens a sentence
# "Back in 2010 that figure was 12 percent" was being rejected for an
# INVENTED entity called "Back", killing an otherwise perfect rewrite.
# Neither group is ever the named entity a claim depends on.
# Generic ROLE nouns: They are common nouns that happen to be capitalized
# at the start of a sentence, and cutting them ("Officials confirmed…",
# "Authorities stated…") is EXACTLY the corporate hedging the channel's
# writing doctrine tells punch-ups to remove. Treating them as named
# entities made the guard reject the very rewrites we ask for — caught when
# the worked example in the bundle instructions failed its own guard.


def _norm_num(tok: str) -> str:
    return tok.lower().replace(",", "").replace(" ", "").rstrip(".")


def _num_kind(tok: str) -> str:
    """Which KIND of quantity a normalized claim token is.

    Swap detection compares like with like — see `_field_problems`."""
    if "%" in tok:
        return "percent"
    if tok[:1] in "$€£":
        return "money"
    if _YEAR.fullmatch(tok):
        return "year"
    return "plain"


def numeric_claims(text: str) -> Counter:
    """Every quantitative claim in a piece of text, normalized — WITH its
    occurrence count.

    This returned a set until 2026-08-24, which collapsed "40% ... 40%" to
    one membership bit: a rewrite could delete one of two sentences carrying
    the same number and the guard saw no dropped claim because one copy
    remained (doctor finding ddfcb2ed4837). A repeated stat is repeated on
    purpose — a beat that restates the number IS a claim — so multiplicity
    is part of what must be preserved. A Counter keeps `in` / iteration
    semantics for existing callers while `check()` compares counts in both
    directions. The token patterns, `_norm_num` normalization, and the
    money/percent/year-before-bare-number precedence are UNCHANGED."""
    text = text or ""
    found: Counter = Counter()
    consumed: list[tuple[int, int]] = []
    for pat in (_MONEY, _PERCENT, _YEAR):
        for m in pat.finditer(text):
            found[_norm_num(m.group(0))] += 1
            consumed.append(m.span())
    for m in _NUMBER.finditer(text):
        if any(s <= m.start() < e for s, e in consumed):
            continue
        found[_norm_num(m.group(0))] += 1
    return found


def _claim_delta(tok: str, before: int, after: int) -> str:
    """Human-readable claim diff: a token whose count merely CHANGED shows
    both counts ("40% (x2 -> x1)"); a token fully dropped or fully new
    reads exactly as it always did (just the token) — the messages the
    existing tests and operators know keep their shape."""
    if before and after:
        return f"{tok} (x{before} -> x{after})"
    return tok


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


# --- claim-bearing fields other than the script -------------------------
# `apply` copies title, hook, hashtags and punches straight through, and
# until 2026-09-09 `check` looked at NONE of them (doctor finding
# 0bf9780d6272). A rewrite could leave the script byte-identical, sail
# through every check above, and put an unsupported percentage or the wrong
# company in the TITLE — the one line most viewers read.
#
# The rules per field, and why they are not simply the script rules:
#
#   INVENTED  — a number or entity in the rewritten field that appears
#               NOWHERE in the original package (title + hook + script +
#               punches). Rejected. Moving a number out of the script and
#               into the title is a legitimate punch-up, so the pool is the
#               whole original package, not the same field.
#   SWAPPED   — the field both lost a claim and gained one. "Rents fell 12%"
#               -> "Rents fell 21%" passes the invention test whenever 21
#               appears anywhere else in the script, and ships a false
#               headline. A swap inside one field is the fabrication shape.
#   dropped   — a field that only LOSES a claim ("Tesla Recalls 2M Cars" ->
#               "The Recall Nobody Saw Coming") states nothing false, so it
#               is allowed. This is where the field rules are deliberately
#               looser than the script's: a title is a headline, not the
#               record.
#
# Entity swaps are rejected on the same reasoning as numeric ones —
# "Tesla Recalls 2M Cars" -> "Ford Recalls 2M Cars" is the harm — at the
# known cost of refusing an honest reword that drops one name and adds
# another. That trade is the module's standing one: a false reject costs a
# missed punch-up, a false accept ships a fabricated fact.

_CLAIM_FIELDS = ("title", "hook")


def _field_text(pkg: dict, key: str) -> str:
    v = pkg.get(key)
    return str(v or "")


def claim_pool(pkg: dict) -> tuple[Counter, set[str], set[str]]:
    """Every claim the ORIGINAL package makes, anywhere in it.

    Returned as (numeric counter, proper nouns, all words) so a rewrite can
    be tested for inventing something the original never said, without
    caring which field the original said it in."""
    parts = [_field_text(pkg, "title"), _field_text(pkg, "hook"),
             _field_text(pkg, "script"), _field_text(pkg, "text")]
    for p in pkg.get("punches") or []:
        parts.append(str((p or {}).get("text") or ""))
        parts.append(str((p or {}).get("phrase") or ""))
    for h in pkg.get("hashtags") or []:
        parts.append(str(h or ""))
    blob = "\n".join(parts)
    return numeric_claims(blob), proper_nouns(blob), _all_words(blob)


def _field_problems(label: str, o_text: str, r_text: str,
                    pool_nums: Counter, pool_props: set[str],
                    pool_words: set[str]) -> list[str]:
    """Claim problems in one rewritten field. See the note above."""
    if not r_text.strip() or r_text == o_text:
        return []
    out: list[str] = []

    o_nums, r_nums = numeric_claims(o_text), numeric_claims(r_text)
    invented = sorted(set(r_nums) - set(pool_nums))
    if invented:
        out.append(f"INVENTED numeric claim in {label}: "
                   + ", ".join(invented[:4]))
    # A swap is judged per KIND. "12% -> 21%" replaces a rate with a
    # different rate and is the harm; "12% -> 21 towers" reframes the
    # headline around a different quantity the package already states, which
    # is a punch-up. Comparing across kinds refused the second along with
    # the first, and refusing honest rewords is how a guard turns into an
    # off switch.
    for kind in ("percent", "money", "year", "plain"):
        lost_n = sorted(t for t in set(o_nums) - set(r_nums)
                        if _num_kind(t) == kind)
        gained_n = sorted(t for t in set(r_nums) - set(o_nums)
                          if _num_kind(t) == kind)
        if lost_n and gained_n and not invented:
            out.append(f"numeric claim SWAPPED in {label}: "
                       f"{', '.join(lost_n[:3])} -> {', '.join(gained_n[:3])}")

    o_props = _field_entities(o_text, pool_props)
    r_props = _field_entities(r_text, pool_props)
    o_words, r_words = _all_words(o_text), _all_words(r_text)
    added = sorted(r_props - pool_props - pool_words)
    if added:
        out.append(f"INVENTED named entity in {label}: " + ", ".join(added[:4]))
    lost_e = sorted(o_props - r_props - r_words)
    gained_e = sorted(r_props - o_props - o_words)
    if lost_e and gained_e and not added:
        out.append(f"named entity SWAPPED in {label}: "
                   f"{', '.join(lost_e[:3])} -> {', '.join(gained_e[:3])}")
    return out


def field_problems(original: dict, rewritten: dict) -> list[str]:
    """Every claim problem in the non-script fields a punch-up may touch."""
    pool_nums, pool_props, pool_words = claim_pool(original)
    out: list[str] = []
    for key in _CLAIM_FIELDS:
        out += _field_problems(key, _field_text(original, key),
                               _field_text(rewritten, key),
                               pool_nums, pool_props, pool_words)

    # Punch overlays are 1-3 ALL-CAPS words burned onto the frame — as
    # claim-bearing as a title, and copied through by `apply` all the same.
    o_p = original.get("punches") or []
    r_p = rewritten.get("punches") or []
    if r_p:
        for i, rp in enumerate(r_p):
            op = o_p[i] if i < len(o_p) else {}
            out += _field_problems(
                f"punch {i} overlay", str((op or {}).get("text") or ""),
                str((rp or {}).get("text") or ""),
                pool_nums, pool_props, pool_words)

    # A hashtag is a word, not a sentence, so only invention applies — and
    # only where there is a signal to read. `#Blackstone` is caught;
    # `#blackstone` is not, because proper_nouns needs capitalization and
    # requiring every hashtag word to appear in the package would refuse
    # `#shorts` and `#fyp` on every single video. That limit is stated here
    # rather than hidden: hashtag entity coverage is casing-dependent.
    r_tags = " ".join(str(h or "") for h in (rewritten.get("hashtags") or []))
    if r_tags.strip():
        bad_n = sorted(set(numeric_claims(r_tags)) - set(pool_nums))
        bad_e = sorted(proper_nouns(r_tags) - pool_props - pool_words)
        if bad_n:
            out.append("INVENTED numeric claim in hashtags: "
                       + ", ".join(bad_n[:4]))
        if bad_e:
            out.append("INVENTED named entity in hashtags: "
                       + ", ".join(bad_e[:4]))
    return out


# CamelCase / internal-capital brands (SpaceX, YouTube, iPhone) — the one
# entity signal that survives a Title Case headline or an ALL CAPS overlay.
_CAMEL = re.compile(r"\b(?:[A-Z][a-z0-9]+[A-Z]\w*|[a-z][A-Z]\w*)\b")


def _informative_caps(text: str) -> bool:
    """False when this field's capitalization says nothing about names.

    A title is Title Case and an on-screen punch is ALL CAPS, so
    `proper_nouns` reads every content word in them as an entity: "The
    Austin Rent Drop Nobody Saw Coming" yields Saw and Coming. Run against a
    headline that would refuse practically every reword, which is an off
    switch with a guard's name on it."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", text or "")]
    if len(words) < 2:
        return True
    upper = sum(1 for w in words if w[0].isupper())
    return (upper / len(words)) < 0.6


def _field_entities(text: str, pool_props: set[str]) -> set[str]:
    """Named entities in a short field.

    Where capitalization is informative this is exactly `proper_nouns`.
    Where it is not (a headline, an overlay) a word counts as a name only if
    the package's PROSE already treats it as one, or it is CamelCase — which
    keeps "Tesla -> Ford" catchable in a title without flagging "Saw"."""
    text = text or ""
    if _informative_caps(text):
        return proper_nouns(text)
    words = _all_words(text)
    out = {w for w in words if w in pool_props}
    out |= {m.group(0).lower() for m in _CAMEL.finditer(text)}
    return {w for w in out if w not in _COMMON_CAPS}


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
        # Counter subtraction keeps only POSITIVE deficits, so each
        # direction reports every token whose occurrence count fell (or
        # rose) — including the one-of-two-copies-deleted case a set
        # comparison was blind to (ddfcb2ed4837).
        o_nums = numeric_claims(o_script)
        r_nums = numeric_claims(r_script)
        dropped = sorted(o_nums - r_nums)
        invented = sorted(r_nums - o_nums)
        if dropped:
            problems.append("dropped numeric claim(s): " + ", ".join(
                _claim_delta(t, o_nums[t], r_nums[t]) for t in dropped[:6]))
        if invented:
            problems.append("INVENTED numeric claim(s): " + ", ".join(
                _claim_delta(t, o_nums[t], r_nums[t]) for t in invented[:6]))

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

        # --- the fields that are NOT the script ---------------------------
        # title, hook, punch overlays and hashtags all ride through `apply`;
        # for a year nothing looked at any of them (0bf9780d6272).
        problems += field_problems(original, rewritten)

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
