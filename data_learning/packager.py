"""Turn an :class:`Insight` into a base-pipeline package.

The output dict matches exactly what ``make_explainer_stacked.build_from_package``
consumes: ``{title, script, shots, punches, hashtags, music_vibe}`` (plus a
``_data_learning`` provenance block the base renderer simply ignores).

Two correctness guarantees the base renderer depends on:
  * every ``shot.phrase`` and ``punch.phrase`` is a *verbatim* substring of
    the script (the renderer aligns them against Whisper output);
  * numbers are written as digits ("2.2 percent"), matching how Whisper
    transcribes the TTS narration.

Per-video variation (rotating hooks/takeaways, deterministic per slug) is
what keeps an automated channel out of "template/inauthentic" territory.
"""
from __future__ import annotations

import hashlib

from .insights import Insight

# Rotating openers/closers — deterministic pick per slug gives variety
# across videos without randomness breaking reproducibility.
HOOKS = {
    "rank": [
        "The number one spot here is probably not what you would guess.",
        "One place is quietly beating everywhere else.",
        "The leader in this ranking is not the obvious one.",
    ],
    "comparison": [
        "These two numbers tell completely different stories.",
        "The headline number is hiding the real gap.",
        "Side by side, the difference is bigger than it looks.",
    ],
    "outlier": [
        "One of these is nowhere near the rest.",
        "Most of these cluster together. One does not.",
        "The pack is tight. Then there is the outlier.",
    ],
    "trend": [
        "This number moved faster than most people realize.",
        "The direction matters. The speed matters more.",
        "Look at how far this has shifted.",
    ],
}
TAKEAWAYS = {
    "rank": "The lesson: the leaderboard rarely matches the assumption.",
    "comparison": "The lesson: one number can hide where the real pressure is.",
    "outlier": "The lesson: averages hide the extremes that actually matter.",
    "trend": "The lesson: watch the trajectory, not just today's value.",
}

# Punch styling by role.
GREEN, RED, ORANGE, WHITE = "#50ff80", "#ff3030", "#ffaa30", "#ffffff"
FLASH = {GREEN: "#0d2818", RED: "#220404", ORANGE: "#2a1d05", WHITE: None}


def _pick(options: list[str], slug: str) -> str:
    h = int(hashlib.sha1(slug.encode()).hexdigest(), 16)
    return options[h % len(options)]


def _num(value: float, unit: str) -> str:
    """Narration-friendly number string (digits, spelled-out unit)."""
    if unit in ("percent", "%", "rate"):
        return f"{value:.1f} percent"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.1f}"


def _find_phrase(script: str, needle: str) -> str | None:
    """Return the verbatim slice of *script* matching *needle*
    case-insensitively, or None."""
    i = script.lower().find(needle.lower())
    if i < 0:
        return None
    return script[i:i + len(needle)]


def build_package(insight: Insight, *, slug: str, chart_path: str | None,
                  hashtags: list[str], music_vibe: str = "cinematic",
                  query_theme: str = "data chart graph statistics") -> dict:
    """Assemble the package dict in the base-pipeline schema."""
    unit = insight.unit
    items = insight.items

    # --- Script beats -------------------------------------------------
    hook = _pick(HOOKS.get(insight.kind, HOOKS["rank"]), slug)
    beats: list[str] = [hook]

    proof_numbers: list[tuple[str, str]] = []  # (number_str, role)

    if insight.kind in ("rank", "outlier"):
        star = items[0]
        beats.append(
            f"{star.label} leads at {_num(star.value, unit)}.")
        proof_numbers.append((_num(star.value, unit), "star"))
        for p in items[1:3]:
            beats.append(f"{p.label} follows at {_num(p.value, unit)}.")
            proof_numbers.append((_num(p.value, unit), "rest"))
        if insight.baseline:
            beats.append(
                f"For context, {insight.baseline.label} sits at "
                f"{_num(insight.baseline.value, unit)}.")
            proof_numbers.append((_num(insight.baseline.value, unit), "baseline"))
    elif insight.kind == "comparison":
        hi, lo = items[0], items[1]
        beats.append(f"{hi.label} comes in at {_num(hi.value, unit)}.")
        proof_numbers.append((_num(hi.value, unit), "star"))
        beats.append(f"But {lo.label} is only {_num(lo.value, unit)}.")
        proof_numbers.append((_num(lo.value, unit), "baseline"))
    else:  # trend
        first, last = items[0], items[-1]
        beats.append(f"In {first.label} it was {_num(first.value, unit)}.")
        proof_numbers.append((_num(first.value, unit), "rest"))
        beats.append(f"By {last.label} it reached {_num(last.value, unit)}.")
        proof_numbers.append((_num(last.value, unit), "star"))

    beats.append(TAKEAWAYS.get(insight.kind, ""))
    script = " ".join(b.strip() for b in beats if b.strip())

    # --- Shots --------------------------------------------------------
    # Hook shot (stock), proof shot (chart image, if any), then a couple
    # of context shots keyed to real substrings of the script.
    shots: list[dict] = []
    hook_phrase = (_find_phrase(script, hook.split(".")[0][:40]) or hook[:30]).strip()
    shots.append({"phrase": hook_phrase, "query": query_theme})

    # Anchor the chart to the strongest proof line.
    star_label = items[0].label
    proof_anchor = _find_phrase(script, star_label) or hook_phrase
    proof_shot = {"phrase": proof_anchor, "query": query_theme}
    if chart_path:
        proof_shot["image_url"] = chart_path
    shots.append(proof_shot)

    # One more context shot from the takeaway line.
    tk = TAKEAWAYS.get(insight.kind, "")
    tk_phrase = _find_phrase(script, "The lesson") or _find_phrase(script, tk[:30])
    if tk_phrase:
        shots.append({"phrase": tk_phrase, "query": query_theme})

    # --- Punches ------------------------------------------------------
    punches: list[dict] = []
    role_color = {"star": GREEN, "baseline": ORANGE, "rest": WHITE}
    seen: set[str] = set()
    for num_str, role in proof_numbers:
        phrase = _find_phrase(script, num_str)
        if not phrase or phrase.lower() in seen:
            continue
        seen.add(phrase.lower())
        color = role_color.get(role, WHITE)
        caps = num_str.replace(" percent", "%").upper()
        punch = {
            "phrase": phrase,
            "text": caps,
            "color": color,
            "size": 190,
            "duration": 2.0,
        }
        flash = FLASH.get(color)
        if flash:
            punch["flash_bg"] = flash
        punches.append(punch)

    return {
        "version": 1,
        "slug": slug,
        "title": _title(insight),
        "script": script,
        "shots": shots,
        "punches": punches,
        "hashtags": hashtags,
        "music_vibe": music_vibe,
        "_data_learning": {
            "kind": insight.kind,
            "source_footer": insight.source.footer(),
            "facts": [
                {"id": f.fact_id, "claim": f.claim, "value": f.value,
                 "unit": f.unit, "calculation": f.calculation}
                for f in insight.facts
            ],
        },
    }


def _title(insight: Insight) -> str:
    """Punchy 6-12 word YouTube title derived from the insight."""
    star = insight.items[0]
    topic = insight.topic[0].upper() + insight.topic[1:]
    if insight.kind == "rank":
        lowest = "lowest" in insight.main_insight.lower()
        sup = "Lowest" if lowest else "Highest"
        return f"{star.label} Has America's {sup} {topic}"
    if insight.kind == "comparison":
        lo = insight.items[1]
        return f"{star.label} vs {lo.label}: The {topic} Gap"
    if insight.kind == "outlier":
        return f"{star.label} Is The Big Outlier In {topic}"
    return f"How {topic} Has Shifted"
