from adkar_bot import config
from adkar_bot.audio import available_tracks, pick_track


def test_available_tracks_empty_when_dir_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path / "does-not-exist")
    assert available_tracks() == []


def test_available_tracks_empty_when_dir_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    assert available_tracks() == []


def test_available_tracks_sorted_by_name(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    for name in ("c.mp3", "a.wav", "b.ogg"):
        (tmp_path / name).write_bytes(b"")
    assert [p.name for p in available_tracks()] == ["a.wav", "b.ogg", "c.mp3"]


def test_available_tracks_ignores_non_audio_files(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    (tmp_path / "track.mp3").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    (tmp_path / "README.md").write_bytes(b"")
    assert [p.name for p in available_tracks()] == ["track.mp3"]


def test_pick_track_none_with_no_tracks(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    assert pick_track("some-id") is None


def test_pick_track_is_deterministic(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    for name in ("a.mp3", "b.mp3", "c.mp3", "d.mp3"):
        (tmp_path / name).write_bytes(b"")
    assert pick_track("hisn-0001") == pick_track("hisn-0001")


def test_pick_track_varies_by_id(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    for name in ("a.mp3", "b.mp3", "c.mp3", "d.mp3", "e.mp3", "f.mp3"):
        (tmp_path / name).write_bytes(b"")
    choices = {pick_track(f"id-{i}") for i in range(20)}
    assert len(choices) > 1
