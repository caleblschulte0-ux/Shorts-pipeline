"""SCOUT a real place before a shot is staged: what a photographed environment shows the director's lens at each turn.

    python scout.py ENV [out.jpg] [pitch_deg]      eight views (turn 0, 45 ... 315), each the 9:16 frame store/director.py
                                                   gets from s.place(ENV, turn=...) on its 24 mm lens

No Blender: the same mapping as the world shader, in numpy, a second a sheet. Pick the turn whose floor is OPEN where
Data and the props will stand (a photograph's own furniture cannot stand in front of him), then stage."""
import math, sys
from pathlib import Path
import numpy as np
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
ENVS = Path(__file__).resolve().parents[3] / "cache" / "polyhaven" / "env"
TANV, TANH = 0.75, 0.75 * 9 / 16


def view(img, turn, pitch=-4.0, w=270, h=480):
    H, W = img.shape[:2]
    xs = (np.arange(w) + 0.5) / w * 2 - 1; ys = 1 - (np.arange(h) + 0.5) / h * 2
    X, Y = np.meshgrid(xs * TANH, ys * TANV)
    p = math.radians(pitch); fw = np.array([0, math.cos(p), math.sin(p)]); rt = np.array([1.0, 0, 0]); up = np.cross(rt, fw)
    d = fw[None, None] + X[..., None] * rt + Y[..., None] * up
    a = math.radians(turn); c, s = math.cos(a), math.sin(a)          # the Mapping node turns the lookup vector about Z
    dx = c * d[..., 0] - s * d[..., 1]; dy = s * d[..., 0] + c * d[..., 1]; dz = d[..., 2]
    u = np.arctan2(-dy, dx) / (2 * math.pi) + 0.5; v = np.arctan2(dz, np.hypot(dx, dy)) / math.pi + 0.5
    return img[((1 - v) * (H - 1)).astype(int).clip(0, H - 1), (u * (W - 1)).astype(int) % W]


def main(argv):
    env = argv[1]; out = argv[2] if len(argv) > 2 else f"/tmp/scout_{env}.jpg"; pitch = float(argv[3]) if len(argv) > 3 else -4.0
    im = Image.open(ENVS / f"{env}.jpg"); im.draft("RGB", (4096, 2048)); img = np.asarray(im.convert("RGB"))
    turns = [float(t) for t in argv[4:]] or [i * 45.0 for i in range(8)]
    sheet = np.concatenate([view(img, t, pitch) for t in turns], axis=1)
    Image.fromarray(sheet).save(out, quality=85); print(out, "turns", turns)


if __name__ == "__main__":
    main(sys.argv)
