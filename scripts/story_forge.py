#!/usr/bin/env python3
"""STORY FORGE — the channel's permanent supply of REAL, citable stories.

The empty queue was never a rendering problem: it was a SOURCING problem. The
old `author_stories.py` kept the queue full by having an LLM invent numbers
(`officiality: illustrative`), which the editorial gate correctly refuses to
publish — so the queue looked full and the channel still shipped nothing.

This forge fixes the actual cause. It goes and GETS real data:

  * World Bank Open Data (WDI)  — ~1,500 official indicators, keyless API.
    Indicators are DISCOVERED from the live catalogue, not hand-listed, so the
    supply doesn't run out: every run draws indicators nobody has used yet.
  * Our World in Data (grapher CSV) — curated seed series for the topics the
    World Bank doesn't cover well (space, oceans, biodiversity, tech).

For every series it fetches it writes a dataset under `data_learning/data/`
with HONEST provenance (publisher, url, access_date, officiality=official /
secondary), then composes 3-segment stories around a theme. The LLM only ever
writes the WORDS (title / hook / narration); it never touches a number — the
numbers come from the source and only from the source.

Every candidate must then clear, before it is kept:
  1. it builds (each segment produces a real insight),
  2. the editorial gate (real-data provenance + premise bar),
  3. topic dedupe against everything the channel has already covered.

  python scripts/story_forge.py --top-up 8      # keep >=8 un-posted stories
  python scripts/story_forge.py --count 3
  python scripts/story_forge.py --count 2 --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG = ROOT / "data_learning" / "niche.config.json"
DATA_DIR = ROOT / "data_learning" / "data"
POSTED_LOG = ROOT / "state" / "explainer_posted_log.json"
USED = ROOT / "state" / "forge_used.json"
LAST = ROOT / "state" / "forge_last.json"
CACHE = ROOT / "cache" / "forge"
UA = {"User-Agent": "Mozilla/5.0 (+data-minute-pipeline; contact via GitHub)"}
TODAY = date.today().isoformat()

WB = "https://api.worldbank.org/v2"
WB_SOURCE = {"name": "World Development Indicators",
             "publisher": "World Bank",
             "url": "https://data.worldbank.org",
             "officiality": "official"}
OWID_SOURCE = {"publisher": "Our World in Data",
               "officiality": "secondary"}

# Themes the channel actually wants (niche.config topic_doctrine): a candidate
# indicator has to look like ONE of these to be considered at all.
THEMES = {
    "energy": ["electricity", "energy", "renewable", "solar", "power",
               "fossil", "fuel", "nuclear"],
    "nature": ["forest", "species", "biodiversity", "land area", "marine",
               "protected area", "arable", "fish", "threatened"],
    "climate": ["co2", "emissions", "greenhouse", "methane", "particulate",
                "air pollution", "temperature"],
    "water": ["water", "freshwater", "sanitation", "drinking"],
    "health": ["life expectancy", "mortality", "immunization", "physicians",
               "hospital", "obesity", "smoking", "health expenditure",
               "birth rate", "fertility"],
    "population": ["population", "urban", "rural", "migration", "refugee",
                   "density", "age dependency"],
    "tech": ["internet", "mobile", "broadband", "telephone", "research and",
             "patent", "high-technology", "scientific"],
    "food": ["cereal", "crop", "food", "agricultur", "livestock", "fertilizer"],
    "travel": ["tourism", "air transport", "rail", "roads", "passengers"],
    "learning": ["school", "literacy", "education", "teachers", "pupil"],
    "work": ["labor force", "unemployment", "employment", "wage", "child labor"],
}
# Indicator names carrying these tokens are analyst plumbing, not a story.
_BORING = re.compile(
    r"\b(gni|ppp|constant|current us\$|balance of payments|deflator|"
    r"official exchange|net oda|dec alt|bop|imf|iso |wb |estimate, |"
    r"modeled ilo|lower bound|upper bound|standard error|broad money|"
    r"claims on|domestic credit|quasi|lcu|dod|debt service)\b", re.I)
# Indicator FAMILIES worth a curiosity channel (World Bank topic prefixes):
# people, health, education, environment, energy, agriculture/land, tech,
# infrastructure, tourism, labour. Everything monetary/fiscal is excluded on
# purpose — the doctrine says this is not a finance channel.
_FAMILIES = ("SP.", "SH.", "SE.", "EN.", "EG.", "AG.", "ER.", "IT.", "IS.",
             "ST.", "SL.", "SN.", "EP.", "MS.")

_YEAR_MIN = 1972


# --------------------------------------------------------------------------- #
# HTTP (best-effort: the forge never crashes a pipeline run)
# --------------------------------------------------------------------------- #
def _get(url: str, *, timeout: int = 40) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception as e:  # noqa: BLE001
        print(f"    [net] {type(e).__name__} {url[:90]}")
        return None


def _get_json(url: str, **kw):
    raw = _get(url, **kw)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return None


def _cached(name: str, loader):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / name
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            pass
    val = loader()
    if val:
        p.write_text(json.dumps(val))
    return val


# --------------------------------------------------------------------------- #
# Discovery — the live World Bank catalogue (this is why we don't run out)
# --------------------------------------------------------------------------- #
def wb_countries() -> dict:
    """iso3 -> name for REAL countries (aggregates like 'World' excluded)."""
    def load():
        out = {}
        for page in (1, 2):
            js = _get_json(f"{WB}/country?format=json&per_page=300&page={page}")
            if not js or len(js) < 2:
                break
            for c in js[1]:
                if (c.get("region") or {}).get("value") in (None, "Aggregates"):
                    continue
                out[c["id"]] = c["name"]
        return out
    return _cached("wb_countries.json", load) or {}


def wb_indicators() -> list[dict]:
    """Every WDI indicator, straight from the live catalogue."""
    def load():
        out, page = [], 1
        while page <= 4:
            js = _get_json(f"{WB}/indicator?source=2&format=json"
                           f"&per_page=500&page={page}")
            if not js or len(js) < 2 or not js[1]:
                break
            out += [{"id": i["id"], "name": i["name"]} for i in js[1]]
            if page >= int(js[0].get("pages", 1)):
                break
            page += 1
        return out
    return _cached("wb_indicators.json", load) or []


def _theme_of(name: str) -> str | None:
    """Whole-WORD match only — substring matching once themed 'Broad money' as
    'road' and put monetary plumbing on a nature channel."""
    low = f" {re.sub(r'[^a-z0-9 ]', ' ', name.lower())} "
    for theme, keys in THEMES.items():
        if any(f" {k} " in low or low.find(f" {k}") >= 0 and
               re.search(rf"\b{re.escape(k)}", low) for k in keys):
            return theme
    return None


def _split_unit(name: str) -> tuple[str, str]:
    """'Forest area (% of land area)' -> ('Forest area', '% of land area')."""
    m = re.match(r"^(.*?)\s*\(([^()]{2,40})\)\s*$", name.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return name.strip(), ""


def candidates(used: set[str], limit: int = 90) -> dict[str, list[dict]]:
    """Theme -> unused, on-doctrine indicator specs, newest catalogue first."""
    by_theme: dict[str, list[dict]] = {}
    for ind in wb_indicators():
        iid, name = ind["id"], ind["name"]
        if iid in used or _BORING.search(name) or len(name) > 95:
            continue
        if not iid.startswith(_FAMILIES):
            continue
        theme = _theme_of(name)
        if not theme:
            continue
        topic, unit = _split_unit(name)
        # WATCHABLE SUBJECT ONLY. An indicator can be perfectly real and still
        # be unspeakable on a Short: "Male primary school age children
        # out-of-school" and "Immunization, DPT" are catalogue entries, not
        # topics. Keep short, comma-free, ungendered subjects.
        if (len(topic.split()) > 5 or "," in topic
                or re.match(r"^(male|female)\b", topic, re.I)):
            continue
        by_theme.setdefault(theme, []).append(
            {"src": "wb", "id": iid, "topic": topic, "unit": unit})
    # deterministic rotation so successive runs draw DIFFERENT indicators
    off = len(used)
    for theme, lst in by_theme.items():
        lst.sort(key=lambda d: d["id"])
        k = off % max(1, len(lst))
        by_theme[theme] = (lst[k:] + lst[:k])[:limit]
    return by_theme


# --------------------------------------------------------------------------- #
# Fetch — real numbers, real provenance
# --------------------------------------------------------------------------- #
def _round(v: float) -> float:
    a = abs(v)
    if a >= 1000:
        return round(v)
    if a >= 10:
        return round(v, 1)
    return round(v, 2)


def fetch_trend(spec: dict) -> dict | None:
    """World-level time series for one indicator."""
    js = _get_json(f"{WB}/country/WLD/indicator/{spec['id']}"
                   f"?format=json&per_page=200&date={_YEAR_MIN}:2026")
    if not js or len(js) < 2 or not js[1]:
        return None
    rows = [(int(r["date"]), float(r["value"]))
            for r in js[1] if r.get("value") is not None]
    rows = sorted(rows)
    if len(rows) < 6:
        return None
    # 6 evenly spaced points across the covered span (first and last always in)
    idx = [round(i * (len(rows) - 1) / 5) for i in range(6)]
    pts = [{"label": str(rows[i][0]), "value": _round(rows[i][1]),
            "period": str(rows[i][0])} for i in sorted(set(idx))]
    if len({p["value"] for p in pts}) < 3:
        return None
    lo, hi = min(p["value"] for p in pts), max(p["value"] for p in pts)
    if lo == 0 or abs(hi - lo) / max(abs(lo), 1e-9) < 0.15:
        return None                      # a flat line is not a story
    return _dataset(spec, pts, "trend", "World",
                    f"{pts[0]['label']}-{pts[-1]['label']}")


def fetch_rank(spec: dict, countries: dict) -> dict | None:
    """Top-5 countries on one indicator, most recent value each."""
    js = _get_json(f"{WB}/country/all/indicator/{spec['id']}"
                   f"?format=json&per_page=400&mrnev=1")
    if not js or len(js) < 2 or not js[1]:
        return None
    rows = []
    years = []
    for r in js[1]:
        iso = r.get("countryiso3code")
        if iso not in countries or r.get("value") is None:
            continue
        try:
            rows.append((countries[iso], float(r["value"])))
            years.append(str(r.get("date", "")))
        except (TypeError, ValueError):
            continue
    if len(rows) < 12:
        return None
    rows.sort(key=lambda t: -t[1])
    top = rows[:5]
    # A ZERO IN THE TAIL IS AN ABSENCE, NOT A SPREAD.
    #
    # This guard exists to refuse a flat ranking — five identical bars, no
    # "whoa" — and its own divide-by-zero guard INVERTED it. With `top[-1]`
    # at 0.0 the denominator falls back to 1e-9 and the ratio comes out at
    # 8.6e10, so the flattest possible data scored as the most spectacular
    # finding in the catalogue. The forge preferentially picks high spread, so
    # it did not merely allow this shape, it hunted for it.
    #
    # It shipped on 2026-09-09 as `oil-rich-algeria-runs-on-0-fossil-fuels-at-
    # home`: "Top 5 countries" on fossil fuel energy consumption, reading
    # Kosovo 86.1, then Albania, Algeria, Angola and Antigua at 0.0 — the
    # first four countries ALPHABETICALLY, which is what a tie among absent
    # values sorts to. Algeria does not run on 0% fossil fuels. The World Bank
    # has no row for it, and the title of the video was the missing number.
    #
    # In a ranking ordered by value, a 0 inside the top five means fewer than
    # five entities have a value at all. That is never a finding.
    lead, tail = top[0][1], abs(top[-1][1])
    if lead <= 0 or tail <= 0:
        return None
    if lead / tail < 2.0:
        return None      # no spread -> five identical bars, and no "whoa"
    pts = [{"label": n, "value": _round(v)} for n, v in top]
    yr = max((y for y in years if y), default="")
    return _dataset(spec, pts, "rank", "Top 5 countries", yr)


def _dataset(spec: dict, points: list, itype: str, geo: str, cover: str) -> dict:
    src = dict(WB_SOURCE) if spec["src"] == "wb" else dict(spec["source"])
    src["access_date"] = TODAY
    if spec["src"] == "wb":
        src["url"] = f"https://data.worldbank.org/indicator/{spec['id']}"
        src["name"] = spec["topic"]
    key = _snake(f"{spec['id']}_{itype}") if spec["src"] == "wb" \
        else _snake(f"{spec['id']}_{itype}")
    return {"key": key,
            "title": spec["topic"][:1].upper() + spec["topic"][1:],
            "unit": spec.get("unit", ""),
            "geography": geo,
            "time_coverage": cover,
            "insight_type": itype,
            "source": src,
            "notes": f"Fetched live from {src['publisher']} on {TODAY}. "
                     f"Values are the publisher's, unmodified.",
            "points": points,
            "_indicator": spec["id"]}


def _snake(s: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s.lower())).strip("_")


def _slugify(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")[:60]


# --------------------------------------------------------------------------- #
# Compose — the LLM writes WORDS around numbers it may not touch
# --------------------------------------------------------------------------- #
def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f} million"
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    return f"{v:g}"


def _say(ds: dict) -> str:
    p, u = ds["points"], (ds["unit"] or "").strip()
    u = f" {u}" if u and len(u) < 22 else ""
    if ds["insight_type"] == "trend":
        a, b = p[0], p[-1]
        if a["value"] and b["value"]:
            x = b["value"] / a["value"]
            move = (f"{x:.1f} times higher" if x >= 1.15
                    else f"down to {abs(x)*100:.0f} percent of that"
                    if x <= 0.87 else "barely moved")
            return (f"In {a['label']}, {ds['title'].lower()} was "
                    f"{_fmt(a['value'])}{u}. By {b['label']}: "
                    f"{_fmt(b['value'])}{u} — {move}.")
    return (f"{p[0]['label']} leads at {_fmt(p[0]['value'])}{u}. "
            f"{p[1]['label']} is {_fmt(p[1]['value'])}{u}. "
            f"{p[-1]['label']} — {_fmt(p[-1]['value'])}{u}.")


def _fallback_words(dss: list[dict]) -> dict:
    """Deterministic title/hook that still names a real number (the premise gate
    demands one) — used whenever no brain is reachable."""
    # Lead with whichever segment has the most dramatic spread — the fallback
    # headline should be the story's strongest number, not just the first one.
    def _drama(d):
        v = [abs(p["value"]) for p in d["points"]] or [1]
        return max(v) / max(min(v), 1e-9)
    d0 = max(dss, key=_drama)
    p = d0["points"]
    subj = re.split(r"[,:(]", d0["title"])[0].strip().rstrip(".")[:46]
    if d0["insight_type"] == "trend" and p[0]["value"]:
        x = p[-1]["value"] / p[0]["value"]
        title = (f"{subj} Is {x:.1f}x Higher Than In {p[0]['label']}"
                 if x >= 1 else
                 f"{subj} Fell {100 - x * 100:.0f}% Since {p[0]['label']}")
        hook = (f"In {p[0]['label']} it was {_fmt(p[0]['value'])}. "
                f"Now it's {_fmt(p[-1]['value'])}, and almost nobody noticed.")
    else:
        x = p[0]["value"] / max(abs(p[2]["value"]), 1e-9)
        title = f"{p[0]['label']} Beats Everyone On {subj} — By {x:.1f}x"
        hook = (f"You'd guess {p[2]['label']} leads on {subj.lower()}. "
                f"It's {p[0]['label']} — {_fmt(p[0]['value'])} to "
                f"{_fmt(p[2]['value'])}.")
    return {"title": title[:95], "hook": hook,
            "closing": "The numbers were public the whole time.",
            "question": "Which number surprised you most?",
            "hashtags": ["data", "facts", "statistics", "shorts", "worldbank"]}


def _claude_words(sysmsg: str, user: str) -> dict | None:
    """The HEADLESS BRAIN (claude CLI on CLAUDE_CODE_OAUTH_TOKEN) — the same
    credential the showrunner judges on. The free-tier API keys 429 in CI,
    which is how a whole run shipped deterministic fallback titles like
    'Congo, Dem. Rep. Beats Everyone On Male primary school age children
    out-of-school'. This path is the reliable one; the API keys stay as
    backup below it."""
    import shutil
    import subprocess
    if not shutil.which("claude") or not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return None
    try:
        proc = subprocess.run(
            ["claude", "-p", f"{sysmsg}\n\n{user}", "--model",
             os.environ.get("FORGE_MODEL", "sonnet"),
             "--output-format", "text"],
            capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            return None
        m = re.search(r"\{.*\}", proc.stdout or "", re.S)
        return json.loads(m.group(0)) if m else None
    except Exception:  # noqa: BLE001
        return None


def _brain_words(dss: list[dict], reject_note: str | None = None) -> dict | None:
    brief = []
    for d in dss:
        pts = ", ".join(f"{p['label']}={p['value']}" for p in d["points"])
        brief.append(f"- {d['title']} ({d['unit'] or 'units'}), "
                     f"{d['insight_type']}, {d['geography']}: {pts}")
    # These are the EXACT criteria the adversarial publish-time judge applies
    # (scripts/editorial_gate.premise_ok). Writing to a softer bar is why the
    # forge kept banking stories that passed here and were held at publish:
    # "India's 153,868,700 hectares beat America's farmland" is a geography
    # comparison, not a reversal, and the judge said so.
    sysmsg = (
        "You write YouTube Shorts data explainers. HARD RULE: every number you "
        "write must appear VERBATIM in the data given to you — you may never "
        "invent, round differently, or extrapolate a number. Your job is the "
        "WORDS.\n"
        "The TITLE must reverse a specific expectation the viewer already "
        "holds AND hang on one consequential number. A ruthless editor will "
        "REJECT it otherwise. Automatic rejects:\n"
        "  - a bare noun phrase ('Forest Area By Country')\n"
        "  - a league table or geography comparison ('India Beats America On "
        "Farmland', 'Russia Has The Most Forest') — being biggest is not "
        "surprising\n"
        "  - a number with no belief attached to it\n"
        "What passes: the viewer believes X, the data says NOT-X, and one "
        "number proves it ('Landlines Fell Below Their 1993 Level', 'Cities "
        "Are Growing Half As Fast As In 1983'). Ask yourself what the viewer "
        "would have guessed, then write the title that corrects them.\n"
        "The hook is one spoken line that makes scrolling stop.")
    kit = ("  object      — a drawable SUBJECT cut-out sized by its value. "
           "region 'ground-row' for a row of 2-5 of them. needs subject + "
           "data.value_from ('item:0','item:1',... or 'star').\n"
           "  stack       — N copies of a subject stacked to show a magnitude. "
           "needs subject + data.value_from + data.per_value.\n"
           "  fill_object — a subject silhouette filled bottom-up to a share. "
           "needs subject + data.value_from.\n"
           "  timeline_axis / orbit_group — region 'full', for time or "
           "distances.\n"
           # THE OFFLINE FORMS. These need no generated imagery — they draw
           # from the icon library or from primitives — so they always render,
           # in a fraction of a second, and cost nothing if the image provider
           # is down. They were added to the kit and NOT to this prompt, which
           # meant the brain could not compose with the only elements that
           # reliably work.
           "  unit_figures — N copies of one icon in a block; COUNTING them is "
           "the number ('22 houses, each $20K'). needs subject + "
           "data.value_from + data.per_value (a rough guess; it is rescaled "
           "to a round unit).\n"
           "  balance     — two values on a set of scales, heavier side down. "
           "The clearest way to say 'this one is bigger' without an axis. "
           "needs data.value_from AND data.vs_from, naming two DIFFERENT "
           "items.\n"
           "  dot_field   — a share of a population as 'k in n' figures, some "
           "lit. ONLY for a percentage that is a share of something you could "
           "count out (prevalence, ownership, turnout). NEVER for an interest "
           "rate, a growth rate or a yield — those are not a proportion of "
           "anything. needs subject + data.value_from.\n"
           "  race_track  — 3-8 items as a RACE: rank becomes position and the "
           "gap between them becomes literal distance. Every runner is Data. "
           "region 'full', no other fields — it reads the whole insight. Two "
           "items is a duel (use balance), one is not a race.\n"
           # THE TIME MACHINES. Each reads the whole insight and takes no
           # parameters — the relationship decides them, so there is nothing
           # left for the writer to choose but WHICH.
           "  staircase   — a rising series as steps Data CLIMBS. Progress "
           "becomes height. region 'full'. Use when the numbers go up.\n"
           "  elevator    — a falling series as a lift descending past "
           "labelled floors. The value is a floor. region 'full'. Use when "
           "the numbers go down.\n"
           "  burden      — a cost as WEIGHT: a slab stack he holds over his "
           "head, growing until he buckles. region 'full'. Use for money "
           "going up, where the point is what it costs someone.\n"
           "  gauge       — a rate as a NEEDLE sweeping toward a red zone. "
           "region 'full'. Use for a speed or a per-unit figure, not a "
           "quantity.\n"
           "  skyline     — one item dwarfing the rest as a TOWER, with Data "
           "tiny at its foot so the height has a human unit. region 'full'. "
           "Use when one number is several times every other.\n"
           "  tower       — an accumulated total as a stack of blocks, Data on "
           "top, with a legend saying what one block is worth. region 'full'.\n"
           "  hurdle      — a value against a LINE it has to clear (the "
           "insight's baseline: a national average, a target, a record). "
           "region 'full'. Only when a baseline exists.\n"
           "  funnel      — named STAGES each smaller than the last, narrowing, "
           "with the share that survives to the end. region 'full'. Only for "
           "real stages — five cities sorted by size are a ranking, not a "
           "funnel.\n"
           "  conveyor    — a count PER UNIT OF TIME as things arriving on a "
           "belt. region 'full'. Only when the number really is a rate of "
           "arrival (per day, per year), never a total.\n"
           "  pipes       — one flow splitting, each branch as wide as its "
           "share. region 'full'. Only for a real composition, where the parts "
           "make up the whole.\n"
           "  spotlight   — the RANGE a number moved in, claiming no "
           "direction. region 'full'. For a series that zig-zags: every other "
           "machine asserts a direction and a swinging series has none.\n"
           "  road        — a series that BARELY MOVED, as a flat road Data "
           "cruises. region 'full'. Use when the story is that nothing "
           "changed — a flat line makes that look like nothing happened.\n"
           "  tape         — the SIZE of a change, as a measuring tape pulled "
           "between a then and a now. region 'full'.\n"
           "  bridge      — how far SHORT of a line it falls, as a bridge that "
           "does not reach. region 'full'. Needs a baseline.\n"
           "  centre      — items lined up shortest to tallest with Data "
           "walking to the middle one. region 'full'. For an average or a "
           "median, acted out rather than asserted.\n"
           "  coaster     — a zig-zag series as a rollercoaster track Data "
           "rides. region 'full'. Like the spotlight it claims no direction.\n"
           "  thermometer — a value climbing toward a limit, with the red zone "
           "shown. region 'full'. Use when the point is that it is getting "
           "CLOSE, not whether it cleared.\n"
           "  wheel       — a REPEATING series as a ferris wheel turning, one "
           "car per point. region 'full'. Only when the movement genuinely "
           "recurs — a crash and a recovery is not a season.\n"
           "  darts       — values on a dartboard, tight or scattered, for "
           "when the finding is that they are all nearly the SAME. region "
           "'full'. A sorted bar chart hides exactly this.\n"
           "  queue       — a backlog as a line of people growing behind Data. "
           "region 'full'. For a rising number of things WAITING, which is a "
           "different feeling from a rising number.\n"
           # THE FLOW MACHINES. Each is a different CLAIM about the same
           # numbers, so the words decide them: parts of a whole is a pipe
           # split, where it WENT is a sorter, what is LEFT is a leaky bucket.
           "  bottleneck  — stages as a pipe that PINCHES at the one step "
           "doing the damage, marked 'here'. region 'full'. Use when a single "
           "stage is the problem; a funnel says they leak away all the way "
           "down, this names the culprit.\n"
           "  leaky       — a bucket with a hole: how many were kept out of "
           "how many started, with the rest running out. region 'full'. For "
           "RETENTION — enrolled vs finished, signed up vs still there.\n"
           "  inout       — two pipes, one filling and one draining a tank, "
           "and the LEVEL is the consequence. region 'full'. For an income "
           "against an outgoing, an intake against a discharge. Only when the "
           "two numbers really are a flow in and a flow out.\n"
           "  sorter      — one stream arriving and dropped into labelled "
           "bins, each as full as its share. region 'full'. For where "
           "something WENT (spending by department, waste by destination) — a "
           "decision somebody made, not what a thing is made of.\n"
           "  chain       — named steps as chain links, thickness by value, "
           "the weakest drawn as a thread and marked 'it breaks here'. region "
           "'full'. For a dependency where every step must hold and the worst "
           "one sets the pace.\n"
           # THE UNCERTAINTY MACHINES. All four are the same numbers as
           # something else and a different CLAIM, so only use one when the
           # claim really is that: a chance is not a share, a projection is
           # not a measurement.
           "  spinner     — a CHANCE as a wheel with one slice lit, spinning. "
           "region 'full'. For the probability of one event ('a 23% chance'), "
           "NEVER for a share of a population — that is dot_field. It never "
           "lands, because landing would show an outcome nobody measured.\n"
           "  doors       — the same chance told long: a wall of n doors "
           "opened one at a time, all empty but one. region 'full'. Only for "
           "a genuine '1 in n' with n up to 50.\n"
           "  fan         — measured points solid, then a widening cone to a "
           "PROJECTED point, with the line where the data stops drawn and "
           "labelled. region 'full'. Only when the last point really is a "
           "projection dated well past the measured ones.\n"
           "  gears       — two meshed gears turning together, sized by their "
           "values. region 'full'. For two quantities that MOVE TOGETHER. Say "
           "'move together', never 'drives': it is a correlation.\n"
           "  slider      — one track, two ends, one handle: every unit of "
           "one is a unit of the other you did not get. region 'full'. For a "
           "real trade-off, not for any two numbers.\n"
           # PHYSICAL COMPARISONS. Each needs the claim to say so — every one
           # of them is a plain ranking by the numbers alone.
           "  density     — the SAME square twice, packed differently. region "
           "'full'. For a per-square-km / per-acre figure. The box never "
           "changes size: only the crowd inside it does.\n"
           "  nest        — the small thing tiled inside the big thing until "
           "it fills it, with the count. region 'full'. For 'X times bigger', "
           "when the ratio is between about 2 and 150.\n"
           "  chairs      — more people than seats, with the ones left "
           "standing. region 'full'. For a shortage: applicants per opening, "
           "families per home.\n"
           "  hourglass   — a LENGTH OF TIME as sand, one glass per item, the "
           "pile left at the bottom being the number. region 'full'. Only "
           "when the unit really is time.\n"
           "  trophies    — a tally where the objects are the point: one cup, "
           "one title. region 'full'. For titles / medals / championships, up "
           "to about 30.\n"
           "  basket      — what the same money actually BUYS, as two baskets "
           "filled from one note. region 'full'. For cost of living and "
           "purchasing power, where the price is not the story.\n"
           "  caption     — a short text line (needs text).")
    user = ("DATA (the only numbers you may use):\n" + "\n".join(brief) +
            "\n\nEach scene must DEMONSTRATE its number with a drawable "
            "object, not label it: a chart build with a caption is an "
            "automatic reject. Pick a concrete, everyday subject that stands "
            "for the quantity (rural population -> a house; fish catch -> a "
            "fish; health spending -> a pill bottle) and let its size, count "
            "or fill carry the value.\n\nELEMENT KIT:\n" + kit +
            "\n\nReturn STRICT JSON: {\"title\":str,\"hook\":str,"
            "\"closing\":str,\"question\":str,\"hashtags\":[str],"
            "\"says\":[str],\"scenes\":[{\"title\":true,\"elements\":"
            "[{...}]}]} where says AND scenes each have exactly "
            f"{len(dss)} entries, one per dataset in order. Each say speaks "
            "that dataset's actual numbers in spoken English (~22 words).\n\n"
            "SAY THE NUMBER THE PICTURE SHOWS. Each say line is spoken OVER "
            "its own beat's chart, so the LOUDEST number in it must be one "
            "that chart can show: a value from that dataset, a difference "
            "between two of them, a percentage change, or a share of the "
            "total. Do NOT convert a rate into a headcount or a price — "
            "\"34 percent, 2.6 billion people\" over a chart of percentages "
            "makes the viewer hunt for a number that is not on screen. Say "
            "\"34 percent, up from 22\" instead.")
    if reject_note:
        user += ("\n\nYour previous title was REJECTED by the editor for this "
                 f"reason — fix exactly this:\n{reject_note}")
    out = _claude_words(sysmsg, user)
    if out and out.get("title") and out.get("hook"):
        return out
    try:
        from shared.script_generator import _call_llm, _strip_fence
        raw = _strip_fence(_call_llm(sysmsg, user))
        m = re.search(r"\{.*\}", raw, re.S)
        out = json.loads(m.group(0))
        if not out.get("title") or not out.get("hook"):
            return None
        return out
    except Exception as e:  # noqa: BLE001
        print(f"    [brain] unavailable ({str(e)[:60]}) — deterministic words")
        return None


# NO authored viz. Hardcoding a kind per insight_type fought the viz director
# and lost: a forced 'pictorial_race' fell back to a static 'pictograph' and
# the scene measured 0.8 effective fps. Leaving viz unset lets the director
# best-fit the depiction by SHAPE and couple Data to it mechanically — the
# path the benchmark suite actually validates.


def _words_that_clear_the_bar(dss: list[dict]) -> tuple[dict, str]:
    """Ask the brain for words until the PUBLISH-TIME premise judge accepts
    them (up to 3 tries), feeding each rejection back in. A story that only
    passes the deterministic floor gets held at publish and wastes a render."""
    from scripts import editorial_gate as eg
    from shared import beat_match as bm
    last = None
    for attempt in range(3):
        w = _brain_words(dss, reject_note=last)
        if not w:
            break
        v = eg.premise_ok({"title": w.get("title", ""), "hook": w.get("hook", "")},
                          use_llm=True)
        reasons = list(v["reasons"]) if not v["ok"] else []
        # BEAT MATCHING. Every `say` line is spoken OVER its own beat's
        # picture, so the loudest number in it has to be one that picture can
        # show. Measured over the 858 configured beats that speak a quantity,
        # 15.5% failed this — and always the same way: the writer converts the
        # measured figure into a bigger one the data does not contain ("34
        # percent — 2.6 billion people", "on a 50 thousand dollar car"), and
        # the viewer hears a number they cannot find on screen.
        #
        # Fed back to the brain rather than refused outright: the story is
        # fine and the SENTENCE is fixable, which is exactly what this retry
        # loop is for.
        for i, (ds, say) in enumerate(zip(dss, w.get("says") or [])):
            vals = [p.get("value") for p in (ds.get("points") or [])
                    if isinstance(p, dict) and p.get("value") is not None]
            m = bm.check(str(say), vals, ds.get("unit", ""))
            if not m["ok"]:
                reasons.append(f"say[{i}]: {m['why']}")
        if v["ok"] and not reasons:
            return w, f"brain(attempt {attempt + 1}, judge {v['judge']})"
        last = "; ".join(reasons)[:300]
        print(f"    [words] rejected: {last[:140]}")
    return _fallback_words(dss), "deterministic"


def compose(dss: list[dict], used_slugs: set[str]) -> dict | None:
    # WHO wrote the words. The numbers always come from the source, but the
    # title/hook/narration come from a brain — and when no brain is reachable
    # (Claude out AND no Groq/Gemini key) the deterministic path produces
    # lines like "Congo, Dem. Rep. Beats Everyone On Male primary school age
    # children out-of-school". Recording it here is what lets the exchange
    # SEE that Claude contributed nothing and hand the words to ChatGPT
    # instead of shipping that. See shared/authoring_brief.py.
    words, words_by = _words_that_clear_the_bar(dss)
    title = str(words.get("title", "")).strip()
    slug = _slugify(title)
    if not slug or slug in used_slugs:
        slug = f"{slug}-{len(used_slugs)}"[:60]
    says = words.get("says") or []
    scenes = words.get("scenes") or []
    segs = []
    for i, d in enumerate(dss):
        say = str(says[i]).strip() if i < len(says) and says[i] else _say(d)
        seg = {"source": "offline", "key": d["key"],
               "params": {"file": f"{d['key']}.json"},
               "insight_type": d["insight_type"],
               "role": f"{i+1} · {d['title'].upper()[:18]}",
               "topic": d["title"][:40],
               "say": say}
        # A SCENE, not a chart. The gate blocks "the data is stated, not
        # demonstrated" — a scene sizes/stacks/fills a drawable subject by the
        # value, which is what the videos that actually ship do. Validated
        # against the element kit; an invalid scene is dropped, never shipped.
        if i < len(scenes):
            try:
                from scripts.author_stories import _clean_scene
                sc = _clean_scene({"scene": scenes[i]}, d["points"])
                if sc:
                    seg["scene"] = sc
            except Exception:  # noqa: BLE001
                pass
        segs.append(seg)
    tags = [re.sub(r"[^a-z0-9]", "", str(t).lower())
            for t in (words.get("hashtags") or [])]
    return {"slug": slug, "title": title,
            "hook": str(words.get("hook", "")).strip(),
            "closing": str(words.get("closing") or
                           "The numbers were public the whole time.").strip(),
            "hashtags": [t for t in tags if t][:12] or ["data", "facts", "shorts"],
            "question": str(words.get("question") or
                            "Which number surprised you most?").strip(),
            "segments": segs, "_datasets": dss,
            "words_by": words_by}


# --------------------------------------------------------------------------- #
# Gates
# --------------------------------------------------------------------------- #
def _builds(story: dict) -> bool:
    from data_learning import insights
    from data_learning.sources.offline import dataset_from_dict
    for seg, ds in zip(story["segments"], story["_datasets"]):
        try:
            insights.build(dataset_from_dict(ds),
                           insight_type=seg.get("insight_type", "auto"))
        except Exception as e:  # noqa: BLE001
            print(f"    [skip] {ds['key']} won't build: {str(e)[:70]}")
            return False
    return True


def _passes_editorial(story: dict) -> tuple[bool, list[str]]:
    """Provenance is checked against the datasets IN HAND (they aren't on disk
    yet on a dry run); the premise bar runs exactly as it will at publish."""
    from scripts import editorial_gate as eg
    bad = []
    for ds in story["_datasets"]:
        s = ds.get("source") or {}
        if str(s.get("officiality", "")).lower() not in eg.REAL_OFFICIALITY:
            bad.append(f"{ds['key']}: officiality={s.get('officiality')}")
        if not s.get("publisher") or not s.get("access_date"):
            bad.append(f"{ds['key']}: incomplete provenance")
    prem = eg.premise_ok(story, use_llm=True)
    return (not bad and prem["ok"]), bad + [f"premise: {r}" for r in prem["reasons"]]


def _too_similar(story: dict, cfg: dict) -> str | None:
    from scripts.topic_guard import _kw, _story_keywords
    cand = _kw(story.get("title", ""), story.get("hook", ""),
               " ".join(s.get("topic", "") for s in story["segments"]))
    if not cand:
        return None
    for s in cfg.get("stories", []):
        shared = cand & _story_keywords(s)
        if len(shared) / max(1, len(cand)) >= 0.45:
            return s["slug"]
    return None


# --------------------------------------------------------------------------- #
# Run
# --------------------------------------------------------------------------- #
def _load_used() -> dict:
    try:
        return json.loads(USED.read_text())
    except Exception:  # noqa: BLE001
        return {"indicators": []}


def _stable_hash(text: str) -> int:
    """A deterministic small integer for a string.

    `hash()` is salted per process in Python 3, so using it here would give the
    same theme a different shape on every run — which is worse than a fixed
    template, because a story that re-forges would silently change length.
    """
    import hashlib
    return int(hashlib.sha1((text or "").encode()).hexdigest()[:8], 16)


def _unposted(cfg: dict) -> int:
    try:
        posted = set(json.loads(POSTED_LOG.read_text()).get("posted", {}))
    except Exception:  # noqa: BLE001
        posted = set()
    return sum(1 for s in cfg.get("stories", []) if s["slug"] not in posted)


def forge(count: int, dry_run: bool = False) -> int:
    cfg = json.loads(CONFIG.read_text())
    used_state = _load_used()
    used_inds = set(used_state.get("indicators", []))
    used_keys = {seg.get("key") for s in cfg.get("stories", [])
                 for seg in s.get("segments", [])}
    used_slugs = {s["slug"] for s in cfg.get("stories", [])}
    countries = wb_countries()
    pool = candidates(used_inds)
    if not pool:
        print("no fresh indicators reachable (network?) — nothing forged")
        return 0
    print(f"themes available: {', '.join(f'{t}({len(v)})' for t, v in pool.items())}")

    made, leftovers = 0, []

    def keep(dss: list, label: str) -> bool:
        """Compose + gate + persist one story. Returns True if it was kept."""
        nonlocal made
        story = compose(dss, used_slugs)
        if not story:
            return False
        ok, why = _passes_editorial(story)
        if not ok:
            print(f"[{label}] HELD by editorial gate: {why[:2]}")
            return False
        if not _builds(story):
            return False
        dup = _too_similar(story, cfg)
        if dup:
            print(f"[{label}] duplicate of {dup} — skipped")
            return False
        print(f"[{label}] FORGED {story['slug']}: {story['title']}")
        for d in dss:
            print(f"    {d['key']}  {d['insight_type']}  "
                  f"{len(d['points'])}pts  src={d['source']['publisher']}")
        if not dry_run:
            for d in dss:
                out = {k: v for k, v in d.items() if not k.startswith("_")}
                (DATA_DIR / f"{d['key']}.json").write_text(
                    json.dumps(out, indent=2))
            entry = {k: v for k, v in story.items() if not k.startswith("_")}
            cfg.setdefault("stories", []).append(entry)
            from shared.fsutil import write_json_if_changed
            write_json_if_changed(CONFIG, cfg)
            USED.parent.mkdir(parents=True, exist_ok=True)
            USED.write_text(json.dumps(
                {"indicators": sorted(used_inds), "updated": TODAY}, indent=1))
        used_slugs.add(story["slug"])
        made += 1
        if not dry_run:
            # What this run created, so the posting step can target exactly
            # these instead of re-rendering older stories the gate already
            # rejected.
            try:
                prev = json.loads(LAST.read_text()).get("slugs", []) \
                    if LAST.exists() else []
            except Exception:  # noqa: BLE001
                prev = []
            LAST.write_text(json.dumps(
                {"slugs": prev + [story["slug"]], "at": TODAY}, indent=1))
        return True

    themes = sorted(pool, key=lambda t: -len(pool[t]))
    for theme in themes:
        if made >= count:
            break
        specs = pool[theme]
        # HOW MANY BEATS THIS STORY GETS.
        #
        # Every video this channel has ever posted is exactly three. Combined
        # with a fixed "(3 Charts)" title suffix and four uploads a day, that
        # is a template, and a template at volume is what YouTube's
        # repetitious-content policy is written about — the operator is being
        # penalised for it right now.
        #
        # Keyed on the theme AND this attempt's leading indicator, so it is
        # stable for a given story (one that re-forges keeps its shape) while
        # still varying WITHIN a theme — keying on the theme alone would have
        # given every health story ever made the identical length, which is a
        # smaller template but still a template. Weighted toward 3 because that
        # is the length the writing is tuned for: 2, 3, 3, 4.
        target = (2, 3, 3, 4)[_stable_hash(
            theme + (specs[0]["id"] if specs else "")) % 4]
        dss, tried, seen_fam = [], 0, set()
        while specs and len(dss) < target and tried < 40:
            spec = specs.pop(0)
            tried += 1
            # Each segment must be a DIFFERENT measurement: sibling indicators
            # (same family stem) render as the same chart twice over.
            fam = ".".join(spec["id"].split(".")[:2])
            if fam in seen_fam:
                continue
            ds = (fetch_trend(spec) if tried % 2 else None) \
                or fetch_rank(spec, countries) or fetch_trend(spec)
            if not ds or ds["key"] in used_keys:
                continue
            used_inds.add(spec["id"])
            used_keys.add(ds["key"])
            seen_fam.add(fam)
            dss.append(ds)
        if len(dss) < 2:
            # A thin theme's series are still REAL, fetched data — bank them
            # instead of throwing the fetch away; they become a cross-theme
            # story below rather than a wasted API round trip. Two is the floor:
            # one measurement is a stat, not a story you can build to.
            print(f"[{theme}] only {len(dss)} usable series — banked")
            leftovers += dss
            continue
        keep(dss, theme)
    # Cross-theme fill: banked series that each cleared the same quality
    # checks. Coherence comes from the words the brain writes over them. The
    # count varies here too — a mixed story is not automatically a three.
    while made < count and len(leftovers) >= 2:
        n_mix = min(len(leftovers), (2, 3, 3, 4)[_stable_hash(
            leftovers[0].get("key", "")) % 4])
        keep(leftovers[:n_mix], "mixed")
        leftovers = leftovers[n_mix:]
    print(f"\nforged {made} real-data stor{'y' if made == 1 else 'ies'} "
          f"({'dry run' if dry_run else 'written'})")
    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=0)
    ap.add_argument("--top-up", type=int, default=0,
                    help="forge until at least N un-posted stories exist")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = json.loads(CONFIG.read_text())
    n = a.count
    if a.top_up:
        have = _unposted(cfg)
        n = max(n, a.top_up - have)
        print(f"un-posted queue: {have}; target {a.top_up}; forging {n}")
    if n <= 0:
        print("queue already full — nothing to forge")
        return 0
    forge(n, dry_run=a.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
