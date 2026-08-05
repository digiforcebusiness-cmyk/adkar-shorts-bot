"""Picking a background audio track.

The owner supplies their own recitation files by dropping them into
``config.AUDIO_DIR``; this module never downloads, bundles, or references
any specific recitation. It only chooses among whatever is already there.
"""
import random
from pathlib import Path

from . import config

_EXTENSIONS = (".mp3", ".m4a", ".ogg", ".wav")


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
