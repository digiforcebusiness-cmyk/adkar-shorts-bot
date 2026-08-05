"""Picking or generating a background audio bed.

The owner may supply their own recitation files by dropping them into
``config.AUDIO_DIR``; this module never downloads, bundles, or references
any specific recitation for that path. It only chooses among whatever is
already there.

When no user file exists, `build_bed` synthesizes an ambient drone from
scratch with ffmpeg's `lavfi` sources. Recitation recordings are
performances with their own copyright even though the Qur'an's text is
not, and free sources are either NonCommercial-licensed or carry
unverifiable public-domain claims — neither can be redistributed safely on
an automated channel. A synthesized bed has no third-party rights attached
at all, so it's the only background audio that can be generated safely
without a human vetting each file.
"""
import random
import subprocess
from pathlib import Path

from . import config

_EXTENSIONS = (".mp3", ".m4a", ".ogg", ".wav")

# Low, musically related root frequencies (roughly 110-220 Hz -- the A2-A3
# range) that sit comfortably under spoken/read text without buzzing.
_ROOTS = (110.0, 123.47, 130.81, 146.83, 164.81, 174.61, 196.00, 220.00)
# Consonant intervals above the root: perfect fourth, perfect fifth, octave.
_INTERVALS = (1.3333, 1.5, 2.0)


class AudioError(RuntimeError):
    pass


def available_tracks() -> list[Path]:
    """Audio files in config.AUDIO_DIR, sorted by name for determinism.

    Returns an empty list when the directory is missing or empty.
    """
    if not config.AUDIO_DIR.is_dir():
        return []
    return sorted(
        (p for p in config.AUDIO_DIR.iterdir()
         if p.is_file() and p.suffix.lower() in _EXTENSIONS),
        key=lambda p: p.name,
    )


def pick_track(dhikr_id: str) -> Path | None:
    """Deterministically choose a track for `dhikr_id`.

    Seeded by dhikr_id so the same dhikr always gets the same track and
    reruns are reproducible. Returns None when no tracks exist.
    """
    tracks = available_tracks()
    if not tracks:
        return None
    return random.Random(dhikr_id).choice(tracks)


def bed_params(dhikr_id: str) -> dict:
    """Deterministic synthesis parameters for `dhikr_id`'s ambient bed.

    Seeded by dhikr_id (independently of `pick_track`'s own RNG use) so the
    same dhikr always renders the same bed, while different ids audibly
    differ: root frequency, the harmonic interval stacked above it, and a
    slow tremolo rate/depth.
    """
    rng = random.Random(f"bed:{dhikr_id}")
    root = rng.choice(_ROOTS)
    interval = rng.choice(_INTERVALS)
    return {
        "root": root,
        "interval": interval,
        "third_octave": rng.choice((True, False)),
        "tremolo_rate": round(rng.uniform(0.1, 0.4), 3),
        "tremolo_depth": round(rng.uniform(0.15, 0.4), 3),
        "lowpass_hz": rng.randint(500, 900),
    }


def build_bed(dhikr_id: str, duration: float, out_path: Path) -> Path:
    """Synthesize a `duration`-second ambient drone WAV for `dhikr_id`.

    Layers two or three sine drones (root, a harmonic interval above it,
    and optionally that root an octave up) with `amix`, applies a slow
    tremolo so the bed breathes rather than droning flatly, and a gentle
    lowpass so it stays soft. Raises `AudioError` on ffmpeg failure rather
    than returning a broken or partial file.
    """
    p = bed_params(dhikr_id)
    freqs = [p["root"], p["root"] * p["interval"]]
    if p["third_octave"]:
        freqs.append(p["root"] * 2)

    out_path = Path(out_path)
    inputs = []
    for f in freqs:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f:.3f}:duration={duration}"]

    mix_inputs = "".join(f"[{i}:a]" for i in range(len(freqs)))
    filter_complex = (
        f"{mix_inputs}amix=inputs={len(freqs)}:duration=longest:dropout_transition=0,"
        f"tremolo=f={p['tremolo_rate']}:d={p['tremolo_depth']},"
        f"lowpass=f={p['lowpass_hz']}"
        "[aout]"
    )

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-t", f"{duration}",
        "-ar", "44100", "-ac", "2",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AudioError(f"ffmpeg failed to synthesize bed:\n{result.stderr[-2000:]}")
    return out_path
