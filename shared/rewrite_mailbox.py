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
MAX_SAY_WORDS = 40
WORDS_BY = "chatgpt-rewrite"

#: The gate's four word rules, in the words ChatGPT is given. These restate
#: `scripts/editorial_gate.py` — the CODE there is what decides, this text
#: only tells the writer what it will be measured against.
RULES = [
    "TITLE or HOOK must contain a consequential NUMBER from the data below "
    "(the gate refuses a title+hook with no digit in either).",
    "TITLE must be a PREMISE, not a searchable noun phrase: more than five "
    "words, or a number, or a question mark, or a tension word. 'Oldest "
    "Written Languages' is the failure; 'Why 3 of the 5 Oldest Scripts Are "
    "Still Unreadable' is the shape.",
    "Every segment's TOPIC (a 2-4 word on-screen label) must share at least "
    "one real word with the TITLE — the gate checks a keyword bridge from "
    "each segment to the headline. Rename the topic, or write the title so "
    "it names what the segments are about.",
    "Every NUMBER you say in a segment's SAY must be one that segment's data "
    "can show: a listed value, a difference between two of them, a percent "
    "change, a share of the total, or the same value in a bigger unit. A "
    "number from nowhere is refused — a guard derives every spoken quantity "
    "from the listed points.",
    "Keep every number that is already correct. Do not add a country, "
    "company or person the data does not name.",
    "Each SAY is one spoken sentence or two, at most 40 words, and says its "
    "beat's headline number out loud.",
    "TOPIC labels are printed on the video: at most 4 words, no clause.",
]

ANSWER_SCHEMA = {
    "schema": ANSWER_SCHEMA_NAME,
    "request_id": "<copied from the request>",
    "slug": "<copied>",
    "by": "chatgpt",
    "written_at": "<ISO-8601 UTC>",
    "title": "<the premise>",
    "hook": "<one line that stops the thumb, with a number>",
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

_WORD_PREFIX = ("premise:", "thesis:", "beats:")


def word_holds(sc: dict) -> list[str]:
    """The deterministic gate's reasons that a REWRITE can fix. Empty when
    the story passes, or when it is held only for data reasons (a source
    that is not real is not a words problem, and no rewrite is asked)."""
    from scripts import editorial_gate as eg
    v = eg.pre_render_verdict(sc, use_llm=False)
    if v["ok"]:
        return []
    return [r for r in v["reasons"] if r.startswith(_WORD_PREFIX)
            and not r.startswith("beats (noted)")]


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
        reqs = open_requests(rewrites_dir)
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
            if old.get("slug") == slug and old["id"] != rid:
                if old["id"] == base or old["id"].startswith(base + "_r"):
                    return old["id"]          # same words, still open: same ask
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


def file_for_run(results: list[dict], stories: dict, *,
                 rewrites_dir: Path | None = None) -> list[str]:
    """After a posting run: file one request per story the run held for
    word reasons (editorial) or the judge blocked. Returns the ids filed."""
    filed = []
    for r in results or []:
        slug = r.get("slug")
        sc = stories.get(slug)
        if not sc or r.get("ok"):
            continue
        err = r.get("error")
        if err == "editorial_hold":
            reasons = [x for x in (r.get("reasons") or [])
                       if str(x).startswith(_WORD_PREFIX)
                       and not str(x).startswith("beats (noted)")]
            if not reasons:
                continue                      # data holds are not a words job
            rid = file_request(sc, reasons, rewrites_dir=rewrites_dir)
        elif err == "showrunner_block":
            judge = last_block(slug)
            reasons = ["judge: " + str((judge or {}).get("one_line") or
                                       "blocked by the showrunner")]
            rid = file_request(sc, reasons + word_holds(sc), judge=judge,
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
        reasons = word_holds(sc)
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


def validate(sc: dict, ans: dict) -> tuple[dict | None, list[str]]:
    """(candidate story, problems). A candidate is returned only with no
    problems; it is `sc` with the words replaced, and it has PASSED the same
    deterministic gate the run applies."""
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
        ents = _entities_ok(say + " " + topic, orig_all, label_words)
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
    if still:
        return None, ["still held by the gate: " + r for r in still]
    return cand, []


def apply(cfg: dict, cand: dict) -> bool:
    """Put the validated words into the config (in memory) and drop the
    slug's old scene plan — a rewritten story is a new story to plan."""
    for i, s in enumerate(cfg.get("stories") or []):
        if s.get("slug") == cand.get("slug"):
            cand = dict(cand)
            cand["words_by"] = WORDS_BY
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
              dry_run: bool = False) -> dict:
    """Every open request with an answer: validate, apply, settle. A refusal
    is settled with its reasons and a fresh request is filed carrying them."""
    config_path = Path(config_path or REPO / "data_learning" / "niche.config.json")
    report = {"applied": [], "rejected": [], "open": 0}
    reqs = open_requests(rewrites_dir)
    if not reqs:
        return report
    cfg = json.loads(config_path.read_text())
    stories = {s.get("slug"): s for s in cfg.get("stories") or []}
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
        cand, problems = validate(sc, ans)
        if problems:
            settle(req, {"decision": "rejected", "problems": problems})
            report["rejected"].append({"id": req["id"], "problems": problems})
            print(f"[rewrites] REJECT {req['slug']}: {problems[0]}", flush=True)
            # ask again, with the reasons the writer needs
            file_request(sc, (req.get("held_for") or []), judge=req.get("judge"),
                         prior_rejection=problems, rewrites_dir=rewrites_dir)
            continue
        if apply(cfg, cand):
            changed = True
            settle(req, {"decision": "applied", "words_by": WORDS_BY})
            report["applied"].append(req["slug"])
            print(f"[rewrites] APPLIED ChatGPT words to {req['slug']}", flush=True)
    if changed and not dry_run:
        tmp = config_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp, config_path)
    return report
