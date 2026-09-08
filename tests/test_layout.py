import pytest
from conftest import corpus_sample
from adkar_bot import config
from adkar_bot.corpus import load_corpus
from adkar_bot.layout import Layout, LayoutError, duration_for, fit

SHORT = "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ"
LONG = ("اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ، وَأَعُوذُ بِكَ مِنَ الْعَجْزِ "
        "وَالْكَسَلِ، وَأَعُوذُ بِكَ مِنَ الْجُبْنِ وَالْبُخْلِ")


def test_short_text_gets_a_larger_font_than_long_text():
    assert fit(SHORT).font_size > fit(LONG).font_size


def test_layout_always_fits_the_content_box():
    for text in (SHORT, LONG):
        layout = fit(text)
        # ink_h, not block_height, is what fit() actually gates on: block_height
        # includes the full 1.6x line-spacing leading for every line, which is
        # more generous than what is actually painted.
        assert layout.ink_h <= config.CONTENT_H
        assert config.FONT_MIN <= layout.font_size <= config.FONT_MAX


def test_every_corpus_entry_lays_out():
    for dhikr in corpus_sample():
        layout = fit(dhikr.text)
        assert layout.lines
        assert layout.ink_h <= config.CONTENT_H


def test_lines_are_shaped_not_raw():
    layout = fit(SHORT)
    assert "".join(layout.lines) != SHORT


def test_impossible_text_raises():
    with pytest.raises(LayoutError):
        fit("م " * 4000)


def test_duration_is_clamped():
    assert duration_for("كلمة") == config.DUR_MIN
    assert duration_for("كلمة " * 500) == config.DUR_MAX


def test_duration_scales_with_length():
    assert duration_for("كلمة " * 6) > duration_for("كلمة " * 3)
