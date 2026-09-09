#!/usr/bin/env python3
"""The channel's local clock, in ONE place.

Everything this pipeline schedules for humans — ChatGPT's tasks, the publish
slots, Phase B's backstop, the watchdogs — is anchored to America/Chicago,
while GitHub crons fire at fixed UTC hours and slip an hour at DST. The rule
the repo learned the hard way (twice, recorded in CLAUDE.md) is: PAIR THE
CRONS AND DECIDE IN CODE. A UTC-anchored deadline is correct for half the
year and quietly wrong for the other half.

Four modules had grown their own copy of the timezone name — and the docs
had grown two stale copies of the derived UTC hours, which the doctor caught
on 2026-08-22. This is the single definition they should share.
"""
from __future__ import annotations

from datetime import datetime, timezone

TZ = "America/Chicago"


def now(utc_now: datetime | None = None) -> datetime:
    """`utc_now` (default: real now) as Central. Falls back to UTC if the
    tzdata is unavailable — a missing timezone database must never crash a
    scheduling decision, it just makes it conservative."""
    n = utc_now or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        return n.astimezone(ZoneInfo(TZ))
    except Exception:  # noqa: BLE001
        return n


def deadline_passed(date: str, hour_central: int,
                    utc_now: datetime | None = None) -> bool:
    """Has `hour_central` on `date` (YYYYMMDD) gone by?

    True for any earlier date, False for any later one, so a run that fires
    early simply reports "not yet" instead of declaring a failure that has
    not happened. An unparseable date returns True: judge it rather than
    silently skip it."""
    n = now(utc_now)
    try:
        day = datetime.strptime(str(date), "%Y%m%d").date()
    except ValueError:
        return True
    if n.date() != day:
        return n.date() > day
    return n.hour >= hour_central
