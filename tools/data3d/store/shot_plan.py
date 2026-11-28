"""THE SHOT PLAN: every shot is written down as its prop, where Data stands, ONE action, ONE consequence and FOUR
different stills BEFORE a shotN.py exists, and code refuses a plan that breaks the staging that passes (2026-11-26).

The operator, 2026-11-26: "this needs to be an autonomous system that can pump out 1,000 of these", and, of shots that
take 4 to 18 judge rounds each, "what are we not fixing here? Because clearly something is continuously not getting
fixed." What was not fixed: a shot started as a blank Blender file. The storyboard line said what happens; nothing
said which prop the shot is ON, where he stands to it, what his hands are on, or what each of the board's four stills
shows that the one before did not. Those were decided in the shot's code, found wrong by the panel, and decided again.
The shots that passed (lava 3, 4, 5) share one recipe (store/boardlint.py RECIPE); this makes it the starting point.

A story's plan is stories/<story>/plan.json, a sibling of script.json:

  {"shots": [ {                                  one per spoken line, in order
     "prop": "lantern",                          the ONE thing the shot is close on (a name in "props")
     "props": [{"name": "lantern", "objects": ["lantern"], "whole": true, "built_as": "a brass storm lantern, glass, wick, wire handle"}],
                                                 every thing the stills turn on: `objects` are its object-name prefixes
                                                 in the scene (store/recipe_check.py measures them), `whole` false only
                                                 for a thing that runs past the frame by design (a river, a wall)
     "framing": "close",                         close | medium; never wide
     "data": {"stands": "beside", "side": "left", "frame_h": 0.36},
                                                 beside | at the foot of | in front of the prop; which side of the
                                                 frame he is on; how tall he stands in it (a third or more)
     "action": "he hangs the lit lantern on the hook by his window",        ONE action
     "consequence": "the dark window lights up warm",                        ONE consequence
     "says_still": 3,                            the still (1-4) a stranger with the sound off reads the spoken line from
     "stills": [                                 the board's four stills (store/staging.py KEYS_AT), in order
        {"event": "before",   "shows": "...", "hands": "lantern", "new": []},
        {"event": "action",   "shows": "...", "hands": "lantern", "new": [{"what": "lantern", "how": "moves", "cause": "he lifts it to the hook"}]},
        {"event": "result",   "shows": "...", "hands": "free",    "new": [{"what": "window", "how": "lights", "cause": "the lantern hangs beside it"}]},
        {"event": "reaction", "shows": "...", "hands": "free",    "new": [{"what": "data", "how": "pose", "cause": "he turns to us and opens his hands"}]}
     ]} ]}

problems(story, script) is what store/shots.py refuses to build a shot on (with the story gate and the storyboard
lint); store/recipe_check.py then measures the same plan on the built scene; store/recipe_stage.py places Data and
the lens from it. `python shot_plan.py check STORY` prints the problems; `python shot_plan.py blank STORY` prints an
empty plan to fill in for a story's script."""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boardlint, story_gate

STORIES = HERE.parent / "stories"
NAME = "plan.json"

EVENTS = ("before", "action", "result", "reaction")
FRAMING = ("close", "medium")
STANDS = ("beside", "at the foot of", "in front of")
SIDES = ("left", "right")
MIN_FRAME_H = 0.33       # "Data at about a third of frame height or more"
MAX_FRAME_H = 0.6        # taller than this and the event has no room beside him: a talking head
SAME_STILL = 0.6         # two stills whose words overlap this much (Jaccard over content words) are one picture
COVER = 0.5              # of a claim's content words that one still's `shows` must carry
SAYS_WORDS = 2           # content words the says_still shares with the spoken line
# what a thing can do between two stills. The first set is what a box can show (store/recipe_check.py MEASURED measures
# them in the scene); the second is seen in the picture only (the pre-flight's look ticks it)
HOW_BOX = ("moves", "comes", "goes", "grows", "falls", "rises", "breaks", "opens")
HOW_LOOK = ("lights", "darkens", "burns", "steams", "fills", "empties", "changes")
SCALED = re.compile(r"\b(bigger|closer|nearer|larger|zoom(s|ed)?|push(es)? in|same)\b", re.I)   # not a new event: one pose scaled
WIDE = re.compile(r"\b(wide|establishing|aerial|drone|bird'?s[- ]eye|long shot|from far|far off|from a distance|from above the (town|city|valley))\b", re.I)
NEAR = re.compile(r"\b(close|medium|level with him|beside him|at his (side|shoulder|feet)|low|a little above him)\b", re.I)
TOY = re.compile(r"\b(box|boxes|cube|cone|cones|sprite|card|cutout|cut-out|plane|blob|placeholder|slab|toy|capsule)\b", re.I)
STOP = set("a an the and or of to in on at by for from with into onto over under up down off out as is are was it its his her "
           "he she they them their this that then while until so but not no one two side still stills us we him data driver "
           "there here very just now again more most some each every both all".split())

# EVERY WORD A TEXT PROMISES HANGS ON A THING ONE STILL LISTS AS VISIBLE (2026-11-26). "Promised but not shown" is the
# most common hard defect in the round reports (249 of 1,225 lines). Half a claim's words somewhere in a still's `shows`
# sentence let a noun ride through on its neighbours. So each still also lists what a stranger can point at in it:
#   "visible": [{"prop": <one of the shot's props, or "data">, "as": "the words it is seen as", "count": n, "reads": "4,000"}]
# (a bare prop name is short for {"prop": name}). Every content word of the storyboard line's action and of the spoken
# line is a word of ONE still's visible things, or is declared in the shot's `unseen` as a word no picture carries (a
# verb the action or consequence already says, a how, a when). store/recipe_check.py then MEASURES that each listed
# prop is in the frame on that still. A number is seen only as a count a stranger can make in one still (COUNT_MAX or
# fewer of a thing, `count`) or on something in the world that reads it (`reads`: a sign, a gauge, a scale).
COUNT_MAX = 12           # things a stranger can count in one still
UNSEEN_WHY = ("verb", "how", "when")
UNSEEN_SHARE = {"FOR": 0.5, "SAYS": 0.7}   # of a text's content words that may be declared unseen, at most: a storyboard line is
                         # things to see; a spoken line also carries the telling ("almost nobody moved back. Would you?")

# stories whose shots were staged before the plan existed. A plan may be partial for these (a shot's entry null) and is
# not binding; each says why. The test fails when an entry is no longer needed, so the list only shrinks.
PLAN_BEFORE = {
    "checkout": "posted 2026-11-11; never built again",
    "banana": "posted 2026-11-13; never built again",
    "saffron": "rendered 2026-11-15; its shots are not staged again unless the short is remade, and a remake starts from a plan",
    "helium": "parked 2026-11-17 at the hard cap; whoever takes it up again writes the plan first",
    "cardrewards": "rendered 2026-11-18; a remake starts from a plan",
    "lightning": "posted 2026-11-23; never built again",
    "honey": "parked after board round 3 (2026-11-23); whoever takes it up again writes the plan first",
}


def held(story):
    """True when a full, valid plan is required before a shot of this story is built"""
    return story not in PLAN_BEFORE


def load(story):
    try:
        v = json.loads((STORIES / story / NAME).read_text())
        return v if isinstance(v, dict) and isinstance(v.get("shots"), list) else None
    except (OSError, ValueError):
        return None


def shot(story, n):
    """the plan of shot n (1-based), or None"""
    p = load(story)
    if not p or not 0 < n <= len(p["shots"]):
        return None
    s = p["shots"][n - 1]
    return s if isinstance(s, dict) else None


def words(text):
    """the content words of a phrase, crudely stemmed: what two phrases must share to be about the same thing"""
    out = set()
    for w in re.findall(r"[a-z0-9']+", str(text or "").lower()):
        w = w.strip("'")
        if w in STOP or len(w) < 2:
            continue
        for suf in ("ing", "ed", "es", "s"):
            if len(w) > len(suf) + 3 and w.endswith(suf):
                w = w[:-len(suf)]; break
        out.add(w)
    return out


def cover(claim, text):
    """the share of a claim's content words that `text` carries"""
    c = words(claim)
    return len(c & words(text)) / len(c) if c else 1.0


def shot_problems(p, line="", says="", last=False):
    """what ONE shot's plan breaks, as short sentences ([] when it has the recipe's shape). line / says: the shot's
    storyboard line and spoken line, whose promises the stills must carry"""
    out = []
    if not isinstance(p, dict):
        return ["PLAN: no plan for this shot: write its prop, where he stands, one action, one consequence and four stills"]
    props = [q for q in p.get("props") or [] if isinstance(q, dict) and q.get("name")]
    names = {q["name"] for q in props}
    # ---- the prop
    if not props:
        out.append("PROP: the shot names no prop: `props` lists every thing the stills turn on, `prop` the one the shot is close on")
    elif p.get("prop") not in names:
        out.append(f"PROP: `prop` {p.get('prop')!r} is not one of the shot's props {sorted(names)}: name the ONE thing the shot is close on")
    for q in props:
        if not q.get("objects"):
            out.append(f"PROP: '{q['name']}' names no `objects` (its object-name prefixes in the scene): a prop nothing can find cannot be measured")
        built = str(q.get("built_as") or "")
        if len(words(built)) < 3:
            out.append(f"LOOK: '{q['name']}' does not say what it is `built_as` (the real thing and its parts, three words or more): "
                       f"a prop with no parts is a toy on the board")
        elif TOY.search(built):
            out.append(f"LOOK: '{q['name']}' is built as {TOY.search(built).group(0)!r}: a flat, toy or stand-in shape beside a realistic set "
                       f"is OFF THE LOOK; say the real thing and its parts")
    # ---- the framing
    if p.get("framing") not in FRAMING:
        out.append(f"FRAMING: `framing` is {p.get('framing')!r}: a shot is {' or '.join(FRAMING)}, on the prop; a wide shot fails the board")
    _n, _place, camera, action_line = boardlint.parts(line)
    if camera and WIDE.search(camera) and not NEAR.search(camera):
        out.append(f"FRAMING: the storyboard line's camera is '{camera}': a wide or establishing shot as the only framing. "
                   f"Say a close camera in the opening brackets and put the far thing beside him, or in the result still's background")
    d = p.get("data") if isinstance(p.get("data"), dict) else {}
    if d.get("stands") not in STANDS:
        out.append(f"DATA: `data.stands` is {d.get('stands')!r}: he stands {', '.join(STANDS)} the prop, never with the event behind him")
    if d.get("side") not in SIDES:
        out.append(f"DATA: `data.side` is {d.get('side')!r}: say which side of the frame he is on ({' or '.join(SIDES)}); the event takes the other")
    h = d.get("frame_h")
    if not isinstance(h, (int, float)) or isinstance(h, bool) or not MIN_FRAME_H <= h <= MAX_FRAME_H:
        out.append(f"DATA: `data.frame_h` is {h!r}: he stands {MIN_FRAME_H} to {MAX_FRAME_H} of the frame height (a third or more, with room "
                   f"for the event beside him)")
    # ---- one action, one consequence
    for key in ("action", "consequence"):
        t = str(p.get(key) or "").strip()
        ev = boardlint.events(t)
        if len(words(t)) < 2:
            out.append(f"{key.upper()}: the shot names no {key}: ONE {key}, in a clause")
        elif len(ev) > 1:
            out.append(f"{key.upper()}: {len(ev)} things happen in '{t}': ONE {key} per shot; the rest is another shot or is cut")
    # ---- four different stills
    st = p.get("stills") if isinstance(p.get("stills"), list) else []
    st = [s if isinstance(s, dict) else {} for s in st]
    if [s.get("event") for s in st] != list(EVENTS):
        out.append(f"STILLS: the stills are {[s.get('event') for s in st]}: exactly four, in order {list(EVENTS)}, one per board still")
        return out
    for i, s in enumerate(st, 1):
        if len(words(s.get("shows"))) < 3:
            out.append(f"STILLS: still {i} ({s['event']}) does not say what it `shows` (what a stranger could point at, three words or more)")
        hd = s.get("hands")
        if hd != "free" and hd not in names:
            out.append(f"HANDS: still {i} puts his hands on {hd!r}: `hands` is \"free\" or one of the shot's props {sorted(names)}")
    for i in range(4):
        for j in range(i + 1, 4):
            a, b = words(st[i].get("shows")), words(st[j].get("shows"))
            if a and b and len(a & b) / len(a | b) > SAME_STILL:
                out.append(f"STILLS: stills {i + 1} and {j + 1} show the same thing in nearly the same words: four DIFFERENT events, "
                           f"not one picture repeated")
    if st[0].get("new"):
        out.append("STILLS: still 1 is the BEFORE: nothing is new in it yet (`new` is empty)")
    sig = []
    for i, s in enumerate(st[1:], 2):
        new = [c for c in s.get("new") or [] if isinstance(c, dict)]
        if not new:
            out.append(f"STILLS: still {i} ({s['event']}) names nothing `new`: say what is visibly different from still {i - 1} "
                       f"(a prop that moves, comes, goes, grows, breaks, lights; or his pose)")
        for c in new:
            what, how, cause = c.get("what"), str(c.get("how") or ""), str(c.get("cause") or "").strip()
            if what == "data":
                if how != "pose":
                    out.append(f"STILLS: still {i}: what is new about Data is his `pose`, not {how!r}"
                               + (": the same pose bigger or nearer is one pose scaled, not a new event" if SCALED.search(how) else ""))
            elif what not in names:
                out.append(f"STILLS: still {i} changes {what!r}, which is not one of the shot's props {sorted(names)}: declare it or take it out")
            elif how not in HOW_BOX + HOW_LOOK:
                out.append(f"STILLS: still {i}: '{what}' {how!r} is not a change a still shows ({', '.join(HOW_BOX + HOW_LOOK)})"
                           + (": the same thing bigger or nearer is one picture scaled" if SCALED.search(how) else ""))
            if what != "data" and not cause:
                out.append(f"CAUSE: still {i}: '{what}' {how} with no `cause`: a thing that changes with no cause shown floats, pops or teleports")
            if SCALED.search(cause) and what == "data":
                out.append(f"STILLS: still {i}: his new pose is '{cause}': nearer or bigger is the same pose scaled")
        sig.append(sorted((str(c.get("what")), str(c.get("how"))) for c in new))
    if len(sig) == 3 and sig[0] and sig[0] == sig[1] == sig[2]:
        out.append(f"STILLS: stills 2, 3 and 4 each change the same thing the same way {sig[0]}: one event three times; "
                   f"the action, its result and his reaction are three different events")
    world = [c for s in st[2:] for c in s.get("new") or [] if isinstance(c, dict) and c.get("what") in names]
    if not [c for c in st[2].get("new") or [] if isinstance(c, dict) and c.get("what") in names]:
        out.append("RESULT: the result still changes no prop: the consequence is something in the WORLD a viewer sees (not his face, not his pose)")
    # ---- the consequence and the action are IN the stills
    cons, act = str(p.get("consequence") or ""), str(p.get("action") or "")
    if words(cons) and cover(cons, st[2].get("shows")) < COVER:
        out.append(f"RESULT: the consequence '{cons}' is not what still 3 (result) shows ('{st[2].get('shows')}'): the result still "
                   f"shows the consequence, big in the frame, in its own words")
    if words(act) and cover(act, st[1].get("shows")) < COVER:
        out.append(f"ACTION: the action '{act}' is not what still 2 (action) shows ('{st[1].get('shows')}')")
    held_props = [q["name"] for q in props if q.get("held")]
    for hp in held_props:
        if not any(s.get("hands") == hp for s in st):
            out.append(f"HANDS: '{hp}' is a thing he holds and no still has his hands on it")
    # ---- the texts promise only what a still shows
    if line:
        for ev in boardlint.events(action_line):
            best = max(cover(ev, s.get("shows")) for s in st)
            if words(ev) and best < COVER:
                out.append(f"FOR: the storyboard line promises '{ev}' and no still shows it (the nearest carries {best:.0%} of its words): "
                           f"give it a still, or take it out of the line")
    if says:
        nums = story_gate.numbers(says)
        counted = any(v >= 2 for v, _s, _a, _b in nums)
        for val, said, _a, _b in nums:
            if val < 2 and not counted:
                continue
            if not any(re.search(rf"\b{re.escape(said.lower())}\b", str(s.get("shows") or "").lower()) for s in st):
                out.append(f"SAYS: the spoken line says '{said}' and no still shows that many: a number is seen as a count or a size in a still")
        k = p.get("says_still")
        if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= 4:
            out.append("SAYS: `says_still` names no still (1-4): which still does a stranger with the sound off read the spoken line from?")
        elif len(words(says) & words(st[k - 1].get("shows"))) < min(SAYS_WORDS, len(words(says))):
            out.append(f"SAYS: still {k} ('{st[k - 1].get('shows')}') shares fewer than {SAYS_WORDS} words with the spoken line '{says}': "
                       f"the still that carries the line shows the things it names")
    out += visible_problems(p, st, names, action_line if line else "", says)
    if last and st[3].get("new") and all(c.get("what") == "data" for c in st[3]["new"] if isinstance(c, dict)) and not world:
        out.append("PAYOFF: the last shot ends on his pose alone: the video ends ON a visual payoff in the world")
    return out


def _entries(still):
    """a still's visible list, each entry a dict (a bare prop name is {"prop": name})"""
    v = still.get("visible")
    return [({"prop": e} if isinstance(e, str) else e) for e in (v if isinstance(v, list) else []) if isinstance(e, (str, dict))]


def _number_free(text):
    """the text with its numbers taken out, and the numbers a still has to show ([(value, as said)])"""
    nums = story_gate.numbers(text or "")
    counted = any(v >= 2 for v, _s, _a, _b in nums)
    keep = [(v, said) for v, said, _a, _b in nums if v >= 2 or counted]
    out = list(text or "")
    for _v, _s, a, b in nums:
        out[a:b] = " " * (b - a)
    return "".join(out), keep


def visible_problems(p, st, names, action_line, says):
    """the promises of the storyboard line's action and of the spoken line that no still lists as visible"""
    out = []
    vis = []
    for i, s in enumerate(st, 1):
        ok = []
        for e in _entries(s):
            if e.get("prop") != "data" and e.get("prop") not in names:
                out.append(f"VISIBLE: still {i} lists {e.get('prop')!r} as visible, which is not \"data\" or one of the shot's props {sorted(names)}")
                continue
            c = e.get("count")
            if c is not None and (not isinstance(c, int) or isinstance(c, bool) or not 1 <= c <= COUNT_MAX):
                out.append(f"VISIBLE: still {i} counts {c!r} of '{e['prop']}': a stranger counts {COUNT_MAX} or fewer in one still; "
                           f"a bigger number is on a thing in the world that `reads` it, or is not promised")
                continue
            ok.append(e)
        if not ok:
            out.append(f"VISIBLE: still {i} ({s.get('event')}) lists nothing `visible`: name each thing a stranger can point at in it "
                       f"(a prop of the shot, or \"data\"), with the words it is seen `as`")
        vis.append(ok)
    seen_words = [set().union(*[words(e.get("prop")) | words(e.get("as")) for e in ents]) if ents else set() for ents in vis]
    prop_words = set().union(*[words(n) for n in names]) if names else set()
    unseen = {}
    for u in p.get("unseen") or []:
        if not isinstance(u, dict) or u.get("why") not in UNSEEN_WHY or not words(u.get("word")):
            out.append(f"UNSEEN: {u!r} is not {{\"word\": one word, \"why\": {' | '.join(UNSEEN_WHY)}}}")
            continue
        for w in words(u["word"]):
            unseen[w] = u["why"]
    done = words(p.get("action")) | words(p.get("consequence"))
    for w, why in sorted(unseen.items()):
        if w in prop_words:
            out.append(f"UNSEEN: '{w}' is a word of one of the shot's props: a thing is seen in a still, it is never unseen")
        elif re.fullmatch(r"[0-9,.]+", w) or story_gate.numbers(w):
            out.append(f"UNSEEN: '{w}' is a number: a number is a `count` or a `reads` in one still, or it is not promised")
        elif why == "verb" and w not in done:
            out.append(f"UNSEEN: '{w}' is declared a verb and neither the shot's action nor its consequence says it: "
                       f"a thing that happens is the action, the consequence, or another shot")
    for source, text in (("FOR", action_line), ("SAYS", says)):
        if not text:
            continue
        plain, nums = _number_free(text)
        cw = words(plain)
        miss = sorted(w for w in cw if w not in unseen and not any(w in sw for sw in seen_words))
        if miss:
            out.append(f"NOT SHOWN ({source}): {'the storyboard line' if source == 'FOR' else 'the spoken line'} promises {miss} and no still "
                       f"lists a visible thing with that word: add it to ONE still's `visible` (on a prop that is in that still), "
                       f"or take the word out of the line")
        hidden = sorted(w for w in cw if w in unseen)
        if cw and len(hidden) > UNSEEN_SHARE[source] * len(cw):
            out.append(f"UNSEEN ({source}): {len(hidden)} of the line's {len(cw)} content words are declared unseen {hidden} "
                       f"(at most {UNSEEN_SHARE[source]:.0%}): a line is mostly things a still shows")
        for val, said in nums:
            hit = False
            for ents in vis:
                for e in ents:
                    if e.get("count") == val or (e.get("reads") and re.search(rf"(?<![0-9]){re.escape(str(said).lower())}(?![0-9])", str(e["reads"]).lower())) \
                            or (e.get("reads") and re.sub(r"[^0-9]", "", str(e["reads"])) == str(val)):
                        hit = True
            if not hit:
                out.append(f"NOT SHOWN ({source}): the line says '{said}' and no still shows that number: "
                           + (f"{val} is more than a stranger counts in one still ({COUNT_MAX}); put it on a thing in the world that `reads` it, or take it out"
                              if val > COUNT_MAX else f"one still lists a visible thing with `count`: {val} (or a thing that `reads` it)"))
    return out


def validate(script, plan, partial=False):
    """[(where, problem)] over a whole plan against its script. partial: a shot's entry may be null (a story in PLAN_BEFORE)"""
    lines = script.get("lines") or []
    board = script.get("storyboard") or []
    if not isinstance(plan, dict) or not isinstance(plan.get("shots"), list):
        return [("plan", "PLAN: plan.json has no `shots` list")]
    out = []
    if len(plan["shots"]) != len(lines):
        out.append(("plan", f"PLAN: {len(plan['shots'])} shots planned for {len(lines)} spoken lines: one plan per line, in order"))
    for i, p in enumerate(plan["shots"][:len(lines)], 1):
        if p is None and partial:
            continue
        out += [(f"shot {i}", t) for t in shot_problems(p, board[i - 1] if i <= len(board) else "", lines[i - 1], last=i == len(lines))]
    return out


def problems(story, script):
    """what store/shots.py refuses to build on: [] for a story staged before the plan (PLAN_BEFORE)"""
    if not held(story):
        return []
    plan = load(story)
    if plan is None:
        return [("plan", f"PLAN: no stories/{story}/{NAME}: every shot is planned before it is staged "
                         f"(python tools/data3d/store/shot_plan.py blank {story})")]
    return validate(script, plan)


def advisory(story, script):
    """the problems of whatever plan a PLAN_BEFORE story has, printed and not binding"""
    plan = load(story)
    return validate(script, plan, partial=True) if plan is not None and not held(story) else []


def blank(script):
    """an empty plan for a script: one entry per line, the four events laid out, everything else to fill in"""
    one = lambda: {"prop": "", "props": [{"name": "", "objects": [""], "whole": True, "built_as": ""}], "framing": "close",
                   "data": {"stands": "beside", "side": "left", "frame_h": 0.36}, "action": "", "consequence": "", "says_still": 3,
                   "unseen": [],
                   "stills": [{"event": e, "shows": "", "hands": "free", "visible": [{"prop": "", "as": ""}], "new": []} for e in EVENTS]}
    return {"shots": [one() for _ in script.get("lines") or []]}


def main(argv):
    if len(argv) == 3 and argv[1] in ("check", "blank"):
        script = json.loads((STORIES / argv[2] / "script.json").read_text())
        if argv[1] == "blank":
            print(json.dumps(blank(script), indent=1)); return 0
        ps = problems(argv[2], script) + advisory(argv[2], script)
        for where, t in ps:
            print(f"PLAN {argv[2]} {where}: {t}" + ("" if held(argv[2]) else " (not binding: staged before the plan, see PLAN_BEFORE)"))
        if not ps:
            print(f"PLAN {argv[2]}: ok" + ("" if held(argv[2]) else " (staged before the plan; not binding)"))
        return 1 if ps and held(argv[2]) else 0
    print("usage: shot_plan.py check STORY | blank STORY"); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
