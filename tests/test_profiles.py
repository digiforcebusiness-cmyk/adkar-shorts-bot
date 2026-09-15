from adkar_bot.profiles import ADKAR, HADITH, PROFILES


def test_each_profile_name_matches_its_key():
    for key, profile in PROFILES.items():
        assert profile.name == key


def test_profiles_share_no_paths_handles_or_credentials():
    """Two channels that share any of these are one channel with a bug."""
    for field in ("corpus_path", "state_path", "channel_handle", "env_prefix"):
        values = [getattr(p, field) for p in PROFILES.values()]
        assert len(set(values)) == len(values), f"{field} collides across profiles"


def test_base_tags_is_immutable():
    """A list default inside a frozen dataclass is frozen in name only:
    profile.base_tags.append(...) would mutate the shared class-level value
    for every later caller in the process."""
    for profile in PROFILES.values():
        assert isinstance(profile.base_tags, tuple)


def test_hadith_profile_preserves_the_live_channels_appearance():
    """@ZainKhairAllahChannel already has videos published with this exact
    gradient. The split must not restyle a channel that is already running."""
    assert HADITH.gradient == ((14, 34, 48), (6, 12, 20))
    assert HADITH.env_prefix == "YT"
    assert HADITH.default_count == 6


def test_adkar_profile_is_distinct_and_paced_for_a_206_entry_corpus():
    assert ADKAR.gradient != HADITH.gradient
    assert ADKAR.env_prefix == "YT_ADKAR"
    assert ADKAR.default_count == 1
    assert ADKAR.channel_handle == "@DIKR-o6k"
