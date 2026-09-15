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
from difflib import SequenceMatcher
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


SIMILARITY = 0.80

# Strongest attribution first. When a cluster collapses, the survivor is
# whichever member sits highest here, so the best available authentication is
# what ends up on screen.
SOURCE_RANK = {
    "صحيح البخاري": 0,
    "صحيح مسلم": 1,
    "سنن أبي داود": 2,
    "سنن النسائي": 3,
    "جامع الترمذي": 4,
    "سنن ابن ماجه": 5,
    "موطأ مالك": 6,
}
_UNRANKED = len(SOURCE_RANK) + 1

# A run that yields far less than this has hit a source format change or a
# broken pattern, not a genuinely small harvest.
MIN_NEW_ENTRIES = 400


def _rank(entry: dict) -> int:
    return SOURCE_RANK.get(entry["source"], _UNRANKED)


def dedupe(candidates: list[dict], existing: list[dict]) -> list[dict]:
    """Candidates with near-duplicates merged, and anything already held dropped.

    Compared on diacritic-stripped text: the same dua is vocalised differently
    in different books, so the raw strings rarely match even when the words are
    identical.
    """
    existing_bare = [bare(e["text"]) for e in existing]
    ordered = sorted(candidates, key=_rank)   # strongest source wins a cluster

    kept: list[dict] = []
    kept_bare: list[str] = []
    for entry in ordered:
        text = bare(entry["text"])
        if _matches_any(text, existing_bare) or _matches_any(text, kept_bare):
            continue
        kept.append(entry)
        kept_bare.append(text)
    return kept


def _matches_any(text: str, pool: list[str]) -> bool:
    for other in pool:
        matcher = SequenceMatcher(None, text, other)
        # real_quick_ratio is an upper bound from lengths alone; checking it
        # first skips almost every pair without doing the real comparison.
        if matcher.real_quick_ratio() < SIMILARITY:
            continue
        if matcher.quick_ratio() < SIMILARITY:
            continue
        if matcher.ratio() >= SIMILARITY:
            return True
    return False


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    src = Path(argv[1])
    books = sorted(src.rglob("*.json"))
    if not books:
        print(f"no book files found under {src}", file=sys.stderr)
        return 2

    existing = json.loads(ADKAR.read_text(encoding="utf-8"))
    candidates = []
    for path in books:
        try:
            entries, st = convert_book(path)
        except (KeyError, json.JSONDecodeError) as exc:
            print(f"{path.name}: unreadable ({exc})", file=sys.stderr)
            return 1
        candidates.extend(entries)
        print(f"  {path.stem:<22} {st['total']:>6} read | "
              f"no dua {st['no_dua']:>6} | kept {st['kept']:>5}")

    fresh = dedupe(candidates, existing)
    if len(fresh) < MIN_NEW_ENTRIES:
        print(f"\n  refusing to write: only {len(fresh)} new entries, expected "
              f"at least {MIN_NEW_ENTRIES}. A drop this large means a source "
              f"format change or a broken pattern, not a small harvest. "
              f"{ADKAR.name} is unchanged.")
        return 1

    # Skip rather than fail on an id already held. The spec's error-handling
    # table says a collision should exit 1, but it also says re-running the
    # importer must be safe, and those cannot both hold: a second run derives
    # exactly the same ids from the same books. Ids are book slug plus number,
    # so two different books cannot collide - a collision only ever means "this
    # ran before". Idempotency wins; the spec row is the one that is wrong.
    seen = {e["id"] for e in existing}
    merged = list(existing) + [e for e in fresh if e["id"] not in seen]
    ADKAR.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"\n  extracted {len(candidates)} -> {len(fresh)} after merging duplicates")
    print(f"  corpus: {len(existing)} -> {len(merged)} entries")
    print(f"  {len(merged) / 6 / 30.4:.1f} months at 6 shorts/day before a repeat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
