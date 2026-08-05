import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output"

CORPUS_PATH = DATA_DIR / "adkar.json"
STATE_PATH = DATA_DIR / "state.json"
FONT_PATH = ASSETS_DIR / "fonts" / "Amiri-Regular.ttf"

# Frame
WIDTH, HEIGHT = 1080, 1920
MARGIN_X = 96
SAFE_TOP = 220
SAFE_BOTTOM = 280   # Shorts title/description overlay
SAFE_RIGHT = 140    # Shorts action rail
HANDLE_BAND = 90    # reserved strip for the @handle, just above SAFE_BOTTOM
CONTENT_W = WIDTH - 2 * MARGIN_X - SAFE_RIGHT
CONTENT_H = HEIGHT - SAFE_TOP - SAFE_BOTTOM - HANDLE_BAND

# Typography
FONT_MIN, FONT_MAX = 36, 180
LINE_SPACING = 1.6
TEXT_COLOR = (255, 255, 255, 255)
HANDLE_COLOR = (255, 255, 255, 170)
HANDLE_SIZE = 34
GRADIENT_TOP = (14, 34, 48)
GRADIENT_BOTTOM = (6, 12, 20)

# Animation / encode
FPS = 30
CRF = 20
LINE_FADE_D = 0.6
LINE_STAGGER = 0.8
DUR_PER_WORD = 2.2
DUR_MIN, DUR_MAX = 8.0, 30.0

# YouTube
CHANNEL_HANDLE_PLACEHOLDER = "@your-channel"
# GitHub Actions sets an undefined repo variable to "" rather than leaving it
# unset, so os.environ.get(..., default) never sees the default in that case.
# `or` treats "" as falsy and falls through to the placeholder instead.
CHANNEL_HANDLE = os.environ.get("CHANNEL_HANDLE") or CHANNEL_HANDLE_PLACEHOLDER
PRIVACY_STATUS = os.environ.get("PRIVACY_STATUS", "private")
CATEGORY_ID = "22"  # People & Blogs
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class ConfigError(RuntimeError):
    pass


def assert_configured() -> None:
    """Fail loudly rather than publishing cards reading '@your-channel' or blank."""
    if not CHANNEL_HANDLE.strip() or CHANNEL_HANDLE == CHANNEL_HANDLE_PLACEHOLDER:
        raise ConfigError(
            "CHANNEL_HANDLE is not set (placeholder or blank). Set it in "
            "config.py or via the CHANNEL_HANDLE environment variable."
        )
