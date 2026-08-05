import pytest
from adkar_bot import config
from adkar_bot.config import ConfigError, assert_configured


def test_frame_is_vertical_1080x1920():
    assert (config.WIDTH, config.HEIGHT) == (1080, 1920)


def test_content_box_excludes_shorts_ui_chrome():
    assert config.CONTENT_W == 1080 - 2 * 96 - 140
    assert config.CONTENT_H == 1920 - config.SAFE_TOP - 280


def test_assert_configured_raises_on_placeholder(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", config.CHANNEL_HANDLE_PLACEHOLDER)
    with pytest.raises(ConfigError, match="CHANNEL_HANDLE"):
        assert_configured()


def test_assert_configured_passes_on_real_handle(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", "@adkar")
    assert assert_configured() is None
