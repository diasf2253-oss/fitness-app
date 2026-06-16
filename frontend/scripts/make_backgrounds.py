"""
Generate the app's atmospheric background images — no AI service, no key.

Renders a calm, dusk-misty layered-ridgeline valley in the "Quiet Tracker"
palette (deep green-charcoal, sage, bone). Dark-biased on purpose: opaque
cards float over it and bone text must stay readable where it shows through.

Layered ridgelines (sum-of-sines curves, hazier + blurrier the farther back)
give natural atmospheric perspective without a photograph. Pure Pillow, fast
(no per-pixel Python loops — gradients are horizontal lines, ridges are
polygons).

Usage:
    pip install pillow
    python scripts/make_backgrounds.py
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PUBLIC = Path(__file__).resolve().parent.parent / "public"

W, H = 1920, 1280


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sky(width, height, top, glow, glow_at=0.42):
    """Vertical gradient: dark top → a soft fog 'glow' band → dark base."""
    base = (21, 27, 24)  # #151b18
    img = Image.new("RGB", (width, height), base)
    d = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        if t < glow_at:
            c = lerp(top, glow, t / glow_at)
        else:
            c = lerp(glow, base, (t - glow_at) / (1 - glow_at))
        d.line([(0, y), (width, y)], fill=c)
    return img


def ridge_polygon(base_y, amp, seed):
    """A soft organic ridgeline filled down to the bottom edge."""
    rnd = random.Random(seed)
    comps = [
        (amp, rnd.uniform(0.8, 1.4), rnd.uniform(0, 6.28)),
        (amp * 0.45, rnd.uniform(2.0, 3.0), rnd.uniform(0, 6.28)),
        (amp * 0.22, rnd.uniform(4.0, 6.0), rnd.uniform(0, 6.28)),
    ]
    pts = []
    for x in range(0, W + 1, 3):
        y = base_y
        for a, f, p in comps:
            y += a * math.sin((x / W) * f * math.pi * 2 + p)
        pts.append((x, y))
    pts += [(W, H), (0, H)]
    return pts


def ridge_layer(color, alpha, base_y, amp, blur, seed):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(ridge_polygon(base_y, amp, seed), fill=color + (alpha,))
    if blur:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return layer


def valley():
    # Soft sage fog glow about 40% down, fading to charcoal above and below.
    img = sky(W, H, top=(26, 34, 30), glow=(58, 74, 64)).convert("RGBA")

    # Far → near: each ridge darker, lower, sharper (atmospheric perspective).
    layers = [
        ((74, 90, 76),  90, 0.46, 34, 7, 11),
        ((58, 73, 62), 140, 0.57, 40, 4, 23),
        ((42, 54, 46), 185, 0.69, 46, 2, 37),
        ((28, 36, 31), 235, 0.82, 52, 1, 51),
    ]
    for color, alpha, by, amp, blur, seed in layers:
        img = Image.alpha_composite(img, ridge_layer(color, alpha, by * H, amp, blur, seed))

    # Bottom scrim so the lower half blends into the solid page background.
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    start = int(H * 0.55)
    for y in range(start, H):
        a = round(235 * (y - start) / (H - start))
        sd.line([(0, y), (W, y)], fill=(21, 27, 24, a))
    img = Image.alpha_composite(img, scrim)

    return img.convert("RGB")


def main():
    PUBLIC.mkdir(exist_ok=True)
    out = PUBLIC / "bg-valley.jpg"
    valley().save(out, "JPEG", quality=82, optimize=True, progressive=True)
    kb = out.stat().st_size / 1024
    print(f"Wrote {out} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
