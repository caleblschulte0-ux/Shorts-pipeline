from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable, Sequence

from .contracts import CommandPlan


@dataclass(frozen=True)
class SvgBar:
    label: str
    value: float


class SvgMotionBuilder:
    """Dependency-free SVG scene generation for 1080x1920 Shorts graphics."""

    def bar_chart(self, title: str, bars: Sequence[SvgBar], *, width: int = 1080, height: int = 1920) -> str:
        if not bars:
            raise ValueError("at least one bar is required")
        maximum = max(bar.value for bar in bars)
        if maximum <= 0:
            raise ValueError("bar values must include a positive value")
        chart_top = 360
        chart_height = 1050
        left = 140
        usable_width = width - 260
        slot = chart_height / len(bars)
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#101114"/>',
            f'<text x="{width/2:g}" y="190" text-anchor="middle" font-family="sans-serif" font-size="66" font-weight="700" fill="white">{escape(title)}</text>',
        ]
        for index, bar in enumerate(bars):
            y = chart_top + index * slot
            bar_width = usable_width * (bar.value / maximum)
            parts.extend((
                f'<text x="{left}" y="{y + 42:g}" font-family="sans-serif" font-size="42" fill="white">{escape(bar.label)}</text>',
                f'<rect x="{left}" y="{y + 66:g}" width="0" height="70" rx="20" fill="#5fd3ff">'
                f'<animate attributeName="width" from="0" to="{bar_width:g}" dur="0.7s" begin="{index * 0.12:g}s" fill="freeze"/></rect>',
                f'<text x="{left + bar_width + 18:g}" y="{y + 120:g}" font-family="sans-serif" font-size="38" fill="white" opacity="0">{bar.value:g}'
                f'<animate attributeName="opacity" from="0" to="1" dur="0.2s" begin="{0.7 + index * 0.12:g}s" fill="freeze"/></text>',
            ))
        parts.append('</svg>')
        return "".join(parts)

    def comparison_card(self, headline: str, left_label: str, right_label: str, left_value: str, right_value: str) -> str:
        values = tuple(escape(value) for value in (headline, left_label, right_label, left_value, right_value))
        headline, left_label, right_label, left_value, right_value = values
        return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">
<rect width="1080" height="1920" fill="#101114"/><text x="540" y="210" text-anchor="middle" font-family="sans-serif" font-size="68" font-weight="700" fill="white">{headline}</text>
<g transform="translate(90 420)"><rect width="420" height="760" rx="42" fill="#20232a"/><text x="210" y="120" text-anchor="middle" font-family="sans-serif" font-size="44" fill="white">{left_label}</text><text x="210" y="410" text-anchor="middle" font-family="sans-serif" font-size="92" font-weight="700" fill="#5fd3ff">{left_value}</text></g>
<g transform="translate(570 420)"><rect width="420" height="760" rx="42" fill="#20232a"/><text x="210" y="120" text-anchor="middle" font-family="sans-serif" font-size="44" fill="white">{right_label}</text><text x="210" y="410" text-anchor="middle" font-family="sans-serif" font-size="92" font-weight="700" fill="#ffd166">{right_value}</text></g>
<path d="M540 330 L540 1320" stroke="white" stroke-width="8" opacity="0"><animate attributeName="opacity" from="0" to="0.5" dur="0.25s" begin="0.4s" fill="freeze"/></path></svg>'''


class GraphicsCommandPlanner:
    def manim(self, scene_file: str, scene_name: str, output_dir: str, *, quality: str = "m") -> CommandPlan:
        return CommandPlan("manim", ("manim", f"-q{quality}", "--format=mp4", "--media_dir", output_dir, scene_file, scene_name), inputs=(scene_file,), outputs=(output_dir,))

    def blender(self, blend_file: str, output_pattern: str, *, start_frame: int = 1, end_frame: int = 120) -> CommandPlan:
        return CommandPlan("blender", ("blender", "-b", blend_file, "-o", output_pattern, "-s", str(start_frame), "-e", str(end_frame), "-a"), inputs=(blend_file,), outputs=(output_pattern,))

    def imagemagick_card(self, background: str, overlay: str, output: str) -> CommandPlan:
        return CommandPlan("imagemagick", ("magick", background, overlay, "-gravity", "center", "-composite", "-strip", output), inputs=(background, overlay), outputs=(output,))

    def libreoffice_to_pdf(self, source: str, output_dir: str) -> CommandPlan:
        return CommandPlan("libreoffice", ("libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, source), inputs=(source,), outputs=(str(Path(output_dir) / (Path(source).stem + ".pdf")),))

    def graphviz(self, dot_file: str, output: str, *, engine: str = "dot") -> CommandPlan:
        return CommandPlan("graphviz", (engine, "-Tpng", dot_file, "-o", output), inputs=(dot_file,), outputs=(output,))

    def mermaid(self, source: str, output: str, *, width: int = 1080, height: int = 1920) -> CommandPlan:
        return CommandPlan("mermaid", ("mmdc", "-i", source, "-o", output, "-w", str(width), "-H", str(height), "-b", "transparent"), inputs=(source,), outputs=(output,))

    def cairosvg(self, source_svg: str, output_png: str, *, width: int = 1080, height: int = 1920) -> CommandPlan:
        return CommandPlan("cairosvg", ("python", "-m", "cairosvg", source_svg, "-o", output_png, "--output-width", str(width), "--output-height", str(height)), inputs=(source_svg,), outputs=(output_png,))

    def svg_frames_to_video(self, frames_pattern: str, output: str, *, fps: int = 30) -> CommandPlan:
        return CommandPlan("ffmpeg", ("ffmpeg", "-y", "-framerate", str(fps), "-i", frames_pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), output), inputs=(frames_pattern,), outputs=(output,))


def graphviz_dot(edges: Iterable[tuple[str, str]], *, directed: bool = True) -> str:
    graph_type = "digraph" if directed else "graph"
    operator = "->" if directed else "--"
    lines = [f"{graph_type} G {{", '  graph [bgcolor="transparent"];', '  node [shape=box, style="rounded,filled"];']
    for source, destination in edges:
        lines.append(f'  "{source}" {operator} "{destination}";')
    lines.append("}")
    return "\n".join(lines)
