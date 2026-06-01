"""Generated abstract / semi-abstract visual assets — no external media, no APIs.

Additive to the shared core. Used by the livestream module to produce themed
background loops from ffmpeg's synthetic sources only. The main app does NOT use
this; adding it does not change make_short.py's output (tools/verify_identical.py).

Two generators:
  generate_abstract_clip() — a simple moving multi-stop gradient (legacy).
  generate_scene_clip()    — a detailed, stylized "scene": sky + stars + aurora +
                             horizon haze + sun/moon glow + drifting clouds +
                             LAYERED ridges (depth) + tree-line foreground +
                             two seasonal particle layers (near/far) + grain.
                             Stylized, not photoreal. Loops seamlessly: every
                             moving layer travels a whole number of screen-spans
                             per loop, so no boomerang is needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import H, W
from .shell import run


# ---------- legacy abstract gradient ----------

def generate_abstract_clip(
    out: Path,
    duration: float,
    *,
    colors: list[str],
    speed: float = 0.012,
    fps: int = 30,
    w: int = W,
    h: int = H,
    vignette: bool = True,
) -> Path:
    """Render a moving multi-stop gradient (the original abstract look)."""
    palette = [c.lstrip("#") for c in colors][:8]
    if len(palette) < 2:
        raise ValueError("generate_abstract_clip needs at least 2 colors")
    c_args = ":".join(f"c{i}=0x{c}" for i, c in enumerate(palette))
    src = (
        f"gradients=s={w}x{h}:{c_args}:n={len(palette)}"
        f":x0=0:y0=0:x1={w}:y1={h}:speed={speed}:d={duration:.3f}:r={fps}"
    )
    vf = "vignette" if vignette else "null"
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", src,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        str(out),
    ])
    return out


# ---------- detailed stylized scene ----------

@dataclass
class RidgeLayer:
    """One silhouette layer. Stack several back-to-front for depth. `jag_amp`>0
    adds a spiky tree-canopy edge (foreground forest)."""
    base: float                       # baseline as fraction of height (0=top)
    color: str                        # hex
    sines: tuple = ((100, 200, 0.0), (45, 70, 1.0))   # (amp_px, period_px, phase)
    jag_amp: float = 0.0              # px; spiky canopy detail
    jag_period: float = 26.0          # px between tree spikes


@dataclass
class SceneSpec:
    """A detailed stylized scene. Themes build one of these."""
    sky_top: str
    sky_bottom: str
    ridges: tuple = (
        RidgeLayer(0.62, "16203f", ((70, 260, 0.0), (28, 90, 0.6))),
        RidgeLayer(0.72, "0e1630", ((110, 190, 0.7), (44, 70, 1.2))),
        RidgeLayer(0.82, "070b1c", ((70, 150, 0.2),), jag_amp=46, jag_period=24),
    )
    glow: bool = True
    glow_x: float = 0.70
    glow_y: float = 0.18
    glow_radius: int = 120
    glow_color: str = "f0f4ff"
    haze: bool = True                 # atmospheric light band along the horizon
    haze_strength: int = 120          # peak alpha (0-255)
    stars: bool = False               # star field in the sky (night scenes)
    star_density: int = 4             # dots per-mille in the sky band
    aurora: bool = False              # wavy light ribbon high in the sky
    aurora_color: str = "5cffb0"
    aurora_y: float = 0.20            # centerline as fraction of height
    aurora_amp: int = 80              # wave amplitude (px)
    aurora_strength: int = 90         # peak alpha
    clouds: bool = False              # slow-drifting wispy band
    cloud_color: str = "c8d2e6"
    cloud_y: float = 0.22             # band center as fraction of height
    cloud_strength: int = 110         # peak alpha
    cloud_speed: float = 1.0          # screen-widths per loop (integer = seamless)
    fog: bool = False                 # low mist band over the hills
    fog_y: float = 0.66               # band center as fraction of height
    fog_strength: int = 70            # peak alpha
    fog_color: str = "dce4f0"
    cabin: bool = False               # cozy cabin with a warm lit window
    cabin_x: float = 0.30             # cabin center as fraction of width
    cabin_base: float = 0.86          # ground line as fraction of height
    cabin_w: int = 150
    cabin_h: int = 120
    roof_h: int = 78
    window_color: str = "ffcf6b"
    smoke: bool = True                # soft chimney plume (only drawn with cabin)
    smoke_color: str = "9aa3b0"
    smoke_strength: int = 60
    particles: str = "snow"           # "snow" | "leaves" | "none"
    particle_color: str = "ffffff"
    particle_density: int = 8         # dots per-mille (higher = denser)
    particles_near: bool = True       # add a chunkier, faster foreground layer
    grain: int = 6                    # subtle film grain (0 = off)
    vignette: bool = True


def _rgb(hex_str: str) -> tuple[int, int, int]:
    c = hex_str.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _still(out: Path, expr_r, expr_g, expr_b, expr_a, w: int, h: int) -> None:
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:d=1",
        "-vf", f"format=rgba,geq=r='{expr_r}':g='{expr_g}':b='{expr_b}':a='{expr_a}'",
        "-frames:v", "1", str(out),
    ])


def _make_sky(out: Path, top: str, bottom: str, w: int, h: int) -> None:
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i",
        (f"gradients=s={w}x{h}:c0=0x{top.lstrip('#')}:c1=0x{bottom.lstrip('#')}"
         f":n=2:x0=0:y0=0:x1=0:y1={h}:speed=0.00001:d=1"),
        "-frames:v", "1", str(out),
    ])


def _make_glow(out: Path, cx: int, cy: int, radius: int, color: str, w: int, h: int) -> None:
    r, g, b = _rgb(color)
    _still(out, r, g, b, f"255*exp(-((X-{cx})^2+(Y-{cy})^2)/(2*{radius}^2))", w, h)


def _make_haze(out: Path, y: int, strength: int, color: str, w: int, h: int) -> None:
    r, g, b = _rgb(color)
    _still(out, r, g, b, f"{strength}*exp(-((Y-{y})^2)/(2*150^2))", w, h)


def _make_stars(out: Path, density: int, horizon_y: int, w: int, h: int) -> None:
    thresh = max(1, density)
    _still(out, 255, 255, 255,
           f"if(lt(Y\\,{horizon_y})*lt(random(1)*1000\\,{thresh}),200,0)", w, h)


def _make_aurora(out: Path, spec: SceneSpec, w: int, h: int) -> None:
    r, g, b = _rgb(spec.aurora_color)
    cy = f"({spec.aurora_y * h:.1f}+{spec.aurora_amp}*sin(6.28319*X/{w}))"
    _still(out, r, g, b,
           f"clip({spec.aurora_strength}*exp(-((Y-{cy})^2)/(2*60^2)),0,255)", w, h)


def _make_clouds_strip(out: Path, spec: SceneSpec, w: int, h: int) -> None:
    # 2W wide, identical left/right halves (all X-frequencies are integer
    # multiples of 2*pi/W) so a one-screen-width scroll wraps seamlessly.
    r, g, b = _rgb(spec.cloud_color)
    wave = f"(0.5+0.5*sin(6.28319*X/{w}+1.2*sin(6.28319*2*X/{w})))"
    vert = f"exp(-((Y-{spec.cloud_y * h:.1f})^2)/(2*230^2))"
    _still(out, r, g, b, f"clip({spec.cloud_strength}*{wave}*{vert},0,255)", 2 * w, h)


def _make_fog(out: Path, spec: SceneSpec, w: int, h: int) -> None:
    r, g, b = _rgb(spec.fog_color)
    _still(out, r, g, b, f"clip({spec.fog_strength}*exp(-((Y-{spec.fog_y * h:.1f})^2)/(2*70^2)),0,255)", w, h)


def _make_cabin(out: Path, spec: SceneSpec, w: int, h: int) -> None:
    cx = spec.cabin_x * w
    by = spec.cabin_base * h
    half = spec.cabin_w / 2
    roof_half = half + 22
    top_y = by - spec.cabin_h - spec.roof_h
    mid_y = by - spec.cabin_h
    body = f"(lt(abs(X-{cx:.1f})\\,{half:.1f})*gt(Y\\,{mid_y:.1f})*lt(Y\\,{by:.1f}))"
    roof = (f"(gt(Y\\,{top_y:.1f})*lt(Y\\,{mid_y:.1f})*"
            f"lt(abs(X-{cx:.1f})\\,{roof_half:.1f}*((Y-{top_y:.1f})/{spec.roof_h})))")
    _still(out, 12, 10, 14, f"if(gt({body}+{roof},0),255,0)", w, h)


def _make_window_glow(out: Path, spec: SceneSpec, w: int, h: int) -> None:
    cx = spec.cabin_x * w
    wy = spec.cabin_base * h - spec.cabin_h * 0.42
    _make_glow(out, int(cx), int(wy), 24, spec.window_color, w, h)


def _make_smoke(out: Path, spec: SceneSpec, w: int, h: int) -> None:
    r, g, b = _rgb(spec.smoke_color)
    sx = spec.cabin_x * w + spec.cabin_w * 0.22          # chimney sits off-center
    apex = spec.cabin_base * h - spec.cabin_h - spec.roof_h
    yy = f"({apex:.1f}-Y)"                                # height above the roof apex
    sig = f"(8+0.16*{yy})"                                # plume widens as it rises
    a = (f"{spec.smoke_strength}*gt({yy},0)*exp(-({yy})/150)"
         f"*exp(-((X-{sx:.1f})^2)/(2*{sig}^2))")
    _still(out, r, g, b, f"clip({a},0,255)", w, h)


def _make_particle_strip(out: Path, color: str, density: int, w: int, h: int, dot_scale: int = 1) -> None:
    # W x (2H) field whose top and bottom H are IDENTICAL, so scrolling one
    # screen-height per loop wraps seamlessly. density = dots per-mille.
    # dot_scale>1 renders the dot field at lower res then upscales -> chunkier
    # flakes for a nearer/foreground layer.
    r, g, b = _rgb(color)
    thresh = max(1, density)
    tw, th = max(1, w // dot_scale), max(1, h // dot_scale)
    tile = out.with_name("_ptile.png")
    _still(tile, r, g, b, f"if(lt(random(1)*1000\\,{thresh}),220,0)", tw, th)
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(tile), "-i", str(tile),
        "-filter_complex",
        f"[0:v][1:v]vstack=inputs=2,scale={w}:{2*h}:flags=neighbor[v]",
        "-map", "[v]", "-frames:v", "1", str(out),
    ])
    tile.unlink(missing_ok=True)


def _bake(out: Path, layers: list[Path], w: int, h: int, *, transparent: bool) -> None:
    """Flatten a stack of still PNG layers into one image (single ffmpeg frame).

    transparent=True composes over a fully transparent canvas and keeps the alpha
    channel, so the plate can be overlaid on top of moving layers underneath it.
    """
    # Start from the first real layer (its PNG already carries the right alpha) and
    # overlay the rest. For a transparent plate we keep RGBA so the sky shows through
    # where nothing was drawn; for an opaque plate (sky-backed) we flatten to RGB.
    inputs: list[str] = []
    graph: list[str] = []
    cur: str | None = None
    for i, p in enumerate(layers):
        inputs += ["-loop", "1", "-i", str(p)]
        if cur is None:
            cur = f"{i}:v"
        else:
            graph.append(f"[{cur}][{i}:v]overlay=format=auto[bk{i}]")
            cur = f"bk{i}"
    graph.append(f"[{cur}]format={'rgba' if transparent else 'rgb24'}[v]")
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        *inputs, "-filter_complex", ";".join(graph),
        "-map", "[v]", "-frames:v", "1", str(out),
    ])


def generate_scene_clip(
    out: Path,
    duration: float,
    spec: SceneSpec,
    *,
    fps: int = 30,
    w: int = W,
    h: int = H,
    workdir: Path | None = None,
    render_scale: float = 1.0,
) -> Path:
    """Render a detailed stylized scene. Seamless by construction.

    render_scale < 1.0 composites every layer at a smaller internal resolution
    and upscales the final frame (e.g. 0.5 ~= 4x fewer pixels, much faster, a
    touch softer). Output dimensions stay w x h regardless.
    """
    wd = workdir or out.parent
    out_w, out_h = w, h                                   # final delivered dims
    rw = max(2, round(w * render_scale) // 2 * 2)        # internal (even) composite dims
    rh = max(2, round(h * render_scale) // 2 * 2)
    scaled = (rw, rh) != (out_w, out_h)
    # Layers (the still PNGs) are always drawn at full resolution so absolute-pixel
    # geometry — cabin, glow radii, ridge amplitudes — looks identical regardless of
    # render_scale. Only the per-frame composite is done at the smaller (rw x rh) size,
    # then upscaled. So render_scale is purely a speed/sharpness knob, not a look change.
    horizon_y = int(min(r.base for r in spec.ridges) * h)

    tmps: list[Path] = []

    # --- Build the still layers, split by z-order around the drifting clouds. ---
    # Everything except clouds and particles is static, so we flatten it into one or
    # two pre-composited plates. The expensive per-frame pass then only has to overlay
    # the moving layers (clouds + particles) instead of ~12 static ones.
    back: list[Path] = []     # behind the clouds (deep sky)
    front: list[Path] = []    # in front of the clouds (haze, hills, cabin)

    sky = wd / "_sky.png"; _make_sky(sky, spec.sky_top, spec.sky_bottom, w, h); tmps.append(sky)
    back.append(sky)
    if spec.stars:
        stars = wd / "_stars.png"; _make_stars(stars, spec.star_density, horizon_y, w, h); tmps.append(stars)
        back.append(stars)
    if spec.aurora:
        aur = wd / "_aurora.png"; _make_aurora(aur, spec, w, h); tmps.append(aur)
        back.append(aur)
    if spec.glow:
        glow = wd / "_glow.png"
        _make_glow(glow, int(spec.glow_x * w), int(spec.glow_y * h), spec.glow_radius, spec.glow_color, w, h)
        tmps.append(glow); back.append(glow)

    if spec.haze:
        haze = wd / "_haze.png"; _make_haze(haze, horizon_y, spec.haze_strength, spec.glow_color, w, h); tmps.append(haze)
        front.append(haze)
    for i, layer in enumerate(spec.ridges):
        rp = wd / f"_ridge{i}.png"; _make_ridge(rp, layer, w, h); tmps.append(rp)
        front.append(rp)
    if spec.fog:
        fog = wd / "_fog.png"; _make_fog(fog, spec, w, h); tmps.append(fog)
        front.append(fog)
    if spec.cabin:
        cab = wd / "_cabin.png"; _make_cabin(cab, spec, w, h); tmps.append(cab)
        front.append(cab)
        win = wd / "_window.png"; _make_window_glow(win, spec, w, h); tmps.append(win)
        front.append(win)
        if spec.smoke:
            smk = wd / "_smoke.png"; _make_smoke(smk, spec, w, h); tmps.append(smk)
            front.append(smk)

    # --- Compose the temporal graph over the flattened plates. ---
    inputs: list[str] = []
    graph: list[str] = []
    idx = 0
    cur = None

    def add(path: Path, *, x_expr: str = "0", y_expr: str = "0",
            tw: int | None = None, th: int | None = None):
        """Overlay a (possibly moving) layer onto the running composite.
        tw/th are the layer's composite size in render pixels (defaults to a full
        frame; motion strips pass their 2x dimension)."""
        nonlocal idx, cur
        tw = rw if tw is None else tw
        th = rh if th is None else th
        inputs.extend(["-loop", "1", "-i", str(path)])
        src = f"{idx}:v"
        if scaled:
            node = f"p{idx}"
            graph.append(f"[{src}]scale={tw}:{th}:flags=bilinear[{node}]")
            src = node
        if cur is None:
            cur = src
        else:
            graph.append(f"[{cur}][{src}]overlay={x_expr}:{y_expr}[l{idx}]")
            cur = f"l{idx}"
        idx += 1

    if spec.clouds:
        # clouds drift between the deep sky and the hills, so bake the two plates
        # separately and sandwich the moving cloud strip in between.
        base_back = wd / "_base_back.png"; _bake(base_back, back, w, h, transparent=False)
        tmps.append(base_back); add(base_back)
        clouds = wd / "_clouds.png"; _make_clouds_strip(clouds, spec, w, h); tmps.append(clouds)
        cvx = spec.cloud_speed * rw / duration
        add(clouds, x_expr=f"'mod(t*{cvx:.5f},{rw})-{rw}'", tw=2 * rw, th=rh)
        if front:
            base_front = wd / "_base_front.png"; _bake(base_front, front, w, h, transparent=True)
            tmps.append(base_front); add(base_front)
    else:
        base = wd / "_base.png"; _bake(base, back + front, w, h, transparent=False)
        tmps.append(base); add(base)

    # particles: far layer, then a chunkier/faster near layer
    if spec.particles != "none":
        far = wd / "_pfar.png"
        _make_particle_strip(far, spec.particle_color, spec.particle_density, w, h)
        tmps.append(far)
        fall = rh / duration
        add(far, y_expr=f"'mod(t*{fall:.5f},{rh})-{rh}'", tw=rw, th=2 * rh)
        if spec.particles_near:
            near = wd / "_pnear.png"
            _make_particle_strip(near, spec.particle_color, max(1, spec.particle_density // 2), w, h, dot_scale=3)
            tmps.append(near)
            fall2 = 2 * rh / duration  # 2 spans/loop -> still seamless
            add(near, y_expr=f"'mod(t*{fall2:.5f},{rh})-{rh}'", tw=rw, th=2 * rh)

    tail = ""
    if scaled:
        tail += f"scale={out_w}:{out_h}:flags=lanczos,"   # upscale to delivery res first
    if spec.grain:
        tail += f"noise=alls={spec.grain}:allf=t,"        # then grain, crisp at full res
    if spec.vignette:
        tail += "vignette,"
    graph.append(f"[{cur}]{tail}format=yuv420p[v]")

    run([
        "ffmpeg", "-y", "-loglevel", "error",
        *inputs,
        "-filter_complex", ";".join(graph),
        "-map", "[v]", "-t", f"{duration:.3f}", "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out),
    ])
    for tmp in tmps:
        tmp.unlink(missing_ok=True)
    return out


def _make_ridge(out: Path, layer: RidgeLayer, w: int, h: int) -> None:
    r, g, b = _rgb(layer.color)
    base = layer.base * h
    terms = "+".join(f"{a}*sin(X/{p}+{ph})" for a, p, ph in layer.sines) or "0"
    line = f"{base:.1f} - ({terms})"
    if layer.jag_amp > 0:
        tri = f"2*abs(X/{layer.jag_period} - floor(X/{layer.jag_period}+0.5))"
        line += f" - {layer.jag_amp}*({tri})"
    _still(out, r, g, b, f"if(gt(Y, {line}), 255, 0)", w, h)


def overlay_logo(
    clip: Path,
    out: Path,
    logo: Path,
    *,
    corner: str = "tr",
    scale_w: int = 200,
    opacity: float = 0.85,
    margin: int = 48,
    fps: int = 30,
) -> Path:
    """Pin a semi-transparent logo/avatar in a corner of every frame.
    corner: tl|tr|bl|br."""
    pos = {
        "tl": f"{margin}:{margin}",
        "tr": f"W-w-{margin}:{margin}",
        "bl": f"{margin}:H-h-{margin}",
        "br": f"W-w-{margin}:H-h-{margin}",
    }[corner]
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(clip),
        "-i", str(logo),
        "-filter_complex",
        (f"[1:v]scale={scale_w}:-1,format=rgba,"
         f"colorchannelmixer=aa={opacity}[lg];"
         f"[0:v][lg]overlay={pos}:format=auto,format=yuv420p[v]"),
        "-map", "[v]", "-r", str(fps),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        str(out),
    ])
    return out


def make_seamless_loop(clip: Path, out: Path, *, fps: int = 30) -> Path:
    """Turn a clip into a perfectly seamless loop via boomerang (forward +
    reverse concat). The wrap returns to exactly the first frame. Output length
    is 2x input. (Scenes are already seamless, so this is for other callers.)"""
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(clip),
        "-filter_complex",
        "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        str(out),
    ])
    return out
