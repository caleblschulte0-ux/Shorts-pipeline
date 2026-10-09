"""The ONE line of text a Twitch video carries, drawn like the reposts.

Operator, 2026-10-08/09: no narrator, "a line or 2 of text on the screen",
"the text is in the bottom third not the middle", with the dead rose and
the crying face in it the way the big repost channels write it ("Los
thought he ended stream 😭"). drawtext cannot draw a colour emoji, so the
line is drawn here, with Pillow: sentence case, InterDisplay Bold, white
with a black outline, no box, wrapped to two lines, emoji from Noto Color
Emoji inline at the text's height. The PNG is overlaid on the whole video.

Layout is shared with the speech captions so the two never sit on each
other (operator, same day: "don't put captions over the captions"):
`LINE_Y` is the top of this line, `SPEECH_Y` the centre of the word-pop
captions, and `LINE_Y - SPEECH_Y` keeps a full caption's height between
them.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONT = REPO / "assets" / "fonts" / "InterDisplay-Bold.ttf"
EMOJI_FONT = Path("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf")
EMOJI_STRIKE = 109           # Noto Color Emoji's only bitmap size

CANVAS_W = 1080
LINE_Y = 1400                # top of the line: the bottom third
SPEECH_Y = 1210              # centre of the word-pop speech captions
SIZE = 64
MAX_W = CANVAS_W - 2 * 70
STROKE = 7

# anything outside the BMP's text ranges, plus the dingbat/symbol blocks
_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿"
                    "️‍]+")


def has_emoji_font() -> bool:
    return EMOJI_FONT.exists()


def _runs(text: str) -> list[tuple[str, bool]]:
    """[(chunk, is_emoji)] in order."""
    out, pos = [], 0
    for m in _EMOJI.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out


def clean(text: str) -> str:
    """One line of text, emoji kept only if they can be drawn."""
    t = " ".join(str(text or "").split())
    if t.isupper():                  # sentence case, never shouted
        t = t[:1] + t[1:].lower()
    if not has_emoji_font():
        t = " ".join(_EMOJI.sub("", t).split())
    return t


def _fonts(size: int):
    from PIL import ImageFont
    f = ImageFont.truetype(str(FONT), size)
    e = (ImageFont.truetype(str(EMOJI_FONT), EMOJI_STRIKE)
         if has_emoji_font() else None)
    return f, e


def _width(text: str, size: int, f) -> float:
    w = 0.0
    for chunk, emo in _runs(text):
        if emo:
            w += len(chunk.replace("️", "").replace("‍", "")) * \
                size * 1.15
        else:
            w += f.getlength(chunk)
    return w


def wrap(text: str, size: int = SIZE, max_w: int = MAX_W,
         max_lines: int = 2) -> tuple[list[str], int]:
    """(lines, size): at most two lines, shrinking only if it must."""
    words = []
    for w in clean(text).split():
        # an emoji rides with the word before it, never alone on a line
        if words and not _EMOJI.sub("", w):
            words[-1] += " " + w
        else:
            words.append(w)
    if not words:
        return [], size
    for fs in range(size, 39, -4):
        f, _ = _fonts(fs)
        lines, cur = [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if not cur or _width(trial, fs, f) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) == 2:
            # balance the two lines: a lone "is 😳" under a full line reads
            # as a mistake, so split where the wider line is narrowest
            splits = [(" ".join(words[:i]), " ".join(words[i:]))
                      for i in range(1, len(words))]
            lines = list(min(splits, key=lambda ab: max(
                _width(ab[0], fs, f), _width(ab[1], fs, f))))
        if len(lines) <= max_lines and all(
                _width(ln, fs, f) <= max_w for ln in lines):
            return lines, fs
    return lines, 40


def render(text: str, out: Path, size: int = SIZE) -> Path | None:
    """A transparent CANVAS_W-wide PNG of the line, or None when empty.
    Overlay it at (0, LINE_Y)."""
    from PIL import Image, ImageDraw
    lines, fs = wrap(text, size)
    if not lines:
        return None
    f, ef = _fonts(fs)
    lh = int(fs * 1.25)
    img = Image.new("RGBA", (CANVAS_W, lh * len(lines) + 2 * STROKE + 8),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = (CANVAS_W - _width(ln, fs, f)) / 2
        y = STROKE + i * lh
        for chunk, emo in _runs(ln):
            if not emo:
                d.text((x, y), chunk, font=f, fill="white",
                       stroke_width=STROKE, stroke_fill="black")
                x += f.getlength(chunk)
                continue
            for ch in chunk:
                if ch in "️‍":
                    continue
                g = Image.new("RGBA", (EMOJI_STRIKE * 2, EMOJI_STRIKE * 2),
                              (0, 0, 0, 0))
                ImageDraw.Draw(g).text((0, 0), ch, font=ef,
                                       embedded_color=True)
                bb = g.getbbox()
                if bb:
                    g = g.crop(bb)
                    side = int(fs * 1.05)
                    g = g.resize((side, side), Image.LANCZOS)
                    img.alpha_composite(g, (int(x + fs * 0.05),
                                            int(y + fs * 0.12)))
                x += fs * 1.15
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
