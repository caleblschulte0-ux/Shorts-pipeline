"""tile fNNNN.png frames from a dir into a contact sheet: sheet.py DIR OUT COLS [every]"""
import sys, os, glob
from PIL import Image, ImageDraw
d, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3]); every = int(sys.argv[4]) if len(sys.argv) > 4 else 1
fs = sorted(glob.glob(os.path.join(d, "f*.png")))[::every]
ims = [Image.open(f) for f in fs]; w, h = ims[0].size; sc = min(1.0, 360 / w); w2, h2 = int(w * sc), int(h * sc)
rows = (len(ims) + cols - 1) // cols; sheet = Image.new("RGB", (cols * w2, rows * h2), (20, 20, 20)); dr = ImageDraw.Draw(sheet)
for i, (f, im) in enumerate(zip(fs, ims)):
    x, y = (i % cols) * w2, (i // cols) * h2; sheet.paste(im.resize((w2, h2), Image.LANCZOS), (x, y))
    n = int(os.path.basename(f)[1:5]); dr.text((x + 6, y + 6), f"f{n} t={(n - 1) / 24:.2f}", fill=(255, 220, 0))
sheet.save(out, quality=88)
