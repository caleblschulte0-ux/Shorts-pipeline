"""Viz director — decide how each segment DEPICTS its data.

The creative choice is made by the LLM at *authoring* time (see
``scripts/author_stories.py``): each segment carries an authored ``viz`` concept
+ ``viz_params``. This module is the deterministic SAFETY NET that runs at render
time — it honours a valid authored concept, and otherwise picks a best-fit
DEPICTION from the data shape. It is NOT a rotation: every choice depicts the
data (size / length / position / area / count / fill / motion), it never lands on
bare numbers, it never repeats a depiction within a video, and it guarantees at
least one stand-out "novelty" moment per video.

Kinds are registered with metadata so new depictions (added in later chunks)
automatically join the vocabulary the director can pick from.
"""
from __future__ import annotations

import re

from . import charts
from . import viz_scene  # noqa: F401  (registers the "scene" full-frame renderer)

# --- Vocabulary --------------------------------------------------------------
# Each depiction kind and how the director treats it:
#   image   — needs generated cut-outs (budget-capped, may fail -> fallback)
#   novelty — a stand-out / cinematic depiction (we want >=1 per video)
#   place   — a geographic map (may repeat within a video; place data always maps)
#   time    — a time-series depiction
# Kinds that only some chunks have shipped are gated by `charts.FULLFRAME_RENDERERS`
# / the `_compose_story` dispatch, so the director checks `renderable()` too.
KINDS = {
    "geo_us":         {"image": False, "novelty": False, "place": True},
    "geo_world":      {"image": False, "novelty": False, "place": True},
    "geo_city":       {"image": False, "novelty": False, "place": True},
    "trend":          {"image": False, "novelty": False, "time": True},
    "timeline":       {"image": False, "novelty": True,  "time": True},
    "diorama":        {"image": True,  "novelty": True},
    "scale_stack":    {"image": True,  "novelty": True},
    "pictorial_race": {"image": True,  "novelty": False},
    "fill_vessel":    {"image": False, "novelty": True},
    "waffle_grid":    {"image": False, "novelty": True},
    "orbit":          {"image": False, "novelty": True},
    "flow_race":      {"image": False, "novelty": True},
    "pictograph":     {"image": False, "novelty": False},
    "bubbles":        {"image": False, "novelty": False},
    "share":          {"image": False, "novelty": False},   # donut
    "comparison":     {"image": False, "novelty": False},   # versus columns
}

# Depictions that are always available (pure matplotlib, no image gen, and their
# renderer already exists). Used as guaranteed fallbacks + the terminal choice.
_ALWAYS = {"bubbles", "pictograph", "trend", "share", "comparison",
           "geo_us", "geo_world", "geo_city"}

_AGE_KW = re.compile(r"\b(age|old|older|oldest|ancient|since|ago|history|"
                     r"historic|year[s]? old|existed|lifespan|founded|era)\b", re.I)
_SCALE_KW = re.compile(r"\b(tall|taller|tallest|height|deep|deepest|far|"
                       r"farther|distance|long|longest|size|huge|heavy|"
                       r"heaviest|big|biggest|massive)\b", re.I)


# Card kinds handled by the `_compose_story` dispatch. Later chunks add
# depictions here (waffle_grid, pictorial_race) as their renderers land.
CARD_KINDS = {"pictograph", "bubbles", "share", "comparison", "trend",
              "geo_us", "geo_world", "geo_city", "waffle_grid", "pictorial_race"}


def renderable(kind: str) -> bool:
    """Only offer a kind whose renderer is actually wired up in this build."""
    return kind in charts.FULLFRAME_RENDERERS or kind in CARD_KINDS


# --- Feature extraction ------------------------------------------------------
def _features(ins) -> dict:
    vals = [p.value for p in ins.items if p.value is not None]
    n = len(ins.items)
    vmax = max(vals) if vals else 0.0
    vmin = min(vals) if vals else 0.0
    v0 = vals[0] if vals else 0.0
    v1 = vals[1] if len(vals) > 1 else 0.0
    unit = (ins.unit or "").strip().lower()
    if unit in ("percent", "%", "rate", "pct", "share"):
        unit_class = "pct"
    elif unit in ("dollars", "dollar", "usd", "$", "billion dollars",
                  "thousand dollars", "million dollars"):
        unit_class = "money"
    elif unit in ("years", "year"):
        unit_class = "years"
    elif unit in ("mph", "km/h", "kmh", "kph"):
        unit_class = "speed"
    else:
        unit_class = "count"
    has_period = any(getattr(p, "period", None) for p in ins.items)
    place = charts.place_scope_for([p.label for p in ins.items])
    topic = ins.topic or ""
    return {
        "n": n, "vmax": vmax, "vmin": vmin,
        "dominance": (v0 / v1) if v1 else (99.0 if v0 else 1.0),
        "spread": (vmax / vmin) if vmin else (99.0 if vmax else 1.0),
        "unit_class": unit_class,
        "has_period": has_period,
        "place": place,
        "age": bool(_AGE_KW.search(topic)),
        "scale": bool(_SCALE_KW.search(topic)),
        "is_share": ins.kind == "share" or (unit_class == "pct" and n >= 3),
    }


def _candidates(ins, f: dict) -> list[str]:
    """Ranked depiction candidates for one insight, best first. Every entry
    DEPICTS the data — bare-number kinds are never produced here."""
    # Place data always maps.
    if f["place"]:
        return [f["place"]]
    ranked: list[str] = []
    # Time / age.
    if f["age"] and (f["has_period"] or getattr(ins, "viz_params", None)):
        ranked += ["timeline", "trend"]
    elif f["has_period"]:
        ranked += ["trend", "timeline"]
    # Scale / magnitude comparisons.
    if f["scale"] and f["dominance"] >= 1.6:
        ranked += ["scale_stack", "diorama"]
    # Shares / part-to-whole.
    if f["is_share"]:
        ranked += ["waffle_grid", "share"]
    # One value dwarfs the rest -> a hero depiction.
    if f["dominance"] >= 2.0:
        ranked += ["diorama", "fill_vessel"]
    # Single shock stat.
    if f["n"] <= 2:
        ranked += ["fill_vessel", "diorama"]
    # General ranking / comparison.
    ranked += ["pictorial_race", "diorama", "pictograph", "bubbles"]
    # De-dup preserving order, keep only renderable kinds.
    seen, out = set(), []
    for k in ranked:
        if k not in seen and renderable(k):
            seen.add(k)
            out.append(k)
    out.append("bubbles")            # terminal guarantee
    return out


# --- Assignment --------------------------------------------------------------
def assign(inss: list, *, seed: int = 0, image_budget: int = 5) -> None:
    """Set each insight's final ``kind`` (depiction). Honours a valid authored
    concept; otherwise best-fit by shape. Enforces: never bare numbers, no
    repeated depiction within a video (maps/trend may repeat), >=1 novelty,
    and an image-generation budget."""
    n = len(inss)
    feats = [_features(ins) for ins in inss]
    chosen: list[str | None] = [None] * n
    used: set[str] = set()
    images = 0

    def _take(i: int, kind: str) -> bool:
        nonlocal images
        meta = KINDS.get(kind, {})
        # place/trend may repeat; other depictions must be distinct in a video.
        if not (meta.get("place") or meta.get("time")) and kind in used:
            return False
        if meta.get("image"):
            if images >= image_budget:
                return False
            images += 1
        chosen[i] = kind
        used.add(kind)
        return True

    # Pass 1 — honour a valid authored concept (the LLM's creative choice).
    order = sorted(range(n), key=lambda i: (seed + i) % max(1, n))
    for i in order:
        av = (getattr(inss[i], "authored_viz", "") or "").strip().lower()
        if av and av in KINDS and renderable(av):
            # timeline needs time data; skip if unsupported so it falls through.
            if av == "timeline" and not (feats[i]["has_period"]
                                         or getattr(inss[i], "viz_params", None)):
                continue
            _take(i, av)

    # Pass 2 — fill the rest with the best renderable, non-repeating candidate.
    for i in order:
        if chosen[i]:
            continue
        for cand in _candidates(inss[i], feats[i]):
            if _take(i, cand):
                break
        if not chosen[i]:
            chosen[i] = "bubbles"        # absolute last resort (still depicts)

    # Pass 3 — guarantee at least one NOVELTY per multi-segment video. If none
    # was chosen, upgrade the best eligible segment to its top novelty candidate.
    if n >= 2 and not any(KINDS.get(k, {}).get("novelty") for k in chosen):
        for i in order:
            if feats[i]["place"] or feats[i]["has_period"]:
                continue
            nov = next((c for c in _candidates(inss[i], feats[i])
                        if KINDS.get(c, {}).get("novelty")
                        and not (KINDS[c].get("image") and images >= image_budget)), None)
            if nov:
                used.discard(chosen[i])
                chosen[i] = nov
                used.add(nov)
                if KINDS[nov].get("image"):
                    images += 1
                break

    for ins, k in zip(inss, chosen):
        ins.kind = k
