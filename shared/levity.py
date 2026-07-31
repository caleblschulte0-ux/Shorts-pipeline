"""Levity — make the channel's humour concrete, checkable, and safe to skip.

The voice doctrine has always said "dry wit". That is an adjective, not an
instruction, and the result is a channel where nobody has ever laughed. An
adjective cannot be followed and cannot be checked, so nothing ever
enforced it and no writer ever knew whether they had done it.

This module replaces the adjective with three concrete things:

    MOVES        the specific shapes of joke that fit this narrator, with
                 worked examples. "Be funny" is not actionable; "state the
                 absurd fact flat, then react in four words" is.
    a GATE       subjects that must never carry a joke. A quip over a
                 fatal crash is not a tone miss, it is the kind of thing
                 that ends a channel.
    a DETECTOR   `has_levity()` — so "none of our videos are funny" becomes
                 a number in the retro brief instead of a feeling.

Deliberately NOT a joke generator. A canned pun bolted onto a script is
worse than silence: it reads as a bot trying, which is the one thing this
voice cannot survive. The writer writes the line; this says what shape it
should be, refuses the videos that must stay straight, and reports whether
it actually happened.

    from shared import levity
    ok, why = levity.allowed(pkg)      # may this one carry a joke?
    levity.has_levity(text)            # did a joke actually land?
    levity.brief_for(pkg)              # what to tell the writer
"""
from __future__ import annotations

import re

# --------------------------------------------------------------------------
# The gate — subjects that stay straight, always
# --------------------------------------------------------------------------
# Not squeamishness. A joke next to a death is the single fastest way to
# lose an audience permanently, and "the algorithm rewarded it" is not a
# defence anyone accepts afterwards. When in doubt this refuses: a straight
# video is a fine outcome, a callous one is not recoverable.
_NO_JOKE = re.compile(
    r"\b("
    r"kill(ed|ing)?|death|died|dead|fatalit(y|ies)|deceased|"
    r"murder(ed|ing|s)?|homicide|manslaughter|shooting|shot dead|"
    r"stabb(ed|ing)|"
    r"victim|casualt(y|ies)|body|bodies|remains|autopsy|morgue|"
    r"funeral|memorial|mourn(ing|ers)?|obituary|condolence|"
    r"suicide|overdose|self[- ]harm|"
    r"assault(ed|ing|s)?|rap(e|ed|ing|ist)|abus(e|ed|es|ing|ive)|molest\w*|"
    r"trafficking|kidnap(p(ed|ing|er|ers))?|abduct\w*|"
    r"missing (child|girl|boy|teen|woman|man)|amber alert|"
    r"cancer|hospice|life support|critical condition|"
    r"war|airstrike|bombing|massacre|genocide|refugee|famine|"
    r"earthquake|tsunami|wildfire deaths|hurricane deaths|"
    r"crash(ed)? (killing|leaving)|plane crash|derailment"
    r")\b", re.I)
# Words that mean death in prose but something ordinary in a headline:
# "fatal error", "oil terminal", "terminal building". Matched separately so
# a technical usage does not silence an otherwise light video.
_AMBIGUOUS = (
    (re.compile(r"\bfatal\b(?!\s+(error|exception|flaw|bug|crash of a "
                r"program))", re.I),
     re.compile(r"\bfatal\s+(error|exception|flaw|bug)\b", re.I)),
    (re.compile(r"\bterminal\b", re.I),
     re.compile(r"\b(oil|gas|lng|container|shipping|port|airport|bus|"
                r"ferry|cargo|import|export)\s+terminal|terminal\s+"
                r"(building|velocity|emulator|window)\b", re.I)),
)

# Signals that a subject is inherently light — a joke is not just allowed
# here, its absence is a missed opportunity.
_LIGHT = re.compile(
    r"\b(raccoon|squirrel|goose|geese|emu|alpaca|llama|kangaroo|"
    r"escaped (zoo|farm)|stole|stolen|heist gone|botched|"
    r"petty revenge|karma|entitled (parent|customer)|refund|"
    r"world record|weirdest|bizarre|absurd|ridiculous|"
    r"town renamed|mayor|parade|festival|contest|competition|"
    r"pumpkin|cheese|hot sauce|vending machine|inflatable)\b", re.I)


def _text_of(pkg: dict) -> str:
    parts = [pkg.get("title") or "", pkg.get("script") or "",
             pkg.get("text") or "", pkg.get("hook") or "",
             pkg.get("closing") or ""]
    for seg in pkg.get("segments") or []:
        parts.append((seg or {}).get("say") or "")
    return "\n".join(parts)


def allowed(pkg: dict) -> tuple[bool, str]:
    """(may this package carry a joke, why not).

    Fails CLOSED on anything that reads as tragedy. A false negative costs
    one dry video; a false positive costs the channel."""
    text = _text_of(pkg)
    for word, benign in _AMBIGUOUS:
        m = word.search(text)
        if m and not benign.search(text):
            return False, (f"subject touches {m.group(0)!r} — this one stays "
                           f"straight.")
    hit = _NO_JOKE.search(text)
    if hit:
        return False, (f"subject touches {hit.group(0)!r} — this one stays "
                       f"straight. A joke here is not a tone miss, it is "
                       f"the kind of thing an audience does not forgive.")
    return True, "fine to land a dry aside"


def is_light(pkg: dict) -> bool:
    """Inherently absurd subject — humour is expected, not optional."""
    return bool(_LIGHT.search(_text_of(pkg))) and allowed(pkg)[0]


# --------------------------------------------------------------------------
# The moves — what "dry wit" actually means in this narrator's mouth
# --------------------------------------------------------------------------
MOVES = [
    {
        "name": "the flat undercut",
        "how": "State the absurd fact plainly, then react in 3-6 words with "
               "no adjectives. The comedy is the gap between the size of "
               "the event and the size of the reaction.",
        "example": "The chase lasted two hours. Top speed: twelve.",
    },
    {
        "name": "the mundane detail",
        "how": "Amid chaos, name the one boring specific. Specificity is "
               "the joke; the reader does the rest.",
        "example": "He fled on foot, still holding the salad.",
    },
    {
        "name": "the understatement",
        "how": "Describe a disaster as a mild inconvenience. Never signal "
               "it — no 'ironically', no 'you can guess'.",
        "example": "This did not go well for the bees.",
    },
    {
        "name": "the callback kicker",
        "how": "End by returning to the hook's image with one word changed. "
               "It lands because the viewer already has the setup.",
        "example": "hook 'nobody checked the roof' -> kicker "
                   "'somebody should have checked the roof'",
    },
    {
        "name": "the deadpan attribution",
        "how": "Quote officialese straight and let it sit. Do not mock it.",
        "example": "The report calls this 'an unplanned pond entry'.",
    },
]

# What kills it. Every one of these reads as a bot performing humour, which
# this narrator cannot survive — the voice is a friend, and friends do not
# do tight five minutes.
ANTI_PATTERNS = [
    "puns and wordplay",
    "setup-then-punchline structure",
    "'wait for it', 'plot twist', 'you won't believe'",
    "exclamation marks",
    "telling the viewer it was funny ('hilariously', 'comedy gold')",
    "emoji, 'lol', 'lmao'",
    "sarcasm aimed at a person rather than a situation",
    "a joke in the first 2 seconds — the hook earns attention, then you "
    "spend it",
]

# --------------------------------------------------------------------------
# The detector — so "we are never funny" is a number, not a feeling
# --------------------------------------------------------------------------
# Heuristics, and honest about it: they detect the SHAPE of an aside, not
# whether it is actually funny. Nothing can measure that. What they catch
# is the failure mode that matters — scripts that are pure recitation with
# no reaction anywhere in them.
_SHORT_REACTION = re.compile(r"(?:^|[.!?]\s)([A-Z][^.!?]{4,45}[.!?])")
_HEDGE = re.compile(r"\b(apparently|somehow|allegedly|reportedly|of course|"
                    r"naturally|predictably|sure enough|as you do|"
                    r"for some reason|obviously)\b", re.I)
_UNDERSTATED = re.compile(r"\b(did not go well|went about as well|less than "
                          r"ideal|not ideal|mixed results|room for "
                          r"improvement|could have gone better)\b", re.I)


def has_levity(text: str) -> dict:
    """Does this script contain anything shaped like a joke?

    Returns the signals found. Empty `signals` on a 150-word script means
    pure recitation — no reaction, no aside, nothing for a viewer to enjoy
    beyond the facts."""
    text = str(text or "")
    sentences = [x for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    signals = []
    if _HEDGE.search(text):
        signals.append("dry hedge ('apparently', 'somehow', 'as you do')")
    if _UNDERSTATED.search(text):
        signals.append("understatement")

    # THE UNDERCUT is a SHAPE, not a length: a short flat beat landing
    # immediately after a long one. Counting short sentences on their own
    # said 84% of this channel's scripts were funny while the operator had
    # never heard a single joke — because a 5-word sentence in the middle
    # of exposition is just a short sentence. The operator was right and
    # the first version of this heuristic was flattering us.
    undercuts = 0
    for prev, cur in zip(sentences, sentences[1:]):
        if len(prev.split()) >= 14 and len(cur.split()) <= 6:
            undercuts += 1
    if undercuts:
        signals.append(f"{undercuts} undercut beat(s) — a short flat "
                       f"reaction after a long setup")
    return {
        "has_levity": bool(signals),
        "signals": signals,
        "undercuts": undercuts,
        "note": ("This detects the SHAPE of an aside, not whether it is "
                 "funny — nothing can measure that. Zero signals on a full "
                 "script means pure recitation, which is the real problem."),
    }


def brief_for(pkg: dict) -> dict:
    """What to tell whoever is writing this package."""
    ok, why = allowed(pkg)
    if not ok:
        return {"levity": "none", "reason": why,
                "instruction": "Write this one completely straight. Do not "
                               "reach for a light note anywhere in it."}
    light = is_light(pkg)
    return {
        "levity": "expected" if light else "welcome",
        "reason": ("the subject is inherently absurd — a straight recitation "
                   "wastes it" if light else
                   "safe subject; one dry aside will lift it"),
        "instruction": (
            "Land ONE dry aside. One — a second reads as trying. Put it "
            "after the fact it reacts to, never in the first two seconds: "
            "the hook earns attention and the aside spends it. If nothing "
            "genuinely occurs to you, ship it straight; a forced joke is "
            "worse than none."),
        "moves": MOVES,
        "never": ANTI_PATTERNS,
    }
