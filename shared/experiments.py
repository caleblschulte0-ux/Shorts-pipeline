"""The experiment register — multi-day tests, so a small channel can learn.

The retro loop's hardest constraint is sample size. This channel posts six
videos a day into single-digit view counts, so ANY one-day comparison is
noise, and a reviewer that concludes from one day will confidently walk the
channel in a random direction. The answer is not "be careful" — it is to
make early conclusions structurally impossible.

An experiment here is a coded, dated commitment:

    hypothesis   what we think is true
    change       what shipped to test it (files + description)
    metric       the number that must move, and which way
    baseline     that number at the moment the change went live
    min_days     no readout before this many days have passed
    min_samples  no readout before this many videos have run under it
    guardrail    a number that must NOT regress (quality, usually)

`readout_ready()` refuses until BOTH thresholds are met. `conclude()` then
compares against the recorded baseline and returns adopted / reverted /
inconclusive — and it will return `reverted` when the guardrail regressed
even if the target metric improved, because "more views, worse videos" is
a loss.

This is what turns a daily suggestion box into something that compounds:
every day, the running experiments are in the brief, the ones whose window
has closed DEMAND a readout, and their verdicts accumulate in the ledger
instead of evaporating.

    from shared import experiments as ex
    e = ex.register("Shorter graph hooks hold better", ...)
    ex.readout_ready(e, samples=12)      # (False, "3/7 days elapsed")
    ex.conclude(e, observed=0.31, guardrail_observed=0.02)
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETRO_STATE = ROOT / "retro" / "state"
REGISTER = RETRO_STATE / "experiments.json"

# Defaults tuned to this channel's volume: 6 posts/day means 10 samples is
# under two days of output, so the DAYS floor is what actually binds. Both
# exist because a slow week should not let a thin experiment conclude.
DEFAULT_MIN_DAYS = 7
DEFAULT_MIN_SAMPLES = 10

STATUSES = ("running", "readout_due", "adopted", "reverted", "inconclusive",
            "abandoned")
DIRECTIONS = ("up", "down")
# A change under this relative move is called inconclusive rather than a
# win. On single-digit view counts, a 4% swing is weather.
MIN_EFFECT = 0.15
# How far the guardrail may slip before a "win" is treated as a loss.
GUARDRAIL_TOLERANCE = 0.10

_SLUG = re.compile(r"[^a-z0-9-]+")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:                                # noqa: BLE001
        return None


def _read() -> dict:
    try:
        return json.loads(REGISTER.read_text())
    except Exception:                                # noqa: BLE001
        return {"experiments": []}


def _write(data: dict) -> None:
    RETRO_STATE.mkdir(parents=True, exist_ok=True)
    tmp = REGISTER.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(REGISTER)


def slug(text: str) -> str:
    return (_SLUG.sub("-", (text or "").lower()).strip("-") or "exp")[:50]


def all_experiments() -> list[dict]:
    return [e for e in _read().get("experiments") or [] if isinstance(e, dict)]


def running() -> list[dict]:
    return [e for e in all_experiments()
            if e.get("status") in ("running", "readout_due")]


def register(hypothesis: str, *, change: str, metric: str, direction: str,
             baseline: float, files: list[str] | None = None,
             guardrail: str = "", guardrail_baseline: float | None = None,
             min_days: int = DEFAULT_MIN_DAYS,
             min_samples: int = DEFAULT_MIN_SAMPLES,
             proposal_file: str = "", channel: str = "",
             format: str = "", now: str = "") -> dict:
    """Start the clock on a change that just shipped."""
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}")
    data = _read()
    exp = {
        "id": f"{(now or _now())[:10].replace('-', '')}-{slug(hypothesis)}",
        "hypothesis": hypothesis,
        "change": change,
        # Scope. Without these the sample counter would credit any video on
        # any channel, and the experiment would "finish" without ever having
        # been tested.
        "channel": channel,
        "format": format,
        "files": files or [],
        "metric": metric,
        "direction": direction,
        "baseline": float(baseline),
        "guardrail": guardrail,
        "guardrail_baseline": (None if guardrail_baseline is None
                               else float(guardrail_baseline)),
        "min_days": int(min_days),
        "min_samples": int(min_samples),
        "started_at": now or _now(),
        "status": "running",
        "samples_seen": 0,
        "proposal_file": proposal_file,
        "readout": None,
    }
    data.setdefault("experiments", []).append(exp)
    _write(data)
    return exp


def days_elapsed(exp: dict, now: datetime | None = None) -> float:
    started = _parse(exp.get("started_at") or "")
    if not started:
        return 0.0
    now = now or datetime.now(timezone.utc)
    return round((now - started).total_seconds() / 86400.0, 2)


def readout_ready(exp: dict, *, samples: int | None = None,
                  now: datetime | None = None) -> tuple[bool, str]:
    """(ready, why-not). BOTH the day floor and the sample floor must pass —
    this is the whole point of the register."""
    if exp.get("status") not in ("running", "readout_due"):
        return False, f"status is {exp.get('status')}"
    d = days_elapsed(exp, now)
    n = exp.get("samples_seen", 0) if samples is None else samples
    if d < exp.get("min_days", DEFAULT_MIN_DAYS):
        return False, (f"{d:.1f}/{exp.get('min_days')} days elapsed — "
                       f"too early to read")
    if n < exp.get("min_samples", DEFAULT_MIN_SAMPLES):
        return False, (f"{n}/{exp.get('min_samples')} samples — not enough "
                       f"videos have run under this change")
    return True, "ready"


def _improved(direction: str, baseline: float, observed: float) -> float:
    """Relative movement in the INTENDED direction. Negative = went wrong."""
    if baseline == 0:
        return 0.0 if observed == 0 else (1.0 if direction == "up" else -1.0)
    rel = (observed - baseline) / abs(baseline)
    return rel if direction == "up" else -rel


def conclude(exp: dict, *, observed: float,
             guardrail_observed: float | None = None,
             note: str = "", now: str = "") -> dict:
    """Read the experiment out. Mutates and persists the register entry.

    A guardrail regression outranks a win on the target metric: shipping
    more views at the cost of quality is a loss, and the channel's whole
    premise is the other way round."""
    effect = _improved(exp.get("direction", "up"),
                       float(exp.get("baseline") or 0), float(observed))
    guard_slip = 0.0
    if (exp.get("guardrail") and guardrail_observed is not None
            and exp.get("guardrail_baseline") is not None):
        base = float(exp["guardrail_baseline"])
        guard_slip = ((base - float(guardrail_observed)) / abs(base)
                      if base else 0.0)

    if guard_slip > GUARDRAIL_TOLERANCE:
        status, why = "reverted", (
            f"guardrail {exp['guardrail']} regressed {guard_slip:.0%} — a "
            f"win on {exp['metric']} does not pay for that")
    elif effect >= MIN_EFFECT:
        status, why = "adopted", f"{exp['metric']} moved {effect:+.0%}"
    elif effect <= -MIN_EFFECT:
        status, why = "reverted", f"{exp['metric']} moved {effect:+.0%}"
    else:
        status, why = "inconclusive", (
            f"{exp['metric']} moved {effect:+.0%}, under the {MIN_EFFECT:.0%} "
            f"floor — this is weather, not a result")

    exp["status"] = status
    exp["readout"] = {"at": now or _now(), "observed": float(observed),
                      "effect": round(effect, 4),
                      "guardrail_observed": guardrail_observed,
                      "guardrail_slip": round(guard_slip, 4),
                      "verdict": why, "note": note}
    data = _read()
    for i, e in enumerate(data.get("experiments") or []):
        if e.get("id") == exp.get("id"):
            data["experiments"][i] = exp
            break
    _write(data)
    return exp


def bump_samples(exp_id: str, n: int) -> None:
    data = _read()
    for e in data.get("experiments") or []:
        if e.get("id") == exp_id:
            e["samples_seen"] = int(e.get("samples_seen", 0)) + int(n)
    _write(data)


def refresh_due(samples_by_id: dict | None = None) -> list[dict]:
    """Flip anything whose window has closed to `readout_due`. Returns the
    ones now demanding a readout — the brief makes these non-optional."""
    samples_by_id = samples_by_id or {}
    data = _read()
    due = []
    for e in data.get("experiments") or []:
        if e.get("status") != "running":
            continue
        ok, _ = readout_ready(e, samples=samples_by_id.get(e.get("id")))
        if ok:
            e["status"] = "readout_due"
            due.append(e)
    if due:
        _write(data)
    return due


def summary() -> dict:
    exps = all_experiments()
    by = {}
    for e in exps:
        by[e.get("status")] = by.get(e.get("status"), 0) + 1
    return {"total": len(exps), "by_status": by,
            "running": [{"id": e["id"], "hypothesis": e["hypothesis"],
                         "days": days_elapsed(e),
                         "samples": e.get("samples_seen", 0),
                         "needs": f"{e.get('min_days')}d / "
                                  f"{e.get('min_samples')} samples",
                         "status": e["status"],
                         "blocked_by": readout_ready(e)[1]}
                        for e in running()],
            "concluded": [{"id": e["id"], "hypothesis": e["hypothesis"],
                           "status": e["status"],
                           "verdict": (e.get("readout") or {}).get("verdict")}
                          for e in exps
                          if e.get("status") in ("adopted", "reverted",
                                                 "inconclusive")][-10:]}

# --------------------------------------------------------------------------
# Sample advancement — the thing that makes an experiment finish
# --------------------------------------------------------------------------
def eligible_videos(exp: dict, videos: list[dict]) -> list[dict]:
    """Videos that actually ran UNDER this experiment.

    Three filters, all necessary. Counting everything would let an
    experiment on the trending channel be concluded by explainer uploads,
    or by videos published before the change even shipped — which is not a
    test of anything.

      published_at > started_at   the change was live when it rendered
      channel matches             a different channel is a different world
      format matches (if scoped)  a reddit_story does not test a graph tweak
    """
    started = _parse(exp.get("started_at") or "")
    if not started:
        return []
    want_channel = (exp.get("channel") or "").strip()
    want_format = (exp.get("format") or "").strip()
    out = []
    for v in videos or []:
        pub = _parse(v.get("published_at") or "")
        if not pub or pub <= started:
            continue
        if want_channel and str(v.get("_channel") or "") != want_channel:
            continue
        if want_format and str(v.get("format") or v.get("_fmt") or "") != want_format:
            continue
        out.append(v)
    return out


def advance(videos_by_channel: dict) -> list[dict]:
    """Recount every running experiment from the analytics, then flip the
    ones whose window has closed.

    Recount rather than increment: a counter that only ever goes up drifts
    the moment a run is retried or a video is deleted, and nobody notices
    because the number still looks plausible. This is idempotent — running
    it five times a day gives the same answer as running it once."""
    data = _read()
    changed, due = False, []
    for e in data.get("experiments") or []:
        if e.get("status") not in ("running", "readout_due"):
            continue
        pool = []
        for chan, vids in (videos_by_channel or {}).items():
            for v in vids or []:
                v = dict(v)
                v["_channel"] = chan
                pool.append(v)
        n = len(eligible_videos(e, pool))
        if n != e.get("samples_seen"):
            e["samples_seen"] = n
            changed = True
        ok, _ = readout_ready(e, samples=n)
        if ok and e.get("status") == "running":
            e["status"] = "readout_due"
            changed = True
        if e.get("status") == "readout_due":
            due.append(e)
    if changed:
        _write(data)
    return due


# An experiment nobody reads out is worse than no experiment: it blocks the
# one-active-per-channel cap forever and quietly stops the loop.
STALE_AFTER_DAYS = 30


def stale(now: "datetime | None" = None) -> list[dict]:
    """Experiments that have been due for a readout far too long."""
    return [e for e in running()
            if days_elapsed(e, now) > STALE_AFTER_DAYS]


def abandon(exp_id: str, reason: str) -> dict | None:
    """Close out an experiment that will never produce a clean verdict."""
    data = _read()
    for e in data.get("experiments") or []:
        if e.get("id") == exp_id:
            e["status"] = "abandoned"
            e["readout"] = {"at": _now(), "verdict": reason}
            _write(data)
            return e
    return None
