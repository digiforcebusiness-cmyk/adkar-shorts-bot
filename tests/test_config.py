import pytest
from adkar_bot import config
from adkar_bot.profiles import HADITH


def test_frame_is_vertical_1080x1920():
    assert (config.WIDTH, config.HEIGHT) == (1080, 1920)


def test_content_box_excludes_shorts_ui_chrome():
    assert config.CONTENT_W == 1080 - 2 * 96 - 140
    # HANDLE_BAND, not a literal: the band grew when the like CTA was
    # added above the handle, and the box must give up exactly that much.
    assert config.CONTENT_H == (
        1920 - config.SAFE_TOP - 280 - config.HANDLE_BAND
    )


def test_content_box_leaves_room_for_the_handle():
    """The text block must never reach the handle's band.

    Without HANDLE_BAND the content box ran to the bottom safe line and the
    tallest cards drew the duaa straight over the @handle — 8 of 12 corpus
    entries did exactly that before this was reserved.
    """
    text_bottom = config.SAFE_TOP + config.CONTENT_H
    handle_top = config.HEIGHT - config.SAFE_BOTTOM - config.HANDLE_SIZE - 24
    assert text_bottom < handle_top


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
    monkeypatch.setattr(config, "PRIVACY_STATUS", "publik")
    with pytest.raises(config.ConfigError, match="PRIVACY_STATUS"):
        config.assert_configured(HADITH)


def test_assert_configured_accepts_public(monkeypatch):
    monkeypatch.setattr(config, "PRIVACY_STATUS", "public")
    assert config.assert_configured(HADITH) is None


def test_assert_configured_rejects_a_count_below_one():
    import dataclasses
    with pytest.raises(config.ConfigError, match="count"):
        config.assert_configured(dataclasses.replace(HADITH, default_count=0))
