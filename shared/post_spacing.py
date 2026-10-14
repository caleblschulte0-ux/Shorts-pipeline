"""No channel posts twice inside its minimum gap.

Operator, 2026-10-14: *"We need to be making sure things are posting at
proper times we can't drop 3 videos in 2 hours"*. That morning the
explainer went live at 15:50Z (a mailbox ship, public the moment it
uploaded), 16:20Z (a posting run that had picked "an hour from now" when it
STARTED and uploaded after that hour had passed) and 17:23Z (the slot an
earlier run had already scheduled). Each path chose its time alone: the
mailbox always said "now", a posting run counted from its own clock, and
neither looked at what the posted log already had going live.

This is the one place a go-live time is checked against the others. Every
upload path asks `schedule()` (or `next_free()`) for its time, and a late or
catch-up video is pushed to the next free time instead of landing on top of
the last one. The gap is the registry's (`cadence.min_gap_hours`), never a
number written here. TikTok follows: a future YouTube publish_at is queued
for tiktok_due, so pushing YouTube pushes TikTok with it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

#: YouTube refuses a publishAt that is not in the future, and a run that
#: hands it one only minutes out risks the same — so nothing is scheduled
#: closer than this to now.
LEAD = timedelta(minutes=15)

#: How far back an earlier post still counts. A gap is hours, so two days
#: covers every neighbour with room to spare.
WINDOW = timedelta(hours=48)

PUBLISH_TZ = "America/Chicago"

_WHEN_KEYS = ("publish_at", "at", "posted_at", "uploaded_at", "claimed_at")


def parse(v) -> datetime | None:
    if not v:
        return None
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).replace(microsecond=0) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def min_gap(channel: str, reg=None) -> timedelta:
    """The registry's minimum time between two of this channel's posts."""
    from shared import channel_registry
    h = (channel_registry.channel(channel, reg).get("cadence") or {}) \
        .get("min_gap_hours")
    if not isinstance(h, (int, float)) or h <= 0:
        raise channel_registry.RegistryError(
            f"channels.{channel}.cadence.min_gap_hours is missing — refusing "
            f"to guess how far apart this channel's posts go")
    return timedelta(hours=float(h))


def _records(log) -> list[dict]:
    """Every record in a posted log, whichever shape it keeps (explainer and
    third key `posted` by slug, trending keeps a list), with the claim in
    `uploads` and its `posted` record merged into one — the claim of a
    scheduled trending video has no publish_at, and read alone it would
    count as a post at claim time."""
    if isinstance(log, list):
        raw = [e for e in log if isinstance(e, dict)]
    else:
        raw = []
        posted = (log or {}).get("posted")
        if isinstance(posted, dict):
            raw += [dict(e, slug=e.get("slug") or k)
                    for k, e in posted.items() if isinstance(e, dict)]
        elif isinstance(posted, list):
            raw += [e for e in posted if isinstance(e, dict)]
        raw += [e for e in (log or {}).get("uploads") or []
                if isinstance(e, dict)]
    merged: dict[str, dict] = {}
    for e in raw:
        key = (e.get("title") or e.get("slug") or e.get("topic")
               or e.get("url") or e.get("video_url") or str(id(e)))
        into = merged.setdefault(str(key), {})
        for k, v in e.items():
            if into.get(k) in (None, ""):
                into[k] = v
    return list(merged.values())


def taken(log, *, now: datetime | None = None) -> list[datetime]:
    """When each of this log's videos goes (or went) live: its publish_at,
    else the moment it was uploaded public. Failed claims do not count."""
    now = now or datetime.now(timezone.utc)
    out = []
    for e in _records(log):
        if e.get("state") in ("failed", "released", "pulled"):
            continue
        when = next((d for d in (parse(e.get(k)) for k in _WHEN_KEYS) if d),
                    None)
        if when and when >= now - WINDOW:
            out.append(when)
    return sorted(out)


def clashes(t: datetime, busy, gap: timedelta) -> datetime | None:
    """The first busy time closer than `gap` to `t`, or None."""
    return next((x for x in sorted(busy) if abs(t - x) < gap), None)


def next_free(want: datetime, busy, gap: timedelta, *,
              now: datetime | None = None) -> datetime:
    """The earliest time at or after `want` (and at least LEAD from now)
    that is `gap` clear of every busy time. Only ever moves later."""
    now = now or datetime.now(timezone.utc)
    t = max(want, now + LEAD)
    while (x := clashes(t, busy, gap)) is not None:
        t = x + gap
    return t


def slot_times(now: datetime, slots, days: int = 4) -> list[datetime]:
    """A channel's fixed (hour, minute) Central slots from today on, as UTC."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(PUBLISH_TZ)
        base = now.astimezone(tz)
    except Exception:  # noqa: BLE001 - no tzdata: a fixed CDT offset
        tz, base = None, now - timedelta(hours=5)
    out = []
    for d in range(days):
        day = (base + timedelta(days=d)).replace(hour=0, minute=0, second=0,
                                                microsecond=0)
        for h, m in slots:
            t = day.replace(hour=int(h), minute=int(m))
            out.append(t.astimezone(timezone.utc) if tz
                       else (t + timedelta(hours=5)).replace(tzinfo=timezone.utc))
    return sorted(out)


def next_free_slot(slots, busy, gap: timedelta, *, after: datetime | None = None,
                   now: datetime | None = None) -> datetime:
    """The first fixed slot past `after` and LEAD from now that is `gap`
    clear of every busy time — a catch-up post waits for the next free slot
    instead of going out on top of the last one."""
    now = now or datetime.now(timezone.utc)
    cands = [t for t in slot_times(now, slots)
             if t >= now + LEAD and (after is None or t > after)]
    for t in cands:
        if clashes(t, busy, gap) is None:
            return t
    return next_free(cands[-1] if cands else now, busy, gap, now=now)


def schedule(channel: str, log, *, want: datetime | None = None,
             now: datetime | None = None, reg=None) -> str | None:
    """The publish_at for this channel's next upload, or None when posting
    it public right now keeps the gap. `want` is the time the caller had in
    mind (a run's own spacing); without one it means "now"."""
    from shared import channel_registry
    now = now or datetime.now(timezone.utc)
    gap = min_gap(channel, reg)
    busy = taken(log, now=now)
    slots = (channel_registry.channel(channel, reg).get("cadence") or {}) \
        .get("publish_slots_central")
    if slots:
        t = next_free_slot(slots, busy, gap, now=now)
        if want and want > t:
            t = next_free_slot(slots, busy, gap, after=want - timedelta(seconds=1),
                               now=now)
        return iso(t)
    want = want or now
    if want <= now + LEAD and clashes(now, busy, gap) is None:
        return None                       # public now keeps the gap
    t = next_free(want, busy, gap, now=now)
    if t > max(want, now + LEAD):
        print(f"[spacing] {channel}: {iso(want)} is within "
              f"{gap.total_seconds() / 3600:g}h of a post at "
              f"{iso(clashes(max(want, now + LEAD), busy, gap))} — going live "
              f"{iso(t)} instead", flush=True)
    return iso(t)
