#!/usr/bin/env python3
"""Tests for provider routing: live records reflect keys + breaker state,
open circuits sink providers, maybe_route never raises, and media.find's
image order honors the router while keeping its default as fallback."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for p in (REPO, REPO / "experiments"):
    sys.path.insert(0, str(p))

from data_learning import provider_routing as pr  # noqa: E402
from data_learning.media_context import BREAKER  # noqa: E402


def main():
    recs = {r.provider_id: r for r in pr.records()}
    assert set(recs) == set(pr._PROVIDERS)
    assert not recs["openverse_images"].unit_cost  # free pool
    print("ok  1. records cover every real provider")

    # 1b. the env var each provider's HEALTH depends on must be the same name
    # the provider actually reads. A mismatch marks a live provider unhealthy
    # and sinks it in the route exactly when it is available (this caught
    # APIFY_API_TOKEN vs the real APIFY_TOKEN).
    media_src = (REPO / "data_learning" / "media.py").read_text()
    stock_src = (REPO / "data_learning" / "stock.py").read_text()
    for pid, (_, _, _, _, env) in pr._PROVIDERS.items():
        if env is None:
            continue
        assert env in media_src or env in stock_src, (
            f"{pid}: routing gates health on {env!r}, which no provider "
            f"module reads — health check is wrong")
    print("ok  1b. health env names match what the providers really read")

    # keyless providers are unhealthy with zero quota
    saved = {k: os.environ.pop(k, None) for k in
             ("APIFY_API_TOKEN", "PEXELS_API_KEY", "PIXABAY_API_KEY")}
    try:
        recs = {r.provider_id: r for r in pr.records()}
        assert not recs["google_images"].healthy
        assert recs["google_images"].quota_remaining == 0
        assert recs["commons_images"].healthy   # keyless-by-design stays up
        order = pr.maybe_route("image")
        assert order and order[0] in ("openverse_images", "commons_images"), order
        assert "google_images" not in order, order
        print("ok  2. missing API key sinks the provider; free pools lead")

        # an OPEN circuit sinks a provider for the rest of the run
        for _ in range(3):
            BREAKER.record("openverse_images", False)
        order = pr.maybe_route("image")
        assert order and order[0] == "commons_images", order
        assert "openverse_images" not in order, order
        print("ok  3. open circuit removes the provider from the route")
        BREAKER.record("openverse_images", True)   # close it again

        # routing abstains (None) rather than raising on internal errors
        real = pr.records
        pr.records = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            assert pr.maybe_route("image") is None
        finally:
            pr.records = real
        print("ok  4. maybe_route abstains on error, never raises")

        # media.find image order: router consulted, default preserved on None
        import data_learning.media as media
        calls = []
        real_fns = (media.google_images, media.openverse_images,
                    media.commons_images)
        media.google_images = lambda *a, **k: calls.append("google") or []
        media.openverse_images = lambda *a, **k: calls.append("openverse") or []
        media.commons_images = lambda *a, **k: calls.append("commons") or []
        try:
            media.find("test query", kind="image")
            assert calls in (["openverse", "commons"], ["commons",
                             "openverse"]), calls  # keyless google skipped
            print("ok  5. media.find follows the routed order")
        finally:
            (media.google_images, media.openverse_images,
             media.commons_images) = real_fns
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v

    table = pr.table()
    assert "image" in table and "video" in table and table["providers"]
    print("ok  6. routing table renders for both kinds")
    print("provider routing: 6/6 tests pass")


if __name__ == "__main__":
    main()
