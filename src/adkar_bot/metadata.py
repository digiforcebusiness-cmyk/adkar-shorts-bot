from .corpus import Dhikr
from .profiles import Profile

TITLE_LIMIT = 100
SUFFIX = " #shorts"


def _truncate_on_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip() + "…"


def build_title(dhikr: Dhikr) -> str:
    body = _truncate_on_word(dhikr.text.strip(), TITLE_LIMIT - len(SUFFIX))
    return f"{body}{SUFFIX}"


def build_description(dhikr: Dhikr, profile: Profile) -> str:
    return (
        f"{dhikr.text}\n\n"
        f"المصدر: {dhikr.source}\n"
        f"التخريج: {dhikr.reference}\n\n"
        f"{profile.channel_handle}\n"
        f"{profile.hashtags}"
    )


def build_tags(dhikr: Dhikr, profile: Profile) -> list[str]:
    # dict.fromkeys de-duplicates while preserving order, and builds a new
    # list - profile.base_tags is never handed out to a caller.
    return list(dict.fromkeys([*profile.base_tags, dhikr.category]))
