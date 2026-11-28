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
the reason and who must fix them; the test fails once an entry is no longer needed, so the list only shrinks.

THE SHAPE OF A STORYBOARD LINE (2026-11-25). The lava short's round-7 lines each listed six to eight events and props
(a car door slapped, a baton, a hose, a sandbag that dropped and was never seen again, a focus rack and back) and the
board grades FOUR STILLS against every word of the line: whatever it names and a still does not show is a hard fail.
The lines that passed the same day said one action and one consequence. So a storyboard line is written as what four
stills show, BEFORE / ACTION / RESULT / REACTION, and shape_problems() refuses, per line:
  EVENTS  more than MAX_EVENTS things happening (clauses), more than MAX_BEATS sentences, or more than MAX_WORDS words
          after the "(place; camera):" opening. Measured on the lava lines: the five that were on the board on
          2026-11-25 (shots 3 and 4 passed) run 4-5 events, 3 sentences, 57-77 words; the five round-7 lines
          (commit b22987e5d, all failed) run 6-8 events, 4-6 sentences, 87-111 words.
  CAMERA  a camera move in the action ("the focus racks", "cut to", "zooms in"): the camera is said ONCE, in the
          opening brackets, and it is the camera the shot renders; four stills cannot show a move.
  PROP    a thing that leaves his hands (dropped, thrown, let go) and is not named in the line's last sentence:
          a prop that just disappears. The stills are checked for the same thing by store/preflight3d.py.
RECIPE is the staging that passes; the README and the proof loop's reviser are given it word for word."""
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


# ---------------------------------------------------------------- THE SHAPE OF A LINE (2026-11-25)
MAX_EVENTS = 5     # before, action, result, reaction, and one more: lava's passing lines have 4-5, its failed ones 6-8
MAX_BEATS = 4      # sentences / semicolon parts: one per still
MAX_WORDS = 80     # lava's passing lines run 57-77 words of action, its failed ones 87-111
# written before the shape rule and never restaged under it; each says why, and the test fails when one passes
SHAPE_BEFORE = {
    "cardrewards": "rendered 2026-11-18; beat 2 is five semicolon parts; its storyboard is not judged again unless the short is remade, and whoever remakes it rewrites the lines first",
    "helium": "parked 2026-11-17 at the hard cap with 83- and 93-word lines; whoever takes it up again rewrites each line as one action and one consequence",
    "lightning": "posted 2026-11-23 from lines of 108 to 166 words with hard cuts written in; never built again, the same reason it is grandfathered in store/story_gate.py",
}
EVENT = re.compile(r"(?<!\d)[.;](?!\d)|,\s*(?:and|then|where|as|while|until)\b|"
                   r"\b(?:and|then|as|while|until)\s+(?=(?:he|she|it|they|the|a|an|his|its|data|lava|steam|one|two|three)\b)", re.I)
BEAT = re.compile(r"(?<!\d)[.;](?!\d)")
CAMERA_MOVE = re.compile(r"\b(the focus (racks?|pulls?|shifts?)|racks? focus|focus racks?|(hard |jump |match |smash )?cuts? (to|on|back)|hard cuts?|"
                         r"zooms? (in|out|on)|the (camera|lens) (pans|moves|cranes|pulls|pushes|tracks|swings|follows|tilts|rushes|cuts|racks|walks|flies|drops|rises)|cranes? (up|back|down|over)|doll(y|ies) (in|out|back)|pulls? back to (reveal|show)|"
                         r"whip[- ]pans?)\b", re.I)
LEAVES = re.compile(r"\b(?:drops?|throws?|tosses|toss|flings?|hurls?|lets? go of|loses?)\s+(?:the|his|a|an)\s+(?:[a-z'-]+\s+){0,2}?([a-z'-]+)"
                    r"(?=\s+(?:and|into|onto|on|in|to|at|down|over|off|away|behind|from)\b|\s*[,;.]|\s*$)", re.I)
BODY = {"hand", "hands", "arm", "arms", "head", "jaw", "shoulders", "eyes", "gaze", "fist", "fists", "weight", "balance", "footing", "grip"}

RECIPE = """THE STAGING THAT PASSES THE BOARD (lava shots 3 and 4, 2026-11-25; every board is four stills at phone size):
- write the line as what the four stills show: BEFORE, the ACTION, its RESULT, his REACTION. One action, one consequence.
- a CLOSE shot: Data fills a third of the frame or more, and the event is right beside him or in front of him, mid-frame.
- nothing that is the subject touches a frame edge in any still; if it does not fit, come closer to less of it.
- Data stands three-quarter to the lens: face and chest to us, never in profile for the whole shot, never his back.
- the four stills are clearly different from each other: a new state in each, not one pose held.
- one grade across the stills: the same light and colour in all four unless the line says the light changes.
- his feet are planted on the ground in every still (a jump is in the line or it is not in the shot).
- every prop the line names is in the result: in his hand, on the ground where it fell, or changed by what happened.
- say the camera once, in the opening brackets, and render that camera: no camera move inside the action."""


def parts(line):
    """one storyboard line as (name, place, camera, action): "3 the wall holds (the lava side ...; low, looking at the
    wall): the driver ..." -> name, the words before the last ';' in the opening brackets, the words after it, and
    everything after the colon that closes the opening. A line with no brackets is all action."""
    b = re.sub(r"^\s*\d+\s*", "", str(line)); depth = 0; open_at = close_at = None
    for i, ch in enumerate(b):
        if ch == "(":
            if depth == 0 and open_at is None: open_at = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and close_at is None: close_at = i
        elif ch == ":" and depth == 0:
            inner = b[open_at + 1:close_at] if open_at is not None and close_at is not None and close_at < i else ""
            name = (b[:open_at] if inner else b[:i]).strip()
            place, _, cam = inner.rpartition(";") if ";" in inner else (inner, "", "")
            return name, place.strip(), cam.strip(), b[i + 1:].strip()
    return "", "", "", b.strip()


def events(action):
    """the things that happen in a line's action, one per clause"""
    return [c.strip() for c in EVENT.split(action) if c and c.strip()]


def beats(action):
    return [c.strip() for c in BEAT.split(action) if c and c.strip()]


def shape_problems(line):
    """what makes ONE storyboard line more than four stills can show, as short sentences ([] when it has the shape)"""
    _, _, _, action = parts(line)
    ev, bt, words, out = events(action), beats(action), len(action.split()), []
    if len(ev) > MAX_EVENTS or len(bt) > MAX_BEATS or words > MAX_WORDS:
        out.append(f"EVENTS: {len(ev)} things happen in {len(bt)} sentences and {words} words (at most {MAX_EVENTS}, {MAX_BEATS} and "
                   f"{MAX_WORDS}): four stills show ONE action and ONE consequence (before, action, result, reaction). Cut it to that; "
                   f"every extra event is a promise a still has to keep")
    for move in sorted({m.group(0).lower() for m in CAMERA_MOVE.finditer(action)}):
        out.append(f"CAMERA: '{move}' is a camera move inside the action: say the camera once, in the opening brackets "
                   f"\"(place; camera)\", and render that camera")
    last_at = action.rfind(bt[-1]) if bt else 0
    for m in LEAVES.finditer(action):
        thing = m.group(1).lower()
        if BODY & set(re.findall(r"[a-z'-]+", m.group(0).lower())):
            continue                                   # "throws his arms wide" is a pose, not a prop
        if not re.search(rf"\b{re.escape(thing)}s?\b", action[max(m.end(), last_at):], re.I):
            out.append(f"PROP: '{m.group(0)}': the {thing} leaves his hands and the line's last sentence never names it again: "
                       f"a prop that just disappears. Say where it ends up in the result, or take it out of the shot")
    return out


def shape(script):
    """[(where, problem)] over a script's storyboard lines"""
    return [(f"storyboard beat {i}", p) for i, b in enumerate(script.get("storyboard") or [], 1) for p in shape_problems(b)]


def shape_held(story):
    """True when the shape rule binds this story (not posted, not written before the rule)"""
    return story not in POSTED and story not in SHAPE_BEFORE


def held(story):
    """True when the lint binds this story (not posted, not grandfathered)"""
    return story not in POSTED and story not in GRANDFATHERED
