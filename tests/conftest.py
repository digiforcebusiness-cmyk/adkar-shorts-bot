import pytest


@pytest.fixture(autouse=True)
def _yt_oauth_env(monkeypatch):
    """cmd_publish reads real OAuth env vars via cli._require_env(), which
    raises a ConfigError (with an actionable message) if one is unset. Tests
    always patch build_client/upload_video/post_comment so the values
    themselves are never used for a real network call — this just keeps
    _require_env from raising in environments where they aren't set.
    """
    monkeypatch.setenv("YT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("YT_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("YT_REFRESH_TOKEN", "test-refresh-token")
