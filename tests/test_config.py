import importlib

import pytest
from adkar_bot import config
from adkar_bot.config import ConfigError, assert_configured


def test_frame_is_vertical_1080x1920():
    assert (config.WIDTH, config.HEIGHT) == (1080, 1920)


def test_content_box_excludes_shorts_ui_chrome():
    assert config.CONTENT_W == 1080 - 2 * 96 - 140
    assert config.CONTENT_H == 1920 - config.SAFE_TOP - 280 - 90


def test_content_box_leaves_room_for_the_handle():
    """The text block must never reach the handle's band.

    Without HANDLE_BAND the content box ran to the bottom safe line and the
    tallest cards drew the duaa straight over the @handle — 8 of 12 corpus
    entries did exactly that before this was reserved.
    """
    text_bottom = config.SAFE_TOP + config.CONTENT_H
    handle_top = config.HEIGHT - config.SAFE_BOTTOM - config.HANDLE_SIZE - 24
    assert text_bottom < handle_top


def test_assert_configured_raises_on_placeholder(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", config.CHANNEL_HANDLE_PLACEHOLDER)
    with pytest.raises(ConfigError, match="CHANNEL_HANDLE"):
        assert_configured()


def test_assert_configured_passes_on_real_handle(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", "@adkar")
    assert assert_configured() is None


def test_assert_configured_raises_on_empty_handle(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", "")
    with pytest.raises(ConfigError, match="CHANNEL_HANDLE"):
        assert_configured()


def test_assert_configured_raises_on_whitespace_handle(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", "   ")
    with pytest.raises(ConfigError, match="CHANNEL_HANDLE"):
        assert_configured()


@pytest.fixture
def _reload_config_after():
    """Reload config.py after the test so a stubbed env var doesn't leak
    into config.CHANNEL_HANDLE for tests that run later in the session.

    Depends on monkeypatch being torn down first (request it before
    monkeypatch in the test signature) so the reload here sees the real,
    restored environment rather than the value the test injected.
    """
    yield
    importlib.reload(config)


def test_channel_handle_empty_env_var_resolves_to_placeholder(
    _reload_config_after, monkeypatch
):
    """A GitHub Actions repo variable left undefined still sets the env var
    to "" rather than leaving it unset — os.environ.get(..., default) would
    return "" in that case and never see the default. CHANNEL_HANDLE must
    treat "" the same as unset.
    """
    monkeypatch.setenv("CHANNEL_HANDLE", "")
    importlib.reload(config)
    assert config.CHANNEL_HANDLE == config.CHANNEL_HANDLE_PLACEHOLDER


def test_privacy_status_empty_env_falls_back_to_private(monkeypatch):
    """An undefined GitHub repo variable arrives as "", not unset."""
    import importlib
    monkeypatch.setenv("PRIVACY_STATUS", "")
    reloaded = importlib.reload(config)
    try:
        assert reloaded.PRIVACY_STATUS == "private"
    finally:
        monkeypatch.delenv("PRIVACY_STATUS", raising=False)
        importlib.reload(config)


def test_assert_configured_rejects_invalid_privacy_status(monkeypatch):
    # Resolve through the module, not the name imported at file scope:
    # importlib.reload in a sibling test rebinds ConfigError to a NEW class
    # object, so a previously-imported reference stops matching what is raised.
    monkeypatch.setattr(config, "CHANNEL_HANDLE", "@adkar")
    monkeypatch.setattr(config, "PRIVACY_STATUS", "publik")
    with pytest.raises(config.ConfigError, match="PRIVACY_STATUS"):
        config.assert_configured()


def test_assert_configured_accepts_public(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", "@adkar")
    monkeypatch.setattr(config, "PRIVACY_STATUS", "public")
    assert config.assert_configured() is None
