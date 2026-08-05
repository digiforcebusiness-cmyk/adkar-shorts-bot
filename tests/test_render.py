import json
import shutil
import subprocess
import pytest
from adkar_bot import config
from adkar_bot.corpus import Dhikr
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


def test_text_never_enters_the_shorts_action_rail():
    """The regression that matters: drawn pixels must stay in the safe box.

    Deliberately not a golden-image comparison — Windows and Ubuntu rasterize
    the same font differently, so byte or per-pixel equality fails in CI for
    reasons unrelated to any real defect. This asserts placement instead,
    which is what actually breaks.
    """
    img = line_overlay(fit(DHIKR.text), index=0)
    alpha = img.getchannel("A")
    box = alpha.getbbox()  # tight bounds of everything drawn
    assert box is not None, "nothing was drawn"
    left, top, right, bottom = box
    assert left >= config.MARGIN_X
    assert right <= config.WIDTH - config.SAFE_RIGHT
    assert top >= config.SAFE_TOP
    assert bottom <= config.HEIGHT - config.SAFE_BOTTOM


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
