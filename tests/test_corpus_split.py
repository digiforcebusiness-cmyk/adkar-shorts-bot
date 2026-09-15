import json

from adkar_bot import config
from adkar_bot.profiles import ADKAR, HADITH


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_each_corpus_holds_only_its_own_texts():
    adkar_ids = {e["id"] for e in _load(ADKAR.corpus_path)}
    hadith_ids = {e["id"] for e in _load(HADITH.corpus_path)}
    # "hisn-" is the original 206 curated entries; "adkar-" is the corpus
    # expansion's machine-extracted supplications (scripts/import_adkar.py).
    # Both belong to the adkar channel's corpus by design - see
    # tests/test_import_adkar.py, which mixes the two prefixes deliberately.
    assert all(i.startswith(("hisn-", "adkar-")) for i in adkar_ids)
    assert all(i.startswith(("bukhari-", "muslim-")) for i in hadith_ids)


def test_the_two_corpora_are_disjoint():
    adkar_ids = {e["id"] for e in _load(ADKAR.corpus_path)}
    hadith_ids = {e["id"] for e in _load(HADITH.corpus_path)}
    assert adkar_ids.isdisjoint(hadith_ids)


def test_nothing_was_lost_in_the_split():
    """7,888 entries went in; 7,888 must still be there. A partition that
    drops entries is the one failure mode here that is silent and
    unrecoverable. The adkar corpus has since grown by design (the corpus
    expansion in scripts/import_adkar.py adds machine-extracted entries on
    top of the original 206), so the total only ever grows from here - it
    must never fall back below the original count."""
    total = len(_load(ADKAR.corpus_path)) + len(_load(HADITH.corpus_path))
    assert total >= 7888


def test_the_mixed_state_file_is_gone():
    assert not (config.DATA_DIR / "state.json").exists()


def test_neither_channel_starts_with_entries_marked_used():
    """@DIKR-o6k has published nothing, so all 206 adkar are available to it.

    Asserted only for adkar. The hadith channel was still running while this
    split was built and has since published real hadith, so its used list is
    legitimately non-empty - see the subset invariant below, which is the
    property that actually has to hold forever.
    """
    assert _load(ADKAR.state_path)["used"] == []


def test_neither_channel_can_mark_the_other_corpus_entry_used():
    """The invariant that outlives the migration: every id a channel has
    marked used must be an entry of that channel's own corpus.

    A violation means the rotations have crossed - one channel consuming the
    other's corpus - which is the failure this whole split exists to prevent.
    """
    for profile in (ADKAR, HADITH):
        corpus_ids = {e["id"] for e in _load(profile.corpus_path)}
        used = set(_load(profile.state_path)["used"])
        assert used <= corpus_ids, f"{profile.name} used ids outside its corpus"


def test_the_hadith_channel_keeps_its_publish_history():
    """The already-uploaded videos went out through that channel's
    credentials. The record of them is the only audit trail of what is on
    the channel, so it survives the split even though some of those ids no
    longer appear in that profile's corpus.

    Deliberately not pinned to a count: the channel publishes daily, so any
    exact number here would be stale within a day of being written.
    """
    published = _load(HADITH.state_path)["published"]
    assert published, "the hadith channel's publish history was lost"
    assert all("id" in record and "video_id" in record for record in published)


def test_the_new_channel_starts_with_no_history():
    assert _load(ADKAR.state_path)["published"] == []
