from unittest.mock import MagicMock, patch
from adkar_bot import cli
from adkar_bot.selector import State, load_state


def test_failed_upload_does_not_consume_an_entry(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(cli.config, "STATE_PATH", state_path)
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE", "@adkar")

    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "upload_video", side_effect=RuntimeError("boom")):
        assert cli.main(["publish"]) != 0

    assert not state_path.exists()


def test_comment_failure_still_persists_state(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(cli.config, "STATE_PATH", state_path)
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE", "@adkar")

    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "upload_video", return_value="vid42"), \
         patch.object(cli, "post_comment", side_effect=RuntimeError("nope")):
        assert cli.main(["publish"]) == 0

    state = load_state(state_path)
    assert len(state.used) == 1
    assert state.published[0]["video_id"] == "vid42"


def test_publish_refuses_placeholder_handle(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE",
                        cli.config.CHANNEL_HANDLE_PLACEHOLDER)
    assert cli.main(["publish"]) != 0


def test_publish_fails_cleanly_when_a_secret_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE", "@adkar")
    monkeypatch.delenv("YT_REFRESH_TOKEN", raising=False)

    assert cli.main(["publish"]) == 2   # ConfigError exit code, not a crash


def test_publish_checks_secrets_before_rendering(tmp_path, monkeypatch):
    """A misconfigured run must not spend ~20s in ffmpeg first."""
    monkeypatch.setattr(cli.config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE", "@adkar")
    monkeypatch.delenv("YT_CLIENT_ID", raising=False)

    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish"]) == 2
    fake_render.assert_not_called()


def test_render_does_not_touch_the_network(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cli.config, "OUTPUT_DIR", tmp_path)

    with patch.object(cli, "render", return_value=tmp_path / "v.mp4") as fake_render, \
         patch.object(cli, "build_client") as fake_client, \
         patch.object(cli, "upload_video") as fake_upload:
        assert cli.main(["render"]) == 0

    fake_render.assert_called_once()
    fake_client.assert_not_called()
    fake_upload.assert_not_called()
    assert not (tmp_path / "state.json").exists()   # render never writes state
