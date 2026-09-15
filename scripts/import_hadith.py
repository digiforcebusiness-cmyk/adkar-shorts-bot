"""Build the corpus from Sahih al-Bukhari and Sahih Muslim.

Run:  py scripts/import_hadith.py <dir-with-bukhari.json-and-muslim.json>

Source: github.com/AhmedBaset/hadith-json (the hadith text itself is a
9th-century public-domain work; the compilation carries no stated licence).

Two rules govern what lands in the corpus, both about not misquoting:

1. An entry is only shortened when it says, in so many words, that the Prophet
   spoke - "قال رسول الله صلى الله عليه وسلم" and its close variants. Then the
   text is cut to start at that phrase, so what remains is the saying plus its
   own introduction. Every other entry is copied verbatim, chain and all.
   Nothing is ever cut on a guess.
2. Entries that only point at another hadith's chain ("بهذا الإسناد", "نحوه")
   are dropped: standalone they carry no content to read.
"""
import json
import re
import sys
from pathlib import Path

# Loading this file by path (as tests/test_import_hadith.py does) does not put
# its directory on sys.path, so add it before importing the shared helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _arabic_text import MAX_CHARS, MIN_CHARS, XREF, clean, flex  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# The hadith corpus, not data/adkar.json: since the two-channel split, the
# adkar file holds only Hisn al-Muslim and this importer never touches it.
HADITH = ROOT / "data" / "hadith.json"

# Kept deliberately narrow. Each one names the Prophet and a verb of speech,
# which is what makes the cut safe.
# The leading (?<=\s)|^ is load-bearing. Without it "ان رسول الله" matches the
# tail of وَكَانَ and the cut lands mid-word, producing "انَ رسول الله" - broken
# Arabic that misquotes the text. A marker must begin its own word.
MATN = re.compile(r"(?:(?<=\s)|^)(?:" + "|".join(flex(p) for p in (
    "قال رسول الله صلى الله عليه وسلم",
    "قال النبي صلى الله عليه وسلم",
    "أن رسول الله صلى الله عليه وسلم",
    "ان رسول الله صلى الله عليه وسلم",
)) + ")")

BOOKS = {"bukhari": ("صحيح البخاري", "bukhari"),
         "muslim": ("صحيح مسلم", "muslim")}


def convert(path: Path, key: str) -> tuple[list[dict], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    title, slug = BOOKS[key]
    chapters = {c["id"]: c["arabic"] for c in data["chapters"]}

    out, stats = [], {"total": 0, "xref": 0, "long": 0, "short": 0, "matn": 0}
    for h in data["hadiths"]:
        stats["total"] += 1
        text = clean(h.get("arabic", ""))
        if not text:
            continue
        if XREF.search(text):
            stats["xref"] += 1
            continue

        m = MATN.search(text)
        if m:
            text = text[m.start():]
            stats["matn"] += 1

        if len(text) > MAX_CHARS:
            stats["long"] += 1
            continue
        if len(text) < MIN_CHARS:
            stats["short"] += 1
            continue

        out.append({
            "id": f"{slug}-{h['idInBook']:05d}",
            "text": text,
            "category": chapters.get(h["chapterId"], title),
            "source": title,
            "reference": f"{title} {h['idInBook']}",
        })
    return out, stats


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    src = Path(argv[1])

    existing = json.loads(HADITH.read_text(encoding="utf-8"))
    merged = list(existing)
    seen = {e["id"] for e in merged}

    for key in BOOKS:
        entries, st = convert(src / f"{key}.json", key)
        kept = 0
        for e in entries:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            merged.append(e)
            kept += 1
        print(f"  {key:<8} {st['total']:>5} read | xref {st['xref']:>4} "
              f"| too long {st['long']:>4} | shortened {st['matn']:>4} "
              f"| kept {kept:>5}")

    HADITH.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"\n  corpus: {len(existing)} -> {len(merged)} entries")
    print(f"  {len(merged) / 10 / 365:.2f} years at 10 shorts/day")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
