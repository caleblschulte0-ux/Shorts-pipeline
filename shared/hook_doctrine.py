"""THE HOOK — the first sentence we say: clickbait, never a scam, and said
the way a PERSON says it.

Operator, 2026-09-25: *"Our intros need to be 2000s, ad on a fucking LimeWire
type shit ... real clickbaity. And not like scammy clickbaity."* Operator,
2026-10-08: *"we need to work on our wording like our word hooks are trash"*.

Between the two, hooks were RANKED BY KEYWORDS: two points for "you", two for
a verb off a list (vanished, gutted, exploded), and the forge refused any hook
under 7. So the brain learned to staple those words onto anything: "Your
garden vanished 94% of monarch milkweed", "Your town's peanut allergies
vanished 43% overnight, shocking everyone", "Your world vanished 15,000 years
ago", "Your octopus has 500 million neurons". It also rewrote good plain hooks
("A degree costs triple. It pays half.") because they scored 1. And the score
bought nothing: across the posted videos with 30+ views, hooks scoring 7+
kept 31% of viewers and hooks scoring 0-2 kept 36%.

So a hook is now judged the way a viewer meets it, by a LISTENER
(`listen`): the brain hears every candidate — the current hook included — as
someone scrolling, fails any that is untrue, does not parse heard once, or
sounds like a template, and ranks the rest by "which would make you stop".
Code keeps what code can check (`floor`: quiz, hedge, vague, scam, formula
tag, length, garbled; `problems`: the numbers and names), and only a line
that clears both reaches the listener.

THE LINE BETWEEN CLICKBAIT AND A SCAM is the same one the rest of this repo
already holds: EXAGGERATE NOTHING. Every number in a new hook must come from
the story's own data (`rewrite_mailbox._quantities_ok`), it may not bring a
name from outside (`rewrite_mailbox._entities_ok`), and a hook that fails
either is thrown away, however good it sounds. Those checks are REUSED, not
re-written: they are what already guards a ChatGPT rewrite.
"""
from __future__ import annotations

import json
import re

#: What the brain is told. Kept here so the forge and the render-time
#: sharpener ask for the SAME thing.
DOCTRINE = """\
THE HOOK is the first sentence the viewer hears, over the first frame. It has \
to stop a thumb mid-scroll. It is clickbait, never a scam: the most surprising \
TRUE thing in this story, said the way a person says it when they just found \
out and can't believe it.

HOW IT SOUNDS:
  - Like a person talking, not ad copy. Read it out loud: if nobody would ever \
say that sentence to a friend, it is wrong, however dramatic it is.
  - It makes sense heard ONCE, at full speed, with no picture. Plain words, \
normal grammar, one idea.
  - The surprise is the FACT, so say the fact: the number, the flip, the thing \
nobody expects. "More than half the web is bots now." "A degree costs triple. \
It pays half." "One ship now carries 24,000 truckloads of cargo."
  - Concrete beats abstract: a thing you can picture, a number you can feel.
  - "You" only when it really is about the viewer: their money, their body, \
their phone, their kids. "Your dead phone joined 62 million tons of trash" is \
fine — it is your phone. "Your octopus", "your lecture hall", "your garden \
vanished 94% of milkweed", "your world vanished 15,000 years ago" are not \
about the viewer and do not parse.
  - A strong verb only when it is the true verb. "Vanished" needs a thing that \
vanished; "exploded" needs a thing that grew that fast.
  - Short: 5 to 14 words. One sentence, two at most.

NEVER:
  - A formula tag bolted on the end: "...and nobody told you", "...your town \
feels it", "...shocking everyone", "...here's what changed". If the fact needs \
a tag to be interesting, pick a better fact.
  - A number that is not in the data, rounded differently, or converted.
  - A name — country, company, person — the story does not already use.
  - A fact that is not true. Exaggerate nothing: a 24% cut is not "gone".
  - Quiz or trivia openers: "Which animal...", "Did you know...", "Can you \
guess...", "You won't believe...". A question is fine only if it accuses \
("Why is your coffee twice the price?").
  - Hedges (might, may, perhaps), vague size words with no number \
("astonishing", "gargantuan", "much more"), and scam tells ("click", "free", \
ALL CAPS).

Opening lines this channel posted that held the most viewers (the numbers \
are theirs — use yours): "One laser shot finally changed the math." "More \
than half the web is bots now." "One ship now carries 24,000 truckloads of \
cargo." "Your dead phone joined 62 million tons of trash, and the pile is \
growing fast."
"""

MAX_WORDS = 16

_QUIZ = re.compile(
    r"^\s*(which|what|who|can you|could you|bet you|guess|did you know|have "
    r"you ever|you won'?t believe|ever wonder|here'?s a fun)\b", re.I)
_HEDGE = re.compile(r"\b(might|may|possibly|perhaps|somewhat|a bit|arguably|"
                    r"kind of|sort of|some say)\b", re.I)
_SCAM = re.compile(r"\b(click|link|free|guaranteed|doctors hate|one weird "
                   r"trick|subscribe)\b", re.I)
_SHOUT = re.compile(r"\b[A-Z]{4,}\b")
_ACCUSE = re.compile(r"^\s*why (is|are|did|do|does) (your|you)\b", re.I)
#: A size said with no size: "Your nose can detect an astonishing number of
#: scents", "home to gargantuan creatures". The viewer is told to be amazed
#: and given nothing to be amazed BY.
_VAGUE = re.compile(r"\b(astonishing\w*|incredibl\w*|amazing\w*|gargantuan|"
                    r"mind[- ]blowing|unbelievabl\w*|much more|so many)\b", re.I)
#: The tags the keyword score taught the forge to bolt on: if a fact needs
#: one to be interesting, it is the wrong fact.
_TAG = re.compile(r"(\band nobody (told you|noticed|is talking about it)|"
                  r"\bshocking everyone|\bfeels it\b|\bthink about that|"
                  r"\bthen something \w+ happened)", re.I)
#: A number with nothing after it to say what it counts, run straight into a
#: dash: "Your sky vanished 29.9— the ozone hole is healing" was spoken over
#: the first frame on 2026-10-07. A viewer hears a number of nothing.
#: Only a number run INTO the dash: "shrank from 29.9 million km² to 22.9 —
#: and ..." is a list a viewer can follow, the unit said once.
_BARE_NUMBER = re.compile(r"\d(?:[\d.,]*\d)?(?:[—–]|--)")


def garbled(line: str) -> list:
    """Why this line is not a sentence a person would say. Empty = fine."""
    m = _BARE_NUMBER.search(" ".join(str(line or "").split()))
    if m:
        return [f"a bare number with nothing after it ({m.group(0).strip()!r})"]
    return []


def floor(line: str) -> list:
    """Why this line cannot open a video, by what code can see. Empty = the
    listener may hear it. Never a ranking: a line that clears the floor is
    no better for clearing it by more."""
    s = " ".join(str(line or "").split())
    if not s:
        return ["empty"]
    out = []
    words = len(s.split())
    if words > MAX_WORDS:
        out.append(f"long ({words} words)")
    if _QUIZ.match(s) and not _ACCUSE.match(s):
        out.append("quiz opener")
    if _HEDGE.search(s):
        out.append("hedge")
    if _SCAM.search(s) or _SHOUT.search(s):
        out.append("scam tell")
    for rx, what in ((_VAGUE, "vague"), (_TAG, "a formula tag")):
        m = rx.search(s)
        if m:
            out.append(f"{what} ({m.group(0).strip()!r})")
    return out + garbled(s)


# ---------------------------------------------------------------------------
# What a new hook is allowed to say — the story's own data, nothing else
# ---------------------------------------------------------------------------

def evidence(story_cfg: dict) -> tuple[set, set]:
    """(the quantities the HOOK may say, every word the story's labels use).

    THE HOOK IS SPOKEN OVER THE FIRST BEAT'S PICTURE — the cold open is
    drawn from segment 0's data in both looks — so its number must be one
    that picture shows. A sharpened hook said "750,000 square kilometers"
    over a picture of 27,772 (amazon-still-shrinking, 2026-09-25): "line up
    the hook caption with the number on screen". Names may come from any
    beat; numbers only from the first.
    """
    from shared import rewrite_mailbox as rm
    allowed: set = set()
    label_words: set = set()
    for k, seg in enumerate(story_cfg.get("segments") or []):
        if k == 0:
            allowed |= rm._allowed_for(seg)
        d = rm._dataset(seg) or {}
        for p in d.get("points") or []:
            label_words |= {w.lower() for w in re.findall(
                r"[A-Za-z][A-Za-z'\-]+", str(p.get("label") or ""))}
        label_words |= {w.lower() for w in re.findall(
            r"[A-Za-z][A-Za-z'\-]+", str(d.get("title") or ""))}
    return allowed, label_words


def scale_facts(story_cfg: dict) -> list:
    """TRUE size comparisons this story's own data supports
    (`shared/scale_refs`) — the only outside names a hook may borrow."""
    from shared import rewrite_mailbox as rm
    from shared import scale_refs as sr
    rows = []
    for seg in (story_cfg.get("segments") or [])[:1]:     # the hook's picture
        d = rm._dataset(seg) or {}
        for p in d.get("points") or []:
            if p.get("value") is not None:
                rows.append((float(p["value"]), d.get("unit", ""),
                             p.get("label", "")))
    return sr.comparisons(rows)


def _opening_words(story_cfg: dict) -> str:
    """What is already SAID over the opening: the old hook and beat one."""
    segs = story_cfg.get("segments") or []
    return " ".join([story_cfg.get("hook") or "",
                     str(segs[0].get("say") or "") if segs else ""])


def _story_words(story_cfg: dict) -> str:
    return " ".join([story_cfg.get("title") or "", story_cfg.get("hook") or "",
                     story_cfg.get("caption") or "",
                     *[str(s.get("say") or "")
                       for s in story_cfg.get("segments") or []]])


_NOT_NAMES = {"one", "two", "three", "four", "five", "six", "seven", "eight",
              "nine", "ten", "earth", "world", "planet", "sun", "moon",
              "nobody", "everyone", "someone", "this", "that", "these",
              "those", "now", "then", "today", "yesterday", "tomorrow"}


def problems(line: str, story_cfg: dict, allowed: set, label_words: set) -> list:
    """Why this hook may not ship. Empty = it may."""
    from shared import rewrite_mailbox as rm
    out = []
    s = " ".join(str(line or "").split())
    if not s:
        return ["empty"]
    if len(s.split()) > MAX_WORDS + 4:
        out.append("too long")
    # a number must be in the data, or already said by this story's own
    # narration — a hook may repeat what the video goes on to prove
    bad = rm._quantities_ok(s, allowed, _opening_words(story_cfg))
    if bad:
        out.append(f"numbers not in the data: {bad}")
    # `_entities_ok` forgives a sentence's first word, because a rewritten
    # narration line may open on anything. A hook is short enough that its
    # first word is often the name ("Starbucks is hiding..."), so it is
    # checked too — a common opener ("Your", "Every", "Half") is in the
    # punch-up guard's own list of words that are capitalised by position.
    # "France-sized" is France, which the story names; "One", "Earth" and
    # "World" are capitalised by position or are nobody's proper noun.
    ents = [e for e in rm._entities_ok(
                "so " + re.sub(r"(\w)['’](?:s|re|ve|ll|d|m)\b", r"\1",
                               re.sub(r"(\w)-(\w)", r"\1 \2", s)),
                _story_words(story_cfg), label_words)
            if e.lower() not in _NOT_NAMES]
    if ents:
        out.append(f"names the story never uses: {ents}")
    if _SCAM.search(s) or _SHOUT.search(s):
        out.append("scam tell")
    out += garbled(s)
    return out


def _facts_text(facts: list) -> str:
    return "\n".join(
        f"  - {f['value']:,g} {f['unit']}"
        + (f" ({f['label']})" if f.get("label") else "")
        + f" is {f['phrase']}" for f in facts)


def _prompt(story_cfg: dict, n: int, facts: list | None = None) -> str:
    lines = [f"TITLE: {story_cfg.get('title', '')}",
             f"CURRENT HOOK (write better, or it stays): {story_cfg.get('hook', '')}"]
    for i, seg in enumerate(story_cfg.get("segments") or []):
        lines.append(f"BEAT {i + 1}: {seg.get('say', '')}")
    if facts:
        lines.append("TRUE SIZE COMPARISONS (checked — you may use these, "
                     "and no other comparison):\n" + _facts_text(facts))
    return (DOCTRINE + "\n" + "\n".join(lines) +
            f"\n\nWrite {n} different hooks for THIS story, strongest first. "
            "The hook is spoken over BEAT 1's picture, so any number in it "
            "must be one BEAT 1 says — the viewer has to see it on screen. "
            "Return STRICT "
            'JSON: {"hooks": [str, ...]}')


def _ask(prompt: str, brain) -> list:
    raw = brain(prompt) if brain else None
    if not raw:
        return []
    m = re.search(r"\{.*\}", str(raw), re.S)
    try:
        hooks = json.loads(m.group(0)).get("hooks") if m else None
    except Exception:  # noqa: BLE001
        return []
    return [str(h).strip() for h in hooks or [] if str(h).strip()]


def _default_brain(prompt: str):
    try:
        from data_learning import scene_author as sa
        return sa.ask_brain(prompt, model="sonnet", timeout=120)
    except Exception:  # noqa: BLE001
        return None


_LISTEN = """You are scrolling YouTube Shorts. Below are candidate opening lines for one \
video — each one is spoken over its first frame — and the story the video \
tells. Judge them the way a viewer hears them, and as a fact-checker.

A line FAILS if any of these is true:
  - it states a fact, cause, consequence, quantity, "never" or "every" the \
story does not support;
  - it does not make sense heard once at full speed (broken grammar, a \
number of nothing, "your" stuck on something that is not the viewer's, a \
thing "vanished" that did not);
  - it sounds like ad copy or a template nobody would say out loud \
("...and nobody told you", "...shocking everyone", "your town feels it");
  - it is a quiz, a hedge, or vague ("astonishing", "gargantuan").

Then RANK the lines that pass, best first, by one question: which one would \
actually make YOU stop scrolling and watch the next five seconds?

STORY:
{say}

CANDIDATES:
{cands}

Return STRICT JSON: {{"ranking": [<numbers of the passing lines, best \
first>], "why": {{"<n>": "<one line on each line you failed>"}}}}"""


def _say(story_cfg: dict) -> str:
    return "\n".join([str(story_cfg.get("title") or "")] +
                     [str(s.get("say") or "")
                      for s in story_cfg.get("segments") or []])


def _ranking(raw, n: int) -> list | None:
    """The 0-based candidates the listener passed, best first; None = no
    verdict."""
    m = re.search(r"\{.*\}", str(raw or ""), re.S)
    try:
        got = json.loads(m.group(0)).get("ranking") if m else None
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(got, list):
        return None
    out = []
    for k in got:
        try:
            i = int(k) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < n and i not in out:
            out.append(i)
    return out


def listen(cands: list, story_cfg: dict, brain,
           facts: list | None = None) -> list | None:
    """The candidates a scrolling viewer would stop for, best first, each one
    TRUE to the story and a sentence a person would say. Indices into
    `cands`; a candidate left out failed. None = no verdict (fail CLOSED:
    a soft hook is a missed click, a false one is a lie)."""
    if not cands:
        return []
    say = _say(story_cfg)
    if facts:
        say += ("\nALSO TRUE (checked reference sizes):\n"
                + _facts_text(facts))
    raw = brain(_LISTEN.format(
        say=say, cands="\n".join(f"{i + 1}. {c}" for i, c in enumerate(cands)))) \
        if brain else None
    return _ranking(raw, len(cands))


def sharpen(story_cfg: dict, brain=_default_brain, n: int = 6,
            log=print) -> str | None:
    """A better hook for this story, or None to keep the one it has.

    Asks for `n` rewrites, drops every one that fails `problems` or `floor`,
    and has the LISTENER hear the survivors beside the current hook. Returns
    the line it ranks first, or None when that is the current hook, nothing
    survived, or there is no verdict.
    """
    old = str(story_cfg.get("hook") or "").strip()
    why_old = floor(old)
    if why_old:
        # a line under the floor is worth nothing, however loud it is
        log(f"[hook] {old!r} must be rewritten: {why_old[0]}")
    allowed, label_words = evidence(story_cfg)
    facts = scale_facts(story_cfg)
    for f in facts:                 # a checked comparison may be said
        label_words |= {w.lower() for w in re.findall(r"[A-Za-z]+", f["said"])}
        m = re.search(r"more than (\d+) times", f["phrase"])
        if m:
            allowed.add(float(m.group(1)))
    cands = [] if why_old else [old]
    for cand in _ask(_prompt(story_cfg, n, facts), brain):
        why = problems(cand, story_cfg, allowed, label_words) + floor(cand)
        if why:
            log(f"[hook] refused {cand!r}: {'; '.join(dict.fromkeys(why))}")
        elif cand not in cands:
            cands.append(cand)
    if not cands or cands == [old]:
        log(f"[hook] kept {old!r}: no rewrite cleared the floor")
        return None
    rank = listen(cands, story_cfg, brain, facts)
    if rank is None:
        log(f"[hook] kept {old!r}: the listener gave no verdict")
        return None
    for i, c in enumerate(cands):
        if i not in rank:
            log(f"[hook] refused {c!r}: the listener failed it")
    if not rank:
        log(f"[hook] kept {old!r}: the listener passed nothing")
        return None
    best = cands[rank[0]]
    if best == old:
        log(f"[hook] kept {old!r}: the listener ranked it first")
        return None
    log(f"[hook] {old!r} -> {best!r}")
    return best
