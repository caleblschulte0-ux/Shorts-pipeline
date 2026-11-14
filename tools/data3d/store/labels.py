"""Printed graphics for the set, generated with PIL by the SYSTEM python (bpy's venv has no PIL): product labels
(front + wrap), the kiosk and register UIs, a repeating price-tag strip, a repeating barcode-and-fine-print
sheet. Deterministic from a seed so a re-run rebuilds the same pictures.
    python3 -I labels.py OUTDIR            writes OUTDIR/manifest.txt and the PNGs
scene_kit.labels() runs this once and loads the images by name."""
import sys, os, random
from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/freefont"]
def font(name, size):
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

BRANDS = ["OATIES", "VITA", "PURE", "CRISP", "NOVA", "ALPINE", "SUNNY", "GOLD", "FRESH", "DAILY", "ORIGIN", "KETTLE", "MAPLE",
          "HARVEST", "BLUE SKY", "ROOTS", "SILK", "NORTH", "PRIMA", "ZEST", "ORCHARD", "CLASSIC"]
SUBS = ["whole grain", "family size", "no added sugar", "since 1952", "original", "extra crunchy", "organic", "100% natural",
        "lightly salted", "farm fresh", "real fruit", "new recipe", "value pack", "gluten free", "rich & creamy", "made with oats"]
PRODUCTS = ["#B8655A", "#6E8FB5", "#C9A94E", "#7E9C6A", "#8A6FA8", "#D08A4E", "#5F8F8A", "#B5B0A6", "#C46A7E", "#5E6E8F",
            "#2F5FB8", "#C6392B", "#E8C94E", "#2B2F36", "#F2F2F0", "#3F8F5A"]

def hexrgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)
def ink_for(c): return (28, 30, 36) if sum(c) / 3 > 140 else (250, 248, 242)

def barcode(dr, x, y, w, h, r):
    cx = x
    while cx < x + w:
        bw = r.choice((2, 2, 3, 4, 5)); dr.rectangle((cx, y, cx + bw, y + h), fill=(20, 20, 20)); cx += bw + r.choice((2, 3, 4))

def fine_print(dr, x, y, w, n, r, col=(60, 60, 60)):
    for k in range(n):
        ww = int(w * r.uniform(0.5, 1.0)); dr.rectangle((x, y + k * 7, x + ww, y + k * 7 + 2), fill=col)

def label(i, r, out):
    """a 512x512 front: field colour, a wide band, the brand in a display face, a sub line, a product picture as a
    simple shape, a bar code block, fine print and a weight. Also a 1024x512 wrap for cans: the same at 2:1."""
    bg = hexrgb(PRODUCTS[i % len(PRODUCTS)]); band = hexrgb(PRODUCTS[(i * 7 + 3) % len(PRODUCTS)])
    if abs(sum(bg) - sum(band)) < 120: band = shade(bg, 0.55 if sum(bg) > 300 else 1.6)
    ink = ink_for(bg); ink_b = ink_for(band)
    brand = BRANDS[i % len(BRANDS)]; sub = SUBS[(i * 5) % len(SUBS)]
    layout = i % 4
    for W, H, tag in ((512, 512, "front"), (1024, 512, "wrap")):
        im = Image.new("RGB", (W, H), bg); dr = ImageDraw.Draw(im)
        # a soft texture: faint diagonal grain so the field is not one flat value
        for k in range(0, W + H, 6):
            dr.line((k, 0, 0, k), fill=shade(bg, 0.985), width=1)
        if layout == 0:   # band across the top third
            dr.rectangle((0, int(H * 0.16), W, int(H * 0.44)), fill=band)
            ty = int(H * 0.3)
        elif layout == 1:   # a diagonal swoosh
            dr.polygon([(0, int(H * 0.55)), (W, int(H * 0.38)), (W, int(H * 0.62)), (0, int(H * 0.8))], fill=band)
            ty = int(H * 0.22)
        elif layout == 2:   # a rounded badge
            dr.rounded_rectangle((int(W * 0.1), int(H * 0.14), int(W * 0.9), int(H * 0.5)), radius=40, fill=band)
            ty = int(H * 0.32)
        else:   # vertical stripe at the left
            dr.rectangle((0, 0, int(W * 0.12), H), fill=band)
            ty = int(H * 0.2)
        f = font("Inter-Bold.otf", int(H * 0.14) if len(brand) < 7 else int(H * 0.1))
        tw = dr.textlength(brand, font=f)
        tc = ink_b if layout in (0, 2) else ink
        dr.text(((W - tw) / 2, ty - f.size * 0.6), brand, font=f, fill=tc)
        f2 = font("Inter-Medium.otf", int(H * 0.05)); tw2 = dr.textlength(sub, font=f2)
        dr.text(((W - tw2) / 2, ty + f.size * 0.55), sub, font=f2, fill=tc if layout in (0, 2) else ink)
        # product picture: a simple emblem (circle / bowl / leaf) in the band's colour, lower middle
        cx, cy, rr = W // 2, int(H * 0.68), int(H * 0.1)
        emb = shade(band, 1.15) if sum(band) < 400 else shade(band, 0.85)
        kind = (i // 4) % 3
        if kind == 0: dr.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=emb); dr.ellipse((cx - rr * 0.55, cy - rr * 0.55, cx + rr * 0.55, cy + rr * 0.55), fill=shade(emb, 0.8))
        elif kind == 1: dr.chord((cx - rr * 1.3, cy - rr, cx + rr * 1.3, cy + rr), 0, 180, fill=emb); dr.rectangle((cx - rr * 1.3, cy - 4, cx + rr * 1.3, cy + 2), fill=shade(emb, 0.8))
        else: dr.polygon([(cx, cy - rr), (cx + rr * 0.9, cy), (cx, cy + rr), (cx - rr * 0.9, cy)], fill=emb)
        # weight, barcode, fine print
        f3 = font("Inter-SemiBold.otf", int(H * 0.045)); wt = r.choice(("500 g", "340 g", "1 L", "750 ml", "12 oz", "16 oz", "2 lb", "6 pack"))
        dr.text((W - dr.textlength(wt, font=f3) - int(W * 0.05), H - int(H * 0.1)), wt, font=f3, fill=ink)
        barcode(dr, int(W * 0.05), H - int(H * 0.14), int(W * 0.18), int(H * 0.08), r)
        fine_print(dr, int(W * 0.05), H - int(H * 0.05), int(W * 0.3), 1, r, col=shade(ink, 0.7) if sum(ink) > 300 else (90, 90, 90))
        if tag == "wrap":   # the wrap carries a nutrition panel on the back half
            dr.rectangle((int(W * 0.62), int(H * 0.1), int(W * 0.95), int(H * 0.9)), fill=(246, 244, 238)); dr2 = ImageDraw.Draw(im)
            f4 = font("Inter-Bold.otf", int(H * 0.05)); dr2.text((int(W * 0.64), int(H * 0.12)), "Nutrition Facts", font=f4, fill=(30, 30, 30))
            fine_print(dr2, int(W * 0.64), int(H * 0.22), int(W * 0.29), 28, r, col=(70, 70, 70))
            barcode(dr2, int(W * 0.66), int(H * 0.76), int(W * 0.24), int(H * 0.1), r)
        im.save(os.path.join(out, f"label{i:02d}_{tag}.png"))

def kiosk_ui(out):
    W, H = 600, 520; im = Image.new("RGB", (W, H), (236, 242, 250)); dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, W, 70), fill=(31, 59, 99)); f = font("Inter-SemiBold.otf", 30); dr.text((24, 18), "Self Checkout", font=f, fill=(255, 255, 255))
    f2 = font("Inter-Medium.otf", 22); dr.text((W - 150, 24), "Lane 3", font=f2, fill=(200, 215, 235))
    f3 = font("Inter-Bold.otf", 44); t = "Welcome"; dr.text(((W - dr.textlength(t, font=f3)) / 2, 120), t, font=f3, fill=(31, 59, 99))
    f4 = font("Inter-Regular.otf", 24); t = "Scan your first item to begin"; dr.text(((W - dr.textlength(t, font=f4)) / 2, 185), t, font=f4, fill=(80, 90, 110))
    dr.rounded_rectangle((110, 260, W - 110, 340), radius=18, fill=(47, 127, 224)); f5 = font("Inter-SemiBold.otf", 30); t = "START"
    dr.text(((W - dr.textlength(t, font=f5)) / 2, 280), t, font=f5, fill=(255, 255, 255))
    for k, (x, lab) in enumerate(((60, "Scan"), (230, "Pay"), (400, "Help"))):
        dr.rounded_rectangle((x, 380, x + 140, 470), radius=14, fill=(255, 255, 255), outline=(190, 200, 215), width=2)
        dr.text((x + 70 - dr.textlength(lab, font=f2) / 2, 412), lab, font=f2, fill=(60, 70, 90))
    im.save(os.path.join(out, "kiosk_ui.png"))

def register_ui(out):
    W, H = 340, 240; im = Image.new("RGB", (W, H), (248, 249, 252)); dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, W, 34), fill=(43, 47, 54)); f = font("Inter-SemiBold.otf", 18); dr.text((12, 8), "POS  •  Lane", font=f, fill=(230, 232, 236))
    f2 = font("DejaVuSansMono.ttf", 15); r = random.Random(3)
    for k in range(7):
        item = r.choice(("MILK 2% 1L", "OAT CRUNCH", "BANANAS 1.2kg", "ORCHARD JUICE", "KETTLE CHIPS", "NORTH BREAD", "ZEST SODA 6PK"))
        price = f"{r.uniform(1.2, 9.9):5.2f}"; dr.text((14, 46 + k * 22), item, font=f2, fill=(40, 40, 44)); dr.text((W - 70, 46 + k * 22), price, font=f2, fill=(40, 40, 44))
    dr.rectangle((0, 204, W, H), fill=(47, 127, 224)); f3 = font("Inter-Bold.otf", 20); dr.text((14, 210), "TOTAL", font=f3, fill=(255, 255, 255)); dr.text((W - 90, 210), "38.46", font=f3, fill=(255, 255, 255))
    im.save(os.path.join(out, "register_ui.png"))

def price_strip(out, r):
    """a repeating strip of shelf-edge price tags: 2048x64, 8 tags"""
    W, H = 2048, 64; im = Image.new("RGB", (W, H), (236, 234, 228)); dr = ImageDraw.Draw(im); f = font("Inter-Bold.otf", 26); f2 = font("Inter-Regular.otf", 13)
    for k in range(8):
        x0 = k * 256; dr.rectangle((x0 + 6, 6, x0 + 250, H - 6), fill=(255, 255, 255), outline=(200, 198, 192))
        if k % 3 == 0: dr.rectangle((x0 + 6, 6, x0 + 250, 22), fill=(230, 60, 40)); dr.text((x0 + 12, 7), "SALE", font=f2, fill=(255, 255, 255))
        price = f"${r.uniform(0.99, 12.49):.2f}"; dr.text((x0 + 150, 22), price, font=f, fill=(30, 30, 30))
        fine_print(dr, x0 + 14, 30, 120, 3, r, col=(110, 110, 110)); barcode(dr, x0 + 14, 50, 90, 8, r)
    im.save(os.path.join(out, "price_strip.png"))

def main(out):
    os.makedirs(out, exist_ok=True); r = random.Random(11)
    n = 24
    for i in range(n): label(i, r, out)
    kiosk_ui(out); register_ui(out); price_strip(out, r)
    with open(os.path.join(out, "manifest.txt"), "w") as f: f.write(f"labels {n}\n")

if __name__ == "__main__":
    main(sys.argv[1])
