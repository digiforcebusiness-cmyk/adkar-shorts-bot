"""Guards on the hadith importer's two cutting rules.

The importer edits scripture. A rule that is slightly wrong does not crash —
it publishes a subtly misquoted hadith, every day, automatically. These tests
pin the behaviour that made the difference.
"""
import importlib.util
import re
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "import_hadith", Path(__file__).resolve().parents[1] / "scripts" / "import_hadith.py"
)
imp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(imp)


def test_marker_must_begin_its_own_word():
    """The bug this exists for: 'ان رسول الله' matching the tail of وكان.

    Cutting there yields 'انَ رسول الله' — a fragment of a word presented as
    the start of a narration. It read plausibly and was wrong.
    """
    text = "حَدَّثَنَا مُوسَى وَكَانَ رَسُولُ اللَّهِ صلى الله عليه وسلم يُعَالِجُ"
    m = imp.MATN.search(text)
    assert m is None or not text[m.start():].startswith("انَ")


def test_cut_never_starts_mid_word():
    text = "حَدَّثَنَا مُوسَى وَكَانَ رَسُولُ اللَّهِ صلى الله عليه وسلم يُعَالِجُ"
    m = imp.MATN.search(text)
    if m:
        assert m.start() == 0 or text[m.start() - 1].isspace()


def test_explicit_saying_is_still_extracted():
    """The guard must not cost us the real matches it was added around."""
    text = ("حَدَّثَنَا عَبْدُ اللَّهِ، قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم "
            "\" إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ \"")
    m = imp.MATN.search(text)
    assert m is not None
    assert text[m.start():].startswith("قَالَ")


@pytest.mark.parametrize("phrase", ["بِهَذَا الإِسْنَادِ", "نَحْوَهُ", "بِمِثْلِهِ"])
def test_cross_reference_stubs_are_detected(phrase):
    """Entries that only point at another chain carry no readable content."""
    assert imp.XREF.search(f"وَحَدَّثَنِي عُبَيْدُ اللَّهِ {phrase} .")


def test_clean_strips_bidi_marks_but_keeps_words():
    raw = "قَالَ‏ .‏  رَسُولُ   اللَّهِ"
    out = imp.clean(raw)
    assert "‏" not in out
    assert "  " not in out
    assert "قَالَ" in out and "رَسُولُ" in out


def test_length_bounds_are_the_measured_ones():
    """450 is a legibility limit, not a round number - see README section 5."""
    assert imp.MAX_CHARS == 450
    assert imp.MIN_CHARS == 40
