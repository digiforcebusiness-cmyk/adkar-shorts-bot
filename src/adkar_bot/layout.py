from dataclasses import dataclass

from PIL import ImageFont

from . import config
from .arabic import shape, wrap_logical


class LayoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class Layout:
    font_size: int
    lines: list[str]      # already shaped, display order
    line_height: int
    block_height: int


def _try_size(text: str, size: int) -> Layout | None:
    font = ImageFont.truetype(str(config.FONT_PATH), size)

    def fits(candidate: str) -> bool:
        return font.getlength(shape(candidate)) <= config.CONTENT_W

    logical_lines = wrap_logical(text, fits)
    if not logical_lines:
        return None

    shaped = [shape(line) for line in logical_lines]
    if max(font.getlength(line) for line in shaped) > config.CONTENT_W:
        return None  # a single word overflows at this size

    line_height = int(size * config.LINE_SPACING)
    block_height = line_height * len(shaped)
    if block_height > config.CONTENT_H:
        return None

    return Layout(
        font_size=size,
        lines=shaped,
        line_height=line_height,
        block_height=block_height,
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
