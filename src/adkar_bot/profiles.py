"""Per-channel settings. Everything identical between channels lives in
config.py; only what genuinely differs is here.

Two profiles, both authored in this repo, both changing about never - so
they are literals in a module rather than JSON loaded and validated at
runtime. A typo fails at import, which is the strongest failure mode
available and costs nothing.
"""
from dataclasses import dataclass
from pathlib import Path

from . import config

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Profile:
    name: str
    corpus_path: Path
    state_path: Path
    channel_handle: str
    gradient: tuple[RGB, RGB]   # (top, bottom)
    # A tuple, not a list. The dataclass is frozen, but a mutable default
    # inside it is frozen in name only - one caller appending would corrupt
    # the value for every later caller in the process.
    base_tags: tuple[str, ...]
    hashtags: str               # description footer line
    default_count: int
    env_prefix: str             # credentials are read as f"{env_prefix}_CLIENT_ID" etc.


# Inherits the running channel's exact gradient, count and credential names,
# so the split is provably a no-op for the channel that is already live.
HADITH = Profile(
    name="hadith",
    corpus_path=config.DATA_DIR / "hadith.json",
    state_path=config.DATA_DIR / "state-hadith.json",
    channel_handle="@ZainKhairAllahChannel",
    gradient=((14, 34, 48), (6, 12, 20)),
    base_tags=("حديث", "أحاديث", "صحيح البخاري", "صحيح مسلم", "السنة",
               "hadith", "sunnah", "shorts"),
    hashtags="#shorts #حديث #السنة",
    default_count=6,
    env_prefix="YT",
)

# default_count is 1, not 6: the Hisn corpus is 206 entries, which at 6/day
# cycles in 34 days. At 1/day it lasts ~7 months, which is the runway for
# growing the corpus (Project B) before anything repeats.
ADKAR = Profile(
    name="adkar",
    corpus_path=config.DATA_DIR / "adkar.json",
    state_path=config.DATA_DIR / "state-adkar.json",
    channel_handle="@DIKR-o6k",
    gradient=((16, 44, 34), (6, 18, 14)),
    base_tags=("أذكار", "أدعية", "ذكر", "دعاء", "إسلام",
               "adkar", "dua", "shorts"),
    hashtags="#shorts #أذكار #أدعية",
    default_count=1,
    env_prefix="YT_ADKAR",
)

PROFILES: dict[str, Profile] = {p.name: p for p in (HADITH, ADKAR)}
