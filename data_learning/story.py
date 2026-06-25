"""Story builder — multiple data pulls -> multiple charts -> one narrative.

A *story* chains several data segments. Each segment pulls its own data
(possibly from a different source), builds an insight, renders its OWN chart,
and contributes one spoken line + a punch. The story opens with a punchy,
attention-grabbing HOOK and ends with a closing takeaway, so a longer video
tells a real arc across 3-4 distinct charts.

Segment lines are auto-generated from the insight (so the spoken numbers are
always source-backed and the punch phrases are guaranteed verbatim). The hook
and closing are hand-written in the config for maximum catchiness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import charts, insights
from .insights import Insight
from .sources import get_source
from .sources.offline import OfflineSource

# Connectors give the sequence a story rhythm instead of a list feel.
CONNECTORS = ["", "Now look at this.", "But here's the twist.",
              "And it gets sharper.", "Then this."]
GREEN, RED, ORANGE, WHITE = "#50ff80", "#ff3030", "#ffaa30", "#ffffff"
FLASH = {GREEN: "#0d2818", RED: "#220404", ORANGE: "#2a1d05", WHITE: None}


@dataclass
class Segment:
    sentence: str
    chart_path: str | None
    punches: list[dict]
    source_footer: str
    topic: str
    role: str = ""
    kind: str = ""                      # viz kind; "diorama" renders full-frame
    # Every data point's pixel within the chart PNG: [{value, px, py}, ...].
    anchors: list = field(default_factory=list)


@dataclass
class Story:
    slug: str
    title: str
    hook: str
    closing: str
    segments: list[Segment]
    hashtags: list[str]
    sources: list[str] = field(default_factory=list)
    question: str = ""               # engagement CTA spoken + shown at the end

    def sentences(self) -> list[str]:
        # The closing line also SPEAKS the engagement question so the CTA is
        # heard, not just shown.
        close = self.closing + (" " + self.question if self.question else "")
        return [self.hook] + [s.sentence for s in self.segments] + [close]


def _fmtnum(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if float(value).is_integer():
        return f"{value:.0f}"
    return f"{value:.1f}"


def _num(value: float, unit: str) -> str:
    """Spoken form, WITH the unit in plain words so it's clear out loud."""
    u = (unit or "").lower()
    n = _fmtnum(value)
    if u in ("percent", "%", "rate"):
        return f"{n} percent"
    if u == "thousand dollars":
        return f"{n} thousand dollars"
    if u == "billion dollars":
        return f"{n} billion dollars"
    if u in ("dollars", "dollar", "usd"):
        return f"{n} dollars"
    if u == "million":
        return f"{n} million"
    if u == "years":
        return f"{n} years"
    if u == "hours":
        return f"{n} hours"
    return n          # index / ratio / bare count — meaning comes via explain


def _tok(value: float, unit: str) -> tuple[str, bool]:
    """The bare numeric token that appears in the sentence and on the chart
    (used to time the caption and match the ring)."""
    return _fmtnum(value), (unit or "").lower() in ("percent", "%", "rate")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _join(connector: str, clause: str) -> str:
    clause = _cap(clause)
    return f"{connector} {clause}" if connector else clause


def _find(script: str, needle: str) -> str | None:
    i = script.lower().find(needle.lower())
    return script[i:i + len(needle)] if i >= 0 else None


def _punch(sentence: str, value: float, unit: str, color: str) -> dict | None:
    token, pct = _tok(value, unit)
    # Whole-number match only: reject when the token is part of a larger
    # number ("4" inside "4.3"/"4.8", "1" inside "1,030") but still allow a
    # trailing sentence period ("...449."). So: not preceded by a digit/.,;
    # not followed by a digit, nor by a . or , that itself precedes a digit.
    if not re.search(r"(?<![\d.,])" + re.escape(token) + r"(?!\d)(?![.,]\d)",
                     sentence):
        return None
    p = {"phrase": token, "text": token + ("%" if pct else ""),
         "color": color, "duration": 1.8}
    if FLASH.get(color):
        p["flash_bg"] = FLASH[color]
    return p


def _punches_from_anchors(say: str, anchors: list, unit: str) -> list[dict]:
    """For a writer-authored line, circle whichever on-chart numbers it names.
    Each anchor is {value, ...}; we punch the ones whose value appears in the
    line (deduped, max 3) so the ring lands on the number as it's spoken."""
    out: list[dict] = []
    seen: set[str] = set()
    for a in anchors:
        v = a.get("value")
        if v is None:
            continue
        tok, _ = _tok(v, unit)
        if tok in seen:
            continue
        pp = _punch(say, v, unit, GREEN)
        if pp:
            out.append(pp)
            seen.add(tok)
    return out[:3]


def _segment_text(ins: Insight, connector: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (sentence, [(num_str, color)]) for one segment."""
    u = ins.unit
    items = ins.items
    if ins.kind in ("rank", "outlier"):
        star = items[0]
        sup = "lowest" if "lowest" in ins.main_insight.lower() else "highest"
        clause = f"{star.label} has the {sup} {ins.topic}, at {_num(star.value, u)}."
        return _join(connector, clause), [(star.value, u, GREEN)]
    if ins.kind == "comparison":
        hi, lo = items[0], items[1]
        clause = (f"{hi.label} is up {_num(hi.value, u)}, while {lo.label} "
                  f"is only {_num(lo.value, u)}.")
        return _join(connector, clause), [(hi.value, u, GREEN),
                                          (lo.value, u, ORANGE)]
    # trend — mention the peak so the spoken story matches the line shape.
    first, last = items[0], items[-1]
    peak = max(items, key=lambda p: p.value)
    if peak.value > last.value * 1.1 and peak.label not in (first.label, last.label):
        clause = (f"{_cap(ins.topic)} spiked from {_num(first.value, u)} to "
                  f"{_num(peak.value, u)} in {peak.label}, then fell to "
                  f"{_num(last.value, u)}.")
        return _join(connector, clause), [(peak.value, u, RED),
                                          (last.value, u, GREEN)]
    direction = "climbed" if last.value > first.value else "fell"
    clause = (f"{_cap(ins.topic)} {direction} from {_num(first.value, u)} in "
              f"{first.label} to {_num(last.value, u)} in {last.label}.")
    return _join(connector, clause), [(last.value, u, GREEN)]


def _build_insight(seg_cfg: dict):
    src = get_source(seg_cfg["source"])
    ds = src.fetch(seg_cfg["key"], seg_cfg.get("params"))
    baseline = None
    if seg_cfg.get("use_baseline"):
        baseline = (src.baseline(seg_cfg["key"], seg_cfg.get("params"))
                    if isinstance(src, OfflineSource)
                    else (seg_cfg.get("params") or {}).get("baseline"))
    ins = insights.build(ds, insight_type=seg_cfg.get("insight_type", "auto"),
                         baseline=baseline,
                         ascending=bool(seg_cfg.get("ascending", False)))
    if seg_cfg.get("topic"):
        ins.topic = seg_cfg["topic"]
    # Suggest a viz (final kind decided per-video in _finalize_viz). An explicit
    # `"viz"` hint wins; otherwise auto-detect whether the labels are PLACES
    # (states/countries/metros -> a map). Non-place data is decided later.
    viz = (seg_cfg.get("viz") or "").strip().lower()
    if viz in ("geo_us", "geo_world", "geo_city", "callouts", "diorama", "trend"):
        ins.suggested_viz = viz
    else:
        ins.suggested_viz = charts.place_scope_for([p.label for p in ins.items])
    return ins


def _spread(ins) -> float:
    """max/min value ratio — how dramatic (map-worthy / shock-worthy) a segment
    is. Used to pick which segment gets the one map / the big-number scene."""
    vals = [p.value for p in ins.items if p.value]
    return (max(vals) / min(vals)) if vals and min(vals) > 0 else 0.0


def _finalize_viz(inss: list) -> None:
    """Decide each segment's final `kind`. Rules (operator-mandated):
      * ANY place data -> a MAP, every time (states/countries -> choropleth,
        cities/metros -> pinned map). No cap.
      * time-series trends -> the styled line (the only 'chart' we keep).
      * everything else -> bold number CALLOUTS over the scene image.
    No dots, no icon-tiling, no bars, no bare numbers."""
    for ins in inss:
        sv = getattr(ins, "suggested_viz", None)
        if sv in ("geo_us", "geo_world", "geo_city"):
            ins.kind = sv                       # place -> map, always
        elif sv in ("callouts", "diorama"):
            ins.kind = sv
        elif sv == "trend" or ins.kind == "trend":
            ins.kind = "trend"                  # time-series keeps the line
        else:
            # rank/comparison/share/outlier -> illustrated proportional SCENE
            # (objects sized by value, numbers above). Falls back to callouts
            # automatically if image generation is unavailable.
            ins.kind = "diorama"


def build(story_cfg: dict, cfg: dict, workdir: Path, repo: Path) -> Story:
    """Construct a Story: fetch each segment's data, render its chart, and
    assemble the narration + punches."""
    chart_dir = workdir / "charts"
    segments: list[Segment] = []
    sources: list[str] = []
    # Build every insight first, then pick viz at the video level, then render.
    seg_cfgs = list(story_cfg["segments"])
    inss = [_build_insight(seg_cfg) for seg_cfg in seg_cfgs]
    _finalize_viz(inss)
    # NEVER open on a chart — viewers swipe away. Move trend (line) segments to
    # the end so the video opens on a map / diorama / scene. Stable within groups.
    order = sorted(range(len(inss)), key=lambda i: (inss[i].kind == "trend", i))
    seg_cfgs = [seg_cfgs[i] for i in order]
    inss = [inss[i] for i in order]
    if inss and inss[0].kind == "trend":      # all-trend video: don't lead w/ a line
        inss[0].kind = "callouts"
    for i, (seg_cfg, ins) in enumerate(zip(seg_cfgs, inss)):
        # A short "build" frame sequence (bars grow / line draws on) ending on
        # the exact static chart — the renderer plays it then holds the last
        # frame. Anchors come from the final frame so the rings still land.
        cpath, anchors = charts.render_story_build(
            ins, chart_dir, f"{story_cfg['slug']}_seg{i:02d}")
        say = seg_cfg.get("say")
        if say:
            # Writer-authored line: reference a number, then explain what it
            # MEANS. We circle whichever on-chart numbers the line names.
            sentence = say.strip()
            punches = _punches_from_anchors(sentence, anchors, ins.unit)
        else:
            connector = seg_cfg.get("connector",
                                    CONNECTORS[min(i, len(CONNECTORS) - 1)])
            sentence, nums = _segment_text(ins, connector)
            explain = seg_cfg.get("explain")
            if explain:
                sentence = sentence.rstrip() + " " + explain.strip()
            punches = [pp for pp in
                       (_punch(sentence, v, un, c) for v, un, c in nums) if pp]
        footer = ins.source.footer()
        if footer not in sources:
            sources.append(footer)
        segments.append(Segment(
            sentence, str(cpath) if cpath else None, punches, footer,
            ins.topic, role=seg_cfg.get("role", ""), kind=ins.kind, anchors=anchors))

    return Story(
        slug=story_cfg["slug"],
        title=story_cfg.get("title", story_cfg["slug"]),
        hook=story_cfg["hook"],
        closing=story_cfg.get("closing", "That's the story in the data."),
        segments=segments,
        hashtags=story_cfg.get("hashtags", []),
        sources=sources,
        question=(story_cfg.get("question")
                  or "Which number hit you hardest? Drop it in the comments."),
    )
