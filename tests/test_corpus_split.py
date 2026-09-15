import json

from adkar_bot import config
from adkar_bot.profiles import ADKAR, HADITH


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_each_corpus_holds_only_its_own_texts():
    adkar_ids = {e["id"] for e in _load(ADKAR.corpus_path)}
    hadith_ids = {e["id"] for e in _load(HADITH.corpus_path)}
    assert all(i.startswith("hisn-") for i in adkar_ids)
    assert all(i.startswith(("bukhari-", "muslim-")) for i in hadith_ids)


def test_the_two_corpora_are_disjoint():
    adkar_ids = {e["id"] for e in _load(ADKAR.corpus_path)}
    hadith_ids = {e["id"] for e in _load(HADITH.corpus_path)}
    assert adkar_ids.isdisjoint(hadith_ids)


def test_nothing_was_lost_in_the_split():
    """7,888 entries went in; 7,888 must come out. A partition that drops
    entries is the one failure mode here that is silent and unrecoverable."""
    total = len(_load(ADKAR.corpus_path)) + len(_load(HADITH.corpus_path))
    assert total == 7888


def test_the_mixed_state_file_is_gone():
    assert not (config.DATA_DIR / "state.json").exists()


def test_neither_channel_starts_with_entries_marked_used():
    """No hadith has ever published, and @DIKR-o6k has published nothing at
    all - so all 206 adkar must still be available to it."""
    for profile in (ADKAR, HADITH):
        assert _load(profile.state_path)["used"] == []


def test_the_hadith_channel_keeps_its_publish_history():
    """The 33 already-uploaded videos went out through that channel's
    credentials. The record of them is the only audit trail of what is on
    the channel, so it survives the split even though the ids no longer
    appear in that profile's corpus."""
    published = _load(HADITH.state_path)["published"]
    assert len(published) == 33
    assert all(record["id"].startswith("hisn-") for record in published)


def test_the_new_channel_starts_with_no_history():
    assert _load(ADKAR.state_path)["published"] == []
