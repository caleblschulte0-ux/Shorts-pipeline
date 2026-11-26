"""THE STAGING HELPER, PROVEN: build every case in tests/data3d_recipe/cases through store/shots.py (no render) and
write down what each of the harness's checks said (2026-11-26).

store/recipe_stage.py stages a shot to the recipe and keys a first performance. "It passes the checks by construction"
is a claim about Blender, the rig and a dozen checks at once, so it is not asserted: it is RUN, on seven prop shapes
(a small thing he picks up, a crate he works, a crate he shoves from the lens, a tall post worked by its lever, a
lever over his reach worked from a step, a small crate walked across the frame, a thing on the ground worked with a
tool), and the result is committed as tests/data3d_recipe/proof.json with a fingerprint of the helper's code and of
the cases. tests/test_data3d_a_shot_is_born_to_the_recipe.py fails when a check in it reads FAIL, and when the helper
or a case has changed since the proof was run: change recipe_stage.py, then run this again.

  python tools/data3d/store/recipe_prove.py            every case; writes the proof
  python tools/data3d/store/recipe_prove.py 3 6        only these (the proof keeps the others' records, marked stale if the code changed)
  env: BLENDER_PY (a python with bpy; default "python3"), PROVE_LOAD (wait for a 1-minute load under this; default 5),
       PROVE_WAIT (seconds to wait for it; default 900), PROVE_KEEP=dir (keep the logs there)

Each build is the scene data only (shots.py's DIAG exit, before any frame renders): about a minute and a half."""
import ast, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = ROOT / "tests" / "data3d_recipe" / "cases"
PROOF = ROOT / "tests" / "data3d_recipe" / "proof.json"
STORY = "recipe_cases"
# every per-shot check the harness prints with a verdict; a case's proof carries each of these, and each reads OK
CHECKS = ("STAGING", "CONSEQUENCE", "EDGES", "KEYS", "TALKING", "CAUSE", "RECIPE", "ANATOMY", "CLIPPING", "TWITCH", "FLUID", "REACH",
          "FACE", "STEADY", "POP", "HOLD", "READ", "FAR", "HANDS")
LINE = re.compile(r"^([A-Z]+) shot \d+[^:]*:.*-> (OK|FAIL|within grace)\b")   # "within grace" is the clipping check's own pass


def _code(path):
    """the file's code with its docstrings and comments out: a reworded comment is not a new helper"""
    tree = ast.parse(Path(path).read_text())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)


def fingerprint():
    """what the proof is a proof OF: the helper's code and the cases'"""
    h = hashlib.sha256()
    h.update(_code(HERE / "recipe_stage.py").encode())
    h.update(_code(CASES / "shots.py").encode())
    for name in ("plan.json", "script.json"):
        h.update(json.dumps(json.loads((CASES / name).read_text()), sort_keys=True).encode())
    return h.hexdigest()


def read(log):
    """{check: "OK" | "FAIL"} and the failing lines of one build's log"""
    said = {}; fails = []
    for line in log.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        name, v = m.groups()
        if v == "FAIL":
            said[name] = "FAIL"; fails.append(line[:400])
        else:
            said.setdefault(name, "OK")
    return said, fails


def tree(tmp):
    """a copy of the store with the cases as its one story (the store's modules find their stories beside them)"""
    d3 = Path(tmp) / "tools" / "data3d"; (d3 / "stories").mkdir(parents=True)
    shutil.copytree(HERE, d3 / "store", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(CASES, d3 / "stories" / STORY, ignore=shutil.ignore_patterns("__pycache__", "make_plan.py"))
    for p in HERE.parent.iterdir():
        if p.name not in ("store", "stories", "__pycache__"):
            (d3 / p.name).symlink_to(p)
    noop = Path(tmp) / "noop.py"; noop.write_text("pass\n")
    return d3, noop


def wait_for_load():
    limit = float(os.environ.get("PROVE_LOAD", "5")); until = time.time() + float(os.environ.get("PROVE_WAIT", "900"))
    while os.getloadavg()[0] >= limit and time.time() < until:
        time.sleep(15)
    return os.getloadavg()[0]


def build(d3, noop, n, keep=None):
    load = wait_for_load()
    env = dict(os.environ, STORY=STORY, SHOT=str(n), STAGING="on", DIAG=str(noop))
    out = Path(d3).parents[1] / f"out{n}"
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    one_core = ["taskset", "-c", str(max(0, (os.cpu_count() or 1) - 1))] if shutil.which("taskset") else []
    # the lowest priority, on ONE core: a proof never takes the machine from a shot that is being made
    r = subprocess.run(["nice", "-n", "19"] + one_core + [os.environ.get("BLENDER_PY", "python3"), "-I", "shots.py", str(out), "8", "30"],
                       cwd=str(d3 / "store"), env=env, capture_output=True, text=True, timeout=3000)
    log = r.stdout + r.stderr
    if keep:
        Path(keep).mkdir(parents=True, exist_ok=True); (Path(keep) / f"case{n}.log").write_text(log)
    said, fails = read(log)
    built = r.returncode == 0 and "Traceback" not in log
    if not built:
        fails.insert(0, "the build did not finish: " + (log.strip().splitlines() or ["no output"])[-1][:300])
    return {"built": built, "load": round(load, 1), "checks": said, "fails": fails}


def main(argv):
    script = json.loads((CASES / "script.json").read_text())
    want = [int(a) for a in argv[1:]] or list(range(1, len(script["lines"]) + 1))
    old = json.loads(PROOF.read_text()) if PROOF.exists() else {}
    fp = fingerprint()
    cases = old.get("cases", {}) if old.get("fingerprint") == fp else {}      # another helper's records prove nothing about this one
    with tempfile.TemporaryDirectory() as tmp:
        d3, noop = tree(tmp)
        for n in want:
            rec = build(d3, noop, n, os.environ.get("PROVE_KEEP"))
            rec["case"] = re.sub(r"^\d+\s+", "", script["storyboard"][n - 1].split("(")[0]).strip()
            cases[str(n)] = rec
            bad = [c for c in CHECKS if rec["checks"].get(c) != "OK"]
            print(f"case {n} ({rec['case']}): " + ("every check OK" if rec["built"] and not bad else f"NOT PROVEN {bad}"), flush=True)
            for l in rec["fails"]:
                print("   " + l, flush=True)
    PROOF.write_text(json.dumps({"fingerprint": fp, "story": STORY, "checks": list(CHECKS),
                                 "cases": {k: cases[k] for k in sorted(cases, key=int)}}, indent=1) + "\n")
    return 0 if all(c["built"] and all(c["checks"].get(k) == "OK" for k in CHECKS) for c in cases.values()) and len(cases) == len(script["lines"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
