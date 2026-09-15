from unittest.mock import MagicMock, patch

from adkar_bot import cli
from adkar_bot.profiles import ADKAR, HADITH


def _isolate(monkeypatch, tmp_path, profile):
    """Point a profile's state at a temp file without touching the real one."""
    import dataclasses
    isolated = dataclasses.replace(profile, state_path=tmp_path / "state.json")
    monkeypatch.setitem(cli.PROFILES, profile.name, isolated)
    return isolated


def test_publish_requires_a_profile(tmp_path, monkeypatch):
    """No default: forgetting the flag must not pick a channel for you."""
    monkeypatch.delenv("PROFILE", raising=False)
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish"]) == 2
    fake_render.assert_not_called()


def test_an_unknown_profile_name_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE", "nasai")
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish"]) == 2
    fake_render.assert_not_called()


def test_the_profile_env_var_is_honoured(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path, ADKAR)
    monkeypatch.setenv("PROFILE", "adkar")
    monkeypatch.setattr(cli.config, "OUTPUT_DIR", tmp_path)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4") as fake_render:
        assert cli.main(["render"]) == 0
    assert fake_render.call_args.args[2].name == "adkar"


def test_failed_upload_does_not_consume_an_entry(tmp_path, monkeypatch):
    isolated = _isolate(monkeypatch, tmp_path, HADITH)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel"), \
         patch.object(cli, "upload_video", side_effect=RuntimeError("boom")):
        assert cli.main(["publish", "--profile", "hadith"]) != 0
    assert not isolated.state_path.exists()


def test_publish_fails_cleanly_when_a_secret_is_missing(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.delenv("YT_REFRESH_TOKEN", raising=False)
    assert cli.main(["publish", "--profile", "hadith"]) == 2


def test_each_profile_reads_only_its_own_credentials(tmp_path, monkeypatch):
    """Guard 1. With the hadith credentials present and the adkar ones gone,
    a run of the adkar profile must fail rather than quietly authenticate as
    the other channel."""
    _isolate(monkeypatch, tmp_path, ADKAR)
    monkeypatch.delenv("YT_ADKAR_CLIENT_ID", raising=False)
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish", "--profile", "adkar"]) == 2
    fake_render.assert_not_called()


def test_the_missing_credential_is_named_in_the_error(tmp_path, monkeypatch, caplog):
    _isolate(monkeypatch, tmp_path, ADKAR)
    monkeypatch.delenv("YT_ADKAR_CLIENT_ID", raising=False)
    with caplog.at_level("ERROR"):
        cli.main(["publish", "--profile", "adkar"])
    assert "YT_ADKAR_CLIENT_ID" in caplog.text


def test_publish_checks_secrets_before_rendering(tmp_path, monkeypatch):
    """A misconfigured run must not spend ~20s in ffmpeg first."""
    _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.delenv("YT_CLIENT_ID", raising=False)
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish", "--profile", "hadith"]) == 2
    fake_render.assert_not_called()


def test_the_channel_is_verified_before_anything_is_rendered(tmp_path, monkeypatch):
    """Guard 2 is worth nothing if it fires after 1,600 units are spent."""
    _isolate(monkeypatch, tmp_path, HADITH)
    from adkar_bot.youtube import WrongChannel
    with patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel", side_effect=WrongChannel("nope")), \
         patch.object(cli, "render") as fake_render, \
         patch.object(cli, "upload_video") as fake_upload:
        assert cli.main(["publish", "--profile", "hadith"]) == 1
    fake_render.assert_not_called()
    fake_upload.assert_not_called()


def test_render_does_not_touch_the_network(tmp_path, monkeypatch):
    isolated = _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.setattr(cli.config, "OUTPUT_DIR", tmp_path)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4") as fake_render, \
         patch.object(cli, "build_client") as fake_client, \
         patch.object(cli, "upload_video") as fake_upload:
        assert cli.main(["render", "--profile", "hadith"]) == 0
    fake_render.assert_called_once()
    fake_client.assert_not_called()
    fake_upload.assert_not_called()
    assert not isolated.state_path.exists()   # render never writes state


def test_a_run_writes_only_its_own_profiles_state(tmp_path, monkeypatch):
    adkar = _isolate(monkeypatch, tmp_path / "a", ADKAR)
    hadith = _isolate(monkeypatch, tmp_path / "h", HADITH)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel"), \
         patch.object(cli, "upload_video", return_value="vid1"):
        assert cli.main(["publish", "--profile", "adkar"]) == 0
    assert adkar.state_path.exists()
    assert not hadith.state_path.exists()


def test_publish_logs_the_actual_privacy_status(tmp_path, monkeypatch, caplog):
    """The log line must reflect config.PRIVACY_STATUS, not a hardcoded value."""
    _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.setattr(cli.config, "PRIVACY_STATUS", "unlisted")
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel"), \
         patch.object(cli, "upload_video", return_value="vid1"), \
         caplog.at_level("INFO"):
        assert cli.main(["publish", "--profile", "hadith"]) == 0
    assert "unlisted" in caplog.text
    assert "(private)" not in caplog.text
