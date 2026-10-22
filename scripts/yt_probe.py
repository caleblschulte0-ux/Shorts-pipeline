"""Probe free video routes from a CI runner (logs only, downloads kept in
/tmp). 1) loader.to driven through its own page in a real Chromium, every
redirect logged. 2) Dailymotion's public API + yt-dlp."""
import json, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

VID = sys.argv[1] if len(sys.argv) > 1 else "jxuMjd6hPJA"
Q = sys.argv[2] if len(sys.argv) > 2 else "kevin durant"


def loader_page():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900},
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
        page = ctx.new_page()
        def resp(r):
            if any(h in r.url for h in ("affadaffa", "download", "progress", "ajax")):
                print("  resp", r.status, r.url[:140], r.headers.get("location", "")[:120],
                      r.headers.get("content-type", ""), flush=True)
        ctx.on("response", resp)
        ctx.on("page", lambda pg: print("  popup", pg.url[:120], flush=True))
        page.goto("https://loader.to/en94/youtube-mp4-downloader.html",
                  wait_until="domcontentloaded", timeout=60000)
        print("title", page.title(), flush=True)
        for sel in ("input", "select", "button"):
            for el in page.query_selector_all(sel)[:12]:
                print(" ", sel, (el.evaluate("e=>e.outerHTML") or "")[:200], flush=True)
        inp = page.query_selector("input#link") or page.query_selector("input[type=text], input[type=url], input:not([type])")
        inp.fill(f"https://www.youtube.com/watch?v={VID}")
        fmt = page.query_selector("select#format, select")
        if fmt:
            opts = fmt.evaluate("e=>[...e.options].map(o=>o.value)")
            print("formats", opts[:30], flush=True)
            for want in ("720", "480", "360", "1080"):
                if want in opts:
                    fmt.select_option(want); break
        btn = page.query_selector("button#load") or page.query_selector("button")
        btn.click()
        deadline = time.time() + 240
        link = None
        while time.time() < deadline:
            for a in page.query_selector_all("a[href], button"):
                h = a.get_attribute("href") or ""
                t = (a.inner_text() or "").strip()[:40]
                if ("download" in h.lower() and "affadaffa" in h) or (a.is_visible() and t.lower() == "download"):
                    link = a; break
            if link: break
            time.sleep(3)
        if not link:
            print("no download link; body:", page.inner_text("body")[:800], flush=True)
            b.close(); return
        print("link", link.evaluate("e=>e.outerHTML")[:300], flush=True)
        for i in range(4):
            try:
                with page.expect_download(timeout=60000) as dl:
                    link.click()
                p = Path(f"/tmp/probe_{i}.mp4"); dl.value.save_as(str(p))
                print(f"DOWNLOAD try {i}: {p.stat().st_size} bytes", flush=True)
                if p.stat().st_size > 50000:
                    break
            except Exception as e:
                print(f"try {i}: {type(e).__name__}; pages:",
                      [pg.url[:100] for pg in ctx.pages], flush=True)
                for pg in ctx.pages[1:]:
                    pg.close()
                page.bring_to_front()
        b.close()


def dailymotion():
    u = ("https://api.dailymotion.com/videos?" + urllib.parse.urlencode(
        {"search": Q, "limit": 5, "sort": "relevance",
         "fields": "id,title,url,duration,views_total"}))
    d = json.load(urllib.request.urlopen(u, timeout=30))
    for v in d.get("list", []):
        print("  dm", v, flush=True)
    if d.get("list"):
        v = d["list"][0]
        r = subprocess.run(["yt-dlp", "-q", "-f", "mp4/best", "-o", "/tmp/dm.mp4",
                            v["url"]], capture_output=True, text=True, timeout=300)
        print("dm yt-dlp", r.returncode, r.stderr[-400:], flush=True)
        p = Path("/tmp/dm.mp4")
        print("dm file", p.stat().st_size if p.exists() else None, flush=True)


for name, fn in (("loader page", loader_page), ("dailymotion", dailymotion)):
    print("=====", name, flush=True)
    try:
        fn()
    except Exception as e:
        print(name, "FAILED", type(e).__name__, str(e)[:300], flush=True)
