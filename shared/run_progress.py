"""Where a posting run is, and when its next video should be up.

Operator, 2026-10-12, after a day of "ETA?" answered with "I can't say":
*"You need to add something so we have a better guess on this shit."*
A run's live log is unreadable until the job ends, so nobody — operator or
session — could see whether a run was drawing its second story or stuck on
its first.

Now the run says so itself. `Tracker.mark(slug, phase)` is called at each
step a story goes through (prep -> render -> review -> upload -> posted /
held). Every mark is pushed to the `run-progress` branch as one small JSON
file per channel — a status branch, force-written, never merged, so it adds
nothing to `main` and fires no workflow. The same file keeps the last
`HISTORY` stories' phase timings, and the ETA is read from them:
how long this story's remaining phases usually take, and how often a story
that reaches render actually posts.

`python scripts/run_eta.py` prints it in plain words. Bookkeeping only:
nothing here can raise into a run, and nothing reads it to decide anything.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

BRANCH = "run-progress"
HISTORY = 60
PHASES = ("prep", "render", "review", "upload")
# Used until a phase has history of its own (minutes). Deliberately on the
# slow side: an ETA that comes early is the one that gets a person angry.
DEFAULT_MIN = {"prep": 4.0, "render": 30.0, "review": 12.0, "upload": 2.0}
DEFAULT_POST_RATE = 0.5
MIN_LEFT = 1.0


def _now() -> float:
    return time.time()


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


def typical(history: list[dict]) -> dict:
    """Median minutes per phase over stories that went through it."""
    out = dict(DEFAULT_MIN)
    for ph in PHASES:
        xs = [h["phases"][ph] for h in history
              if isinstance(h.get("phases"), dict)
              and "review" in h["phases"]
              and isinstance(h["phases"].get(ph), (int, float))]
        if len(xs) >= 3:
            out[ph] = round(statistics.median(xs), 1)
    return out


def post_rate(history: list[dict]) -> float:
    """Share of stories that reached review and then posted."""
    tried = [h for h in history if "review" in (h.get("phases") or {})]
    if len(tried) < 3:
        return DEFAULT_POST_RATE
    return max(0.1, sum(1 for h in tried if h.get("outcome") == "posted")
               / len(tried))


def estimate(state: dict, now: float | None = None) -> dict:
    """Minutes until the current story is done, and until the next post.

    `this_story_min` assumes the story passes; `next_post_min` adds, for
    the chance it is held, the expected number of further full attempts.
    """
    now = _now() if now is None else now
    hist = state.get("history") or []
    typ = typical(hist)
    rate = post_rate(hist)
    cur = state.get("current") or {}
    full = sum(typ[p] for p in PHASES)
    if not cur.get("slug"):
        left = None
    else:
        ph = cur.get("phase")
        idx = PHASES.index(ph) if ph in PHASES else 0
        spent = (now - cur.get("phase_since", now)) / 60.0
        left = max(MIN_LEFT, typ[PHASES[idx]] - spent)
        left += sum(typ[p] for p in PHASES[idx + 1:])
    base = left if left is not None else full
    nxt = base + (1 - rate) / rate * full
    return {"this_story_min": None if left is None else round(left),
            "next_post_min": round(nxt), "typical_min": typ,
            "post_rate": round(rate, 2), "full_story_min": round(full)}


def _git(*a, inp: str | None = None) -> str:
    r = subprocess.run(["git", *a], input=inp, capture_output=True,
                       text=True, timeout=60)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-200:])
    return r.stdout.strip()


def _read_remote(name: str) -> dict:
    try:
        _git("fetch", "-q", "--depth=1", "origin", f"+refs/heads/{BRANCH}:"
             f"refs/remotes/origin/{BRANCH}")
        return json.loads(_git("show", f"origin/{BRANCH}:{name}"))
    except Exception:  # noqa: BLE001 — a first run has no branch yet
        return {}


def _write_remote(name: str, state: dict) -> None:
    """One commit holding just this file, force-pushed to the status
    branch. Plumbing only: the run's working tree and index are untouched."""
    blob = _git("hash-object", "-w", "--stdin",
                inp=json.dumps(state, indent=1) + "\n")
    tree = _git("mktree", inp=f"100644 blob {blob}\t{name}\n")
    env_msg = f"progress: {state.get('channel')} {state.get('updated')}"
    commit = _git("-c", "user.name=run-progress",
                  "-c", "user.email=run-progress@users.noreply.github.com",
                  "commit-tree", tree, "-m", env_msg)
    _git("push", "-q", "-f", "origin", f"{commit}:refs/heads/{BRANCH}")


class Tracker:
    def __init__(self, channel: str, *, push: bool | None = None,
                 reader=None, writer=None):
        self.channel = channel
        self.name = f"{channel}.json"
        self.push = (bool(os.environ.get("GITHUB_ACTIONS"))
                     if push is None else push)
        self._read = reader or _read_remote
        self._write = writer or _write_remote
        prev = self._safe(lambda: self._read(self.name)) if self.push else {}
        prev = prev if isinstance(prev, dict) else {}
        self.state = {
            "channel": channel,
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "run_started": _iso(_now()),
            "current": {}, "done": [],
            "history": list(prev.get("history") or [])[-HISTORY:],
        }
        self._story: dict = {}

    @staticmethod
    def _safe(fn):
        try:
            return fn()
        except Exception:  # noqa: BLE001 — never break a run over this
            return None

    def mark(self, slug: str, phase: str) -> None:
        """Record that `slug` has entered `phase` (one of PHASES)."""
        self._safe(lambda: self._mark(slug, phase))

    def _mark(self, slug, phase):
        t = _now()
        if self._story.get("slug") != slug:
            self._story = {"slug": slug, "phases": {}}
        cur = self.state["current"]
        if cur.get("slug") == slug and cur.get("phase") in PHASES:
            self._story["phases"][cur["phase"]] = round(
                (t - cur["phase_since"]) / 60.0, 1)
        self.state["current"] = {"slug": slug, "phase": phase,
                                 "phase_since": t, "since": _iso(t)}
        self._flush()

    def finish(self, slug: str, outcome: str, url: str | None = None) -> None:
        """`outcome` is "posted" or the reason it was not."""
        self._safe(lambda: self._finish(slug, outcome, url))

    def _finish(self, slug, outcome, url):
        cur = self.state["current"]
        if cur.get("slug") != slug:
            return
        t = _now()
        if cur.get("phase") in PHASES:
            self._story.setdefault("phases", {})[cur["phase"]] = round(
                (t - cur["phase_since"]) / 60.0, 1)
        rec = {"slug": slug, "outcome": outcome, "at": _iso(t),
               "phases": dict(self._story.get("phases") or {})}
        if url:
            rec["url"] = url
        self.state["done"].append(rec)
        # Only a story that got as far as review taught us anything about
        # timing: one refused at the start of render (no drawn scenes,
        # 2026-10-13) took 0.2 min and would drag every median to zero.
        if "review" in rec["phases"]:
            self.state["history"] = (self.state["history"] + [rec])[-HISTORY:]
        self.state["current"] = {}
        self._story = {}
        self._flush()

    def end(self) -> None:
        self.state["current"] = {}
        self.state["ended"] = _iso(_now())
        self._safe(self._flush)

    def _flush(self):
        self.state["updated"] = _iso(_now())
        self.state["eta"] = estimate(self.state)
        if self.push:
            self._write(self.name, self.state)
