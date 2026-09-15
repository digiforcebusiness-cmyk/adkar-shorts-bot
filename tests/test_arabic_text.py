"""The shared matching helpers. Both importers edit scripture through these,
so a subtly wrong rule here misquotes on two channels instead of one."""
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "_arabic_text",
    Path(__file__).resolve().parents[1] / "scripts" / "_arabic_text.py",
)
at = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(at)


def test_bare_strips_diacritics_without_touching_letters():
    assert at.bare("اللَّهُمَّ") == "اللهم"
    assert at.bare("سُبْحَانَ اللَّهِ") == "سبحان الله"


def test_bare_collapses_whitespace():
    assert at.bare("قَالَ   رَسُولُ\nاللَّهِ") == "قال رسول الله"


def test_bare_is_idempotent():
    once = at.bare("اللَّهُمَّ اغْفِرْ لِي")
    assert at.bare(once) == once


def test_flex_matches_the_same_phrase_however_it_is_vocalised():
    """A plain substring search finds almost nothing in this corpus."""
    import re
    pat = re.compile(at.flex("قال رسول الله"))
    assert pat.search("قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم")


def test_flex_tolerates_extra_spacing_between_words():
    import re
    assert re.compile(at.flex("لا حول ولا قوة")).search("لا  حول   ولا قوة")


@pytest.mark.parametrize("phrase", ["بِهَذَا الإِسْنَادِ", "نَحْوَهُ", "بِمِثْلِهِ"])
def test_cross_reference_stubs_are_detected(phrase):
    assert at.XREF.search(f"وَحَدَّثَنِي عُبَيْدُ اللَّهِ {phrase} .")


def test_clean_strips_bidi_marks_but_keeps_words():
    out = at.clean("قَالَ‏ .‏  رَسُولُ   اللَّهِ")
    assert "‏" not in out
    assert "  " not in out
    assert "قَالَ" in out and "رَسُولُ" in out


def test_length_bounds_are_the_measured_ones():
    """450 is a legibility limit, not a round number - see README section 5."""
    assert at.MAX_CHARS == 450
    assert at.MIN_CHARS == 40
