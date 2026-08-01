#!/usr/bin/env python3
"""A media candidate's `title` must describe the SUBJECT, never be a URL.

The bug this locks out cost four renders and a wrong diagnosis. Both stock
providers put a URL in `title`:

    {"source": "pexels",  "title": v["url"]}        # https://pexels.com/video/123/
    {"source": "pixabay", "title": v["pageURL"]}    # https://pixabay.com/videos/...

`title` is exactly what media._relevance() ranks a candidate on and what the
credits print, so a URL there is wrong on both counts.

SCOPE, honestly: when a page URL happens to carry a descriptive slug
(`/video/woman-walking-on-a-beach-123/`) `_relevance` already tokenized those
words, and check 3 proves the score is unchanged. So the URL-title alone does
NOT explain why these providers never won a beat. What it does break outright
is the slug-less case (`/video/1234567/`), which scores a flat zero against any
query and is therefore dropped by MOTION_REL_FLOOR before the clip is ever
downloaded or motion-probed — check 4.

Measured context (media probe, run 30562479600): Pexels returns HTTP 403, and
Pixabay returned **32 candidates across 4 queries** while three consecutive
renders credited **zero** Pixabay clips. This test locks the title contract;
the remaining gap between "32 candidates" and "zero used" is measured by
scripts/media_probe.py --decide, not assumed here.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "scripts"):
    sys.path.insert(0, str(p))

from data_learning import media, stock  # noqa: E402

# real API response shapes, trimmed to the fields the adapters read
PIXABAY_HIT = {
    "pageURL": "https://pixabay.com/videos/id-man-sleeping-in-bed-98765/",
    "tags": "man, sleeping, bed, night",
    "duration": 12,
    "videos": {"large": {"url": "https://cdn.pixabay.com/vimeo/1/large.mp4"}},
}
PEXELS_HIT = {
    "url": "https://www.pexels.com/video/woman-walking-on-a-beach-1234567/",
    "duration": 9,
    "video_files": [{"height": 1080, "link": "https://player.pexels.com/a.mp4"}],
}


def main():
    # 1. a URL must never survive as a title
    for src, hit in (("pixabay", PIXABAY_HIT), ("pexels", PEXELS_HIT)):
        t = stock.describe(hit, src)
        assert t, f"{src}: empty title"
        assert "http" not in t and "//" not in t, f"{src}: title is a URL: {t!r}"
        assert ".com" not in t, f"{src}: title carries a domain: {t!r}"
    print("ok  1. neither provider emits a URL as a title")

    # 2. the title carries the SUBJECT's words
    assert "sleeping" in stock.describe(PIXABAY_HIT, "pixabay")
    assert stock.describe(PEXELS_HIT, "pexels") == "woman walking on a beach"
    print("ok  2. titles describe the subject "
          f"({stock.describe(PEXELS_HIT, 'pexels')!r})")

    # 3. Relevance never REGRESSES, and improves strictly where it matters.
    #    Honest scope: when the page URL happens to carry a descriptive slug,
    #    _relevance already tokenized those words, so the score is unchanged —
    #    the URL-title was NOT, on its own, what sank these providers. The real
    #    damage is the degenerate case below.
    q_sleep, q_walk = "person sleeping in bed", "woman walking on a beach"
    floor = media.MOTION_REL_FLOOR
    pairs = [("pixabay", PIXABAY_HIT["pageURL"],
              stock.describe(PIXABAY_HIT, "pixabay"), q_sleep),
             ("pexels", PEXELS_HIT["url"],
              stock.describe(PEXELS_HIT, "pexels"), q_walk)]
    for name, old_t, new_t, q in pairs:
        old, new = media._relevance(old_t, q), media._relevance(new_t, q)
        assert new >= old, f"{name}: relevance regressed {old} -> {new}"
        assert new >= floor, f"{name}: {new} under the floor {floor}"
    print(f"ok  3. relevance never regresses and clears the floor ({floor})")

    # 4. THE DEGENERATE CASE — a Pexels URL with NO slug, which is common.
    #    Here the old title scored a flat zero against any query, so the clip
    #    was dropped by the relevance floor before it was ever downloaded.
    bare = {"url": "https://www.pexels.com/video/1234567/", "alt": "person sleeping in a bed at night",
            "video_files": [{"height": 1080, "link": "https://x/a.mp4"}]}
    old = media._relevance(bare["url"], q_sleep)
    new = media._relevance(stock.describe(bare, "pexels"), q_sleep)
    assert old < floor <= new, (old, new, floor)
    print(f"ok  4. a slug-less URL scored {old:.2f} (under the {floor} floor, "
          f"skipped unprobed); it now scores {new:.2f}")

    # 5. the adapters themselves use describe() — not a URL field
    src = (REPO / "data_learning" / "stock.py").read_text()
    for bad in ('"title": v.get("url"', '"title": v.get("pageURL"'):
        assert bad not in src, f"a provider still titles candidates with {bad}"
    assert src.count('"title": describe(') >= 2
    print("ok  5. both adapters title candidates via describe()")

    # 6. degrades safely — never invents a URL when it knows nothing
    assert stock.describe({}, "pexels") == "pexels"
    assert stock.slug_words("") == ""
    assert stock.slug_words("https://x.com/video/1234567/") == ""
    print("ok  6. unknown subject falls back to the source name, never a URL")

    print("stock titles: 6/6 checks pass")


if __name__ == "__main__":
    main()
