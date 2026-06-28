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
_VALID_VIZ = {"geo_us", "geo_world", "geo_city", "callouts", "diorama",
              "trend", "pictograph", "bubbles"}
_DUP_THRESHOLD = 0.5          # topic_guard overlap fraction that = "already done"


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
                "viz": "diorama | geo_us | geo_world | trend | pictograph (optional)",
                "say": "spoken line that NAMES the key numbers it shows",
                "points": [{"label": "concrete label", "value": 0}]
            }]
        }]
    }
    return (
        f"Channel doctrine: {doctrine}\n\n"
        f"Invent {n} BRAND-NEW data stories that fit the doctrine. Each is a "
        f"25-40 second Short with EXACTLY 3 segments that build one arc.\n\n"
        "HARD RULES:\n"
        "- Do NOT repeat or closely resemble any already-covered subject.\n"
        "- Each segment needs 2-6 data points with realistic, illustrative "
        "numbers (approximate real-world values; they will be labelled "
        "'illustrative').\n"
        "- At least ONE segment must be a 'diorama': a RANK or COMPARISON of "
        "2-4 CONCRETE PHYSICAL THINGS that an illustrator can draw as single "
        "objects (e.g. animals, foods, vehicles, planets, landmarks) — never "
        "abstract concepts. Use literal object names as labels.\n"
        "- If a segment compares PLACES, use real US states (viz geo_us) or "
        "real countries (viz geo_world) as labels, and set the viz field.\n"
        "- Make the numbers have a dramatic spread so the visual pops.\n"
        "- 'say' lines must speak the actual numbers shown.\n"
        "- Prefer science, space, nature, animals, the human body, history, "
        "records, scale and superlatives. Avoid dry personal-finance topics.\n\n"
        f"ALREADY COVERED (avoid these): {covered_blob}\n\n"
        "Return STRICT JSON matching this schema exactly:\n"
        + json.dumps(schema)
    )


# --------------------------------------------------------------------------- #
# Validation + materialisation
# --------------------------------------------------------------------------- #
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
                points.append({"label": str(p["label"]).strip(),
                               "value": float(p["value"])})
            except (KeyError, TypeError, ValueError):
                continue
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
        viz = str(seg.get("viz", "")).strip().lower()
        viz = viz if viz in _VALID_VIZ else ""

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
        if viz:
            seg_cfg["viz"] = viz
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
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be added; don't write files")
    ap.add_argument("--max-attempts", type=int, default=3,
                    help="LLM batches to try before giving up")
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text())
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
