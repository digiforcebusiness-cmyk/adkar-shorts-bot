import json
import shutil
import subprocess
import pytest
from conftest import corpus_sample
from adkar_bot import config
from adkar_bot.corpus import Dhikr, load_corpus
from adkar_bot.profiles import ADKAR, HADITH
from adkar_bot.render import gradient_background, line_overlay, render
from adkar_bot.layout import duration_for, fit

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)

DHIKR = Dhikr(
    id="t1", text="لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ",
    category="dhikr", source="متفق عليه", reference="البخاري ٦٤٠٩",
)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def test_gradient_is_frame_sized():
    assert gradient_background(HADITH).size == (config.WIDTH, config.HEIGHT)


def test_each_profile_paints_its_own_gradient():
    """The two channels have to be tellable apart at a glance."""
    a = gradient_background(ADKAR).getpixel((540, 100))
    h = gradient_background(HADITH).getpixel((540, 100))
    assert a != h


def test_the_gradient_top_row_is_the_profiles_top_colour():
    """Guards the orientation: a flipped gradient still differs between
    profiles, so the test above would pass while the frame was upside down."""
    assert gradient_background(HADITH).getpixel((0, 0)) == HADITH.gradient[0]
    assert gradient_background(ADKAR).getpixel((0, 0)) == ADKAR.gradient[0]


def test_line_overlay_is_frame_sized_and_transparent():
    img = line_overlay(fit(DHIKR.text), index=0)
    assert img.size == (config.WIDTH, config.HEIGHT)
    assert img.mode == "RGBA"
    assert img.getpixel((5, 5))[3] == 0


def test_no_corpus_entry_draws_outside_the_safe_box():
    """Every entry, every line, all ink inside the box.

    The single-fixture version of this test passed while 4 of 12 real
    entries overflowed, because layout measured advance width rather than
    painted ink.

    The bottom bound is the handle's top edge, not the outer SAFE_BOTTOM
    line: that's the actual invariant HANDLE_BAND exists to protect. The
    outer line is 58px slacker and would not catch text drawn over the
    handle.
    """
    handle_top = config.HEIGHT - config.SAFE_BOTTOM - config.HANDLE_SIZE - 24
    for dhikr in corpus_sample():
        layout = fit(dhikr.text)
        box = None
        for i in range(len(layout.lines)):
            b = line_overlay(layout, i).getchannel("A").getbbox()
            if b is None:
                continue
            box = b if box is None else (
                min(box[0], b[0]), min(box[1], b[1]),
                max(box[2], b[2]), max(box[3], b[3]),
            )
        x0, y0, x1, y1 = box
        assert x0 >= config.MARGIN_X, f"{dhikr.id} overflows left"
        assert x1 <= config.WIDTH - config.SAFE_RIGHT, f"{dhikr.id} overflows right"
        assert y0 >= config.SAFE_TOP, f"{dhikr.id} overflows top"
        assert y1 <= handle_top, f"{dhikr.id} overflows into the handle band"


def test_overlay_rendering_is_deterministic():
    layout = fit(DHIKR.text)
    assert line_overlay(layout, 0).tobytes() == line_overlay(layout, 0).tobytes()


def test_render_produces_a_valid_short(tmp_path):
    out = render(DHIKR, tmp_path / "out.mp4", HADITH)
    info = probe(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")

    assert (video["width"], video["height"]) == (1080, 1920)
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    assert audio["codec_name"] == "aac"

    duration = float(info["format"]["duration"])
    assert config.DUR_MIN - 1 <= duration <= config.DUR_MAX + 1
    assert duration <= 180  # Shorts hard limit


def test_last_line_finishes_fading_before_the_clip_ends():
    """Nothing today truncates the last line's fade-in, but nothing checks
    it either: it holds only by construction. A change to LINE_STAGGER or
    DUR_MAX could silently cut the animation short for a longer entry.
    """
    for dhikr in corpus_sample():
        layout = fit(dhikr.text)
        duration = duration_for(dhikr.text)
        last_line_fade_end = (
            (len(layout.lines) - 1) * config.LINE_STAGGER + config.LINE_FADE_D
        )
        assert last_line_fade_end <= duration, f"{dhikr.id} fade overruns clip"


def _make_tone(path, seconds):
    """A synthetic sine tone standing in for a real recitation file.

    Never a real recitation — background audio is the owner's own file, and
    nothing generated here is ever committed (tmp_path only).
    """
    result = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}",
         "-c:a", "pcm_s16le", str(path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]


def _audio_stream_duration(info):
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    if "duration" in audio:
        return float(audio["duration"])
    return float(info["format"]["duration"])


def _mean_volume(path):
    result = subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    for line in result.stderr.splitlines():
        if "mean_volume" in line:
            return float(line.strip().split(":")[-1].replace("dB", "").strip())
    raise AssertionError(f"no mean_volume in ffmpeg output:\n{result.stderr}")


def _extract_pcm(path, out_wav):
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-vn", "-acodec", "pcm_s16le",
         "-ar", "44100", "-ac", "1", str(out_wav)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return out_wav.read_bytes()


def test_render_without_any_audio_files_falls_back_to_a_generated_bed(tmp_path, monkeypatch):
    """No files in assets/audio/ -> a synthesized ambient bed now plays
    instead of silence. This is the behaviour change: the track used to be
    genuinely silent (anullsrc) whenever no user file existed; now a
    generated bed is the default and anullsrc is only the last resort.
    """
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path / "empty-audio-dir")

    out = render(DHIKR, tmp_path / "out.mp4", HADITH)
    info = probe(out)
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert audio["codec_name"] == "aac"
    assert _mean_volume(out) > -60.0


def test_different_dhikr_get_audibly_different_generated_beds(tmp_path, monkeypatch):
    """Two different dhikr, both with no user audio, must not end up with
    the same background bed -- compare decoded PCM, not MP4 container
    bytes (which would differ trivially from encode-timestamp noise even
    for identical audio).
    """
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path / "empty-audio-dir")
    other = Dhikr(
        id="t2", text="سُبْحَانَ اللَّهِ وَبِحَمْدِهِ",
        category="dhikr", source="متفق عليه", reference="مسلم ٢٦٩٢",
    )

    out1 = render(DHIKR, tmp_path / "out1.mp4", HADITH)
    out2 = render(other, tmp_path / "out2.mp4", HADITH)

    pcm1 = _extract_pcm(out1, tmp_path / "a1.wav")
    pcm2 = _extract_pcm(out2, tmp_path / "a2.wav")
    assert pcm1 != pcm2


def test_render_with_a_background_track_does_not_extend_the_clip(tmp_path, monkeypatch):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    _make_tone(audio_dir / "tone.wav", 40)  # longer than DUR_MAX
    monkeypatch.setattr(config, "AUDIO_DIR", audio_dir)

    out = render(DHIKR, tmp_path / "out.mp4", HADITH)
    info = probe(out)
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert audio["codec_name"] == "aac"

    video_duration = float(
        next(s for s in info["streams"] if s["codec_type"] == "video")["duration"]
    )
    audio_duration = _audio_stream_duration(info)
    assert audio_duration == pytest.approx(video_duration, abs=0.5)


def test_render_loops_a_track_shorter_than_the_video(tmp_path, monkeypatch):
    """A 2s tone under a clip that is at least DUR_MIN=8s must not leave the
    tail silent: the track has to loop, not just play once and stop.
    """
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    _make_tone(audio_dir / "short.wav", 2)
    monkeypatch.setattr(config, "AUDIO_DIR", audio_dir)

    out = render(DHIKR, tmp_path / "out.mp4", HADITH)
    info = probe(out)
    video_duration = float(
        next(s for s in info["streams"] if s["codec_type"] == "video")["duration"]
    )
    audio_duration = _audio_stream_duration(info)
    assert video_duration >= config.DUR_MIN
    assert audio_duration == pytest.approx(video_duration, abs=0.5)
    assert audio_duration > 2.5  # spans the full clip, not just the source tone
