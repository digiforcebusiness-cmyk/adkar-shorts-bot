import logging
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config
from .audio import AudioError, build_bed, pick_track
from .arabic import shape
from .corpus import Dhikr
from .layout import Layout, duration_for, fit, load_font
from .profiles import Profile

log = logging.getLogger("adkar_bot")


class RenderError(RuntimeError):
    pass


def gradient_background(profile: Profile) -> Image.Image:
    """Vertical linear gradient, drawn one row at a time."""
    img = Image.new("RGB", (config.WIDTH, config.HEIGHT))
    draw = ImageDraw.Draw(img)
    top, bottom = profile.gradient
    for y in range(config.HEIGHT):
        t = y / (config.HEIGHT - 1)
        draw.line(
            [(0, y), (config.WIDTH, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return img


def _center_x() -> int:
    return config.MARGIN_X + config.CONTENT_W // 2


def _origin(layout: Layout) -> tuple[int, int]:
    """Draw origin such that the block's ink lands centered in the content box."""
    left = config.MARGIN_X + (config.CONTENT_W - layout.ink_w) // 2
    top = config.SAFE_TOP + (config.CONTENT_H - layout.ink_h) // 2
    return left - layout.ink_dx, top - layout.ink_dy


def line_overlay(layout: Layout, index: int) -> Image.Image:
    """A full-frame transparent image containing only line `index`."""
    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(layout.font_size)
    origin_x, origin_y = _origin(layout)
    draw.text(
        (origin_x, origin_y + index * layout.line_height),
        layout.lines[index],
        font=font,
        fill=config.TEXT_COLOR,
        anchor="ma",  # middle-ascender: horizontally centered
    )
    return img


def _handle_layer(profile: Profile) -> Image.Image:
    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(config.HANDLE_SIZE)
    # Above the bottom safe line, not inside it — the Shorts title overlay
    # covers everything below HEIGHT - SAFE_BOTTOM.
    baseline = config.HEIGHT - config.SAFE_BOTTOM - config.HANDLE_SIZE - 24
    draw.text(
        (_center_x(), baseline),
        profile.channel_handle,
        font=font,
        fill=config.HANDLE_COLOR,
        anchor="ma",
    )

    # Call to action above the handle. shape() is required: the text is Arabic
    # and the fonts load with Layout.BASIC, which does no joining of its own.
    like_font = load_font(config.LIKE_SIZE)
    draw.text(
        (_center_x(), baseline - config.LIKE_SIZE - 10),
        shape(config.LIKE_TEXT),
        font=like_font,
        fill=config.LIKE_COLOR,
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


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def _audio_filter(duration: float, volume: float = config.AUDIO_VOLUME) -> str:
    """Trim/fade/attenuate a background track to exactly `duration` seconds.

    Kept separate from `_filter_complex` (the video overlay graph) — the two
    are independent sub-graphs joined only at the ffmpeg command line, never
    sharing a label or a builder function.

    `volume` defaults to the user-file level; the generated ambient bed
    passes `config.BED_VOLUME` instead, since a synthetic drone under
    religious text should be quieter than a deliberately chosen recitation.
    """
    fade_out_start = max(duration - config.AUDIO_FADE, 0.0)
    return (
        f"atrim=0:{duration},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={config.AUDIO_FADE},"
        f"afade=t=out:st={fade_out_start:.3f}:d={config.AUDIO_FADE},"
        f"volume={volume}"
    )


def render(dhikr: Dhikr, out_path: Path, profile: Profile) -> Path:
    layout = fit(dhikr.text)
    duration = duration_for(dhikr.text)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    track = pick_track(dhikr.id)
    volume = config.AUDIO_VOLUME

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bg = tmp / "bg.png"
        gradient_background(profile).save(bg)

        overlays = []
        for i in range(len(layout.lines)):
            p = tmp / f"line{i}.png"
            line_overlay(layout, i).save(p)
            overlays.append(p)
        handle = tmp / "handle.png"
        _handle_layer(profile).save(handle)
        overlays.append(handle)

        if track is None:
            # No user-supplied recitation: synthesize a unique ambient bed
            # instead of dropping straight to silence. A synthesized drone
            # carries no third-party rights, unlike a recitation recording,
            # so it's the only background audio that can be generated
            # automatically. Written into this render's own temp dir, never
            # into assets/audio/ (that folder belongs to the user). If
            # synthesis itself fails, fall back further to silence rather
            # than letting the whole render die over background audio.
            try:
                track = build_bed(dhikr.id, duration, tmp / "bed.wav")
                volume = config.BED_VOLUME
            except AudioError as exc:
                log.warning(
                    "bed synthesis failed for %s, falling back to silence: %s",
                    dhikr.id, exc,
                )

        video_chain, last = _filter_complex(len(overlays))
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{duration}", "-i", str(bg)]
        for p in overlays:
            cmd += ["-loop", "1", "-t", f"{duration}", "-i", str(p)]

        audio_input_index = len(overlays) + 1
        if track is not None:
            # Loop the track only if it's shorter than the clip, so it never
            # runs dry mid-video; atrim below cuts it back to `duration`
            # regardless of whether it was looped.
            loop_opts = (
                ["-stream_loop", "-1"]
                if _probe_duration(track) < duration
                else []
            )
            cmd += loop_opts + ["-i", str(track)]
            audio_chain = (
                f"[{audio_input_index}:a]{_audio_filter(duration, volume)}[aout]"
            )
            chain = f"{video_chain};{audio_chain}"
            audio_map = "[aout]"
        else:
            cmd += [
                "-f", "lavfi", "-t", f"{duration}",
                "-i", "anullsrc=r=44100:cl=stereo",
            ]
            chain = video_chain
            audio_map = f"{audio_input_index}:a"

        cmd += [
            "-filter_complex", chain,
            "-map", f"[{last}]", "-map", audio_map,
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
