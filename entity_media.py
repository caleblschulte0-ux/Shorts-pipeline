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
import urllib.error
import urllib.request
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


# ---------- LLM-based visual extraction ----------
#
# Regex catches proper nouns but doesn't know which ones MATTER to the
# story, doesn't disambiguate ("Apple" the company vs "apple" the fruit),
# and can't suggest the disambiguating context that makes Commons /
# Wikipedia / GDELT searches actually return the right photo. An LLM
# trip costs one call per package and fixes all three problems.
#
# The LLM is asked for {entity, context, phrase} triples:
#   - entity: the searchable thing ("Tim Cook", "WWDC 2026 keynote")
#   - context: extra disambiguating keywords to bias image search
#     ("Apple CEO", "Apple developer conference San Jose")
#   - phrase: verbatim substring of the script to pin against a shot
#
# If the LLM dispatch isn't wired (no API keys, network out), this
# returns None and the regex path takes over.

_VISUAL_SYSTEM = """You annotate YouTube Shorts scripts with the specific real-world \
visuals an editor needs to find. For each concrete thing mentioned in the \
script — a person, company, product, place, event, named object — output ONE \
{entity, context, phrase} triple. Output strict JSON only, no prose."""


_VISUAL_USER = """Title: {title}

Script:
{script}

For every concrete, photographable thing in the script — every person, \
company, product line, named place, named event, named object — output one \
triple in this exact JSON shape:

{{"visuals": [
  {{"entity": "Tim Cook",
    "context": "Apple CEO keynote",
    "phrase": "Tim Cook"}},
  {{"entity": "WWDC 2026",
    "context": "Apple worldwide developers conference",
    "phrase": "at WWDC"}}
]}}

Rules:
- entity = the SEARCHABLE thing. Real proper nouns, not generic descriptors. \
"Tim Cook" yes, "the CEO" no. "Siri" yes, "the assistant" no.
- context = 2-6 extra keywords that DISAMBIGUATE for image search. For \
"Apple" the company, context is "Apple Inc tech logo headquarters" — NOT \
"red fruit". For "Mercury" the planet, context is "planet space NASA" — NOT \
"Roman god".
- phrase = VERBATIM substring of the script (case-sensitive copy-paste) so \
the renderer can pin this visual to the right shot. Pick the shortest \
substring that uniquely identifies the mention.
- Skip generic things ("the country", "the company", "the weather") — only \
named, photographable things.
- Skip abstract nouns ("freedom", "the economy", "growth") — same reason.
- Cap at 12 entries. If the script has more, pick the most STORY-CRITICAL \
ones (subject + main actions, not throwaway references).
- If two mentions point to the same entity, output it once (use the first \
mention's phrase).

Output JSON only."""


# Process-wide flag so the LLM-skip message prints once instead of
# once per package when the validator/enrich loops over a whole batch.
_LLM_SKIP_LOGGED = False


def extract_visuals_llm(script: str, title: str = "") -> list[dict] | None:
    """Ask the LLM for {entity, context, phrase} triples. Returns None
    when the LLM path is unavailable (no API key, network failure,
    malformed response) so the caller can fall back to the regex
    extractor. Never raises."""
    global _LLM_SKIP_LOGGED
    if not script.strip():
        return None
    try:
        from script_generator import _call_llm
    except Exception:
        return None
    user = _VISUAL_USER.format(script=script, title=title or "(none)")
    try:
        raw = _call_llm(_VISUAL_SYSTEM, user)
    except Exception as e:  # noqa: BLE001
        if not _LLM_SKIP_LOGGED:
            print(f"  [entity_media LLM skip] {type(e).__name__}: "
                  f"{str(e).splitlines()[0]}")
            _LLM_SKIP_LOGGED = True
        return None
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  [entity_media LLM json parse fail] {e}")
        return None
    items = data.get("visuals") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    out: list[dict] = []
    seen: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        entity = (it.get("entity") or "").strip()
        context = (it.get("context") or "").strip()
        phrase = (it.get("phrase") or "").strip()
        if not entity or not phrase:
            continue
        key = entity.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"entity": entity, "context": context, "phrase": phrase})
    return out or None


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

    Cached on disk keyed by entity+context (case-folded). Including the
    context disambiguates collisions across packages — "Apple" the
    company on a WWDC story shouldn't be cached against "apple" the
    fruit on a farming story. Empty-string cache value means "tried,
    no media available" — we don't retry those on the next render
    unless the cache file is wiped.
    """
    ctx_norm = " ".join((context or "").lower().split())[:80]
    key = f"{entity.lower()}|{ctx_norm}" if ctx_norm else entity.lower()
    cache = _load_cache()
    if key in cache:
        return cache[key] or None
    chosen = ""
    try:
        import topic_media
        urls = topic_media.search(entity, context)
        # Take the first candidate that actually resolves to an image.
        # Wikipedia API results are nearly always live, but GDELT
        # og:image links rot within days — skip the dead ones instead
        # of caching a 404 we'll render a blank shot from.
        for u in urls or []:
            if url_is_image(u):
                chosen = u
                break
    except Exception as e:  # noqa: BLE001
        print(f"  [entity_media resolve fail] {entity!r}: {e}")
    cache[key] = chosen
    _save_cache(cache)
    return chosen or None


# ---------- URL verification ----------

_VERIFY_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120 Safari/537.36")


def url_is_image(url: str, timeout: float = 8.0) -> bool:
    """True only when `url` resolves (following redirects) to a 200
    with an image/* content-type.

    This is the trust boundary for routine-supplied image URLs. The
    morning routine writes Wikipedia filenames from memory and the
    LLM hallucinates plausible-looking ones about half the time —
    e.g. `Brad_Paisley_(2023).jpg` 302s to a Commons 404. Before this
    check, a fabricated URL silently fell through to generic stock
    and we'd caption "BRAD PAISLEY" over a random stock-photo guy.

    HEAD first (cheap); some CDNs reject HEAD with 405, so fall back
    to a Range-limited GET before giving up."""
    for method in ("HEAD", "GET"):
        try:
            headers = {"User-Agent": _VERIFY_UA}
            if method == "GET":
                headers["Range"] = "bytes=0-0"
            req = urllib.request.Request(url, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if resp.status in (200, 206) and ctype.startswith("image/"):
                    return True
                if resp.status in (200, 206):
                    # Resolved but not an image (e.g. an HTML error page
                    # served with 200) — reject, don't retry.
                    return False
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue          # server dislikes HEAD — retry as GET
            return False
        except Exception:  # noqa: BLE001 — timeouts, DNS, TLS: all unusable
            return False
    return False


def verify_shot_urls(pkg: dict, *, verbose: bool = True) -> int:
    """Drop every routine-supplied image URL that doesn't actually
    resolve to an image. Returns the number of URLs dropped.

    Runs BEFORE entity enrichment so a dropped URL leaves a hole that
    `enrich_package` then re-fills through the Wikipedia-API path
    (`resolve_entity_media`), which only returns URLs it got from the
    API itself — real files, not guesses."""
    dropped = 0
    for s in pkg.get("shots") or []:
        url = s.get("image_url") or s.get("image")
        if not url:
            continue
        if url_is_image(url):
            continue
        if verbose:
            print(f"  [entity_media] BROKEN url dropped "
                  f"({(s.get('phrase') or '?')[:30]!r}): {url[:80]}")
        s.pop("image_url", None)
        s.pop("image", None)
        dropped += 1
    if verbose and dropped:
        print(f"  [entity_media] dropped {dropped} unresolvable image "
              f"url(s); entity resolution will re-fill from Wikipedia")
    return dropped


# ---------- Enrichment ----------

def _match_shot(shots: list[dict], phrase: str, entity: str) -> dict | None:
    """Find the best shot for a (phrase, entity) pair. Prefers an exact
    substring match on the LLM-supplied phrase (case-insensitive); falls
    back to the entity name. The first matching shot wins so order in
    `shots` controls placement when there are multiple candidates."""
    p_lower = phrase.lower()
    if p_lower:
        for s in shots:
            sp = (s.get("phrase") or "").lower()
            if not sp:
                continue
            if sp in p_lower or p_lower in sp:
                return s
    e_lower = entity.lower()
    if e_lower:
        for s in shots:
            sp = (s.get("phrase") or "").lower()
            if e_lower in sp:
                return s
    return None


def enrich_package(pkg: dict, *, verbose: bool = True) -> dict:
    """Auto-attach `image_url` to every shot whose phrase mentions a
    real-world entity that doesn't already have media. Mutates `pkg`
    in place and returns it.

    Strategy:
      1. Ask the LLM for {entity, context, phrase} triples — this
         picks story-critical entities, disambiguates them ("Apple
         Inc" vs "apple fruit"), and supplies extra search context.
      2. If the LLM dispatch fails (no key, network out, bad JSON),
         fall back to the regex proper-noun extractor with title as
         context.

    Decision rules:
      * Shots with an existing `image_url` (or legacy `image`) are
        never overwritten — the routine's manual picks always win.
      * Entities the LLM names but no shot matches are logged as
        "uncoverable" so the package author can see what they missed.
      * Multiple entities in the same shot: first one to attach wins.
    """
    script = pkg.get("script") or ""
    if not script:
        return pkg

    title = pkg.get("title") or ""
    shots = pkg.get("shots") or []

    # 0. Trust boundary: verify every routine-supplied URL actually
    # resolves to an image. Fabricated Wikipedia filenames get dropped
    # here, leaving holes the entity-resolution pass below re-fills
    # with REAL files from the Wikipedia API.
    verify_shot_urls(pkg, verbose=verbose)

    visuals = extract_visuals_llm(script, title=title)
    used_llm = visuals is not None
    if not visuals:
        # Fallback: regex extractor, with title as context.
        nouns = extract_proper_nouns(script)
        visuals = [{"entity": n, "context": title, "phrase": n} for n in nouns]

    if verbose:
        src = "LLM" if used_llm else "regex"
        names = [v["entity"] for v in visuals]
        preview = names if len(names) <= 10 else names[:10] + ["..."]
        print(f"  [entity_media] {len(visuals)} visuals via {src}: {preview}")
    if not visuals:
        return pkg

    attached = 0
    missed_shots: list[str] = []   # entities with no matching shot
    missed_media: list[str] = []   # entities matched but no media found

    for v in visuals:
        entity = v["entity"]
        context = v.get("context") or title
        phrase = v.get("phrase") or entity

        target = _match_shot(shots, phrase, entity)
        if target is None:
            missed_shots.append(entity)
            continue
        # Stash entity + context on the matched shot so the renderer can
        # do a per-shot topic_video search with this same disambiguating
        # context. Set even when an image_url already exists — videos
        # are a separate channel and benefit from the same context.
        target.setdefault("pin_query", entity)
        target.setdefault("pin_context", context)
        if target.get("image_url") or target.get("image"):
            continue
        url = resolve_entity_media(entity, context=context)
        if not url:
            missed_media.append(entity)
            continue
        target["image_url"] = url
        attached += 1
        if verbose:
            print(f"  [entity_media] {entity!r} (ctx: {context[:40]!r}) "
                  f"-> {url[:80]}")

    if verbose:
        if attached:
            print(f"  [entity_media] attached {attached} entity image(s)")
        if missed_media:
            print(f"  [entity_media] no media for: {missed_media}")
        if missed_shots:
            print(f"  [entity_media] mentioned but no shot covers: "
                  f"{missed_shots}")
    return pkg


def validate_package(pkg: dict) -> dict:
    """Dry-run coverage analysis for a package. Returns a report dict
    with counts and the lists of uncovered entities so a pre-flight
    script can flag problem packages BEFORE render time, when the
    routine author can still fix the package's shot list.

    Does NOT call resolve_entity_media (no network). The shot-coverage
    check is the cheap, deterministic half of enrichment; actual
    image lookup is deferred to render time so the validator is fast
    enough to run on every package in the daily batch.
    """
    script = pkg.get("script") or ""
    shots = pkg.get("shots") or []
    visuals = extract_visuals_llm(script, title=pkg.get("title", ""))
    used_llm = visuals is not None
    if not visuals:
        nouns = extract_proper_nouns(script)
        visuals = [{"entity": n, "context": pkg.get("title", ""),
                    "phrase": n} for n in nouns]

    matched: list[str] = []
    uncovered: list[str] = []
    for v in visuals:
        if _match_shot(shots, v.get("phrase") or "", v["entity"]) is not None:
            matched.append(v["entity"])
        else:
            uncovered.append(v["entity"])
    return {
        "source": "llm" if used_llm else "regex",
        "total_visuals": len(visuals),
        "matched": matched,
        "uncovered": uncovered,
        "coverage_pct": round(100.0 * len(matched) / max(1, len(visuals)), 1),
    }


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
