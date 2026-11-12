"""The 3D shorts are made from STORY FOLDERS on one clock (2026-11-12, the second 3D short's brief: "Improve our
existing reusable 3D production system ... so these improvements carry forward into the third video").

Held here, offline, with no Blender: the clock tiles a story's narration into shots with no gap and no overlap at
30 fps; every story folder is complete (a line, a storyboard brief and a shot per narration line, and every claim
sourced); a new story's words fit the explainer's own pacing caps from the registry; and nothing in the 3D pipeline
names a frame rate of its own any more."""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D3 = ROOT / "tools" / "data3d"
sys.path.insert(0, str(D3))
import clock  # noqa: E402

STORIES = sorted(p for p in (D3 / "stories").iterdir() if (p / "script.json").exists())


def test_the_clock_is_30fps_and_tiles_every_story():
    assert clock.FPS == 30
    for st in STORIES:
        w = json.loads((st / "script.json").read_text())["draft_windows"]
        spans = [clock.span(w, k) for k in range(1, len(w) + 1)]
        assert spans[0][2] == 0
        for a, b in zip(spans, spans[1:]):
            assert a[2] + a[3] == b[2], f"{st.name}: shots overlap or leave a gap"
        assert spans[-1][2] + spans[-1][3] == clock.total(w)


def test_every_story_folder_is_complete():
    assert {"checkout", "banana"} <= {p.name for p in STORIES}
    for st in STORIES:
        s = json.loads((st / "script.json").read_text())
        n = len(s["lines"])
        assert len(s["draft_windows"]) == n and s["slug"]
        tree = ast.parse((st / "shots.py").read_text())
        shots = next(node for node in tree.body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "SHOTS")
        assert [k.value for k in shots.value.keys] == list(range(1, n + 1)), f"{st.name}: one shot per line"
        if st.name != "checkout":     # the first short predates the folder; every story after it carries all of it
            assert len(s["storyboard"]) == n
            assert s["sources"] and all(x["url"].startswith("https://") and x["says"] for x in s["sources"])
            # every beat happens SOMEWHERE OF ITS OWN (caaleb 2026-11-12, of five beats in one store aisle: "way too
            # similar to be the whole 4 different beats"): no two beats in a row share a place, and a short has three
            # places at least. The harness refuses a shot built somewhere other than its script says.
            sets = s["sets"]
            assert len(sets) == n, f"{st.name}: a place per beat"
            assert all(a != b for a, b in zip(sets, sets[1:])), f"{st.name}: two beats in a row in one place"
            assert len(set(sets)) >= 3, f"{st.name}: a short needs three places at least"
            known = set(re.findall(r'^PLACES = \{(.*)\}$', (D3 / "store" / "locations.py").read_text(), re.M)[0].replace('"', "").replace(" ", "").split(","))
            assert {x for x in sets if x != "store"} <= {k.split(":")[0] for k in known}, f"{st.name}: a place store/locations.py does not build"


def test_a_new_story_fits_the_explainers_pacing():
    reg = json.loads((ROOT / "config" / "channel_registry.json").read_text())
    pace = reg["channels"]["explainer"]["formats"]["data_story"]["pacing"]
    for st in STORIES:
        if st.name == "checkout":
            continue
        lines = json.loads((st / "script.json").read_text())["lines"]
        words = [len(x.split()) for x in lines]
        assert words[0] <= pace["hook_words"], f"{st.name}: hook too long"
        assert words[-1] <= pace["closing_words"], f"{st.name}: closing too long"
        assert all(w <= pace["say_words"] for w in words[1:-1]), f"{st.name}: a beat runs over say_words"
        assert len(lines) - 2 >= pace["min_beats"]


def test_no_part_of_the_3d_pipeline_keeps_its_own_frame_rate():
    files = list((D3).rglob("*.py")) + [ROOT / ".github/workflows/data3d_render.yml", ROOT / ".github/workflows/data3d_assemble.yml"]
    bad = []
    for f in files:
        if f.name in ("clock.py", "base_build.py") or "__pycache__" in f.parts or not f.exists():
            continue
        txt = f.read_text()
        for pat in (r"\bFPS\s*=\s*24\b", r"fps\s*=\s*24\b", r"/\s*24\b(?!\d)", r"\*\s*24\)", r'"-framerate",\s*"24"', r"\bF=24\b"):
            if re.search(pat, txt):
                bad.append(f"{f.relative_to(ROOT)}: {pat}")
    assert not bad, bad


def test_the_shorts_are_native_and_the_captions_sit_in_the_safe_area():
    src = (D3 / "story" / "assemble.py").read_text()
    assert "ALLOW_UPSCALE" in src and "(1080, 1920)" in src           # a smaller render is refused, never stretched
    vals = {k: int(v) for k, v in re.findall(r"(SAFE_L|SAFE_R|HOOK_TOP|CAP_BOTTOM)\s*=\s*(\d+)", src)}
    vals.update(dict(zip(("SAFE_L", "SAFE_R"), map(int, re.search(r"SAFE_L, SAFE_R = (\d+), (\d+)", src).groups()))))
    assert vals["CAP_BOTTOM"] >= 420, "the caption sits under the app's own title and buttons"
    assert vals["SAFE_R"] >= 150, "the caption runs under the like / share column"
    assert vals["HOOK_TOP"] >= 230, "the hook sits under the app's tabs"
