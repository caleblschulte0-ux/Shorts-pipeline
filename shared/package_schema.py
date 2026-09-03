"""Is this package WELL FORMED? — the one structural gate for a trending
package, wherever it came from.

Every producer of a package is checked by this module and nothing else: the
Claude Routine's own slate, the in-CI brain's, and anything ChatGPT authors
during a takeover. One validator means a package that passes for one
producer passes for all of them, and a package that would explode at render
time is refused before it gets a slot.

    from shared import package_schema as sch
    sch.structural_problems(pkg)     # shape: fields, counts, cross-refs
    sch.staleness_problems(pkg)      # date-anchored language
    sch.retirement_problems(pkg)     # a format the channel no longer ships
    ok, why = sch.eligible(pkg)      # all three at once

HISTORY. This was `shared/package_buffer.py`, the reserve bank: a shelf of
pre-authored evergreen packages drawn when a day came up short. The operator
retired it on 2026-08-05 — *"there shouldn't be a reserve bank; if something
doesn't run properly, it goes through and tries again."* A shelf only ever
covers as many failures as somebody remembered to stock it for (ours held
two packages against a low-water mark of twelve), while re-authoring has no
such ceiling. The bank's storage half — deposit / select / draw / fill_day
and the draw-once ledger — is gone; `run_trending_daily._backfill` authors a
fresh replacement instead. The VALIDATION half is what survived, and it was
never about banking: it is the answer to "is this package well formed",
which every producer still needs.

`staleness_problems` outlived the bank for the same reason. Date-anchored
language ("Tuesday night", "breaking", "just announced") is still wrong in a
package authored at 09:19 UTC and rendered eight hours later, and very wrong
in one ChatGPT writes during a multi-day takeover.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

from shared import channel_registry as _reg

ROOT = Path(__file__).resolve().parent.parent

# THE MIX IS NOT DECLARED HERE. It lives in config/channel_registry.json and
# is resolved through shared/channel_registry.py, because a constant in this
# file is exactly what went stale: on 2026-07-31 the operator retired
# `text_card` and moved trending to 4 graph_race + 2 reddit_story, the ruling
# landed only in daily.yml's brain prompt, and this module went on validating
# against a slate that no longer existed.
CHANNEL = "trending"


def formats() -> tuple[str, ...]:
    """Formats the channel still ships — retired ones are gone, not zeroed."""
    return tuple(_reg.active_formats(CHANNEL))


def target_mix() -> dict:
    """One day's slate, from the registry."""
    return _reg.target_mix(CHANNEL)

# Authored slugs carry the ordering prefix from their filename
# ("03_textcard-shrinkflation"), so underscores are legal here.
_SLUG_OK = re.compile(r"^[a-z0-9][a-z0-9_-]{2,79}$")

# Language that pins a script to a specific day. Anything matching is
# refused: a package is authored hours before it renders and may be
# re-authored or replayed later, so "tonight" is a claim we cannot keep.
_DATE_ANCHORED = re.compile(
    r"\b("
    r"today|tonight|yesterday|tomorrow|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"this (morning|afternoon|evening|week|month|year|weekend)|"
    r"last (night|week|month|year|weekend)|"
    r"next (week|month|year)|"
    r"earlier (today|this week)|overnight|moments ago|just now|"
    r"just (announced|released|dropped|happened|confirmed)|"
    r"breaking|developing story|so far this (year|month)|"
    r"\d+\s+(minutes?|hours?|days?)\s+ago|"
    r"as of (today|this)"
    r")\b", re.I)
_MONTH_DAY = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2}\b", re.I)


# --------------------------------------------------------------------------
# shape
# --------------------------------------------------------------------------
def bare_slug(slug: str) -> str:
    """Slug without the filename ordering prefix — `03_textcard-foo` is the
    same package as `textcard-foo` — so dedupe compares bare slugs."""
    return re.sub(r"^\d+_", "", slug or "")


def format_of(pkg: dict) -> str:
    """Canonical format name — resolved by the registry's `detect` rules.

    Retired formats are still RECOGNISED here (a text_card authored before
    the retirement is still a text_card); `retirement_problems()` is what
    refuses a new one. Recognise-but-refuse, because a format we cannot name
    counts as "unknown" and quietly distorts every shortfall calculation."""
    return (_reg.classify(pkg, CHANNEL)
            or "explainer")     # the legacy stacked shape


def narrative_text(pkg: dict) -> str:
    """Only the prose a viewer hears or reads. Deliberately excludes
    `source` lines and chart data, where a year is a citation rather than
    a staleness signal."""
    parts = [pkg.get("title") or "", pkg.get("script") or "",
             pkg.get("text") or "", pkg.get("hook") or ""]
    for p in pkg.get("punches") or []:
        parts.append((p or {}).get("text") or "")
    return "\n".join(parts)


def _substrings_ok(haystack: str, needles, label: str) -> list[str]:
    return [f"{label} not a substring of the script: {n!r}"
            for n in needles if n and n not in haystack]


def _finite_number(v) -> bool:
    """A REAL, finite number. bool is excluded (True is an int in Python,
    but a chart of Trues is not data), and so are NaN/inf — the renderer
    divides, interpolates and takes maxima over these values, so anything
    else here is a crash or a nonsense frame waiting for render time."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v))


def _graph_data_problems(years: list, series: list) -> list[str]:
    """Every NUMERIC defect in a graph_race's data, before any gate that
    does arithmetic on it. Until 2026-08-24 the validator checked only
    LENGTHS (doctor finding d64b063a21bd): two series of strings sailed
    through with an empty problem list, because the drama gate's TypeError
    was swallowed by a blanket `except: pass` that read every crash as
    "engine absent". The one structural gate cannot wave through data the
    renderer will choke on."""
    bad: list[str] = []
    non_num = [y for y in years if not _finite_number(y)]
    if non_num:
        bad.append(f"years contain non-numeric/non-finite entries: "
                   f"{non_num[:4]!r}")
    elif any(b <= a for a, b in zip(years, years[1:])):
        bad.append(f"years are not strictly increasing: {years!r} — the "
                   f"race timeline would run backwards or fold on itself")
    for s in series:
        vals = (s or {}).get("values") or []
        non_num = [v for v in vals if not _finite_number(v)]
        if non_num:
            bad.append(f"series {(s or {}).get('name')!r} has non-numeric/"
                       f"non-finite values: {non_num[:4]!r}")
    return bad


def structural_problems(pkg: dict) -> list[str]:
    """The same hard rules the Routine is told to self-verify. A package
    that fails these would fail at render time too."""
    bad: list[str] = []
    fmt = format_of(pkg)
    # STRUCTURE, not authorisation. Every format the registry KNOWS is
    # checked here, including retired ones — a text_card authored before the
    # retirement is still a well-formed text_card, and refusing to parse it
    # would make it "unknown", which silently distorts every count. Whether a
    # format may still be AUTHORED is `retirement_problems()`'s question, and
    # `authoring_brief.validate_authored`'s for promotion.
    known = _reg.formats(CHANNEL, state=None)
    if fmt not in known:
        return [f"format {fmt!r} is not registered for {CHANNEL} "
                f"(registry knows: {', '.join(sorted(known))})"]
    slug = pkg.get("slug") or ""
    if not _SLUG_OK.match(slug):
        bad.append(f"slug {slug!r} is not a lowercase kebab-case slug")
    if not (pkg.get("title") or "").strip():
        bad.append("missing title")
    if len(pkg.get("hashtags") or []) < 6:
        bad.append("fewer than 6 hashtags")

    if fmt == "reddit_story":
        script = pkg.get("script") or ""
        if len(script.split()) < 80:
            bad.append(f"script is only {len(script.split())} words")
        if not pkg.get("shots"):
            bad.append("no shots")
        bad += _substrings_ok(
            script, [(s or {}).get("phrase") for s in pkg.get("shots") or []],
            "shot.phrase")
        bad += _substrings_ok(
            script, [(p or {}).get("phrase") for p in pkg.get("punches") or []],
            "punch.phrase")
    elif fmt == "text_card":
        text = pkg.get("text") or ""
        if len(text.split()) < 30:
            bad.append(f"text is only {len(text.split())} words")
        if not (pkg.get("broll_query") or "").strip():
            bad.append("missing broll_query")
        hl = pkg.get("highlights") or []
        if len(hl) < 4:
            bad.append(f"only {len(hl)} highlights")
        bad += _substrings_ok(text, hl, "highlight")
    elif fmt == "graph_race":
        years = pkg.get("years") or []
        series = pkg.get("series") or []
        graph_bad: list[str] = []
        if len(years) < 4:
            graph_bad.append(f"only {len(years)} years")
        if len(series) < 2:
            graph_bad.append(f"only {len(series)} series")
        for s in series:
            vals = (s or {}).get("values") or []
            if len(vals) != len(years):
                graph_bad.append(f"series {(s or {}).get('name')!r} has "
                                 f"{len(vals)} values for {len(years)} years")
        graph_bad += _graph_data_problems(years, series)
        bad += graph_bad
        # The renderer's drama gate — but only on data the shape/numeric
        # checks above accepted (running arithmetic over known-garbage
        # would just crash the gate on the defect already reported). The
        # gate itself FAILS CLOSED now: this used to be one blanket
        # `except: pass` meaning "engine absent, skip", which also ate
        # every CRASH — a TypeError over string values, an IndexError over
        # short series — so a package the renderer could not survive
        # validated clean (doctor d64b063a21bd). Absence and a crash are
        # named apart, and both refuse: a graph the gate never judged is
        # unproven, not passed.
        if not graph_bad:
            try:
                from engines import chart_race       # noqa: PLC0415
            except Exception as e:                   # noqa: BLE001
                bad.append(f"graph drama gate could not run — chart_race "
                           f"engine unavailable ({type(e).__name__}: "
                           f"{str(e)[:80]})")
            else:
                try:
                    verdict = chart_race.assess(pkg)
                except Exception as e:               # noqa: BLE001
                    bad.append(f"graph drama gate CRASHED "
                               f"({type(e).__name__}: {str(e)[:80]}) — an "
                               f"unjudged package is unproven, not passed")
                else:
                    ok = (verdict.get("ok") if isinstance(verdict, dict)
                          else verdict)
                    if not ok:
                        bad.append(f"fails the graph drama gate: {verdict}")
    return bad


def staleness_problems(pkg: dict) -> list[str]:
    """Date-anchored language that would read wrong weeks from now."""
    text = narrative_text(pkg)
    hits = {m.group(0).lower() for m in _DATE_ANCHORED.finditer(text)}
    hits |= {m.group(0).lower() for m in _MONTH_DAY.finditer(text)}
    if not hits:
        return []
    return [f"date-anchored language (a package must still read true when "
            f"it renders): "
            f"{', '.join(sorted(hits)[:6])}"]


def retirement_problems(pkg: dict) -> list[str]:
    """Refuse a format the registry has retired.

    Authoring one just guarantees a package that gets rejected downstream,
    burning a slot on the morning it was supposed to fill."""
    fmt = format_of(pkg)
    if _reg.is_authorable(CHANNEL, fmt):
        return []
    try:
        spec = _reg.format_spec(CHANNEL, fmt)
    except _reg.RegistryError:
        return [f"format {fmt!r} is not authorable for {CHANNEL} — the "
                f"registry does not know it"]
    return [f"format {fmt!r} is {spec.get('state')} "
            f"(since {spec.get('retired_on', 'unknown')}) — the channel only "
            f"ships: {', '.join(formats())}"]


def eligible(pkg: dict) -> tuple[bool, list[str]]:
    """(usable?, reasons it isn't). Every gate always runs so one report
    shows everything wrong at once."""
    problems = (structural_problems(pkg) + staleness_problems(pkg)
                + retirement_problems(pkg))
    return (not problems), problems
