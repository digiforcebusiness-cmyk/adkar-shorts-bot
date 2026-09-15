from adkar_bot.corpus import Dhikr
from adkar_bot.metadata import build_description, build_tags, build_title
from adkar_bot.profiles import ADKAR, HADITH

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
    desc = build_description(SHORT, ADKAR)
    assert SHORT.text in desc
    assert SHORT.source in desc
    assert SHORT.reference in desc


def test_tags_include_category_and_are_unique():
    tags = build_tags(SHORT, ADKAR)
    assert SHORT.category in tags
    assert len(tags) == len(set(tags))


def test_description_carries_the_profiles_own_handle_and_hashtags():
    assert ADKAR.channel_handle in build_description(SHORT, ADKAR)
    assert ADKAR.hashtags in build_description(SHORT, ADKAR)
    assert HADITH.channel_handle in build_description(SHORT, HADITH)
    assert HADITH.hashtags in build_description(SHORT, HADITH)


def test_a_description_never_advertises_the_other_channel():
    assert HADITH.channel_handle not in build_description(SHORT, ADKAR)
    assert ADKAR.channel_handle not in build_description(SHORT, HADITH)


def test_tags_come_from_the_profile():
    assert set(HADITH.base_tags).issubset(build_tags(SHORT, HADITH))
    assert set(ADKAR.base_tags).issubset(build_tags(SHORT, ADKAR))


def test_building_tags_does_not_mutate_the_profile():
    """build_tags returns a list; if it returned the profile's own storage,
    a caller appending to the result would corrupt every later run in the
    process."""
    before = HADITH.base_tags
    build_tags(SHORT, HADITH).append("sabotage")
    assert HADITH.base_tags == before
