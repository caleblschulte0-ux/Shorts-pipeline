#!/usr/bin/env python3
"""Storyline auto-detection — finds the ARCS hiding in the clip corpus.

A story (a beef that starts, escalates, resolves; a challenge set up and
paid off) is spread across MANY clips from different streamers and days.
No single slot ever sees it. This module looks at the whole corpus — what
we've already posted plus a wide multi-window discovery sweep — and
clusters clips by the PEOPLE they share, so the showrunner brain
(`author.order_story`) can judge which clusters are real beginning-to-end
stories worth compiling.

Design constraints:
- Pure heuristics here, judgement in the brain: this module only proposes
  candidate clusters (cheap, offline, deterministic); `order_story` is the
  strict gate that rejects piles that aren't stories.
- A cluster must show CHANGE OVER TIME (>=2 distinct moments on >=2
  distinct dates) — one hot afternoon clipped twice is not an arc.
- Compilations get their own identity (`story_key`, hashed from the member
  set) so the posted-log's never-repeat law applies to the STORY without
  burning its member clips for single-slot use — members may already be
  posted (that's the point: we posted the beef, we posted the makeup; the
  compilation is the new artifact that tells the whole thing).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

# Ordinary Title-Case words that must never read as a person. Our authored
# titles capitalize every word, so person detection = capitalized token NOT
# in this list (plus every known allowlist streamer, matched anywhere).
_STOP = set("""
a an the and or but nor so yet after before during while when where what who
whom whose why how this that these those his her him hers their theirs them
they she he it its we our ours you your yours i me my mine us then than as at
by for from in into of off on onto out over to under up down with without
about against between through
gets get got getting keeps keep kept makes make made making calls call called
calling goes go went going comes come came coming takes take took taking
watches watch watched watching loses lose lost losing wins win won winning
starts start started starting ends end ended ending tries try tried trying
says say said saying tells tell told telling asks ask asked asking
finds find found finding gives give gave giving turns turn turned turning
breaks break broke breaking falls fall fell falling hits hit hitting
leaves leave left leaving runs run ran running walks walk walked walking
screams scream screamed screaming yells yell yelled yelling laughs laugh
laughed laughing cries cry cried crying panics panic panicked panicking
reacts react reacted reacting responds respond responded responding
denies deny denied denying refuses refuse refused refusing
finally instantly suddenly literally actually really totally completely
absolutely accidentally immediately again never always still just only even
whole entire full big huge wild crazy insane new old first last next one two
three every all some no not cant wont dont didnt doesnt isnt arent wasnt
werent
stream streamer streamers streaming live chat clip clips moment reaction
everyone everybody someone somebody anyone nobody people guy girl man woman
dude bro
day days night morning today yesterday tomorrow week hour minute second
thing things stuff way ways time times
""".split())


def clip_key(url: str) -> str:
    """Canonical clip identity — the trailing URL slug, lowercased (same
    normalization as run_third._clip_key, duplicated here to keep this
    module import-light)."""
    tail = str(url or "").rstrip("/").rsplit("/", 1)[-1]
    return tail.split("?")[0].lower()


def story_key(member_urls: list[str]) -> str:
    """Identity of a compilation = hash of its (sorted, canonical) member
    set. The posted-log never-repeat law keys stories on this, so the same
    arc can never ship twice while member clips stay reusable."""
    keys = sorted({clip_key(u) for u in member_urls if u})
    return "story-" + hashlib.sha1("|".join(keys).encode()).hexdigest()[:16]


def _entities(title: str, streamer: str, known: set[str]) -> set[str]:
    """People a clip is about: its own streamer, any KNOWN streamer named in
    the title (matched case-insensitively anywhere), and capitalized
    name-like tokens that survive the stoplist (catches people outside the
    allowlist — 'Cudi', 'Tfue', 'Dean')."""
    def _norm(s: str) -> str:
        # alnum-only lowercase so "caseoh_" and "CaseOh" are one person
        return re.sub(r"[^a-z0-9]", "", str(s).lower())

    ents = set()
    if streamer:
        ents.add(_norm(streamer))
    low = f" {str(title).lower()} "
    for k in known:
        if k and re.search(rf"\b{re.escape(k)}\b", low):
            ents.add(_norm(k))
    for tok in re.findall(r"\b[A-Z][a-zA-Z]{2,15}\b", str(title)):
        t = _norm(tok)
        if t and t not in _STOP and not t.isdigit():
            ents.add(t)
    ents.discard("")
    return ents


def corpus_from_log(log: dict, days: int = 30) -> list[dict]:
    """Posted-log entries usable as story material: every twitch_clip entry
    (INCLUDING qa-rejected ones — rejection judged the standalone render,
    not the moment) inside the lookback window. Deduped by clip key."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out, seen = [], set()
    for slug, v in (log.get("posted") or {}).items():
        url = v.get("source_url")
        if not url or v.get("kind") not in (None, "twitch_clip"):
            continue
        if str(v.get("ts", "")) < cutoff:
            continue
        ck = clip_key(url)
        if ck in seen:
            continue
        seen.add(ck)
        out.append({"source_url": url,
                    "title": str(v.get("title", "")),
                    "channel": str(v.get("streamer", "")),
                    "date": str(v.get("ts", ""))[:10],
                    "series": v.get("series", ""),
                    "posted": not slug.startswith("rejected-")})
    return out


def from_discovery(pool: list[dict]) -> list[dict]:
    """Normalize clip_edit.discover() items to corpus shape. Date is
    derived from the helix age when present; unknown otherwise."""
    now = datetime.now(timezone.utc)
    out = []
    for c in pool:
        url = c.get("url")
        if not url:
            continue
        date = ""
        if c.get("age_h"):
            date = (now - timedelta(hours=float(c["age_h"]))) \
                .strftime("%Y-%m-%d")
        out.append({"source_url": url, "title": str(c.get("title", "")),
                    "channel": str(c.get("channel", "")), "date": date,
                    "views": c.get("views", 0), "posted": False})
    return out


def find_clusters(corpus: list[dict], known_streamers: list[str],
                  max_members: int = 8) -> list[dict]:
    """Group the corpus into candidate storylines by shared people.

    Buckets on PAIRS of entities (two people = the classic beef/friendship
    arc) and on solo known streamers (a personal arc, held to a stricter
    bar). Every cluster must involve at least one known streamer, contain
    >=2 distinct clips, and span >=2 distinct dates — an arc needs change
    over time. Returns clusters best-first:
    [{"who": [...], "clips": [...], "score": float}]."""
    known = {re.sub(r"[^a-z0-9]", "", str(k).lower())
             for k in known_streamers if k} - {""}
    items = []
    seen = set()
    for c in corpus:
        ck = clip_key(c.get("source_url", ""))
        if not ck or ck in seen:
            continue
        seen.add(ck)
        ents = _entities(c.get("title", ""), c.get("channel", ""), known)
        if ents:
            items.append((c, ents))

    buckets: dict[tuple, list[dict]] = {}
    for c, ents in items:
        el = sorted(ents)
        for i, a in enumerate(el):          # pair buckets
            for b in el[i + 1:]:
                if a in known or b in known:
                    buckets.setdefault((a, b), []).append(c)
        for a in el:                         # solo buckets (known only)
            if a in known:
                buckets.setdefault((a,), []).append(c)

    clusters = []
    for who, clips in buckets.items():
        uniq = {clip_key(c["source_url"]): c for c in clips}
        clips = sorted(uniq.values(), key=lambda c: c.get("date", ""))
        dates = {c["date"] for c in clips if c.get("date")}
        if len(clips) < 2 or len(dates) < 2:
            continue                        # no change over time = no arc
        if len(who) == 1 and (len(clips) < 3 or len(dates) < 3):
            continue                        # solo arcs held to a higher bar
        score = (len(dates) * 10 + len(clips) * 3
                 + (8 if len(who) == 2 else 0))
        clusters.append({"who": list(who),
                         "clips": clips[-max_members:],
                         "score": score})
    clusters.sort(key=lambda c: -c["score"])
    # one cluster per real storyline: name aliases ("kai" vs "kaicenat" vs
    # "cenat") spawn near-identical clusters, so drop any cluster whose
    # member overlap with an already-kept one exceeds 60% (Jaccard) — the
    # kept one scored higher and tells the same story.
    kept, covered = [], []
    for cl in clusters:
        keys = {clip_key(c["source_url"]) for c in cl["clips"]}
        if any(len(keys & k) / max(1, len(keys | k)) >= 0.5 for k in covered):
            continue
        covered.append(keys)
        kept.append(cl)
    return kept
