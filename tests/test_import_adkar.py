"""Guards on the adkar extractor.

This importer cuts a fragment out of scripture and publishes it alone. A rule
that is slightly wrong does not crash - it puts a truncated supplication on a
channel, six times a day, unreviewed. Every test here pins one of the rules
that stops that.
"""
import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "import_adkar",
    Path(__file__).resolve().parents[1] / "scripts" / "import_adkar.py",
)
ia = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ia)

CHAIN = "حَدَّثَنَا عَلِيُّ بْنُ عَبْدِ اللَّهِ، قَالَ حَدَّثَنَا جَرِيرٌ، عَنْ مَنْصُورٍ، "
DUA = "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ وَالْعَجْزِ وَالْكَسَلِ وَالْبُخْلِ"


def test_the_supplication_is_taken_and_the_chain_is_left_behind():
    text = f'{CHAIN}أَنَّ النَّبِيَّ صلى الله عليه وسلم قَالَ " {DUA} "'
    out = ia.extract(text)
    assert out is not None
    assert out.startswith("اللَّهُمَّ")
    assert "حَدَّثَنَا" not in out
    assert "جَرِيرٌ" not in out


def test_a_hadith_with_no_quote_yields_nothing():
    """No quote means no boundary the source drew, and we never invent one."""
    assert ia.extract(f"{CHAIN}كَانَ النَّبِيُّ صلى الله عليه وسلم يَقُولُ {DUA}") is None


def test_a_quote_without_a_supplication_yields_nothing():
    text = f'{CHAIN}قَالَ " إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى "'
    assert ia.extract(text) is None


def test_a_quote_that_still_holds_a_narration_marker_is_dropped():
    """A correctly quoted span cannot contain one. If it does, the quotation
    marks were unreliable for that entry - drop it rather than repair it."""
    text = f'قَالَ " {DUA} حَدَّثَنَا مُوسَى عَنْ نَافِعٍ وَقَالَ اللَّهُمَّ بَارِكْ "'
    assert ia.extract(text) is None


def test_a_cross_reference_stub_is_dropped():
    text = f'قَالَ " {DUA} بِهَذَا الإِسْنَادِ "'
    assert ia.extract(text) is None


def test_too_short_and_too_long_are_both_rejected():
    assert ia.extract('قَالَ " اللَّهُمَّ "') is None            # under 40
    long = "اللَّهُمَّ " + ("اغْفِرْ لِي وَارْحَمْنِي " * 40)
    assert len(long) > ia.MAX_CHARS
    assert ia.extract(f'قَالَ " {long} "') is None


def test_matching_ignores_diacritics():
    """The corpus is fully vocalised. A bare pattern must still find the
    vocalised form, or this importer silently yields nothing at all."""
    assert ia.FORMULA.search("اللَّهُمَّ اغْفِرْ لِي وَارْحَمْنِي")
    assert ia.FORMULA.search("سُبْحَانَ اللَّهِ وَبِحَمْدِهِ")


def test_both_dhikr_and_dua_families_are_recognised():
    dhikr = "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ سُبْحَانَ اللَّهِ الْعَظِيمِ وَالْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"
    assert ia.extract(f'قَالَ " {dhikr} "') is not None
    assert ia.extract(f'قَالَ " {DUA} "') is not None


def test_only_the_first_qualifying_segment_is_taken():
    """Several quoted passages means a narrative with dialogue, which is what
    this importer exists to exclude - so we never concatenate them."""
    second = "اللَّهُمَّ رَبَّنَا لَكَ الْحَمْدُ مِلْءَ السَّمَاوَاتِ وَمِلْءَ الأَرْضِ وَمَا بَيْنَهُمَا"
    out = ia.extract(f'قَالَ " {DUA} " ثُمَّ قَالَ " {second} "')
    assert out is not None
    assert second not in out


def _book(tmp_path, name, hadiths, title="صحيح البخاري"):
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps({
        "id": 1,
        "metadata": {"arabic": {"title": title, "author": "فلان"}},
        "chapters": [{"id": 1, "arabic": "كتاب الدعوات"}],
        "hadiths": hadiths,
    }, ensure_ascii=False), encoding="utf-8")
    return p


def test_convert_book_builds_entries_with_adkar_prefixed_ids(tmp_path):
    p = _book(tmp_path, "bukhari", [
        {"idInBook": 141, "chapterId": 1,
         "arabic": f'{CHAIN}قَالَ " {DUA} "'},
    ])
    entries, stats = ia.convert_book(p)
    assert len(entries) == 1
    e = entries[0]
    assert e["id"] == "adkar-bukhari-00141"
    assert e["source"] == "صحيح البخاري"
    assert e["reference"] == "صحيح البخاري 141"
    assert e["category"] == "كتاب الدعوات"
    assert e["text"].startswith("اللَّهُمَّ")
    assert stats["kept"] == 1


def test_convert_book_skips_hadith_with_no_supplication(tmp_path):
    p = _book(tmp_path, "bukhari", [
        {"idInBook": 1, "chapterId": 1,
         "arabic": f'{CHAIN}قَالَ " إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى "'},
        {"idInBook": 2, "chapterId": 1, "arabic": f'قَالَ " {DUA} "'},
    ])
    entries, stats = ia.convert_book(p)
    assert [e["id"] for e in entries] == ["adkar-bukhari-00002"]
    assert stats["total"] == 2
    assert stats["no_dua"] == 1


def test_convert_book_skips_hadith_with_empty_text(tmp_path):
    p = _book(tmp_path, "bukhari", [
        {"idInBook": 1, "chapterId": 1, "arabic": ""},
        {"idInBook": 2, "chapterId": 1, "arabic": f'قَالَ " {DUA} "'},
    ])
    entries, stats = ia.convert_book(p)
    assert len(entries) == 1
    assert stats["no_text"] == 1


def test_convert_book_falls_back_to_the_book_title_for_an_unknown_chapter(tmp_path):
    p = _book(tmp_path, "nawawi40", [
        {"idInBook": 7, "chapterId": 999, "arabic": f'قَالَ " {DUA} "'},
    ], title="الأربعون النووية")
    entries, _ = ia.convert_book(p)
    assert entries[0]["category"] == "الأربعون النووية"


def test_every_produced_entry_has_the_five_required_fields(tmp_path):
    """corpus.py rejects an entry missing any of these, and it rejects the
    whole file - one bad entry would take the channel down, not just itself."""
    p = _book(tmp_path, "muslim", [
        {"idInBook": 9, "chapterId": 1, "arabic": f'قَالَ " {DUA} "'},
    ], title="صحيح مسلم")
    entries, _ = ia.convert_book(p)
    for field in ("id", "text", "category", "source", "reference"):
        assert isinstance(entries[0][field], str) and entries[0][field].strip()
