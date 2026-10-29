#!/usr/bin/env python3
"""Union-merge the two learning files a CI push race used to clobber.

Usage: merge_state_json.py THEIRS OURS OUT [BASE]   (OUT's name picks the rule)

    data_learning/viz_mechanics.json   entries by `sig`
    data_learning/niche.config.json    stories by `slug`

THE DAY THE TEACHERS VANISHED. PR #407 seeded four hand-authored tier-1
mechanics into the library and merged at 17:33 UTC on 2026-09-21. At 17:47
the explainer run that had checked out main at 16:58 finished, its persist
step lost the push race, and `ci_commit_state.sh` did what it does for
every artifact that is not a posted log: restored ITS copy over fresh
main. Sixty entries, zero exemplars — fourteen minutes after they landed,
with the persist reporting success. The same rule silently discards a
story the Routine adds to `niche.config.json` while a render is running,
and (since #405) the mechanic a render persisted into a story segment
whenever another run's older copy of the config wins the race.

The posted logs never had this problem because they are UNIONED
(`merge_posted_log.py`). These two files are unioned the same way now:

  mechanics  every `sig` from either side survives; a sig on both sides
             keeps every field of both (ours' newer fields win, but a
             `grade`, `starred`, `exemplar`, `moves`/`moves_on` that only
             one side has is never dropped); starred/exemplar entries are
             never evicted; the rest roll at the library's own cap.
  stories    every `slug` from either side survives, in main's order with
             ours-only appended; a slug on both sides takes OUR story (the
             run that just rendered it — the status quo for the conflict
             case), except that a segment `scene` carrying a `grade` or
             `code` on their side is kept if ours has none for that key,
             and a drawn scene (`STORY_SCENES`, `SEGMENT_SCENES`) only
             their side has is kept while the words it was drawn for agree.

THE NIGHT THE GIANT PHONE CAME BACK. "ours wins" is a two-way rule, and a
two-way merge cannot tell an edit from a stale copy. PR #706 nulled the
giant-phone `hook_scene` on nyc-noise-complaints-per-day at 14:26 UTC on
2026-10-28; the posting runs that had checked out before it lost their push
races at 18:47 and 23:48, took OUR story for the slug, and wrote the scene
back both times, while the 19:18 forge (checked out before 18:47) took ITS
story and reverted five retold stories and two drawn beats the 18:47 run had
just landed. Every writer clobbered the one before it. So when the caller
passes BASE (the main the run last synced with), stories are merged
THREE-WAY, field by field and segment by segment: a field only one side
changed takes that side's value, so a run writes back only what it changed
and can never resurrect what main nulled; a field both sides changed takes
ours, the old rule, now confined to a real conflict. Without BASE the
two-way rule below still applies.

Fails CLOSED on unparseable input, like merge_posted_log: a corrupt side
must never be pushed over a good one.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

LIB_CAP = 120


def _load(p: str):
    text = Path(p).read_text() if Path(p).exists() else ""
    if not text.strip():
        return None
    return json.loads(text)


def _pin(t: dict, o: dict) -> dict:
    """Merge one mechanic entry: ours' fields over theirs', never losing a
    learning field that only one side has."""
    m = dict(t)
    m.update(o)
    for k in ("starred", "exemplar", "moves"):
        if k in t and k not in o:
            m[k] = t[k]
        if t.get(k) is True or o.get(k) is True:
            if k != "moves":
                m[k] = True
    if "moves_on" in t and "moves_on" not in o:
        m["moves_on"] = t["moves_on"]
    tg, og = t.get("grade"), o.get("grade")
    if isinstance(tg, dict) and not isinstance(og, dict):
        m["grade"] = tg
    elif isinstance(tg, dict) and isinstance(og, dict):
        m["grade"] = og if str(og.get("ts") or "") >= str(tg.get("ts") or "") else tg
    return m


def _key(e: dict) -> str:
    """The entry's identity: its `sig`, or — for the 24 legacy entries that
    predate signatures — the SAME sha1(mechanic + code)[:12] that
    `viz_director._record_mechanic` writes as `sig`, written onto the entry
    so it has one from here on. The first live run of this merger (2026-09-21
    22:00 UTC) kept only entries that already had a `sig` and dropped the
    other 24, 64 -> 40. Identity is the CONTENT, not the presence of a field."""
    sig = e.get("sig")
    if not sig:
        sig = hashlib.sha1((str(e.get("mechanic", "")) + str(e.get("code", "")))
                           .encode()).hexdigest()[:12]
        e["sig"] = sig
    return str(sig)


def merge_mechanics(theirs, ours) -> list:
    tl = theirs if isinstance(theirs, list) else []
    ol = ours if isinstance(ours, list) else []
    by = {}
    order = []
    for e in tl:
        if not isinstance(e, dict):
            continue
        k = _key(e)
        by[k] = e
        order.append(k)
    for e in ol:
        if not isinstance(e, dict):
            continue
        k = _key(e)
        if k in by:
            by[k] = _pin(by[k], e)
        else:
            by[k] = e
            order.append(k)
    lib = [by[s] for s in order]
    keep = [m for m in lib if m.get("starred") or m.get("exemplar")]
    rest = [m for m in lib if not (m.get("starred") or m.get("exemplar"))]
    return keep + rest[-max(0, LIB_CAP - len(keep)):]


#: A drawn scene, keyed on the words it was drawn for. THE AFTERNOON THE
#: SCENES VANISHED: on 2026-10-12 the predraw saved three stories' last
#: scenes at 21:05; at 21:07 a posting run that had checked out at 18:20 lost
#: the push race, took OUR story for every slug, and the hook, closing and
#: beat scenes it never had were gone. A scene only one side has is kept
#: while both sides still tell the story in the same words; a story whose
#: words changed is a new story to draw (`rewrite_mailbox.apply`).
STORY_SCENES = (("hook_scene", "hook"), ("hook_data", "hook"),
                ("closing_scene", "closing"), ("closing_data", "closing"))
SEGMENT_SCENES = ("illustrated_scene",)


def _merge_story(t: dict, o: dict) -> dict:
    out = dict(o)
    for key, words in STORY_SCENES:
        if key in t and key not in o and t.get(words) == o.get(words):
            out[key] = t[key]
    ts, os_ = t.get("segments"), o.get("segments")
    if isinstance(ts, list) and isinstance(os_, list) and len(ts) == len(os_):
        segs = []
        for a, b in zip(ts, os_):
            seg = dict(b) if isinstance(b, dict) else b
            if isinstance(a, dict) and isinstance(b, dict):
                if a.get("say") == b.get("say"):
                    for key in SEGMENT_SCENES:
                        if key in a and key not in b:
                            seg[key] = a[key]
                asc, bsc = a.get("scene"), b.get("scene")
                if isinstance(asc, dict) and (asc.get("grade") or asc.get("code")) \
                        and not (isinstance(bsc, dict) and (bsc.get("grade") or bsc.get("code"))):
                    seg["scene"] = asc
            segs.append(seg)
        out["segments"] = segs
    return out


def merge_stories(theirs, ours) -> dict:
    t = theirs if isinstance(theirs, dict) else {}
    o = ours if isinstance(ours, dict) else {}
    out = dict(t)
    out.update({k: v for k, v in o.items() if k != "stories"})
    tl = t.get("stories") if isinstance(t.get("stories"), list) else []
    ol = o.get("stories") if isinstance(o.get("stories"), list) else []
    by = {}
    order = []
    for s in tl:
        if isinstance(s, dict) and s.get("slug"):
            by[s["slug"]] = s
            order.append(s["slug"])
    for s in ol:
        if not (isinstance(s, dict) and s.get("slug")):
            continue
        if s["slug"] in by:
            by[s["slug"]] = _merge_story(by[s["slug"]], s)
        else:
            by[s["slug"]] = s
            order.append(s["slug"])
    out["stories"] = [by[k] for k in order]
    return out


_GONE = object()


def _three(b, t, o):
    """One value, three-way: whichever side moved off the base wins; when
    both moved, ours (the run that just rendered it)."""
    if o == b:
        return t
    if t == b:
        return o
    return o


def _fields3(b: dict, t: dict, o: dict, skip=()) -> dict:
    out = {}
    for k in list(t) + [k for k in o if k not in t] + [k for k in b if k not in t and k not in o]:
        if k in skip or k in out:
            continue
        v = _three(b.get(k, _GONE), t.get(k, _GONE), o.get(k, _GONE))
        if v is not _GONE:
            out[k] = v
    return out


def _words_moved(b: dict, t: dict, o: dict, out: dict, pairs) -> None:
    """A scene is drawn FOR its words: where main re-worded and the run did
    not, the run's scene is for words that are gone, so main's stands."""
    for key, words in pairs:
        if t.get(words, _GONE) != b.get(words, _GONE) and o.get(words, _GONE) == b.get(words, _GONE):
            if key in t:
                out[key] = t[key]
            else:
                out.pop(key, None)


def _merge_story3(b: dict, t: dict, o: dict) -> dict:
    if o == b:
        return t
    if t == b:
        return o
    out = _fields3(b, t, o, skip=("segments",))
    _words_moved(b, t, o, out, STORY_SCENES)
    bs, ts, os_ = b.get("segments"), t.get("segments"), o.get("segments")
    if all(isinstance(x, list) for x in (bs, ts, os_)) and len(bs) == len(ts) == len(os_) \
            and all(isinstance(x, dict) for x in bs + ts + os_):
        out["segments"] = []
        for x, y, z in zip(bs, ts, os_):
            seg = _fields3(x, y, z)
            _words_moved(x, y, z, seg, [(k, "say") for k in SEGMENT_SCENES])
            out["segments"].append(seg)
    elif os_ == bs:                          # beats re-cut on main only
        if ts is not None:
            out["segments"] = ts
    elif ts == bs:                           # ...or in the run only
        if os_ is not None:
            out["segments"] = os_
    elif os_ is not None:                    # re-cut on both sides: old rule
        out["segments"] = _merge_story(t, o).get("segments", os_)
    return out


def merge_stories3(theirs, ours, base) -> dict:
    """`merge_stories` with the common ancestor: see THE NIGHT THE GIANT
    PHONE CAME BACK. A slug one side deleted and the other left alone is
    gone; a slug new on both sides falls back to the two-way rule."""
    t = theirs if isinstance(theirs, dict) else {}
    o = ours if isinstance(ours, dict) else {}
    b = base if isinstance(base, dict) else {}
    out = _fields3(b, t, o, skip=("stories",))

    def by_slug(d):
        lst = d.get("stories") if isinstance(d.get("stories"), list) else []
        return {s["slug"]: s for s in lst if isinstance(s, dict) and s.get("slug")}, \
            [s["slug"] for s in lst if isinstance(s, dict) and s.get("slug")]
    bb, _ = by_slug(b)
    tb, torder = by_slug(t)
    ob, oorder = by_slug(o)
    stories = []
    for slug in torder + [x for x in oorder if x not in tb]:
        bs, ts, os_ = bb.get(slug), tb.get(slug), ob.get(slug)
        if ts is not None and os_ is not None:
            stories.append(_merge_story3(bs, ts, os_) if bs is not None
                           else _merge_story(ts, os_))
        elif ts is not None:                 # ours lacks it
            if bs is None or ts != bs:       # new on main, or main edited it
                stories.append(ts)
        elif os_ is not None:                # theirs lacks it
            if bs is None or os_ != bs:      # new in the run, or the run edited it
                stories.append(os_)
    out["stories"] = stories
    return out


def merge_for(name: str, theirs, ours, base=None):
    if name.endswith("viz_mechanics.json"):
        return merge_mechanics(theirs, ours)
    if name.endswith("niche.config.json"):
        if isinstance(base, dict):
            return merge_stories3(theirs, ours, base)
        return merge_stories(theirs, ours)
    raise SystemExit(f"merge_state_json: no rule for {name}")


def merge_jsonl(theirs_text: str, ours_text: str) -> str:
    """Union of LINES for an append-only ledger (state/showrunner_verdicts
    .jsonl): theirs in order, then every line of ours theirs does not have.
    Never reorders, never drops. A blank line is not a record."""
    out: list[str] = []
    seen: set[str] = set()
    for text in (theirs_text, ours_text):
        for line in text.splitlines():
            s = line.strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return ("\n".join(out) + "\n") if out else ""


def main(argv: list[str]) -> int:
    if len(argv) not in (4, 5):
        print(__doc__.splitlines()[2], file=sys.stderr)
        return 2
    if argv[3].endswith(".jsonl"):
        theirs = Path(argv[1]).read_text() if Path(argv[1]).exists() else ""
        ours = Path(argv[2]).read_text() if Path(argv[2]).exists() else ""
        merged = merge_jsonl(theirs, ours)
        Path(argv[3]).write_text(merged)
        print(f"[merge_state_json] line-union -> {merged.count(chr(10))} "
              f"lines in {Path(argv[3]).name}")
        return 0
    try:
        theirs, ours = _load(argv[1]), _load(argv[2])
    except json.JSONDecodeError as e:
        print(f"[merge_state_json] refusing: unparseable input ({e})", file=sys.stderr)
        return 1
    base = None
    if len(argv) == 5:
        try:                     # an unreadable base only costs the three-way
            base = _load(argv[4])
        except json.JSONDecodeError:
            print("[merge_state_json] base unparseable — two-way merge", file=sys.stderr)
    merged = merge_for(argv[3], theirs, ours, base)
    Path(argv[3]).write_text(json.dumps(merged, indent=1, ensure_ascii=False) + "\n")
    n = len(merged) if isinstance(merged, list) else len(merged.get("stories", []))
    print(f"[merge_state_json] union -> {n} entries in {Path(argv[3]).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
