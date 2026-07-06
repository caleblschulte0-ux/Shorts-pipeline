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

import os
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
    # A canonical SCENE the director attaches (resolves to kind "scene"):
    "fill_scene":     {"image": True,  "novelty": True},     # subject filled to %
    "rank_scene":     {"image": True,  "novelty": True,  "repeatable": True},
    "race":           {"image": True,  "novelty": True,  "repeatable": True},
    "scene":          {"image": True,  "novelty": True,  "repeatable": True},
}

# Pseudo-kinds that resolve to an attached `ins.scene` (kind becomes "scene").
_SCENE_BUILDERS = {"fill_scene": "fill_scene", "rank_scene": "object_scene"}

# Depictions that are always available (pure matplotlib, no image gen, and their
# renderer already exists). Used as guaranteed fallbacks + the terminal choice.
_ALWAYS = {"bubbles", "pictograph", "trend", "share", "comparison",
           "geo_us", "geo_world", "geo_city"}

_AGE_KW = re.compile(r"\b(age|old|older|oldest|ancient|since|ago|history|"
                     r"historic|year[s]? old|existed|lifespan|founded|era)\b", re.I)
_SPEED_KW = re.compile(r"\b(speed|speeds|fast|fastest|faster|mph|km/?h|kmh|kph|"
                       r"knots|velocity|quick|quickest|swim|swimming|run|running|"
                       r"fly|flying|flight|race|racing|sprint)\b", re.I)
_SCALE_KW = re.compile(r"\b(tall|taller|tallest|height|deep|deepest|far|"
                       r"farther|distance|long|longest|size|huge|heavy|"
                       r"heaviest|big|biggest|massive)\b", re.I)


# Card kinds handled by the `_compose_story` dispatch. Later chunks add
# depictions here (waffle_grid, pictorial_race) as their renderers land.
CARD_KINDS = {"pictograph", "bubbles", "share", "comparison", "trend",
              "geo_us", "geo_world", "geo_city", "waffle_grid", "pictorial_race"}


def renderable(kind: str) -> bool:
    """Only offer a kind whose renderer is actually wired up in this build."""
    return (kind in _SCENE_BUILDERS or kind in charts.FULLFRAME_RENDERERS
            or kind in CARD_KINDS)


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
    n_periods = sum(1 for p in ins.items if getattr(p, "period", None))
    has_period = n_periods >= 2          # a real time series needs >=2 points
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
        "speed": unit_class == "speed" or bool(_SPEED_KW.search(topic)),
        "is_share": ins.kind == "share" or (unit_class == "pct" and n >= 3),
    }


def _candidates(ins, f: dict) -> list[str]:
    """Ranked depiction candidates for one insight, best first. Every entry
    DEPICTS the data — bare-number kinds are never produced here."""
    # Place data always maps.
    if f["place"]:
        return [f["place"]]
    ranked: list[str] = []
    # Speeds / velocities -> a RACE (real photos moving on a highway / in water).
    if f["speed"] and f["n"] >= 2:
        ranked += ["race", "rank_scene", "diorama"]
    # Time / age.
    if f["age"] and (f["has_period"] or getattr(ins, "viz_params", None)):
        ranked += ["timeline", "trend"]
    elif f["has_period"]:
        ranked += ["trend", "timeline"]
    # Scale / magnitude comparisons.
    if f["scale"] and f["dominance"] >= 1.6:
        ranked += ["scale_stack", "diorama"]
    # Shares / part-to-whole -> a filled SUBJECT (globe), not a grid.
    if f["is_share"]:
        ranked += ["fill_scene", "waffle_grid", "share"]
    # Single shock stat (one or two values) -> FILL a real photo of the subject
    # to the value. This is the image-first answer for a lone "30% increase" —
    # never an abstract bar/trend. Checked before the ranking branch so a single
    # value shows the TOPIC's photo, not a stray item label.
    if f["n"] <= 2:
        ranked += ["fill_scene", "diorama"]
    # One value dwarfs the rest of a real (3+) list -> real photos of each.
    elif f["dominance"] >= 2.0:
        ranked += ["rank_scene", "diorama", "fill_scene"]
    # General ranking / comparison -> REAL PHOTOS of each thing (big rows), then
    # the illustrated diorama. NO lazy dots/bubbles for a real ranking.
    ranked += ["rank_scene", "diorama"]
    # De-dup preserving order, keep only renderable kinds.
    seen, out = set(), []
    for k in ranked:
        if k not in seen and renderable(k):
            seen.add(k)
            out.append(k)
    out.append("bubbles")            # terminal guarantee
    return out


# --- Render-time creative director -------------------------------------------
# The heart of the channel: at RENDER time, for EACH data point, an LLM invents
# the single most creative, image-first way to depict THAT data — fresh, every
# video. No baked choice; the AI decides on the spot. If the LLM is unreachable
# the deterministic image-first passes below still guarantee a real depiction.

# The element kit the AI composes a depiction from. Abstract chart shapes
# (bar/bubble) are deliberately absent — every depiction SHOWS the subject.
_KIT = (
    "  - object: a real photo / cut-out of a CONCRETE subject, sized by its "
    "value, with number+label. Needs `subject` + `data.value_from`. Put 2-5 in "
    "region 'ground-row' for a ranking of real things.\n"
    "  - fill_object: fill a real SUBJECT bottom-up to a % / share / single shock "
    "stat (a globe for Earth/water, a lung, a burning forest, a brain). Needs "
    "`subject` + `data.value_from`.\n"
    "  - stack: stack value/per_value copies of a subject to show magnitude. "
    "Needs `subject` + `data.value_from` + `data.per_value`.\n"
    "  - orbit_group: bodies orbit a centre at radii by value (distances/counts). "
    "region 'full'.\n"
    "  - timeline_axis: a marker travels a time/number axis (ages, dates, years). "
    "region 'full'.\n"
    "  - number: a big count-up — ONLY as an accent on top of an image, never "
    "alone. `data.value_from`.\n"
    "  - caption: a short text line. `text`.\n"
)

_invent_cache: dict = {}


def _insight_key(ins) -> tuple:
    items = tuple((p.label, round(float(p.value), 4), getattr(p, "period", None))
                  for p in (ins.items or []))
    return ((ins.topic or ""), (ins.unit or ""), items)


def _invent_scene(ins):
    """Ask the LLM to invent the most creative image-first SCENE for THIS data.
    Returns a validated scene dict, or None (LLM down / invalid -> deterministic
    fallback picks up). Cached per data signature so a re-render is stable+free."""
    import json
    key = _insight_key(ins)
    if key in _invent_cache:
        return _invent_cache[key]
    scene = None
    try:
        from script_generator import _call_llm, _strip_fence
        items = [{"label": p.label, "value": p.value,
                  **({"period": p.period} if getattr(p, "period", None) else {})}
                 for p in ins.items]
        sysp = ("You are the creative director of a top-tier data-explainer "
                "channel. For ONE data point you invent the single most "
                "entertaining, image-first way to VISUALLY depict it. Output ONE "
                "JSON scene object, nothing else.")
        user = (
            f"Topic: {ins.topic!r}\nUnit: {ins.unit!r}\n"
            f"Data points: {json.dumps(items)}\n\n"
            "Compose a `scene` from this element kit:\n" + _KIT + "\n"
            "REGIONS: full, center, hero, left, right, top, bottom, ground-row, "
            "grid-1..4.\n\n"
            "RULES:\n"
            "- SHOW THE THING. The scene MUST contain >=1 image element (object / "
            "fill_object / stack) or a holistic time depiction (timeline_axis / "
            "orbit_group). Depict the value THROUGH the image: fill it, size it, "
            "position it, repeat it, or move it.\n"
            "- There is NO bar and NO bubble. Never a lone number. Abstract chart "
            "shapes are banned.\n"
            "- `subject` must be a CONCRETE, real, photographable thing (an "
            "animal, a planet, a landmark, a lung, a wildfire) — never an "
            "abstraction. Match it to the topic so viewers recognise it.\n"
            "- Pick the smartest shape for the data: a single % / shock stat -> "
            "fill_object of the subject; a ranking of things -> a ground-row of "
            "objects; ages/dates -> timeline_axis; distances/counts -> "
            "orbit_group; one huge magnitude -> stack or a hero object.\n"
            "- `data.value_from` is one of: 'star' (the max), 'total', or "
            "'item:<index>' (0-based) / 'item:<label>'.\n\n"
            'Return ONLY: {"title": true, "elements": [ ... ]}')
        raw = _strip_fence(_call_llm(sysp, user))
        spec = json.loads(raw)
        if viz_scene.validate(spec, ins):
            scene = spec
    except Exception as e:  # noqa: BLE001
        print(f"[director] render-time invent skipped: {type(e).__name__}: {e}",
              flush=True)
    _invent_cache[key] = scene
    return scene


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
        # place/trend/real-photo depictions may repeat (all good); the lazy shape
        # depictions must stay distinct within a video.
        if not (meta.get("place") or meta.get("time") or meta.get("repeatable")) \
                and kind in used:
            return False
        if meta.get("image"):
            if images >= image_budget:
                return False
            images += 1
        chosen[i] = kind
        used.add(kind)
        return True

    order = sorted(range(n), key=lambda i: (seed + i) % max(1, n))

    # Pass -1 — RENDER-TIME creative director. For each data point (except place
    # data, which is always better as a map), the LLM invents a fresh image-first
    # scene right now. This is the "AI decides per data point, every render" path;
    # it OVERRIDES any baked scene. Falls through silently if the LLM is down.
    if os.environ.get("VIZ_INVENT", "1") != "0":
        for i in order:
            if feats[i]["place"]:
                continue
            invented = _invent_scene(inss[i])
            if invented:
                inss[i].scene = invented

    # Pass 0 — honour a valid SCENE (the render-time invention above, or a
    # previously-authored one). Bespoke scenes may repeat across segments (each is
    # distinct by construction), so "scene" is not added to `used`; only the image
    # budget bounds them.
    for i in order:
        sc = getattr(inss[i], "scene", None)
        if sc and viz_scene.validate(sc, inss[i]):
            cost = viz_scene.image_cost(sc)
            if images + cost <= image_budget:
                chosen[i] = "scene"
                images += cost

    # Pass 1 — honour a valid authored concept (the LLM's creative choice).
    for i in order:
        if chosen[i]:
            continue
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
        if k in _SCENE_BUILDERS:                 # deterministic scene token
            builder = getattr(viz_scene, _SCENE_BUILDERS[k])
            ins.scene = builder(ins)
            ins.kind = "scene"
        else:
            ins.kind = k                         # "scene" already has ins.scene set
