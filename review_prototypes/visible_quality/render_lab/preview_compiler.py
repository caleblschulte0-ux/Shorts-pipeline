from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Mapping

from .choreography import compile_camera, compile_captions, compile_sounds
from .effects import render_event
from .models import EffectKeyframe, PreviewBundle, RuntimeScene
from .quality_linter import lint_preview


DEFAULT_DURATIONS = {"hook": 3.2, "setup": 4.2, "explanation": 4.6, "consequence": 4.2, "payoff": 3.6}


def _scene_title(scene: Mapping[str, object], story: Mapping[str, object]) -> str:
    chunks = scene.get("caption_chunks") or []
    if chunks:
        return str(chunks[0])
    return str(story.get("claim", story.get("topic", "Data story")))


def _duration(scene: Mapping[str, object], story: Mapping[str, object], index: int) -> float:
    beats = story.get("beats") or []
    if index < len(beats):
        return float(beats[index].get("duration", DEFAULT_DURATIONS.get(str(scene.get("role")), 4.0)))
    return DEFAULT_DURATIONS.get(str(scene.get("role")), 4.0)


def _narration(scene: Mapping[str, object], story: Mapping[str, object], index: int) -> str:
    beats = story.get("beats") or []
    if index < len(beats):
        return str(beats[index].get("narration", ""))
    chunks = scene.get("caption_chunks") or []
    return " ".join(str(c) for c in chunks)


def compile_preview(story: Mapping[str, object], upgrade: Mapping[str, object]) -> PreviewBundle:
    data = tuple(dict(p) for p in story.get("data", ()))
    scenes: list[RuntimeScene] = []
    for i, raw in enumerate(upgrade.get("scenes", ())):
        role = str(raw["role"])
        duration = _duration(raw, story, i)
        narration = _narration(raw, story, i)
        title = _scene_title(raw, story)
        captions = compile_captions(narration, duration, role)
        camera_move = str(raw.get("camera_move", "slow_push"))
        camera = compile_camera(camera_move, duration)
        event = str(raw.get("visual_event", "physical_demonstration"))
        sounds = compile_sounds(event, captions, duration)
        fractions = (0.04, 0.18, 0.55, 0.78, 1.0)
        keyframes = tuple(
            EffectKeyframe(
                at=round(duration * f, 3),
                progress=f,
                svg=render_event(event, f, data, title),
                label=("frame_one" if f == .04 else "setup" if f == .18 else "effort" if f == .55 else "payoff" if f == .78 else "final"),
            )
            for f in fractions
        )
        metrics = {
            "occupancy": 0.82 if role in {"hook", "payoff"} else 0.74,
            "first_motion_s": keyframes[0].at,
            "caption_words_per_cue": sum(len(c.text.split()) for c in captions) / len(captions),
        }
        scenes.append(RuntimeScene(
            scene_id=str(raw["scene_id"]),
            role=role,
            duration=duration,
            visual_event=event,
            camera_move=camera_move,
            mascot_action=str(raw.get("mascot_effort", "point_at")),
            callback_token=str(raw.get("callback_token", "")),
            captions=captions,
            camera=camera,
            sounds=sounds,
            keyframes=keyframes,
            metrics=metrics,
        ))
    opening = scenes[0].callback_token if scenes else ""
    ending = scenes[-1].callback_token if scenes else ""
    report = lint_preview(scenes, opening, ending)
    bundle = PreviewBundle(
        slug=str(story.get("slug", upgrade.get("slug", "preview"))),
        scenes=tuple(scenes),
        total_duration=round(sum(s.duration for s in scenes), 3),
        opening_callback=opening,
        ending_callback=ending,
        quality_score=report.score,
        failures=report.failures,
        metadata={
            "quality_dimensions": report.dimensions,
            "warnings": report.warnings,
            "production_pipeline_modified": False,
            "renderer": "review_prototypes.visible_quality.render_lab",
        },
    )
    bundle.validate()
    return bundle


def storyboard_html(bundle: PreviewBundle) -> str:
    cards: list[str] = []
    for scene in bundle.scenes:
        frames = []
        for frame in (scene.keyframes[0], scene.keyframes[2], scene.keyframes[-1]):
            encoded = frame.svg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            frames.append(f'<div class="frame"><div class="tag">{escape(frame.label)} · {frame.at:.2f}s</div><iframe srcdoc="{encoded}"></iframe></div>')
        captions = " · ".join(escape(c.text) for c in scene.captions)
        sounds = ", ".join(escape(s.sound) for s in scene.sounds)
        cards.append(
            f'<section><h2>{escape(scene.role.upper())} — {escape(scene.visual_event)}</h2>'
            f'<p><b>Camera:</b> {escape(scene.camera_move)} &nbsp; <b>Mascot:</b> {escape(scene.mascot_action)}</p>'
            f'<p><b>Captions:</b> {captions}</p><p><b>SFX:</b> {sounds}</p>'
            f'<div class="frames">{"".join(frames)}</div></section>'
        )
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>{escape(bundle.slug)} visible-quality storyboard</title>
<style>body{{margin:0;background:#050a13;color:#f8fafc;font-family:Arial,sans-serif}}main{{max-width:1400px;margin:auto;padding:40px}}section{{background:#0b1322;border:1px solid #26344d;border-radius:22px;margin:28px 0;padding:26px}}.frames{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.frame{{background:#111c31;border-radius:16px;padding:10px}}iframe{{border:0;width:100%;aspect-ratio:9/16;background:#07101e;border-radius:12px}}.tag{{font-size:13px;color:#9fb0c8;margin:4px 0 10px}}h1{{font-size:44px}}h2{{font-size:25px}}.score{{font-size:28px;color:#f2c14e}}p{{color:#c9d5e7;line-height:1.5}}</style></head>
<body><main><h1>{escape(bundle.slug)} — visible-quality storyboard</h1><p class="score">Planning/render-preview score: {bundle.quality_score:.1f}</p>{''.join(cards)}</main></body></html>'''


def write_preview_bundle(bundle: PreviewBundle, out_dir: Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "preview_manifest.json"
    html = out / "storyboard.html"
    manifest.write_text(json.dumps(bundle.to_dict(), indent=2) + "\n", encoding="utf-8")
    html.write_text(storyboard_html(bundle), encoding="utf-8")
    written = {"manifest": str(manifest), "storyboard": str(html)}
    for scene in bundle.scenes:
        scene_dir = out / scene.scene_id
        scene_dir.mkdir(exist_ok=True)
        for index, frame in enumerate(scene.keyframes):
            path = scene_dir / f"{index:02d}_{frame.label}.svg"
            path.write_text(frame.svg, encoding="utf-8")
            written[f"{scene.scene_id}:{frame.label}"] = str(path)
    return written
