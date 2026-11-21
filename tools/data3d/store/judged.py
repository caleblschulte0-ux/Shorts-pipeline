"""A SHOT THE PANEL PASSED STAYS PASSED WHILE ITS CODE IS THE SAME (2026-11-13). The judge panel's median still swings
about ten points between runs on identical code (shot 5 of the banana short: 64, then 52; shot 3: 73, then 64), so
re-judging a shot the proof loop already passed turns the render gate into a coin flip, and the loop's whole night of
work can be lost to one bad roll in CI. The proof loop records every pass in stories/<story>/judged.json with the
hash of exactly what was judged: the shot's own function, the module code it can reach (helpers, kits), the
storyboard line it was graded against and the judge's own bar. judge3d.py takes a recorded pass when, and only
when, that hash still matches: change one character of any of it and the shot is judged again. Nothing is ever
passed that the panel did not pass; this only stops a passed shot being re-rolled.

python judged.py STORY [N ...]   prints each shot's hash and whether a recorded pass still matches"""
import hashlib, json, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORIES = HERE.parent / "stories"


def shot_hash(story, n):
    src = (STORIES / story / "shots.py").read_text()
    def blank(m):                                  # every OTHER shot's function: its edits do not touch this shot
        return "" if m.group(1) != str(n) else m.group(0)
    own = re.sub(r"^def shot(\d+)\(\):.*?(?=^def |^# =+|^SHOTS|\Z)", blank, src, flags=re.S | re.M)
    board = json.loads((STORIES / story / "script.json").read_text())["storyboard"][n - 1]
    bar = (HERE / "judge3d.py").read_text()
    return hashlib.sha256("\x00".join((own, board, bar)).encode()).hexdigest()


def _path(story):
    return STORIES / story / "judged.json"


def load(story):
    p = _path(story)
    return json.loads(p.read_text()) if p.exists() else {}


def record(story, n, verdict):
    """the proof loop calls this for a shot the panel PASSED"""
    if not verdict.get("pass"):
        return
    d = load(story)
    d[str(n)] = {"hash": shot_hash(story, n), "score": verdict.get("score"), "scores": verdict.get("scores"),
                 "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    _path(story).write_text(json.dumps(d, indent=1) + "\n")


def still_passed(story, n):
    """the recorded pass for shot n, if its hash still matches the code and brief as they are now; else None"""
    r = load(story).get(str(n))
    return r if r and r.get("hash") == shot_hash(story, n) else None


if __name__ == "__main__":
    st = sys.argv[1]
    ns = [int(x) for x in sys.argv[2:]] or range(1, len(json.loads((STORIES / st / "script.json").read_text())["storyboard"]) + 1)
    for n in ns:
        r = still_passed(st, n)
        print(f"shot {n}: {shot_hash(st, n)[:12]}  {'PASSED ' + str(r['score']) if r else 'not passed (or changed)'}")
