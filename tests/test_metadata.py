from adkar_bot.corpus import Dhikr
from adkar_bot.metadata import build_description, build_tags, build_title

LONG = Dhikr(
    id="x", text="اللَّهُمَّ " * 40, category="duaa",
    source="سنن", reference="أبو داود ١٥٢٢",
)
SHORT = Dhikr(
    id="y", text="لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ", category="dhikr",
    source="متفق عليه", reference="البخاري ٦٤٠٩",
)


def test_title_within_youtube_limit():
    assert len(build_title(LONG)) <= 100


def test_title_tagged_as_short():
    assert "#shorts" in build_title(SHORT)


def test_long_title_truncates_on_a_word_boundary():
    title = build_title(LONG)
    body = title[: -len(" #shorts")]
    assert body.endswith("…")
    assert not body.endswith(" …")          # no dangling space before ellipsis
    kept = body.rstrip("…").split()
    source_words = LONG.text.split()
    assert kept                              # something survived
    assert all(word in source_words for word in kept)  # no split words


def test_short_title_is_not_truncated():
    title = build_title(SHORT)
    assert title == f"{SHORT.text} #shorts"
    assert "…" not in title


def test_description_carries_attribution():
    desc = build_description(SHORT)
    assert SHORT.text in desc
    assert SHORT.source in desc
    assert SHORT.reference in desc


def test_tags_include_category_and_are_unique():
    tags = build_tags(SHORT)
    assert SHORT.category in tags
    assert len(tags) == len(set(tags))
