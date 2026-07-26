from __future__ import annotations

from html import escape

from .models import AudioPlan, LayoutSpec, MotionPlan, StoryScene, W, H

BG = "#07101E"
CARD = "#13213A"
TEXT = "#F8FAFC"
MUTED = "#9DB0C8"
ACCENT = "#F2C14E"
CYAN = "#63D8E8"


def render_scene(scene: StoryScene, layout: LayoutSpec, audio: AudioPlan, motion: MotionPlan, archetype: str) -> str:
    hero = layout.hero
    caption = layout.caption
    secondary = layout.secondary
    cue_marks = "".join(
        f'<line x1="{80 + cue.at / scene.duration * 820:.1f}" y1="1720" x2="{80 + cue.at / scene.duration * 820:.1f}" y2="1780" stroke="{ACCENT}" stroke-width="8"/>'
        for cue in audio.cues
    )
    path = " ".join(f"{frame.x:.1f},{frame.y:.1f}" for frame in motion.keyframes)
    body = (
        f'<rect width="{W}" height="{H}" fill="{BG}"/>'
        f'<rect x="{hero.x}" y="{hero.y}" width="{hero.width}" height="{hero.height}" rx="46" fill="{CARD}" stroke="{CYAN}" stroke-width="8"/>'
        f'<polyline points="{path}" fill="none" stroke="{ACCENT}" stroke-width="14" stroke-dasharray="22 16"/>'
        f'<circle cx="{motion.keyframes[1].x}" cy="{motion.keyframes[1].y}" r="74" fill="{CYAN}"/>'
        f'<text x="{motion.keyframes[1].x}" y="{motion.keyframes[1].y + 12}" text-anchor="middle" font-family="Arial" font-size="38" font-weight="800" fill="{BG}">{escape(scene.focus)}</text>'
        f'<rect x="{caption.x}" y="{caption.y}" width="{caption.width}" height="{caption.height}" rx="30" fill="#0C1729" stroke="#2A3B56" stroke-width="4"/>'
        f'<text x="{caption.x + caption.width / 2}" y="{caption.y + 72}" text-anchor="middle" font-family="Arial" font-size="44" font-weight="800" fill="{TEXT}">{escape(scene.role.upper())}</text>'
        f'<text x="{caption.x + caption.width / 2}" y="{caption.y + 132}" text-anchor="middle" font-family="Arial" font-size="30" fill="{MUTED}">{escape(scene.narration[:55])}</text>'
    )
    if secondary:
        body += f'<rect x="{secondary.x}" y="{secondary.y}" width="{secondary.width}" height="{secondary.height}" rx="28" fill="#0C1729" stroke="{ACCENT}" stroke-width="4"/>'
        body += f'<text x="{secondary.x + secondary.width/2}" y="{secondary.y + secondary.height/2 + 12}" text-anchor="middle" font-family="Arial" font-size="34" font-weight="700" fill="{TEXT}">{escape(scene.visual_event.replace("_", " ")[:35])}</text>'
    body += f'<line x1="80" y1="1750" x2="900" y2="1750" stroke="#30415C" stroke-width="5"/>{cue_marks}'
    body += f'<text x="80" y="1840" font-family="Arial" font-size="30" fill="{MUTED}">ENTRY {motion.entry_edge.upper()} → EXIT {motion.exit_edge.upper()} · {archetype.upper()}</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">{body}</svg>'
