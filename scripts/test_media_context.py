#!/usr/bin/env python3
"""Tests for the story-generic media context layer (PR#173 adoption):
wrong-context filtering, the per-source circuit breaker, and the cross-video
reuse ledger. The named defect under test is real: the blind judge found a
Japanese gas-station sign in an American money story."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from data_learning import media_context as mctx  # noqa: E402


def cand(title, url="https://example.org/x.jpg"):
    return {"title": title, "url": url}


def main():
    ctx = {"geography": "United States", "language": "en",
           "exclude_terms": ["clipart", "cartoon"]}

    kept, rej = mctx.context_filter(
        [cand("Japanese gas station price sign, Tokyo"),
         cand("ガソリンスタンドの価格表"),
         cand("Funny money cartoon illustration"),
         cand("Gas station price board, Texas highway"),
         cand("Counting dollar bills close up")], ctx)
    titles = [c["title"] for c in kept]
    assert "Gas station price board, Texas highway" in titles
    assert "Counting dollar bills close up" in titles
    assert len(kept) == 2 and len(rej) == 3, (titles, rej)
    reasons = " | ".join(r for _, r in rej)
    assert "geography tell" in reasons and "script" in reasons \
        and "excluded term" in reasons, reasons
    print("ok  1. Japanese sign / CJK title / cartoon rejected; on-context kept")

    kept, rej = mctx.context_filter([cand("Anything at all, 東京")], None) \
        if not mctx.active_context() else (None, None)
    assert kept is not None and len(kept) == 1 and not rej
    print("ok  2. no declared context -> nothing filtered")

    # target-country tells never reject their own story
    kept, rej = mctx.context_filter(
        [cand("American flag over New York street")], ctx)
    assert len(kept) == 1, rej
    print("ok  3. target-country tells are not treated as foreign")

    # ---- breaker ----
    b = mctx.Breaker(threshold=3)
    assert b.allow("openverse")
    for _ in range(2):
        b.record("openverse", False)
    assert b.allow("openverse"), "opened too early"
    b.record("openverse", False)
    assert not b.allow("openverse"), "3 consecutive failures must open"
    b.record("commons", False)
    assert b.allow("commons")
    b.record("openverse", True)          # recovery closes it
    assert b.allow("openverse")
    print("ok  4. breaker opens on 3 consecutive fails, closes on success")

    # ---- reuse ledger ----
    real = mctx.LEDGER_PATH
    with tempfile.TemporaryDirectory() as d:
        mctx.LEDGER_PATH = Path(d) / "ledger.json"
        url = "https://example.org/stock-photo-42.jpg"
        assert mctx.reuse_penalty(url, slug="video-a") == 1.0
        mctx.record_use(url, "stock", slug="video-a")
        assert mctx.reuse_penalty(url, slug="video-a") == 1.0, \
            "same-video reuse must not be penalized"
        assert mctx.reuse_penalty(url, slug="video-b") == 0.7
        mctx.record_use(url, "stock", slug="video-b")
        assert mctx.reuse_penalty(url, slug="video-c") == 0.45
        print("ok  5. cross-video reuse penalized (0.7 / 0.45); same-video free")
    mctx.LEDGER_PATH = real

    # story wiring: the flagship declares a context
    import json
    st = json.loads((REPO / "data_learning" / "pro_stories" /
                     "money-goes.beats.json").read_text())
    assert st.get("media_context", {}).get("geography") == "United States"
    print("ok  6. flagship story declares media_context")

    print("media context: 6/6 tests pass")


if __name__ == "__main__":
    main()
