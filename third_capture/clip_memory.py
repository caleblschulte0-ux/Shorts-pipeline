"""What the channel has already WATCHED — the story scout's footage memory.

The scout reads a catalogue of a month of clips and proposes stories. Until
this module, every line it read was a TITLE: our own authored ones for the
clips we posted, and whatever a stranger typed for the rest. On 2026-10-01
it proposed three stories and the director, holding the transcripts and
frames, refused all three for the same reason — the footage did not say
what the titles did:

  "The boar snipe never appears: the 9h40 clip shows Summit1g dying, but
   the transcript and frames never show a boar or any cause."
  "No clip shows a capture, a revenge or a release on bail."

Every one of those clips had just been downloaded, transcribed and looked
at. The run threw that away, and tomorrow's scout would have read the same
titles and proposed the same three stories, spending the same twenty
minutes to be told no again.

So the run remembers. Two things, both small, both keyed on the canonical
clip key:

- CLIPS: for every clip the pipeline transcribed (clip arm) or analysed
  (story arm) — what the footage SHOWS (`saw`, the scene analyst's
  observable one-line summary), what is SAID (`said`, the transcript's
  opening words) and who is in it. The catalogue prints these next to the
  title, so the scout reads evidence where it has it and knows when it is
  reading a guess.
- STORIES TRIED: every candidate the director refused AS A STORY, with its
  reason. The scout is shown them so it does not re-propose them, and a
  candidate that retells one is skipped before any download — unless new
  clips have joined it, in which case it is a different hypothesis.

This is learning state, not dedupe state: losing it costs re-analysis, never
a duplicate upload, so it loads tolerantly. It is pruned by age and capped
so it stays a small JSON file (`docs/STORAGE_AUDIT.md`: state/ is for small
JSON only). Pure apart from `load`/`save`; never raises into a run.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATH = REPO / "state" / "third_clip_memory.json"

MAX_AGE_DAYS = 40          # the catalogue looks back 30; keep a margin
# The catalogue reads at most 120 fresh + 160 history clips, so a memory
# much past that is never read. Held under the 256KB state/ limit at every
# field's cap by tests/test_the_scout_reads_footage.py.
MAX_CLIPS = 400
MAX_STORIES = 60
SAW_CHARS = 140
SAID_CHARS = 90


def _key(url: str) -> str:
    # the channel's ONE dedupe identity (see storyline.clip_key)
    from third_capture import storyline
    return storyline.clip_key(url or "")


def _clean(s, n: int) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def _day(d) -> str:
    return str(d or "")[:10]


def empty() -> dict:
    return {"clips": {}, "stories_tried": []}


def load(path: Path | str | None = None) -> dict:
    from shared.fsutil import load_json
    # PATH is read at CALL time so a test can point the module elsewhere
    mem = load_json(path or PATH, None)
    if not isinstance(mem, dict):
        return empty()
    if not isinstance(mem.get("clips"), dict):
        mem["clips"] = {}
    if not isinstance(mem.get("stories_tried"), list):
        mem["stories_tried"] = []
    return mem


def note_clip(mem: dict, source_url: str, *, day: str = "",
              channel: str = "", saw: str = "", said: str = "",
              people=()) -> None:
    """Remember what one clip contains. Merges: a later transcript-only
    pass never erases an earlier scene summary, and an empty field never
    overwrites a filled one."""
    try:
        k = _key(source_url)
        if not k:
            return
        rec = mem.setdefault("clips", {}).setdefault(k, {})
        rec["d"] = _day(day) or rec.get("d") or _day(
            datetime.now(timezone.utc).date().isoformat())
        if channel:
            rec["ch"] = _clean(channel, 24)
        if _clean(saw, SAW_CHARS):
            rec["saw"] = _clean(saw, SAW_CHARS)
        if _clean(said, SAID_CHARS):
            rec["said"] = _clean(said, SAID_CHARS)
        who = [_clean(p, 20) for p in (people or []) if _clean(p, 20)][:3]
        if who:
            rec["who"] = who
    except Exception:  # noqa: BLE001 — memory must never fail a run
        pass


def said_from_words(words) -> str:
    """The transcript's opening, as the scout will read it."""
    try:
        return _clean(" ".join(w["w"] for w in (words or [])[:30]),
                      SAID_CHARS)
    except Exception:  # noqa: BLE001
        return ""


# Bump when the story EDIT gets a capability a rendered refusal lacked.
# A cut the critic refused is a verdict on THE EDIT as much as on the
# story: the 72 that missed for "who is Buddha" was judged when a cut could
# carry one narrator line. Remembering it forever meant every near-miss of
# the old edit was skipped by every run of the new one, live and backtest
# alike (2026-10-07: the third backtest re-tried nothing it had rendered
# before). The director's "not a story" is about the footage and stands.
#   1 — a narrator line per beat; the stream around a clip arrives (copy)
#   2 — a repair is told which beat and source second the critic meant
EDIT_VERSION = 2


def note_story_tried(mem: dict, member_urls: list[str], *, premise: str = "",
                     why: str = "", day: str = "",
                     rendered: bool = False) -> None:
    """Remember that the director refused these clips AS A STORY. Only an
    editorial refusal belongs here — a starved analysis or a malformed plan
    says nothing about whether the story exists. `rendered` marks a cut the
    critic refused, which a better edit may yet pass (EDIT_VERSION)."""
    try:
        keys = sorted({_key(u) for u in member_urls if _key(u)})
        # one key is a MOMENT candidate (storyline.find_moments); a subset
        # of a refused moment is never a different story, and a story that
        # adds a clip to it is (already_tried)
        if not keys:
            return
        tried = mem.setdefault("stories_tried", [])
        tried[:] = [t for t in tried if sorted(t.get("members") or []) != keys]
        rec = {"members": keys, "premise": _clean(premise, 120),
               "why": _clean(why, 160),
               "d": _day(day) or datetime.now(timezone.utc).date().isoformat()}
        if rendered:
            rec["edit"] = EDIT_VERSION
        tried.append(rec)
    except Exception:  # noqa: BLE001
        pass


def _rendered(t: dict) -> bool:
    # records written before `edit` existed say so in their reason
    return "edit" in t or str(t.get("why", "")).startswith("rendered;")


def already_tried(mem: dict, member_urls: list[str],
                  thresh: float = 0.6) -> dict | None:
    """The refused story this candidate retells, or None.

    A retell is the same overlap rule as a shipped story (Jaccard >= 0.6 on
    clip keys) — with one exception that matters: a candidate holding a
    clip the refused one did NOT is a new hypothesis, because the clip that
    was missing may be the payoff that arrived today."""
    keys = {_key(u) for u in member_urls if _key(u)}
    if not keys:
        return None
    for t in mem.get("stories_tried") or []:
        pk = set(t.get("members") or [])
        if not pk or keys - pk:
            continue
        if _rendered(t) and int(t.get("edit") or 0) < EDIT_VERSION:
            continue                 # judged by an older edit: try again
        if len(keys & pk) / len(keys | pk) >= thresh:
            return t
    return None


def evidence(mem: dict, source_url: str) -> str:
    """The catalogue suffix for one clip: what was seen and said, or ""."""
    rec = (mem.get("clips") or {}).get(_key(source_url)) or {}
    parts = []
    if rec.get("saw"):
        parts.append(f"saw: {rec['saw']}")
    if rec.get("said"):
        parts.append(f'said: "{rec["said"]}"')
    return " | ".join(parts)


def tried_lines(mem: dict, ids_by_key: dict[str, str]) -> list[str]:
    """Refused stories, written in the catalogue's own ids where the clips
    are in today's catalogue — the scout's "do not propose these again"."""
    out = []
    for t in reversed(mem.get("stories_tried") or []):
        ids = [ids_by_key.get(k) for k in t.get("members") or []]
        if sum(1 for i in ids if i) < 2:
            continue
        shown = ", ".join(i for i in ids if i)
        out.append(f"[{shown}] {t.get('premise', '')!s} — refused: "
                   f"{t.get('why', '')!s}")
    return out[:20]


def prune(mem: dict, today: date | None = None) -> dict:
    today = today or datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=MAX_AGE_DAYS)).isoformat()
    clips = {k: v for k, v in (mem.get("clips") or {}).items()
             if isinstance(v, dict) and str(v.get("d", "")) >= cutoff}
    if len(clips) > MAX_CLIPS:
        keep = sorted(clips, key=lambda k: str(clips[k].get("d", "")),
                      reverse=True)[:MAX_CLIPS]
        clips = {k: clips[k] for k in keep}
    tried = [t for t in (mem.get("stories_tried") or [])
             if isinstance(t, dict) and str(t.get("d", "")) >= cutoff]
    return {"clips": clips, "stories_tried": tried[-MAX_STORIES:]}


def save(mem: dict, path: Path | str | None = None,
         today: date | None = None) -> None:
    try:
        from shared.fsutil import write_json_if_changed
        write_json_if_changed(path or PATH, prune(mem, today), indent=1,
                              sort_keys=True)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::[clip-memory] save failed ({e})", flush=True)
