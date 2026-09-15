import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output"

FONT_PATH = ASSETS_DIR / "fonts" / "Amiri-Regular.ttf"
AUDIO_DIR = ASSETS_DIR / "audio"

# Frame
WIDTH, HEIGHT = 1080, 1920
MARGIN_X = 96
SAFE_TOP = 220
SAFE_BOTTOM = 280   # Shorts title/description overlay
SAFE_RIGHT = 140    # Shorts action rail
# Reserved strip below the text for the call-to-action line and the @handle.
# Widened from 90 when the CTA was added: it sits above the handle, so the
# content box has to give up the same height or long adkar overlap it.
HANDLE_BAND = 140
CONTENT_W = WIDTH - 2 * MARGIN_X - SAFE_RIGHT
CONTENT_H = HEIGHT - SAFE_TOP - SAFE_BOTTOM - HANDLE_BAND

# Typography
FONT_MIN, FONT_MAX = 36, 180
LINE_SPACING = 1.6
TEXT_COLOR = (255, 255, 255, 255)
HANDLE_COLOR = (255, 255, 255, 170)
HANDLE_SIZE = 34
# Call to action, rendered just above the handle. Arabic, so it must be run
# through arabic.shape() before drawing like every other Arabic string here.
LIKE_TEXT = "اضغط لايك فالدال على الخير كفاعله"
LIKE_SIZE = 30
LIKE_COLOR = (255, 255, 255, 150)

# Animation / encode
FPS = 30
CRF = 20
LINE_FADE_D = 0.6
LINE_STAGGER = 0.8
DUR_PER_WORD = 2.2
DUR_MIN, DUR_MAX = 8.0, 30.0

# Background audio
AUDIO_FADE = 1.5    # seconds of fade in and out
AUDIO_VOLUME = 0.35  # background level, so text remains the focus
BED_VOLUME = 0.8     # generated ambient bed. Higher than AUDIO_VOLUME because
                     # amix divides gain across its inputs, so the synthesized
                     # drone arrives far quieter than a mastered recording.
                     # At 0.18 it measured -44 dB mean and was inaudible on a
                     # phone; 0.8 lands near -30 dB, comparable to a user file.

# YouTube
# `or` not a get() default: GitHub Actions sets an undefined repository
# variable to "" rather than leaving it unset, and os.environ.get(name,
# default) never sees its default in that case. An empty privacyStatus is
# rejected by the API.
VALID_PRIVACY = ("public", "unlisted", "private")
PRIVACY_STATUS = os.environ.get("PRIVACY_STATUS") or "private"
# Validated in assert_configured(), not here: ConfigError is defined below, so
# raising at module level would be a NameError in the very path meant to fail.
# How many adkar one publish run uploads.
#
# The YouTube Data API grants 10,000 units/day and videos.insert costs 1,600,
# so six uploads is the hard ceiling on the default quota - the seventh comes
# back quotaExceeded. Kept as arithmetic on the two real numbers rather than a
# bare 6 so the reason survives if either ever changes.
DAILY_QUOTA_UNITS = 10_000
UPLOAD_COST_UNITS = 1_600
MAX_UPLOADS_PER_DAY = DAILY_QUOTA_UNITS // UPLOAD_COST_UNITS
CATEGORY_ID = "22"  # People & Blogs
# youtube.readonly is needed by channels.list, which verify_channel uses to
# confirm the refresh token belongs to the profile's channel before spending
# 1,600 quota units uploading to the wrong one. Adding it invalidates every
# refresh token minted under the old scope list: both channels must re-run
# scripts/authorize.py once. See the migration notes in the README.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class ConfigError(RuntimeError):
    pass


def assert_configured(profile) -> None:
    """Fail loudly rather than publishing a run that cannot succeed."""
    if profile.default_count < 1:
        raise ConfigError(
            f"profile {profile.name!r} has an upload count of "
            f"{profile.default_count}; must be a whole number of 1 or more."
        )
    if PRIVACY_STATUS not in VALID_PRIVACY:
        raise ConfigError(
            f"PRIVACY_STATUS is {PRIVACY_STATUS!r}; must be one of "
            f"{VALID_PRIVACY}. An undefined GitHub repository variable arrives "
            f"as an empty string, which the API rejects."
        )
