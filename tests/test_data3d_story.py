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
            # every beat is its own IDEA (caaleb 2026-11-13, of the banana short's five shots: "All those were just
            # varying shots of bananas getting browner. What the fuck is this?"): a story names one visual action per
            # beat in `ideas`, no two alike, and at most one beat may be the thing simply rotting, browning or dying.
            ideas = s["ideas"]
            assert len(ideas) == n and len({i.lower().strip() for i in ideas}) == n, f"{st.name}: one distinct idea per beat"
            decay = re.compile(r"\b(rot|rots|rotting|brown|browns|browning|blacken|blackens|wilt|wilts|dies|dying|decay)\b", re.I)
            assert sum(bool(decay.search(i)) for i in ideas) <= 1, f"{st.name}: more than one beat is just the thing decaying"
            assert sum(bool(decay.search(b)) for b in s["storyboard"]) <= 2, f"{st.name}: the storyboard keeps showing decay"


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


POSTED_BEFORE_THE_QUESTION = {"checkout", "banana"}


def test_a_3d_short_ends_on_a_question_and_its_music_sits_low():
    """caaleb 2026-11-13: "we need to be ending the videos with like a question, so people have a reason to comment
    or engage ... the music's a little too loud on these 3D videos." The closing line ends on a question the viewer
    can answer in a comment, short enough to say (the registry's question_words), and the 3D bed is under the 2D one."""
    reg = json.loads((ROOT / "config" / "channel_registry.json").read_text())
    pace = reg["channels"]["explainer"]["formats"]["data_story"]["pacing"]
    for st in STORIES:
        if st.name in POSTED_BEFORE_THE_QUESTION:
            continue
        last = json.loads((st / "script.json").read_text())["lines"][-1].strip()
        assert last.endswith("?"), f"{st.name}: the closing does not end on a question"
        q = re.split(r"(?<=[.!])\s+", last)[-1]
        assert len(q.split()) <= pace["question_words"], f"{st.name}: the question runs over question_words"
    src = (D3 / "story" / "assemble.py").read_text()
    m = re.search(r"^MUSIC_BED_3D = ([0-9.]+)", src, re.M)
    assert m and "sr.MUSIC_BED = MUSIC_BED_3D" in src
    sys.path.insert(0, str(ROOT / "data_learning"))
    bed = re.search(r"^MUSIC_BED = ([0-9.]+)", (ROOT / "data_learning" / "studio_render.py").read_text(), re.M)
    assert float(m.group(1)) < float(bed.group(1))


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


def test_the_precheck_catches_a_prop_too_small_or_cut_before_anything_renders():
    """caaleb 2026-11-13, after the saffron proofs failed the judge for props "a few pixels on a phone" and a pan cut by
    the frame edge: "Why don't we fix these things beforehand?" The consequence pre-check measures both, in seconds,
    before a frame renders: a floor that a few pixels cannot pass, and the group whole inside the frame."""
    src = (D3 / "store" / "staging.py").read_text()
    h = float(re.search(r"^CONSEQ_MIN_H = ([0-9.]+)", src, re.M).group(1))
    inside = float(re.search(r"^CONSEQ_INSIDE = ([0-9.]+)", src, re.M).group(1))
    assert h >= 0.1, "a consequence a tenth of the frame tall is the least a phone shows"
    assert inside >= 0.8
    assert "inside >= CONSEQ_INSIDE" in src
