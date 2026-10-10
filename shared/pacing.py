"""PACE — how many words a beat may carry, and how fast they are spoken.

Operator, 2026-10-05: *"15 seconds per beat is far too long."* Measured on
the posted explainer videos: 26 words a beat (the forge asked for "~22"
and nothing held the writer to it), spoken by Speechify at 130 words a
minute including the breaths, is 12 seconds of one picture before the
hook and closing are counted. The viewer has left.

The budget is channel POLICY, so it lives in `config/channel_registry.json`
(`explainer.formats.data_story.pacing`) and nowhere else; this module reads
it and gives every writer and every gate the same numbers:

  * the forge writes new stories to it and rejects the brain's draft when a
    line runs over;
  * the takeover brief and the rewrite mailbox state it to ChatGPT;
  * the editorial gate HOLDS a story over it (a `pace:` word reason, so the
    mailbox asks for a rewrite instead of parking it);
  * `tighten()` has the brain compress a queued story BEFORE the gate sees
    it, validated by the mailbox's own rules (numbers derivable, no new
    entity, the gate still passes) and persisted once;
  * the renderer plays the narration at `tempo` and records every beat's
    seconds in the sidecar, so the posted log can say what the pace WAS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

#: Only for a registry that predates the key (fixtures, an old snapshot). The
#: live registry carries it — tests/test_fifteen_seconds_a_beat_is_too_long.py
#: checks — so production reads the registry's numbers, never these.
IF_UNSET = {"beat_max_s": 8, "say_words": 24, "hook_words": 14,
            "closing_words": 18, "question_words": 8, "tempo": 1.12,
            "beat_min_words": 15}

WORDS_BY = "brain-tighten"


def budget(channel: str = "explainer", fmt: str = "data_story") -> dict:
    """The channel's pacing policy, from the registry."""
    out = dict(IF_UNSET)
    try:
        from shared import channel_registry as reg
        r = reg.load()
        pac = (((r.get("channels") or {}).get(channel) or {}).get("formats") or {}
               ).get(fmt, {}).get("pacing") or {}
        for k in IF_UNSET:
            if pac.get(k) is not None:
                out[k] = type(IF_UNSET[k])(pac[k])
    except Exception:  # noqa: BLE001 — a missing registry fails the CHANNEL closed elsewhere
        pass
    return out


def words(text) -> int:
    return len(str(text or "").split())


def problems(sc: dict, b: dict | None = None) -> list[str]:
    """Every line of `sc` over the budget, as the gate's `pace:` reasons."""
    b = b or budget()
    out = []
    h = words(sc.get("hook"))
    if h > b["hook_words"]:
        out.append(f"hook is {h} words (max {b['hook_words']})")
    for i, seg in enumerate(sc.get("segments") or []):
        n = words(seg.get("say"))
        if n > b["say_words"]:
            out.append(f"beat {i + 1} says {n} words (max {b['say_words']}) — "
                       f"the number and what it means, nothing else")
    c = words(sc.get("closing"))
    if c > b["closing_words"]:
        out.append(f"closing is {c} words (max {b['closing_words']})")
    q = words(sc.get("question"))
    if q > b["question_words"]:
        out.append(f"question is {q} words (max {b['question_words']})")
    return out


def short(sc: dict, b: dict | None = None) -> bool:
    """The beats average under `beat_min_words`: a fact read out with no
    "so what" (operator, 2026-10-10, of a 16-second video: "We say one fun
    fact, and then that's it"). Never a hold; the retell makes it longer."""
    b = b or budget()
    segs = sc.get("segments") or []
    return bool(segs) and (sum(words(s.get("say")) for s in segs)
                           < len(segs) * b["beat_min_words"])


def rule(b: dict | None = None) -> str:
    """The budget as one sentence for a writer's hard rules."""
    b = b or budget()
    return (f"PACE: each SAY is at most two short spoken sentences and "
            f"{b['say_words']} words: the beat's number, then what it MEANS "
            f"(why it is surprising, what it caused, why the viewer should "
            f"care), nothing else; the HOOK at most {b['hook_words']} words, "
            f"the CLOSING at most {b['closing_words']} words and it says why "
            f"this matters to the viewer, the QUESTION at most "
            f"{b['question_words']}. A beat is on screen about "
            f"{b['beat_max_s']} seconds; a longer line is refused.")


# ------------------------------------------------------------------ tighten

_PROMPT = """You tighten the narration of a YouTube Shorts data explainer. \
The numbers are sourced and correct; you may not change, drop, round or \
invent any number, year, percent, country, company or person — a guard \
checks every quantity against the data and refuses the whole rewrite if you \
do. You are cutting WORDS, not facts.

{rule}

The gate's other word rules, which the rewrite must also clear (a story is \
often held for one of these at the same time):
{rules}

Keep the title exactly. Keep each beat's headline number and what it means. \
Prefer the plain verb; drop the throat-clearing ("That means", "In other \
words", "It's worth noting").

TITLE: {title}
HOOK ({hw} words): {hook}
{beats}
CLOSING ({cw} words): {closing}
QUESTION ({qw} words): {question}

Return STRICT JSON: {{"hook": str, "closing": str, "question": str, \
"segments": [{{"topic": str, "say": str}}, ...]}} with exactly {n} segments \
in the same order. A "topic" is printed on the video: at most {tw} words — \
keep the beat's when it fits, shorten it when it does not."""


def _prompt(sc: dict, b: dict, note: str | None = None) -> str:
    segs = sc.get("segments") or []
    beats = "\n".join(
        f"BEAT {i + 1} topic={seg.get('topic') or ''!r} ({words(seg.get('say'))} "
        f"words): {seg.get('say') or ''}" for i, seg in enumerate(segs))
    from shared import rewrite_mailbox as rw
    rules = "\n".join(f"- {r}" for r in rw.RULES if not r.startswith("PACE:"))
    p = _PROMPT.format(rule=rule(b), rules=rules, title=sc.get("title") or "",
                       hw=words(sc.get("hook")), hook=sc.get("hook") or "",
                       beats=beats, cw=words(sc.get("closing")),
                       closing=sc.get("closing") or "",
                       qw=words(sc.get("question")),
                       question=sc.get("question") or "", n=len(segs),
                       tw=_topic_words())
    if note:
        p += f"\n\nYour previous rewrite was REFUSED — fix exactly this:\n{note}"
    return p


def _topic_words() -> int:
    from shared import rewrite_mailbox as rw
    return int(rw.MAX_TOPIC_WORDS)


def _default_brain(prompt: str):
    """The headless Claude first; the text chain when the CLI is absent. The
    answer is validated mechanically, so a weaker writer is safe here."""
    try:
        from data_learning import scene_author as sa
        out = sa.ask_brain(prompt, model="sonnet", timeout=120)
        if out:
            return out
    except Exception:  # noqa: BLE001
        pass
    try:
        from shared.script_generator import _call_llm
        return _call_llm("You tighten narration. Return STRICT JSON only.", prompt)
    except Exception:  # noqa: BLE001
        return None


def _parse(raw) -> dict | None:
    m = re.search(r"\{.*\}", str(raw or ""), re.S)
    if not m:
        return None
    try:
        ans = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
    return ans if isinstance(ans, dict) else None


def tighten(sc: dict, *, config_path: Path | None = None, brain=None,
            log=print, tries: int = 2) -> dict:
    """Compress a story that runs over the budget, in place and on disk.

    Returns {"changed": bool, "reasons": [...]} — `reasons` is why the last
    attempt was refused when nothing changed. A story already inside the
    budget is returned untouched with no brain call."""
    b = budget()
    over = problems(sc, b)
    if not over:
        return {"changed": False, "reasons": []}
    from shared import rewrite_mailbox as rw
    brain = brain or _default_brain
    note = None
    reasons: list[str] = over
    for attempt in range(tries):
        raw = brain(_prompt(sc, b, note))
        if not raw:
            reasons = ["no brain answered"]
            log(f"[pace] {sc.get('slug')}: {'; '.join(over[:2])} — no brain to tighten it")
            break
        ans = _parse(raw)
        if not ans:
            reasons = ["the answer was not JSON"]
            note = "return STRICT JSON only"
            continue
        ans["title"] = sc.get("title")
        segs = sc.get("segments") or []
        new = ans.get("segments") or []
        for i, seg in enumerate(new if isinstance(new, list) else []):
            if isinstance(seg, dict) and not seg.get("topic") and i < len(segs):
                seg["topic"] = segs[i].get("topic")
        for k in ("hook", "closing", "question"):
            if not str(ans.get(k) or "").strip():
                ans[k] = sc.get(k)
        cand, probs = rw.validate(sc, ans)
        if cand is None:
            reasons = probs
            note = "; ".join(probs)[:400]
            log(f"[pace] {sc.get('slug')}: rewrite {attempt + 1} refused: {note[:160]}")
            continue
        _apply(sc, cand, config_path, log)
        return {"changed": True, "reasons": []}
    return {"changed": False, "reasons": reasons}


def _apply(sc: dict, cand: dict, config_path, log) -> None:
    from shared import rewrite_mailbox as rw
    for k in ("hook", "closing", "question"):
        if cand.get(k):
            sc[k] = cand[k]
    for a, c in zip(sc.get("segments") or [], cand.get("segments") or []):
        a["say"] = c.get("say")
        if c.get("topic"):
            a["topic"] = c["topic"]
    sc["words_by"] = WORDS_BY
    path = Path(config_path or REPO / "data_learning" / "niche.config.json")
    try:
        cfg = json.loads(path.read_text())
        if rw.apply(cfg, cand, by=WORDS_BY):
            from shared.fsutil import write_json_if_changed
            write_json_if_changed(path, cfg, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001 — the in-memory story is tightened either way
        log(f"[pace] {sc.get('slug')}: persist skipped: {e}")
    log(f"[pace] {sc.get('slug')}: tightened to "
        f"{[words(s.get('say')) for s in sc.get('segments') or []]} words a beat")
