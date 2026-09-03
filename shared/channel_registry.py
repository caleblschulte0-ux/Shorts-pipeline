"""The channel registry — one authority for mutable operational policy.

For most of this pipeline's life, "the trending slate is 2 reddit + 2 text
card + 2 graph race" was written down in eight places: a constant in
the package validator, another in `authoring_brief`, a heading in
`CLAUDE_ROUTINE_INSTRUCTIONS.md`, three tables in `exchange/README.md`, a
paragraph of prose inside `daily.yml`'s brain prompt, and the assertions in
four test files. On 2026-07-31 the operator changed the ruling to 4 graph
races + 2 reddit stories with text cards retired — and it landed in exactly
ONE of those eight. The others kept saying 2+2+2, so the takeover kept
asking for a retired format and the validators kept accepting it.

That is the failure this module exists to make impossible. `config/
channel_registry.json` is the only place a channel's operational rules are
written, and every consumer resolves through here:

    from shared import channel_registry as reg
    reg.target_mix("trending")             -> {"graph_race": 4, "reddit_story": 2}
    reg.shortfall("trending", have)        -> what today still needs
    reg.classify(pkg, "trending")          -> which format a package IS
    reg.plan(date)                         -> the whole resolved day

Two rules keep it honest:

  * **FAIL CLOSED.** A missing or invalid registry raises `RegistryError`. It
    does NOT fall back to a historical mix — a fallback is precisely how a
    retired format gets resurrected on a day nobody is watching.
  * **The registry holds policy, not doctrine.** Voice, topic banks and
    rubrics stay in their own files; the registry names their paths and Phase
    A hashes them into the day's bundle, so editing doctrine cannot silently
    change an already-open day.

Deep editorial doctrine deliberately does NOT live here. Neither does
anything a renderer owns outright (publish slot times are recorded for
reference but `run_trending_daily.py` still owns them).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "config" / "channel_registry.json"
SCHEMA_VERSION = "channel-registry/v1"

#: Override for tests and for the acceptance fixture. Never set in production.
PATH_ENV = "CHANNEL_REGISTRY_PATH"

FORMAT_STATES = ("active", "retired", "disabled")
KNOWN_ROLES = ("media_worker", "editorial_review", "takeover_authoring",
               "queue_stocking", "production_supervisor", "none")


class RegistryError(RuntimeError):
    """The registry is missing, unreadable, or internally inconsistent.

    Deliberately fatal. Every caller would otherwise be tempted to guess, and
    a guess here means authoring a retired format or shipping the wrong count
    on a day nobody is watching."""


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------
_CACHE: dict[str, tuple[float, dict]] = {}


def registry_path() -> Path:
    return Path(os.environ.get(PATH_ENV) or REGISTRY_PATH)


def load(path=None, *, use_cache: bool = True) -> dict:
    """The registry, validated. Raises RegistryError rather than guessing."""
    p = Path(path) if path else registry_path()
    try:
        stat = p.stat()
    except OSError as exc:
        raise RegistryError(
            f"channel registry not found at {p} ({exc}). This file is the "
            f"only authority for channel policy; there is deliberately no "
            f"fallback mix, because falling back is how a retired format "
            f"gets authored again.") from exc

    key = str(p.resolve())
    if use_cache:
        cached = _CACHE.get(key)
        if cached and cached[0] == stat.st_mtime_ns:
            return cached[1]

    try:
        data = json.loads(p.read_text())
    except Exception as exc:                             # noqa: BLE001
        raise RegistryError(f"channel registry at {p} is not valid JSON: "
                            f"{exc}") from exc
    problems = validate(data)
    if problems:
        raise RegistryError(f"channel registry at {p} is invalid:\n  - "
                            + "\n  - ".join(problems))
    _CACHE[key] = (stat.st_mtime_ns, data)
    return data


def raw_bytes(path=None) -> bytes:
    return (Path(path) if path else registry_path()).read_bytes()


def sha256(path=None) -> str:
    """Hash of the registry file's exact bytes — snapshotted into each bundle
    so a later edit is detectable, not silent."""
    return hashlib.sha256(raw_bytes(path)).hexdigest()


def revision(reg=None) -> int:
    return int((reg or load()).get("revision") or 0)


def validate(reg) -> list[str]:
    """Everything structurally wrong with a registry. Empty means usable."""
    problems: list[str] = []
    if not isinstance(reg, dict):
        return ["registry is not an object"]
    if reg.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version {reg.get('schema_version')!r} "
                        f"(this code speaks {SCHEMA_VERSION!r})")
    try:
        if int(reg.get("revision")) < 1:
            problems.append("revision must be >= 1")
    except Exception:                                    # noqa: BLE001
        problems.append("revision missing or not an integer")

    pd = reg.get("production_date")
    if not isinstance(pd, dict) or not pd.get("timezone"):
        problems.append("production_date.timezone missing")

    channels = reg.get("channels")
    if not isinstance(channels, dict) or not channels:
        return problems + ["no channels defined"]

    for cid, ch in channels.items():
        if not isinstance(ch, dict):
            problems.append(f"{cid}: not an object")
            continue
        if ch.get("id") != cid:
            problems.append(f"{cid}: id field is {ch.get('id')!r}")
        if not isinstance(ch.get("enabled"), bool):
            problems.append(f"{cid}: enabled must be true/false")
        for role in ch.get("chatgpt_roles") or []:
            if role not in KNOWN_ROLES:
                problems.append(f"{cid}: unknown chatgpt role {role!r}")

        formats = ch.get("formats")
        if not isinstance(formats, dict) or not formats:
            problems.append(f"{cid}: no formats defined")
            continue
        active_total = 0
        for fid, fmt in formats.items():
            if not isinstance(fmt, dict):
                problems.append(f"{cid}.{fid}: not an object")
                continue
            state = fmt.get("state")
            if state not in FORMAT_STATES:
                problems.append(f"{cid}.{fid}: state {state!r} not one of "
                                f"{FORMAT_STATES}")
            try:
                target = int(fmt.get("target", 0))
            except Exception:                            # noqa: BLE001
                problems.append(f"{cid}.{fid}: target is not an integer")
                continue
            if target < 0:
                problems.append(f"{cid}.{fid}: negative target")
            if state == "active":
                active_total += target
                if not isinstance(fmt.get("detect"), dict):
                    problems.append(f"{cid}.{fid}: active format needs a "
                                    f"`detect` rule")
            elif target:
                problems.append(f"{cid}.{fid}: {state} but target is "
                                f"{target} — a non-active format must "
                                f"target 0")
            for role in fmt.get("chatgpt_roles") or []:
                if role not in KNOWN_ROLES:
                    problems.append(f"{cid}.{fid}: unknown role {role!r}")

        # The one arithmetic invariant. Two numbers that must agree is how a
        # channel ends up asking for five packages and shipping six.
        if ch.get("enabled"):
            try:
                declared = int(ch.get("target_count"))
            except Exception:                            # noqa: BLE001
                problems.append(f"{cid}: target_count missing or not an "
                                f"integer")
                continue
            if declared != active_total:
                problems.append(
                    f"{cid}: target_count is {declared} but the active "
                    f"formats sum to {active_total} — these must agree, or "
                    f"the shortfall calculation and the slate size disagree")

        q = ch.get("queue")
        if q is not None:
            if not isinstance(q, dict):
                problems.append(f"{cid}: queue must be an object or null")
            else:
                try:
                    lo = int(q.get("minimum_unposted"))
                    hi = q.get("maximum_unposted")
                    if hi is not None and int(hi) < lo:
                        problems.append(f"{cid}: queue maximum < minimum")
                except Exception:                        # noqa: BLE001
                    problems.append(f"{cid}: queue.minimum_unposted missing "
                                    f"or not an integer")
    return problems


# --------------------------------------------------------------------------
# channels and formats
# --------------------------------------------------------------------------
def channel(cid: str, reg=None) -> dict:
    reg = reg or load()
    ch = (reg.get("channels") or {}).get(str(cid))
    if not isinstance(ch, dict):
        raise RegistryError(f"no such channel {cid!r} in the registry "
                            f"(have: {', '.join(sorted(reg.get('channels') or {}))})")
    return ch


def channel_ids(reg=None, *, enabled_only: bool = True) -> list[str]:
    reg = reg or load()
    out = []
    for cid, ch in (reg.get("channels") or {}).items():
        if enabled_only and not ch.get("enabled"):
            continue
        out.append(cid)
    return sorted(out)


def is_enabled(cid: str, reg=None) -> bool:
    try:
        return bool(channel(cid, reg).get("enabled"))
    except RegistryError:
        return False


def formats(cid: str, reg=None, *, state: str | None = "active") -> dict:
    """{format_id: spec} for one channel, filtered by state (None = all)."""
    fmts = channel(cid, reg).get("formats") or {}
    if state is None:
        return dict(fmts)
    return {fid: f for fid, f in fmts.items() if f.get("state") == state}


def active_formats(cid: str, reg=None) -> list[str]:
    return sorted(formats(cid, reg, state="active"))


def retired_formats(cid: str, reg=None) -> list[str]:
    out = [fid for fid, f in (channel(cid, reg).get("formats") or {}).items()
           if f.get("state") in ("retired", "disabled")]
    return sorted(out)


def format_spec(cid: str, fid: str, reg=None) -> dict:
    spec = (channel(cid, reg).get("formats") or {}).get(str(fid))
    if not isinstance(spec, dict):
        raise RegistryError(f"{cid}: no such format {fid!r}")
    return spec


def target_mix(cid: str, reg=None) -> dict:
    """{format: how many today}. Active formats only — a retired format is
    absent entirely, not present with a zero, so a caller iterating the mix
    cannot accidentally ask for one."""
    return {fid: int(f.get("target", 0))
            for fid, f in sorted(formats(cid, reg, state="active").items())}


def target_count(cid: str, reg=None) -> int:
    return int(channel(cid, reg).get("target_count") or 0)


def roles(cid: str, fid: str | None = None, reg=None) -> list[str]:
    """What ChatGPT is responsible for, channel-wide or for one format."""
    if fid is None:
        got = channel(cid, reg).get("chatgpt_roles") or []
    else:
        got = format_spec(cid, fid, reg).get("chatgpt_roles") or []
    return [r for r in got if r != "none"]


def has_role(cid: str, role: str, fid: str | None = None, reg=None) -> bool:
    return role in roles(cid, fid, reg)


def media_requirements(cid: str, fid: str, reg=None) -> dict:
    """What media this format needs — the registry decides, not the renderer
    and definitely not a paragraph in a README."""
    spec = format_spec(cid, fid, reg)
    media = dict(spec.get("media") or {})
    media.setdefault("shots", False)
    media.setdefault("chatgpt_supplies_images", False)
    return media


def queue_rule(cid: str, reg=None) -> dict | None:
    q = channel(cid, reg).get("queue")
    return dict(q) if isinstance(q, dict) else None


def doctrine_paths(cid: str, reg=None) -> list[str]:
    return list(channel(cid, reg).get("doctrine") or [])


def protected_fields(cid: str, reg=None) -> list[str]:
    return list(channel(cid, reg).get("protected_fields") or [])


def allowed_mutations(cid: str, reg=None) -> list[str]:
    return list(channel(cid, reg).get("allowed_editorial_mutations") or [])


def paths(cid: str, reg=None) -> dict:
    return dict(channel(cid, reg).get("paths") or {})


def failure_policy(cid: str, reg=None) -> dict:
    reg = reg or load()
    out = dict((reg.get("defaults") or {}).get("failure_policy") or {})
    out.update(channel(cid, reg).get("failure_policy") or {})
    return out


# --------------------------------------------------------------------------
# classifying a package
# --------------------------------------------------------------------------
def classify(pkg, cid: str = "trending", reg=None) -> str | None:
    """Which format IS this package? Decided by the registry's `detect` rules.

    Checked against every format including retired ones — a text_card sitting
    on disk from before the retirement must still be recognised as a
    text_card, or the shortfall maths counts it as an unknown and over-orders.
    Explicit rules beat implicit ones: a format keyed on a field's VALUE wins
    over one keyed on a field's absence, so `reddit_story` ("no `format`,
    has `subreddit`") never swallows a package that names its format."""
    if not isinstance(pkg, dict):
        return None
    fmts = formats(cid, reg, state=None)

    explicit, implicit = [], []
    for fid, spec in fmts.items():
        rule = spec.get("detect") or {}
        (explicit if "equals" in rule else implicit).append((fid, rule))

    for fid, rule in sorted(explicit):
        field = rule.get("field")
        if field and str(pkg.get(field) or "") == str(rule.get("equals")):
            return fid
    for fid, rule in sorted(implicit):
        absent, requires = rule.get("absent"), rule.get("requires")
        field, present = rule.get("field"), rule.get("present")
        if absent is not None:
            if pkg.get(absent):
                continue
            if requires and not pkg.get(requires):
                continue
            return fid
        if field is not None and present:
            if pkg.get(field):
                return fid
    return None


def is_authorable(cid: str, fid: str | None, reg=None) -> bool:
    """May anything author this format today? Retired and disabled are no."""
    if not fid:
        return False
    try:
        return format_spec(cid, fid, reg).get("state") == "active"
    except RegistryError:
        return False


def shortfall(cid: str, have_packages, reg=None) -> dict:
    """{format: how many still to write}, from what genuinely exists.

    Counts every package against the registry's detect rules, ignores
    anything it cannot classify, and never asks for a retired format even if
    the day is short of one. A surplus in one format does NOT reduce the ask
    in another — six graph races do not satisfy a reddit_story slot."""
    mix = target_mix(cid, reg)
    have = {fid: 0 for fid in mix}
    for pkg in have_packages or []:
        fid = classify(pkg, cid, reg)
        if fid in have:
            have[fid] += 1
    return {fid: max(0, n - have[fid]) for fid, n in mix.items()}


def slate_problems(cid: str, packages, reg=None) -> list[str]:
    """Slate-level complaints — retired formats and monoculture, mostly."""
    out: list[str] = []
    counts: dict[str, int] = {}
    for pkg in packages or []:
        fid = classify(pkg, cid, reg)
        counts[fid or "unknown"] = counts.get(fid or "unknown", 0) + 1

    for fid in retired_formats(cid, reg):
        if counts.get(fid):
            spec = format_spec(cid, fid, reg)
            out.append(
                f"{counts[fid]} package(s) use the RETIRED format {fid!r} "
                f"(retired {spec.get('retired_on', '?')}: "
                f"{spec.get('retired_because', 'no reason recorded')})")

    mix = target_mix(cid, reg)
    if len(mix) > 1 and sum(counts.get(f, 0) for f in mix) >= target_count(cid, reg):
        used = [f for f in mix if counts.get(f)]
        if len(used) == 1:
            out.append(f"the whole slate is one format ({used[0]}) — the "
                       f"registry asks for "
                       f"{', '.join(f'{n}x{f}' for f, n in mix.items() if n)}")
    slugs = [(p.get("slug") or "") for p in packages or [] if isinstance(p, dict)]
    dupes = {s for s in slugs if s and slugs.count(s) > 1}
    if dupes:
        out.append(f"duplicate slugs in one slate: {', '.join(sorted(dupes))}")
    return out


# --------------------------------------------------------------------------
# the resolved day
# --------------------------------------------------------------------------
def production_date(now=None, reg=None) -> str:
    """The date a bundle and its packages are keyed by.

    UTC calendar day, because every workflow resolves it with
    `date -u +%Y%m%d` and the folders on disk are named that way. The
    registry's `timezone` is the OPERATIONAL clock (publish slots, the
    06:00/07:00 workers, the Phase B backstop) and is a different thing —
    conflating them is how a folder name drifts a day at midnight."""
    from datetime import datetime, timezone as _tz
    reg = reg or load()
    policy = ((reg.get("production_date") or {}).get("policy")
              or "utc_calendar_day")
    now = now or datetime.now(_tz.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_tz.utc)
    if policy == "local_calendar_day":
        try:
            from zoneinfo import ZoneInfo
            now = now.astimezone(
                ZoneInfo((reg.get("production_date") or {})["timezone"]))
        except Exception:                                # noqa: BLE001
            pass
    elif policy != "utc_calendar_day":
        raise RegistryError(f"unknown production_date.policy {policy!r}")
    return now.strftime("%Y%m%d")


def doctrine_manifest(cid: str, reg=None) -> list[dict]:
    """Doctrine files with the hash of their CURRENT contents.

    The registry stores paths only — hashes here would go stale on every
    typo and turn a doc fix into a registry bump. The hash belongs to the
    SNAPSHOT: Phase A records it in the day's bundle alongside
    `source_commit`, so an edit after the bundle opens is detectable and the
    workers can still read the exact text the day was planned against."""
    out = []
    for rel in doctrine_paths(cid, reg):
        p = ROOT / rel
        entry = {"path": rel}
        try:
            entry["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
            entry["bytes"] = p.stat().st_size
        except OSError as exc:
            entry["error"] = f"unreadable: {exc}"
        out.append(entry)
    return out


def source_commit() -> str | None:
    """The commit the workers must read doctrine from. Best-effort: a shallow
    CI checkout still has HEAD, and a missing value is honest rather than
    fabricated."""
    import subprocess
    for cmd in (["git", "rev-parse", "HEAD"],):
        try:
            out = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                                 text=True, timeout=10)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except Exception:                                # noqa: BLE001
            continue
    return os.environ.get("GITHUB_SHA") or None


def channel_plan(cid: str, have_packages=None, reg=None) -> dict:
    """One channel's resolved requirements for a day."""
    reg = reg or load()
    ch = channel(cid, reg)
    mix = target_mix(cid, reg)
    short = shortfall(cid, have_packages or [], reg)
    plan = {
        "channel": cid,
        "display_name": ch.get("display_name"),
        "enabled": bool(ch.get("enabled")),
        "target_count": target_count(cid, reg),
        "target_mix": mix,
        "have": {fid: mix[fid] - short[fid] for fid in mix},
        "shortfall": short,
        "to_author": sum(short.values()),
        "active_formats": active_formats(cid, reg),
        "retired_formats": retired_formats(cid, reg),
        "chatgpt_roles": roles(cid, reg=reg),
        "chatgpt_job": ch.get("chatgpt_job"),
        "response_key": ch.get("response_key"),
        "media_requirements": {fid: media_requirements(cid, fid, reg)
                               for fid in mix},
        "queue": queue_rule(cid, reg),
        "paths": paths(cid, reg),
        "package_schema": ch.get("package_schema"),
        "response_schema": ch.get("response_schema"),
        "protected_fields": protected_fields(cid, reg),
        "protected_fields_enforced_by": ch.get("protected_fields_enforced_by"),
        "allowed_editorial_mutations": allowed_mutations(cid, reg),
        "doctrine": doctrine_manifest(cid, reg),
        "failure_policy": failure_policy(cid, reg),
    }
    return plan


def plan(date=None, packages_by_channel=None, reg=None, *,
         source_commit_sha=None) -> dict:
    """THE SNAPSHOT. Everything a day is contracted to, resolved once.

    Phase A embeds this in `bundle.json`, which freezes it: the 07:00
    finalizer works the same plan the 06:00 media worker did even if the
    registry changed between them, and a later registry edit starts applying
    from the NEXT bundle."""
    reg = reg or load()
    packages_by_channel = packages_by_channel or {}
    date = date or production_date(reg=reg)
    channels = {}
    for cid in channel_ids(reg):
        channels[cid] = channel_plan(cid, packages_by_channel.get(cid), reg)
    return {
        "schema_version": reg.get("schema_version"),
        "registry_revision": revision(reg),
        "registry_sha256": sha256(),
        "registry_path": str(registry_path().relative_to(ROOT))
                         if str(registry_path()).startswith(str(ROOT))
                         else str(registry_path()),
        "source_commit": source_commit_sha or source_commit(),
        "production_date": str(date),
        "production_date_policy": reg.get("production_date"),
        "response_schema": (reg.get("defaults") or {}).get("response_schema"),
        "checkpoint_schema": (reg.get("defaults") or {}).get("checkpoint_schema"),
        "drive": (reg.get("defaults") or {}).get("drive"),
        "role_glossary": reg.get("chatgpt_roles"),
        "channels": channels,
        "totals": {
            "channels_active": len(channels),
            "packages_expected": sum(c["target_count"] for c in channels.values()),
            "packages_to_author": sum(c["to_author"] for c in channels.values()),
        },
        "immutability": (
            "This block is the CONTRACT for this production date. It is "
            "frozen at bundle creation: if config/channel_registry.json "
            "changes afterwards, the 07:00 finalizer still works these "
            "numbers, and the new rules begin with the next date's bundle. "
            "Read doctrine at `source_commit`, not at HEAD."),
    }


# --------------------------------------------------------------------------
# rendering the rules as prose (so no prompt has to restate them)
# --------------------------------------------------------------------------
def mix_sentence(cid: str = "trending", reg=None) -> str:
    """The slate, as one line — generated, never typed.

    Used by `daily.yml`'s brain prompt, the Routine instructions, and the
    exchange README table. Prose that restates the mix by hand is the
    original bug."""
    mix = target_mix(cid, reg)
    total = target_count(cid, reg)
    parts = [f"{n} {fid}" for fid, n in mix.items() if n]
    retired = retired_formats(cid, reg)
    line = f"EXACTLY {total}: " + " + ".join(parts) if parts else "nothing"
    if retired:
        line += (f". RETIRED — do not author: {', '.join(retired)}")
    return line


def markdown_table(reg=None) -> str:
    """The whole registry as a table, for docs that would otherwise drift."""
    reg = reg or load()
    rows = ["| Channel | Per day | Active formats | Retired | ChatGPT does |",
            "|---|---|---|---|---|"]
    for cid in channel_ids(reg):
        mix = target_mix(cid, reg)
        fmts = ", ".join(f"{n}x `{f}`" for f, n in mix.items()) or "—"
        ret = ", ".join(f"`{f}`" for f in retired_formats(cid, reg)) or "—"
        r = ", ".join(roles(cid, reg=reg)) or "nothing"
        rows.append(f"| `{cid}` | {target_count(cid, reg)} | {fmts} | {ret} "
                    f"| {r} |")
    rows.append("")
    rows.append(f"<!-- generated from config/channel_registry.json "
                f"rev {revision(reg)} — do not edit by hand; run "
                f"`python -m shared.channel_registry --markdown` -->")
    return "\n".join(rows)


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Inspect the channel registry.")
    ap.add_argument("--markdown", action="store_true",
                    help="print the channel table for docs")
    ap.add_argument("--mix", metavar="CHANNEL", nargs="?", const="trending")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--date")
    args = ap.parse_args(argv)
    try:
        reg = load()
    except RegistryError as exc:
        print(f"REGISTRY INVALID: {exc}")
        return 1
    if args.validate:
        print(f"registry rev {revision(reg)} OK — "
              f"sha256 {sha256()[:16]}…")
        for cid in channel_ids(reg):
            print(f"  {cid}: {mix_sentence(cid, reg)}")
        return 0
    if args.markdown:
        print(markdown_table(reg))
    elif args.plan:
        print(json.dumps(plan(args.date, reg=reg), indent=2))
    elif args.mix:
        print(mix_sentence(args.mix, reg))
    else:
        for cid in channel_ids(reg):
            print(f"{cid}: {mix_sentence(cid, reg)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
