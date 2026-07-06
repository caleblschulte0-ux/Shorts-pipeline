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
    # An AI-invented, code-generated mechanic (the "make something new" path).
    "mechanic":       {"image": True,  "novelty": True,  "repeatable": True},
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
        from script_generator import _strip_fence
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
        raw = _strip_fence(_llm_try(sysp, user))
        spec = json.loads(raw)
        if viz_scene.validate(spec, ins):
            scene = spec
    except Exception as e:  # noqa: BLE001
        print(f"[director] render-time invent skipped: {type(e).__name__}: {e}",
              flush=True)
    _invent_cache[key] = scene
    return scene


# --- Invent a BRAND-NEW mechanic (the AI writes the drawing code) -------------
# This is the channel's top-level move: before touching the kit, the AI designs
# a depiction that doesn't exist yet and writes the PIL code for it. Accepted
# mechanics are saved to a growing library and fed back as examples, so the kit
# literally grows and the AI learns from its own best inventions.
_MECH_LIB = charts.__file__.rsplit("/", 1)[0] + "/viz_mechanics.json"
_mech_cache: dict = {}


def _llm_try(sysp: str, user: str) -> str:
    """Call the LLM for a render-time invention, failing OVER across backends.
    Render bursts hammer Groq's free tier (429s), so we lead with Gemini (higher
    free limits) and fall through to Groq then Anthropic — otherwise a single 429
    would silently drop the AI's creative decision for that data point."""
    from script_generator import _call_llm
    order = []
    if os.environ.get("GEMINI_API_KEY"):
        order.append("gemini")
    if os.environ.get("GROQ_API_KEY"):
        order.append("groq")
    if os.environ.get("ANTHROPIC_API_KEY"):
        order.append("anthropic")
    last = None
    for backend in (order or [None]):
        try:
            return _call_llm(sysp, user, backend=backend)
        except Exception as e:  # noqa: BLE001
            last = e
            continue
    raise last or RuntimeError("no LLM backend configured")

# The sandbox the mechanic code runs in — the AI must be told EXACTLY what it can
# call (see viz_scene._run_mechanic_frame for the real implementation).
_MECH_API = """\
You write the BODY of a function that draws ONE frame of a vertical 1080x1920
video. It runs once per frame with these names already in scope (NO imports, NO
while-loops, NO names with underscores):

  d        - PIL ImageDraw: d.rectangle/rounded_rectangle/ellipse/line/polygon/
             arc/pieslice/text(box_or_xy, ...). Use fill=rgba(COLOR, alpha).
  reveal   - float 0..1, the build progress. ANIMATE everything off this
             (grow/rise/sweep from 0 to its final state as reveal -> 1).
  values   - list[float] data;  labels - list[str];  vmax - max value;  n - count
  images   - dict label -> subject image (RGBA, may be None)
  subject_image(name) - fetch a real photo/cut-out of ANY subject you name
                        (a flame, a lung, a droplet); returns image or None
  paste(img, x, y, w=None, h=None)          - stamp a subject image
  fill_image(img, frac, x, y, w, h, direction='up', color=None)
                        - reveal a subject filled to `frac` (gauges/'X% of a thing')
  text(s, x, y, size=48, color=TEXT, center=False)   - labelled numbers
  font(size), rgba(color, alpha), clamp(v,lo,hi), lerp(a,b,t), math
  Colors: ACCENT, HIGHLIGHT, WARN, TEXT (RGB tuples)
  Safe drawing area: x in [RX0=40, RX1=1040], y in [RTOP=80, RBOT=1180].

HARD RULES:
- SHOW THE THING: you MUST place at least one real subject image (paste /
  fill_image / images / subject_image). A mechanic with no subject is rejected.
- Depict every data point THROUGH the visual (size/fill/position/count/motion),
  each with its label and value shown. NEVER a plain bar or bubble or lone number.
- Invent something we don't already have — a bespoke mechanic that fits THIS data.
"""


def _mechanic_examples(k: int = 2) -> list:
    import json
    try:
        with open(_MECH_LIB, encoding="utf-8") as fh:
            lib = json.load(fh)
        return [{"mechanic": m.get("mechanic"), "concept": m.get("concept"),
                 "code": m.get("code")} for m in lib[-k:]]
    except Exception:  # noqa: BLE001
        return []


def _record_mechanic(ins, spec) -> None:
    """Save an accepted mechanic to the growing library (dedup by name+code)."""
    if os.environ.get("VIZ_LIBRARY_WRITE", "1") == "0":
        return
    import json
    import hashlib
    try:
        try:
            with open(_MECH_LIB, encoding="utf-8") as fh:
                lib = json.load(fh)
        except Exception:  # noqa: BLE001
            lib = []
        sig = hashlib.sha1((spec.get("mechanic", "") + spec.get("code", ""))
                           .encode()).hexdigest()[:12]
        if any(m.get("sig") == sig for m in lib):
            return
        lib.append({"sig": sig, "mechanic": spec.get("mechanic", ""),
                    "concept": spec.get("concept", ""), "code": spec.get("code", ""),
                    "topic": ins.topic or ""})
        lib = lib[-60:]                       # keep the corpus bounded
        with open(_MECH_LIB, "w", encoding="utf-8") as fh:
            json.dump(lib, fh, indent=1, ensure_ascii=False)
    except Exception as e:  # noqa: BLE001
        print(f"[director] mechanic save skipped: {e}", flush=True)


def _invent_mechanic(ins):
    """Ask the LLM to INVENT a new visual mechanic and write its drawing code.
    Returns a spec {mechanic, concept, code, title} or None. Cached per data sig."""
    import json
    key = _insight_key(ins)
    if key in _mech_cache:
        return _mech_cache[key]
    spec = None
    try:
        from script_generator import _strip_fence
        items = [{"label": p.label, "value": p.value,
                  **({"period": p.period} if getattr(p, "period", None) else {})}
                 for p in ins.items]
        exs = _mechanic_examples(2)
        ex_blob = ("\nMechanics we've invented before (learn, then do something "
                   "NEW):\n" + json.dumps(exs)) if exs else ""
        sysp = ("You are the creative director + creative coder of a top-tier "
                "data channel. You INVENT brand-new visual mechanics and write "
                "the Python/PIL code that draws them. Output ONE JSON object only.")
        user = (
            f"Topic: {ins.topic!r}\nUnit: {ins.unit!r}\n"
            f"Data points: {json.dumps(items)}\n\n"
            + _MECH_API + ex_blob + "\n\n"
            'Return ONLY: {"mechanic": "short-name", "concept": "one sentence", '
            '"code": "the frame-drawing body as a Python string"}')
        raw = _strip_fence(_llm_try(sysp, user))
        cand = json.loads(raw)
        if isinstance(cand, dict) and viz_scene.validate_mechanic(cand):
            cand["title"] = True
            spec = cand
    except Exception as e:  # noqa: BLE001
        print(f"[director] mechanic invent skipped: {type(e).__name__}: {e}",
              flush=True)
    _mech_cache[key] = spec
    return spec


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

    # Pass -1 — RENDER-TIME creative director, per data point (skip place data,
    # which is always better as a map). The AI's FIRST move is to INVENT A BRAND
    # -NEW mechanic — it writes the drawing code itself (procedural, sandboxed).
    # Only if that can't be produced does it fall to composing from the kit. This
    # is the "make something new first, then get creative with the kit" path; it
    # OVERRIDES any baked choice and falls through silently if the LLM is down.
    if os.environ.get("VIZ_INVENT", "1") != "0":
        for i in order:
            if feats[i]["place"]:
                continue
            mech = _invent_mechanic(inss[i])
            if mech and viz_scene.mechanic_dry_ok(mech, inss[i]):
                inss[i].scene = mech                 # a procedural mechanic
                _record_mechanic(inss[i], mech)      # grow the library
                if images < image_budget:
                    images += 1
                chosen[i] = "mechanic"
                continue
            invented = _invent_scene(inss[i])        # fall to the kit
            if invented:
                inss[i].scene = invented

    # Pass 0 — honour a valid SCENE (the render-time kit invention above, or a
    # previously-authored one). Bespoke scenes may repeat across segments (each is
    # distinct by construction), so "scene" is not added to `used`; only the image
    # budget bounds them.
    for i in order:
        if chosen[i]:
            continue
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
