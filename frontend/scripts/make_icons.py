"""
Generate the PWA icon set into frontend/public/.

The mark is a cairn — three stacked stones in the app's palette (moss,
sage, bone on deep green-charcoal). A cairn marks the trail: quiet
progress, one day at a time.

Usage (Pillow is only needed for this script, not the app):
    pip install pillow
    python scripts/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent.parent / "public"

BG = (21, 27, 24, 255)        # --color-bg  #151b18
MOSS = (127, 155, 120, 255)   # #7f9b78
SAGE = (168, 191, 161, 255)   # #a8bfa1
BONE = (236, 233, 224, 255)   # #ece9e0


def draw_cairn(size: int, *, full_bleed: bool, scale: float = 1.0) -> Image.Image:
    """
    Render the cairn mark at `size`×`size`.
    full_bleed=True paints the background to the edges (maskable / iOS);
    otherwise the background is a rounded square on transparency.
    `scale` shrinks the stones around the center (maskable icons need an
    ~80% safe zone).
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if full_bleed:
        d.rectangle([0, 0, size, size], fill=BG)
    else:
        radius = int(size * 0.21)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)

    def stone(cx, cy, rx, ry, color):
        f = size / 512
        cx = 256 + (cx - 256) * scale
        cy = 256 + (cy - 256) * scale
        rx *= scale
        ry *= scale
        d.ellipse([(cx - rx) * f, (cy - ry) * f, (cx + rx) * f, (cy + ry) * f], fill=color)

    # Stone geometry on a 512 grid
    stone(256, 352, 150, 56, MOSS)
    stone(256, 262, 112, 48, SAGE)
    stone(256, 184, 72, 40, BONE)
    return img


def main() -> None:
    PUBLIC.mkdir(exist_ok=True)

    draw_cairn(512, full_bleed=False).save(PUBLIC / "icon-512.png")
    draw_cairn(512, full_bleed=False).resize((192, 192), Image.LANCZOS).save(PUBLIC / "icon-192.png")
    draw_cairn(512, full_bleed=True, scale=0.78).save(PUBLIC / "icon-512-maskable.png")
    # iOS rounds its own corners — give it a full-bleed square
    draw_cairn(512, full_bleed=True, scale=0.9).resize((180, 180), Image.LANCZOS).save(
        PUBLIC / "apple-touch-icon.png"
    )
    print(f"Icons written to {PUBLIC}")


if __name__ == "__main__":
    main()
