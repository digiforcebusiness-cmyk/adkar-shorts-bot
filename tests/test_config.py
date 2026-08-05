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
