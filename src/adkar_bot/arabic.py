from collections.abc import Callable

from arabic_reshaper import ArabicReshaper
from bidi.algorithm import get_display

# delete_harakat=False is essential — the default strips tashkeel.
_reshaper = ArabicReshaper(
    configuration={"delete_harakat": False, "support_ligatures": True}
)


def shape(line: str) -> str:
    """Reshape one line to presentation forms, then apply bidi for display.

    Must be called on an already-wrapped line. Shaping a multi-line block or
    shaping before wrapping splits presentation forms mid-word.
    """
    return get_display(_reshaper.reshape(line))


def wrap_logical(text: str, fits: Callable[[str], bool]) -> list[str]:
    """Greedy word wrap over logical-order source text.

    `fits` decides whether a candidate line is acceptable; it is supplied by
    the layout stage, which owns all font metrics. A single word wider than
    the box is placed on its own line and left overflowing — the caller's
    binary search resolves that by choosing a smaller font.
    """
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if fits(candidate):
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
