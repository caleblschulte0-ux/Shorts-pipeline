#!/usr/bin/env python3
"""Author brand-new explainer stories so the queue never runs dry.

The channel kept hitting an *empty queue*: once every configured story was
posted, the daily run had nothing fresh to ship and we fell back to re-posting
duplicates. This script INVENTS new, non-duplicate stories — title, hook,
closing, three data segments with illustrative numbers — and appends them to
``data_learning/niche.config.json`` (writing each segment's dataset under
``data_learning/data/``). Run it on a schedule to keep N un-posted stories in
the pipeline at all times, so the daily batch always has new material.

  python scripts/author_stories.py --count 5          # author 5 new stories
  python scripts/author_stories.py --top-up 8         # author until >=8 un-posted
  python scripts/author_stories.py --count 3 --dry-run

The numbers are explicitly *illustrative* (source.officiality = "illustrative",
matching the existing bundled datasets) and are authored by the same LLM client
the rest of the pipeline uses (Groq -> Gemini -> Anthropic, whichever key is
present). Every authored story is validated: unique slug/key, distinct topic
(via topic_guard), and it must actually build an insight before it's kept.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CONFIG = ROOT / "data_learning" / "niche.config.json"
DATA_DIR = ROOT / "data_learning" / "data"
POSTED_LOG = ROOT / "state" / "explainer_posted_log.json"

_VALID_INSIGHT = {"rank", "trend", "comparison", "share", "outlier"}

# The depiction vocabulary the creative director chooses from — each with a
# "use when" so the LLM picks the most ENTERTAINING way to show THIS data.
# Every one DEPICTS the data (motion / size / position / fill / count); there is
# no bare-number option, on purpose.
VIZ_VOCAB = {
    "timeline": "a glowing dot travels a time/number line to a point — for AGES, "
                "dates, 'how long ago', durations. REQUIRES viz_params."
                "{timeline_start, timeline_end} (numbers on the same scale as the "
                "value) and/or a 'period' on each point.",
    "scale_stack": "stacks N copies of a relatable object to show a magnitude "
                   "('as tall as N buses') — for the HEIGHT/DEPTH/DISTANCE/SIZE of "
                   "ONE thing. REQUIRES viz_params.scale_ref={object, per_value, unit}.",
    "fill_vessel": "a jar fills while a number counts up — for a single SHOCK "
                   "percentage or count.",
    "orbit": "bodies orbit a centre at radii set by value — for DISTANCES or a few "
             "counts (planets, moons, satellites).",
    "waffle_grid": "a 100-square grid fills to a percentage — for SHARES / "
                   "part-of-whole expressed in percent.",
    "pictorial_race": "bars race with an icon riding each tip — for a RANKING of "
                      "3-5 items.",
    "diorama": "illustrated cut-outs sized by value — for a RANK/COMPARISON of 2-4 "
               "CONCRETE drawable objects (animals, foods, vehicles, landmarks).",
    "geo_us": "US state choropleth — use when the labels are US STATES.",
    "geo_world": "world choropleth — use when the labels are COUNTRIES.",
    "trend": "an animated line — for a TIME SERIES across several periods.",
}
# Depictions that read as a stand-out 'moment' — aim for >=1 per story.
_NOVELTY = {"timeline", "scale_stack", "fill_vessel", "orbit", "waffle_grid", "diorama"}
_VALID_VIZ = set(VIZ_VOCAB) | {"geo_city", "pictograph", "bubbles"}
_DUP_THRESHOLD = 0.5          # topic_guard overlap fraction that = "already done"

# The composable SCENE element kit — the director can INVENT a bespoke depiction
# per data point by arranging these, instead of picking a fixed viz.
SCENE_ELEMENTS = {
    "fill_object": "fill a SUBJECT silhouette bottom-up to a % (a globe for "
                   "Earth/water, a body, a brain, a gas tank). Needs `subject` + "
                   "`data.value_from`. Best for a share / single %.",
    "object": "a subject cut-out sized by its value, with number+label. Needs "
              "`subject` + `data.value_from`. Use several in region 'ground-row' "
              "for an illustrated ranking of concrete things.",
    "stack": "stack N=value/per_value copies of an object to show a magnitude. "
             "Needs `subject` + `data.value_from` + `data.per_value`.",
    "orbit_group": "bodies orbit a centre at radii by value (distances/counts). "
                   "region 'full'.",
    "timeline_axis": "a marker travels a time/number axis (ages, dates). "
                     "region 'full'.",
    "bar": "a horizontal bar, length by value. `data.value_from`.",
    "bubble": "a circle, area by value. `data.value_from`.",
    "number": "a big count-up of one value. `data.value_from`.",
    "caption": "a short text line. `text`.",
}
_SCENE_TYPES = set(SCENE_ELEMENTS)
_SCENE_IMAGE = {"object", "fill_object", "stack"}
_SCENE_DATA = {"object", "fill_object", "stack", "number", "bar", "bubble"}
_SCENE_REGIONS = {"full", "center", "hero", "left", "right", "top", "bottom",
                  "ground-row"} | {f"grid-{i}" for i in range(1, 5)}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:48]


def _snake(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    return re.sub(r"_{2,}", "_", s)[:48]


def _posted_slugs() -> set[str]:
    if not POSTED_LOG.exists():
        return set()
    try:
        d = json.loads(POSTED_LOG.read_text())
        return set((d.get("posted") or d).keys())
    except Exception:  # noqa: BLE001
        return set()


def _unposted_count(cfg: dict) -> int:
    posted = _posted_slugs()
    return sum(1 for s in cfg.get("stories", []) if s["slug"] not in posted)


def _covered_subjects(cfg: dict) -> list[str]:
    """A compact 'already covered' list to steer the model away from repeats."""
    return [f"{s.get('title', s['slug'])}" for s in cfg.get("stories", [])]


def _too_similar(story: dict, cfg: dict) -> str | None:
    """Return the slug of an existing story this duplicates, or None. Reuses the
    topic_guard keyword-overlap heuristic so we dedupe at the TOPIC level."""
    from scripts.topic_guard import _kw, _story_keywords
    cand = _kw(story.get("title", ""), story.get("hook", ""),
               " ".join(seg.get("topic", "") for seg in story.get("segments", [])),
               " ".join(story.get("hashtags", [])))
    if not cand:
        return None
    for s in cfg.get("stories", []):
        existing = _story_keywords(s)
        shared = cand & existing
        if len(shared) / max(1, len(cand)) >= _DUP_THRESHOLD:
            return s["slug"]
    return None


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
_SYSTEM = (
    "You are a viral data-explainer producer for a YouTube Shorts channel. "
    "You invent SHORT, scroll-stopping data stories backed by concrete numbers. "
    "You output STRICT JSON only — no prose, no markdown fences."
)


def _user_prompt(cfg: dict, n: int) -> str:
    doctrine = cfg.get("topic_doctrine", "")
    covered = _covered_subjects(cfg)
    covered_blob = "; ".join(covered[-80:])     # most-recent window keeps it short
    schema = {
        "stories": [{
            "title": "5-9 word curiosity-gap title",
            "hook": "one punchy spoken opener, NO numbers-only, makes you stop scrolling",
            "closing": "one-line spoken takeaway",
            "question": "an engagement question for the comments",
            "hashtags": ["6-12 lowercase tags, no #"],
            "segments": [{
                "topic": "2-4 word topic label shown on screen",
                "insight_type": "rank | comparison | share | trend",
                "unit": "percent | dollars | years | x | mph | '' (blank for counts)",
                "scene": {"title": True, "elements": [
                    {"type": "one of the element kit", "region": "a region",
                     "subject": "drawable thing (image elements)",
                     "data": {"value_from": "star | item:0 | item:<label> | total"}}]},
                "viz": "OPTIONAL fallback named viz if no scene fits",
                "viz_params": {"...": "params for the fallback viz"},
                "say": "spoken line that NAMES the key numbers it shows",
                "points": [{"label": "concrete label", "value": 0,
                            "period": "optional year for timeline/trend"}]
            }]
        }]
    }
    kit = "\n".join(f"  - {k}: {v}" for k, v in SCENE_ELEMENTS.items())
    menu = "\n".join(f"  - {k}: {v}" for k, v in VIZ_VOCAB.items())
    exs = _scene_examples(cfg, 3)
    ex_blob = ("\nGreat scenes we've made before (learn from these, then do "
               "something fresh):\n" + json.dumps(exs)) if exs else ""
    return (
        f"Channel doctrine: {doctrine}\n\n"
        f"Invent {n} BRAND-NEW data stories that fit the doctrine. Each is a "
        f"25-40 second Short with EXACTLY 3 segments that build one arc.\n\n"
        "You are the CREATIVE DIRECTOR of a top-tier YouTube channel. For EACH "
        "segment, FIRST invent the single most ENTERTAINING way to VISUALLY depict "
        "THAT specific data — compose a `scene` from this element kit (arrange "
        "elements in regions, drive their size/fill/position from the data):\n"
        + kit + "\n\n"
        "REGIONS: full, center, hero, left, right, top, bottom, ground-row, "
        "grid-1..4. Put several `object` elements in 'ground-row' for an "
        "illustrated ranking. Use 'full' for orbit_group/timeline_axis.\n"
        + ex_blob + "\n\n"
        "Only if NOTHING in the kit fits, name a fallback `viz` instead:\n" + menu + "\n\n"
        "HARD RULES:\n"
        "- NEVER just show numbers. Every segment DEPICTS its data (a scene, or a "
        "fallback viz). No bare-number option exists.\n"
        "- Think like a pro: ages/dates -> a timeline_axis; a share/% -> fill a "
        "relevant SUBJECT (a globe for Earth/water) with fill_object; one big "
        "height/size -> a stack vs a hero object; a ranking of drawable things -> "
        "a ground-row of `object`s; distances/counts -> orbit_group.\n"
        "- VARY the depiction across the 3 segments; include at least ONE stand-out.\n"
        "- `subject` for image elements must be a CONCRETE drawable thing (animals, "
        "foods, vehicles, planets, landmarks, a globe) — never an abstraction.\n"
        "- Do NOT repeat or closely resemble any already-covered subject.\n"
        "- Each segment: 2-6 points with realistic, illustrative numbers (labelled "
        "'illustrative') and a dramatic spread. Add a 'period' per point for time.\n"
        "- 'say' lines must speak the actual numbers shown.\n"
        "- Prefer science, space, nature, the human body, history, records, scale "
        "and superlatives. Avoid dry personal-finance topics.\n\n"
        f"ALREADY COVERED (avoid these): {covered_blob}\n\n"
        "Return STRICT JSON matching this schema exactly:\n"
        + json.dumps(schema)
    )


# --------------------------------------------------------------------------- #
# Validation + materialisation
# --------------------------------------------------------------------------- #
def _num(x):
    try:
        return float(str(x).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _clean_viz(seg: dict, points: list) -> tuple[str, dict]:
    """Validate the authored depiction + its params against what each viz needs.
    Returns ("", {}) — so the render-time director picks a best-fit depiction —
    when the concept can't be supported by the data (e.g. timeline w/o a span)."""
    viz = str(seg.get("viz", "")).strip().lower()
    if viz not in _VALID_VIZ:
        return "", {}
    vp_in = seg.get("viz_params") or {}
    vp: dict = {}
    if viz == "timeline":
        lo, hi = _num(vp_in.get("timeline_start")), _num(vp_in.get("timeline_end"))
        if lo is not None and hi is not None and hi != lo:
            vp["timeline_start"], vp["timeline_end"] = lo, hi
        elif not any(p.get("period") for p in points):
            return "", {}
    elif viz == "scale_stack":
        ref = vp_in.get("scale_ref") or {}
        obj, per = str(ref.get("object", "")).strip(), _num(ref.get("per_value"))
        if not obj or not per or per <= 0:
            return "", {}
        vp["scale_ref"] = {"object": obj, "per_value": per,
                           "unit": str(ref.get("unit", "")).strip()}
    return viz, vp


def _resolve_sel(sel, points) -> bool:
    if sel in (None, "", "star", "total"):
        return bool(points)
    if isinstance(sel, str) and sel.startswith("item:"):
        k = sel[5:].strip()
        if k.isdigit():
            return 0 <= int(k) < len(points)
        return any(str(p.get("label", "")).lower() == k.lower() for p in points)
    return False


def _clean_scene(seg: dict, points: list) -> dict | None:
    """Validate + normalise an LLM-invented scene against the element kit and the
    segment's data. Returns a clean spec, or None (→ fall back to a viz kind)."""
    sc = seg.get("scene")
    if not isinstance(sc, dict):
        return None
    els = sc.get("elements")
    if not isinstance(els, list) or not (1 <= len(els) <= 6):
        return None
    clean = []
    for el in els:
        if not isinstance(el, dict):
            return None
        t = el.get("type")
        if t not in _SCENE_TYPES:
            return None
        reg = el.get("region", "center")
        if reg not in _SCENE_REGIONS:
            return None
        ne = {"type": t, "region": reg}
        if el.get("anim"):
            ne["anim"] = str(el["anim"]).strip().lower()
        if t in _SCENE_IMAGE:
            subj = str(el.get("subject", "")).strip()
            if not subj:
                return None
            ne["subject"] = subj
        if t in _SCENE_DATA:
            data = el.get("data") or {}
            sel = data.get("value_from")
            if not _resolve_sel(sel, points):
                return None
            ne["data"] = {"value_from": sel or "star"}
            if t == "stack":
                per = _num(data.get("per_value"))
                if not per or per <= 0:
                    return None
                ne["data"]["per_value"] = per
        if t == "caption":
            ne["text"] = str(el.get("text", "")).strip()
        clean.append(ne)
    return {"title": bool(sc.get("title", True)), "elements": clean}


def _scene_examples(cfg: dict, k: int = 3) -> list[dict]:
    """A few DIVERSE scenes already in the config — the 'growing library' the
    model learns from (quality compounds as more good scenes accumulate)."""
    seen, out = set(), []
    for s in cfg.get("stories", []):
        for seg in s.get("segments", []):
            sc = seg.get("scene")
            if not isinstance(sc, dict):
                continue
            sig = tuple(sorted(e.get("type", "") for e in sc.get("elements", [])))
            if sig in seen:
                continue
            seen.add(sig)
            out.append({"topic": seg.get("topic", ""), "scene": sc})
            if len(out) >= k:
                return out
    return out


def _coerce_story(raw: dict, used_slugs: set[str], used_keys: set[str]) -> dict | None:
    """Validate + normalise one LLM story into the on-disk config shape, or
    None if it's unusable."""
    try:
        title = str(raw["title"]).strip()
        hook = str(raw["hook"]).strip()
        segs_in = raw["segments"]
    except (KeyError, TypeError):
        return None
    if not title or not hook or not isinstance(segs_in, list) or len(segs_in) < 2:
        return None

    slug = _slugify(title)
    if not slug or slug in used_slugs:
        slug = f"{slug}-{len(used_slugs)}"
    if slug in used_slugs:
        return None

    segments, datasets = [], []
    for i, seg in enumerate(segs_in[:3]):
        if not isinstance(seg, dict):
            return None
        pts_in = seg.get("points") or []
        points = []
        for p in pts_in:
            try:
                pt = {"label": str(p["label"]).strip(),
                      "value": float(p["value"])}
            except (KeyError, TypeError, ValueError):
                continue
            if p.get("period") not in (None, ""):
                pt["period"] = str(p["period"]).strip()
            points.append(pt)
        if len(points) < 2:
            return None
        itype = str(seg.get("insight_type", "rank")).strip().lower()
        if itype not in _VALID_INSIGHT:
            itype = "rank"
        topic = str(seg.get("topic", title)).strip()[:40] or title
        key = _snake(f"{slug}_{topic}") or f"{slug}_seg{i}"
        if key in used_keys:
            key = f"{key}_{i}"
        used_keys.add(key)
        viz, viz_params = _clean_viz(seg, points)

        datasets.append({
            "key": key,
            "title": topic[:1].upper() + topic[1:],
            "unit": str(seg.get("unit", "")).strip(),
            "geography": "",
            "time_coverage": "",
            "insight_type": itype,
            "source": {
                "name": str(seg.get("source_name", "Illustrative dataset")).strip()
                        or "Illustrative dataset",
                "publisher": str(seg.get("source_name", "Illustrative")).strip()
                             or "Illustrative",
                "url": str(seg.get("source_url", "")).strip(),
                "officiality": "illustrative",
                "access_date": date.today().isoformat(),
            },
            "notes": "Illustrative figures; approximate real-world values for "
                     "visual storytelling.",
            "points": points,
        })
        seg_cfg = {
            "source": "offline",
            "key": key,
            "params": {"file": f"{key}.json"},
            "insight_type": itype,
            "role": f"{i + 1} · {topic.upper()[:18]}",
            "topic": topic,
        }
        if seg.get("say"):
            seg_cfg["say"] = str(seg["say"]).strip()
        # An invented SCENE wins (the director honours it first); a named viz is
        # the fallback. Keep both so render-time can still best-fit.
        scene = _clean_scene(seg, points)
        if scene:
            seg_cfg["scene"] = scene
        if viz:
            seg_cfg["viz"] = viz
        if viz_params:
            seg_cfg["viz_params"] = viz_params
        segments.append(seg_cfg)

    tags = [re.sub(r"[^a-z0-9]", "", str(t).lower())
            for t in (raw.get("hashtags") or [])]
    tags = [t for t in tags if t][:12] or ["data", "facts", "shorts"]

    story = {
        "slug": slug,
        "title": title,
        "hook": hook,
        "closing": str(raw.get("closing", "That's the story in the data.")).strip(),
        "hashtags": tags,
        "segments": segments,
        "question": str(raw.get("question",
                                "Which number surprised you most? Comment below.")).strip(),
    }
    story["_datasets"] = datasets        # carried out-of-band for writing
    used_slugs.add(slug)
    return story


def _renders(story: dict) -> bool:
    """Confirm every segment actually builds an insight (so we never ship a
    story the renderer will choke on)."""
    from data_learning import insights
    from data_learning.sources.offline import dataset_from_dict
    for seg, ds in zip(story["segments"], story["_datasets"]):
        try:
            dataset = dataset_from_dict(ds)
            insights.build(dataset, insight_type=seg.get("insight_type", "auto"),
                           ascending=bool(seg.get("ascending", False)))
        except Exception as e:  # noqa: BLE001
            print(f"    [skip] {story['slug']} segment {ds['key']} won't build: {e}")
            return False
    return True


def _seg_dataset(seg: dict) -> dict:
    fn = (seg.get("params") or {}).get("file") or f"{seg.get('key')}.json"
    p = DATA_DIR / fn
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _direct_batch(stories: list, examples: list | None = None) -> dict:
    """Ask the LLM (creative director) to INVENT a depiction per segment for a
    batch of existing stories. Returns {slug: [{scene|viz, ...}, ...per segment]}."""
    from script_generator import _call_llm, _strip_fence
    kit = "\n".join(f"  - {k}: {v}" for k, v in SCENE_ELEMENTS.items())
    menu = "\n".join(f"  - {k}: {v}" for k, v in VIZ_VOCAB.items())
    briefs = []
    for s in stories:
        segs = []
        for i, seg in enumerate(s.get("segments", [])):
            ds = _seg_dataset(seg)
            pts = ds.get("points", [])
            segs.append({
                "i": i, "topic": seg.get("topic", ""),
                "insight_type": seg.get("insight_type", ""),
                "unit": ds.get("unit", ""),
                "labels": [str(x.get("label")) for x in pts][:6],
                "values": [x.get("value") for x in pts][:6],
                "has_period": any(x.get("period") for x in pts),
            })
        briefs.append({"slug": s["slug"], "title": s.get("title", ""),
                       "segments": segs})
    ex_blob = ("\nGreat scenes we've made (learn from these):\n"
               + json.dumps(examples)) if examples else ""
    sysp = ("You are the creative director for a top-tier data-explainer YouTube "
            "channel. For each segment you INVENT the most ENTERTAINING way to "
            "depict that data. Output STRICT JSON only.")
    user = (
        "Compose a `scene` from this element kit (arrange elements in regions "
        "full/center/hero/left/right/top/bottom/ground-row/grid-1..4; drive "
        "size/fill/position from the data via data.value_from = "
        "star|item:<idx>|item:<label>|total):\n" + kit + ex_blob + "\n\n"
        "Think like a pro: share/% -> fill a relevant SUBJECT (globe for "
        "Earth/water) with fill_object; ranking of drawable things -> a "
        "'ground-row' of `object`s; ages/dates -> timeline_axis; distances/counts "
        "-> orbit_group; one big size -> stack vs a hero object. Only if nothing "
        "fits, name a fallback `viz` (+viz_params) from:\n" + menu + "\n\n"
        "For EACH story below, return the depiction for EACH segment IN ORDER. "
        "VARY within a story; NEVER bare numbers; places -> geo_us/geo_world.\n\n"
        "Return JSON mapping each slug to a list of "
        "{\"scene\":{...}} or {\"viz\":...,\"viz_params\":{...}} — one per "
        "segment, in order.\n\nStories:\n" + json.dumps(briefs))
    txt = _strip_fence(_call_llm(sysp, user))
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.S)
        return json.loads(m.group(0)) if m else {}


def _backfill(cfg: dict, dry_run: bool, batch: int = 8) -> int:
    """Run the creative director over EVERY existing story, tagging each segment
    with a depiction (viz + viz_params). One-time levelling-up of the back
    catalogue so re-renders/re-posts get the new look too."""
    stories = cfg.get("stories", [])
    changed = 0
    for start in range(0, len(stories), batch):
        chunk = stories[start:start + batch]
        print(f"[backfill] directing {start + 1}-{start + len(chunk)} of "
              f"{len(stories)}...")
        try:
            out = _direct_batch(chunk, examples=_scene_examples(cfg, 3))
        except Exception as e:  # noqa: BLE001
            print(f"  batch error: {e}")
            continue
        for s in chunk:
            choices = out.get(s["slug"])
            if not isinstance(choices, list):
                continue
            for seg, ch in zip(s.get("segments", []), choices):
                if not isinstance(ch, dict):
                    continue
                pts = _seg_dataset(seg).get("points", [])
                scene = _clean_scene(ch, pts)          # INVENTED scene wins
                if scene:
                    seg["scene"] = scene
                    changed += 1
                    continue
                seg.pop("scene", None)
                viz, vp = _clean_viz(ch, pts)
                if not viz:
                    continue
                seg["viz"] = viz
                if vp:
                    seg["viz_params"] = vp
                elif "viz_params" in seg:
                    del seg["viz_params"]
                changed += 1
    print(f"[backfill] set a depiction on {changed} segments "
          f"across {len(stories)} stories")
    if dry_run:
        for s in stories[:10]:
            print("  ", s["slug"],
                  [("scene" if seg.get("scene") else seg.get("viz", "-"))
                   for seg in s.get("segments", [])])
        return 0
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    print(f"[backfill] wrote {CONFIG.relative_to(ROOT)}")
    return 0


def _generate(cfg: dict, n: int) -> list[dict]:
    from script_generator import _call_llm, _strip_fence
    raw = _call_llm(_SYSTEM, _user_prompt(cfg, n))
    text = _strip_fence(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        data = json.loads(m.group(0))
    stories = data.get("stories") if isinstance(data, dict) else data
    return stories or []


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--count", type=int, help="author exactly N new stories")
    g.add_argument("--top-up", type=int, metavar="N",
                   help="author until at least N un-posted stories exist")
    g.add_argument("--backfill", action="store_true",
                   help="creative-direct every EXISTING story (set viz per segment)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be added; don't write files")
    ap.add_argument("--max-attempts", type=int, default=3,
                    help="LLM batches to try before giving up")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
    if args.backfill:
        return _backfill(cfg, args.dry_run)
    used_slugs = {s["slug"] for s in cfg.get("stories", [])}
    used_keys = {seg.get("key") for s in cfg.get("stories", [])
                 for seg in s.get("segments", []) if seg.get("key")}

    if args.top_up is not None:
        have = _unposted_count(cfg)
        need = max(0, args.top_up - have)
        print(f"un-posted={have}, target={args.top_up} -> need {need} new")
    else:
        need = max(0, args.count)
    if need == 0:
        print("queue already full; nothing to author.")
        return 0

    kept: list[dict] = []
    for attempt in range(1, args.max_attempts + 1):
        if len(kept) >= need:
            break
        want = need - len(kept)
        print(f"[attempt {attempt}] asking for {want} stories...")
        try:
            raws = _generate(cfg, want + 2)        # over-ask; some get filtered
        except Exception as e:  # noqa: BLE001
            print(f"  LLM/parse error: {e}")
            continue
        for raw in raws:
            if len(kept) >= need:
                break
            story = _coerce_story(raw, used_slugs, used_keys)
            if not story:
                print("  [skip] malformed story")
                continue
            dup = _too_similar(story, cfg)
            if dup:
                print(f"  [skip] {story['slug']} too close to existing '{dup}'")
                used_slugs.discard(story["slug"])
                continue
            if not _renders(story):
                used_slugs.discard(story["slug"])
                continue
            kept.append(story)
            cfg.setdefault("stories", []).append(story)   # so dedupe sees it too
            vizs = [seg.get("viz", "auto") for seg in story["segments"]]
            print(f"  [keep] {story['slug']}  ({len(story['segments'])} segs, "
                  f"viz={vizs})")

    if not kept:
        print("authored 0 usable stories.")
        return 1

    if args.dry_run:
        print(f"\nDRY RUN — would add {len(kept)} stories:")
        for s in kept:
            print(f"  {s['slug']}: {s['title']}")
        return 0

    # Write datasets, strip the out-of-band payload, persist the config.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for s in kept:
        for ds in s.pop("_datasets"):
            (DATA_DIR / f"{ds['key']}.json").write_text(json.dumps(ds, indent=2))
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    print(f"\nAdded {len(kept)} stories to {CONFIG.relative_to(ROOT)} "
          f"(+{sum(len(s['segments']) for s in kept)} datasets). "
          f"Un-posted now: {_unposted_count(cfg)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
