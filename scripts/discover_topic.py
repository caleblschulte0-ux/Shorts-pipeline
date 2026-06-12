#!/usr/bin/env python3
"""Discover today's trending topics that are actually video-able.

Pulls Google's "Daily Search Trends" RSS feed, which gives us raw search
trends with the news headlines that drove each spike. We filter out
topics that don't make good faceless-explainer fodder (live sports
games, celebrity obits, niche political flare-ups) and rank the rest by
search volume plus a topic-friendliness score.

Output: a ranked list of topic dicts, each with the raw query, the news
context, and a confidence score. Downstream the script generator picks
the top one and asks Claude to turn it into a 25-second script.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


TRENDS_RSS = "https://trends.google.com/trending/rss?geo=US&hours=24"

# Namespace used by the Google Trends RSS extension.
NS = {"ht": "https://trends.google.com/trending/rss"}


# Keyword scoring. Positive keywords mean the topic probably has a story
# we can explain in 60-80 words with stock footage; negative keywords
# flag topics that fall apart on a faceless channel (live games,
# specific dead people, individual political horserace stuff).
POSITIVE_KEYWORDS = {
    # "Data Minute" is a broad DATA-EXPLAINER channel, not a finance channel.
    # The biggest weights go to curiosity-gap topics — science, space, nature,
    # the human body, history, records, mysteries — the stuff that makes people
    # stop scrolling. Economic/news terms stay in (they can still make a good
    # chart) but are deliberately weighted LOW so they stop dominating picks.

    # Curiosity / science / nature / space  (the channel's bread and butter)
    "discovery": 9, "discovered": 9, "scientists": 8, "study": 7, "research": 6,
    "space": 9, "nasa": 9, "universe": 9, "galaxy": 8, "planet": 8, "asteroid": 8,
    "ocean": 8, "deepest": 8, "species": 8, "animal": 7, "extinct": 8, "fossil": 8,
    "ancient": 8, "dinosaur": 8, "brain": 7, "human": 6, "body": 6, "dna": 7,
    "mystery": 8, "rare": 7, "record": 8, "largest": 8, "biggest": 8, "deadliest": 9,
    "oldest": 7, "fastest": 7, "history": 6, "map": 6, "why": 5, "how": 5,
    # Tech / business (kept, modest)
    "layoffs": 5, "recall": 6, "shortage": 5, "bankruptcy": 5, "ban": 5,
    "launches": 6, "leak": 5, "leaked": 5, "discontinued": 5,
    # Economy (deliberately low — was the source of the boring-topic drift)
    "inflation": 3, "housing": 2, "rent": 2, "wages": 2, "tax": 2,
    "tariff": 3, "recession": 3, "stock": 3,
    # Phenomena
    "viral": 6, "ai": 5, "scandal": 5, "exposed": 5,
}

# Hard skips. Any of these in the trend or news text → score below floor.
NEGATIVE_KEYWORDS = {
    # Live sports / time-locked
    "vs": -20, "vs.": -20, "match": -15, "game": -8, "score": -10,
    "playoffs": -20, "championship": -15, "tournament": -10,
    "nfl": -15, "nba": -15, "mlb": -15, "nhl": -15, "ncaa": -15,
    "premier league": -20, "champions league": -20, "world cup": -20,
    "french open": -20, "wimbledon": -20, "us open": -20,
    "live updates": -20, "live blog": -20, "today's game": -20,
    # Death / obit
    "dies": -50, "died": -50, "death": -30, "passes away": -50,
    "obituary": -50, "tribute": -30, "in memoriam": -50,
    "killed": -30, "murdered": -30, "shot dead": -50,
    # Adult / sensitive
    "porn": -100, "onlyfans": -50, "nude": -50,
    # Politics horserace (channel-risk)
    "primary election": -20, "midterms": -20, "campaign rally": -20,
    "endorses": -10,
}

# Domain hints: news source URLs that suggest a topic is/isn't usable.
SOURCE_PENALTY = {
    "espn.com": -25, "foxsports.com": -25, "skysports.com": -25,
    "rolandgarros.com": -30, "wimbledon.com": -30,
}


@dataclass
class Topic:
    query: str
    traffic: int = 0
    score: float = 0.0
    headlines: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    # Populated by the Groq ranker — a one-line hook suggestion for the
    # short explainer. Not set by raw discovery.
    angle: str | None = None
    # ISO-8601 UTC publish time when the source exposed one (RSS <pubDate>,
    # Reddit created_utc). None when the feed didn't carry one. Used to
    # filter stale items and bias the ranker toward fresh stories.
    published_at: str | None = None


def _parse_traffic(s: str | None) -> int:
    """'2000+' / '50,000+' / '100K+' -> integer estimate."""
    if not s:
        return 0
    s = s.strip().rstrip("+").replace(",", "").lower()
    mult = 1
    if s.endswith("k"):
        mult = 1_000
        s = s[:-1]
    elif s.endswith("m"):
        mult = 1_000_000
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def _http_get(url: str, *, ua: str | None = None, timeout: int = 15) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": ua or "Mozilla/5.0 (shorts-pipeline)",
            "Accept": "application/rss+xml, application/xml, application/json, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _fetch_trends(geo: str = "US") -> bytes:
    return _http_get(f"https://trends.google.com/trending/rss?geo={geo}&hours=24",
                     ua="shorts-pipeline/1.0")


def _score(topic: Topic) -> float:
    """Heuristic score: higher is more video-able. Combines keyword
    sentiment with search traffic. The negative keywords act as hard
    skips since they easily reach -100 and dominate any positive."""
    text = " ".join([
        topic.query,
        *topic.headlines,
        *topic.snippets,
    ]).lower()

    kw_score = 0.0
    for kw, w in POSITIVE_KEYWORDS.items():
        if re.search(rf"\b{re.escape(kw)}\b", text):
            kw_score += w
    for kw, w in NEGATIVE_KEYWORDS.items():
        if kw in text:  # substring match — these are usually multi-word
            kw_score += w
    for src in topic.sources:
        for needle, w in SOURCE_PENALTY.items():
            if needle in src:
                kw_score += w

    # Traffic contributes log-scaled. 1k -> +3, 10k -> +4, 100k -> +5.
    import math
    traffic_score = math.log10(max(1, topic.traffic)) if topic.traffic else 0

    return kw_score + traffic_score


def discover(rss_bytes: bytes | None = None, min_score: float = 4.0,
             geo: str = "US") -> list[Topic]:
    """Single-source legacy discovery: Google Trends Daily for one geo,
    keyword-heuristic filtered. Kept for backward compat / dry runs
    when no LLM key is available."""
    raw = rss_bytes if rss_bytes is not None else _fetch_trends(geo)
    root = ET.fromstring(raw)
    items = root.findall("./channel/item")

    topics: list[Topic] = []
    for it in items:
        t = Topic(query=(it.findtext("title") or "").strip())
        t.traffic = _parse_traffic(it.findtext("ht:approx_traffic", namespaces=NS))
        t.sources.append(f"google_trends_{geo}")
        for ni in it.findall("ht:news_item", NS):
            hl = (ni.findtext("ht:news_item_title", namespaces=NS) or "").strip()
            sn = (ni.findtext("ht:news_item_snippet", namespaces=NS) or "").strip()
            src = (ni.findtext("ht:news_item_source", namespaces=NS) or "").strip()
            url = (ni.findtext("ht:news_item_url", namespaces=NS) or "").strip()
            if hl: t.headlines.append(hl)
            if sn: t.snippets.append(sn)
            if src and src not in t.sources: t.sources.append(src)
            if url: t.urls.append(url)
        t.score = _score(t)
        topics.append(t)

    topics.sort(key=lambda x: -x.score)
    return [t for t in topics if t.score >= min_score]


# ----------------------------------------------------------------------
# Multi-source discovery — feeds Groq the broadest catch we can get.
# Each fetch_* returns a list[Topic]; failures are caught at the
# discover_all() level so one dead source doesn't kill the run.
# ----------------------------------------------------------------------

def _parse_rfc822_date(s: str | None) -> str | None:
    """RSS pubDate is RFC-822 ("Sun, 01 Jun 2026 14:32:00 GMT"). Return
    an ISO-8601 UTC string, or None if missing/unparseable."""
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s.strip())
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_generic_rss(raw: bytes, source: str, *, max_items: int = 50) -> list[Topic]:
    """RSS feeds where each <item> is one story (BBC, NPR, HN, etc.).
    Not the Google Trends format — that one bundles multiple news items
    per <item>."""
    root = ET.fromstring(raw)
    out: list[Topic] = []
    for it in root.findall(".//item")[:max_items]:
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        desc = (it.findtext("description") or "").strip()
        link = (it.findtext("link") or "").strip()
        # Strip the trailing source attribution BBC tacks on (" - BBC News").
        title = re.sub(r"\s+[-|]\s+(BBC News|NPR|NPR\.org).*$", "", title)
        headlines = [title]
        if desc and desc != title and len(desc) > 10:
            # Strip HTML tags from descriptions (BBC includes CDATA HTML).
            desc_clean = re.sub(r"<[^>]+>", "", desc).strip()
            if desc_clean and desc_clean != title:
                headlines.append(desc_clean[:300])
        out.append(Topic(
            query=title,
            headlines=headlines,
            urls=[link] if link else [],
            sources=[source],
            published_at=_parse_rfc822_date(it.findtext("pubDate")),
        ))
    return out


def fetch_google_trends(geo: str = "US") -> list[Topic]:
    """Daily search trends RSS — gives us raw search spikes with the
    news article context that drove each one. Unique per geo."""
    return discover(rss_bytes=_fetch_trends(geo), min_score=-1000, geo=geo)


def fetch_bbc_world() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://feeds.bbci.co.uk/news/world/rss.xml"),
                              "bbc_world")


def fetch_bbc_us() -> list[Topic]:
    return _parse_generic_rss(
        _http_get("https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml"),
        "bbc_us")


def fetch_bbc_business() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://feeds.bbci.co.uk/news/business/rss.xml"),
                              "bbc_business")


def fetch_bbc_science() -> list[Topic]:
    return _parse_generic_rss(
        _http_get("https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
        "bbc_science")


def fetch_npr_top() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://feeds.npr.org/1001/rss.xml"),
                              "npr_top")


def fetch_npr_news() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://feeds.npr.org/1003/rss.xml"),
                              "npr_news")


def fetch_npr_politics() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://feeds.npr.org/1014/rss.xml"),
                              "npr_politics")


def fetch_pbs_newshour() -> list[Topic]:
    return _parse_generic_rss(
        _http_get("https://www.pbs.org/newshour/feeds/rss/headlines"),
        "pbs_newshour")


def fetch_guardian_world() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://www.theguardian.com/world/rss"),
                              "guardian_world")


def fetch_guardian_us() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://www.theguardian.com/us-news/rss"),
                              "guardian_us")


def fetch_aljazeera() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://www.aljazeera.com/xml/rss/all.xml"),
                              "aljazeera")


def fetch_apnews_top() -> list[Topic]:
    # AP's "top news" feed via their public RSS — wire copy, neutral.
    return _parse_generic_rss(_http_get("https://feeds.apnews.com/rss/apf-topnews"),
                              "apnews_top")


def fetch_reuters_world() -> list[Topic]:
    # Reuters cut their owned RSS so we use a public mirror that
    # rebroadcasts their feed unchanged. Falls through silently if it's
    # offline (the source list is fault-tolerant).
    return _parse_generic_rss(
        _http_get("https://feeds.feedburner.com/reuters/topNews"),
        "reuters")


def fetch_cnbc_top() -> list[Topic]:
    return _parse_generic_rss(
        _http_get("https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        "cnbc_top")


def fetch_marketwatch_top() -> list[Topic]:
    return _parse_generic_rss(
        _http_get("https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        "marketwatch")


def fetch_politico() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://www.politico.com/rss/politicopicks.xml"),
                              "politico")


def fetch_thehill() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://thehill.com/feed"),
                              "thehill")


def fetch_propublica() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://www.propublica.org/feeds/propublica/main"),
                              "propublica")


def fetch_arstechnica() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://feeds.arstechnica.com/arstechnica/index"),
                              "arstechnica")


def fetch_theverge() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://www.theverge.com/rss/index.xml"),
                              "theverge")


def fetch_techcrunch() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://techcrunch.com/feed/"),
                              "techcrunch")


def fetch_sciencedaily() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://www.sciencedaily.com/rss/all.xml"),
                              "sciencedaily")


def fetch_variety() -> list[Topic]:
    return _parse_generic_rss(_http_get("https://variety.com/feed/"),
                              "variety")


def fetch_googlenews_odd() -> list[Topic]:
    """Google News RSS search for "odd news" / "weird news" — semi-
    truck-full-of-bees, world-record pumpkins, Florida Man, lottery
    weirdness. Aggregates from many outlets that label content with
    those tags (AP "Oddities", local TV, BBC Magazine, etc.), so we
    get higher recall than any single feed.

    UPI used to host an /Odd_News/rss.xml feed but killed it. Google
    News is more reliable as an aggregator anyway since it indexes
    whichever outlet covered each weird story instead of waiting
    for one specific desk to pick it up.
    """
    url = ("https://news.google.com/rss/search?"
           "q=%22odd+news%22+OR+%22weird+news%22+OR+%22oddly+enough%22"
           "&hl=en-US&gl=US&ceid=US:en")
    return _parse_generic_rss(_http_get(url), "googlenews_odd")


def fetch_googlenews_floridaman() -> list[Topic]:
    """Google News RSS for Florida Man / Only In Florida stories.
    Separate from the generic "odd news" query so the ranker sees
    them on their own line and can pick one explicitly when the
    quirky-half quota needs filling."""
    url = ("https://news.google.com/rss/search?"
           "q=%22Florida+Man%22+OR+%22caught+on+camera%22"
           "&hl=en-US&gl=US&ceid=US:en")
    return _parse_generic_rss(_http_get(url), "googlenews_floridaman")


def fetch_hackernews() -> list[Topic]:
    """HN frontpage via hnrss.org (no auth, RSS-formatted)."""
    return _parse_generic_rss(_http_get("https://hnrss.org/frontpage"),
                              "hackernews", max_items=25)


def fetch_reddit(subreddit: str) -> list[Topic]:
    """Reddit JSON API. Some networks (CI sandboxes, corporate egress
    policies) block reddit.com — we swallow the error and the source
    contributes zero topics instead of breaking the run."""
    raw = _http_get(
        f"https://www.reddit.com/r/{subreddit}/top.json?t=day&limit=25",
        ua="shorts-pipeline by /u/anon",
    )
    data = json.loads(raw)
    out: list[Topic] = []
    for c in data.get("data", {}).get("children", [])[:25]:
        p = c.get("data") or {}
        title = (p.get("title") or "").strip()
        if not title:
            continue
        link_url = p.get("url_overridden_by_dest") or p.get("url") or ""
        permalink = p.get("permalink") or ""
        created = p.get("created_utc")
        pub = None
        if created:
            try:
                pub = datetime.fromtimestamp(float(created), tz=timezone.utc).isoformat()
            except (TypeError, ValueError):
                pub = None
        out.append(Topic(
            query=title,
            traffic=int(p.get("score") or 0),
            headlines=[title] + ([(p.get("selftext") or "")[:300]]
                                 if p.get("selftext") else []),
            urls=([link_url] if link_url else []) +
                 ([f"https://reddit.com{permalink}"] if permalink else []),
            sources=[f"reddit_{subreddit}"],
            published_at=pub,
        ))
    return out


# Sources to fan out to. Each entry is (label, callable). Order matters
# only for log readability — discover_all aggregates everything.
DEFAULT_SOURCES: list[tuple[str, callable]] = [
    # Search-trend signal (what people are Googling right now).
    ("google_trends_US", lambda: fetch_google_trends("US")),
    ("google_trends_GB", lambda: fetch_google_trends("GB")),
    ("google_trends_AU", lambda: fetch_google_trends("AU")),
    ("google_trends_CA", lambda: fetch_google_trends("CA")),
    # Wire services — neutral copy, hard to argue political slant on.
    ("apnews_top",       fetch_apnews_top),
    ("reuters",          fetch_reuters_world),
    # Public broadcasters (center-leaning).
    ("bbc_world",        fetch_bbc_world),
    ("bbc_us",           fetch_bbc_us),
    ("bbc_business",     fetch_bbc_business),
    ("bbc_science",      fetch_bbc_science),
    ("npr_top",          fetch_npr_top),
    ("npr_news",         fetch_npr_news),
    ("npr_politics",     fetch_npr_politics),
    ("pbs_newshour",     fetch_pbs_newshour),
    # International perspective.
    ("guardian_world",   fetch_guardian_world),
    ("guardian_us",      fetch_guardian_us),
    ("aljazeera",        fetch_aljazeera),
    # US politics / DC desk.
    ("politico",         fetch_politico),
    ("thehill",          fetch_thehill),
    ("propublica",       fetch_propublica),
    # Business / markets.
    ("cnbc_top",         fetch_cnbc_top),
    ("marketwatch",      fetch_marketwatch_top),
    # Tech (intentionally diversified beyond HN's tilt).
    ("hackernews",       fetch_hackernews),
    ("arstechnica",      fetch_arstechnica),
    ("theverge",         fetch_theverge),
    ("techcrunch",       fetch_techcrunch),
    # Science / culture.
    ("sciencedaily",     fetch_sciencedaily),
    ("variety",          fetch_variety),
    # Social aggregators.
    ("reddit_popular",   lambda: fetch_reddit("popular")),
    ("reddit_news",      lambda: fetch_reddit("news")),
    ("reddit_worldnews", lambda: fetch_reddit("worldnews")),
    # Quirky / offbeat news — the "semi truck full of bees" bucket.
    # Channel data showed these stories outperform serious news on
    # views and likes; rank_topics is configured to require >=3 picks
    # from this bucket per day.
    ("googlenews_odd",          fetch_googlenews_odd),
    ("googlenews_floridaman",   fetch_googlenews_floridaman),
    ("reddit_nottheonion",      lambda: fetch_reddit("nottheonion")),
    ("reddit_upliftingnews",    lambda: fetch_reddit("UpliftingNews")),
    ("reddit_offbeat",          lambda: fetch_reddit("offbeat")),
    ("reddit_floridaman",       lambda: fetch_reddit("FloridaMan")),
]


# Quirky / offbeat sources get a longer freshness window. Wire-service
# "Oddly Enough" digests and r/nottheonion bangers aren't time-locked
# the way breaking news is — a story about a flight turned back over a
# Bluetooth network name reads fresh whether it broke yesterday or last
# Tuesday. Without this, Google News's weekly "Weird News" digests get
# filtered out by the default 48h freshness rule before they reach the
# ranker.
QUIRKY_SOURCE_LABELS = frozenset((
    "googlenews_odd",
    "googlenews_floridaman",
    "reddit_nottheonion",
    "reddit_upliftingnews",
    "reddit_offbeat",
    "reddit_floridaman",
))
QUIRKY_MAX_AGE_HOURS = 24 * 7  # 7 days


def _is_fresh(t: Topic, *, max_age_hours: int) -> bool:
    """Keep items dated within `max_age_hours`. Items without a pubDate
    pass through — we filter against dates that explicitly say 'old'."""
    if not t.published_at:
        return True
    try:
        dt = datetime.fromisoformat(t.published_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    return age_hours <= max_age_hours


def discover_all(*, verbose: bool = True, max_age_hours: int = 48) -> list[Topic]:
    """Fan out to every source, return the combined raw list. Failures
    are caught per-source and logged to stderr; the run continues.

    `max_age_hours` (default 48) drops items the source dated as older
    than that window. Items without a pubDate are kept (we can't tell).
    Quirky sources get `QUIRKY_MAX_AGE_HOURS` (7 days) instead — see
    that constant's comment. This is the difference between picking
    'today's news' and picking 'evergreen topic the feed surfaced again'."""
    all_topics: list[Topic] = []
    for label, fn in DEFAULT_SOURCES:
        per_source_age = (QUIRKY_MAX_AGE_HOURS
                          if label in QUIRKY_SOURCE_LABELS
                          else max_age_hours)
        try:
            items = fn()
            fresh = [t for t in items if _is_fresh(t, max_age_hours=per_source_age)]
            if verbose:
                dropped = len(items) - len(fresh)
                note = f" ({dropped} stale dropped)" if dropped else ""
                print(f"[discover] {label:20s}  {len(fresh):3d} items{note}",
                      file=sys.stderr)
            all_topics.extend(fresh)
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f"[discover] {label:20s}  failed: {type(e).__name__}: {e}",
                      file=sys.stderr)
    return all_topics


def as_dict(t: Topic) -> dict:
    return {
        "query": t.query, "traffic": t.traffic, "score": round(t.score, 2),
        "headlines": t.headlines, "snippets": t.snippets,
        "sources": t.sources, "urls": t.urls,
        "published_at": t.published_at,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="max topics to print")
    ap.add_argument("--min-score", type=float, default=4.0, help="floor on heuristic score")
    ap.add_argument("--json", action="store_true", help="emit JSON for machine use")
    args = ap.parse_args()

    topics = discover(min_score=args.min_score)[:args.limit]
    if args.json:
        print(json.dumps([as_dict(t) for t in topics], indent=2))
    else:
        for i, t in enumerate(topics, 1):
            print(f"{i:2d}. [{t.score:>5.1f}] {t.query!r:35} traffic={t.traffic}")
            for hl in t.headlines[:2]:
                print(f"      - {hl[:110]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
