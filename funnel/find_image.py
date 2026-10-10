"""Find a picture of ANY thing, from everywhere, and check it is the thing.

Operator, 2026-10-09, on the Twitch channel's pop-ups: *"when we pull
pop-ups, we're not going to be looking in the right spots ... let's say we
needed you to pull up an image of that rug pull ... of the exact, like, how
it looked after it got rug pulled ... there needs to be a lot of
capabilities that aren't just on Wikipedia ... we 100% can use copyrighted
images. This is 100% fair use [a picture flashed for a couple of seconds
during a clip about something else] ... make sure you're adding any
capabilities to the shared area of the pipeline."*

So this is a SHARED capability (funnel/), not a Twitch one:

    find(thing, look, kind=..., when=..., work=...) -> dict | None

`thing` is the name ("Hawk Tuah coin"); `look` is what the picture must
SHOW, in search words ("HAWK coin chart after the rug pull"). Every source
is searched at once:

  * the whole media funnel (`media_funnel.search`): news APIs and their
    og:images, Brave, Tavily, DuckDuckGo Images, Reddit, Bluesky,
    Mastodon, Imgur, YouTube thumbnails, Wikidata, Openverse and the rest
    — searched for `look` AND for the bare `thing`;
  * the Wikipedia article whose title IS the thing;
  * for a coin or a stock, its real PRICE DATA (CoinGecko, DEX pairs via
    DexScreener + GeckoTerminal, Yahoo) around the moment, so a chart can
    be drawn from the numbers when no screenshot is found.

Copyrighted images are admissible here: the use is a brief inset in
commentary on something else (transformative-evidence lane,
docs/MEDIA_ACQUISITION.md); each hit records its source and URL.

Then a picture is CHECKED, never trusted on a keyword: the headless brain
reads the downloaded candidates beside `look`
(`shared.shot_relevance.judge_panels`, the same check the trending renderer
runs on every panel) and the first one it says depicts it is returned. If
no brain can look, only the exact-title Wikipedia image may be used; a
search hit nobody looked at never is. Nothing found returns None — a wrong
picture is worse than none, and nothing here is ever generated.

Returns {"path": Path, "url", "source", "via"} for a picture, or
{"chart": {...price data...}, "source"} when only the numbers were found.
"""
from __future__ import annotations

import io
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 10
MAX_JUDGED = 8         # candidates downloaded and shown to the brain
MIN_SIDE = 240         # a thumbnail smaller than this is not worth a pop-up
WINDOW_DAYS = 21       # price window ending at the moment


# ------------------------------------------------------------ network --

def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json,image/*,*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _json(url: str):
    return json.loads(_get(url).decode("utf-8", "replace"))


def _bytes(url) -> bytes | None:
    if not url or not str(url).startswith("http"):
        return None
    try:
        b = _get(str(url))
        return b if len(b) > 200 else None
    except Exception:  # noqa: BLE001
        return None


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _num(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _window(when: float | None) -> tuple[int, int]:
    end = int(when or time.time()) + 86400
    return end - (WINDOW_DAYS + 1) * 86400, end


def _bare(thing: str) -> str:
    """'Hawk Tuah coin' / '$HAWK' -> 'Hawk Tuah' / 'HAWK'."""
    s = str(thing or "").strip().lstrip("$")
    return re.sub(r"\s+(coin|token|crypto|memecoin|meme coin|stock|"
                  r"shares)$", "", s, flags=re.I).strip()


# ------------------------------------------------- price data (truth) --

def coin(thing: str, when: float | None = None) -> dict | None:
    """{"name","symbol","logo": bytes|None,"prices": [(ts, usd)]} for the
    coin whose name or ticker IS `thing`, else None."""
    q = _bare(thing)
    want = _norm(q)
    lo, hi = _window(when)
    try:
        res = _json("https://api.coingecko.com/api/v3/search?query="
                    + urllib.parse.quote(q))
        for c in res.get("coins") or []:
            if want not in (_norm(c.get("name")), _norm(c.get("symbol"))):
                continue
            mc = _json(f"https://api.coingecko.com/api/v3/coins/{c['id']}"
                       f"/market_chart/range?vs_currency=usd&from={lo}"
                       f"&to={hi}")
            prices = [(p[0] / 1000, p[1]) for p in mc.get("prices") or []]
            if len(prices) >= 3:
                return {"name": c.get("name"), "symbol": c.get("symbol"),
                        "logo": _bytes(c.get("large")), "prices": prices}
            break
    except Exception:  # noqa: BLE001
        pass
    return dex_coin(thing, when)


_GT_NET = {"ethereum": "eth", "bsc": "bsc", "solana": "solana",
           "base": "base", "arbitrum": "arbitrum", "polygon": "polygon_pos"}


def dex_coin(thing: str, when: float | None = None) -> dict | None:
    """A meme coin that only trades on a DEX: the deepest pair whose token
    name or ticker IS `thing`, priced from GeckoTerminal's daily candles."""
    q = _bare(thing)
    want = _norm(q)
    lo, hi = _window(when)
    try:
        res = _json("https://api.dexscreener.com/latest/dex/search?q="
                    + urllib.parse.quote(q))
        pairs = [p for p in res.get("pairs") or []
                 if want in (_norm((p.get("baseToken") or {}).get("name")),
                             _norm((p.get("baseToken") or {}).get("symbol")))
                 and p.get("chainId") in _GT_NET]
        if not pairs:
            return None
        p = max(pairs, key=lambda p: _num((p.get("liquidity") or {})
                                          .get("usd")))
        oh = _json(f"https://api.geckoterminal.com/api/v2/networks/"
                   f"{_GT_NET[p['chainId']]}/pools/{p['pairAddress']}/ohlcv/"
                   f"day?before_timestamp={hi}&limit={WINDOW_DAYS + 1}")
        rows = ((oh.get("data") or {}).get("attributes") or {}) \
            .get("ohlcv_list") or []
        prices = sorted((r[0], r[4]) for r in rows if r[0] >= lo)
        if len(prices) < 3:
            return None
        bt = p.get("baseToken") or {}
        return {"name": bt.get("name"), "symbol": bt.get("symbol"),
                "logo": _bytes((p.get("info") or {}).get("imageUrl")),
                "prices": prices}
    except Exception:  # noqa: BLE001
        return None


def stock(thing: str, when: float | None = None) -> dict | None:
    """The listed company whose ticker or name IS `thing`."""
    q = _bare(thing)
    lo, hi = _window(when)
    want = _norm(q)
    try:
        res = _json("https://query1.finance.yahoo.com/v1/finance/search?q="
                    + urllib.parse.quote(q) + "&quotesCount=5&newsCount=0")
        sym, name = None, None
        for c in res.get("quotes") or []:
            if c.get("quoteType") not in ("EQUITY", "ETF"):
                continue
            names = {_norm(c.get("symbol")), _norm(c.get("shortname")),
                     _norm(c.get("longname"))}
            if want in names or any(n.startswith(want) and len(want) >= 4
                                    for n in names if n):
                sym = c["symbol"]
                name = c.get("shortname") or c.get("longname") or sym
                break
        if not sym:
            return None
        ch = _json(f"https://query1.finance.yahoo.com/v8/finance/chart/"
                   f"{urllib.parse.quote(sym)}?period1={lo}&period2={hi}"
                   f"&interval=1d")
        r = (ch.get("chart") or {}).get("result") or []
        ts = r[0].get("timestamp") or []
        cl = (((r[0].get("indicators") or {}).get("quote") or [{}])[0]
              .get("close") or [])
        prices = [(t, c) for t, c in zip(ts, cl) if c is not None]
        if len(prices) < 3:
            return None
        return {"name": name, "symbol": sym, "logo": None, "prices": prices}
    except Exception:  # noqa: BLE001
        return None


def wiki(thing: str) -> dict | None:
    """{"name","url"} of the lead image of the article whose title IS
    `thing` (after redirects), never a disambiguation page."""
    qs = urllib.parse.urlencode({
        "action": "query", "format": "json", "redirects": 1,
        "prop": "pageimages|pageprops", "piprop": "thumbnail",
        "pithumbsize": 900, "titles": thing})
    try:
        res = _json("https://en.wikipedia.org/w/api.php?" + qs)
        q = res.get("query") or {}
        titles = {_norm(thing)}
        for r in (q.get("normalized") or []) + (q.get("redirects") or []):
            if _norm(r.get("from")) in titles:
                titles.add(_norm(r.get("to")))
        for page in (q.get("pages") or {}).values():
            if "disambiguation" in (page.get("pageprops") or {}):
                return None
            title = page.get("title") or ""
            base = _norm(re.sub(r"\s*\(.*?\)\s*$", "", title))
            if _norm(title) not in titles and base != _norm(thing):
                return None
            src = (page.get("thumbnail") or {}).get("source")
            if src:
                return {"name": re.sub(r"\s*\(.*?\)\s*$", "", title),
                        "url": src}
    except Exception:  # noqa: BLE001
        pass
    return None


# ------------------------------------------------------- search, judge --

def search_urls(thing: str, look: str = "") -> list[dict]:
    """Every image the wide funnel finds for `look` and for the bare
    `thing`, best first, deduplicated: [{url, source, title}]."""
    from funnel import media_funnel
    out: list[dict] = []
    seen: set[str] = set()
    for angle, ent in ((look or thing, thing), (thing, _bare(thing))):
        try:
            cands = media_funnel.search(angle, [ent], verbose=False)
        except Exception as e:  # noqa: BLE001
            print(f"::warning::[find_image] funnel failed "
                  f"({type(e).__name__})", flush=True)
            cands = []
        for c in cands:
            if c.url and c.url not in seen:
                seen.add(c.url)
                out.append({"url": c.url, "source": c.source,
                            "title": c.article_title})
        if look == thing:
            break
    return out


def _download(url: str, dest: Path) -> Path | None:
    """The image at `url` as a PNG at `dest`, if it is a real picture at
    least MIN_SIDE on its short side."""
    b = _bytes(url)
    if not b:
        return None
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(b))
        im.load()
        if min(im.size) < MIN_SIDE:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.convert("RGB").save(dest)
        return dest
    except Exception:  # noqa: BLE001
        return None


def judge(paths: list[tuple[int, Path]], look: str, title: str = ""
          ) -> dict[int, dict] | None:
    """The brain's per-picture verdict on whether it DEPICTS `look`, or
    None when no brain could look (shared.shot_relevance)."""
    from shared import shot_relevance
    return shot_relevance.judge_panels(
        [(i, p, look) for i, p in paths], title=title or look)


def find(thing: str, look: str = "", *, kind: str = "thing",
         when: float | None = None, work: Path | str = ".",
         title: str = "") -> dict | None:
    """The best CHECKED picture of `thing` showing `look`, from every
    source; else, for a coin or a stock, its price data; else None."""
    thing = str(thing or "").strip()
    look = str(look or "").strip() or thing
    if not thing:
        return None
    work = Path(work)
    tag = _norm(thing)[:24] or "x"

    cands: list[dict] = []
    w = wiki(_bare(thing)) or (wiki(thing) if _bare(thing) != thing
                               else None)
    if w:
        cands.append({"url": w["url"], "source": "wikipedia_exact",
                      "title": w["name"], "exact": True})
    cands += search_urls(thing, look)

    pics: list[tuple[int, Path]] = []
    meta: dict[int, dict] = {}
    for c in cands:
        if len(pics) >= MAX_JUDGED:
            break
        i = len(meta)
        p = _download(c["url"], work / f"find_{tag}_{i}.png")
        if p:
            pics.append((i, p))
            meta[i] = c
    verdicts = judge(pics, look, title) if pics else None
    for i, p in pics:
        c = meta[i]
        ok = (verdicts.get(i, {}).get("depicts") if verdicts is not None
              else c.get("exact"))
        if ok:
            print(f"[find_image] {thing!r}: {c['source']} "
                  f"({'checked' if verdicts is not None else 'exact title'})"
                  f" {c['url'][:100]}", flush=True)
            return {"path": p, "url": c["url"], "source": c["source"],
                    "name": c.get("title") or thing,
                    "via": "judged" if verdicts is not None else "exact"}

    if kind in ("coin", "stock"):
        info = coin(thing, when) if kind == "coin" else stock(thing, when)
        if info:
            print(f"[find_image] {thing!r}: no picture showed it — "
                  f"{kind} price data instead", flush=True)
            return {"chart": info, "source": f"{kind}_prices"}
    print(f"[find_image] {thing!r}: {len(cands)} found, {len(pics)} "
          f"downloaded, none showed {look!r}"
          + ("" if verdicts is not None or not pics
             else " (no brain to check them)"), flush=True)
    return None
