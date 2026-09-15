"""Build the adkar corpus by extracting supplications out of the hadith books.

Run:  py -3 scripts/import_adkar.py <dir-with-hadith-json-db/by_book>

Source: github.com/AhmedBaset/hadith-json (the text is public domain; the
compilation states no licence).

This is the opposite of scripts/import_hadith.py. That importer preserves the
narration and cuts only at an explicit speech marker; this one discards the
narration entirely and keeps the supplication alone, because a channel of
adkar should show the dua, not four narrators in front of it.

The cut is never ours. The compiler delimits the Prophet's words with " and
that span is what gets taken - the same never-cut-on-a-guess rule the hadith
importer follows. An entry whose quoted span still contains a narration
marker is dropped rather than repaired: the quotes were unreliable there, and
repairing would mean inventing a boundary.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _arabic_text import (  # noqa: E402
    MAX_CHARS, MIN_CHARS, XREF, bare, clean, flex,
)

ROOT = Path(__file__).resolve().parents[1]
ADKAR = ROOT / "data" / "adkar.json"

# Remembrance formulas: praise, not petition.
DHIKR_FORMULAS = (
    "سبحان", "الحمد لله", "لا إله إلا الله", "الله أكبر", "بسم الله",
    "أستغفر", "لا حول ولا قوة", "تبارك", "اللهم صل",
)
# Supplication formulas: petition. A list covering only one family misses
# roughly a quarter of the material - measured, not guessed.
DUA_FORMULAS = (
    "اللهم", "ربنا", "أعوذ", "أسألك", "أسأل الله", "رب اغفر", "رب زدني",
)
FORMULA = re.compile("|".join(flex(p) for p in DHIKR_FORMULAS + DUA_FORMULAS))

# A correctly quoted span holds none of these. Their presence means the
# quotation marks did not delimit what we assumed.
NARRATION = re.compile(r"(?:(?<=\s)|^)(?:" + "|".join(flex(p) for p in (
    "حدثنا", "حدثني", "أخبرنا", "أخبرني", "أنبأنا", "سمعت", "عن أبيه",
)) + ")")

QUOTE = re.compile(r'"\s*(.+?)\s*"', re.S)


def extract(text: str) -> str | None:
    """The supplication inside `text`, or None if none can be taken safely."""
    for match in QUOTE.finditer(text):
        segment = clean(match.group(1))
        if not FORMULA.search(segment):
            continue
        if NARRATION.search(segment) or XREF.search(segment):
            return None
        if not (MIN_CHARS <= len(segment) <= MAX_CHARS):
            return None
        return segment
    return None


def convert_book(path: Path) -> tuple[list[dict], dict]:
    """Every supplication this book yields, plus a count of what was skipped.

    The book's Arabic title comes from its own metadata rather than a map of
    seventeen hardcoded names, so adding a book needs no code change.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    title = data["metadata"]["arabic"]["title"]
    slug = path.stem
    chapters = {c["id"]: c["arabic"] for c in data.get("chapters", [])}

    out, stats = [], {"total": 0, "no_text": 0, "no_dua": 0, "kept": 0}
    for h in data.get("hadiths", []):
        stats["total"] += 1
        text = clean(h.get("arabic", ""))
        if not text:
            stats["no_text"] += 1
            continue
        segment = extract(text)
        if segment is None:
            stats["no_dua"] += 1
            continue
        out.append({
            "id": f"adkar-{slug}-{h['idInBook']:05d}",
            "text": segment,
            "category": chapters.get(h["chapterId"], title),
            "source": title,
            "reference": f"{title} {h['idInBook']}",
        })
        stats["kept"] += 1
    return out, stats
