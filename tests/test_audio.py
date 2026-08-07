import shutil
import subprocess

import pytest

from adkar_bot import config
from adkar_bot.audio import available_tracks, bed_params, build_bed, pick_track
from adkar_bot.corpus import load_corpus

pytestmark_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


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


def test_pick_track_prefers_user_file_over_none(tmp_path, monkeypatch):
    """A user-supplied file must still win even though generated beds now
    exist as a fallback: pick_track itself never reaches for a bed, it
    only ever returns a real file or None, and a user file makes that
    None impossible.
    """
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    (tmp_path / "user-recitation.mp3").write_bytes(b"")
    result = pick_track("hisn-0001")
    assert result is not None
    assert result.name == "user-recitation.mp3"


def test_bed_params_is_deterministic():
    assert bed_params("hisn-0001") == bed_params("hisn-0001")


def test_bed_params_varies_across_corpus_ids():
    """Across the real corpus ids, several distinct root frequencies appear.

    If they all collide the seed derivation is broken -- e.g. reusing
    pick_track's RNG stream, or not actually keying off dhikr_id.

    Deliberately does not assert the corpus size: this is an audio test, and
    pinning the entry count here made it fail for an unrelated reason the
    moment the corpus grew.
    """
    ids = [d.id for d in load_corpus(config.CORPUS_PATH)]
    assert len(ids) >= 12, "corpus unexpectedly small; other tests cover its size"
    roots = {bed_params(i)["root"] for i in ids}
    assert len(roots) > 1


def test_bed_params_yields_reasonable_ranges():
    for i in range(20):
        p = bed_params(f"id-{i}")
        assert 110.0 <= p["root"] <= 220.0
        assert 0.1 <= p["tremolo_rate"] <= 0.4


@pytestmark_ffmpeg
def test_build_bed_matches_requested_duration(tmp_path):
    out = build_bed("hisn-0001", 7.3, tmp_path / "bed.wav")
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    )
    assert abs(float(result.stdout.strip()) - 7.3) < 0.1


def _mean_volume(path):
    result = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    for line in result.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.strip().split(":")[-1].replace("dB", "").strip())
    raise AssertionError(f"no mean_volume in ffmpeg output:\n{result.stderr}")


@pytestmark_ffmpeg
def test_build_bed_is_not_silent(tmp_path):
    out = build_bed("hisn-0002", 5.0, tmp_path / "bed.wav")
    # A truly silent file reports -91 dB (or -inf); a real drone sits well
    # above that.
    assert _mean_volume(out) > -60.0
