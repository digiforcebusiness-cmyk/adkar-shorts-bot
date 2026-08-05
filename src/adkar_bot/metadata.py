from . import config
from .corpus import Dhikr

TITLE_LIMIT = 100
SUFFIX = " #shorts"
BASE_TAGS = ["أذكار", "أدعية", "ذكر", "دعاء", "إسلام", "adkar", "dua", "shorts"]


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


def build_description(dhikr: Dhikr) -> str:
    return (
        f"{dhikr.text}\n\n"
        f"المصدر: {dhikr.source}\n"
        f"التخريج: {dhikr.reference}\n\n"
        f"{config.CHANNEL_HANDLE}\n"
        f"#shorts #أذكار #أدعية"
    )


def build_tags(dhikr: Dhikr) -> list[str]:
    return list(dict.fromkeys([*BASE_TAGS, dhikr.category]))


def build_comment(dhikr: Dhikr) -> str:
    return f"{dhikr.text}\n\n{dhikr.source} — {dhikr.reference}"
