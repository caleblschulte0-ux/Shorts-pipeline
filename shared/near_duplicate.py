"""ONE answer to "is this the same video again?" — for every channel.

Operator, 2026-10-02: *"why do we keep reposting the same videos? ... I'm
talking about those landline videos."* On the trending channel the mobile-
beat-the-landline story shipped as a graph race on 08-03 ("Broadband Passed
Landlines in 20 Years"), 09-26 ("Mobile Broadband Left Fixed Lines Behind")
and 09-27 ("Mobile Lines Buried Landlines Worldwide", twice), and on the
explainer on 10-01 ("Landlines Peaked In 2006"). Every title was different.
Every dedupe in the pipeline compared TITLES, exactly, on ONE channel, over
six days — so a story told again under new words, from a sibling dataset,
on the other channel, was new to every one of them.

Three measures, cheapest first, and a refusal names the video it repeats:

1. `duplicate_of` — the explainer's near-duplicate title guard (sequence
   ratio + significant-word Jaccard), moved here verbatim so both channels
   use the same one. `tests/test_near_duplicate.py` holds it to the
   original byte for byte in behaviour.
2. `subject_words` / `same_subject` — a package's SUBJECT: the nouns of its
   title, hook, series names, axis label and hashtags, with the race verbs
   ("passed", "buried", "beat") and the channel words removed. Two packages
   that share two subject nouns are the same story to a viewer whatever
   the title says ("mobile" + "line" = the landline video again).
3. `brain_duplicate_of` — for what words cannot see: a text brain is shown
   the candidate and the titles the channel family has posted in the
   window, and names the one that tells the same story, or NONE. Fails
   OPEN (None) when no backend answers — the two measures above still
   stand — and says so.

The window and the corpus: `no_repeat_subject_days` in
config/channel_registry.json (defaults, per-channel override), across the
DATA channels (trending, explainer, curiosity) — a story is a repeat to the
operator whichever of his channels it lands on. The third channel's clips
are a different universe and are not in the corpus.
"""
from __future__ import annotations

import difflib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------- 1. titles
# Verbatim from scripts/post_stories.py (2026-10-02), where it was calibrated
# against the real 234-upload log: 0.75/0.60 refuses 24 of them (10%) — the
# straight repeats and the one-noun-swapped templates — and nothing else.
_DUP_SEQ = 0.75
_DUP_JACCARD = 0.60
_DUP_STOP = frozenset(
    "the a an of in on to for is are and or its it how why what when we you "
    "your our new most all than that this has have was were be been at by "
    "with from about into over under more less just now still".split())


def sig_words(title: str) -> set:
    words = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower()).split()
    return {w for w in words if w not in _DUP_STOP and len(w) > 2}


def duplicate_of(title: str, posted_titles) -> str | None:
    """The already-posted title this one repeats, or None.

    Returns the OTHER title rather than a bool so the hold can name it — a
    refusal that says which video it collided with is actionable; one that
    says "too similar" sends someone reading the whole log."""
    if not (title or "").strip():
        return None
    mine = sig_words(title)
    for other in posted_titles:
        if not (other or "").strip():
            continue
        if difflib.SequenceMatcher(None, title.lower(),
                                   other.lower()).ratio() >= _DUP_SEQ:
            return other
        theirs = sig_words(other)
        union = mine | theirs
        if union and len(mine & theirs) / len(union) >= _DUP_JACCARD:
            return other
    return None


# -------------------------------------------------------------- 2. subject
#: Words that say HOW a race went, not WHAT raced — every graph race has
#: one, so they tell two subjects apart from nothing.
_RACE_WORDS = frozenset(
    "passed pass passes buried bury beat beats left behind replaced replace "
    "outran overtook overtake ate ruled ended ends quietly nobody announced "
    "never recovered collapse collapsed grew grows growth fell falls dying "
    "died dead death peaked peak since again back briefly reversed worldwide "
    "world global america american americans usa europe europes chinas "
    "year years decade decades ago one two three ten twenty 20x 7x billion "
    "million per people percent lot way biggest first last big huge then "
    "didn didnt did got get saw coming come came out every other hit time "
    "times entire actually really worth who which wins win won catching "
    "catch caught real good company companies kept going almost close "
    "finally quietly ever own record broke went from zero top stayed ahead "
    "lead led leads crushed caught dwarfed outnumbered outsold war race".split())
#: Words every package on the channel carries.
_CHANNEL_WORDS = frozenset(
    "shorts short trending viral fyp data chart graph race video history "
    "technology tech economy business approximate statistic statistics "
    "didyouknow number numbers total totals share shares count counts "
    "sales annual yearly subscription subscriptions user users million "
    "billion trillion percent inhabitants unit units".split())
#: Two subject nouns in common is the same story told again.
SUBJECT_SHARED = 2


def _stem(w: str) -> str:
    for suf in ("ies", "ing", "ed", "es", "s"):
        if suf == "s" and w.endswith("ss"):
            break
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[:-len(suf)] + ("y" if suf == "ies" else "")
            break
    return w


def subject_words(pkg_or_title) -> set:
    """The nouns a viewer would say this video is ABOUT. A package
    contributes its title, hook, series names and axis label; a
    bare string contributes itself."""
    if isinstance(pkg_or_title, dict):
        parts = [pkg_or_title.get("title") or "", pkg_or_title.get("hook") or "",
                 pkg_or_title.get("y_label") or "",
                 pkg_or_title.get("topic") or ""]
        for s in pkg_or_title.get("series") or []:
            if isinstance(s, dict):
                parts.append(str(s.get("name") or ""))
        # hashtags are deliberately NOT a subject: "#didyouknow #statistic
        # #tech" is on half the slate and made every pair look alike
        text = " ".join(parts)
    else:
        text = str(pkg_or_title or "")
    out = set()
    for w in sig_words(text):
        if w in _RACE_WORDS or w in _CHANNEL_WORDS or w.isdigit():
            continue
        out.add(_stem(w))
    return out


def same_subject(a: set, b: set) -> set:
    """The subject nouns two videos share, when there are enough of them to
    call it the same story; else an empty set."""
    shared = {w for w in a & b if len(w) > 2}
    return shared if len(shared) >= SUBJECT_SHARED else set()


# --------------------------------------------------------------- 3. brain
_BRAIN_SYSTEM = (
    "You are the editor of a family of short data-video channels. A viewer "
    "who sees the same story twice unsubscribes. You are shown ONE new video "
    "and the titles of videos already posted. Answer with the EXACT posted "
    "title that tells the same story as the new one — the same subject and "
    "the same takeaway, even if the dataset, the wording or the years differ "
    "(a race of mobile vs fixed lines IS the landline story again) — or the "
    "single word NONE if the new video is genuinely a different story. "
    "Output only that: a title copied exactly, or NONE.")


def describe(pkg_or_title) -> str:
    """The candidate, as the brain sees it: title, hook, what races."""
    if not isinstance(pkg_or_title, dict):
        return f"title: {pkg_or_title}"
    p = pkg_or_title
    bits = [f"title: {p.get('title') or ''}"]
    if p.get("hook"):
        bits.append(f"hook: {p['hook']}")
    names = [str(s.get("name")) for s in p.get("series") or [] if isinstance(s, dict)]
    if names:
        bits.append("series: " + " vs ".join(names))
    if p.get("y_label"):
        bits.append(f"measure: {p['y_label']}")
    if p.get("topic") and p.get("topic") != p.get("title"):
        bits.append(f"topic: {p['topic']}")
    return "\n".join(bits)


def brain_duplicate_of(candidate, titles, log=print) -> str | None:
    """The posted title the brain says tells the same story, or None (also
    None when no backend answers — logged, never silent)."""
    if os.environ.get("SUBJECT_BRAIN", "on").lower() in ("0", "off", "false"):
        return None
    titles = [t for t in dict.fromkeys(titles) if (t or "").strip()]
    if not titles:
        return None
    try:
        from shared.script_generator import _call_llm
        user = (describe(candidate) + "\n\nALREADY POSTED:\n"
                + "\n".join(f"- {t}" for t in titles[-240:])
                + "\n\nThe posted title that tells the same story, copied "
                  "exactly, or NONE:")
        raw = (_call_llm(_BRAIN_SYSTEM, user) or "").strip()
    except Exception as exc:  # noqa: BLE001 — fail OPEN, say so
        log(f"[near-duplicate] no brain for the subject check "
            f"({type(exc).__name__}: {str(exc)[:80]}) — words only")
        return None
    ans = raw.strip().strip('"').strip("'").strip()
    if not ans or ans.upper().startswith("NONE"):
        return None
    fold = {t.casefold(): t for t in titles}
    if ans.casefold() in fold:
        return fold[ans.casefold()]
    # a title quoted inside a sentence still counts; a made-up one does not
    for t in titles:
        if t.casefold() in ans.casefold():
            return t
    return None


# --------------------------------------------------------------- corpus
DATA_CHANNELS = ("trending", "explainer", "curiosity")
_LOGS = {"trending": "state/posted_log.json",
         "explainer": "state/explainer_posted_log.json",
         "curiosity": "state/curiosity_posted_log.json"}


#: Only for a registry that omits the key (test fixtures, an old snapshot).
#: The live registry carries it — tests/test_near_duplicate.py checks — so
#: production never reads this number; the policy is the registry's.
WINDOW_IF_UNSET = 120


def window_days(channel: str = "trending") -> int:
    """`no_repeat_subject_days` from the registry — per channel, else the
    defaults, else `WINDOW_IF_UNSET` for a registry that predates it."""
    from shared import channel_registry as reg
    try:
        r = reg.load()
    except Exception:  # noqa: BLE001 — a missing registry fails the CHANNEL closed elsewhere
        return WINDOW_IF_UNSET
    ch = (r.get("channels") or {}).get(channel) or {}
    v = ch.get("no_repeat_subject_days",
               (r.get("defaults") or {}).get("no_repeat_subject_days"))
    return WINDOW_IF_UNSET if v is None else int(v)


def posted_corpus(days: int | None = None, channels=DATA_CHANNELS,
                  root: Path | None = None, now=None) -> list[dict]:
    """[{title, topic, channel, at, url}] for every upload on the data
    channels inside the window, oldest first. Unreadable logs are skipped —
    this is the guard's memory, not its gate; a corrupt ledger fails the
    channel's own loader closed before anything reaches here."""
    root = Path(root or ROOT)
    days = window_days() if days is None else days
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    out = []
    for ch in channels:
        p = root / _LOGS[ch]
        if not p.is_file():
            continue
        try:
            log = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            continue
        posted = log.get("posted") if isinstance(log, dict) else log
        entries = posted.values() if isinstance(posted, dict) else (posted or [])
        for e in entries:
            if not isinstance(e, dict):
                continue
            at = str(e.get("posted_at") or e.get("at") or e.get("ts") or "")
            if at[:10] < since:
                continue
            if e.get("state") not in (None, "posted"):
                continue
            title = (e.get("title") or "").strip()
            if title:
                out.append({"title": title, "topic": (e.get("topic") or "").strip(),
                            "channel": ch, "at": at,
                            "url": e.get("video_url") or e.get("url") or ""})
    out.sort(key=lambda r: r["at"])
    return out


def corpus_titles(corpus) -> list[str]:
    seen = []
    for r in corpus:
        for t in (r.get("title"), r.get("topic")):
            if t and t not in seen:
                seen.append(t)
    return seen


# ----------------------------------------------------------- the verdict
def subject_duplicate_of(candidate, corpus, *, brain: bool = True,
                         log=print):
    """(posted title, how) when `candidate` (a package dict or a title) is
    the same video again as something in `corpus` (posted_corpus rows or
    plain titles) — how is "title", "subject" or "brain" — else None."""
    rows = [{"title": c} if isinstance(c, str) else c for c in corpus]
    titles = corpus_titles(rows)
    title = candidate.get("title") if isinstance(candidate, dict) else candidate
    hit = duplicate_of(title or "", titles)
    if hit:
        return hit, "title"
    mine = subject_words(candidate)
    for r in rows:
        for t in (r.get("title"), r.get("topic")):
            if not t:
                continue
            shared = same_subject(mine, subject_words(t))
            if shared:
                return t, "subject:" + "+".join(sorted(shared))
    if brain:
        hit = brain_duplicate_of(candidate, titles, log=log)
        if hit:
            return hit, "brain"
    return None
