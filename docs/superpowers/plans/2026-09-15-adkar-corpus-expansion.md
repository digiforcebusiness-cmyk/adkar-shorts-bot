# Adkar Corpus Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Grow `data/adkar.json` from 206 to roughly 1,100 entries of genuine dhikr and dua, so `@DIKR-o6k` at six uploads a day cycles every ~6 months instead of every 34 days.

**Architecture:** A new `scripts/import_adkar.py` extracts the supplication itself out of hadith across all 17 books of the `hadith-json` dataset, using the compiler's own `"` quotation marks as the boundary so the isnad chain is discarded without anyone deciding where it ends. Helpers shared with the existing hadith importer move into `scripts/_arabic_text.py` rather than being copied. A companion `scripts/review_adkar.py` renders everything extracted for human reading before it publishes.

**Tech Stack:** Python 3.12 standard library only — `json`, `re`, `difflib`, `pathlib`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-15-adkar-corpus-expansion-design.md`

## Global Constraints

- **The 206 existing Hisn al-Muslim entries must survive byte-for-byte.** They are the hand-curated selection; every task must leave them untouched. A test compares them against the pre-run file.
- **Never cut on a guess.** The only cut this project makes is at a `"` the source itself placed. Any entry whose quotes look unreliable — a narration marker surviving inside the quoted span — is dropped, never repaired.
- **All Arabic matching is diacritic-insensitive.** The corpus is fully vocalised; a plain substring search finds almost nothing. This is the trap already documented in `import_hadith.py`, and forgetting it produces an importer that silently yields zero entries.
- **Arabic strings are copied verbatim from this plan.** Do not retype them, do not "fix" spacing, do not reorder. Copy-paste the exact bytes — these ship to a live channel.
- **New ids are prefixed `adkar-`.** `data/adkar.json` and `data/hadith.json` must stay disjoint by id; there is already a test asserting it.
- **Length bounds are 40 and 450 characters**, reusing the measured legibility limits. At 450 the worst-case rendered font size is 41px.
- Run tests with `py -3 -m pytest` — plain `python` is not on PATH, it hits the Microsoft Store shim.
- Python's stdout here is cp1252. Set `PYTHONIOENCODING=utf-8` before any command that prints Arabic, or you get a `UnicodeEncodeError` that is about the terminal, not the code.

## File structure

| File | Responsibility |
| --- | --- |
| `scripts/_arabic_text.py` (new) | Diacritic-insensitive matching, cross-reference detection, whitespace cleaning, the shared length bounds. Used by both importers. |
| `scripts/import_hadith.py` (modify) | Unchanged behaviour; its copies of the shared helpers are replaced by imports. |
| `scripts/import_adkar.py` (new) | Extraction rules, book conversion, deduplication, merge into `data/adkar.json`. |
| `scripts/review_adkar.py` (new) | Renders every extracted entry with its source hadith to `docs/adkar-review.md`. |
| `tests/test_arabic_text.py` (new) | The shared helpers. |
| `tests/test_import_adkar.py` (new) | Extraction, conversion, dedup, and the safety guards. |

---

### Task 1: Shared Arabic-text helpers

**Files:**
- Create: `scripts/_arabic_text.py`
- Create: `tests/test_arabic_text.py`
- Modify: `scripts/import_hadith.py` (lines 27-64: the constants and helpers that move out)

**Interfaces:**
- Consumes: nothing.
- Produces: `flex(phrase: str) -> str`, `bare(text: str) -> str`, `clean(text: str) -> str`, `XREF` (compiled pattern), `MAX_CHARS = 450`, `MIN_CHARS = 40`. Tasks 2-4 import all of these.

**Context an engineer needs:** `scripts/import_hadith.py` currently defines `_DIA`, `flex`, `XREF`, `clean`, `MAX_CHARS` and `MIN_CHARS` itself. `tests/test_import_hadith.py` loads that script by file path with `importlib` and reaches into it for `imp.MATN`, `imp.XREF`, `imp.clean`, `imp.MAX_CHARS`, `imp.MIN_CHARS` — so after the move those names must still resolve as attributes of `import_hadith`. Re-exporting them with `from _arabic_text import ...` does exactly that.

Loading a script by path does not put its directory on `sys.path`, so `import_hadith.py` must add its own directory before importing the shared module, or the existing tests break.

- [ ] **Step 1: Write the failing test**

Create `tests/test_arabic_text.py`:

```python
"""The shared matching helpers. Both importers edit scripture through these,
so a subtly wrong rule here misquotes on two channels instead of one."""
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "_arabic_text",
    Path(__file__).resolve().parents[1] / "scripts" / "_arabic_text.py",
)
at = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(at)


def test_bare_strips_diacritics_without_touching_letters():
    assert at.bare("اللَّهُمَّ") == "اللهم"
    assert at.bare("سُبْحَانَ اللَّهِ") == "سبحان الله"


def test_bare_collapses_whitespace():
    assert at.bare("قَالَ   رَسُولُ\nاللَّهِ") == "قال رسول الله"


def test_bare_is_idempotent():
    once = at.bare("اللَّهُمَّ اغْفِرْ لِي")
    assert at.bare(once) == once


def test_flex_matches_the_same_phrase_however_it_is_vocalised():
    """A plain substring search finds almost nothing in this corpus."""
    import re
    pat = re.compile(at.flex("قال رسول الله"))
    assert pat.search("قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم")


def test_flex_tolerates_extra_spacing_between_words():
    import re
    assert re.compile(at.flex("لا حول ولا قوة")).search("لا  حول   ولا قوة")


@pytest.mark.parametrize("phrase", ["بِهَذَا الإِسْنَادِ", "نَحْوَهُ", "بِمِثْلِهِ"])
def test_cross_reference_stubs_are_detected(phrase):
    assert at.XREF.search(f"وَحَدَّثَنِي عُبَيْدُ اللَّهِ {phrase} .")


def test_clean_strips_bidi_marks_but_keeps_words():
    out = at.clean("قَالَ‏ .‏  رَسُولُ   اللَّهِ")
    assert "‏" not in out
    assert "  " not in out
    assert "قَالَ" in out and "رَسُولُ" in out


def test_length_bounds_are_the_measured_ones():
    """450 is a legibility limit, not a round number - see README section 5."""
    assert at.MAX_CHARS == 450
    assert at.MIN_CHARS == 40
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_arabic_text.py -v`
Expected: FAIL — `FileNotFoundError` on `scripts/_arabic_text.py`.

- [ ] **Step 3: Create the shared module**

Create `scripts/_arabic_text.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_arabic_text.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Point the hadith importer at the shared module**

In `scripts/import_hadith.py`, delete the definitions of `_DIA`, `flex`, `clean`, `XREF`, `MAX_CHARS` and `MIN_CHARS`, and replace the import block at the top with:

```python
import json
import re
import sys
from pathlib import Path

# Loading this file by path (as tests/test_import_hadith.py does) does not put
# its directory on sys.path, so add it before importing the shared helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _arabic_text import MAX_CHARS, MIN_CHARS, XREF, clean, flex  # noqa: E402
```

Leave `MATN`, `BOOKS`, `convert` and `main` exactly as they are. `MATN` is built from `flex(...)` and keeps working unchanged.

- [ ] **Step 6: Verify the hadith importer still behaves identically**

Run: `py -3 -m pytest tests/test_import_hadith.py tests/test_arabic_text.py -v`
Expected: PASS. The existing tests reach into `import_hadith` for `XREF`, `clean`, `MAX_CHARS` and `MIN_CHARS`; the re-export keeps those resolvable.

- [ ] **Step 7: Run the full suite**

Run: `py -3 -m pytest -q`
Expected: PASS at 138 plus the 8 new tests.

- [ ] **Step 8: Commit**

```bash
git add scripts/_arabic_text.py scripts/import_hadith.py tests/test_arabic_text.py
git commit -m "refactor: share the Arabic matching helpers between importers"
```

---

### Task 2: The extraction rule

**Files:**
- Create: `scripts/import_adkar.py`
- Create: `tests/test_import_adkar.py`

**Interfaces:**
- Consumes: `flex`, `bare`, `clean`, `XREF`, `MAX_CHARS`, `MIN_CHARS` from `scripts/_arabic_text.py` (Task 1).
- Produces: `extract(text: str) -> str | None` — the supplication, or `None` if the hadith holds none that can be taken safely. Also `FORMULA`, `NARRATION`, `QUOTE` as module-level compiled patterns. Task 3 calls `extract`.

**Context an engineer needs:** this is the whole safety argument of the project, so read it before writing code. A hadith looks like `حَدَّثَنَا فُلَانٌ، عَنْ فُلَانٍ، أَنَّ رَسُولَ اللَّهِ صلى الله عليه وسلم قَالَ " اللَّهُمَّ اغْفِرْ لِي "` — narrators first, then the Prophet's words inside `"`. Taking the quoted span is what separates the supplication from its chain, and the boundary is the source's, not ours.

57% of the hadith corpus carries a paired quote. Of those, roughly 2.6% contain a dhikr or dua formula. Both of those numbers are measured, not estimated.

- [ ] **Step 1: Write the failing test**

Create `tests/test_import_adkar.py`:

```python
"""Guards on the adkar extractor.

This importer cuts a fragment out of scripture and publishes it alone. A rule
that is slightly wrong does not crash - it puts a truncated supplication on a
channel, six times a day, unreviewed. Every test here pins one of the rules
that stops that.
"""
import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "import_adkar",
    Path(__file__).resolve().parents[1] / "scripts" / "import_adkar.py",
)
ia = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ia)

CHAIN = "حَدَّثَنَا عَلِيُّ بْنُ عَبْدِ اللَّهِ، قَالَ حَدَّثَنَا جَرِيرٌ، عَنْ مَنْصُورٍ، "
DUA = "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ وَالْعَجْزِ وَالْكَسَلِ وَالْبُخْلِ"


def test_the_supplication_is_taken_and_the_chain_is_left_behind():
    text = f'{CHAIN}أَنَّ النَّبِيَّ صلى الله عليه وسلم قَالَ " {DUA} "'
    out = ia.extract(text)
    assert out is not None
    assert out.startswith("اللَّهُمَّ")
    assert "حَدَّثَنَا" not in out
    assert "جَرِيرٌ" not in out


def test_a_hadith_with_no_quote_yields_nothing():
    """No quote means no boundary the source drew, and we never invent one."""
    assert ia.extract(f"{CHAIN}كَانَ النَّبِيُّ صلى الله عليه وسلم يَقُولُ {DUA}") is None


def test_a_quote_without_a_supplication_yields_nothing():
    text = f'{CHAIN}قَالَ " إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى "'
    assert ia.extract(text) is None


def test_a_quote_that_still_holds_a_narration_marker_is_dropped():
    """A correctly quoted span cannot contain one. If it does, the quotation
    marks were unreliable for that entry - drop it rather than repair it."""
    text = f'قَالَ " {DUA} حَدَّثَنَا مُوسَى عَنْ نَافِعٍ وَقَالَ اللَّهُمَّ بَارِكْ "'
    assert ia.extract(text) is None


def test_a_cross_reference_stub_is_dropped():
    text = f'قَالَ " {DUA} بِهَذَا الإِسْنَادِ "'
    assert ia.extract(text) is None


def test_too_short_and_too_long_are_both_rejected():
    assert ia.extract('قَالَ " اللَّهُمَّ "') is None            # under 40
    long = "اللَّهُمَّ " + ("اغْفِرْ لِي وَارْحَمْنِي " * 40)
    assert len(long) > ia.MAX_CHARS
    assert ia.extract(f'قَالَ " {long} "') is None


def test_matching_ignores_diacritics():
    """The corpus is fully vocalised. A bare pattern must still find the
    vocalised form, or this importer silently yields nothing at all."""
    assert ia.FORMULA.search("اللَّهُمَّ اغْفِرْ لِي وَارْحَمْنِي")
    assert ia.FORMULA.search("سُبْحَانَ اللَّهِ وَبِحَمْدِهِ")


def test_both_dhikr_and_dua_families_are_recognised():
    dhikr = "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ سُبْحَانَ اللَّهِ الْعَظِيمِ وَالْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"
    assert ia.extract(f'قَالَ " {dhikr} "') is not None
    assert ia.extract(f'قَالَ " {DUA} "') is not None


def test_only_the_first_qualifying_segment_is_taken():
    """Several quoted passages means a narrative with dialogue, which is what
    this importer exists to exclude - so we never concatenate them."""
    second = "اللَّهُمَّ رَبَّنَا لَكَ الْحَمْدُ مِلْءَ السَّمَاوَاتِ وَمِلْءَ الأَرْضِ وَمَا بَيْنَهُمَا"
    out = ia.extract(f'قَالَ " {DUA} " ثُمَّ قَالَ " {second} "')
    assert out is not None
    assert second not in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_import_adkar.py -v`
Expected: FAIL — `FileNotFoundError` on `scripts/import_adkar.py`.

- [ ] **Step 3: Write the extractor**

Create `scripts/import_adkar.py`:

```python
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
```

Note the two `return None` rather than `continue`: once a segment qualifies on
its formula, a narration marker or a bad length is a signal about *this*
hadith, and hunting for a later segment that happens to pass would be exactly
the guessing the module docstring forbids.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_import_adkar.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 5: Sanity-check against the real corpus**

```bash
PYTHONIOENCODING=utf-8 py -3 -c "
import json, importlib.util
from pathlib import Path
s = importlib.util.spec_from_file_location('ia', 'scripts/import_adkar.py')
ia = importlib.util.module_from_spec(s); s.loader.exec_module(ia)
items = json.load(open('data/hadith.json', encoding='utf-8'))
got = [ia.extract(i['text']) for i in items]
got = [g for g in got if g]
print(f'extracted {len(got)} of {len(items)}')
for g in got[:3]: print(' -', g[:90])
"
```

Expected: roughly 180-210 extracted from 7,682, and each printed line should read as a supplication with no narrator names. If it prints 0, the diacritic handling is wrong — that is the failure mode the docstring warns about.

- [ ] **Step 6: Commit**

```bash
git add scripts/import_adkar.py tests/test_import_adkar.py
git commit -m "feat: extract supplications from hadith at the source's own quote boundary"
```

---

### Task 3: Book conversion

**Files:**
- Modify: `scripts/import_adkar.py` (append `convert_book`)
- Modify: `tests/test_import_adkar.py` (append conversion tests)

**Interfaces:**
- Consumes: `extract` (Task 2).
- Produces: `convert_book(path: Path) -> tuple[list[dict], dict]` — entries and a stats dict with keys `total`, `no_text`, `no_dua`, `kept`. Task 4 calls it once per book file.

**Context an engineer needs:** every book file in the dataset has the same shape, verified against `nawawi40.json`:

```json
{
  "id": 1,
  "metadata": {"arabic": {"title": "الأربعون النووية", "author": "..."}},
  "chapters": [{"id": 0, "arabic": "الأربعون النووية"}],
  "hadiths": [{"idInBook": 1, "chapterId": 0, "arabic": "عَنْ أَمِيرِ..."}]
}
```

`metadata.arabic.title` is the book's Arabic name, so no map of 17 hardcoded titles is needed. The slug for ids comes from the filename stem.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_import_adkar.py`:

```python
import json


def _book(tmp_path, name, hadiths, title="صحيح البخاري"):
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps({
        "id": 1,
        "metadata": {"arabic": {"title": title, "author": "فلان"}},
        "chapters": [{"id": 1, "arabic": "كتاب الدعوات"}],
        "hadiths": hadiths,
    }, ensure_ascii=False), encoding="utf-8")
    return p


def test_convert_book_builds_entries_with_adkar_prefixed_ids(tmp_path):
    p = _book(tmp_path, "bukhari", [
        {"idInBook": 141, "chapterId": 1,
         "arabic": f'{CHAIN}قَالَ " {DUA} "'},
    ])
    entries, stats = ia.convert_book(p)
    assert len(entries) == 1
    e = entries[0]
    assert e["id"] == "adkar-bukhari-00141"
    assert e["source"] == "صحيح البخاري"
    assert e["reference"] == "صحيح البخاري 141"
    assert e["category"] == "كتاب الدعوات"
    assert e["text"].startswith("اللَّهُمَّ")
    assert stats["kept"] == 1


def test_convert_book_skips_hadith_with_no_supplication(tmp_path):
    p = _book(tmp_path, "bukhari", [
        {"idInBook": 1, "chapterId": 1,
         "arabic": f'{CHAIN}قَالَ " إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ وَإِنَّمَا لِكُلِّ امْرِئٍ مَا نَوَى "'},
        {"idInBook": 2, "chapterId": 1, "arabic": f'قَالَ " {DUA} "'},
    ])
    entries, stats = ia.convert_book(p)
    assert [e["id"] for e in entries] == ["adkar-bukhari-00002"]
    assert stats["total"] == 2
    assert stats["no_dua"] == 1


def test_convert_book_skips_hadith_with_empty_text(tmp_path):
    p = _book(tmp_path, "bukhari", [
        {"idInBook": 1, "chapterId": 1, "arabic": ""},
        {"idInBook": 2, "chapterId": 1, "arabic": f'قَالَ " {DUA} "'},
    ])
    entries, stats = ia.convert_book(p)
    assert len(entries) == 1
    assert stats["no_text"] == 1


def test_convert_book_falls_back_to_the_book_title_for_an_unknown_chapter(tmp_path):
    p = _book(tmp_path, "nawawi40", [
        {"idInBook": 7, "chapterId": 999, "arabic": f'قَادَ " {DUA} "'.replace("قَادَ", "قَالَ")},
    ], title="الأربعون النووية")
    entries, _ = ia.convert_book(p)
    assert entries[0]["category"] == "الأربعون النووية"


def test_every_produced_entry_has_the_five_required_fields(tmp_path):
    """corpus.py rejects an entry missing any of these, and it rejects the
    whole file - one bad entry would take the channel down, not just itself."""
    p = _book(tmp_path, "muslim", [
        {"idInBook": 9, "chapterId": 1, "arabic": f'قَالَ " {DUA} "'},
    ], title="صحيح مسلم")
    entries, _ = ia.convert_book(p)
    for field in ("id", "text", "category", "source", "reference"):
        assert isinstance(entries[0][field], str) and entries[0][field].strip()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_import_adkar.py -v`
Expected: FAIL — `AttributeError: module 'import_adkar' has no attribute 'convert_book'`.

- [ ] **Step 3: Write `convert_book`**

Append to `scripts/import_adkar.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_import_adkar.py -v`
Expected: PASS, 14 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/import_adkar.py tests/test_import_adkar.py
git commit -m "feat: convert a hadith book into adkar entries"
```

---

### Task 4: Deduplication and merge

**Files:**
- Modify: `scripts/import_adkar.py` (append `dedupe` and `main`)
- Modify: `tests/test_import_adkar.py` (append dedup and guard tests)

**Interfaces:**
- Consumes: `convert_book` (Task 3), `bare` (Task 1).
- Produces: `dedupe(candidates: list[dict], existing: list[dict]) -> list[dict]`, `SOURCE_RANK: dict[str, int]`, `MIN_NEW_ENTRIES = 400`, `main(argv) -> int`.

**Context an engineer needs:** the same supplication appears across many books — Hisn al-Muslim's own references routinely cite two or three. Unmerged, the channel repeats itself within a week while appearing to hold a thousand entries. Measured within Bukhari and Muslim alone the collapse rate is 11%; across all 17 it will be higher, because the Sunan restate the two Sahihs heavily.

`difflib.SequenceMatcher.ratio()` over every pair would be ~600,000 comparisons. `real_quick_ratio()` is an upper bound computed from length alone, so calling it first and skipping anything already below the threshold removes nearly all of them.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_import_adkar.py`:

```python
def _entry(eid, text, source="صحيح البخاري"):
    return {"id": eid, "text": text, "category": "كتاب الدعوات",
            "source": source, "reference": f"{source} 1"}


def test_near_duplicates_collapse_to_one():
    a = _entry("adkar-bukhari-00001", DUA)
    b = _entry("adkar-abudawud-00002", DUA + " وَالْجُبْنِ", "سنن أبي داود")
    out = ia.dedupe([a, b], [])
    assert len(out) == 1


def test_the_stronger_source_survives_a_merge():
    """Whatever ends up on screen should carry the best attribution available."""
    weak = _entry("adkar-ibnmajah-00002", DUA, "سنن ابن ماجه")
    strong = _entry("adkar-bukhari-00001", DUA, "صحيح البخاري")
    assert ia.dedupe([weak, strong], [])[0]["source"] == "صحيح البخاري"
    assert ia.dedupe([strong, weak], [])[0]["source"] == "صحيح البخاري"


def test_distinct_supplications_are_both_kept():
    a = _entry("adkar-bukhari-00001", DUA)
    b = _entry("adkar-muslim-00002",
               "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ سُبْحَانَ اللَّهِ الْعَظِيمِ وَالْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ")
    assert len(ia.dedupe([a, b], [])) == 2


def test_a_candidate_matching_an_existing_hisn_entry_is_dropped():
    """The 206 hand-curated entries always win; they carry an occasion in
    `category` that an extracted entry cannot."""
    existing = [_entry("hisn-0001", DUA, "حصن المسلم")]
    assert ia.dedupe([_entry("adkar-bukhari-00001", DUA)], existing) == []


def test_dedupe_ignores_diacritic_differences():
    plain = "اللهم اغفر لي وارحمني واهدني وعافني وارزقني وتب علي انك انت التواب الرحيم"
    voweled = "اللَّهُمَّ اغْفِرْ لِي وَارْحَمْنِي وَاهْدِنِي وَعَافِنِي وَارْزُقْنِي وَتُبْ عَلَىَّ إِنَّكَ أَنْتَ التَّوَّابُ الرَّحِيمُ"
    out = ia.dedupe([_entry("adkar-bukhari-00001", plain),
                     _entry("adkar-muslim-00002", voweled, "صحيح مسلم")], [])
    assert len(out) == 1


def test_main_refuses_to_write_a_suspiciously_thin_corpus(tmp_path, monkeypatch, capsys):
    """A large silent drop means a source format change or a broken pattern.
    Overwriting a good corpus with a thin one is the failure that would reach
    the channel unnoticed."""
    target = tmp_path / "adkar.json"
    target.write_text(json.dumps([_entry("hisn-0001", DUA, "حصن المسلم")],
                                 ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(ia, "ADKAR", target)
    src = tmp_path / "books"
    src.mkdir()
    _book(src, "bukhari", [{"idInBook": 1, "chapterId": 1,
                            "arabic": f'قَالَ " {DUA} وَالْجُبْنِ وَالْهَرَمِ "'}])
    assert ia.main(["import_adkar.py", str(src)]) == 1
    assert "refusing" in capsys.readouterr().out.lower()
    assert json.loads(target.read_text(encoding="utf-8"))[0]["id"] == "hisn-0001"


def test_main_reports_usage_when_given_no_source(capsys):
    assert ia.main(["import_adkar.py"]) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_import_adkar.py -v`
Expected: FAIL — `AttributeError: module 'import_adkar' has no attribute 'dedupe'`.

- [ ] **Step 3: Write `dedupe` and `main`**

Append to `scripts/import_adkar.py`, and add `from difflib import SequenceMatcher` to the imports:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_import_adkar.py -v`
Expected: PASS, 21 tests.

- [ ] **Step 5: Run the full suite**

Run: `py -3 -m pytest -q`
Expected: PASS. Nothing outside these two new files has changed.

- [ ] **Step 6: Commit**

```bash
git add scripts/import_adkar.py tests/test_import_adkar.py
git commit -m "feat: merge near-duplicate supplications and guard a thin harvest"
```

---

### Task 5: The review document, and running the import

**Files:**
- Create: `scripts/review_adkar.py`
- Modify: `README.md` (section 5, "The corpus")
- Data: rewrites `data/adkar.json`; creates `docs/adkar-review.md`

**Interfaces:**
- Consumes: the finished `data/adkar.json`.
- Produces: `docs/adkar-review.md`. Nothing in the publish path reads it.

**Context an engineer needs:** this task actually runs the import, which needs the source dataset. Clone it first:

```bash
git clone --depth 1 https://github.com/AhmedBaset/hadith-json.git /tmp/hadith-json
```

The books live under `/tmp/hadith-json/db/by_book/` in three subdirectories (`the_9_books`, `other_books`, `forties`), which is why `main` uses `rglob`.

- [ ] **Step 1: Write the review script**

Create `scripts/review_adkar.py`:

```python
"""Render every extracted adkar entry for reading, before any of it publishes.

Run:  py -3 scripts/review_adkar.py

Writes docs/adkar-review.md. Nothing in the publish path reads it - it exists
because this corpus is machine-extracted from a text that has never been
checked against a printed, scholarly-reviewed edition, and a mis-paired
quotation mark in the source becomes a truncated supplication published six
times a day. The extractor's rules catch malformed quotes, but they are
heuristics, not a scholar. Reading the output once is the only real defence.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADKAR = ROOT / "data" / "adkar.json"
OUT = ROOT / "docs" / "adkar-review.md"


def main(argv=None) -> int:
    entries = json.loads(ADKAR.read_text(encoding="utf-8"))
    extracted = [e for e in entries if e["id"].startswith("adkar-")]
    curated = [e for e in entries if not e["id"].startswith("adkar-")]

    lines = [
        "# Adkar corpus — review copy",
        "",
        f"{len(entries)} entries: {len(curated)} hand-curated "
        f"(Hisn al-Muslim), {len(extracted)} machine-extracted.",
        "",
        "Only the machine-extracted entries are listed below. Read each one and",
        "check it stands alone as a supplication: no dangling conjunction, no",
        "half sentence, no narrator's name. Anything wrong should be deleted",
        "from `data/adkar.json` by its id.",
        "",
    ]
    by_source: dict[str, list[dict]] = {}
    for e in extracted:
        by_source.setdefault(e["source"], []).append(e)

    for source in sorted(by_source, key=lambda s: -len(by_source[s])):
        group = by_source[source]
        lines += [f"## {source} ({len(group)})", ""]
        for e in group:
            lines += [f"- **`{e['id']}`** · {e['reference']} · {e['category']}",
                      f"  > {e['text']}", ""]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(extracted)} entries to review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 2: Clone the source dataset**

```bash
git clone --depth 1 https://github.com/AhmedBaset/hadith-json.git /tmp/hadith-json
ls /tmp/hadith-json/db/by_book/
```

Expected: three directories — `forties`, `other_books`, `the_9_books`.

- [ ] **Step 3: Record the pre-import state**

```bash
cd /g/adkar-shorts-bot
git status --short
PYTHONIOENCODING=utf-8 py -3 -c "
import json; d=json.load(open('data/adkar.json',encoding='utf-8'))
print('before:', len(d), 'entries,', sum(1 for e in d if e['id'].startswith('hisn-')), 'hisn')"
```

Expected: a clean tree, `before: 206 entries, 206 hisn`. If the tree is not clean, commit or stash first — the next step rewrites a data file and you want a clean diff.

- [ ] **Step 4: Run the import**

```bash
PYTHONIOENCODING=utf-8 py -3 scripts/import_adkar.py /tmp/hadith-json/db/by_book
```

Expected: a per-book table, then a corpus line showing 206 growing to roughly 1,000-1,200, and a months-per-repeat figure around 5-7.

If it prints `refusing to write`, stop and report: the harvest came in under 400 and the corpus is deliberately unchanged. Do not lower `MIN_NEW_ENTRIES` to get past it.

- [ ] **Step 5: Verify the result**

```bash
PYTHONIOENCODING=utf-8 py -3 -c "
import json, sys
sys.path.insert(0, 'src')
from adkar_bot.corpus import load_corpus
from adkar_bot.profiles import ADKAR, HADITH
c = load_corpus(ADKAR.corpus_path)
print('loads under corpus.py:', len(c), 'entries')
d = json.load(open('data/adkar.json', encoding='utf-8'))
hisn = [e for e in d if e['id'].startswith('hisn-')]
print('hisn entries still present:', len(hisn))
ids = {e['id'] for e in d}
hids = {e['id'] for e in json.load(open('data/hadith.json', encoding='utf-8'))}
print('disjoint from hadith corpus:', ids.isdisjoint(hids))
print('all new ids prefixed:', all(e['id'].startswith(('adkar-','hisn-')) for e in d))
"
git diff --stat data/adkar.json
```

Expected: loads cleanly, `hisn entries still present: 206`, disjoint `True`, prefixed `True`.

- [ ] **Step 6: Confirm the curated 206 are byte-identical**

```bash
PYTHONIOENCODING=utf-8 py -3 -c "
import json, subprocess
old = json.loads(subprocess.run(['git','show','HEAD:data/adkar.json'],
                                capture_output=True).stdout.decode('utf-8'))
new = json.load(open('data/adkar.json', encoding='utf-8'))
o = {e['id']: json.dumps(e, sort_keys=True, ensure_ascii=False) for e in old}
n = {e['id']: json.dumps(e, sort_keys=True, ensure_ascii=False) for e in new}
print('every original entry unchanged:', all(n.get(k) == v for k, v in o.items()))
print('originals:', len(o), '-> total now:', len(n))
"
```

Expected: `every original entry unchanged: True`. If False, stop — the importer modified curated content, which it must never do.

- [ ] **Step 7: Generate the review document**

```bash
PYTHONIOENCODING=utf-8 py -3 scripts/review_adkar.py
head -40 docs/adkar-review.md
```

Expected: the file is written and the first entries read as standalone supplications.

- [ ] **Step 8: Run the full suite**

Run: `py -3 -m pytest -q`
Expected: PASS. Note the layout tests now walk a much larger adkar corpus, so the suite takes longer than before; that is expected, let it finish. A failure in `test_every_adkar_corpus_entry_lays_out` means an extracted entry does not fit the frame — report it rather than widening the layout.

- [ ] **Step 9: Update the README**

In `README.md` section 5, replace the paragraph describing `data/adkar.json` as 206 Hisn al-Muslim entries with the new composition: the 206 curated entries plus the machine-extracted supplications, the total, and the months-per-repeat figure the importer printed. Add a short paragraph stating that `scripts/import_adkar.py` extracts only the text inside the source's own quotation marks and drops anything whose quoted span still contains a narration marker, and that `scripts/review_adkar.py` regenerates the review copy. Keep the three hadith-importer rules and the "Still outstanding" caveat verbatim — they are unchanged and still true.

- [ ] **Step 10: Commit**

```bash
git add scripts/review_adkar.py data/adkar.json docs/adkar-review.md README.md
git commit -m "feat: grow the adkar corpus with extracted supplications"
```

---

## After the plan

The corpus is in place but **not yet read by a human**. `docs/adkar-review.md` exists for that, and it is the only defence against a mis-paired quotation mark in the source becoming a truncated supplication on the channel. Delete any bad entry from `data/adkar.json` by its id and re-run `scripts/review_adkar.py`.

Once the corpus is reviewed, raise `ADKAR_PUBLISH_COUNT` from `1` to `6` — that cadence is what this work exists to support.
