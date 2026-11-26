"""THE RENDER PLAN: which runner renders which frames of a short, and which shots are not rendered at all.

Measured on the full renders of 2026-11-18 and 2026-11-23 (runs 44400238941 and 45115274403): the render was already
forty slices on forty runners, never one job. Setup is 20 to 30 seconds of a slice and the scene build and its checks
about a minute; everything else is Cycles, frame by frame, 1,758 runner-minutes for 729 frames. The account runs
twenty jobs at once, so the frames can never take under 88 minutes however they are cut; they took 143 and 105,
because a frame cost 87 s in one stretch and 287 s in the next (it varies inside a shot too, so a shot's proof time
does not predict it), the slices were 25 to 88 minutes long, and a long one that started late was the whole tail.
And a fix to one shot rendered all five again unless a session named an old run by hand.

So the plan, made once after the gate has passed and before any frame renders:
  parts   every shot is cut into its own frame ranges (no job builds two scenes), eighty across the video in
          proportion to frames and never under MIN_FRAMES each. Half the length per job halves the tail one slow job
          can add; it is a small gain (the same frames replayed: about 109 minutes against 114), because the cap of
          twenty runners is the floor. What a short costs is its runner-minutes, and only reuse lowers those.
  reuse   a shot whose KEY is unchanged is not rendered: its frames are copied from the run that made them. A fix
          to one shot of five renders a fifth of the frames.

THE KEY of a shot is a hash of everything its pixels can be made from: the harness and every module it can import
(found by following the imports and the .py files named in shots.py and the story, never from a list), the story's shots.py with the OTHER shots' functions blanked (judged.py's rule, and only for a shot
nothing else calls), its script.json, any data file beside them, the narration windows, spp, pct, the asset branch's
commit and the render environment. Change one character of any of it and the shot renders again. The judge's records
(judge_rounds.md, notes_ledger.json, preflight.json, judged.json) are not pixels and are not in it. A frames artifact
carries the key in its name (frames-s<shot>-<key>-p<i>of<n>); a run holds a shot when it holds every part under that
key, which only happens after each job counted its frames. No lookup, an API error or `fresh=1` in the trigger:
render it.

The gate is not here. data3d_render.yml runs this only after the proof and the judge have passed, exactly as before.

  python render_plan.py plan    (the workflow: env STORY NARR SPP PCT ASSETS_SHA RENDER_ENV, writes the matrix)
  python render_plan.py keys STORY   each shot's key as it stands (draft windows, 16 spp, 100%)"""
import ast, hashlib, json, os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
D3 = HERE.parent
STORIES = D3 / "stories"
sys.path.insert(0, str(D3))
import clock

VERSION = "1"            # bump when what a key must cover changes: every old frame is then rendered again
PARTS = 80               # the render's jobs (forty until 2026-11-26; see the docstring)
RECORDS = {"judge_rounds.md", "notes_ledger.json", "preflight.json", "judged.json"}   # what the judge writes: never pixels
KEY_LEN = 16
MIN_FRAMES = 4           # a part shorter than this spends more on building the scene than it saves
MANUAL = "manual"        # frames taken on a session's word (reuse_run=): never a hex key, so never found by key


def _sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def _local(name):
    """the file a module name resolves to on the harness's own path (store/, then tools/data3d/), or None"""
    for d in (HERE, D3):
        p = d / (name.split(".")[0] + ".py")
        if p.exists():
            return p
    return None


def _imports(src):
    """the module names a source imports, or None when it cannot be read or imports by a computed name"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "__import__":
            if not (n.args and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
                return None
            out.add(n.args[0].value)
    return None if "importlib" in out else out


def render_modules(story_src=""):
    """every local module the render can reach, by following imports and named .py files from the harness and the
    story. A file that cannot be parsed, or one that imports by a computed name, makes the whole tree the answer
    (never fewer files)"""
    everything = sorted(p for d in (HERE, D3) for p in d.glob("*.py"))
    seen, todo = {}, [HERE / "shots.py"]
    texts = [story_src]
    while todo or texts:
        if texts:
            src = texts.pop()
        else:
            p = todo.pop()
            if p in seen:
                continue
            src = p.read_text(); seen[p] = src
        names = _imports(src)
        if names is None:
            return everything
        names |= set(re.findall(r"\b(\w+)\.py\b", src))    # a file run or read by its name (labels.py, base_build.py), even in a comment
        todo += [q for q in map(_local, names) if q and q not in seen]
    return sorted(seen)


def own_source(src, n):
    """the story's shots.py as shot n renders it: every OTHER shot's function blanked (store/judged.py's rule), unless
    something outside that function calls it, in which case it stays"""
    rx = re.compile(r"^def shot(\d+)\(\):.*?(?=^def |^# =+|^SHOTS|\Z)", re.S | re.M)
    spans = {m.group(1): m for m in rx.finditer(src)}
    def called_elsewhere(k):
        m = spans[k]
        rest = src[:m.start()] + src[m.end():]
        rest = re.sub(r"^SHOTS\b.*$", "", rest, flags=re.M)
        return re.search(rf"\bshot{k}\b", rest) is not None
    keep = {k for k in spans if k == str(n) or called_elsewhere(k)}
    return rx.sub(lambda m: m.group(0) if m.group(1) in keep else "", src)


def shot_key(story, n, windows, spp, pct, assets="", env=""):
    """the hash of everything shot n's frames are made from (see the module docstring)"""
    sd = STORIES / story
    src = (sd / "shots.py").read_text()
    code = [(str(p.relative_to(D3)), _sha(p.read_bytes())) for p in render_modules(src)]
    data = [(str(p.relative_to(D3)), _sha(p.read_bytes())) for p in sorted(D3.rglob("*"))
            if p.is_file() and p.suffix not in (".py", ".pyc", ".md", ".sh") and "__pycache__" not in p.parts
            and (STORIES not in p.parents or (p.parent == sd and p.name not in RECORDS))]
    return _sha(json.dumps({"v": VERSION, "story": story, "shot": n, "code": code, "data": data,
                            "own": _sha(own_source(src, n)), "windows": windows, "spp": str(spp), "pct": str(pct),
                            "assets": assets, "env": env}, sort_keys=True))[:KEY_LEN]


def artifact(shot, key, part, parts):
    return f"frames-s{shot}-{key}-p{part}of{parts}"


def holds(names, shot, key):
    """True when these artifact names carry every part of this shot under this key"""
    got = {}
    for nm in names:
        m = re.fullmatch(rf"frames-s{shot}-{re.escape(key)}-p(\d+)of(\d+)", nm)
        if m:
            got.setdefault(int(m.group(2)), set()).add(int(m.group(1)))
    return any(p > 0 and have == set(range(p)) for p, have in got.items())


def plan(windows, keys, parts=PARTS, reuse=None):
    """the frames matrix. windows: the narration's; keys {shot: key}; reuse {shot: (run id, key or MANUAL)} for the
    shots that are copied. Every frame of the video is in exactly one entry. The entries that render come first, one
    part of each shot in turn (a costly stretch is spread over the queue, not bunched at its end); the copies last"""
    reuse = reuse or {}
    span = {n: clock.span(windows, n) for n in range(1, len(windows) + 1)}
    todo = [n for n in span if n not in reuse]
    cut = {n: 1 for n in todo}
    for _ in range(max(0, parts - len(reuse) - len(todo))):       # each next job goes to the shot whose parts are longest
        open_ = [n for n in todo if (cut[n] + 1) * MIN_FRAMES <= span[n][3]]
        if not open_:
            break
        n = max(open_, key=lambda k: (span[k][3] / cut[k], -k)); cut[n] += 1
    out = []
    for n in todo:
        _, _, g0, nf = span[n]; p = cut[n]
        for i in range(p):
            a, b = i * nf // p + 1, (i + 1) * nf // p
            out.append({"shot": n, "part": i, "parts": p, "a": g0 + a, "b": g0 + b, "frames": b - a + 1,
                        "artifact": artifact(n, keys[n], i, p), "reuse_run": "", "pattern": ""})
    out.sort(key=lambda e: (e["part"] / e["parts"], e["shot"]))
    for n in sorted(reuse):
        run, key = reuse[n]; _, _, g0, nf = span[n]
        out.append({"shot": n, "part": 0, "parts": 1, "a": g0 + 1, "b": g0 + nf, "frames": nf,
                    "artifact": artifact(n, keys[n] if key != MANUAL else MANUAL, 0, 1), "reuse_run": str(run),
                    "pattern": f"frames-s{n}-*" if key == MANUAL else f"frames-s{n}-{key}-p*"})
    return out


# ---------------------------------------------------------------- what only a runner can ask (the GitHub API, via gh)
def _gh(path, jq, pages=False):
    p = subprocess.run(["gh", "api"] + (["--paginate"] if pages else []) + [path, "--jq", jq], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    return [l for l in p.stdout.splitlines() if l.strip()]


def find_reuse(repo, this_run, keys, workflow="data3d_render.yml", look_back=40):
    """{shot: (run, key)} for each shot an earlier run of this workflow still holds under today's key"""
    found = {}
    runs = _gh(f"repos/{repo}/actions/workflows/{workflow}/runs?per_page={look_back}", ".workflow_runs[].id")[:look_back]
    for run in runs:
        if str(run) == str(this_run) or len(found) == len(keys):
            continue
        names = _gh(f"repos/{repo}/actions/runs/{run}/artifacts?per_page=100", ".artifacts[]|select(.expired|not)|.name", pages=True)
        for n, k in keys.items():
            if n not in found and holds(names, n, k):
                found[n] = (run, k)
    return found


def main(argv):
    if len(argv) > 2 and argv[1] == "keys":
        w = json.loads((STORIES / argv[2] / "script.json").read_text())["draft_windows"]
        for n in range(1, len(w) + 1):
            print(f"shot {n}: {shot_key(argv[2], n, w, 16, 100)}")
        return 0
    if len(argv) < 2 or argv[1] != "plan":
        print(__doc__); return 1
    e = os.environ
    story = e["STORY"]; windows = json.load(open(e["NARR"]))["windows"]
    spp, pct = e.get("SPP") or "16", e.get("PCT") or "100"
    keys = {n: shot_key(story, n, windows, spp, pct, e.get("ASSETS_SHA", ""), e.get("RENDER_ENV", ""))
            for n in range(1, len(windows) + 1)}
    repo, run = e.get("GITHUB_REPOSITORY", ""), e.get("GITHUB_RUN_ID", "")
    reshoot = {int(x) for x in e.get("RESHOOT", "").split()}
    reuse, why = {}, "render every shot"
    if e.get("REUSE_RUN") and reshoot:                       # a session's word, as before: every other shot from that run
        reuse = {n: (e["REUSE_RUN"], MANUAL) for n in keys if n not in reshoot}
        why = f"reuse_run={e['REUSE_RUN']} reshoot={sorted(reshoot)}"
    elif e.get("FRESH") in ("1", "true", "yes"):
        why = "fresh=1: nothing reused"
    elif repo:
        try:
            reuse = {n: r for n, r in find_reuse(repo, run, keys).items() if n not in reshoot}
            why = f"unchanged shots reused: {sorted(reuse)}" if reuse else "no earlier run holds a shot under today's key"
        except Exception as ex:                              # no lookup is no reuse: render it
            why = f"no reuse lookup ({ex}): render every shot"
    m = plan(windows, keys, int(e.get("PARTS") or PARTS), reuse)
    for x in m: x.update(spp=spp, pct=pct)
    total = clock.total(windows)
    assert sorted(f for x in m for f in range(x["a"], x["b"] + 1)) == list(range(1, total + 1)), "the plan must tile the video"
    lines = [f"PLAN {story}: {total} frames, {sum(1 for x in m if not x['reuse_run'])} render jobs, {why}"]
    for n in sorted(keys):
        mine = [x for x in m if x["shot"] == n]
        lines.append(f"  shot {n} key {keys[n]}: " + (f"copied from run {mine[0]['reuse_run']}" if mine[0]["reuse_run"] else
                     f"{len(mine)} parts of ~{mine[0]['frames']} frames"))
    print("\n".join(lines))
    for path, text in ((e.get("GITHUB_OUTPUT"), f"matrix={json.dumps(m, separators=(',', ':'))}\ntotal={total}\n"),
                       (e.get("GITHUB_STEP_SUMMARY"), "```\n" + "\n".join(lines) + "\n```\n")):
        if path:
            with open(path, "a") as fh: fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
