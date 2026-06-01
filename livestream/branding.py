"""Channel identity for the livestream.

One channel, so one logo/avatar that sits on every frame. Drop your real logo
at livestream/assets/logo.png (PNG with transparency works best). If it's
missing, ensure_logo() generates a labeled placeholder badge so the pipeline
still runs — and prints a clear note that it's a placeholder.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.shell import run

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
LOGO_PATH = ASSETS / "logo.png"


@dataclass(frozen=True)
class Channel:
    name: str = "My Channel"
    initials: str = "MC"        # used only for the placeholder badge
    accent: str = "1e3a6e"      # placeholder badge background (hex)
    logo_corner: str = "tr"     # tl|tr|bl|br
    logo_scale_w: int = 200     # logo width in px on the 1080-wide frame
    logo_opacity: float = 0.85


CHANNEL = Channel()


def generate_placeholder_logo(out: Path, text: str, bg: str, size: int = 320) -> Path:
    """A round accent-colored badge with the channel initials. Stand-in until a
    real logo is supplied."""
    out.parent.mkdir(parents=True, exist_ok=True)
    c = size / 2
    r = size / 2 - 8
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=0x{bg.lstrip('#')}:s={size}x{size}:d=1",
        "-vf", (
            f"format=rgba,"
            f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
            f"a='if(lt((X-{c})^2+(Y-{c})^2,{r}^2),255,0)',"
            f"drawtext=text='{text}':fontcolor=white:fontsize={int(size*0.40)}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:borderw=5:bordercolor=black@0.35"
        ),
        "-frames:v", "1", str(out),
    ])
    return out


def ensure_logo() -> Path:
    """Return the channel logo, generating a placeholder if none is provided."""
    if LOGO_PATH.exists():
        return LOGO_PATH
    placeholder = ASSETS / "logo_placeholder.png"
    generate_placeholder_logo(placeholder, CHANNEL.initials, CHANNEL.accent)
    print(f"[branding] no logo at {LOGO_PATH} — using generated placeholder "
          f"({placeholder.name}). Drop your real logo there to brand the stream.")
    return placeholder
