"""Storyboard review — every scene of a sleep film LOOKED AT before the
two-hour render, by the same brain that judges the finished film.

Why (2026-09-23): three CI films in a row scored 74 with `craft 1` and
`data_demo 3`. Every note was a picture defect a person sees in a second —
a sleeper in the fire, a wolf that read as a carcass, cave paintings in
the sky, a bundle across a head — and every one cost a two-hour render
and a fresh vision review to learn. The geometric checks (`scene.collisions`)
catch what geometry can catch; this catches the rest, on stills, in
minutes: the frames are tiled nine to a sheet with their passages, the
brain marks each one BROKEN (something drawn through something, cut off,
floating, malformed, unreadable) and says whether it SHOWS THE WORDS, and
the repairs are deterministic and small — a different layout, a prop
fewer, a different place — or, for a picture that does not match its
passage, one author call to re-specify the scene under the kit's own
vocabulary. Then the changed beats are looked at again. Up to ROUNDS.

The gate is untouched: this is a front-line editor, and the showrunner
still watches the finished film and can veto it. Nothing here lowers a bar;
it moves defects from the film's verdict to the storyboard, where fixing
them is cheap.

    python -m data_learning.ori_storyboard --slug <slug>            # review + repair, write the episode
    python -m data_learning.ori_storyboard --slug <slug> --sheets o/ # only draw the sheets
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(REPO / "scripts") not in sys.path:
    sys.path.append(str(REPO / "scripts"))

from data_learning import ori_sleep as OS                        # noqa: E402
from data_learning.doodle import scene as S                       # noqa: E402

LEDGER = REPO / "state" / "ori_storyboard.jsonl"
PER_SHEET = 9                    # 3 x 3 tiles, each 640 x 360 — readable, one image per call
ROUNDS = 3
SHOWS_MIN = 1          # a scene graded this or lower on showing its words is re-specified
MAX_RESPECS = 60       # author calls per polish, so a strict judge cannot cost a whole render slot
TILE_W, TILE_H = 640, 360

PROMPT = """You are the STORYBOARD EDITOR of a hand-drawn sleep film (round-headed \
cartoon people, ink outlines, flat colour, drawn by code). The image is a sheet \
of {n} storyboard frames, numbered 1-{n} in big white digits, laid out left to \
right, top to bottom. Under each number below is the narration the frame \
illustrates. Look at EVERY frame and answer for each:

  broken       true if anything is drawn wrong: a figure or prop drawn through \
another, a body or head crossed by a limb/tool/prop, something cut off by the \
frame edge, something floating where it cannot be (a painting in the sky), a \
malformed limb or hand, an animal or person that reads as dead/upside down, \
unreadable clutter. A calm, sparse picture is NOT broken.
  why          one short line naming the defect — or, when shows_words is \
under 2, the ACTIVITY the words describe that the frame does not show \
(e.g. "no knapping: the man only sits"); empty only when nothing is wrong
  shows_words  2 = the frame shows the place, time and THE ACTIVITY the words \
describe (name it to yourself first: sewing, knapping, a game, looking up, \
carrying wood, feeding the fire, sleeping) and a viewer who had not heard \
the words could guess them from the picture; 1 = right place and era but \
that activity is not visible (people who only sit where the words describe \
work, play or looking at the sky), or the picture could be any passage of \
the film; 0 = wrong or unrelated. Be strict on 2: the finished film is \
graded on whether each scene SHOWS its words, and 1 is the usual answer.

Frames:
{listing}

Return ONLY a JSON object: {{"frames": [{{"n": 1, "broken": false, "why": "", \
"shows_words": 2}}, ...]}} with one entry per frame, n from 1 to {n}."""

RESPEC = """One scene of a hand-drawn sleep film does not show its passage. Write a \
new scene spec for it in the kit's own vocabulary, so that a viewer who had \
not heard the words could guess the activity from the picture: give the people \
the ACTION the words name (a child at play crouches with a stick; sky-watchers \
look_up, one lying on their back on the grass; a fire-keeper does feed_fire; \
cold is hug_self in frost), put the activity in a close shot, and prefer a \
different setting from the old scene when the words allow it. \
Return ONLY JSON: SCENE.
Era: {era}
Chapter: "{chapter}"
Passage: "{say}"
The old scene: {old}
What was wrong: {why}
{vocab}"""


# ------------------------------------------------------------------ stills
def kit_sha() -> str:
    """What the drawings depend on: a stamp that says when a clean review is stale."""
    h = hashlib.sha1()
    for p in sorted((PKG / "doodle").glob("*.py")):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def flat_beats(ep: dict) -> list[dict]:
    out = []
    n = 0
    for ci, ch in enumerate(ep["chapters"]):
        for bi, b in enumerate(ch["beats"]):
            out.append(dict(index=n, chapter=ci, beat=bi, say=b["say"], scene=b["scene"]))
            n += 1
    return out


def still(ep: dict, fb: dict, out: Path, t: float = 1.7) -> Path:
    sc = S.Scene(fb["scene"], ep["era"], OS._scene_seed(ep["slug"], fb["index"], fb["scene"]))
    sc.frame(t).write_to_png(str(out))
    return out


def sheets(ep: dict, beats: list[dict], work: Path) -> list[tuple[Path, list[dict]]]:
    """Tile the beats' stills nine to a sheet, numbered. Returns
    [(sheet_png, beats_on_it)] in order."""
    from PIL import Image, ImageDraw, ImageFont
    work.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype(str(OS.FONTS / "LuckiestGuy-Regular.ttf"), 72)
    except OSError:                                    # pragma: no cover
        font = ImageFont.load_default()
    out = []
    for s0 in range(0, len(beats), PER_SHEET):
        group = beats[s0:s0 + PER_SHEET]
        cols = 3
        rows = (len(group) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * TILE_W, rows * TILE_H), (12, 12, 14))
        for k, fb in enumerate(group):
            png = work / f"still_{fb['index']}.png"
            still(ep, fb, png)
            im = Image.open(png).convert("RGB").resize((TILE_W, TILE_H))
            d = ImageDraw.Draw(im)
            d.text((14, 6), str(k + 1), font=font, fill=(255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0))
            sheet.paste(im, ((k % cols) * TILE_W, (k // cols) * TILE_H))
        p = work / f"sheet_{s0 // PER_SHEET:02d}.png"
        sheet.save(p)
        out.append((p, group))
    return out


# ------------------------------------------------------------------ the brain
def judge_available() -> bool:
    import shutil
    return bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") and shutil.which("claude")) or \
        bool(os.environ.get("GEMINI_API_KEY"))


def _default_judge(prompt: str, sheet: Path) -> dict:
    import showrunner_review as SR
    grades, _backend = SR._judge(prompt, [(str(sheet), "storyboard sheet", 0.0)])
    return grades


def review_sheet(sheet: Path, group: list[dict], judge) -> dict[int, dict]:
    """{beat index: {"broken": bool, "why": str, "shows_words": int}} for one
    sheet. A malformed answer for a frame counts as not reviewed (absent)."""
    listing = "\n".join(f"{k + 1}. \"{fb['say'][:260]}\"" for k, fb in enumerate(group))
    prompt = PROMPT.format(n=len(group), listing=listing)
    raw = judge(prompt, sheet)
    out = {}
    for fr in (raw or {}).get("frames") or []:
        try:
            k = int(fr.get("n")) - 1
            if not 0 <= k < len(group):
                continue
            out[group[k]["index"]] = dict(
                broken=bool(fr.get("broken")), why=str(fr.get("why") or "")[:200],
                shows_words=max(0, min(2, int(fr.get("shows_words", 2)))))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


# ------------------------------------------------------------------ repairs
def _next_setting(setting: str, era: str, avoid=()) -> str | None:
    """The next outdoor setting of the era that is not one of `avoid` (the
    neighbouring beats' settings: a repair that made the same picture as the
    beat before it put the shelf in breach of the author's own rule)."""
    names = [k for k, v in S.SETTINGS.items() if era in v.eras and not v.interior]
    if setting not in names or len(names) < 2:
        return None
    i = names.index(setting)
    for k in range(1, len(names)):
        cand = names[(i + k) % len(names)]
        if cand not in avoid:
            return cand
    return None


def repair_broken(spec: dict, era: str, round_: int, avoid=()) -> str | None:
    """A small deterministic change, escalating by round: another layout,
    one prop fewer, another place. Returns what was done, or None when
    nothing more can be tried. The result always validates."""
    old = json.loads(json.dumps(spec))
    if round_ == 1:
        spec["variant"] = int(spec.get("variant") or 0) + 1
        return "variant"
    if round_ == 2:
        props = S._prop_list(spec)
        for i in range(len(props) - 1, -1, -1):
            pr = S.PROPS.get(props[i]["name"])
            if pr is not None and not pr.living and not pr.light:
                del props[i]
                spec["props"] = [p if "at" in p else p["name"] for p in props]
                if not S.validate(spec, era):
                    return f"dropped {old['props'][i] if isinstance(old['props'][i], str) else old['props'][i]['name']}"
                spec.clear(); spec.update(old)
        spec["variant"] = int(spec.get("variant") or 0) + 1
        return "variant"
    nxt = _next_setting(spec.get("setting"), era, avoid)
    if nxt:
        spec["setting"] = nxt
        spec["props"] = [p for p in spec.get("props", [])
                         if S.PROPS.get(p if isinstance(p, str) else p["name"]) is not None and
                         (S.PROPS[p if isinstance(p, str) else p["name"]].settings is None or
                          nxt in S.PROPS[p if isinstance(p, str) else p["name"]].settings)]
        if not S.validate(spec, era):
            return f"setting -> {nxt}"
        spec.clear(); spec.update(old)
    spec["variant"] = int(spec.get("variant") or 0) + 1
    return "variant"


def respec(fb: dict, era: str, why: str, ask, chapter: str | None = None, chapter_beats=None) -> str | None:
    """Ask the author's brain for a scene that shows the passage. Kept only
    if it validates against the kit; otherwise the old scene stays."""
    import ori_author as A
    try:
        raw = ask(A.SYSTEM, RESPEC.format(era=era, say=fb["say"][:600], old=json.dumps(fb["scene"]),
                                          why=why or "the activity in the words is not shown",
                                          chapter=chapter or "", vocab=S.vocabulary(era)))
        new = A._parse(raw)
    except Exception as e:                                # noqa: BLE001
        return None if not isinstance(e, A.NoBrain) else None
    if not isinstance(new, dict) or S.validate(new, era):
        return None
    if chapter_beats is not None:
        # the author's own picture rules still hold: a respec that makes the
        # same picture as the beat before or after it is not an improvement
        before = set(A._chapter_problems(chapter_beats, era, 0, 10 ** 6))
        saved = dict(fb["scene"])
        fb["scene"].clear(); fb["scene"].update(new)
        after = set(A._chapter_problems(chapter_beats, era, 0, 10 ** 6))
        if any("same picture" in x for x in after - before):
            fb["scene"].clear(); fb["scene"].update(saved)
            return None
        return "respecified"
    fb["scene"].clear()
    fb["scene"].update(new)
    return "respecified"


# ------------------------------------------------------------------ the loop
def _log(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def polish(ep: dict, *, judge=None, ask=None, work: Path | None = None, rounds: int = ROUNDS,
           write: bool = False, path: Path | None = None) -> dict:
    """Review every scene, repair what is flagged, review the repairs. Mutates
    `ep` in place; writes it back when `write`. Never raises past a judge
    failure — a render must not wait on a storyboard nobody could read.
    Returns a report {reviewed, flagged, repaired, rounds, clean, skipped}."""
    stamp = ep.get("storyboard") or {}
    sha = kit_sha()
    if stamp.get("clean") and stamp.get("kit") == sha and not os.environ.get("ORI_STORYBOARD_FORCE"):
        return dict(reviewed=0, flagged=0, repaired=0, rounds=0, clean=True, skipped="already clean for this kit")
    judge = judge or _default_judge
    if ask is None:
        try:
            import ori_author as A
            ask = A._ask
        except Exception:                                # noqa: BLE001
            ask = None
    report = dict(reviewed=0, flagged=0, repaired=0, rounds=0, clean=False, skipped=None, notes=[])
    beats = flat_beats(ep)
    todo = beats
    respecs = 0
    with tempfile.TemporaryDirectory() as td:
        wd = Path(work or td)
        for r in range(1, rounds + 1):
            findings: dict[int, dict] = {}
            try:
                for sheet, group in sheets(ep, todo, wd / f"r{r}"):
                    findings.update(review_sheet(sheet, group, judge))
            except Exception as e:                        # noqa: BLE001
                report["skipped"] = f"nobody could look at the storyboard: {str(e)[:160]}"
                _log(dict(ts=datetime.now(timezone.utc).isoformat(timespec="seconds"), slug=ep["slug"],
                          round=r, error=report["skipped"]))
                return report
            report["rounds"] = r
            report["reviewed"] += len(findings)
            flagged = [fb for fb in todo if fb["index"] in findings and
                       (findings[fb["index"]]["broken"] or findings[fb["index"]]["shows_words"] <= SHOWS_MIN)]
            report["flagged"] += len(flagged)
            _log(dict(ts=datetime.now(timezone.utc).isoformat(timespec="seconds"), slug=ep["slug"], round=r,
                      reviewed=len(findings), flagged=[dict(index=fb["index"], **findings[fb["index"]])
                                                       for fb in flagged]))
            if not flagged:
                report["clean"] = True
                break
            again = []
            for fb in flagged:
                f = findings[fb["index"]]
                did = None
                if f["shows_words"] <= SHOWS_MIN and ask is not None and respecs < MAX_RESPECS:
                    respecs += 1
                    did = respec(fb, ep["era"], f["why"], ask,
                                 chapter=(ep["chapters"][fb["chapter"]].get("title") or ""),
                                 chapter_beats=ep["chapters"][fb["chapter"]]["beats"])
                if did is None:
                    chb = ep["chapters"][fb["chapter"]]["beats"]
                    avoid = {chb[j]["scene"].get("setting") for j in (fb["beat"] - 1, fb["beat"] + 1)
                             if 0 <= j < len(chb)}
                    did = repair_broken(fb["scene"], ep["era"], r, avoid=avoid)
                if did:
                    report["repaired"] += 1
                    report["notes"].append(f"beat {fb['index']} r{r}: {f['why'] or 'does not show the words'} -> {did}")
                    again.append(fb)
            todo = again
            if not todo:
                break
    ep["storyboard"] = dict(kit=sha, clean=report["clean"],
                            reviewed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M"),
                            rounds=report["rounds"], repaired=report["repaired"])
    if write:
        p = path or (OS.EPISODES / f"{ep['slug']}.json")
        p.write_text(json.dumps(ep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--sheets", default=None, help="only draw the storyboard sheets into this directory")
    ap.add_argument("--rounds", type=int, default=ROUNDS)
    args = ap.parse_args()
    ep = OS.load(args.slug)
    if args.sheets:
        out = sheets(ep, flat_beats(ep), Path(args.sheets))
        print(f"[storyboard] {len(out)} sheets in {args.sheets}")
        return 0
    if not judge_available():
        print("[storyboard] no judge available (CLAUDE_CODE_OAUTH_TOKEN + claude CLI, or GEMINI_API_KEY)")
        return 1
    rep = polish(ep, rounds=args.rounds, write=True)
    print(f"[storyboard] {json.dumps({k: v for k, v in rep.items() if k != 'notes'})}")
    for n in rep.get("notes", []):
        print("   ", n)
    return 0 if rep["clean"] or rep.get("skipped") else 2


if __name__ == "__main__":
    sys.exit(main())
