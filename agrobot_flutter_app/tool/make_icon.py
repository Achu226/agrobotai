"""Draws the AGROBOTAI launcher icon (leaf + circuit vein = crop + AI) at 1024 px.

    E:\\AGROBOTAI\\.venv\\Scripts\\python.exe tool\\make_icon.py
    flutter pub run flutter_launcher_icons
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "assets" / "icon"
OUT.mkdir(parents=True, exist_ok=True)
S = 1024
DARK, GREEN, LIGHT = (27, 94, 32), (46, 125, 50), (129, 199, 132)


def leaf_layer(scale: float = 1.0) -> Image.Image:
    """White leaf with a green circuit-style midrib, on transparency."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2

    def p(x, y):  # scale around the centre
        return (c + (x - c) * scale, c + (y - c) * scale)

    # Leaf body: two arcs meeting at the tip and the stem
    leaf = [p(512, 170)]
    import math

    for i in range(1, 60):
        t = i / 60
        leaf.append(p(512 + 300 * math.sin(math.pi * t) * (1 - 0.15 * t), 170 + 640 * t))
    for i in range(60, 0, -1):
        t = i / 60
        leaf.append(p(512 - 300 * math.sin(math.pi * t) * (1 - 0.15 * t), 170 + 640 * t))
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 10, y + 16) for x, y in leaf], fill=(0, 0, 0, 90))
    img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(img)
    d.polygon(leaf, fill=(255, 255, 255, 255))

    # Stem
    d.line([p(512, 800), p(512, 880)], fill=(255, 255, 255, 255), width=int(34 * scale))
    # Circuit midrib with side traces ending in nodes
    w = int(22 * scale)
    d.line([p(512, 250), p(512, 800)], fill=GREEN, width=w)
    for y, dx, dy in [(360, 150, -60), (470, -170, -70), (580, 170, -70), (690, -150, -60)]:
        mid = p(512 + dx * 0.55, y)
        end = p(512 + dx, y + dy)
        d.line([p(512, y + 40), mid, end], fill=GREEN, width=int(16 * scale), joint="curve")
        r = 26 * scale
        d.ellipse([end[0] - r, end[1] - r, end[0] + r, end[1] + r], fill=GREEN)
        r2 = 11 * scale
        d.ellipse([end[0] - r2, end[1] - r2, end[0] + r2, end[1] + r2], fill=(255, 255, 255, 255))
    r = 34 * scale
    tip = p(512, 250)
    d.ellipse([tip[0] - r, tip[1] - r, tip[0] + r, tip[1] + r], fill=GREEN)
    return img


def background() -> Image.Image:
    bg = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(bg)
    for y in range(S):  # vertical gradient, light top-left to dark bottom
        t = y / S
        col = tuple(int(LIGHT[i] * (1 - t) * 0.35 + GREEN[i] * (1 - t) * 0.65 + DARK[i] * t) for i in range(3))
        d.line([(0, y), (S, y)], fill=col + (255,))
    return bg


# Full icon (legacy launchers, Play Store): rounded square
full = Image.alpha_composite(background(), leaf_layer(0.92))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=220, fill=255)
rounded = Image.new("RGBA", (S, S), (0, 0, 0, 0))
rounded.paste(full, mask=mask)
rounded.save(OUT / "app_icon.png")
# Adaptive icon foreground: leaf inside the 66% safe zone, transparent background
leaf_layer(0.62).save(OUT / "app_icon_foreground.png")
print("icons written to", OUT)
