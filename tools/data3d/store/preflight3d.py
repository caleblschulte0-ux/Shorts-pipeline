"""THE PRE-FLIGHT: before the judge panel is spent on a storyboard sheet, ONE cheap look ticks every promise the texts
make against a still (2026-11-25).

The lava short took four board rounds a shot, about forty minutes each, and nearly every round failed on something a
person could have seen in the sheet before sending it: a sandbag the line named and no still showed, a "close" line
over a wide render, a still a different colour from the other three, a wall cut by the frame edge. The panel grades
each sheet against three texts (the shot's storyboard line, FOR; its spoken line, SAYS; and the story's world), and
anything named there and not visible is a hard fail. Nothing compared the stills with those texts first.

  claims(script, n)      the list of promises for shot n, from code: the place, the camera, the time of day and every
                         event of the storyboard line; the spoken line and each number in it; the hero's costume, the
                         weather and the continuity things of the world.
  check(story, n, sheet, stills)   one headless look (the `claude` CLI on the subscription, never the paid API) Reads
                         the sheet and must tick each claim against a SPECIFIC still, and answer CONTINUITY between the
                         stills. Code decides: a claim with no still named is not ticked.
  gate(story, sheets)    what store/judge3d.py calls on a board round. A shot whose sheet has an unticked claim or a
                         continuity fault never reaches the panel that round; it prints what to fix, or which promise
                         to take out of the text. No look (no CLI, no answer) is no pass: the round does not run.
  passed(story, n, sheet)  True only for a recorded pass of THIS sheet (its sha256) under THESE claims.
  DEFECTS / defects()    the same look also answers the judges' hard-defect classes as plain questions (one event
                         repeated, anything broken, off the look, his body, no consequence). One not answered ok
                         blocks the sheet exactly like an unticked claim.

The result is kept in stories/<story>/preflight.json keyed by the sheet's sha256. It only ever ADDS a block: it has
no say in a score, it cannot pass a shot, and the panel's bar is not touched. A wrong block is answered by fixing the
shot or the text; PREFLIGHT3D_AGAIN=1 spends a second look at a sheet already blocked (never a way round it).

usage: python preflight3d.py claims STORY SHOT | check STORY SHOT SHEET.jpg STILLS
"""
import hashlib, json, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boardlint, story_gate

STORIES = HERE.parent / "stories"
NAME = "preflight.json"
KEEP = 80      # sheets remembered per story: a few rounds of every shot

TIME = re.compile(r"\b(dawn|sunrise|morning|noon|midday|afternoon|golden hour|sunset|dusk|evening|twilight|night|"
                  r"midnight|by day|daylight)\b", re.I)

# what must hold BETWEEN the stills, whatever the texts say
CONTINUITY = {
    "props": "every prop and every thing that matters in still n is still there in still n+1, or the stills show where "
             "it went (nothing vanishes, nothing appears from nowhere)",
    "grade": "the grade and the lighting are the same in every still (the same time of day and colour of light; no "
             "still darker, greyer or tinted differently from the others) unless a claim says the light changes",
    "feet": "Data's feet are on the ground in every still: not floating above it, not sunk into it (a jump the "
            "claims name is the only exception)",
    "edges": "the shot's subject and Data are whole in the frame in every still: nothing that is the subject is cut "
             "by a frame edge",
    "different": "the stills are clearly different from each other: each shows a new state (before, action, result, "
                 "reaction), not one picture repeated",
}

# the judges' own HARD-DEFECT classes, asked of the sheet as plain questions (2026-11-26: two shots lost a panel round
# each to a sheet whose every claim was ticked: four stills of one run only bigger, two stray rods in the sky, a pale
# sprite of a fountain). A claim says what must be there; these say what must NOT be. One that fails blocks the sheet.
DEFECTS = {
    "gag": "ONE-SECOND GAG: the stills are different EVENTS, something new happens in each one. It fails when two or "
           "more stills show the same pose or the same action only bigger, nearer, or from another distance",
    "broken": "BROKEN: nothing in any still is broken: no stray rod, bar or streak, no flat sprite or card, nothing "
              "floating with no support, nothing that changes place between stills with no cause shown, and no object "
              "half cut off by a frame edge",
    "look": "OFF THE LOOK: every element belongs to one realistic look: no toy, no flat untextured box or slab, no "
            "sprite or clip-art thing beside realistic ones; fire, smoke, lava, dust and water read as the real thing",
    "body": "BODY: Data's hands are on whatever he holds, carries or works (nothing of his floats beside him or rests "
            "on him with no hand on it), his limbs bend as limbs do, and his feet are down unless he is mid-stride",
    "consequence": "CONSEQUENCE: what happens in the shot visibly changes something a phone viewer can see: its "
                   "subject is big enough to read at a glance, and the last still shows the result, not the same "
                   "picture as the first",
}

PROMPT = """You are checking a storyboard sheet before it is sent to a panel of judges. The sheet is ONE image of {k} stills
from one shot of a 3D animated Short starring Data, a small teal cartoon scientist, in time order left to right (top
to bottom if it wraps). Number them 1 to {k}. READ it with the Read tool: {sheet}

Look at it the way a viewer holding a phone would. You are not grading quality. You are answering one question per
line below: IS THIS VISIBLE IN A STILL? The judges will fail the shot for anything promised and not shown, so be
literal and strict: a thing counts only if a stranger could point at it in the still. Do not give the benefit of the
doubt, and do not tick a claim because another claim near it is true.

CLAIMS (each must be ticked against ONE specific still that shows it):
{claims}

A CAMERA claim is ticked only when the stills are framed the way it says (wide or close, low or high, what it looks
at). A NUMBER claim is ticked only when that many can be counted, or the size is seen beside something familiar. An
ACTION claim is ticked only when every thing it names is in the still and the still shows it happening or having
happened. The SAYS claim is the judges' own test, no stricter and no looser: with the sound off, could a stranger
tell the line's fact from these stills? Read the line for the EVENTS and THINGS it names and look for each in the
stills taken together; name the still that carries it best. A place named in the line is shown by the place itself (its
landscape, its houses, what the world block says it looks like), never by a label or a map. A word for people in
general ("everyone", "people", "they") is shown when the hero is seen doing it, or by its traces (cars leaving, an
empty street). Do NOT tick it when an event or a thing the line names is depicted in no still, when only a generic
stand-in for a named thing is there, or when the fact is something only the voice could state. A TIME or WEATHER claim from WORLD describes the whole story: tick it against a still when nothing in this
shot's stills contradicts it.

CONTINUITY (between the stills):
{continuity}

HARD DEFECTS (the judges fail a sheet outright for any of these; here, and only here, look as a judge would: answer
ok false when a stranger would notice the fault at phone size, and say exactly what and in which stills):
{defects}

Return ONLY JSON:
{{"claims": [{{"id": "c1", "seen": true|false, "still": N, "note": "what you see, or what is missing"}}, ...],
 "continuity": [{{"id": "props", "ok": true|false, "stills": "2-3", "note": "what breaks, in which stills"}}, ...],
 "defects": [{{"id": "gag", "ok": true|false, "stills": "2-4", "note": "what the fault is, in which stills"}}, ...]}}
One entry for every claim id, every continuity id and every hard-defect id above."""


def claims(script, n):
    """every promise the three texts make about shot n: [{"id", "kind", "from", "text"}], ids c1.. in a fixed order"""
    out = []

    def add(kind, source, text):
        text = re.sub(r"\s+", " ", str(text or "")).strip(" ,;:.")
        if text:
            out.append({"id": f"c{len(out) + 1}", "kind": kind, "from": source, "text": text})

    board = script.get("storyboard") or []
    line = board[n - 1] if 0 < n <= len(board) else ""
    _, place, camera, action = boardlint.parts(line)
    for piece in re.split(r"[,:]", place):
        add("PLACE", "FOR", piece)
    add("CAMERA", "FOR", camera)
    times = sorted({m.group(0).lower() for m in TIME.finditer(place + " " + camera + " " + action)})
    for t in times:
        add("TIME", "FOR", f"it is {t}")
    for ev in boardlint.events(action):
        add("ACTION", "FOR", ev)
    lines = script.get("lines") or []
    says = lines[n - 1] if 0 < n <= len(lines) else ""
    add("SAYS", "SAYS", f"a stranger with the sound off would say the stills show what this line says: {says}" if says else "")
    nums = story_gate.numbers(says)
    counted = any(v >= 2 for v, _, _, _ in nums)
    for val, said, a, b in nums:
        if val < 2 and not counted:      # "one Icelandic town" is an article, not a count; "one in seven" is a count
            continue
        thing = re.match(r"(?:\s+[A-Za-z'-]+){0,3}", says[b:]).group(0)
        add("NUMBER", "SAYS", f"{said}{thing}: seen as that count or that size")
    world = script.get("world") or {}
    add("HERO", "WORLD", world.get("hero"))
    if not times:
        add("TIME", "WORLD", f"nothing in the stills contradicts the story's time: {world.get('time')}" if world.get("time") else "")
    add("WEATHER", "WORLD", f"nothing in the stills contradicts the story's weather: {world.get('weather')}" if world.get("weather") else "")
    low = str(line).lower()
    for key, what in (world.get("continuity") or {}).items():
        if str(key).lower() in low:
            add("CONTINUITY", "WORLD", f"the {key} is in this shot and is the same one as in the rest of the story ({what})")
    return out


def claims_key(cl):
    """the texts AND the questions a sheet was looked at under: a pass from before a question was asked is no pass"""
    return hashlib.sha256(json.dumps([[(c["kind"], c["text"]) for c in cl], sorted(DEFECTS.items())], ensure_ascii=False).encode()).hexdigest()[:16]


def sheet_sha(sheet):
    return hashlib.sha256(Path(sheet).read_bytes()).hexdigest()


def prompt(cl, sheet, k):
    return PROMPT.format(k=k, sheet=sheet,
                         claims="\n".join(f"- {c['id']} [{c['kind']}, from {c['from']}] {c['text']}" for c in cl),
                         continuity="\n".join(f"- {i}: {t}" for i, t in CONTINUITY.items()),
                         defects="\n".join(f"- {i}: {t}" for i, t in DEFECTS.items()))


def look(text):
    """the one headless look: the brain's raw answer, or None (no CLI, an error, a timeout)"""
    if not shutil.which("claude"):
        return None
    try:
        p = subprocess.run(["claude", "-p", text, "--model", os.environ.get("PREFLIGHT3D_MODEL", "sonnet"),
                            "--allowedTools", "Read", "--output-format", "text"], capture_output=True, text=True,
                           timeout=int(os.environ.get("PREFLIGHT3D_TIMEOUT", "300")))
    except (subprocess.TimeoutExpired, OSError):
        return None
    return p.stdout if p.returncode == 0 else None


def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except ValueError:
        return None
    return v if isinstance(v, dict) and isinstance(v.get("claims"), list) and isinstance(v.get("continuity"), list) else None


def decide(cl, answer, k):
    """code holds the rule: (unticked claims, continuity faults). A claim is ticked only when the look said it is seen
    AND named a still from 1 to k; a continuity check holds only when the look said ok. Anything it left out fails."""
    seen = {str(a.get("id")): a for a in answer.get("claims") or [] if isinstance(a, dict)}
    unticked = []
    for c in cl:
        a = seen.get(c["id"]) or {}
        still = a.get("still")
        ok = a.get("seen") is True and isinstance(still, int) and not isinstance(still, bool) and 1 <= still <= k
        if not ok:
            unticked.append(dict(c, note=str(a.get("note") or ("not answered" if not a else "no still named"))[:300]))
    cont = {str(a.get("id")): a for a in answer.get("continuity") or [] if isinstance(a, dict)}
    faults = []
    for cid, what in CONTINUITY.items():
        a = cont.get(cid) or {}
        if a.get("ok") is not True:
            faults.append({"id": cid, "rule": what, "stills": str(a.get("stills") or ""), "note": str(a.get("note") or "not answered")[:300]})
    return unticked, faults


def defects(answer):
    """the hard-defect questions the look did not answer ok: [{"id", "rule", "stills", "note"}]. One left out fails."""
    got = {str(a.get("id")): a for a in answer.get("defects") or [] if isinstance(a, dict)}
    out = []
    for did, what in DEFECTS.items():
        a = got.get(did) or {}
        if a.get("ok") is not True:
            out.append({"id": did, "rule": what, "stills": str(a.get("stills") or ""), "note": str(a.get("note") or "not answered")[:300]})
    return out


def load(story):
    try:
        v = json.loads((STORIES / story / NAME).read_text())
        return v if isinstance(v.get("sheets"), dict) else {"sheets": {}}
    except (OSError, ValueError, AttributeError):
        return {"sheets": {}}


def save(story, led):
    p = STORIES / story / NAME
    if p.parent.is_dir():
        keep = sorted(led["sheets"].items(), key=lambda kv: kv[1].get("at", ""))[-KEEP:]
        p.write_text(json.dumps({"sheets": dict(keep)}, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return p


def recorded(story, n, sheet, cl=None):
    """the record for this exact sheet under these exact claims, or None"""
    try:
        sha = sheet_sha(sheet)
    except OSError:
        return None
    if cl is None:
        cl = claims(json.loads((STORIES / story / "script.json").read_text()), n)
    r = load(story)["sheets"].get(sha)
    return r if r and r.get("shot") == n and r.get("claims_key") == claims_key(cl) else None


def passed(story, n, sheet):
    """True only when THIS sheet was looked at under THESE claims and every one was ticked"""
    r = recorded(story, n, sheet)
    return bool(r and r.get("status") == "pass" and not r.get("unticked") and not r.get("continuity") and not r.get("defects"))


def check(story, n, sheet, k, look=None):
    """the pre-flight of one sheet: its record. status "pass", "blocked" (an unticked claim or a continuity fault) or
    "no_look" (nothing answered: never recorded, never a pass)"""
    look = look or globals()["look"]
    script = json.loads((STORIES / story / "script.json").read_text())
    cl = claims(script, n)
    old = recorded(story, n, sheet, cl)
    if old and (old.get("status") == "pass" or os.environ.get("PREFLIGHT3D_AGAIN") != "1"):
        return dict(old, kept=True)
    answer = parse(look(prompt(cl, sheet, k)))
    if answer is None:
        return {"shot": n, "status": "no_look", "sha256": sheet_sha(sheet), "unticked": [], "continuity": []}
    unticked, faults = decide(cl, answer, k)
    bad = defects(answer)
    rec = {"shot": n, "status": "blocked" if unticked or faults or bad else "pass", "sha256": sheet_sha(sheet),
           "claims_key": claims_key(cl), "claims": len(cl), "stills": k, "unticked": unticked, "continuity": faults, "defects": bad,
           "at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())}
    led = load(story); led["sheets"][rec["sha256"]] = rec; save(story, led)
    return rec


TEXT = {"FOR": "the shot's storyboard line", "SAYS": "the shot's spoken line", "WORLD": "the script's world block"}


def lines(rec):
    """what a blocked shot has to fix, one line per fault"""
    out = []
    for c in rec.get("unticked") or []:
        out.append(f"NOT SEEN [{c['kind']}, promised by {TEXT.get(c['from'], c['from'])}]: \"{c['text']}\" ({str(c.get('note')).rstrip('. ')}). "
                   f"Fix the shot so one still shows it, or take that promise out of {TEXT.get(c['from'], c['from'])}.")
    for f in rec.get("continuity") or []:
        out.append(f"CONTINUITY {f['id']}" + (f" (stills {f['stills']})" if f.get("stills") else "") + f": {str(f['note']).rstrip('. ')}. "
                   f"The rule: {f['rule']}.")
    for f in rec.get("defects") or []:
        out.append(f"HARD DEFECT {f['id']}" + (f" (stills {f['stills']})" if f.get("stills") else "") + f": {str(f['note']).rstrip('. ')}. "
                   f"The question: {f['rule']}.")
    return out


def gate(story, sheets, look=None):
    """a board round's pre-flight: {shot: record} for [(shot, sheet path, stills)], looked at side by side. Prints
    every block. The caller sends to the panel only the shots whose record is a pass."""
    def one(item):
        n, sheet, k = item
        return n, check(story, n, sheet, k, look)
    with ThreadPoolExecutor(max(1, min(4, len(sheets)))) as ex:
        res = dict(ex.map(one, sheets))
    for n in sorted(res):
        r = res[n]; sha = r.get("sha256", "")[:12]
        if r["status"] == "pass":
            print(f"PRE-FLIGHT shot {n}: every claim ticked ({r.get('claims')} claims, sheet {sha})"
                  + (" (kept: this sheet was already looked at)" if r.get("kept") else ""), flush=True)
        elif r["status"] == "no_look":
            print(f"PRE-FLIGHT shot {n}: no look answered (sheet {sha}): no pre-flight, no panel", flush=True)
        else:
            print(f"PRE-FLIGHT shot {n}: BLOCKED before the panel (sheet {sha}): {len(r['unticked'])} of {r.get('claims')} "
                  f"claims not seen, {len(r['continuity'])} continuity fault(s), {len(r.get('defects') or [])} hard defect(s)"
                  + (" (kept: this exact sheet was already blocked; change the shot or the text)" if r.get("kept") else ""), flush=True)
            for l in lines(r):
                print("   " + l, flush=True)
    return res


def verdict(rec):
    """a blocked shot's entry in the round's verdict: never a pass, no score of its own"""
    return {"shot": rec["shot"], "score": 0, "pass": False, "preflight": True, "scores": [],
            "hard": ["PRE-FLIGHT: " + l for l in lines(rec)][:12], "problems": [], "better": []}


def main(argv):
    if len(argv) == 4 and argv[1] == "claims":
        for c in claims(json.loads((STORIES / argv[2] / "script.json").read_text()), int(argv[3])):
            print(f"{c['id']:>4} [{c['kind']}, {c['from']}] {c['text']}")
        return 0
    if len(argv) == 6 and argv[1] == "check":
        r = gate(argv[2], [(int(argv[3]), str(Path(argv[4]).resolve()), int(argv[5]))])[int(argv[3])]
        return {"pass": 0, "blocked": 2}.get(r["status"], 1)
    print("usage: preflight3d.py claims STORY SHOT | check STORY SHOT SHEET.jpg STILLS"); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
