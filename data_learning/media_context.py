"""Story-generic media context: wrong-context guard, cross-video reuse ledger,
and a per-source circuit breaker (PR#173 adoptions: media_ranker context
fields, repetition_ledger, circuit_breaker — adapted to the real gateway).

The defect class this kills: the blind judge found a JAPANESE gas-station sign
in an American money story — a high-appeal, on-query, wrong-CONTEXT image.
Stories may declare a top-level ``media_context``:

    "media_context": {"geography": "United States",
                      "language": "en",
                      "exclude_terms": ["cartoon", "clipart"]}

Selection is filtered by candidate METADATA (title/url text — what the keyless
gateway actually provides), never by story slug: the same rules apply to every
story that declares a context. No context declared -> no filtering.

The reuse ledger (``state/curiosity_media_ledger.json``) tracks which asset
URLs the CHANNEL has already shipped, so the fiftieth video does not lean on
the same twelve stock photos: reuse in a DIFFERENT video applies a scoring
penalty (never a hard ban — a genuinely perfect asset can still win).

The breaker stops hammering a provider that is failing repeatedly within a
run: three consecutive failures opens the circuit for the rest of the process
and the fallback ladder reports it honestly instead of eating N timeouts.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPO / "state" / "curiosity_media_ledger.json"

# ---------------------------------------------------------------- active story
_ACTIVE: dict = {"slug": None, "context": {}}


def set_story(slug: str | None, context: dict | None) -> None:
    _ACTIVE["slug"] = slug
    _ACTIVE["context"] = dict(context or {})


def clear() -> None:
    set_story(None, None)


def active_context() -> dict:
    return dict(_ACTIVE["context"])


# ------------------------------------------------------------- context filter
# Compact geography tells: tokens that strongly signal a specific country in a
# stock/commons title. Generic table — a story's own target country is removed
# from the tell set, everything else rejects. Word-boundary matched.
GEO_TELLS: dict[str, tuple[str, ...]] = {
    "japan": ("japan", "japanese", "tokyo", "osaka", "kyoto", "yen"),
    "germany": ("germany", "german", "berlin", "münchen", "munich", "euro"),
    "france": ("france", "french", "paris"),
    "united kingdom": ("uk", "british", "britain", "london", "pound sterling"),
    "china": ("china", "chinese", "beijing", "shanghai", "yuan", "renminbi"),
    "india": ("india", "indian", "delhi", "mumbai", "rupee"),
    "russia": ("russia", "russian", "moscow", "ruble"),
    "south korea": ("korea", "korean", "seoul", "won"),
    "brazil": ("brazil", "brazilian", "sao paulo", "real brasileiro"),
    "mexico": ("mexico", "mexican", "peso"),
    "italy": ("italy", "italian", "rome", "milano"),
    "spain": ("spain", "spanish", "madrid", "barcelona"),
    "united states": ("usa", "american", "america", "us dollar",
                      "new york", "california", "texas"),
}
_FOREIGN_SCRIPTS = ("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "CYRILLIC",
                    "ARABIC", "THAI", "DEVANAGARI")


def _foreign_script_fraction(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    foreign = 0
    for c in letters:
        try:
            name = unicodedata.name(c)
        except ValueError:
            continue
        if any(s in name for s in _FOREIGN_SCRIPTS):
            foreign += 1
    return foreign / len(letters)


def _word_hit(text: str, token: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])",
                     text) is not None


def context_filter(cands: list[dict], context: dict | None = None
                   ) -> tuple[list[dict], list[tuple[str, str]]]:
    """Filter candidates by the story's declared media context. Returns
    (kept, rejections) where rejections are (title, reason) for honest logs.
    No context -> everything kept."""
    ctx = context if context is not None else _ACTIVE["context"]
    if not ctx:
        return cands, []
    target_geo = str(ctx.get("geography", "")).strip().lower()
    language = str(ctx.get("language", "")).strip().lower()
    excludes = [str(t).lower() for t in ctx.get("exclude_terms", [])]
    kept, rejected = [], []
    for c in cands:
        text = f"{c.get('title') or ''} {c.get('url') or ''}".lower()
        reason = None
        for t in excludes:
            if t and _word_hit(text, t):
                reason = f"excluded term {t!r}"
                break
        if reason is None and language == "en" and \
                _foreign_script_fraction(c.get("title") or "") > 0.3:
            reason = "title predominantly in a non-English script"
        if reason is None and target_geo:
            for country, tells in GEO_TELLS.items():
                if country == target_geo:
                    continue
                hit = next((t for t in tells if _word_hit(text, t)), None)
                if hit:
                    reason = f"geography tell {hit!r} ({country}) vs target {target_geo!r}"
                    break
        if reason:
            rejected.append(((c.get("title") or c.get("url") or "")[:60], reason))
        else:
            kept.append(c)
    return kept, rejected


# ------------------------------------------------------------ circuit breaker
class Breaker:
    """Per-source consecutive-failure breaker, process-scoped. Three straight
    failures open the circuit for that source; any success closes it."""

    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self._fails: dict[str, int] = {}
        self._open: set[str] = set()

    def allow(self, source: str) -> bool:
        return source not in self._open

    def record(self, source: str, ok: bool) -> None:
        if ok:
            self._fails[source] = 0
            self._open.discard(source)
            return
        n = self._fails.get(source, 0) + 1
        self._fails[source] = n
        if n >= self.threshold and source not in self._open:
            self._open.add(source)
            print(f"[media] circuit OPEN for {source!r} after {n} consecutive "
                  "failures — skipping it for the rest of this run")

    def report(self) -> dict:
        return {"open": sorted(self._open), "fails": dict(self._fails)}


BREAKER = Breaker()


# ---------------------------------------------------------- cross-video reuse
def _load_ledger() -> dict:
    if LEDGER_PATH.exists():
        try:
            return json.loads(LEDGER_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {"assets": {}}


def _url_key(url: str) -> str:
    return sha256(url.split("?")[0].encode()).hexdigest()[:20]


def prior_use_count(url: str, exclude_slug: str | None = None) -> int:
    """How many OTHER videos already used this asset."""
    rec = _load_ledger()["assets"].get(_url_key(url))
    if not rec:
        return 0
    slugs = {u["slug"] for u in rec.get("uses", [])}
    slugs.discard(exclude_slug)
    return len(slugs)


def reuse_penalty(url: str, slug: str | None = None) -> float:
    """Score multiplier: 1.0 unused elsewhere, 0.7 one other video, 0.45 two+.
    A penalty, never a ban — a perfect asset can still win."""
    n = prior_use_count(url, exclude_slug=slug or _ACTIVE["slug"])
    return 1.0 if n == 0 else (0.7 if n == 1 else 0.45)


def record_use(url: str, title: str = "", slug: str | None = None) -> None:
    slug = slug or _ACTIVE["slug"]
    if not slug or not url:
        return
    ledger = _load_ledger()
    key = _url_key(url)
    rec = ledger["assets"].setdefault(key, {"url": url.split("?")[0],
                                            "title": title[:120], "uses": []})
    if not any(u["slug"] == slug for u in rec["uses"]):
        rec["uses"].append({"slug": slug,
                            "at": datetime.now(timezone.utc).isoformat()})
    try:
        from shared.fsutil import atomic_write_json
        atomic_write_json(LEDGER_PATH, ledger)
    except Exception:  # noqa: BLE001 — ledger is advisory, never blocks a render
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n")
