"""Authoring takeover — the brief that lets ChatGPT be the brain for a day.

The chain normally runs: Claude Routine authors 6 packages -> Phase A judges
the media -> ChatGPT fills gaps and punches up scripts -> Phase B -> render.
Every one of those first steps needs a live Claude subscription. If it lapses,
the Routine never fires, `daily.yml`'s in-CI brain step also fails, and the
reserve bank (`shared/package_buffer.py`) covers the day only while it has
stock.

This module is the next line: when Phase A finds the day still short, it
writes an AUTHORING REQUEST into the same `bundle.json` ChatGPT already reads
at 6:00 AM Central. ChatGPT sees `mode: "author"`, writes the missing
packages into its `response.json`, and Phase B validates and promotes them
into the day's package directory — after which the pipeline cannot tell the
difference between a ChatGPT slate and a Claude one.

The brief is deliberately self-contained: ChatGPT gets the full per-format
spec as DATA, not a pointer into a 900-line markdown file it may or may not
read. And the spec it is handed is generated from the same constants the
validator enforces, so "what we asked for" and "what we accept" cannot drift.

    from shared import authoring_brief as brief
    req = brief.build_request("20260801", "trending", have=0, target=6)
    problems = brief.validate_authored(pkg)     # [] means promotable
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import package_buffer as _buf        # noqa: E402

SCHEMA = "chatgpt-authoring-request/v1"

# The slate is 2 + 2 + 2 (CLAUDE_ROUTINE_INSTRUCTIONS.md). A takeover honours
# the same mix — a day of six identical formats is the regression that doc
# exists to prevent, and a fallback brain must not reintroduce it.
SLATE_MIX = dict(_buf.TARGET_MIX)

# How many days back a takeover slate must not collide with.
RECENT_DAYS = 6

FORMAT_SPECS = {
    "reddit_story": {
        "how_to_signal": "omit the `format` field, set `subreddit`",
        "renderer": "make_reddit_story.py",
        "shape": "full-screen gameplay + Reddit post card + narrated TTS",
        "required": ["subreddit", "slug", "title", "hashtags", "script",
                     "shots", "punches", "music_vibe"],
        "subreddit_options": ["pettyrevenge", "MaliciousCompliance",
                              "ProRevenge", "entitledparents",
                              "TalesFromTheCustomer", "IDontWorkHereLady"],
        "rules": [
            "ORIGINAL first-person story, 130-170 words, ONE paragraph.",
            "Open-loop hook; end on a satisfying twist or payoff, NOT a "
            "question.",
            "UNIVERSAL premises — workplace justice, petty/pro revenge, "
            "entitled customers or neighbours, scams turned around, karma. "
            "NO weddings, NO relationship/breakup/cheating drama.",
            "6-8 `shots`: {phrase, query, mascot_pose}. Every `phrase` must "
            "be an EXACT substring of `script`. `query` is mood b-roll.",
            "3-5 `punches`: {phrase, text, color}. `phrase` an EXACT "
            "substring of `script`; `text` SHORT CAPS; color one of "
            "#ff3030 / #ffaa30 / #50ff80.",
            "At most 3 non-idle mascot poses.",
        ],
    },
    "text_card": {
        "how_to_signal": 'set "format": "text_card"',
        "renderer": "make_text_card.py",
        "shape": "big typographic card over a looping topical b-roll clip, "
                 "no voice-over",
        "required": ["format", "slug", "title", "duration", "broll_query",
                     "text", "highlights", "hashtags", "music_vibe"],
        "rules": [
            "60-100 words of `text` in 2-3 short paragraphs separated by "
            "\\n\\n.",
            "First line is a scroll-stopping claim; last line is a punchy "
            "kicker.",
            "8-12 `highlights`, each an EXACT substring of `text` — these "
            "get the gold emphasis treatment.",
            "`broll_query` is a 1-3 word CONCRETE filmable thing "
            "(\"potato chips\", not \"consumer economics\").",
            "`duration` 6. No `shots`, no `script`, no `subreddit`.",
        ],
    },
    "graph_race": {
        "how_to_signal": 'set "format": "graph_race"',
        "renderer": "make_graph_race.py",
        "shape": "animated multi-series chart race — lines grow, a year "
                 "counter climbs, a live leaderboard reorders",
        "required": ["format", "slug", "title", "y_label", "duration",
                     "source", "years", "series", "hashtags", "music_vibe"],
        "rules": [
            "`years`: 6-8 ascending integers. `series`: 2-4 entries, each "
            "{name, color, icon, values} with `values` the SAME LENGTH as "
            "`years`.",
            "`icon`: a 2-letter country code (\"US\", \"CN\") for countries, "
            "otherwise a brand/org name to look up (\"Netflix\"). Omit only "
            "for abstract categories.",
            "BIG NUMBERS — a HARD renderer gate, not a preference: the "
            "chart is REFUSED if the leader peaks under 1,000 or grows less "
            "than 3x (1.6x when there is a lead change). A line creeping "
            "from 12 to 40 is an instant reject.",
            "Prefer a dramatic crossover or collapse mid-video.",
            "`source` must cite real, defensible numbers. Approximate is "
            "fine; FABRICATION IS NOT. `hook` (<=32 chars) is optional but "
            "strongly preferred — it buys the first-seconds hold.",
            "`title` <= 60 chars. `duration` 13. No `shots`, no `text`.",
        ],
    },
}


def _recent_titles(channel: str, days: int = RECENT_DAYS) -> list[str]:
    """Titles from the last few authored days — a takeover slate must not
    repeat what the channel just posted."""
    base = ROOT / "state" / ("third_packages" if channel == "third"
                             else "trending_packages")
    if not base.exists():
        return []
    day_dirs = sorted((d for d in base.iterdir()
                       if d.is_dir() and len(d.name) == 8 and d.name.isdigit()),
                      key=lambda d: d.name, reverse=True)[:days]
    out = []
    for d in day_dirs:
        for p in sorted(d.glob("*.json")):
            if p.name.startswith("_"):
                continue
            try:
                pkg = json.loads(p.read_text())
            except Exception:                        # noqa: BLE001
                continue
            if pkg.get("title"):
                out.append(pkg["title"])
    return out[:40]


def missing_mix(have_packages: list[dict], target: int) -> dict:
    """How many of each format the day still needs, honouring 2/2/2."""
    have = {f: 0 for f in _buf.FORMATS}
    for pkg in have_packages or []:
        f = _buf.format_of(pkg)
        if f in have:
            have[f] += 1
    need = {f: max(0, SLATE_MIX.get(f, 0) - have[f]) for f in _buf.FORMATS}
    # If the target is smaller than a full slate, trim worst-covered-last.
    short = max(0, target - sum(have.values()))
    while sum(need.values()) > short:
        biggest = max(need, key=lambda f: need[f])
        if need[biggest] == 0:
            break
        need[biggest] -= 1
    return need


def build_request(date: str, channel: str, *, have_packages: list[dict] | None
                  = None, target: int = 6, reason: str = "") -> dict:
    """The authoring brief handed to ChatGPT inside the day's bundle."""
    have_packages = have_packages or []
    need = missing_mix(have_packages, target)
    total = sum(need.values())
    return {
        "schema": SCHEMA,
        "date": str(date),
        "channel": channel,
        "reason": reason or ("the Claude authoring Routine did not run and "
                             "the reserve bank could not cover the day"),
        "authored_already": len(have_packages),
        "target": target,
        "write": total,
        "mix": need,
        "where": {
            "preferred": (
                "Add an `authored` array to the SAME response.json you "
                "already write, one complete package object per entry. One "
                "file write, no new plumbing."),
            "alternative": (
                f"Or commit one file per package to "
                f"exchange/bundles/{date}/authored/NN_slug.json. Both are "
                f"read; the response.json array is preferred because it is "
                f"a single write."),
            "never": (
                "Do NOT write into state/trending_packages/ directly. "
                "Everything you author is validated before promotion, and "
                "anything that fails validation is quarantined with reasons "
                "rather than silently rendered."),
        },
        "formats": FORMAT_SPECS,
        "hard_rules": [
            f"Write EXACTLY {total} package(s) in the mix above — "
            f"{', '.join(f'{n} x {f}' for f, n in need.items() if n)}.",
            "Every package a DIFFERENT topic. None may repeat a title in "
            "`do_not_repeat`.",
            "Real, verifiable stories only for news-based formats — "
            "wire-service (AP/UPI/Reuters/BBC) confirmation or skip it. "
            "r/nottheonion and r/FloridaMan carry satire reposts.",
            "NO fabricated statistics. A graph_race with invented numbers "
            "is worse than no video — the channel's whole data credibility "
            "rides on this.",
            "TOS-safe: no slurs, no explicit content, no gore.",
            "`slug` lowercase kebab-case; filenames/order 01..06 grouped by "
            "format.",
            "VERIFY BEFORE YOU FINISH: every shot/punch `phrase` is an exact "
            "substring of its `script`; every `highlight` is an exact "
            "substring of its `text`; every `series.values` has the same "
            "length as `years`. These are mechanically checked on our side "
            "and a failure means that package is dropped from the slate.",
        ],
        "do_not_repeat": _recent_titles(channel),
        "quality_bar": (
            "You are standing in for the channel's brain, not filling a "
            "quota. A deadpan, slightly incredulous friend telling you the "
            "most ridiculous thing they read today: dry wit, real voice, a "
            "hook that stops the thumb in two seconds, and a kicker that "
            "names the story instead of trailing off. Six mediocre packages "
            "is a worse outcome than four good ones — if you cannot make one "
            "land, write fewer and say so."),
        "read_first": ["CLAUDE_ROUTINE_INSTRUCTIONS.md",
                       "data_learning/SCHULTE_MEDIA_BRAIN.md",
                       "docs/FALLBACKS.md"],
    }


def validate_authored(pkg: dict, *, known_titles: set[str] | None = None
                      ) -> list[str]:
    """Problems that disqualify a ChatGPT-authored package from promotion.

    Deliberately the SAME structural gate the reserve bank uses, so the
    brief, the bank, and the renderer all agree on what a valid package is.
    The evergreen/staleness gate is NOT applied — a takeover slate is for
    today, so "this morning" is correct language there and only wrong in
    the bank."""
    problems = _buf.structural_problems(pkg)
    title = (pkg.get("title") or "").strip()
    if known_titles and title and title in known_titles:
        problems.append(f"title repeats a recently posted video: {title!r}")
    return problems


def slate_problems(packages: list[dict], *, target: int = 6) -> list[str]:
    """Slate-level complaints — the 6-of-one regression, mostly."""
    out = []
    counts: dict[str, int] = {}
    for pkg in packages:
        counts[_buf.format_of(pkg)] = counts.get(_buf.format_of(pkg), 0) + 1
    slugs = [(_p.get("slug") or "") for _p in packages]
    dupes = {s for s in slugs if slugs.count(s) > 1 and s}
    if dupes:
        out.append(f"duplicate slugs in one slate: {', '.join(sorted(dupes))}")
    if len(packages) >= target and len(counts) == 1:
        out.append(f"the whole slate is one format ({next(iter(counts))}) — "
                   f"the slate is 2 + 2 + 2 (see "
                   f"CLAUDE_ROUTINE_INSTRUCTIONS.md)")
    return out


_SAFE_SLUG = re.compile(r"[^a-z0-9-]+")


def safe_slug(slug: str, fallback: str = "authored") -> str:
    """A filename-safe slug — ChatGPT output is untrusted input, and this
    string becomes a path."""
    s = _SAFE_SLUG.sub("-", (slug or "").lower()).strip("-")
    return (s or fallback)[:60]
