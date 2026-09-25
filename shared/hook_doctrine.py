"""THE HOOK — the first sentence we say, written like a 2000s download-site ad.

Operator, 2026-09-25: *"Our intros need to be 2000s, ad on a fucking LimeWire
type shit ... real clickbaity. And not like scammy clickbaity"* — and, of the
rainforest story: *"why a forest the size of France disappeared ... You're
gonna die because the Amazon rainforest lost a million trees. Shit like
that."*

The queue's hooks were polite: "Your nose can detect an astonishing number of
scents", "Why do some clocks even still change?", "Which animal could crush a
bowling ball in its jaws?". A quiz question, a hedge, a fact read aloud. This
module is the one place that says what a hook is now, scores it, and — at
render time, for every story in the queue, not just new ones — has the brain
rewrite any hook that does not clear the bar.

THE LINE BETWEEN CLICKBAIT AND A SCAM is the same one the rest of this repo
already holds: EXAGGERATE THE FEELING, NEVER THE FACT. Every number in a new
hook must come from the story's own data (`rewrite_mailbox._quantities_ok`),
it may not bring a name from outside (`rewrite_mailbox._entities_ok`), and a
hook that fails either is thrown away, however good it sounds. Those checks
are REUSED, not re-written: they are what already guards a ChatGPT rewrite,
and a second copy is how the two would drift.

The score builds on `scripts/hook_director.grade_line` (curiosity, stakes,
a number, you) — the curiosity channel's gate — and adds what that grader
never asked for: the viewer is the one in danger, the verb is visceral, the
line is short, and it is not a quiz.
"""
from __future__ import annotations

import json
import re

#: What the brain is told. Kept here so the forge and the render-time
#: sharpener ask for the SAME thing.
DOCTRINE = """\
THE HOOK is the first sentence the viewer hears, over the first frame. Write \
it like a 2000s download-site ad or a tabloid front page: it has to stop a \
thumb mid-scroll. Real clickbait — never a scam.

DO:
  - Put the VIEWER in it. "You", "your" — their money, their food, their \
body, their town, their kids. Make it their problem.
  - Lead with the shock. The most alarming TRUE consequence of the data, \
first word to last. No warm-up.
  - Use visceral verbs: wiped out, vanished, exploded, gutted, doubled, \
swallowed, bleeding, gone, dying, erased, crushed.
  - Leave a gap the video fills: "...and nobody noticed", "...here's who's \
paying", "...and it's speeding up".
  - Say ONE number from the data, the loudest one, in the words a person \
would shout ("11 million bags", "more than double", "a third of them").
  - Short. 6 to 14 words. One sentence, two at most.

NEVER:
  - A number that is not in the data. Not rounded differently, not \
converted into a bigger one, not a comparison the data does not contain.
  - A name — country, company, person — that the story does not already use.
  - A fact that is not true. Exaggerate the FEELING, never the FACT: "your \
coffee is being wiped out" is a feeling about a real 24% cut; "coffee will \
be extinct by 2030" is a lie.
  - Quiz or trivia openers: "Which animal...", "Can you guess...", "Did you \
know...", "Have you ever...". A question is fine only if it is an accusation \
("Why is your coffee twice the price?").
  - Hedges: might, may, possibly, perhaps, somewhat, a bit, arguably.
  - Scam tells: "click", "link", "free", "guaranteed", "doctors hate", \
"one weird trick", ALL CAPS.

Examples of the voice (the numbers here are illustrations — use yours):
  "Your coffee just got gutted: 11 million bags, gone overnight."
  "A forest bigger than your whole state vanished — and you paid for it."
  "You're breathing air from a sky that lost a third of its birds."
  "Your rent doubled. Your paycheck didn't. Here's the number."
"""

#: A hook at or above this does not get rewritten.
BAR = 7
MAX_WORDS = 16

_VISCERAL = re.compile(
    r"\b(wip\w+ out|vanish\w*|explod\w*|gutt\w*|doubl\w*|tripl\w*|swallow\w*|"
    r"bleed\w*|gone|dying|dies|died|dead|kill\w*|erase\w*|crush\w*|collaps\w*|"
    r"disappear\w*|destroy\w*|stole\w*|steal\w*|drown\w*|burn\w*|starv\w*|"
    r"poison\w*|shrink\w*|shrank|plung\w*|crash\w*|lost|losing|lose|broke|"
    r"skyrocket\w*|soar\w*|slash\w*|choke\w*|devour\w*|melt\w*|empt\w*)\b",
    re.I)
_QUIZ = re.compile(
    r"^\s*(which|what|who|can you|could you|bet you|guess|did you know|have "
    r"you ever|you won'?t believe|ever wonder|here'?s a fun)\b", re.I)
_HEDGE = re.compile(r"\b(might|may|possibly|perhaps|somewhat|a bit|arguably|"
                    r"kind of|sort of|some say)\b", re.I)
_SCAM = re.compile(r"\b(click|link|free|guaranteed|doctors hate|one weird "
                   r"trick|subscribe)\b", re.I)
_SHOUT = re.compile(r"\b[A-Z]{4,}\b")
_ACCUSE = re.compile(r"^\s*why (is|are|did|do|does) (your|you)\b", re.I)


def punch(line: str) -> dict:
    """0-10: how hard the line stops a scroll, and why.

    The first five points are `hook_director.grade_line` unchanged — one
    grader for "is there a curiosity gap, stakes, a number, a you". The
    other five are this doctrine's own, and the penalties can take a line
    back to zero: a quiz, a hedge or a scam tell each cost more than any
    single virtue earns.
    """
    from scripts import hook_director as hd
    s = " ".join(str(line or "").split())
    base = hd.grade_line(s)
    score, notes = base["score"], list(base["hits"])
    words = len(s.split())
    if hd.YOU.search(s):
        score += 2
        notes.append("the viewer is in it")
    if _VISCERAL.search(s):
        score += 2
        notes.append("visceral verb")
    if 5 <= words <= 14:
        score += 1
        notes.append("short")
    if words > MAX_WORDS:
        score -= 2
        notes.append(f"long ({words} words)")
    if _QUIZ.match(s) and not _ACCUSE.match(s):
        score -= 3
        notes.append("quiz opener")
    if _HEDGE.search(s):
        score -= 2
        notes.append("hedge")
    if _SCAM.search(s) or _SHOUT.search(s):
        score -= 4
        notes.append("scam tell")
    for g in base["gates"]:
        score -= 2
        notes.append(g)
    return {"score": max(0, min(10, score)), "notes": notes, "words": words}


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
    return out


def _facts_text(facts: list) -> str:
    return "\n".join(
        f"  - {f['value']:,g} {f['unit']}"
        + (f" ({f['label']})" if f.get("label") else "")
        + f" is {f['phrase']}" for f in facts)


def _prompt(story_cfg: dict, n: int, facts: list | None = None) -> str:
    lines = [f"TITLE: {story_cfg.get('title', '')}",
             f"CURRENT HOOK (too soft): {story_cfg.get('hook', '')}"]
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


_VERIFY = """You are a fact-checker for a YouTube Shorts channel. Below is \
a story's narration and some candidate opening lines. Clickbait TONE is \
allowed — drama, "you", exaggerated feeling. What is NOT allowed is a FACT \
the narration does not support: a cause, a consequence, a quantity, a date, \
a "never" or an "every" the story does not back up.

NARRATION:
{say}

CANDIDATES:
{cands}

Return STRICT JSON: {{"supported": [<the numbers of the candidates whose every \
factual claim is supported>], "why": {{"<n>": "<one line, for the ones you \
refused>"}}}}"""


def verified(cands: list, story_cfg: dict, brain,
             facts: list | None = None) -> list:
    """The candidates whose every FACT the story's own narration supports,
    in their original order. Fails CLOSED: no brain, no verdict, nothing
    changes — a soft hook is a missed click, a false one is a lie."""
    if not cands:
        return []
    say = "\n".join([str(story_cfg.get("title") or "")] +
                    [str(s.get("say") or "")
                     for s in story_cfg.get("segments") or []])
    if facts:
        say += ("\nALSO TRUE (checked reference sizes):\n"
                + _facts_text(facts))
    raw = brain(_VERIFY.format(
        say=say, cands="\n".join(f"{i + 1}. {c}" for i, c in enumerate(cands))))
    m = re.search(r"\{.*\}", str(raw or ""), re.S)
    try:
        ok = json.loads(m.group(0)).get("supported") if m else None
    except Exception:  # noqa: BLE001
        return []
    keep = set()
    for k in ok or []:
        try:
            keep.add(int(k) - 1)
        except (TypeError, ValueError):
            continue
    return [c for i, c in enumerate(cands) if i in keep]


def sharpen(story_cfg: dict, brain=_default_brain, n: int = 6,
            log=print) -> str | None:
    """A harder hook for this story, or None to keep the one it has.

    Keeps the current hook when it already clears `BAR`. Otherwise asks for
    `n` rewrites, drops every one that fails `problems`, and returns the
    highest-punch survivor — only if it beats the current hook.
    """
    old = str(story_cfg.get("hook") or "").strip()
    was = punch(old)
    if was["score"] >= BAR:
        return None
    allowed, label_words = evidence(story_cfg)
    facts = scale_facts(story_cfg)
    for f in facts:                 # a checked comparison may be said
        label_words |= {w.lower() for w in re.findall(r"[A-Za-z]+", f["said"])}
        m = re.search(r"more than (\d+) times", f["phrase"])
        if m:
            allowed.add(float(m.group(1)))
    passed = []
    for cand in _ask(_prompt(story_cfg, n, facts), brain):
        why = problems(cand, story_cfg, allowed, label_words)
        if why:
            log(f"[hook] refused {cand!r}: {'; '.join(why)}")
            continue
        p = punch(cand)["score"]
        if p > was["score"]:
            passed.append((p, cand))
    passed.sort(key=lambda t: -t[0])          # stable: brain order breaks ties
    top = [c for _, c in passed[:3]]
    true = verified(top, story_cfg, brain, facts)
    for c in top:
        if c not in true:
            log(f"[hook] refused {c!r}: a fact the story does not support")
    best, best_p = None, was["score"]
    for p, c in passed:
        if c in true:
            best, best_p = c, p
            break
    if best:
        log(f"[hook] {was['score']}->{best_p}: {old!r} -> {best!r}")
    else:
        log(f"[hook] kept {old!r} (punch {was['score']}): no rewrite beat it")
    return best
