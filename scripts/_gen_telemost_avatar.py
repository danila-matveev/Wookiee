"""One-shot generator for Wookiee Recorder bot avatar.

Pillow only — generates a 512x512 PNG with brand colors and a microphone glyph.
Run: .venv/bin/python scripts/_gen_telemost_avatar.py
Output: services/telemost_recorder_api/assets/avatar.png
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

_OUT = Path(__file__).resolve().parent.parent / "services" / "telemost_recorder_api" / "assets" / "avatar.png"
_BG_TOP = (94, 60, 233)
_BG_BOTTOM = (124, 58, 237)
_FG = (255, 255, 255)
_DOT = (245, 184, 0)


def _gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), _BG_TOP)
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        r = int(_BG_TOP[0] + (_BG_BOTTOM[0] - _BG_TOP[0]) * t)
        g = int(_BG_TOP[1] + (_BG_BOTTOM[1] - _BG_TOP[1]) * t)
        b = int(_BG_TOP[2] + (_BG_BOTTOM[2] - _BG_TOP[2]) * t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def main() -> None:
    size = 512
    img = _gradient(size)
    draw = ImageDraw.Draw(img)

    cx, cy = size // 2, size // 2 - 24
    mic_w, mic_h = 132, 200
    capsule = (cx - mic_w // 2, cy - mic_h // 2, cx + mic_w // 2, cy + mic_h // 2)
    draw.rounded_rectangle(capsule, radius=mic_w // 2, fill=_FG)

    arc_box = (cx - 110, cy + 30, cx + 110, cy + 250)
    draw.arc(arc_box, start=0, end=180, fill=_FG, width=18)

    stem_x = cx - 8
    draw.rectangle((stem_x, cy + 140, stem_x + 16, cy + 220), fill=_FG)

    base = (cx - 80, cy + 218, cx + 80, cy + 246)
    draw.rounded_rectangle(base, radius=14, fill=_FG)

    dot_r = 22
    draw.ellipse((cx + 56 - dot_r, cy - mic_h // 2 - dot_r + 18, cx + 56 + dot_r, cy - mic_h // 2 + dot_r + 18), fill=_DOT)

    halo = Image.new("L", img.size, 0)
    halo_draw = ImageDraw.Draw(halo)
    halo_draw.ellipse((40, 40, size - 40, size - 40), fill=70)
    halo = halo.filter(ImageFilter.GaussianBlur(40))
    img = Image.composite(Image.new("RGB", img.size, _FG), img, halo)
    # Above composite faded background; redo gradient under glyph by recomposing
    final = _gradient(size)
    glyph = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glyph)
    gd.rounded_rectangle(capsule, radius=mic_w // 2, fill=_FG + (255,))
    gd.arc(arc_box, start=0, end=180, fill=_FG + (255,), width=18)
    gd.rectangle((stem_x, cy + 140, stem_x + 16, cy + 220), fill=_FG + (255,))
    gd.rounded_rectangle(base, radius=14, fill=_FG + (255,))
    gd.ellipse((cx + 56 - dot_r, cy - mic_h // 2 - dot_r + 18, cx + 56 + dot_r, cy - mic_h // 2 + dot_r + 18), fill=_DOT + (255,))
    final = Image.alpha_composite(final.convert("RGBA"), glyph).convert("RGB")

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    final.save(_OUT, format="PNG", optimize=True)
    print(f"Wrote {_OUT} ({_OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
