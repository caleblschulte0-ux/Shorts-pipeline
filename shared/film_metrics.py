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

    # A HUMAN ON SCREEN, BY WHATEVER MEANS. This counted `scene_*` kinds only
    # — the designed pictograms — which made the metric's name a lie: a film
    # carried entirely by real footage of people scored figure_shots=0 and
    # would have been refused by `guard` for having "no character", while a
    # blind judge watching it sees people throughout. Worse, the judges HATE
    # the pictograms ("a cartoon stick figure on an empty blue slide") and
    # every memorable frame any of them named was real footage of a person.
    # Equating "figure" with "pictogram" had the sign backwards.
    #
    # Both are still visible separately, because the regression this module
    # was built to catch — the scene-library ban that removed all 14 character
    # shots — is a collapse in `pictogram_shots`, and folding the two together
    # would hide it.
    pictogram = [s for s in shots if _kind(s).startswith(_FIGURE_PREFIX)]
    live_figure = []
    try:
        from shared import shot_brief
        for s in shots:
            if _kind(s).startswith(_FIGURE_PREFIX):
                continue
            q = s.get("motion_query") or s.get("image_query") \
                or (s.get("image") or {}).get("query") or ""
            if q and shot_brief.wants_a_person(q):
                live_figure.append(s)
    except Exception:  # noqa: BLE001 — metrics never break a render
        pass
    figure = pictogram + live_figure
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

    # THE CUT ITSELF. SAMENESS and BORING appeared in EVERY taste verdict on
    # shared-air and every response was a change to what was on screen. The
    # plan for that film had 39 shots and FOUR distinct shot lengths, because
    # `max_unchanged` was a constant and every beat cut at exactly 4.5s.
    #
    # Two numbers, because one of them alone is gameable and I gamed it: an
    # early version of the rhythm fix raised distinct lengths 4 -> 8 while
    # squeezing the range from 1.85-4.5s down to 2.80-3.55s. More values, less
    # contrast, a worse edit — and a scorer counting only distinct values would
    # have called it progress. Variety without range is a different monotony.
    durs = [round(_secs(s), 2) for s in shots if _secs(s) > 0]
    span = round(max(durs) - min(durs), 2) if durs else None

    # THE CAMERA, same defect shape as the cut and found the same way: the
    # planner never set `direction` or `pan`, so every shot pushed in with the
    # same drift for two minutes. `repeated` counts adjacent pairs sharing a
    # move — two cuts in a row drifting the same way read as one continuous
    # camera, not as two shots.
    moves = [(s.get("direction"), s.get("pan")) for s in shots
             if s.get("direction")]
    repeated = sum(1 for a, b in zip(moves, moves[1:]) if a == b) if moves else None

    # THE SAME DESIGNED SCENE, DRAWN THE SAME WAY, MORE THAN ONCE. Not an
    # adjacency check like `repeated_moves` — the judges' complaint was about
    # recurrence anywhere in the film ("94.4s and its verbatim repeats at
    # 59.5s and 150.4s"), so this counts every scene shot after the first that
    # shares BOTH its kind and its framing with an earlier one. Four blind
    # judges across two films named this and nothing in this module could see
    # it, which is why it is here.
    staged = [(_kind(s), tuple(s.get("framing") or ()))
              for s in shots if _kind(s).startswith(_FIGURE_PREFIX)]
    seen_stagings: set = set()
    dup_staging = 0
    for key in staged:
        if key in seen_stagings:
            dup_staging += 1
        seen_stagings.add(key)

    m = {
        "shots": len(shots),
        "runtime_s": round(total, 1),
        "shot_lengths": len(set(durs)) if durs else None,
        "length_span_s": span,
        "camera_moves": len(set(moves)) if moves else None,
        "repeated_moves": repeated,
        "repeated_stagings": dup_staging if staged else None,
        "figure_shots": len(figure),
        "pictogram_shots": len(pictogram),
        "live_figure_shots": len(live_figure),
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
        f"cut {_n(m['shot_lengths'])} lengths over {_n(m['length_span_s'])}s · "
        f"camera {_n(m['camera_moves'])} moves, {_n(m['repeated_moves'])} repeats · "
        f"staging-repeats {_n(m['repeated_stagings'])} · "
        f"figure {m['figure_shots']} ({m['figure_fraction']:.0%}) · "
        f"cards {m['card_fraction']:.0%} · "
        f"dup-media {_n(m['duplicate_media'])} · "
        f"unanchored {_n(m['unanchored_media'])}/{m['anchorable_media']}")
    return m


# ADVISORY, NOT ACTIONABLE. `unanchored_media` is deliberately absent from any
# automatic repair, and this is not an oversight.
#
# 2026-08-02: the metric said 8 of 15 shots were unanchored. The obvious fix —
# derive the query from the beat's own narration, which does contain the nouns —
# took it to 0/15 and would have shipped a worse film:
#
#     'wind blowing grass field'        -> 'stay home moves constantly'
#     'two people talking outdoors'     -> 'every argument anyone ever'
#     'child running outdoors sunlight' -> 'means next person breathe'
#
# First-N-content-words grabs verbs and abstractions; those are not stock
# searches. A perfect score, no footage, every beat degraded to a card.
#
# Picking a searchable SUBJECT out of prose needs language understanding, not
# word counting. The pipeline has that in the authoring brain, which runs before
# the planner. So this number is REPORTED for an author to act on and is never
# wired to a transformation. A measure that can be satisfied without improving
# the film must not be given a lever.
UNANCHORED_IS_ADVISORY = True


def unanchored_beats(shots: list[dict]) -> list[dict]:
    """The shots whose query does not depict their own line — for an AUTHOR.

    Returns what a person (or the authoring brain) needs to rewrite the beat:
    the query that was used and the line it played under. No suggestion is
    offered, because the one this module tried to generate was word salad.
    """
    out = []
    try:
        from data_learning import textmatch
    except Exception:  # noqa: BLE001
        return out
    for s in shots or []:
        q = s.get("motion_query") or (s.get("image") or {}).get("query")
        line = s.get("line") or s.get("line_hint") or ""
        if q and str(line).strip() and not textmatch.shares(q, line):
            out.append({"query": str(q), "line": str(line)[:120]})
    return out


# What "better" means, per metric. This is the only place the direction of
# improvement is written down, so a future change cannot quietly redefine it.
BETTER = {
    "figure_shots": "up",
    "figure_fraction": "up",
    # Real people beat drawn ones: every judge's memorable frame was footage.
    "live_figure_shots": "up",
    "card_fraction": "down",
    "duplicate_media": "down",
    "unanchored_media": "down",
    "unanchored_fraction": "down",
    # The cut. Both, always, together — see the note in `score_plan`: raising
    # the count while shrinking the span is a WORSE edit that scores better on
    # either number read alone. Listing both here means `compare` reports the
    # squeeze as a REGRESSION, which is exactly what it is.
    "shot_lengths": "up",
    "length_span_s": "up",
    # The camera. `repeated_moves` is the one that matters — a plan can have
    # many distinct moves and still put two identical ones back to back.
    "camera_moves": "up",
    "repeated_moves": "down",
    # The same designed scene drawn identically twice. Four judges, two films.
    "repeated_stagings": "down",
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


def ledger_path() -> Path:
    """Where rows go. `CURIOSITY_QUALITY_LEDGER` overrides it.

    Needed the moment `produce()` started recording every render by itself:
    the CI producer smoke runs the real producer on a throwaway fixture, so
    the first smoke after that landed wrote a `zz-ci-smoke` row into the
    standing ledger. Every CI run would have added one, and `trend()` averages
    whatever it finds — a window of fixture scores reported as the channel's
    quality. Fixtures go to a temp file; only real renders reach the record.
    """
    import os
    return Path(os.environ.get("CURIOSITY_QUALITY_LEDGER") or LEDGER)


def record(slug: str, metrics: dict, *, verdict: dict | None = None,
           note: str = "", head: str = "", path: Path | None = None) -> None:
    """Append one row: what was planned, and what the judge said about it.

    Without this, "is it improving?" is answered from memory across renders
    hours apart. With it, five videos is a table.
    """
    f = Path(path) if path else ledger_path()
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
    f = Path(path) if path else ledger_path()
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


# How many renders a defect must survive before it is a CODE problem.
# Two is the smallest number that can distinguish "this film had that flaw"
# from "the machine produces that flaw". One is not evidence of anything.
RECURRENCE_THRESHOLD = 2


def recurring_defects(rows: list[dict] | None = None, n: int = 5) -> dict:
    """Split the judge's complaints into CODE problems and FILM problems.

    THE MISTAKE THIS EXISTS TO STOP. Across the 2026-08-01/02 sprint every
    change was chosen from the single loudest complaint in the single most
    recent verdict. That is a sample size of one, and it produced two
    regressions out of five: the scene-library ban was a response to one
    judge's UI_WIDGET note, and it deleted every human in the film.

    A label that appears in ONE verdict is evidence about ONE film — re-author
    the beat. A label that survives across renders, through repairs aimed at
    it, is evidence about the MACHINE — that is the one worth spending a code
    change on. This function does not rank, score, or suggest; it counts, and
    counting is the whole contribution. What to do about a recurring label is
    a judgment, and judgments do not belong in a metrics module.
    """
    rows = rows if rows is not None else history()
    window = rows[-n:] if n else rows
    seen: dict[str, list[str]] = {}
    for r in window:
        for lab in (r.get("reject_labels") or []):
            seen.setdefault(str(lab), []).append(str(r.get("head", ""))[:8])
    recurring = {k: v for k, v in seen.items() if len(v) >= RECURRENCE_THRESHOLD}
    once = {k: v for k, v in seen.items() if len(v) < RECURRENCE_THRESHOLD}
    return {"window": len(window), "n_judged":
            sum(1 for r in window if r.get("reject_labels") is not None),
            "recurring": dict(sorted(recurring.items(),
                                     key=lambda kv: -len(kv[1]))),
            "once": once,
            "threshold": RECURRENCE_THRESHOLD}


def stagnant(rows: list[dict] | None = None, n: int = 5) -> str | None:
    """Has the window moved at all? Returns why not, or None if it moved.

    A flat trend across a full window is itself a finding: it means the
    changes being made are not the changes that matter. Saying so is the
    difference between a sprint and a treadmill.
    """
    rows = rows if rows is not None else history()
    scored = [r for r in (rows[-n:] if n else rows)
              if r.get("overall_10") is not None]
    if len(scored) < n:
        return None                      # not a full window yet: no claim
    vals = [r["overall_10"] for r in scored]
    if max(vals) - min(vals) < 0.25:
        return (f"{len(vals)} renders and the score never left {vals[0]} — the "
                "changes being made are not the ones that matter")
    if vals[-1] <= vals[0]:
        return (f"{len(vals)} renders ended at {vals[-1]}, no better than the "
                f"{vals[0]} it started at")
    return None


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
