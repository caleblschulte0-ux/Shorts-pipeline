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

from shared import channel_registry as _reg      # noqa: E402
from shared import levity as _levity             # noqa: E402
from shared import package_buffer as _buf        # noqa: E402


def _levity_moves() -> list:
    return _levity.MOVES


def _levity_never() -> list:
    return _levity.ANTI_PATTERNS

SCHEMA = "chatgpt-authoring-request/v1"

# THE SLATE IS NOT DECLARED HERE. `SLATE_MIX` used to be a copy of a constant
# in package_buffer, which was itself a copy of a heading in
# CLAUDE_ROUTINE_INSTRUCTIONS.md — three copies of one ruling, and when the
# operator changed it only a fourth place (daily.yml's prompt) was updated.
# The takeover then kept asking ChatGPT for a retired format.
#
# Everything now resolves through config/channel_registry.json.

# How many days back a takeover slate must not collide with. Registry-driven
# per channel; this is only the fallback for a channel that omits it.
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
            "6-8 `shots`: {phrase, query}. Every `phrase` must "
            "be an EXACT substring of `script`. `query` is mood b-roll.",
            "3-5 `punches`: {phrase, text, color}. `phrase` an EXACT "
            "substring of `script`; `text` SHORT CAPS; color one of "
            "#ff3030 / #ffaa30 / #50ff80.",
            "Do not add the Data/Explainer mascot; Trending is a separate channel.",
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


# On a NORMAL day the pipeline finds the media first and only asks ChatGPT to
# fill the judged gaps. On a TAKEOVER day the packages do not exist when that
# search runs, so there is nothing to search FOR — which means the same pass
# that writes the script has to bring its own pictures. ChatGPT owns the whole
# day, or the day ships on stock filler.
#
# The pointer shape is deliberately identical to the `media` array entries it
# already produces, so Phase B verifies it with the SAME code path: SHA-256
# against the claim, a full pixel decode, and a placeholder check. A pointer
# that fails any of those is dropped and that shot falls to self-fill.
MEDIA_CONTRACT = {
    "rule": ("Every shot in every package you author needs an image. Attach "
             "it to the shot itself as `media` — do not put authored-package "
             "images in the top-level `media` array, which is keyed by "
             "request_id and has no request for work you invented."),
    "shape": {
        "shots": [{
            "phrase": "...exact substring of your script...",
            "query": "...what the shot shows...",
            "media": {
                "status": "fulfilled",
                "drive": {"file_id": "1AbC...",
                          "folder_id": "1FolderXyz...",
                          "filename": "<date>__authored-<slug>-s0.png",
                          "download_url": "https://drive.google.com/uc?"
                                          "export=download&id=1AbC...",
                          "sharing": "anyone_with_link"},
                "image": {"sha256": "...64 hex of the exact bytes...",
                          "bytes": 1554380, "format": "png",
                          "width": 1080, "height": 1080},
            },
        }],
    },
    "every_field_must_match_the_checkpoint": (
        "filename, file_id, folder_id, sha256, bytes, format, width, height "
        "and sharing are ALL compared against the checkpoint you wrote, and "
        "any disagreement refuses the image. Hash and byte count alone say "
        "the CONTENT matches; they say nothing about whether the pointer "
        "names the same asset you verified. Copy the values from the "
        "checkpoint — do not re-describe the file from memory."),
    "verified_on_arrival": [
        "SHA-256 recomputed from the downloaded bytes — a mismatch is "
        "refused, never pinned.",
        "Full pixel decode — an undecodable file is refused.",
        "Placeholder check — an image with <= 8 distinct colours is refused.",
        "A Drive file that is not link-visible serves an HTML page instead; "
        "that is detected and refused.",
    ],
    "checkpoint_every_shot": (
        "Each of these images ALSO needs a checkpoint, exactly like a bundle "
        "request: `exchange/bundles/<date>/media-progress/"
        "<safe_request_id>.json` with `request_kind: \"authored_shot\"`, the "
        "package slug in `package_id`, and the shot index in `shot_index`. "
        "There is no bundle request behind an authored shot, so build the id "
        "yourself: `authored-<slug>-s<shot_index>` (slug lowercased, anything "
        "outside [a-z0-9-] replaced by `-`). Derive it from slug + shot index "
        "ONLY — the 07:00 finalizer recomputes the identical string from the "
        "package on disk, and it cannot do that from a prompt or a counter. "
        "Upload the file as `<date>__<safe_request_id>.png`."),
    "if_you_cannot": ("Leave `media` off that shot and say so honestly. We "
                      "self-fill it from real stock media — weaker, but it "
                      "ships. A fabricated pointer or a wrong hash is worse "
                      "than an honest omission."),
    "text_card_and_graph_race": ("These formats have no `shots` and need no "
                                 "media from you — the renderer sources "
                                 "b-roll from `broll_query` and draws the "
                                 "chart itself."),
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


def missing_mix(have_packages: list[dict], target: int | None = None,
                channel: str = "trending") -> dict:
    """How many of each ACTIVE format the day still needs.

    Straight from the registry: it classifies what exists, subtracts, and
    never returns a retired format at all. `target` is accepted for callers
    that want a smaller-than-full day (a manual partial run); when it is
    below the registry's own count the ask is trimmed worst-covered-last.
    Passing None — the normal case — means "whatever the registry says"."""
    need = _reg.shortfall(channel, have_packages or [])
    if target is None:
        return need
    have_count = len(have_packages or [])
    short = max(0, int(target) - have_count)
    while sum(need.values()) > short:
        biggest = max(need, key=lambda f: need[f])
        if need[biggest] == 0:
            break
        need[biggest] -= 1
    return need


def active_format_specs(channel: str = "trending", reg=None) -> dict:
    """The writing spec for the formats that are ACTIVE today.

    FORMAT_SPECS holds how to WRITE each format — prose rules a validator
    cannot generate. Which formats are OFFERED, and their required fields,
    come from the registry, so retiring a format removes it from the brief
    without touching this file. A retired format is not listed at all rather
    than listed with a zero: a brief that mentions text_card is a brief that
    can produce one."""
    out = {}
    for fid in _reg.active_formats(channel, reg):
        spec = dict(FORMAT_SPECS.get(fid) or {})
        registry_spec = _reg.format_spec(channel, fid, reg)
        required = registry_spec.get("required_fields")
        if required:
            spec["required"] = list(required)
        spec["renderer"] = registry_spec.get("renderer", spec.get("renderer"))
        spec["media"] = _reg.media_requirements(channel, fid, reg)
        spec["target_today"] = int(registry_spec.get("target", 0))
        if not spec.get("rules"):
            spec["rules"] = [
                f"No prose spec is recorded for {fid!r} in "
                f"shared/authoring_brief.py:FORMAT_SPECS. Follow "
                f"`required` and the channel doctrine, and say in your "
                f"response that the spec was thin."]
        out[fid] = spec
    return out


def build_request(date: str, channel: str, *, have_packages: list[dict] | None
                  = None, target: int | None = None, reason: str = "") -> dict:
    """The authoring brief handed to ChatGPT inside the day's bundle.

    Every number in it comes from config/channel_registry.json. `target`
    stays available for a deliberately partial manual run; None means "the
    registry decides", which is what every automatic caller passes."""
    have_packages = have_packages or []
    need = missing_mix(have_packages, target, channel)
    total = sum(need.values())
    registry_target = _reg.target_count(channel)
    retired = _reg.retired_formats(channel)
    return {
        "schema": SCHEMA,
        "date": str(date),
        "channel": channel,
        "reason": reason or ("the Claude authoring Routine did not run and "
                             "the reserve bank could not cover the day"),
        "authored_already": len(have_packages),
        "target": int(target) if target is not None else registry_target,
        "registry_target": registry_target,
        "write": total,
        "mix": need,
        "retired_formats": retired,
        "retired_note": (
            f"These formats are RETIRED and must not be authored: "
            f"{', '.join(retired)}. They are absent from `formats` and from "
            f"`mix` on purpose. If an example anywhere — a README, an old "
            f"bundle, a remembered instruction — shows one, the registry "
            f"wins." if retired else
            "No formats are retired for this channel."),
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
        "formats": active_format_specs(channel),
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
            "SUPPLY THE MEDIA TOO. Every shot of every reddit_story you "
            "write needs an image attached as `media` per `media_contract`. "
            "This is the one pass — nothing downstream asks you again.",
            "VERIFY BEFORE YOU FINISH: every shot/punch `phrase` is an exact "
            "substring of its `script`; every `highlight` is an exact "
            "substring of its `text`; every `series.values` has the same "
            "length as `years`. These are mechanically checked on our side "
            "and a failure means that package is dropped from the slate.",
        ],
        "do_not_repeat": _recent_titles(channel),
        "levity": {
            "rule": ("Land ONE dry aside per script where the subject "
                     "allows it. This channel has never made anyone laugh "
                     "and that is a real gap, not a style preference."),
            "moves": _levity_moves(),
            "never": _levity_never(),
            "hard_gate": ("NO joke on anything involving death, injury, "
                          "crime victims, war, illness or missing persons. "
                          "Those stay completely straight — a quip there is "
                          "not a tone miss, it is unrecoverable."),
        },
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
        "media_contract": MEDIA_CONTRACT,
    }


def validate_authored(pkg: dict, *, known_titles: set[str] | None = None,
                      channel: str = "trending") -> list[str]:
    """Problems that disqualify a ChatGPT-authored package from promotion.

    Deliberately the SAME structural gate the reserve bank uses, so the
    brief, the bank, and the renderer all agree on what a valid package is.
    The evergreen/staleness gate is NOT applied — a takeover slate is for
    today, so "this morning" is correct language there and only wrong in
    the bank."""
    problems = _buf.structural_problems(pkg)
    # THE RETIREMENT GATE. A retired format must not reach a slate no matter
    # who wrote it — a remembered instruction, a README example, or an old
    # constant. Structural validity is not the question; authorisation is.
    fid = _reg.classify(pkg, channel)
    if fid and not _reg.is_authorable(channel, fid):
        spec = _reg.format_spec(channel, fid)
        problems.append(
            f"format {fid!r} is {spec.get('state')} for {channel} "
            f"(since {spec.get('retired_on', 'unknown')}): "
            f"{spec.get('retired_because', 'see config/channel_registry.json')}")
    elif not fid:
        problems.append(
            f"package matches no format registered for {channel} "
            f"(active: {', '.join(_reg.active_formats(channel))})")
    title = (pkg.get("title") or "").strip()
    if known_titles and title and title in known_titles:
        problems.append(f"title repeats a recently posted video: {title!r}")
    return problems


def slate_problems(packages: list[dict], *, target: int | None = None,
                   channel: str = "trending") -> list[str]:
    """Slate-level complaints — monoculture and RETIRED formats.

    Delegated to the registry so "what a good slate looks like" has exactly
    one definition. `target` is ignored except for backwards compatibility;
    the registry's own count is authoritative."""
    return _reg.slate_problems(channel, packages)


_SAFE_SLUG = re.compile(r"[^a-z0-9-]+")


def safe_slug(slug: str, fallback: str = "authored") -> str:
    """A filename-safe slug — ChatGPT output is untrusted input, and this
    string becomes a path."""
    s = _SAFE_SLUG.sub("-", (slug or "").lower()).strip("-")
    return (s or fallback)[:60]


# --------------------------------------------------------------------------
# The other channels
# --------------------------------------------------------------------------
# Trending is not the only channel a dark Claude hurts, it was only the
# loudest — its floor was "nothing". The others keep posting, but on words
# nobody wrote:
#
#   explainer/curiosity  story_forge fills the QUEUE from real World Bank
#       numbers with no brain involved, but the title/hook/narration fall to
#       a deterministic template. That template once shipped "Congo, Dem.
#       Rep. Beats Everyone On Male primary school age children
#       out-of-school" (scripts/story_forge.py). The numbers are fine; the
#       WORDS are the hole, and words are exactly what ChatGPT can write.
#   curiosity            its queue is stocked by the Claude routine, so it
#       can run DRY — a different failure from bad words.
#   third                genuinely cannot be pre-authored: its package is a
#       CAPTURE RECIPE (`title: "{clip_title}"`) and the clip it will title
#       does not exist until the run happens. Nothing to hand ChatGPT ahead
#       of time. It self-heals to Groq, then to a safe raw clip title.

# Paths and thresholds come from the registry — these names remain as
# properties so existing callers keep working, but nothing is typed twice.
#: Test seam. Production leaves this empty; tests point a channel's config or
#: posted log at a temp file WITHOUT having to fake a whole registry, and
#: without reintroducing a module-level constant that could drift.
PATH_OVERRIDES: dict[tuple[str, str], Path] = {}


def _cfg_path(channel: str, key: str = "config") -> Path:
    override = PATH_OVERRIDES.get((channel, key))
    if override is not None:
        return Path(override)
    return ROOT / _reg.paths(channel)[key]


def _queue_min(channel: str) -> int:
    q = _reg.queue_rule(channel) or {}
    return int(q.get("minimum_unposted") or 0)


# RESOLVED LAZILY. At import time a broken registry would raise here and the
# traceback would come from an import statement three frames from the cause —
# Phase A could not catch it and print the one thing an operator needs to see.
# Module __getattr__ defers the lookup to first use, where the caller can.
_LAZY_PATHS = {
    "NICHE_CONFIG": ("explainer", "config"),
    "CURIOSITY_CONFIG": ("curiosity", "config"),
    "EXPLAINER_LOG": ("explainer", "posted_log"),
    "CURIOSITY_LOG": ("curiosity", "posted_log"),
}


def __getattr__(name):
    if name in _LAZY_PATHS:
        return _cfg_path(*_LAZY_PATHS[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:                                # noqa: BLE001
        return default


def _posted_slugs(path: Path) -> set[str]:
    log = _load(path, {})
    entries = log.get("posted") if isinstance(log, dict) else log
    out = set()
    for e in entries or []:
        if isinstance(e, dict) and e.get("slug"):
            out.add(e["slug"])
    return out


def explainer_word_request(date: str) -> dict | None:
    """Stories sitting in the queue whose WORDS came from the deterministic
    fallback — i.e. no brain was reachable when story_forge composed them.

    This is a rewrite job, not an authoring job: the numbers are already
    right and must not move. Phase B runs `shared.punchup_guard` over what
    comes back, so a rewrite that touches a number is rejected outright."""
    cfg = _load(_cfg_path("explainer"), {})
    posted = _posted_slugs(_cfg_path("explainer", "posted_log"))
    needy = [s for s in cfg.get("stories") or []
             if s.get("words_by") == "deterministic"
             and s.get("slug") not in posted]
    if not needy:
        return None
    return {
        "schema": SCHEMA,
        "date": str(date),
        "channel": "explainer",
        "job": "rewrite_words",
        "reason": ("these stories were composed with NO brain reachable — "
                   "their numbers are real but their title/hook/narration "
                   "came from a deterministic template"),
        "write": len(needy),
        "stories": [{
            "slug": s.get("slug"),
            "current_title": s.get("title"),
            "current_hook": s.get("hook"),
            "current_closing": s.get("closing"),
            "current_question": s.get("question"),
            "says": [(seg or {}).get("say") for seg in s.get("segments") or []],
        } for s in needy],
        "hard_rules": [
            "You are rewriting WORDS around numbers that are already correct "
            "and sourced. You may not change, drop, or invent ANY number, "
            "percent, year, date, country or entity — a guard checks this "
            "mechanically and rejects the whole rewrite if you do.",
            "Return one `says` entry per segment, in the same order and the "
            "same count. Each speaks that segment's actual numbers in "
            "natural English, ~22 words.",
            "The title must name the surprise, not describe the dataset. "
            "'Congo, Dem. Rep. Beats Everyone On Male primary school age "
            "children out-of-school' is the failure this exists to fix.",
            "Hook stops the thumb in two seconds. Closing lands the point.",
        ],
        "where": {"preferred": "an `authored_explainer` array in "
                               "response.json, one object per slug with "
                               "title / hook / says / closing / question"},
    }


def curiosity_queue_request(date: str) -> dict | None:
    """The curiosity queue is stocked by the Claude routine, so a dark Claude
    drains it. Ask for long-form stories when it runs short."""
    cfg = _load(_cfg_path("curiosity"), {})
    posted = _posted_slugs(_cfg_path("curiosity", "posted_log"))
    unposted = [s for s in cfg.get("stories") or []
                if s.get("slug") and s["slug"] not in posted]
    minimum = _queue_min("curiosity")
    if len(unposted) >= minimum:
        return None
    return {
        "schema": SCHEMA,
        "date": str(date),
        "channel": "curiosity",
        "job": "stock_queue",
        "reason": (f"only {len(unposted)} un-posted curiosity stories "
                   f"remain (registry minimum {minimum}); the Claude "
                   f"routine that normally stocks this queue did not run"),
        "write": minimum - len(unposted),
        "required": ["slug", "title", "hook", "closing", "question",
                     "hashtags", "segments"],
        "hard_rules": [
            "Long-form curiosity: one genuinely surprising thing explained "
            "properly, not a listicle. Read data_learning/CURIOSITY_BRAIN.md "
            "for the voice and the topic bank.",
            "Every factual claim must be real and checkable. No invented "
            "statistics — this channel's whole premise is that the numbers "
            "are true.",
            "`slug` lowercase kebab-case, not already in "
            "data_learning/curiosity.config.json.",
        ],
        "queued_now": [s.get("slug") for s in unposted],
        "where": {"preferred": "an `authored_curiosity` array in "
                               "response.json, one story object per entry"},
    }


def all_requests(date: str, trending: dict | None = None) -> dict:
    """Every channel's ask for the day, keyed by channel. ONE bundle, so
    ChatGPT reads a single file and sees everything Claude did not do."""
    out: dict[str, dict] = {}
    if trending:
        out["trending"] = trending
    for fn in (explainer_word_request, curiosity_queue_request):
        try:
            req = fn(date)
        except Exception as exc:                     # noqa: BLE001
            print(f"[brief] {fn.__name__} unavailable: {exc}")
            continue
        if req:
            out[req["channel"]] = req
    return out
