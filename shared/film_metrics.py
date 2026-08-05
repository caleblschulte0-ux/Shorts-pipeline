"""FILM METRICS — score a shot plan in milliseconds, before spending a render.

WHY THIS EXISTS. Between 2026-08-01 and 08-02 five full renders of one story
were judged. Each cost 2.5-4.5 hours of runner time. Each taught exactly one
thing, because there was no way to ask "did that change help?" without paying
for a render and a blind judge. Two of the five changes made the film WORSE and
nobody could know until the video existed:

    attempt  scene shots  overall  personality   what changed
    1        14           4.0      2             (baseline)
    2        14           4.0      2             healer input fixed
    3        14           3.5      2             scenes restaged -> NOW SERVING widgets
    4         0           3.5      2             scene library banned -> character GONE
    5         0           3.0      1             media dedupe; NO_CHARACTER appears

The regression that cost a full point is visible in column two. It is a
property of the SHOT PLAN — computable offline, instantly, with no media, no
ffmpeg and no judge. Twelve hours of rendering were spent discovering something
a function could have said in a millisecond.

So: this module scores a plan. It does not replace the blind taste judge, which
sees pixels and is the only thing allowed to say a film is good. It catches the
class of change that makes a film structurally worse — no human on screen, one
clip used twice, half the beats depicting nothing in particular — so that a
render is only ever spent on a plan that is not already known to be broken.

    from shared import film_metrics
    m = film_metrics.score_plan(shots, beats)
    print(m["summary"])            # one line
    film_metrics.compare(before, after)   # what a change did, in both directions

SHARED ON PURPOSE. Nothing here knows a slug, a channel or a topic. Any channel
that plans shots before rendering can score them.
"""
from __future__ import annotations

import json
from pathlib import Path

# A shot kind that puts a human figure on screen. The taste rubric's
# NO_CHARACTER / NO_SOUL labels are about this and almost nothing else.
_FIGURE_PREFIX = "scene_"
# Flat designed plates: the CARDS_OVER_BUDGET family.
_CARD_PREFIX = ("flat_", "chapter", "title")


def _kind(sh: dict) -> str:
    return str(sh.get("kind") or "")


def _secs(sh: dict) -> float:
    try:
        return float(sh.get("seconds") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _media_key(sh: dict) -> str:
    """What asset this shot will fetch — the thing that must not repeat."""
    for k in ("_local_src", "footage_nasa_id", "motion_query", "image_query"):
        v = sh.get(k)
        if v:
            return f"{k}:{str(v).strip().lower()}"
    img = sh.get("image") or {}
    q = img.get("query") if isinstance(img, dict) else None
    return f"image_query:{str(q).strip().lower()}" if q else ""


def score_plan(shots: list[dict], beats: list[dict] | None = None) -> dict:
    """Objective, render-free properties of a planned film.

    Every number here is something a blind judge has actually complained about
    in a recorded verdict, which is the bar for being in this dict at all. No
    metric is included because it seemed sensible.
    """
    shots = list(shots or [])
    total = sum(_secs(s) for s in shots) or 1.0

    figure = [s for s in shots if _kind(s).startswith(_FIGURE_PREFIX)]
    cards = [s for s in shots if _kind(s).startswith(_CARD_PREFIX)]

    # A repeated asset is the flaw a viewer notices unprompted. Judges have
    # named duplicate pairs by timestamp without being asked to look for them.
    keys = [k for k in (_media_key(s) for s in shots) if k]
    dup = len(keys) - len(set(keys))

    # A media shot whose query shares no content word with the line it plays
    # under would serve any other beat equally well — the "could be shuffled
    # with zero consequence" complaint, made mechanical.
    unanchored = 0
    anchorable = 0
    try:
        from data_learning import textmatch
        for s in shots:
            q = s.get("motion_query") or (s.get("image") or {}).get("query")
            line = s.get("line") or s.get("line_hint") or ""
            if not q or not str(line).strip():
                continue
            anchorable += 1
            if not textmatch.shares(q, line):
                unanchored += 1
    except Exception:  # noqa: BLE001 — metrics must never break a render
        pass

    m = {
        "shots": len(shots),
        "runtime_s": round(total, 1),
        "figure_shots": len(figure),
        "figure_fraction": round(sum(_secs(s) for s in figure) / total, 3),
        "card_fraction": round(sum(_secs(s) for s in cards) / total, 3),
        # NOT-MEASURED IS None, NEVER ZERO. A plan with no media queries in it
        # (a legacy plan, or one reconstructed from performance.json, which
        # records what rendered and not what was searched) can say nothing
        # about duplicates or anchoring. Reporting 0 there makes an unmeasured
        # axis look perfect, and comparing a real plan against it manufactures
        # a regression that never happened — which this module did, once, on
        # its own first real comparison.
        "duplicate_media": dup if keys else None,
        "distinct_media": len(set(keys)) if keys else None,
        "unanchored_media": unanchored if anchorable else None,
        "anchorable_media": anchorable,
        "unanchored_fraction": (round(unanchored / anchorable, 3)
                                if anchorable else None),
        "beats": len(beats or []),
    }
    def _n(v, alt="n/a"):
        return alt if v is None else v

    m["summary"] = (
        f"{m['shots']} shots / {m['runtime_s']}s · "
        f"figure {m['figure_shots']} ({m['figure_fraction']:.0%}) · "
        f"cards {m['card_fraction']:.0%} · "
        f"dup-media {_n(m['duplicate_media'])} · "
        f"unanchored {_n(m['unanchored_media'])}/{m['anchorable_media']}")
    return m


# What "better" means, per metric. This is the only place the direction of
# improvement is written down, so a future change cannot quietly redefine it.
BETTER = {
    "figure_shots": "up",
    "figure_fraction": "up",
    "card_fraction": "down",
    "duplicate_media": "down",
    "unanchored_media": "down",
    "unanchored_fraction": "down",
}


def compare(before: dict, after: dict) -> dict:
    """What a change did — improvements AND regressions, both named.

    Reporting only the wins is how a change that removed every human from the
    frame got shipped as a fix. `regressions` is not optional output.
    """
    wins, losses = [], []
    for k, want in BETTER.items():
        a, b = before.get(k), after.get(k)
        if a is None or b is None or a == b:
            continue
        improved = (b > a) if want == "up" else (b < a)
        (wins if improved else losses).append(f"{k} {a} -> {b}")
    return {"improved": wins, "regressed": losses,
            "verdict": ("REGRESSION" if losses else
                        "improvement" if wins else "no change")}


def guard(before: dict, after: dict, *, forbid: tuple = ("figure_shots",)) -> list[str]:
    """Hard refusals: changes never worth making, whatever else improves.

    `figure_shots` going to zero is the default because that exact regression is
    measured — it cost a point of overall score and a point of personality, and
    it was invisible until a 4-hour render and a blind judge said NO_CHARACTER.
    """
    bad = []
    for k in forbid:
        a, b = before.get(k), after.get(k)
        if a is None or b is None:
            continue
        if a > 0 and b == 0:
            bad.append(f"{k} fell to ZERO ({a} -> 0) — refuse this change")
    return bad


# ---------------------------------------------------------------- the ledger
LEDGER = Path("state/curiosity_quality_ledger.jsonl")


def record(slug: str, metrics: dict, *, verdict: dict | None = None,
           note: str = "", head: str = "", path: Path | None = None) -> None:
    """Append one row: what was planned, and what the judge said about it.

    Without this, "is it improving?" is answered from memory across renders
    hours apart. With it, five videos is a table.
    """
    f = Path(path) if path else LEDGER
    row = {"slug": slug, "head": head, "note": note, **metrics}
    if verdict:
        row["overall_10"] = verdict.get("overall_10")
        row["personality"] = verdict.get("personality")
        row["reject_labels"] = verdict.get("reject_labels")
        row["pass"] = verdict.get("pass")
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    except Exception as e:  # noqa: BLE001 — a ledger write must not fail a render
        print(f"[film_metrics] could not record: {e}")


def history(path: Path | None = None) -> list[dict]:
    f = Path(path) if path else LEDGER
    if not f.exists():
        return []
    out = []
    for ln in f.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def trend(rows: list[dict] | None = None, n: int = 5) -> dict:
    """Is the last n better than the n before it? Answered, not asserted.

    Deliberately blunt: mean overall_10 and mean personality over two adjacent
    windows. With single-digit sample sizes anything cleverer would launder
    noise into a mandate — the same failure `retro/README.md` warns about.
    """
    rows = rows if rows is not None else history()
    scored = [r for r in rows if r.get("overall_10") is not None]
    if len(scored) < 2:
        return {"enough_data": False, "n_scored": len(scored)}
    recent, prior = scored[-n:], scored[-2 * n:-n]
    if not prior:
        return {"enough_data": False, "n_scored": len(scored),
                "note": f"only {len(scored)} scored renders; need {n * 2} to compare windows"}

    def mean(rs, k):
        v = [r[k] for r in rs if r.get(k) is not None]
        return round(sum(v) / len(v), 2) if v else None

    out = {"enough_data": True, "window": n,
           "recent_overall": mean(recent, "overall_10"),
           "prior_overall": mean(prior, "overall_10"),
           "recent_personality": mean(recent, "personality"),
           "prior_personality": mean(prior, "personality")}
    d = (out["recent_overall"] or 0) - (out["prior_overall"] or 0)
    out["delta_overall"] = round(d, 2)
    out["direction"] = "better" if d > 0.25 else "worse" if d < -0.25 else "flat"
    return out


if __name__ == "__main__":  # pragma: no cover
    import sys
    rows = history()
    print(f"{len(rows)} rows in {LEDGER}")
    for r in rows[-10:]:
        print(f"  {r.get('slug','?'):<16} {str(r.get('head',''))[:8]:<9} "
              f"overall={r.get('overall_10')} p={r.get('personality')} "
              f"figure={r.get('figure_shots')} dup={r.get('duplicate_media')} "
              f"{r.get('note','')}")
    t = trend(rows)
    print(json.dumps(t, indent=1))
    sys.exit(0)
