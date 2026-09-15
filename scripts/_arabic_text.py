"""Arabic matching helpers shared by the two corpus importers.

Both importers edit scripture. These rules are the part most likely to be
subtly wrong in a way that does not crash - it publishes a misquotation,
automatically, every day. They live in one place so a fix cannot land in one
importer and miss the other.
"""
import re

# Combining marks, the tatweel, and the Qur'anic annotation range.
_DIA_CLASS = r"ً-ْٰـۖ-ۭ"
_DIA = f"[{_DIA_CLASS}]*"
_DIA_ONE = re.compile(f"[{_DIA_CLASS}]")

# Longest text that still renders at a readable size. Measured, not guessed:
# at 450 characters the worst case fit is 41px and the median 72px; allowing
# 500 buys more content but drags the floor down to 38px.
MAX_CHARS = 450
MIN_CHARS = 40


def flex(phrase: str) -> str:
    """A pattern matching `phrase` however it happens to be vocalised.

    The corpus is fully diacritised and the marks vary between editions, so a
    plain substring search finds almost nothing.
    """
    out = []
    for ch in phrase:
        out.append(r"\s+" if ch == " " else re.escape(ch) + _DIA)
    return "".join(out)


def bare(text: str) -> str:
    """Diacritics removed and whitespace collapsed, for comparing two texts.

    `flex` builds a pattern for searching; this normalises a whole string so
    two vocalisations of the same words compare equal. Deduplication needs
    that - the same dua is diacritised differently in different books.
    """
    return re.sub(r"\s+", " ", _DIA_ONE.sub("", text)).strip()


def clean(text: str) -> str:
    """Drop bidi control marks and collapse whitespace. No words are changed."""
    return re.sub(r"\s+", " ", text.replace("‏", "")).strip()


XREF = re.compile("|".join(flex(p) for p in (
    "بهذا الاسناد", "بهذا الإسناد", "نحوه", "مثله", "بمثله", "بنحوه",
)))
