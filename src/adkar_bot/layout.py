from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from . import config
from .arabic import shape, wrap_logical


class LayoutError(RuntimeError):
    pass


_PROBE = ImageDraw.Draw(Image.new("L", (1, 1)))


def _ink_box(font, shaped_lines, line_height):
    """Union ink box of the whole block, drawn at x=0 with anchor='ma'.

    Returns (x0, y0, x1, y1) relative to that nominal origin. getlength()
    gives the advance width, which excludes tashkeel above the ascender and
    glyph overhang past the advance — this measures what is actually painted.
    """
    boxes = [
        _PROBE.textbbox((0, i * line_height), line, font=font, anchor="ma")
        for i, line in enumerate(shaped_lines)
    ]
    return (
        min(b[0] for b in boxes), min(b[1] for b in boxes),
        max(b[2] for b in boxes), max(b[3] for b in boxes),
    )


@dataclass(frozen=True)
class Layout:
    font_size: int
    lines: list[str]      # already shaped, display order
    line_height: int
    block_height: int
    ink_w: int
    ink_h: int
    ink_dx: int
    ink_dy: int


def _try_size(text: str, size: int) -> Layout | None:
    font = ImageFont.truetype(str(config.FONT_PATH), size)

    def fits(candidate: str) -> bool:
        return font.getlength(shape(candidate)) <= config.CONTENT_W

    logical_lines = wrap_logical(text, fits)
    if not logical_lines:
        return None

    shaped = [shape(line) for line in logical_lines]

    line_height = int(size * config.LINE_SPACING)
    block_height = line_height * len(shaped)

    x0, y0, x1, y1 = _ink_box(font, shaped, line_height)
    ink_w, ink_h = x1 - x0, y1 - y0
    if ink_w > config.CONTENT_W or ink_h > config.CONTENT_H:
        return None  # painted ink overflows the content box

    return Layout(
        font_size=size,
        lines=shaped,
        line_height=line_height,
        block_height=block_height,
        ink_w=ink_w,
        ink_h=ink_h,
        ink_dx=x0,
        ink_dy=y0,
    )


def fit(text: str) -> Layout:
    """Largest font size at which the wrapped text fits the content box."""
    lo, hi = config.FONT_MIN, config.FONT_MAX
    best: Layout | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        attempt = _try_size(text, mid)
        if attempt is not None:
            best, lo = attempt, mid + 1
        else:
            hi = mid - 1

    if best is None:
        raise LayoutError(
            f"text does not fit at minimum size {config.FONT_MIN}px: {text[:40]!r}..."
        )
    return best


def duration_for(text: str) -> float:
    words = len(text.split())
    return min(config.DUR_MAX, max(config.DUR_MIN, config.DUR_PER_WORD * words))
