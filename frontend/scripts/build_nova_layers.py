"""Cut the designer's Nova portrait into animation layers, without repainting her.

Input : png-girl1.png at the repo root (the designer's file, transparent background).
Output: frontend/public/nova/
  body.webp           shoulders, necklace and top, fading out up the neck
  head.webp           everything above the neck, untouched except the spot hidden behind each iris
  eyes-iris.webp      both irises as full discs           -> slide to follow the cursor
  eyes-frame.webp     the lids and lashes around each eye -> keeps irises inside the eye
  eyes-lids.webp      skin-coloured lids over each eye    -> scaled in to blink
All layers are full-canvas and lossless; stacked at rest they equal the original (checked on every run).

Run from the repo root:  python3 frontend/scripts/build_nova_layers.py
The numbers it prints are the percentages used in components/character/NovaPortrait.tsx and globals.css.
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "png-girl1.png"
OUT = ROOT / "frontend" / "public" / "nova"

OUT_H = 1200

# --- all coordinates below are in the source PNG's pixels ---
# visible eye openings (sclera + iris), traced by hand
LEFT_EYE = [(583, 778), (595, 772), (610, 769), (630, 767), (655, 767), (675, 770), (690, 778), (702, 790), (708, 798),
            (690, 800), (665, 800), (640, 800), (615, 797), (598, 790), (588, 784)]
RIGHT_EYE = [(832, 800), (845, 786), (857, 774), (870, 767), (890, 764), (910, 764), (930, 766), (952, 771), (968, 777),
             (962, 786), (950, 792), (930, 798), (910, 801), (885, 802), (860, 802)]
IRISES = [((639, 783), 24), ((900, 784), 33)]
# neck: head is opaque above NECK_HEAD_FULL and fades out by NECK_HEAD_END; the body fills in exactly underneath
NECK_HEAD_FULL, NECK_HEAD_END = 1275, 1320
HEAD_PIVOT = (782, 1290)

LASH = (28, 20, 18)


def poly_mask(size, polys, grow=0, feather=1.2):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for p in polys:
        d.polygon(p, fill=255)
    if grow:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    return m.filter(ImageFilter.GaussianBlur(feather)) if feather else m


def vertical_ramp(size, y0, y1, rising=True):
    """Alpha ramp: 0 above y0 -> 255 below y1 (rising) or the reverse."""
    w, h = size
    col = Image.new("L", (1, h))
    for y in range(h):
        t = 0 if y <= y0 else 1 if y >= y1 else (y - y0) / (y1 - y0)
        col.putpixel((0, y), round(255 * (t if rising else 1 - t)))
    return col.resize((w, h))


def median_colour(img, mask, keep=lambda r, g, b: True):
    px = [img.getpixel((x, y))[:3] for y in range(img.height) for x in range(img.width)
          if mask.getpixel((x, y)) > 200 and keep(*img.getpixel((x, y))[:3])]
    if not px:
        raise SystemExit("no pixels sampled — check the eye polygons")
    return tuple(sorted(c[i] for c in px)[len(px) // 2] for i in range(3))


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def disc_mask(size, grow=0, feather=1.0):
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    for (cx, cy), r in IRISES:
        d.ellipse([cx - r - grow, cy - r - grow, cx + r + grow, cy + r + grow], fill=255)
    return m.filter(ImageFilter.GaussianBlur(feather)) if feather else m


def fill_behind_irises(src, opening):
    """Repaint ONLY the spot the iris covers, row by row, blending the painted eye-white found
    either side of it. Everything else in the head stays the designer's pixels. This patch is
    only ever seen when the iris layer has slid off it."""
    hard_open = opening.point(lambda v: 255 if v > 127 else 0)
    target = ImageChops.multiply(disc_mask(src.size, grow=2, feather=0), hard_open)
    fill = src.copy()
    px, tp, op = fill.load(), target.load(), hard_open.load()

    def side_colour(x, y, step):
        cols = []
        while 0 < x < src.width - 1 and len(cols) < 3:
            x += step
            if op[x, y] == 0:
                break
            if tp[x, y] == 0:
                cols.append(src.getpixel((x, y))[:3])
        return tuple(sum(c[i] for c in cols) // len(cols) for i in range(3)) if cols else None

    last = {}
    for (cx, cy), r in IRISES:
        for y in range(cy - r - 3, cy + r + 4):
            xs = [x for x in range(cx - r - 3, cx + r + 4) if tp[x, y]]
            if not xs:
                continue
            xa, xb = xs[0], xs[-1]
            left, right = side_colour(xa, y, -1), side_colour(xb, y, 1)
            left = left or right or last.get((cx, "l"))
            right = right or left or last.get((cx, "r"))
            if left is None:
                continue
            last[(cx, "l")], last[(cx, "r")] = left, right
            for x in xs:
                t = 0 if xb == xa else (x - xa) / (xb - xa)
                px[x, y] = (*lerp(left, right, t), 255)
    soft = target.filter(ImageFilter.GaussianBlur(1.2))
    return fill.filter(ImageFilter.GaussianBlur(1.6)), soft


def build_head(src, opening):
    fill, mask = fill_behind_irises(src, opening)
    head = src.copy()
    head.paste(fill, (0, 0), mask)
    alpha = ImageChops.multiply(head.getchannel("A"), vertical_ramp(src.size, NECK_HEAD_FULL, NECK_HEAD_END, rising=False))
    head.putalpha(alpha)
    return head


def build_irises(src, opening):
    # a few px wider than the iris so it fully covers the repainted spot underneath
    discs = disc_mask(src.size, grow=5)
    rim = median_colour(src, ImageChops.multiply(discs, opening), lambda r, g, b: (r + g + b) / 3 < 110)
    # inside the opening: the painted iris; under the lids: its darker rim colour, so a moved iris never shows a cut edge
    iris = Image.new("RGBA", src.size, (*lerp(rim, LASH, 0.35), 255))
    # painted pixels a little past the soft edge, so lid frame + iris blend back to the exact original
    iris.paste(src, (0, 0), opening.point(lambda v: 255 if v else 0).filter(ImageFilter.MaxFilter(5)))
    # never wider than the lid frame, so no part of an iris can show outside the eye
    iris.putalpha(ImageChops.multiply(discs, poly_mask(src.size, [LEFT_EYE, RIGHT_EYE], grow=FRAME_GROW - 4, feather=1.5)))
    return iris


FRAME_GROW = 18


def frame_ring(size):
    """Area the lid frame covers: each opening grown by FRAME_GROW px, soft-edged so resizing adds no halo."""
    return poly_mask(size, [LEFT_EYE, RIGHT_EYE], grow=FRAME_GROW, feather=2.5)


def build_frame(src, opening):
    ring = frame_ring(src.size)
    frame = src.copy()
    frame.putalpha(ImageChops.subtract(ring, opening))
    return frame


def build_lids(src):
    above = [[(x, y - 30) for x, y in poly] for poly in (LEFT_EYE, RIGHT_EYE)]
    band = ImageChops.subtract(poly_mask(src.size, above, grow=2, feather=0), poly_mask(src.size, [LEFT_EYE, RIGHT_EYE], grow=12, feather=0))
    skin = median_colour(src, band, lambda r, g, b: r > g > b and (r + g + b) / 3 > 70)
    lids = Image.new("RGBA", src.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lids)
    for poly in (LEFT_EYE, RIGHT_EYE):
        top, bottom = min(p[1] for p in poly) - 3, max(p[1] for p in poly) + 3
        for y in range(top, bottom + 1):
            t = (y - top) / (bottom - top)
            d.line([(0, y), (src.width, y)], fill=(*lerp(skin, LASH, max(0, (t - 0.62) / 0.38)), 255))
    lids.putalpha(poly_mask(src.size, [LEFT_EYE, RIGHT_EYE], grow=3, feather=1.2))
    return lids


def build_body(src, head):
    """Body alpha chosen so head-over-body equals the original exactly at rest:
    A_body = (A - A_head) / (1 - A_head). Only the neck fade rows need the formula."""
    body = src.copy()
    a, ah = src.getchannel("A").load(), head.getchannel("A").load()
    out = Image.new("L", src.size, 0)
    o = out.load()
    for y in range(NECK_HEAD_FULL, src.height):
        for x in range(src.width):
            if y >= NECK_HEAD_END:
                o[x, y] = a[x, y]
            elif ah[x, y] < 255:
                o[x, y] = round(255 * (a[x, y] - ah[x, y]) / (255 - ah[x, y]))
    body.putalpha(out)
    return body


def check_rest_matches_original(src, bbox, scale):
    """Stack the layers as the page does at rest and compare with the original."""
    w, h = round((bbox[2] - bbox[0]) * scale), OUT_H
    ref = src.crop(bbox).resize((w, h), Image.LANCZOS)
    bg = (235, 95, 40, 255)
    a = Image.new("RGBA", (w, h), bg)
    a.alpha_composite(ref)
    b = Image.new("RGBA", (w, h), bg)
    for name in ("body", "head", "eyes-iris", "eyes-frame"):
        b.alpha_composite(Image.open(OUT / f"{name}.webp").convert("RGBA"))
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    hist = [sum(c) for c in zip(*[diff.getchannel(i).histogram() for i in range(3)])]
    print(f"rest vs original: {sum(hist[9:])} channel values differ by >8/255 (max {max(i for i, v in enumerate(hist) if v)})")


def save(img, crop_box, name, scale):
    out = img.crop(crop_box)
    out = out.resize((round(out.width * scale), round(out.height * scale)), Image.LANCZOS)
    out.save(OUT / name, lossless=True, quality=100, method=6, exact=True)
    print(f"  {name:20s} {out.width}x{out.height}  {(OUT / name).stat().st_size // 1024} KB")


def main():
    src = Image.open(SRC).convert("RGBA")
    bbox = src.getchannel("A").getbbox()
    bx, by, bx2, by2 = bbox
    bw, bh = bx2 - bx, by2 - by
    scale = OUT_H / bh
    OUT.mkdir(parents=True, exist_ok=True)

    opening = poly_mask(src.size, [LEFT_EYE, RIGHT_EYE], feather=0).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    head = build_head(src, opening)
    body = build_body(src, head)

    # every layer is the full canvas, so nothing has to be positioned or can drift
    save(body, bbox, "body.webp", scale)
    save(head, bbox, "head.webp", scale)
    save(build_irises(src, opening), bbox, "eyes-iris.webp", scale)
    save(build_frame(src, opening), bbox, "eyes-frame.webp", scale)
    save(build_lids(src), bbox, "eyes-lids.webp", scale)
    check_rest_matches_original(src, bbox, scale)

    pct = lambda v, o, size: round((v - o) / size * 100, 3)
    eye_top = min(min(p[1] for p in LEFT_EYE), min(p[1] for p in RIGHT_EYE)) - 3
    print(f"canvas {round(bw * scale)}x{OUT_H}")
    print(f"lid origin y {pct(eye_top, by, bh)}%")
    print(f"head pivot  {pct(HEAD_PIVOT[0], bx, bw)}%  {pct(HEAD_PIVOT[1], by, bh)}%")


if __name__ == "__main__":
    main()
