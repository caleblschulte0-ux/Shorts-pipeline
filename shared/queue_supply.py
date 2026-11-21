"""How many explainer stories can actually POST — the queue's real supply.

A queue is not "full" because it holds un-posted stories. It is full when it
holds stories the posting run will PUBLISH. The two came apart on
2026-11-20: `data_learning/niche.config.json` held 73 un-posted stories, the
posting run held every one of them (34 on non-official data, the rest on
premise, currency or repetition), and the story forge's top-up read "73
un-posted, target 10 — queue already full, nothing to forge" twice a day
while the channel posted nothing. The forge measured stock; the channel
needed supply.

`postable()` is the one measure: un-posted stories MINUS the ones the most
recent posting run held, read from the run's own record
(`state/explainer_runs.json`, written by `post_stories._record_run`). A
story the last run held is not supply until something rewrites it — the
rewrite mailbox owns that — so it must not count against a top-up. A story
the last run never looked at (a brand-new one) counts: it has not failed.

Every caller that asks "do we need more stories?" reads this, never a raw
un-posted count: the forge's `--top-up`, the authoring brief's queue
minimum. The posted log is never touched.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "data_learning" / "niche.config.json"
POSTED_LOG = ROOT / "state" / "explainer_posted_log.json"
RUNS = ROOT / "state" / "explainer_runs.json"


def _read(path: Path) -> dict:
    try:
        got = json.loads(Path(path).read_text())
    except Exception:  # noqa: BLE001
        return {}
    return got if isinstance(got, dict) else {}


def posted_slugs(posted_log: Path = POSTED_LOG) -> set[str]:
    return set(_read(posted_log).get("posted", {}) or {})


def held_by_last_run(runs_path: Path = RUNS) -> set[str]:
    """Slugs the most recent REAL posting run held, by any reason.

    A dry run is a rehearsal and holds nothing on the channel's behalf; it
    is skipped. With no record at all (a fresh checkout, a first run) the
    answer is the empty set — nothing is known to be held, so nothing is
    discounted.
    """
    runs = _read(runs_path).get("runs") or []
    for rec in reversed(runs):
        if not isinstance(rec, dict) or rec.get("dry_run"):
            continue
        held = rec.get("held") or {}
        out: set[str] = set()
        for slugs in held.values():
            out.update(s for s in (slugs or []) if isinstance(s, str))
        return out
    return set()


def unposted_slugs(cfg: dict, posted_log: Path = POSTED_LOG) -> list[str]:
    posted = posted_slugs(posted_log)
    return [s.get("slug") for s in cfg.get("stories", [])
            if s.get("slug") and s["slug"] not in posted]


def postable(cfg: dict, *, posted_log: Path = POSTED_LOG,
             runs_path: Path = RUNS) -> dict:
    """The queue's supply, with its arithmetic shown.

    Returns {"unposted": n, "held": m, "postable": [slug, ...]} where
    `held` counts the un-posted stories the last posting run held and
    `postable` is what is left — the number a top-up compares to its target.
    """
    unposted = unposted_slugs(cfg, posted_log)
    held = held_by_last_run(runs_path)
    left = [s for s in unposted if s not in held]
    return {"unposted": len(unposted), "held": len(unposted) - len(left),
            "postable": left}


def describe(supply: dict, target: int) -> str:
    """One line a run log can print and a reader can check."""
    return (f"un-posted queue: {supply['unposted']} "
            f"({supply['held']} held by the last posting run) -> "
            f"postable {len(supply['postable'])}; target {target}")
