import random

import pytest


@pytest.fixture(autouse=True)
def _yt_oauth_env(monkeypatch):
    """cmd_publish reads real OAuth env vars via cli._require_env(), which
    raises a ConfigError (with an actionable message) if one is unset. Tests
    always patch build_client/upload_video so the values themselves are
    never used for a real network call — this just keeps _require_env from
    raising in environments where they aren't set.
    """
    monkeypatch.setenv("YT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("YT_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("YT_REFRESH_TOKEN", "test-refresh-token")
    monkeypatch.setenv("YT_ADKAR_CLIENT_ID", "test-adkar-client-id")
    monkeypatch.setenv("YT_ADKAR_CLIENT_SECRET", "test-adkar-client-secret")
    monkeypatch.setenv("YT_ADKAR_REFRESH_TOKEN", "test-adkar-refresh-token")
    monkeypatch.delenv("PROFILE", raising=False)
    monkeypatch.delenv("PUBLISH_COUNT", raising=False)


def corpus_sample(profile=None, n=120):
    """A bounded, deterministic slice of a corpus for the exhaustive tests.

    These tests used to walk all 206 entries. The corpus is now ~7,900, and
    rasterising every line of every one of them turned a 90-second suite into
    a many-minute one on the daily publish job.

    Defaults to the hadith profile: it is by far the larger corpus and holds
    the long entries this sample exists to exercise.

    The sample is half longest-first and half seeded-random. The longest
    entries are the point: overflow and handle collisions only ever happen at
    the small end of the font range, so the worst cases are always covered
    rather than left to chance.
    """
    from adkar_bot.corpus import load_corpus
    from adkar_bot.profiles import HADITH

    corpus = load_corpus((profile or HADITH).corpus_path)
    if len(corpus) <= n:
        return corpus
    longest = sorted(corpus, key=lambda d: -len(d.text))[: n // 2]
    rest = [d for d in corpus if d not in longest]
    return longest + random.Random(0).sample(rest, n - len(longest))
