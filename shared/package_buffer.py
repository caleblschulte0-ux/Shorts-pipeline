"""Reserve package buffer — the pipeline's answer to "the brain went dark".

Every path that authors a day's videos runs on a Claude subscription: the
Routine at ~09:19 UTC, and daily.yml's in-CI "Brain" step. If that
subscription lapses, the token is revoked, or the Routine simply doesn't
fire, the day has NO packages and the pipeline falls to the weak Groq
writer (or to `most_recent_package_dir()`, which re-serves yesterday's
already-posted slate).

The reserve fixes that with banked work instead of a weaker writer: while
the subscription is healthy, the Routine tops up a small bank of EVERGREEN
packages. When a day comes up empty, `fill_day()` draws from the bank into
`state/trending_packages/<date>/` and every downstream stage — Phase A,
ChatGPT, Phase B, the renderers — proceeds unchanged, because what it finds
on disk is an ordinary authored slate.

Two properties make this safe to run unattended:

  EVERGREEN ONLY  A banked package may sit for weeks, so anything
      date-anchored ("Tuesday night", "yesterday", "breaking") is refused
      at deposit time. A stale news script is worse than no video.
  DRAW ONCE       Withdrawal deletes the banked file and appends to
      `used.json`. A reserve package can never be served twice, so it can
      never collide with the posted-log dedupe.

    from shared import package_buffer as buf
    buf.inventory()                      # what's in the bank, by format
    buf.deposit(pkg, source="routine")   # bank one (returns None if unfit)
    buf.fill_day("20260801", target=6)   # draw into the day's package dir

CLI: `python scripts/package_reserve.py status|deposit|fill|prune`.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from shared import channel_registry as _reg

ROOT = Path(__file__).resolve().parent.parent

BUFFER_DIR = ROOT / "state" / "package_buffer"
PKG_DIR = BUFFER_DIR / "packages"
USED_LOG = BUFFER_DIR / "used.json"
DAY_DIR = ROOT / "state" / "trending_packages"
POSTED_LOG = ROOT / "state" / "posted_log.json"

# THE MIX IS NOT DECLARED HERE. It lives in config/channel_registry.json and
# is resolved through shared/channel_registry.py, because a constant in this
# file is exactly what went stale: on 2026-07-31 the operator retired
# `text_card` and moved trending to 4 graph_race + 2 reddit_story, the ruling
# landed only in daily.yml's brain prompt, and this module kept banking a
# retired format for a slate that no longer existed.
#
# `FORMATS` and `TARGET_MIX` remain as FUNCTIONS so the bank keeps its shape,
# but every value now comes from the registry.
#: Days of cover the bank aims to hold per active format.
LOW_WATER_DAYS = 2
BANK_CHANNEL = "trending"


def formats() -> tuple[str, ...]:
    """Active, bankable formats — retired ones are gone, not zeroed."""
    return tuple(_reg.active_formats(BANK_CHANNEL))


def target_mix() -> dict:
    """One day's slate, from the registry."""
    return _reg.target_mix(BANK_CHANNEL)


def low_water() -> dict:
    """Below this the bank is 'low'. Derived from the day's mix rather than
    typed, so retiring a format stops the bank asking for it and raising a
    format's target raises its buffer automatically."""
    return {f: n * LOW_WATER_DAYS for f, n in target_mix().items() if n}

# Authored slugs carry the ordering prefix from their filename
# ("03_textcard-shrinkflation"), so underscores are legal here.
_SLUG_OK = re.compile(r"^[a-z0-9][a-z0-9_-]{2,79}$")

# Language that pins a script to a specific day. Anything matching is
# refused: the whole point of the bank is that it keeps.
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
    same package as `textcard-foo` and must not be banked twice."""
    return re.sub(r"^\d+_", "", slug or "")


def format_of(pkg: dict) -> str:
    """Canonical format name — resolved by the registry's `detect` rules.

    Retired formats are still RECOGNISED here (a text_card banked before the
    retirement is still a text_card); `eligible()` is what refuses to bank a
    new one. Recognise-but-refuse, because a format we cannot name counts as
    "unknown" and quietly distorts every shortfall calculation."""
    return (_reg.classify(pkg, BANK_CHANNEL)
            or "explainer")     # the legacy stacked shape; not bankable


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


def structural_problems(pkg: dict) -> list[str]:
    """The same hard rules the Routine is told to self-verify. A package
    that fails these would fail at render time too."""
    bad: list[str] = []
    fmt = format_of(pkg)
    # STRUCTURE, not authorisation. Every format the registry KNOWS is
    # checked here, including retired ones — a text_card banked before the
    # retirement is still a well-formed text_card, and refusing to parse it
    # would make it "unknown", which silently distorts every count. Whether a
    # format may still be AUTHORED is `eligible()`'s question (for the bank)
    # and `authoring_brief.validate_authored`'s (for promotion).
    known = _reg.formats(BANK_CHANNEL, state=None)
    if fmt not in known:
        return [f"format {fmt!r} is not registered for {BANK_CHANNEL} "
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
        if len(years) < 4:
            bad.append(f"only {len(years)} years")
        if len(series) < 2:
            bad.append(f"only {len(series)} series")
        for s in series:
            vals = (s or {}).get("values") or []
            if len(vals) != len(years):
                bad.append(f"series {(s or {}).get('name')!r} has "
                           f"{len(vals)} values for {len(years)} years")
        # The renderer's own drama gate, if the engine is importable.
        try:
            from engines import chart_race          # noqa: PLC0415
            verdict = chart_race.assess(pkg)
            ok = verdict.get("ok") if isinstance(verdict, dict) else verdict
            if not ok:
                bad.append(f"fails the graph drama gate: {verdict}")
        except Exception:                            # noqa: BLE001
            pass                                     # engine absent: skip
    return bad


def staleness_problems(pkg: dict) -> list[str]:
    """Date-anchored language that would read wrong weeks from now."""
    text = narrative_text(pkg)
    hits = {m.group(0).lower() for m in _DATE_ANCHORED.finditer(text)}
    hits |= {m.group(0).lower() for m in _MONTH_DAY.finditer(text)}
    if not hits:
        return []
    return [f"date-anchored language (banked packages must keep): "
            f"{', '.join(sorted(hits)[:6])}"]


def retirement_problems(pkg: dict) -> list[str]:
    """Refuse to bank a format the registry has retired.

    The bank exists to cover a future day, and a future day will not ship a
    retired format — banking one just guarantees a draw that gets rejected
    downstream, on the morning it was supposed to save."""
    fmt = format_of(pkg)
    if _reg.is_authorable(BANK_CHANNEL, fmt):
        return []
    try:
        spec = _reg.format_spec(BANK_CHANNEL, fmt)
    except _reg.RegistryError:
        return [f"format {fmt!r} is not bankable for {BANK_CHANNEL} — the "
                f"registry does not know it"]
    return [f"format {fmt!r} is {spec.get('state')} "
            f"(since {spec.get('retired_on', 'unknown')}) — the bank only "
            f"holds formats the channel still ships: "
            f"{', '.join(formats())}"]


def eligible(pkg: dict) -> tuple[bool, list[str]]:
    """(bankable?, reasons it isn't). Every gate always runs so a deposit
    report shows everything wrong at once."""
    problems = (structural_problems(pkg) + staleness_problems(pkg)
                + retirement_problems(pkg))
    return (not problems), problems


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:                                # noqa: BLE001
        return default


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def used_slugs() -> set[str]:
    log = _read_json(USED_LOG, {"used": []})
    return {bare_slug(e.get("slug")) for e in log.get("used") or []
            if e.get("slug")}


def _authored_slugs() -> set[str]:
    """Slugs that already exist in any day's package directory. Prevents
    banking a duplicate of something the channel has already run."""
    out: set[str] = set()
    if not DAY_DIR.exists():
        return out
    for d in DAY_DIR.iterdir():
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            if p.name.startswith("_"):
                continue
            pkg = _read_json(p, {})
            if isinstance(pkg, dict) and pkg.get("slug"):
                out.add(bare_slug(pkg["slug"]))
    return out


def _banked_slugs() -> set[str]:
    return {bare_slug(e["package"].get("slug")) for e in _entries()
            if e.get("package", {}).get("slug")}


def _entries() -> list[dict]:
    if not PKG_DIR.exists():
        return []
    out = []
    for p in sorted(PKG_DIR.glob("*.json")):
        e = _read_json(p, None)
        if isinstance(e, dict) and isinstance(e.get("package"), dict):
            e["_file"] = str(p)
            out.append(e)
    return out


def entries() -> list[dict]:
    """Every banked entry, unsorted. Each carries `_file` (bank path),
    `banked_at`, `format`, and the `package` itself."""
    return _entries()


def drawn_count() -> int:
    """How many packages the bank has served over its lifetime."""
    return len(_read_json(USED_LOG, {"used": []}).get("used") or [])


def deposit(pkg: dict, *, source: str = "", force: bool = False
            ) -> tuple[Path | None, list[str]]:
    """Bank one package. Returns (path, problems); path is None when the
    package was refused (or is a duplicate)."""
    ok, problems = eligible(pkg)
    if not ok and not force:
        return None, problems
    slug = bare_slug(pkg.get("slug") or "")
    if slug in _banked_slugs():
        return None, [f"already in the bank: {slug}"]
    if slug in used_slugs():
        return None, [f"already drawn from the bank once: {slug}"]
    if slug in _authored_slugs():
        return None, [f"already authored for a day's slate: {slug}"]
    clean = {k: v for k, v in pkg.items() if not k.startswith("_")}
    clean["slug"] = slug
    entry = {"banked_at": _now(), "source": source,
             "format": format_of(clean), "package": clean}
    path = PKG_DIR / f"{entry['format']}__{slug}.json"
    _write_json(path, entry)
    return path, problems


def inventory() -> dict:
    """What the bank holds, by format, oldest first."""
    by_fmt: dict[str, list[dict]] = {f: [] for f in formats()}
    for e in _entries():
        by_fmt.setdefault(e.get("format") or "?", []).append(e)
    for v in by_fmt.values():
        v.sort(key=lambda e: e.get("banked_at") or "")
    return by_fmt


def low_formats() -> list[str]:
    """Formats sitting under their low-water mark — what to top up next."""
    inv, lw = inventory(), low_water()
    return [f for f in formats() if len(inv.get(f) or []) < lw.get(f, 0)]


def select(count: int, *, mix: dict | None = None) -> list[dict]:
    """Choose up to `count` banked entries, honouring the format mix where
    the bank allows and back-filling from whatever is left otherwise.
    Read-only — nothing is consumed until `draw()`."""
    mix = dict(mix or target_mix())
    inv = inventory()
    picked: list[dict] = []
    for fmt in formats():
        want = min(mix.get(fmt, 0), count - len(picked))
        picked += (inv.get(fmt) or [])[:max(0, want)]
    if len(picked) < count:                      # back-fill, oldest first
        chosen = {e["_file"] for e in picked}
        rest = sorted((e for e in _entries() if e["_file"] not in chosen),
                      key=lambda e: e.get("banked_at") or "")
        picked += rest[:count - len(picked)]
    return picked[:count]


def draw(entries: list[dict], *, date: str, reason: str = "") -> list[dict]:
    """Consume banked entries: append to used.json, delete the bank file,
    return the packages. Irreversible by design — a reserve package is
    served exactly once, so it can never duplicate an upload."""
    log = _read_json(USED_LOG, {"used": []})
    log.setdefault("used", [])
    out = []
    for e in entries:
        pkg = dict(e["package"])
        pkg["_reserve"] = {"banked_at": e.get("banked_at"),
                           "drawn_on": date, "reason": reason}
        out.append(pkg)
        log["used"].append({"slug": pkg.get("slug"),
                            "format": e.get("format"),
                            "banked_at": e.get("banked_at"),
                            "used_on": date, "reason": reason})
        try:
            Path(e["_file"]).unlink()
        except OSError:
            pass
    _write_json(USED_LOG, log)
    return out


def fill_day(date: str, *, target: int = 6, reason: str = "",
             dry_run: bool = False) -> dict:
    """Top the day's package directory up to `target` packages from the
    bank. A no-op when the day is already full — this NEVER displaces work
    the brain actually produced, it only covers a shortfall.

    Returns a report dict; `drawn` is the packages written."""
    day = DAY_DIR / str(date)
    have = [p for p in sorted(day.glob("*.json"))
            if not p.name.startswith("_")] if day.exists() else []
    need = max(0, target - len(have))
    report = {"date": str(date), "existing": len(have), "target": target,
              "need": need, "drawn": [], "shortfall": need,
              "inventory": {f: len(v) for f, v in inventory().items()}}
    if need == 0:
        return report

    chosen = select(need)
    if not chosen:
        return report
    if dry_run:
        report["drawn"] = [e["package"].get("slug") for e in chosen]
        report["shortfall"] = need - len(chosen)
        return report

    packages = draw(chosen, date=str(date), reason=reason)
    day.mkdir(parents=True, exist_ok=True)
    start = len(have)
    for i, pkg in enumerate(packages, start=start + 1):
        path = day / f"{i:02d}_{pkg.get('slug')}.json"
        _write_json(path, pkg)
        try:
            report["drawn"].append(str(path.relative_to(ROOT)))
        except ValueError:                           # bank redirected (tests)
            report["drawn"].append(str(path))
    report["shortfall"] = need - len(packages)
    return report
