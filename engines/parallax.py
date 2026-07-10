"""EXPERIMENTAL: 2.5D depth-parallax camera moves from a single still.

Pipeline: Depth Anything V2 Small (ONNX, CPU) estimates per-pixel depth,
then each output frame back-warps the image with a depth-weighted offset
(cv2.remap) while a virtual camera drifts along an eased path. Near pixels
move more than far pixels — real parallax, not a flat zoom.

Status: experimental until it passes the visual benchmark
(engines/benchmarks/parallax_bench.py — Ticket E2). Known failure modes:
torn/haloed edges at strong depth discontinuities, rubber-sheeting on flat
art/diagrams/text, garbage depth on illustrations. Do NOT wire into a
channel before the benchmark verdict and a suitability gate exist.

License: the SMALL V2 checkpoint is Apache-2.0. The Base/Large checkpoints
are CC-BY-NC — never swap them in on a monetized channel.

Provisioning is explicit (`python -m engines install parallax`);
`available()` is offline and deterministic per the package contract.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from engines import MODELS_DIR, REGISTRY

MODEL = REGISTRY["parallax"]["model"]
MODEL_PATH = MODELS_DIR / MODEL["name"]
# Presence + size is the cheap deterministic check; full SHA-256 runs once
# and is stamped alongside the model so doctor stays fast afterward.
_STAMP = MODEL_PATH.with_suffix(".sha256.ok")


def _deps_ok() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


def model_verified() -> bool:
    """Model present, exact pinned size, and SHA-256 verified (cached stamp)."""
    if not MODEL_PATH.is_file() or MODEL_PATH.stat().st_size != MODEL["size_bytes"]:
        return False
    if _STAMP.is_file():
        return True
    digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    if digest != MODEL["sha256"]:
        return False
    _STAMP.write_text(digest + "\n")
    return True


def available() -> bool:
    import shutil
    return shutil.which("ffmpeg") is not None and _deps_ok() and model_verified()


# ---------------------------------------------------------------------------
# Depth estimation
# ---------------------------------------------------------------------------
_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort
        _SESSION = ort.InferenceSession(
            str(MODEL_PATH), providers=["CPUExecutionProvider"])
    return _SESSION


def _depth_map(bgr):
    """Relative depth for a BGR uint8 frame, normalized 0(far)..1(near),
    resized back to the frame's resolution."""
    import cv2
    import numpy as np

    n = MODEL["input_size"]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype("float32") / 255.0
    rgb = cv2.resize(rgb, (n, n), interpolation=cv2.INTER_CUBIC)
    mean = np.array([0.485, 0.456, 0.406], dtype="float32")
    std = np.array([0.229, 0.224, 0.225], dtype="float32")
    x = ((rgb - mean) / std).transpose(2, 0, 1)[None]
    sess = _session()
    depth = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
    lo, hi = float(depth.min()), float(depth.max())
    if hi - lo < 1e-6:
        return None  # flat depth — image unsuitable for parallax
    depth = (depth - lo) / (hi - lo)
    h, w = bgr.shape[:2]
    depth = cv2.resize(depth, (w, h), interpolation=cv2.INTER_LINEAR)
    # Soften discontinuities: hard depth edges are what tear into halos.
    return cv2.GaussianBlur(depth, (0, 0), sigmaX=max(2.0, w / 200.0))


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def _suitable(stage) -> tuple[bool, str]:
    """Suitability gate (Ticket E2): depth models hallucinate confident
    relief on flat art and text, so intrinsic depth stats can't gate —
    we screen the INPUT instead. Thresholds calibrated on the v1 benchmark
    set (engines/benchmarks/parallax_bench.py); recalibrate there when the
    bench grows.

    - flat art / posterized graphics: vector fills are EXACTLY flat while
      photos (even B&W) always carry grain — fraction of 8x8 blocks with
      near-zero std separates them (mascot 0.68 vs photos <=0.43).
    - text documents: uniquely high color-uniformity AND stroke density
      (0.83/0.53 on the bench doc; nothing else exceeds both).
    """
    import cv2
    import numpy as np

    gray = cv2.cvtColor(stage, cv2.COLOR_BGR2GRAY).astype("float32")
    h, w = gray.shape
    g = gray[:h // 8 * 8, :w // 8 * 8]
    blocks = g.reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 64)
    flat = float((blocks.std(axis=1) < 1.5).mean())
    if flat > 0.55:
        return False, f"flat-art input (flat-block fraction {flat:.2f})"
    small = cv2.resize(stage, (128, 128))
    _, counts = np.unique((small >> 4).reshape(-1, 3), axis=0, return_counts=True)
    top8 = float(np.sort(counts)[-8:].sum() / counts.sum())
    lap = np.abs(cv2.Laplacian(
        cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype("float32"), cv2.CV_32F))
    strokes = float((lap > 40).mean())
    if top8 > 0.70 and strokes > 0.40:
        return False, f"text-heavy input (top8 {top8:.2f}, strokes {strokes:.2f})"
    return True, ""


def _fit_cover(img, w, h):
    """Cover-crop `img` to exactly (w, h)."""
    import cv2
    ih, iw = img.shape[:2]
    scale = max(w / iw, h / ih)
    rw, rh = int(round(iw * scale)), int(round(ih * scale))
    img = cv2.resize(img, (rw, rh), interpolation=cv2.INTER_AREA
                     if scale < 1 else cv2.INTER_CUBIC)
    x0, y0 = (rw - w) // 2, (rh - h) // 2
    return img[y0:y0 + h, x0:x0 + w]


def parallax(
    image: str | Path,
    out: str | Path,
    duration: float,
    *,
    size: tuple[int, int] = (1080, 1920),
    fps: int = 30,
    strength: float = 18.0,   # max pixel shift for the nearest plane
    drift: str = "orbit",     # "orbit" | "lateral" | "vertical"
    zoom: float = 1.06,       # slight push-in layered on top
    crf: int = 20,
    content: str | None = None,  # caller hint: "photo" skips the input
                                 # gate; "art"/"text"/"chart"/"diagram"
                                 # refuses outright (caller falls back)
) -> Path:
    """Render a depth-parallax clip. Raises on failure; use maybe_parallax
    for the best-effort contract."""
    import cv2
    import numpy as np

    w, h = int(size[0]), int(size[1])
    src = cv2.imread(str(image), cv2.IMREAD_COLOR)
    if src is None:
        raise ValueError(f"unreadable image: {image}")
    # Render on an oversized stage so warp + zoom never expose borders.
    margin = 1.0 + 2.2 * strength / min(w, h)
    sw, sh = int(w * margin) // 2 * 2, int(h * margin) // 2 * 2
    stage = _fit_cover(src, sw, sh)
    if content in ("art", "text", "chart", "diagram"):
        raise ValueError(f"content={content!r} — parallax not suitable")
    if content != "photo":
        ok, why = _suitable(stage)
        if not ok:
            raise ValueError(f"suitability gate: {why}")
    depth = _depth_map(stage)
    if depth is None:
        raise ValueError("flat depth map — image unsuitable for parallax")
    # Center depth around 0 so the mid-plane stays still and the composition
    # doesn't slide: near pixels (+) move with the camera, far (-) against.
    depth = depth - float(np.median(depth))

    frames = max(2, int(round(duration * fps)))
    ys, xs = np.mgrid[0:sh, 0:sw].astype("float32")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
            "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", str(crf), "-pix_fmt", "yuv420p", str(out),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        for i in range(frames):
            t = i / max(1, frames - 1)
            ease = 0.5 - 0.5 * np.cos(np.pi * 2 * t)  # smooth out-and-back
            if drift == "orbit":
                ox = strength * np.sin(2 * np.pi * t)
                oy = 0.35 * strength * (0.5 - 0.5 * np.cos(2 * np.pi * t))
            elif drift == "vertical":
                ox, oy = 0.0, strength * (2 * ease - 1)
            else:  # lateral
                ox, oy = strength * (2 * ease - 1), 0.0
            # np trig returns float64; cv2.remap demands float32 maps.
            map_x = xs + depth * np.float32(ox)
            map_y = ys + depth * np.float32(oy)
            frame = cv2.remap(stage, map_x, map_y, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT)
            z = 1.0 + (zoom - 1.0) * t
            cw, ch = int(w / z) // 2 * 2, int(h / z) // 2 * 2
            x0, y0 = (sw - cw) // 2, (sh - ch) // 2
            frame = cv2.resize(frame[y0:y0 + ch, x0:x0 + cw], (w, h),
                               interpolation=cv2.INTER_LINEAR)
            enc.stdin.write(frame.tobytes())
    finally:
        enc.stdin.close()
        enc.wait()
    if enc.returncode != 0:
        raise RuntimeError(f"ffmpeg encode failed (rc={enc.returncode})")
    return out


def maybe_parallax(image, out, duration, **kwargs) -> Path | None:
    """Best-effort contract: clip path on success, None on ANY failure.

    Refuses to run unless provisioned — unless ENGINES_AUTO_PROVISION=1,
    in which case it attempts a one-time install (CI convenience only).
    """
    try:
        if not available():
            if os.environ.get("ENGINES_AUTO_PROVISION") == "1":
                from engines import provision
                if not provision.install("parallax"):
                    return None
            else:
                print("[engines.parallax] not provisioned — run: "
                      "python -m engines install parallax")
                return None
        return parallax(image, out, duration, **kwargs)
    except Exception as e:  # noqa: BLE001 — contract: never raise into a caller
        print(f"[engines.parallax] failed ({e}) — caller should fall back")
        return None
