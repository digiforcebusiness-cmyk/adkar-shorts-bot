import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config
from .corpus import Dhikr
from .layout import Layout, duration_for, fit


class RenderError(RuntimeError):
    pass


def gradient_background() -> Image.Image:
    """Vertical linear gradient, drawn one row at a time."""
    img = Image.new("RGB", (config.WIDTH, config.HEIGHT))
    draw = ImageDraw.Draw(img)
    top, bottom = config.GRADIENT_TOP, config.GRADIENT_BOTTOM
    for y in range(config.HEIGHT):
        t = y / (config.HEIGHT - 1)
        draw.line(
            [(0, y), (config.WIDTH, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return img


def _block_top(layout: Layout) -> int:
    free = config.CONTENT_H - layout.block_height
    return config.SAFE_TOP + free // 2


def _center_x() -> int:
    return config.MARGIN_X + config.CONTENT_W // 2


def line_overlay(layout: Layout, index: int) -> Image.Image:
    """A full-frame transparent image containing only line `index`."""
    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(config.FONT_PATH), layout.font_size)
    y = _block_top(layout) + index * layout.line_height
    draw.text(
        (_center_x(), y),
        layout.lines[index],
        font=font,
        fill=config.TEXT_COLOR,
        anchor="ma",  # middle-ascender: horizontally centered
    )
    return img


def _handle_layer() -> Image.Image:
    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(config.FONT_PATH), config.HANDLE_SIZE)
    # Above the bottom safe line, not inside it — the Shorts title overlay
    # covers everything below HEIGHT - SAFE_BOTTOM.
    baseline = config.HEIGHT - config.SAFE_BOTTOM - config.HANDLE_SIZE - 24
    draw.text(
        (_center_x(), baseline),
        config.CHANNEL_HANDLE,
        font=font,
        fill=config.HANDLE_COLOR,
        anchor="ma",
    )
    return img


def _filter_complex(n_overlays: int) -> tuple[str, str]:
    """Fade each overlay in on its own schedule, then stack them.

    Returns the filter graph and the label of its final video output.
    """
    parts, prev = [], "0:v"
    for i in range(n_overlays):
        start = i * config.LINE_STAGGER
        parts.append(
            f"[{i + 1}:v]fade=t=in:st={start:.2f}:d={config.LINE_FADE_D}:alpha=1[l{i}]"
        )
        parts.append(f"[{prev}][l{i}]overlay=0:0[v{i}]")
        prev = f"v{i}"
    return ";".join(parts), prev


def render(dhikr: Dhikr, out_path: Path) -> Path:
    layout = fit(dhikr.text)
    duration = duration_for(dhikr.text)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bg = tmp / "bg.png"
        gradient_background().save(bg)

        overlays = []
        for i in range(len(layout.lines)):
            p = tmp / f"line{i}.png"
            line_overlay(layout, i).save(p)
            overlays.append(p)
        handle = tmp / "handle.png"
        _handle_layer().save(handle)
        overlays.append(handle)

        chain, last = _filter_complex(len(overlays))
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{duration}", "-i", str(bg)]
        for p in overlays:
            cmd += ["-loop", "1", "-t", f"{duration}", "-i", str(p)]
        cmd += [
            "-f", "lavfi", "-t", f"{duration}",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-filter_complex", chain,
            "-map", f"[{last}]", "-map", f"{len(overlays) + 1}:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", str(config.FPS), "-crf", str(config.CRF),
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-shortest",
            str(out_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RenderError(f"ffmpeg failed:\n{result.stderr[-2000:]}")

    return out_path
