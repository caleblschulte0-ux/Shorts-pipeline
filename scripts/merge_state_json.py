#!/usr/bin/env python3
"""Union-merge the two learning files a CI push race used to clobber.

Usage: merge_state_json.py THEIRS OURS OUT   (OUT's name picks the rule)

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
             `code` on their side is kept if ours has none for that key.

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


def _merge_story(t: dict, o: dict) -> dict:
    out = dict(o)
    ts, os_ = t.get("segments"), o.get("segments")
    if isinstance(ts, list) and isinstance(os_, list) and len(ts) == len(os_):
        segs = []
        for a, b in zip(ts, os_):
            seg = dict(b) if isinstance(b, dict) else b
            if isinstance(a, dict) and isinstance(b, dict):
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


def merge_for(name: str, theirs, ours):
    if name.endswith("viz_mechanics.json"):
        return merge_mechanics(theirs, ours)
    if name.endswith("niche.config.json"):
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
    if len(argv) != 4:
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
    merged = merge_for(argv[3], theirs, ours)
    Path(argv[3]).write_text(json.dumps(merged, indent=1, ensure_ascii=False) + "\n")
    n = len(merged) if isinstance(merged, list) else len(merged.get("stories", []))
    print(f"[merge_state_json] union -> {n} entries in {Path(argv[3]).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
