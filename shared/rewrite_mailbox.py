"""A HELD EXPLAINER STORY IS RE-AUTHORED, NOT PARKED — by ChatGPT, through a mailbox.

Operator, 2026-09-22: *"ChatGPT is supposed to render videos if nothing else
is available. And ChatGPT is always available."* — and the gap that made
that false on the explainer, read off the queue that morning with the
deterministic gate (`python scripts/editorial_gate.py`):

    312 of 337 stories HELD, 25 pass. Top reasons:
      205  premise: no consequential number in the title or hook
       95  premise: title reads as a searchable noun phrase, not a premise
       79  thesis:  segN shares no keyword with the headline
       29  beats:   the line's headline number is Nx away from anything
                    this beat's picture can show

Every one of those is a WORD problem — title, hook, a segment's `topic`
label, a `say` line — and the numbers underneath are real and sourced. The
takeover already asked ChatGPT to rewrite explainer words, but only for
stories flagged `words_by == "deterministic"`; none of the 87 un-posted
stories carry that flag, so nothing was ever asked, and a story the gate
held on Monday was held identically on Tuesday. Trending re-authors a
refused slot (`run_trending_daily._backfill`); the explainer had no loop.

This is the loop:

    the run holds a story  ->  exchange/rewrites/<date>/<id>.request.json
        (current words, every segment's real numbers, the EXACT rules the
         gate applies, the exact hold reasons, and for a judge block the
         judge's own problems/fixes)
    ChatGPT rewrites       ->  exchange/rewrites/<date>/<id>.answer.json
    claim_rewrites         ->  CODE validates: same segment count; every
        number spoken must be derivable from THAT segment's data
        (`shared.beat_match` — the same matcher the gate uses); no new
        named entity outside the data's own labels; then the SAME
        deterministic gate the run applies must PASS on the rewritten
        story. Only then is niche.config.json updated, `words_by` set to
        `chatgpt-rewrite`, the slug's old scene plan dropped, and the
        story re-rendered by the next run and judged like any other.

Nothing ships unjudged. A rewrite that moves a number, invents an entity, or
still fails the gate is REFUSED with the reasons written beside it, and a
fresh request goes out carrying those reasons so the next round can fix
them. ChatGPT writes; code decides.

THE ASK IS TODAY'S (doctor aaeb12de3ebd, 2026-11-23). Read off the open
index that morning, 144 requests for a queue of 72:

    48  carried hold reasons the run no longer gave -- 14 of them "premise:
        no consequential number in the title or hook", a rule retired on
        11-17, because a request is idempotent on the story's WORDS and the
        same words held again for a NEW reason kept the old file untouched;
    37  were for stories held `data:` (an illustrative source) that no
        rewrite can ever post -- a quarter of every firing's 10-request cap;
     0  asked for the narration: nine stories had sat `not_current` for six
        or more runs as readouts the brain's retell could not fix, and the
        mailbox only ever filed `editorial_hold` and the judge's blocks.

So: the same words held again REFRESHES the open request with the reasons
the run gave today (`refiled`); a story held for its data RETIRES every
open request for it (`unpostable`) and files none; a narration readout or
a hook under the floor is filed as a `narration:` / `hook:` reason; and
ChatGPT's answer must clear the narration doctrine too, as the rules it is
handed already say (the brain's own retell and tighten keep checking it
themselves).

A REPEAT IS RETITLED, NOT PARKED (doctor aaeb12de3ebd, 2026-11-25). The
run holds a story whose TITLE is too close to a video already up before
the gate ever sees it, and its own message has said since 10-02 "The
story is fine; the PACKAGING repeats. Retitle it and it ships" -- but
nothing ever asked anyone to retitle it: `file_for_run` had no branch for
`duplicate_hold`, so three stories sat `duplicate_hold` on every one of
the twelve runs of 11-23..11-25 (one of them "The Ocean Lost 71% Of Its
Sharks Since 1970", held against "The World Lost 35% Of Its Wetlands
Since 1970" -- the title TEMPLATE repeats, the story does not). Now a
title repeat is filed as a `repeat:` reason naming the video it collides
with, plus whatever the gate would say; the claim refuses a retitle that
still collides (`validate(..., posted_titles=...)`, the run's own
matcher, `shared.near_duplicate.duplicate_of`, over the run's own corpus);
and a story the BRAIN reads as the same story as a posted video (the
`repeat: "story"` hold -- "a new title over the same comparison is a
repeat") retires its asks instead: no retitle can post it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REWRITES_DIR = REPO / "exchange" / "rewrites"
PLANS_DIR = REPO / "state" / "scene_plans"
SCHEMA = "shorts-rewrite-request/v1"
ANSWER_SCHEMA_NAME = "shorts-rewrite-answer/v1"
MAX_POINTS = 24           # data points listed per segment in a request
MAX_TOPIC_WORDS = 4       # a topic is an ON-SCREEN label; long ones clip
# The beat budget is the registry's (shared/pacing.py; operator 2026-10-05:
# "15 seconds per beat is far too long"). 40 was the old ceiling and it let
# 26-word beats through for a month.
from shared import pacing as _pacing  # noqa: E402
MAX_SAY_WORDS = _pacing.budget()["say_words"]
WORDS_BY = "chatgpt-rewrite"


def words_by(ans: dict) -> str:
    """Who wrote these words, for the record: `aletheia:<route>` answers
    (operator, 2026-09-30: "let Alethea answer the mailbox") are
    Aletheia's; an interactive Claude session answering the mailbox directly
    (the ChatGPT-quarterback backlog is content, not pipeline code — rule
    zero, 2026-08-01) writes `by: "claude"` and is recorded as its own
    provenance rather than borrowing ChatGPT's name; anything else keeps the
    historical name. Provenance only — every writer's words pass the same
    `validate`."""
    head = str((ans or {}).get("by") or "").strip().lower().split(":", 1)[0]
    if head == "aletheia":
        return "aletheia-rewrite"
    if head == "claude":
        return "claude-rewrite"
    return WORDS_BY

#: The gate's four word rules, in the words ChatGPT is given. These restate
#: `scripts/editorial_gate.py` — the CODE there is what decides, this text
#: only tells the writer what it will be measured against.
RULES = [
    # story-first playbook §13, 2026-11-17: a CONCRETE premise replaced the
    # mandatory digit (the hook carries no number — hook_doctrine).
    "The PREMISE must be CONCRETE: the TITLE or HOOK names the story's own "
    "subject plainly (a word its topics or data are labelled with) and "
    "promises a specific surprise, threat or scale the viewer can picture. "
    "The video says the number; the hook says what it means.",
    "TITLE must be a PREMISE, not a searchable noun phrase: more than five "
    "words, or a number, or a question mark, or a tension word. 'Oldest "
    "Written Languages' is the failure; 'Why 3 of the 5 Oldest Scripts Are "
    "Still Unreadable' is the shape.",
    "The beats are ONE STORY in order: each one helps prove the headline "
    "AND follows from the beat before it (it happens because of it, or "
    "turns against it) — never 'and another fact'. A judge reads every beat "
    "for that; with no judge answering, each TOPIC (a 2-4 word on-screen "
    "label) must share a real word with the TITLE, so name the topics for "
    "what they are about.",
    "Every NUMBER you say in a segment's SAY must be one that segment's data "
    "can show: a listed value, a difference between two of them, a percent "
    "change, a share of the total, or the same value in a bigger unit. A "
    "number from nowhere is refused — a guard derives every spoken quantity "
    "from the listed points.",
    "Keep every number that is already correct. Do not add a country, "
    "company or person the data does not name.",
    _pacing.rule() + " Each SAY says its beat's headline number out loud.",
    # operator, 2026-10-09 — the full doctrine is shared/narration.py
    "Each beat is part of a STORY, not a readout, simple enough for a "
    "distracted viewer: at most ONE number a beat, said with what it means "
    "(a change in words: 'it nearly doubled'). Name no group a "
    "viewer would not know ('the experts', not 'the OECD'); the WHO, NASA "
    "and the White House are fine.",
    "TOPIC labels are printed on the video: at most 4 words, no clause.",
    # operator, 2026-09-25 — the full doctrine is shared/hook_doctrine.py
    "The HOOK is clickbait, never a scam: the most surprising TRUE fact in "
    "the story, 5-14 words, said the way a person tells a friend. It makes "
    "sense heard once. 'You' only when it is the viewer's own money, body or "
    "kids. No formula tags ('...and nobody told you', '...shocking "
    "everyone'), no quiz ('Which animal...', 'Did you know...'), no hedge "
    "(might, may), no vague size ('astonishing'). Exaggerate nothing.",
]

ANSWER_SCHEMA = {
    "schema": ANSWER_SCHEMA_NAME,
    "request_id": "<copied from the request>",
    "slug": "<copied>",
    "by": "chatgpt",
    "written_at": "<ISO-8601 UTC>",
    "title": "<the premise>",
    "hook": "<one line that stops the thumb: the threat or twist, no number>",
    "closing": "<lands the point>",
    "question": "<an engagement question, optional>",
    "segments": [{"topic": "<2-4 words>", "say": "<the line>"}],
}


def _rel(p) -> str:
    """A repo-relative path for logs/indexes, or the absolute one when the
    mailbox lives elsewhere (tests)."""
    try:
        return str(Path(p).relative_to(REPO))
    except ValueError:
        return str(p)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def words_of(sc: dict) -> dict:
    return {"title": sc.get("title") or "", "hook": sc.get("hook") or "",
            "closing": sc.get("closing") or "", "question": sc.get("question") or "",
            "segments": [{"topic": (s or {}).get("topic") or "",
                          "say": (s or {}).get("say") or ""}
                         for s in sc.get("segments") or []]}


def words_hash(sc: dict) -> str:
    return hashlib.sha1(json.dumps(words_of(sc), sort_keys=True).encode()).hexdigest()[:8]


def request_id(sc: dict) -> str:
    return f"{sc.get('slug')}__{words_hash(sc)}"


def _dataset(seg: dict) -> dict | None:
    from scripts import editorial_gate as eg
    p = eg._seg_data_path(seg)
    if p is None or not p.exists():
        return None
    try:
        d = json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None
    pts = [{"label": x.get("label"), "value": x.get("value"),
            **({"period": x["period"]} if x.get("period") else {})}
           for x in (d.get("points") or []) if isinstance(x, dict)]
    return {"file": p.name, "unit": d.get("unit", ""), "title": d.get("title", ""),
            "points": pts[:MAX_POINTS], "n_points": len(pts)}


# ---------------------------------------------------------------------------
# What the gate would say — word reasons only
# ---------------------------------------------------------------------------

#: `story:` is the story-first scorecard (shared/story_brief.py): a story it
#: holds is re-authored here like any other words hold.
#: `repeat:` is the run's near-duplicate TITLE hold: the packaging repeats a
#: posted video; a retitle fixes it (post_stories, `duplicate_hold`).
_WORD_PREFIX = ("premise:", "thesis:", "beats:", "pace:", "story:", "repeat:")


#: A hold no rewrite can lift: the story's DATA is not a real source
#: (`editorial_gate.data_provenance`). A request for such a story asks
#: ChatGPT to polish words over numbers that can never post.
_DATA_PREFIX = "data:"


def gate_reasons(sc: dict) -> list[str]:
    """Every reason the deterministic gate holds this story for; empty when
    it passes."""
    from scripts import editorial_gate as eg
    v = eg.pre_render_verdict(sc, use_llm=False)
    return [] if v["ok"] else [str(r) for r in v["reasons"]]


def words_only(reasons) -> list[str]:
    """The reasons in `reasons` a REWRITE can fix."""
    return [str(r) for r in reasons or []
            if str(r).startswith(_WORD_PREFIX)
            and not str(r).startswith("beats (noted)")]


def word_holds(sc: dict) -> list[str]:
    """The deterministic gate's reasons that a REWRITE can fix. Empty when
    the story passes, or when it is held only for data reasons (a source
    that is not real is not a words problem, and no rewrite is asked)."""
    return words_only(gate_reasons(sc))


def unpostable(reasons) -> list[str]:
    """The reasons in `reasons` that no rewrite can answer: the data."""
    return [str(r) for r in reasons or [] if str(r).startswith(_DATA_PREFIX)]


def narration_holds(sc: dict) -> list[str]:
    """The narration's word problems (`shared.narration.problems`) as hold
    reasons. The posting run holds a readout `not_current` before the gate
    ever sees it, so these never reached `editorial_hold` -- nine stories
    sat that way for six-plus runs each (explainer_health, 2026-11-23) with
    nobody asked to fix them."""
    from shared import narration
    return ["narration: " + str(p) for p in narration.problems(sc)]


#: The hold reason a title repeat is filed under, and the one a retitle that
#: still collides is refused with. Named here so the filing and the claim
#: can never drift on the word.
REPEAT_PREFIX = "repeat:"


def repeat_reason(duplicate_of: str) -> str:
    """The ask for a title repeat, in the run's own words (post_stories:
    "The story is fine; the PACKAGING repeats. Retitle it and it ships")."""
    return (f"{REPEAT_PREFIX} the TITLE is too close to a video already up: "
            f"{duplicate_of!r}. The story is fine; the PACKAGING repeats. Give "
            f"this video its own title (and a hook that says what THIS story "
            f"shows), not the posted video's shape with a noun swapped.")


def posted_titles(log_path: Path | None = None) -> list[str]:
    """Every title the run's near-duplicate check compares a story against:
    the explainer's whole posted log plus the data channels' uploads inside
    the registry's no-repeat window -- the same corpus `post_stories`
    builds before the gate, so a retitle the claim accepts is one the run
    will not hold again. Unreadable logs contribute nothing (the run's own
    loader fails closed on a corrupt ledger before anything reaches here)."""
    titles: list[str] = []
    log_path = Path(log_path or REPO / "state" / "explainer_posted_log.json")
    try:
        log = json.loads(log_path.read_text())
        posted = log.get("posted") if isinstance(log, dict) else {}
        entries = posted.values() if isinstance(posted, dict) else (posted or [])
        titles += [str(e.get("title") or "") for e in entries if isinstance(e, dict)]
    except Exception:  # noqa: BLE001
        pass
    try:
        from shared import near_duplicate as _nd
        titles += _nd.corpus_titles(_nd.posted_corpus(root=REPO))
    except Exception:  # noqa: BLE001
        pass
    return [t for t in titles if t.strip()]


def repeats(title: str, titles) -> str | None:
    """The posted title `title` is too close to, by the run's own matcher,
    or None."""
    from shared.near_duplicate import duplicate_of
    return duplicate_of(title or "", titles or [])


# ---------------------------------------------------------------------------
# Filing
# ---------------------------------------------------------------------------

def open_requests(rewrites_dir: Path | None = None) -> list[dict]:
    rewrites_dir = Path(rewrites_dir or REWRITES_DIR)
    out = []
    if not rewrites_dir.exists():
        return out
    for rp in sorted(rewrites_dir.glob("*/*.request.json")):
        rid = rp.name[:-len(".request.json")]
        if (rp.parent / f"{rid}.done.json").exists():
            continue
        try:
            req = json.loads(rp.read_text())
        except Exception:  # noqa: BLE001
            continue
        if req.get("schema") != SCHEMA or req.get("id") != rid:
            continue
        req["_path"] = str(rp)
        out.append(req)
    return out


def write_index(rewrites_dir: Path | None = None) -> Path | None:
    rewrites_dir = Path(rewrites_dir or REWRITES_DIR)
    try:
        # ONE entry per story, the newest. Every run that holds a story
        # files it again, so on 2026-09-30 the index listed 681 requests
        # for 98 stories — a writer working down it answered the same story
        # nine times and never reached the rest. Older copies stay on disk
        # (the claim step still decides any that get answered).
        newest: dict = {}
        for r in open_requests(rewrites_dir):
            if str(r.get("filed")) >= str(newest.get(r["slug"], {}).get("filed", "")):
                newest[r["slug"]] = r
        reqs = sorted(newest.values(), key=lambda r: str(r.get("filed")), reverse=True)
        idx = {"schema": "shorts-rewrite-index/v1", "updated": _now(),
               "open": [{"id": r["id"], "slug": r["slug"], "filed": r.get("filed"),
                         "why": (r.get("reasons") or [])[:3],
                         "request": _rel(r["_path"]),
                         "answer_path": r.get("answer_path")} for r in reqs],
               "how": "For each entry open `request` (raw), rewrite the words "
                      "as its rules say, commit `answer_path`. Never edit a "
                      "request. Numbers come only from the listed data."}
        rewrites_dir.mkdir(parents=True, exist_ok=True)
        ip = rewrites_dir / "OPEN.json"
        ip.write_text(json.dumps(idx, indent=1, ensure_ascii=False) + "\n")
        try:
            from shared import exchange_index as _xi
            _xi.refresh(rewrites_dir.parent)
        except Exception:  # noqa: BLE001 — a stale roll-up, never a failure
            pass
        return ip
    except Exception as e:  # noqa: BLE001
        print(f"[rewrites] index not written: {e}", flush=True)
        return None


def settle(req: dict, outcome: dict) -> Path:
    dp = Path(req["_path"]).parent / f"{req['id']}.done.json"
    rec = {"id": req["id"], "slug": req.get("slug"), "settled": _now(), **outcome}
    dp.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    write_index(dp.parent.parent)
    return dp


def file_request(sc: dict, reasons: list[str], *, judge: dict | None = None,
                 prior_rejection: list[str] | None = None,
                 rewrites_dir: Path | None = None) -> str | None:
    """File the ask for one story. Idempotent on the story's CURRENT words:
    the same words held again is the same request; changed words (a rewrite
    that got held again) supersede the old open request."""
    try:
        rewrites_dir = Path(rewrites_dir or REWRITES_DIR)
        base = request_id(sc)
        slug = sc.get("slug")
        # ROUNDS. The same words asked again is the same request (idempotent);
        # but a request that was settled — a refused answer — must be asked
        # again under a new id, or the refusal would end the conversation.
        settled = {p.name[:-len(".done.json")] for p in rewrites_dir.glob("*/*.done.json")}
        rid, n = base, 0
        while rid in settled:
            n += 1
            rid = f"{base}_r{n}"
        for old in open_requests(rewrites_dir):
            if old.get("slug") != slug:
                continue
            if (old["id"] == rid or old["id"] == base
                    or old["id"].startswith(base + "_r")):
                # same words, still open: the same ask -- carrying the
                # reasons the run gave TODAY, not the ones it gave when
                # the file was written
                refresh(old, reasons, judge=judge, prior_rejection=prior_rejection)
                return old["id"]
            settle(old, {"decision": "superseded", "by": rid})
        day = rewrites_dir / _today()
        day.mkdir(parents=True, exist_ok=True)
        rp = day / f"{rid}.request.json"
        if rp.exists():
            return rid
        segs = []
        for i, seg in enumerate(sc.get("segments") or []):
            segs.append({"index": i, "topic": seg.get("topic") or "",
                         "say": seg.get("say") or "", "role": seg.get("role") or "",
                         "data": _dataset(seg)})
        req = {
            "schema": SCHEMA, "id": rid, "filed": _now(), "status": "open",
            "channel": "explainer", "slug": slug,
            "current": words_of(sc),
            "segments": segs,
            "held_for": reasons,
            "reasons": reasons,
            "judge": judge,
            "prior_rejection": prior_rejection or [],
            "rules": RULES,
            "answer_path": f"exchange/rewrites/{_today()}/{rid}.answer.json",
            "answer_schema": ANSWER_SCHEMA,
            "how_to_answer": (
                "Rewrite the WORDS so this story clears every rule above and "
                "answers every reason in `held_for`. Same number of segments, "
                "same order. Use ONLY numbers you can derive from each "
                "segment's `data.points` (or a year that appears as a label). "
                "If `judge` is present, its `problems`/`fixes` are what the "
                "video editor saw on the RENDERED video — shorter topics and "
                "one clear number per line are what fix 'unreadable' and "
                "'text on text'. Write answer_path as one JSON object matching "
                "answer_schema, request_id and slug copied, and commit it. Do "
                "not touch the request."),
        }
        rp.write_text(json.dumps(req, indent=1, ensure_ascii=False) + "\n")
        print(f"[rewrites] request filed: {_rel(rp)} "
              f"({len(reasons)} reason(s))", flush=True)
        write_index(rewrites_dir)
        return rid
    except Exception as e:  # noqa: BLE001
        print(f"[rewrites] could not file for {sc.get('slug')}: {type(e).__name__}: {e}",
              flush=True)
        return None


def last_block(slug: str, ledger: Path | None = None) -> dict | None:
    """The judge's LAST verdict for a slug if it was a block: its one-line,
    problems and fixes — what a re-author needs to know."""
    ledger = ledger or (REPO / "state" / "showrunner_verdicts.jsonl")
    if not ledger.exists():
        return None
    found = None
    for line in ledger.read_text().splitlines():
        try:
            v = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if v.get("slug") == slug:
            found = v
    if not found or str(found.get("verdict")).lower() != "block":
        return None
    return {"ts": found.get("ts"), "score": found.get("score"),
            "one_line": found.get("one_line"),
            "problems": (found.get("problems") or [])[:8],
            "fixes": (found.get("fixes") or [])[:8]}


def refresh(req: dict, reasons: list[str], *, judge: dict | None = None,
            prior_rejection: list[str] | None = None) -> bool:
    """Bring an OPEN request up to date with the run that held its story
    again: today's reasons, the judge's words, the current rules. The id
    and the words stay (an answer in flight is still for this story), so
    nothing about claiming changes. Returns True if the file changed.

    Until 2026-11-23 the same words held again returned the old id and
    left the file alone, so a story the gate held on 10-18 for a rule
    retired on 11-17 was still asking ChatGPT to satisfy that rule on
    11-23 -- 48 of 144 open requests carried reasons the run no longer
    gave, and a writer working the index fixed the wrong thing."""
    reasons = [str(r) for r in reasons or []]
    new: dict = {"held_for": reasons, "reasons": reasons, "rules": RULES,
                 "answer_schema": ANSWER_SCHEMA}
    if judge is not None:
        new["judge"] = judge
    if prior_rejection:
        new["prior_rejection"] = list(prior_rejection)
    if all(req.get(k) == v for k, v in new.items()):
        return False
    path = Path(req["_path"])
    on_disk = json.loads(path.read_text())
    on_disk.update(new)
    on_disk["refiled"] = _now()
    path.write_text(json.dumps(on_disk, indent=1, ensure_ascii=False) + "\n")
    req.update(new)
    req["refiled"] = on_disk["refiled"]
    print(f"[rewrites] request refreshed: {_rel(path)} "
          f"({len(reasons)} reason(s) as of today)", flush=True)
    write_index(path.parent.parent)
    return True


def retire(slug: str, reasons: list[str], *,
           rewrites_dir: Path | None = None) -> list[str]:
    """Close every open request for a story no rewrite can post -- the
    data under it is not a real source. Settled `unpostable` with the
    data reasons, so a later run whose data IS fixed asks again under a
    new round id. Returns the ids closed."""
    closed = []
    for old in open_requests(rewrites_dir):
        if old.get("slug") == slug:
            settle(old, {"decision": "unpostable", "problems": list(reasons)})
            closed.append(old["id"])
    if closed:
        print(f"[rewrites] {slug}: {len(closed)} request(s) retired -- "
              f"no rewrite can post it: {reasons[0]}", flush=True)
    return closed


#: The one `not_current` reason besides the narration that a rewrite CAN
#: answer (`shared.currency.problems`); the render-standard ones are not words.
_HOOK_FLOOR = "the hook is under the floor"


def file_for_run(results: list[dict], stories: dict, *,
                 rewrites_dir: Path | None = None) -> list[str]:
    """After a posting run: file one request per story the run held for
    word reasons (editorial, a narration readout, a hook under the floor)
    or the judge blocked; retire the asks for a story held for its data.
    Returns the ids filed."""
    filed = []
    for r in results or []:
        slug = r.get("slug")
        sc = stories.get(slug)
        if not sc or r.get("ok"):
            continue
        err = r.get("error")
        all_reasons = [str(x) for x in (r.get("reasons") or [])]
        dead = unpostable(all_reasons)
        if dead:
            # data holds are not a words job -- and an open ask for the
            # story is a words job nobody should be doing
            retire(slug, dead, rewrites_dir=rewrites_dir)
            continue
        if err in ("editorial_hold", "story_hold"):
            reasons = words_only(all_reasons)
            if not reasons:
                continue
            rid = file_request(sc, reasons, rewrites_dir=rewrites_dir)
        elif err == "not_current":
            # The narration is words (operator, 2026-10-09: "this whole
            # thing is just us reading off numbers"); so is the hook. The
            # look and the standard are the renderer's, not the writer's.
            reasons = narration_holds(sc) + [
                "hook: " + x for x in all_reasons if x.startswith(_HOOK_FLOOR)]
            if not reasons:
                continue
            rid = file_request(sc, reasons + word_holds(sc), rewrites_dir=rewrites_dir)
        elif err == "showrunner_block":
            judge = last_block(slug)
            reasons = ["judge: " + str((judge or {}).get("one_line") or
                                       "blocked by the showrunner")]
            rid = file_request(sc, reasons + word_holds(sc), judge=judge,
                               rewrites_dir=rewrites_dir)
        elif err == "duplicate_hold":
            # THE PACKAGING REPEATS. A title too close to a posted video is
            # a words job -- the run has said "Retitle it and it ships"
            # since 10-02 and nobody was ever asked. The brain reading the
            # STORY as a posted one is not: a new title over the same
            # comparison is a repeat, so its asks are retired. A slug
            # another run posted meanwhile is a race, not a hold.
            dup = str(r.get("duplicate_of") or "a video already up")
            how = r.get("repeat")
            if how == "story":
                retire(slug, [f"{REPEAT_PREFIX} the same story as {dup!r} is "
                              f"already up on a data channel; no retitle "
                              f"can post it"], rewrites_dir=rewrites_dir)
                continue
            if how != "title":
                continue
            rid = file_request(sc, [repeat_reason(dup)] + word_holds(sc),
                               rewrites_dir=rewrites_dir)
        else:
            continue
        if rid:
            filed.append(rid)
    return filed


def sweep(stories: dict, posted: set, *, rewrites_dir: Path | None = None) -> list[str]:
    """File for every un-posted story the deterministic gate holds for word
    reasons — the backlog, so the first round has the whole queue."""
    filed = []
    for slug, sc in stories.items():
        if slug in posted:
            continue
        gate = gate_reasons(sc)
        dead = unpostable(gate)
        if dead:
            retire(slug, dead, rewrites_dir=rewrites_dir)
            continue
        reasons = words_only(gate) + narration_holds(sc)
        if reasons:
            rid = file_request(sc, reasons, rewrites_dir=rewrites_dir)
            if rid:
                filed.append(rid)
    return filed


# ---------------------------------------------------------------------------
# Claiming: CODE decides
# ---------------------------------------------------------------------------

def answer_for(req: dict) -> tuple[dict | None, str]:
    ap = Path(req["_path"]).parent / f"{req['id']}.answer.json"
    if not ap.exists():
        return None, "no answer yet"
    try:
        a = json.loads(ap.read_text())
    except Exception as e:  # noqa: BLE001
        return None, f"answer unreadable: {e}"
    if not isinstance(a, dict):
        return None, "answer is not an object"
    if str(a.get("request_id")) != req["id"]:
        return None, f"answer names request {a.get('request_id')!r}, not {req['id']!r}"
    if str(a.get("slug")) != str(req.get("slug")):
        return None, "answer names a different slug"
    return a, "ok"


def _quantities_ok(text: str, allowed: set, original: str) -> list[str]:
    """Every quantity a listener hears in `text` must be near something in
    `allowed` or already spoken in `original`. Returns the offenders."""
    from shared import beat_match as bm
    prior = set(abs(q) for q in bm.spoken_quantities(original))
    bad = []
    for q in bm.spoken_quantities(text):
        q = abs(q)
        if any(bm._near(q, p) for p in prior):
            continue
        if any(bm._near(q, a) for a in allowed):
            continue
        bad.append(q)
    return bad


def _allowed_for(seg: dict) -> set:
    from shared import beat_match as bm
    d = _dataset(seg) or {}
    vals = [float(p["value"]) for p in d.get("points") or []
            if p.get("value") is not None]
    out = set(abs(v) for v in bm.sayable(vals, d.get("unit", ""))) if vals else set()
    for p in d.get("points") or []:
        for tok in re.findall(r"\d{4}", f"{p.get('label')} {p.get('period', '')}"):
            out.add(float(tok))            # a year is a label, not a quantity
    return out


_SENT = re.compile(r"(?<=[.!?])\s+|^")
_CAP = re.compile(r"\b([A-Z][a-z][A-Za-z'\-]*)\b")


def _entities_ok(new_text: str, original: str, label_words: set) -> list[str]:
    """Capitalised words INSIDE a sentence that neither the original words
    nor the data's own labels contain — a country, a company, a person the
    writer brought from outside. A sentence's first word is never counted
    (a rewrite is allowed to open with a new word), which is why the title
    (Title Case throughout) is not checked here at all."""
    from shared import punchup_guard as pg
    pool = pg._all_words(original) | label_words
    common = {c.lower() for c in getattr(pg, "_COMMON_CAPS", ())}
    out = set()
    for sent in _SENT.split(new_text or ""):
        words = sent.split()
        for tok in words[1:]:
            m = _CAP.match(tok)
            if not m:
                continue
            w = m.group(1)
            if w.lower() in pool or w.lower() in common:
                continue
            out.add(w)
    return sorted(out)


def _forms(w: str) -> set:
    """The word and the roots it could have been inflected from, so a label's
    "Collapse" meets the narration's "collapsed" and "Losses" meets "loss"."""
    w = w.lower().removesuffix("'s")
    out = {w}
    for suf in ("ing", "ed", "es", "s", "d"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            root = w[: -len(suf)]
            out |= {root, root + "e"}
    return out


def _topic_entities(topic: str, original: str, label_words: set,
                    plain_text: str) -> list[str]:
    """A topic is an ON-SCREEN LABEL, written in Title Case, so a capital
    there says nothing; checked as part of the beat's sentence every word of
    "Bats Collapse Versus Farms" read as a newly named thing, and on
    2026-10-12 that refused a third of the morning's retells. A label word
    is a NAME only if the writing never uses it as an ordinary word: a word
    (or its stem) that the old words or the new narration use in lower case
    is a common word. "France" is never written "france", so it still
    counts."""
    plain: set = set()
    for w in re.findall(r"\b[a-z][a-z'\-]*", plain_text or ""):
        plain |= _forms(w)
    cand = _entities_ok("x " + (topic or ""), original, label_words)
    return [w for w in cand if not (_forms(w) & plain)]


def validate(sc: dict, ans: dict, *,
             narration: bool = False,
             posted_titles: list | None = None) -> tuple[dict | None, list[str]]:
    """(candidate story, problems). A candidate is returned only with no
    problems; it is `sc` with the words replaced, and it has PASSED the same
    deterministic gate the run applies. With `narration`, it has also
    cleared `shared.narration.problems` -- the rules every request carries
    say one number a beat, and an answer that is a readout would only be
    held `not_current` by the next run. The brain's own retell and tighten
    call this without it: they check the narration themselves, and tighten
    runs before the retell has had its turn. With `posted_titles`, the
    candidate's TITLE must not repeat one of them by the run's own
    near-duplicate matcher -- a retitle asked for because the packaging
    repeated, that still repeats, would only be held `duplicate_hold`
    again (the claim passes the run's own corpus, `posted_titles()`)."""
    import copy
    problems: list[str] = []
    segs = sc.get("segments") or []
    new_segs = ans.get("segments")
    if not isinstance(new_segs, list) or len(new_segs) != len(segs):
        return None, [f"{len(new_segs) if isinstance(new_segs, list) else 0} "
                      f"segments for {len(segs)}"]
    for f in ("title", "hook", "closing"):
        if not str(ans.get(f) or "").strip():
            problems.append(f"missing {f}")
    if problems:
        return None, problems

    label_words: set = set()
    for seg in segs:
        d = _dataset(seg) or {}
        for p in d.get("points") or []:
            label_words |= {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]+",
                                                          str(p.get("label") or ""))}
        label_words |= {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'\-]+",
                                                      str(d.get("title") or ""))}
    orig_all = " ".join([sc.get("title") or "", sc.get("hook") or "",
                         sc.get("closing") or ""]
                        + [(s.get("say") or "") + " " + (s.get("topic") or "")
                           for s in segs])
    allowed_all: set = set()
    for i, (seg, new) in enumerate(zip(segs, new_segs)):
        if not isinstance(new, dict):
            problems.append(f"segment {i}: not an object")
            continue
        say = str(new.get("say") or "").strip()
        topic = str(new.get("topic") or seg.get("topic") or "").strip()
        if not say:
            problems.append(f"segment {i}: empty say")
            continue
        if len(say.split()) > MAX_SAY_WORDS:
            problems.append(f"segment {i}: say is {len(say.split())} words (max {MAX_SAY_WORDS})")
        if len(topic.split()) > MAX_TOPIC_WORDS:
            problems.append(f"segment {i}: topic {topic!r} is {len(topic.split())} words (max {MAX_TOPIC_WORDS})")
        allowed = _allowed_for(seg)
        allowed_all |= allowed
        bad = _quantities_ok(say, allowed, seg.get("say") or "")
        if bad:
            problems.append(f"segment {i}: number(s) not derivable from this beat's data: "
                            + ", ".join(f"{b:,.6g}" for b in bad[:4]))
        plain = " ".join([orig_all, str(ans.get("closing") or "")]
                         + [str((x or {}).get("say") or "") for x in new_segs
                            if isinstance(x, dict)])
        ents = sorted(set(_entities_ok(say, orig_all, label_words))
                      | set(_topic_entities(topic, orig_all, label_words, plain)))
        if ents:
            problems.append(f"segment {i}: new named entity not in the data: " + ", ".join(ents[:4]))
    for f in ("title", "hook", "closing"):
        txt = str(ans.get(f) or "")
        bad = _quantities_ok(txt, allowed_all, orig_all)
        if bad:
            problems.append(f"{f}: number(s) not derivable from any beat's data: "
                            + ", ".join(f"{b:,.6g}" for b in bad[:4]))
        if f != "title":
            ents = _entities_ok(txt, orig_all, label_words)
            if ents:
                problems.append(f"{f}: new named entity not in the data: " + ", ".join(ents[:4]))
    if problems:
        return None, problems

    cand = copy.deepcopy(sc)
    for f in ("title", "hook", "closing", "question"):
        if ans.get(f):
            cand[f] = str(ans[f]).strip()
    for seg, new in zip(cand["segments"], new_segs):
        seg["say"] = str(new.get("say")).strip()
        if new.get("topic"):
            seg["topic"] = str(new["topic"]).strip()
    still = word_holds(cand)
    if narration:
        still += narration_holds(cand)
    if posted_titles is not None:
        hit = repeats(cand.get("title") or "", posted_titles)
        if hit:
            still.append(f"{REPEAT_PREFIX} the title is still too close to a "
                         f"video already up: {hit!r}")
    if still:
        return None, ["still held by the gate: " + r for r in still]
    return cand, []


def apply(cfg: dict, cand: dict, by: str = WORDS_BY) -> bool:
    """Put the validated words into the config (in memory) and drop the
    slug's old scene plan — a rewritten story is a new story to plan."""
    for i, s in enumerate(cfg.get("stories") or []):
        if s.get("slug") == cand.get("slug"):
            cand = dict(cand)
            cand["words_by"] = by
            cand["rewritten_at"] = _now()
            cfg["stories"][i] = cand
            try:
                pf = PLANS_DIR / f"{cand['slug']}.json"
                if pf.exists():
                    pf.unlink()
            except OSError:
                pass
            return True
    return False


def claim_all(config_path: Path | None = None, *, rewrites_dir: Path | None = None,
              dry_run: bool = False, log_path: Path | None = None) -> dict:
    """Every open request with an answer: validate, apply, settle. A refusal
    is settled with its reasons and a fresh request is filed carrying them.
    An answer's title is checked against the run's own posted corpus
    (`posted_titles(log_path)`) so a retitle that still repeats is refused
    here, with the video named, instead of being held by the next run."""
    config_path = Path(config_path or REPO / "data_learning" / "niche.config.json")
    report = {"applied": [], "rejected": [], "open": 0}
    reqs = open_requests(rewrites_dir)
    if not reqs:
        return report
    cfg = json.loads(config_path.read_text())
    stories = {s.get("slug"): s for s in cfg.get("stories") or []}
    titles = posted_titles(log_path)
    changed = False
    for req in reqs:
        ans, why = answer_for(req)
        if ans is None:
            if why != "no answer yet":
                settle(req, {"decision": "rejected", "problems": [why]})
                report["rejected"].append({"id": req["id"], "problems": [why]})
            else:
                report["open"] += 1
            continue
        sc = stories.get(req.get("slug"))
        if not sc:
            settle(req, {"decision": "rejected", "problems": ["story no longer in the queue"]})
            report["rejected"].append({"id": req["id"], "problems": ["gone"]})
            continue
        base = request_id(sc)
        if not (req["id"] == base or req["id"].startswith(base + "_r")):
            settle(req, {"decision": "superseded", "problems": ["the story's words changed since this was filed"]})
            continue
        cand, problems = validate(sc, ans, narration=True, posted_titles=titles)
        if problems:
            settle(req, {"decision": "rejected", "problems": problems})
            report["rejected"].append({"id": req["id"], "problems": problems})
            print(f"[rewrites] REJECT {req['slug']}: {problems[0]}", flush=True)
            # ask again, with the reasons the writer needs
            file_request(sc, (req.get("held_for") or []), judge=req.get("judge"),
                         prior_rejection=problems, rewrites_dir=rewrites_dir)
            continue
        by = words_by(ans)
        if apply(cfg, cand, by):
            changed = True
            settle(req, {"decision": "applied", "words_by": by})
            report["applied"].append(req["slug"])
            print(f"[rewrites] APPLIED {by} words to {req['slug']}", flush=True)
    if changed and not dry_run:
        tmp = config_path.with_suffix(".json.tmp")
        # in the file's own indent, or one rewrite is a 29,000-line diff
        from shared.fsutil import file_indent
        tmp.write_text(json.dumps(cfg, indent=file_indent(config_path),
                                  ensure_ascii=False) + "\n")
        os.replace(tmp, config_path)
    return report
