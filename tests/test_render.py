import json
import shutil
import subprocess
import pytest
from adkar_bot import config
from adkar_bot.corpus import Dhikr, load_corpus
from adkar_bot.render import gradient_background, line_overlay, render
from adkar_bot.layout import fit

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
    assert gradient_background().size == (config.WIDTH, config.HEIGHT)


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
    """
    for dhikr in load_corpus(config.CORPUS_PATH):
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
        assert y1 <= config.HEIGHT - config.SAFE_BOTTOM, f"{dhikr.id} overflows bottom"


def test_overlay_rendering_is_deterministic():
    layout = fit(DHIKR.text)
    assert line_overlay(layout, 0).tobytes() == line_overlay(layout, 0).tobytes()


def test_render_produces_a_valid_short(tmp_path):
    out = render(DHIKR, tmp_path / "out.mp4")
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
