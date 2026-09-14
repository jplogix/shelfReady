"""Generate category-matching demonstration illustrations (not authentic product photography)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "fixtures" / "demo_images"

CREAM = (246, 241, 232, 255)
CHARCOAL = (41, 37, 36, 255)
MUTED = (87, 83, 78, 255)
WHITE = (255, 253, 248, 255)
LINE = (231, 224, 212, 255)

SPECS = {
    "demo-soda-can.png": {
        "label": "Soda can",
        "draw": "can",
        "fill": (185, 45, 48, 255),
        "accent": (212, 175, 55, 255),
    },
    "demo-toothpaste.png": {
        "label": "Toothpaste",
        "draw": "tube",
        "fill": (232, 244, 248, 255),
        "accent": (47, 107, 79, 255),
    },
    "demo-laundry-pods.png": {
        "label": "Laundry pacs",
        "draw": "pods",
        "fill": (234, 122, 48, 255),
        "accent": (255, 214, 160, 255),
    },
    "demo-paper-towels.png": {
        "label": "Paper towels",
        "draw": "rolls",
        "fill": (250, 250, 248, 255),
        "accent": (70, 130, 180, 255),
    },
    "demo-shampoo.png": {
        "label": "Shampoo bottle",
        "draw": "bottle",
        "fill": (70, 110, 168, 255),
        "accent": (196, 214, 232, 255),
    },
    "demo-deodorant.png": {
        "label": "Deodorant",
        "draw": "stick",
        "fill": (90, 98, 110, 255),
        "accent": (176, 184, 196, 255),
    },
    "demo-cleaner.png": {
        "label": "Spray cleaner",
        "draw": "spray",
        "fill": (72, 140, 92, 255),
        "accent": (190, 220, 196, 255),
    },
}


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _caption(draw: ImageDraw.ImageDraw, w: int, h: int, label: str) -> None:
    title_font = _font(28)
    cap_font = _font(18)
    draw.text((w / 2, 72), label, fill=CHARCOAL, font=title_font, anchor="mm")
    draw.text(
        (w / 2, h - 56),
        "Demonstration illustration · not authentic product photography",
        fill=MUTED,
        font=cap_font,
        anchor="mm",
    )


def _ellipse(draw: ImageDraw.ImageDraw, box, fill, outline=None, width=3) -> None:
    draw.ellipse(box, fill=fill, outline=outline or LINE, width=width)


def _rounded(draw: ImageDraw.ImageDraw, box, fill, radius=28, outline=None) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline or CHARCOAL, width=3)


def draw_can(draw: ImageDraw.ImageDraw, fill, accent) -> None:
    _rounded(draw, (300, 210, 500, 620), fill, radius=40)
    _rounded(draw, (318, 228, 482, 310), accent, radius=20, outline=accent)
    _ellipse(draw, (310, 188, 490, 248), WHITE, CHARCOAL)
    _ellipse(draw, (360, 206, 440, 236), LINE, MUTED)


def draw_tube(draw: ImageDraw.ImageDraw, fill, accent) -> None:
    _rounded(draw, (250, 300, 550, 500), fill, radius=36)
    _rounded(draw, (550, 340, 610, 460), accent, radius=16, outline=accent)
    draw.polygon([(250, 320), (190, 400), (250, 480)], fill=accent, outline=CHARCOAL)
    _rounded(draw, (300, 340, 500, 460), WHITE, radius=18, outline=LINE)


def draw_pods(draw: ImageDraw.ImageDraw, fill, accent) -> None:
    _rounded(draw, (230, 250, 570, 590), fill, radius=36)
    for i, xy in enumerate(((290, 320), (400, 320), (345, 420))):
        color = accent if i != 1 else WHITE
        _ellipse(draw, (xy[0], xy[1], xy[0] + 110, xy[1] + 90), color, CHARCOAL)


def draw_rolls(draw: ImageDraw.ImageDraw, fill, accent) -> None:
    for x in (250, 355, 460):
        _rounded(draw, (x, 240, x + 90, 600), fill, radius=20)
        _ellipse(draw, (x, 210, x + 90, 270), WHITE, CHARCOAL)
        _rounded(draw, (x + 8, 360, x + 82, 410), accent, radius=8, outline=accent)


def draw_bottle(draw: ImageDraw.ImageDraw, fill, accent) -> None:
    _rounded(draw, (320, 260, 480, 620), fill, radius=48)
    _rounded(draw, (360, 170, 440, 270), accent, radius=16, outline=accent)
    _rounded(draw, (345, 330, 455, 470), WHITE, radius=20, outline=LINE)


def draw_stick(draw: ImageDraw.ImageDraw, fill, accent) -> None:
    _rounded(draw, (330, 280, 470, 600), fill, radius=24)
    _rounded(draw, (345, 210, 455, 300), accent, radius=18, outline=accent)
    _ellipse(draw, (355, 188, 445, 238), WHITE, CHARCOAL)


def draw_spray(draw: ImageDraw.ImageDraw, fill, accent) -> None:
    _rounded(draw, (320, 300, 480, 620), fill, radius=36)
    _rounded(draw, (360, 230, 440, 310), accent, radius=12, outline=accent)
    draw.polygon([(440, 240), (530, 200), (440, 270)], fill=CHARCOAL)
    _rounded(draw, (345, 360, 455, 500), WHITE, radius=18, outline=LINE)


DRAWERS = {
    "can": draw_can,
    "tube": draw_tube,
    "pods": draw_pods,
    "rolls": draw_rolls,
    "bottle": draw_bottle,
    "stick": draw_stick,
    "spray": draw_spray,
}


def render(name: str, spec: dict) -> None:
    img = Image.new("RGBA", (800, 800), CREAM)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((48, 48, 752, 752), radius=36, outline=LINE, width=3)
    DRAWERS[spec["draw"]](draw, spec["fill"], spec["accent"])
    _caption(draw, 800, 800, spec["label"])
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, format="PNG", optimize=True)


def main() -> None:
    for name, spec in SPECS.items():
        render(name, spec)
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
