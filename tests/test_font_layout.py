"""Guards against Pillow re-applying bidi on top of ours.

`arabic.shape()` reshapes and applies bidi before text reaches Pillow. Pillow's
RAQM layout engine applies its own bidi and shaping via FriBiDi/HarfBuzz, so it
reverses everything a second time and every word renders backwards.

Pillow selects RAQM automatically whenever libraqm is available. It is bundled
in the manylinux wheels used on CI and absent from the Windows wheels used
locally, so the same code renders correctly on one machine and reversed on the
other. That difference published a broken video before it was caught, and no
geometry test can detect it: reversed text occupies exactly the same box.
"""
import re
from pathlib import Path

from PIL import ImageFont

from adkar_bot.layout import load_font

SRC = Path(__file__).resolve().parents[1] / "src" / "adkar_bot"


def test_load_font_pins_the_basic_layout_engine():
    assert load_font(48).layout_engine is ImageFont.Layout.BASIC


def test_pinning_does_not_depend_on_libraqm_being_absent():
    """The engine must be BASIC even where RAQM is available.

    Locally libraqm is usually missing so BASIC is the default and this passes
    trivially. On CI libraqm is present, and this fails unless load_font pins
    the engine explicitly — which is the environment that actually broke.
    """
    from PIL import features

    font = load_font(64)
    assert font.layout_engine is ImageFont.Layout.BASIC, (
        f"layout engine is {font.layout_engine!r} with raqm="
        f"{features.check('raqm')}; text will be double-bidied and render "
        f"backwards"
    )


def test_load_font_is_the_only_way_fonts_are_loaded():
    """One choke point, so the engine cannot be bypassed by a new call site."""
    offenders = []
    for path in SRC.glob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"ImageFont\.truetype\s*\(", line):
                if path.name != "layout.py":
                    offenders.append(f"{path.name}:{i}")
    assert not offenders, (
        f"ImageFont.truetype called outside layout.load_font at {offenders}; "
        f"route it through load_font so the layout engine stays pinned"
    )
