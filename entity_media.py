"""Hard-set per-noun media for every shot.

Problem: the renderer's existing fallback chain
(shot.image_url -> topic_video pool -> topic_media -> stock) depends on
the morning routine carefully attaching a Wikipedia / Commons image for
every proper noun in the script. When the routine forgets, the shot
falls all the way through to generic Pexels/Pixabay stock and we end
up narrating "Putin said today..." over a stock shot of an unrelated
politician at a podium.

This module enforces the rule at the code level: BEFORE rendering,
scan the script for proper nouns, resolve a real photo for each one,
and pin it to the matching shot. The routine's existing image_urls
are respected (their careful manual work always wins); we only fill
holes.

Scope:
  * Proper nouns only (capitalized phrases) — common nouns like
    "meteor" or "hurricane" stay on the topic_video pool / stock path.
  * Image URLs only — videos already get the pool-level treatment.
  * Cached on disk by entity, so the same name across multiple
    packages doesn't re-fetch Wikipedia/Commons every day.

Pipeline integration point: `make_explainer_stacked.build_from_package`
calls `enrich_package(pkg)` right before constructing Shot objects.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


# Words that get auto-capitalized at sentence start but are NEVER
# part of a real entity name. The proper-noun regex grabs them when
# followed by another capitalized word ("The FAA", "Today Trump",
# "After Putin") and we strip them post-match.
#
# Critical: "New", "Old", "First", "Second", etc. are intentionally
# NOT here — they're commonly part of real entity names ("New Jersey",
# "Old Trafford", "First Amendment", "Second Avenue"). The list is
# narrowed to true sentence-starters only.
_STOPWORDS = frozenset({
    # Articles
    "the", "a", "an",
    # Connectives / conjunctions
    "and", "or", "but", "yet", "so", "if", "as", "that",
    # Sentence-initial referents
    "this", "these", "those", "it", "they", "we", "you", "i", "he", "she",
    "his", "her", "their", "its", "our", "your", "my",
    # Counting words ("One scientist said...") — proper nouns rarely
    # start with these and they cause false positives like "One Wi-Fi"
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten",
    # Temporal sentence-starters
    "today", "yesterday", "tomorrow", "now", "then", "soon", "later",
    "once", "while",
    # Subordinating conjunctions
    "after", "before", "during", "since", "though", "although",
    "because", "if", "unless", "until", "when", "where", "why",
    "what", "who", "which", "how",
    # Prepositions that can start a sentence
    "for", "to", "from", "by", "with", "in", "on", "at", "of",
    "over", "under",
    # Pronoun forms
    "him", "us", "them",
    # Demonyms / generic group nouns
    "americans", "american",
    # Common adverbs that auto-capitalize
    "back", "still", "even", "just", "also", "very", "always", "never",
    "ever", "much", "many", "few", "all", "some", "any", "every",
    # Time units. "Second" is intentionally omitted — collides with
    # "Second Avenue", "Second Amendment", etc. The few false-positive
    # sentence-starts using "Second" as a time unit are tolerable.
    "year", "month", "week", "day", "hour", "minute",
    "years", "months", "weeks", "days", "hours",
    # Months — rarely the subject of a short; usually scaffolding
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    # Weekdays — same logic
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
})


# Match a capitalized word, optionally followed by more capitalized
# words. Allows internal apostrophes (`O'Reilly`) and hyphens
# (`SpaceX-Blue`). Trailing `'s` is stripped post-match so we get
# the bare entity name.
_PROPER_NOUN_RE = re.compile(
    r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)*)\b"
)

# Caps a sequence at this many words to avoid pulling in whole
# headlines as a single "entity" (e.g. "United States Of America" is
# fine; "Trump Announces New Tariff On China" is not).
_MAX_ENTITY_WORDS = 4


def extract_proper_nouns(script: str) -> list[str]:
    """Return proper-noun candidates from `script`, in first-mention
    order, deduplicated. Handles three messy cases the raw regex
    can't:
      1. `Microsoft's` -> `Microsoft` (drop possessive)
      2. `The FAA` -> `FAA` (drop leading stopwords; the sentence
         started with "The" and the regex grabbed it because the next
         word was also capitalized)
      3. Trailing stopwords (rare, e.g. `Apple And`)
    Drops single-letter results and pure-stopword phrases.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in _PROPER_NOUN_RE.findall(script):
        cand = re.sub(r"'s\b", "", raw).strip()
        if not cand:
            continue
        # Walk in from both ends, dropping stopword tokens. Stops as
        # soon as we hit a real-noun token on either side.
        words = cand.split()
        while words and words[0].lower() in _STOPWORDS:
            words = words[1:]
        while words and words[-1].lower() in _STOPWORDS:
            words = words[:-1]
        if not words:
            continue
        if len(words) > _MAX_ENTITY_WORDS:
            continue
        cand = " ".join(words)
        if len(cand) < 2:
            continue
        key = cand.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out


# ---------- Cache ----------

_CACHE_PATH = (Path(__file__).resolve().parent / "state"
               / "entity_media_cache.json")


def _load_cache() -> dict[str, str]:
    if not _CACHE_PATH.exists():
        return {}
    try:
        return json.loads(_CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")
    except OSError as e:
        print(f"  [entity_media cache save fail] {e}")


# ---------- Resolution ----------

def resolve_entity_media(entity: str, context: str = "") -> str | None:
    """Return a usable image URL for `entity`, or None if no source
    has it. Wraps `topic_media.search()` which already hits Wikipedia
    -> Commons -> GDELT news og:image in that order.

    Cached on disk keyed by entity (case-folded). Empty-string
    cache value means "tried, no media available" — we don't retry
    those on the next render unless the cache file is wiped.
    """
    key = entity.lower()
    cache = _load_cache()
    if key in cache:
        return cache[key] or None
    chosen = ""
    try:
        import topic_media
        urls = topic_media.search(entity, context)
        if urls:
            chosen = urls[0]
    except Exception as e:  # noqa: BLE001
        print(f"  [entity_media resolve fail] {entity!r}: {e}")
    cache[key] = chosen
    _save_cache(cache)
    return chosen or None


# ---------- Enrichment ----------

def enrich_package(pkg: dict, *, verbose: bool = True) -> dict:
    """Auto-attach `image_url` to every shot whose phrase mentions a
    proper noun that doesn't already have media. Mutates `pkg` in
    place and returns it.

    Decision rules:
      * Shots with an existing `image_url` (or legacy `image`) are
        never overwritten — the routine's manual picks always win.
      * Entities found in the script but not present in any shot's
        phrase are logged as "uncoverable" so the package author can
        see which shots they should have built.
      * Multiple entities in the same shot phrase: the first one
        wins. (Future work: pick the most distinctive entity.)
    """
    script = pkg.get("script") or ""
    if not script:
        return pkg

    nouns = extract_proper_nouns(script)
    if verbose:
        print(f"  [entity_media] {len(nouns)} proper nouns: "
              f"{nouns if len(nouns) <= 10 else nouns[:10] + ['...']}")
    if not nouns:
        return pkg

    title = pkg.get("title") or ""
    shots = pkg.get("shots") or []

    attached = 0
    missed_shots: list[str] = []   # entities with no matching shot
    missed_media: list[str] = []   # entities matched but no media found

    for entity in nouns:
        e_lower = entity.lower()
        # Find the first shot whose phrase contains this entity.
        target = None
        for s in shots:
            phrase = (s.get("phrase") or "").lower()
            if e_lower in phrase:
                target = s
                break
        if target is None:
            missed_shots.append(entity)
            continue
        # Respect routine's existing work.
        if target.get("image_url") or target.get("image"):
            continue
        url = resolve_entity_media(entity, context=title)
        if not url:
            missed_media.append(entity)
            continue
        target["image_url"] = url
        attached += 1
        if verbose:
            print(f"  [entity_media] {entity!r} -> {url[:90]}")

    if verbose:
        if attached:
            print(f"  [entity_media] attached {attached} entity image(s)")
        if missed_media:
            print(f"  [entity_media] no media for: {missed_media}")
        if missed_shots:
            print(f"  [entity_media] mentioned but no shot covers: "
                  f"{missed_shots}")
    return pkg


if __name__ == "__main__":
    import sys
    # Smoke test: print proper nouns from a script passed via stdin.
    script = sys.stdin.read() if not sys.stdin.isatty() else (
        "Putin met Trump in Washington. Microsoft and Anthropic signed a "
        "deal worth 3 billion dollars. The FBI investigated. Today the "
        "deal closed, ending Project Stargate."
    )
    print("Script:")
    print(script)
    print()
    print("Proper nouns extracted:")
    for n in extract_proper_nouns(script):
        print(f"  - {n}")
