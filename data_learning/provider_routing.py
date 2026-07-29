"""PROVIDER ROUTING — nextgen capability/health/cost routing on REAL providers.

Adapter over experiments/curiosity_nextgen/provider_pool.py: the actual media
providers (google_images via Apify, Openverse, Wikimedia Commons, NASA,
Pexels/Pixabay stock) are described as ProviderRecords built from LIVE state —
API-key presence, the per-run circuit breaker (media_context.BREAKER), rough
cost/latency profiles — and ranked by the reference fitness function
(reliability 45% / cost 25% / latency 20% / quota 10%) with independence-aware
fallbacks (a fallback never shares the selected provider's family).

CONTRACT: ``maybe_route()`` returns an ordered provider-id list or None and
NEVER raises — media.find() consults it to order its image providers and
falls back to its own hard-coded order when routing abstains. Routing can
therefore never make acquisition worse than the status quo, only reorder it
away from open-circuited / keyless providers.

    python3 -m data_learning.provider_routing      # print the routing table
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO / "experiments") not in sys.path:
    sys.path.insert(0, str(REPO / "experiments"))


# real providers -> (family, capabilities, unit_cost, latency_s, needs_env)
_PROVIDERS: dict[str, tuple[str, frozenset, float, float, str | None]] = {
    "google_images": ("apify", frozenset({"image"}), 0.02, 12.0,
                      "APIFY_API_TOKEN"),
    "openverse_images": ("openverse", frozenset({"image"}), 0.0, 4.0, None),
    "commons_images": ("wikimedia", frozenset({"image"}), 0.0, 4.0, None),
    "nasa": ("nasa", frozenset({"video", "image"}), 0.0, 8.0, None),
    "pexels": ("stock", frozenset({"video", "image"}), 0.0, 5.0,
               "PEXELS_API_KEY"),
    "pixabay": ("stock", frozenset({"video", "image"}), 0.0, 5.0,
                "PIXABAY_API_KEY"),
}


def records():
    """Live ProviderRecords: health = key present AND circuit closed; the
    breaker's consecutive-failure count feeds recent_error_rate."""
    from curiosity_nextgen.provider_pool import ProviderRecord
    from data_learning.media_context import BREAKER
    state = BREAKER.report()
    out = []
    for pid, (family, caps, cost, latency, env) in _PROVIDERS.items():
        keyed = env is None or bool(os.environ.get(env))
        open_circuit = pid in state["open"]
        fails = state["fails"].get(pid, 0)
        out.append(ProviderRecord(
            provider_id=pid,
            provider_family=family,
            model_family="search",
            capabilities=caps,
            healthy=keyed and not open_circuit,
            deterministic=False,
            unit_cost=cost,
            estimated_latency_seconds=latency,
            recent_error_rate=min(1.0, fails / 3.0),
            quota_remaining=0 if not keyed else 100,
        ))
    return out


def maybe_route(kind: str = "image") -> list[str] | None:
    """Ordered provider ids ([selected, *fallbacks, *rest-eligible]) for this
    media kind, or None when routing abstains (no eligible provider, or any
    internal error). Never raises."""
    try:
        from curiosity_nextgen.provider_pool import (
            RoutingRequest, route_provider)
        recs = records()
        decision = route_provider(recs, RoutingRequest(
            stage="media_acquisition",
            required_capabilities=frozenset({kind}),
            maximum_unit_cost=1.0,
            maximum_latency_seconds=60.0), fallback_count=2)
        if not decision.selected_provider_id:
            return None
        ordered = [decision.selected_provider_id,
                   *decision.fallback_provider_ids]
        rejected = {pid for pid, _ in decision.rejected}
        for r in recs:                       # eligible leftovers keep a slot
            if r.provider_id not in ordered and r.provider_id not in rejected \
                    and kind in r.capabilities:
                ordered.append(r.provider_id)
        return ordered
    except Exception:  # noqa: BLE001 — routing must never break acquisition
        return None


def table() -> dict:
    """JSON-ready routing table for both kinds, with rejection reasons."""
    from curiosity_nextgen.provider_pool import RoutingRequest, route_provider
    recs = records()
    doc: dict = {"providers": [
        {"id": r.provider_id, "family": r.provider_family,
         "healthy": r.healthy, "error_rate": r.recent_error_rate,
         "capabilities": sorted(r.capabilities)} for r in recs]}
    for kind in ("image", "video"):
        d = route_provider(recs, RoutingRequest(
            stage="media_acquisition",
            required_capabilities=frozenset({kind}),
            maximum_unit_cost=1.0, maximum_latency_seconds=60.0))
        doc[kind] = {"selected": d.selected_provider_id,
                     "fallbacks": list(d.fallback_provider_ids),
                     "rejected": [list(x) for x in d.rejected],
                     "valid": d.valid, "blockers": list(d.blockers)}
    return doc


if __name__ == "__main__":
    print(json.dumps(table(), indent=2))
