"""THE STORYBOARD LINT: a beat's payoff is carried by a BIG PROP or a BIG ACTION, never by a subtle face or a tiny change
(2026-11-14). Every saffron round that failed on the judge had written the failure into its own storyboard first: "the
needle barely twitches", "a wry, unimpressed look", "he looks down at it, then up at us, alarmed". A phone viewer cannot
see a needle flick 2% of the frame or read a brow at 9 cm; the judge said so every round, and each round was ~40
minutes of proof render. This says it before the first frame.

Two rules, over every storyboard beat and every `ideas` entry of a story's script.json:
  TINY   a beat whose payoff is a small change ("barely", "slightly", "subtle", "hardly", "faint", "a twitch") must
         name a big carrier IN THE SAME CLAUSE: what barely moves is not the payoff, what it barely moves against is.
  FACE   a beat that leans on a reaction ("reacts", "looks alarmed / worried / unimpressed ...", "a wry look", "raises
         a brow") must name a big carrier SOMEWHERE in the beat: a face may close a beat, it cannot carry one.
A big carrier is a big thing ("a big / huge / giant / whole / heap / pile / wall of ...") or a big action (falls,
crashes, pours, spills, fills, slams, rings, races, topples, bursts, floods, collapses, wilts, flops ...).

Run by store/shots.py on every shot of a story that is not POSTED (STAGING=strict fails it, before anything renders)
and held offline by tests/test_data3d_storyboard_lint.py. GRANDFATHERED stories predate the lint and are named with
the reason and who must fix them; the test fails once an entry is no longer needed, so the list only shrinks."""
import re

POSTED = {"checkout", "banana"}          # already on the channel: the same set the ending-question test exempts
GRANDFATHERED = {}                       # saffron came off 2026-11-14: beat 2 rewritten around a giant crocus

TINY = re.compile(r"\b(barely|slightly|subtl[ey]|subtlety|hardly|faint(ly)?|imperceptibl[ey]|a tiny (change|move|flick|twitch)|"
                  r"twitch(es|ing)?|flickers?|moves? a little|a little (more|less))\b", re.I)
FACE = re.compile(r"\b(react(s|ing|ion)?|looks?\b[^.;:]{0,30}?\b(alarmed|worried|unimpressed|surprised|sad|shocked|confused|skeptical|"
                  r"sceptical|wry|nervous|scared|pleased|happy|disappointed|puzzled|annoyed|horrified)|"
                  r"(a |an |his )?(wry|worried|alarmed|unimpressed|surprised|sad|shocked|skeptical|knowing|puzzled|nervous)\s+"
                  r"(look|face|expression|glance|smile|frown|smirk)|raises? (an |one |his )?(eye)?brows?|frowns?|winces?|"
                  r"his face (falls|drops|changes))\b", re.I)
BIG = re.compile(r"\b(big|bigger|huge|giant|enormous|massive|towering|whole|entire|heap(s|ed|ing)?|piles?|mountain|wall of|"
                 r"stacks?|row of|flood(s|ing)?|crash(es|ing)?|topples?|falls?|falling|spill(s|ing)?|pours?|pouring|burst(s)?|"
                 r"explodes?|slams?|rings?|ringing|races?|racing|spins?|spinning|fills?|filling|empties|collapses?|shuts?|"
                 r"wilts?|flops?|tips?|shoves?|hauls?|knocks? down|rolls? in|blinks? red|fires?)\b", re.I)
CLAUSE = re.compile(r"[;:.]|,\s*(?:then|but|and then|while)\b|\bthen\b")


def clauses(text):
    return [c.strip() for c in CLAUSE.split(text) if c and c.strip()]


def beat_problems(text):
    """the rule(s) one storyboard beat or idea breaks, as short sentences ([] when it is carried by something big)"""
    out = []
    for c in clauses(text):
        m = TINY.search(c)
        if m and not BIG.search(c.replace(m.group(0), " ")):
            out.append(f"TINY: '{c}' -- its payoff is a {m.group(0)!r} change with nothing big in the same clause carrying it")
    face = FACE.search(text)
    if face:
        rest = text.replace(face.group(0), " ")
        if not BIG.search(rest):
            out.append(f"FACE: the beat leans on {face.group(0)!r} and names no big prop or big action to carry it")
    return out


def problems(script):
    """[(where, problem)] over a script's storyboard and ideas"""
    out = []
    for i, b in enumerate(script.get("storyboard") or [], 1):
        out += [(f"storyboard beat {i}", p) for p in beat_problems(b)]
    for i, b in enumerate(script.get("ideas") or [], 1):
        out += [(f"idea {i}", p) for p in beat_problems(b)]
    return out


def held(story):
    """True when the lint binds this story (not posted, not grandfathered)"""
    return story not in POSTED and story not in GRANDFATHERED
