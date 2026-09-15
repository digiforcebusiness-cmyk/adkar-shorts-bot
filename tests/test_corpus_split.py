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
    """7,888 entries went in and none may silently vanish. The two corpora
    are asserted separately rather than summed: a total that only has to
    reach 7,888 would still pass if adkar's growth masked an equal loss from
    hadith, which is precisely the silent, unrecoverable failure this guards.

    hadith is pinned exactly - nothing in this project writes to it, so any
    change there is a bug. adkar is a lower bound, since the corpus
    expansion adds to it by design and will add more later.
    """
    adkar = _load(ADKAR.corpus_path)
    hadith = _load(HADITH.corpus_path)
    assert len(hadith) == 7682, "the hadith corpus must not change"
    assert len(adkar) >= 206, "the curated Hisn al-Muslim entries must survive"
    assert len(adkar) + len(hadith) >= 7888


def test_the_mixed_state_file_is_gone():
    assert not (config.DATA_DIR / "state.json").exists()


def test_every_published_record_is_well_formed():
    """Replaces an assertion that neither channel had marked anything used.

    That was true the day the split landed and is now false for both: each
    channel publishes daily. The shape of a record is what actually has to
    hold forever, along with the subset invariant below.
    """
    for profile in (ADKAR, HADITH):
        for record in _load(profile.state_path)["published"]:
            assert record.get("id"), f"{profile.name} record with no entry id"
            assert record.get("video_id"), f"{profile.name} record with no video id"


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


def test_the_adkar_channel_only_ever_published_its_own_corpus():
    """@DIKR-o6k was created after the split, so unlike the hadith channel it
    inherited no history - every id it has published must be one of its own
    entries.

    Asserted for adkar alone on purpose: the hadith channel deliberately
    keeps 34 hisn-* records that predate the split and no longer appear in
    its corpus, which the test above documents. This replaces an assertion
    that @DIKR-o6k had published nothing at all - true on the day it was
    written, false as soon as the channel went live.
    """
    corpus_ids = {e["id"] for e in _load(ADKAR.corpus_path)}
    published = {r["id"] for r in _load(ADKAR.state_path)["published"]}
    assert published <= corpus_ids, "adkar published an entry outside its corpus"
