"""STORY FIRST — the idea brief before the words, the scorecard before the render.

Operator, 2026-11-17: *"our scripts suck ... fix all of this stuff times 10
... ChatGPT made some thing about how we should improve our scripts, and
it's in the GitHub, so go find that and do it."* The thing is
`data_learning/STORY_FIRST_SCRIPT_PLAYBOOK.md`; this module is its §13 for
the illustrated explainer.

Four things, each small, each one brain call at most:

  * `pitch(dss)` — the §3 IDEA BRIEF, written before a word of narration:
    what a viewer believes, what the data says instead, why it matters, the
    one picture that proves it, the promise, the payoff, and FIVE genuinely
    different hook concepts (personal, reversal, scale, mystery,
    consequence). The brain picks the best TRUTHFUL one. A pitch that is
    only "here are some statistics about X" comes back `weak` and the
    dataset is refused before any words are written.
  * `scorecard(story)` — the §11 100-point card, scored BLIND: the judge
    sees the premise, the read-aloud script and the scene, never a self-
    score or the author's brief. Exact integers per criterion, clamped to
    the criterion's points; anything else is no card at all.
  * `decide(card)` — pure. The bands are channel POLICY and live in the
    registry (`explainer.formats.data_story.story_gate`), read by
    `gate_policy()`: at or over `pass_at` renders, `rewrite_at` up to it
    goes to the rewrite mailbox naming the weakest criterion, under that is
    re-conceived, and a fatal condition holds whatever the number.
  * `sidecar(story)` — the §7 EARS / EYES / EVIDENCE storyboard, one row
    per window, from what the story already holds. No brain.

The operator's rulings win where the playbook differs; the list is in the
PR that added this module and in docs/SYSTEM_AUDIT.md's story-first entry:
the hook is a tabloid THREAT with no number (`hook_doctrine`), one number a
beat (`narration.MAX_NUMBERS`), "the experts", words for the voice.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from shared.jsonreply import one_object  # noqa: E402
except ImportError:  # run as a script
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__))))
    from shared.jsonreply import one_object  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

#: §11, verbatim weights. The criteria ARE the playbook's; the bands that act
#: on the total are policy and live in the registry.
CRITERIA = {
    "premise": 15,       # one-sentence reason an ordinary viewer cares
    "hook": 20,          # first frame + spoken hook: legible, true, intriguing
    "arc": 20,           # each beat changes understanding; no slideshow
    "factual": 15,       # source-backed, units, denominators, dates
    "visual_proof": 15,  # the picture explains, not decorates; phone-sized
    "payoff": 10,        # the ending resolves the promise
    "voice": 5,          # a person could say it; no classroom filler
}
FATAL = ("invented_fact", "false_comparison", "missing_payoff",
         "unrenderable_visual", "confusing", "deceptive")

#: Only for a registry that predates the key (fixtures, an old snapshot).
#: tests/test_story_first.py holds the live registry to carrying it.
IF_UNSET = {"pass_at": 46, "rewrite_at": 40}

ANGLES = ("personal", "reversal", "scale", "mystery", "consequence")


def gate_policy(channel: str = "explainer", fmt: str = "data_story") -> dict:
    """The scorecard bands, from the registry."""
    out = dict(IF_UNSET)
    try:
        from shared import channel_registry as reg
        r = reg.load()
        g = ((((r.get("channels") or {}).get(channel) or {}).get("formats")
              or {}).get(fmt) or {}).get("story_gate") or {}
        for k in IF_UNSET:
            if isinstance(g.get(k), (int, float)) and not isinstance(g.get(k), bool):
                out[k] = g[k]
    except Exception:  # noqa: BLE001 — fixtures without a registry
        pass
    return out


def _llm(system: str, user: str) -> str:
    from shared.script_generator import _call_llm
    return _call_llm(system, user)


def _obj(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw or "", re.S)
    d = one_object(m.group(0)) if m else {}
    return d if isinstance(d, dict) else {}


# ---------------------------------------------------------------------------
# 1. The idea brief — before any words
# ---------------------------------------------------------------------------
PITCH_SYSTEM = (
    "You are the story editor of a YouTube Shorts channel that explains real "
    "data with an illustrated mascot. A dataset is an INGREDIENT, not an "
    "idea. Before anyone writes a word, you write the idea brief. Be honest: "
    "if the only pitch is 'here are some statistics about X', say so -- not "
    "every dataset deserves a video. Never invent a number or a fact the "
    "data does not hold.")

_PITCH_FIELDS = ("belief", "surprise", "stakes", "visual_proof", "promise",
                 "payoff")


def pitch_prompt(digest: str) -> str:
    return (
        f"DATA (every number the video may use comes from here):\n{digest}\n\n"
        "Write the idea brief:\n"
        "  belief: what an ordinary viewer assumes today\n"
        "  surprise: what this data says instead\n"
        "  stakes: why it matters to money, time, body, safety, family, "
        "wonder or how the world works\n"
        "  visual_proof: the ONE picture that makes it obvious with the "
        "sound off\n"
        "  promise: the question the video answers\n"
        "  payoff: what the viewer walks away realising\n"
        "  hooks: FIVE genuinely different spoken openings, one per angle "
        f"({', '.join(ANGLES)}) -- not five synonyms. Each names the subject "
        "plainly, says the threat or the twist, and has NO number (the video "
        "says the number; the hook says what it means). Under 14 words.\n"
        "  pick: the index of the hook with the best TRUE payoff and the most "
        "drawable picture -- not the biggest superlative\n"
        "  weak: true if this is only a pile of statistics with no surprise "
        "or stakes a stranger would stop for\n\n"
        "Return STRICT JSON: {\"belief\":..., \"surprise\":..., \"stakes\":"
        "..., \"visual_proof\":..., \"promise\":..., \"payoff\":..., "
        "\"hooks\":[{\"angle\":..., \"line\":...} x5], \"pick\":<int>, "
        "\"weak\":true|false, \"why_weak\":\"<when weak>\"}")


def parse_pitch(raw: str) -> dict | None:
    """A brief, or None when the answer is not one. `weak` must be an exact
    bool and every field present: garbage is no brief, never a pass."""
    d = _obj(raw)
    if not d or not isinstance(d.get("weak"), bool):
        return None
    if not all(isinstance(d.get(k), str) and d[k].strip()
               for k in _PITCH_FIELDS):
        return None
    hooks = [h for h in (d.get("hooks") or [])
             if isinstance(h, dict) and isinstance(h.get("line"), str)
             and h["line"].strip()]
    pick = d.get("pick")
    if len(hooks) < 3 or not isinstance(pick, int) or isinstance(pick, bool) \
            or not 0 <= pick < len(hooks):
        return None
    if len({h["line"].strip().lower() for h in hooks}) < len(hooks):
        return None          # five synonyms is not five concepts
    out = {k: d[k].strip() for k in _PITCH_FIELDS}
    out.update(hooks=hooks, pick=pick, weak=d["weak"],
               why_weak=str(d.get("why_weak") or "").strip(),
               hook=hooks[pick]["line"].strip(),
               angle=str(hooks[pick].get("angle") or "").strip())
    return out


def pitch(digest: str, *, llm=None) -> dict | None:
    """The idea brief for a dataset digest, or None when no brain answered
    usably (the forge then writes as it did before, and says so)."""
    try:
        raw = (llm or _llm)(PITCH_SYSTEM, pitch_prompt(digest))
    except Exception:  # noqa: BLE001
        return None
    return parse_pitch(raw)


def brief_for_writer(b: dict) -> str:
    """The brief as the writer reads it: the words are written TO it."""
    return (
        "IDEA BRIEF (write the story to this; the hook below was chosen from "
        "five concepts -- keep its idea, you may tighten its words):\n"
        f"  the viewer believes: {b['belief']}\n"
        f"  the data says instead: {b['surprise']}\n"
        f"  why it matters: {b['stakes']}\n"
        f"  the picture that proves it: {b['visual_proof']}\n"
        f"  the promise: {b['promise']}\n"
        f"  the payoff (the closing lands it): {b['payoff']}\n"
        f"  the hook: {b['hook']}")


# ---------------------------------------------------------------------------
# 2. The blind scorecard — before the render
# ---------------------------------------------------------------------------
SCORE_SYSTEM = (
    "You are a viewer-side editor scoring a 30-50 second YouTube Short "
    "BEFORE it is made, from its script and its planned pictures. You did "
    "not write it and you have not seen anyone's opinion of it. First "
    "impressions count: would a stranger scrolling stop, follow, and "
    "remember it? Score hard; most scripts are not good.")


_DECL = re.compile(r"(?m)^\s*(HERO|SUBSTANCE|CAUSE):\s*(.+)$")


def picture(x) -> str:
    """What a window SHOWS, in words: a drawn scene's own HERO / SUBSTANCE
    / CAUSE declarations (every brain scene carries them), else a brief or
    the machine/insight the renderer will draw."""
    if isinstance(x, str):
        decl = _DECL.findall(x)
        return "; ".join(f"{k.lower()}: {v.strip()}" for k, v in decl)[:300]
    if not isinstance(x, dict):
        return ""
    for k in ("illustrated_scene", "scene"):
        v = x.get(k)
        if isinstance(v, str) and _DECL.search(v):
            return picture(v)
        if isinstance(v, dict) and (v.get("brief") or v.get("what")):
            return str(v.get("brief") or v.get("what"))[:300]
    v = x.get("visual") or x.get("machine")
    if v:
        return str(v)[:300]
    return f"a data picture ({x.get('insight_type') or 'chart'})"


def _read_aloud(story: dict) -> str:
    lines = [f"TITLE: {story.get('title', '')}",
             f"HOOK (said over the first frame): {story.get('hook', '')}"]
    hp = picture(story.get("hook_scene") or "")
    if hp:
        lines.append(f"   picture: {hp}")
    for i, seg in enumerate(story.get("segments") or []):
        lines.append(f"BEAT {i + 1} [{(seg.get('topic') or '').strip()}]: "
                     f"{(seg.get('say') or '').strip()}")
        lines.append(f"   picture: {picture(seg)}")
    if story.get("closing"):
        lines.append(f"CLOSING: {story['closing']}")
        cp = picture(story.get("closing_scene") or "")
        if cp:
            lines.append(f"   picture: {cp}")
    if story.get("question"):
        lines.append(f"ON-SCREEN QUESTION: {story['question']}")
    return "\n".join(lines)


def score_prompt(story: dict) -> str:
    rubric = "\n".join(f"  {k}: 0-{v}" for k, v in CRITERIA.items())
    return (
        f"{_read_aloud(story)}\n\n"
        "Score each criterion (integers):\n"
        "  premise -- one plain reason an ordinary viewer cares\n"
        "  hook -- the first frame and spoken hook are instantly clear, true, "
        "intriguing, and match the payoff\n"
        "  arc -- each beat changes what you understand; not a row of facts\n"
        "  factual -- units, denominators, dates make sense; nothing "
        "overclaimed\n"
        "  visual_proof -- the pictures show the idea, readable on a phone\n"
        "  payoff -- the ending answers what the opening promised\n"
        "  voice -- a person would say it this way; no classroom filler\n"
        f"Maximums:\n{rubric}\n"
        f"Fatal flags (list any that apply, else []): {', '.join(FATAL)}.\n\n"
        "Return STRICT JSON: {\"scores\": {<criterion>: <int>}, \"fatal\": "
        "[...], \"weakest_note\": \"<the one change that would help most>\"}")


def parse_card(raw: str) -> dict | None:
    """A card, or None. Every criterion must be an exact int within its
    points and `fatal` a list of known flags; anything else is no card."""
    d = _obj(raw)
    sc = d.get("scores") if d else None
    if not isinstance(sc, dict):
        return None
    scores = {}
    for k, top in CRITERIA.items():
        v = sc.get(k)
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= top:
            return None
        scores[k] = v
    fatal = d.get("fatal")
    if not isinstance(fatal, list) or not all(isinstance(f, str) for f in fatal):
        return None
    fatal = [f for f in fatal if f in FATAL]
    return {"scores": scores, "total": sum(scores.values()), "fatal": fatal,
            "weakest": weakest(scores),
            "note": str(d.get("weakest_note") or "").strip()[:240]}


def weakest(scores: dict) -> str:
    """The criterion furthest below its own maximum, as a share of it."""
    return min(CRITERIA, key=lambda k: (scores.get(k, 0) / CRITERIA[k], k))


def scorecard(story: dict, *, llm=None) -> dict | None:
    try:
        raw = (llm or _llm)(SCORE_SYSTEM, score_prompt(story))
    except Exception:  # noqa: BLE001
        return None
    return parse_card(raw)


def fingerprint(story: dict) -> str:
    """What the card was scored on — a card is reused only while the words
    it read are unchanged, so a story is scored once, not every run."""
    import hashlib
    return hashlib.sha256(_read_aloud(story).encode()).hexdigest()[:16]


def decide(card: dict | None, policy: dict | None = None) -> dict:
    """Pure. `ship` / `rewrite` / `reconceive` / `hold` / `unscored`."""
    if card is None:
        return {"action": "unscored", "reason": "no usable scorecard"}
    pol = policy or gate_policy()
    if card.get("fatal"):
        return {"action": "hold",
                "reason": "fatal: " + ", ".join(card["fatal"])}
    t = card["total"]
    if t >= pol["pass_at"]:
        return {"action": "ship", "reason": f"scorecard {t}/100"}
    why = (f"scorecard {t}/100 — weakest: {card['weakest']} "
           f"({card['scores'][card['weakest']]}/{CRITERIA[card['weakest']]})"
           + (f": {card['note']}" if card.get("note") else ""))
    if t >= pol["rewrite_at"]:
        return {"action": "rewrite", "reason": why}
    return {"action": "reconceive", "reason": why}


# ---------------------------------------------------------------------------
# 3. EARS / EYES / EVIDENCE
# ---------------------------------------------------------------------------
DATA_DIR = REPO / "data_learning" / "data"


def _evidence(seg: dict) -> str:
    """The dataset a beat's numbers come from, resolved the way story.build
    and the editorial gate resolve it."""
    fn = (seg.get("params") or {}).get("file") or f"{seg.get('key', '')}.json"
    p = DATA_DIR / fn if fn and fn != ".json" else None
    try:
        if p is not None and p.is_file():
            d = json.loads(p.read_text())
            src = d.get("source") or {}
            bits = [src.get("publisher") or src.get("name"), d.get("title"),
                    src.get("url"), src.get("access_date")]
            return " | ".join(str(b) for b in bits if b) or fn
    except Exception:  # noqa: BLE001
        pass
    return f"unresolved dataset {fn!r}" if p is not None else "no dataset"


def sidecar(story: dict) -> list[dict]:
    """One row per window: what is SAID, what is SHOWN, what PROVES it."""
    rows = [{"window": "hook", "ears": story.get("hook", ""),
             "eyes": picture(story.get("hook_scene") or "")
             or "the first beat's finished picture",
             "evidence": "no number in the hook (hook_doctrine)"}]
    for i, seg in enumerate(story.get("segments") or []):
        rows.append({"window": f"beat {i}", "ears": seg.get("say", ""),
                     "eyes": picture(seg), "evidence": _evidence(seg)})
    rows.append({"window": "closing", "ears": story.get("closing", ""),
                 "eyes": picture(story.get("closing_scene") or "")
                 or "the last beat's finished picture",
                 "evidence": "restates no new number"})
    return rows


def write_sidecar(story: dict, root: Path | None = None) -> Path | None:
    """`state/story_sidecars/<slug>.json` — small JSON, safe for state/."""
    slug = story.get("slug")
    if not slug:
        return None
    out = (root or REPO) / "state" / "story_sidecars" / f"{slug}.json"
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "slug": slug, "brief": story.get("brief"),
            "scorecard": story.get("scorecard"),
            "storyboard": sidecar(story)}, indent=1, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        return None
    return out


# ---------------------------------------------------------------------------
# 4. The gate as the posting run calls it
# ---------------------------------------------------------------------------
def _persist_card(slug: str, card: dict, config_path) -> None:
    path = Path(config_path or REPO / "data_learning" / "niche.config.json")
    cfg = json.loads(path.read_text())
    for s in cfg.get("stories") or []:
        if s.get("slug") == slug:
            if s.get("scorecard") == card:
                return
            s["scorecard"] = card
            from shared.fsutil import write_json_if_changed
            write_json_if_changed(path, cfg, ensure_ascii=False)
            return


def gate(sc: dict, *, config_path=None, llm=None, log=print) -> dict:
    """Score the story (once per wording), record it, decide.

    The card is kept on the story with the fingerprint of the words it read,
    so a story waiting in the queue is not re-scored every run; a rewrite
    changes the words and so earns a fresh card. No usable card is
    `unscored`: this gate is NEW, so with no brain it adds nothing and the
    story goes on to the gates that already existed — said in the log, never
    labelled a pass."""
    fp = fingerprint(sc)
    cached = sc.get("scorecard") if isinstance(sc.get("scorecard"), dict) else None
    card = cached if cached and cached.get("fp") == fp else None
    if card is None:
        card = scorecard(sc, llm=llm)
        if card is not None:
            card = dict(card, fp=fp)
            sc["scorecard"] = card
            try:
                _persist_card(sc.get("slug"), card, config_path)
            except Exception as e:  # noqa: BLE001
                log(f"[story] scorecard persist skipped: {e}")
    write_sidecar(sc)
    d = decide(card)
    log(f"[story] {d['action']}: {d['reason']}"
        + (" — no judge answered; the existing gates decide" if d["action"] == "unscored" else ""))
    return d


#: The posting run's hold reasons carry this prefix, which the rewrite
#: mailbox reads as a words job (`rewrite_mailbox._WORD_PREFIX`).
PREFIX = "story:"


def hold_reasons(d: dict) -> list[str]:
    if d["action"] == "rewrite":
        return [f"{PREFIX} rewrite the weakest part — {d['reason']}"]
    if d["action"] == "reconceive":
        return [f"{PREFIX} re-conceive it: a new premise, hook and arc from "
                f"the same data — {d['reason']}"]
    if d["action"] == "hold":
        return [f"{PREFIX} {d['reason']} — fix the words so it is true and "
                f"pays off what it promises"]
    return []
