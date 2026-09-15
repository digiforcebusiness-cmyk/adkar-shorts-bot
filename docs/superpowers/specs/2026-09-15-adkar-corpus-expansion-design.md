# Adkar Corpus Expansion — Design

**Date:** 2026-09-15
**Status:** Approved
**Follows:** `2026-09-15-two-channel-split-design.md`, which named this work
"Project B" and deliberately left it out of scope.

## Purpose

`data/adkar.json` holds 206 entries. At the `adkar` profile's six uploads a
day that is 34 days before the rotation cycles and `@DIKR-o6k` begins
republishing. This project grows it to roughly 1,100 entries of genuine
dhikr and dua, which pushes the first repeat out to about six months.

## What this is not

**It is not three years of content.** The original request was three years at
six a day — 6,570 entries. That target is unreachable, and the reason is the
material rather than the method:

- Measured across the 7,682 Bukhari and Muslim hadith already in the repo,
  199 quoted segments contain a dhikr or dua formula. That is 2.6%.
- Projected across all 17 books in the source dataset (50,884 hadith), and
  after merging near-duplicates, the ceiling is roughly 900 entries, plus the
  206 already held.
- Al-Nawawi's *al-Adhkar* and *al-Kalim al-Tayyib* were named as sources in
  the earlier spec. Neither exists in a machine-readable edition. Searching
  turns up only Hisn al-Muslim derivatives, which is what the 206 already are.

Six months at six a day was accepted in preference to diluting the channel
with narrative hadith to reach a longer cycle. That trade is the whole point
of the design below: precision over volume.

## Success criteria

1. Every entry added is a supplication or a remembrance formula. No
   narratives, no rulings, no biography.
2. No entry carries an isnad chain.
3. No two entries in the corpus are near-duplicates of each other.
4. The 206 existing Hisn al-Muslim entries are byte-for-byte unchanged.
5. The resulting file loads under `corpus.py`'s existing validator, and
   `data/adkar.json` and `data/hadith.json` remain disjoint by id.

## Non-goals

Qur'anic supplications as a source (a separate body of text with different
citation conventions). Translations or transliteration. Reaching three years.
Any change to the hadith channel, the render pipeline, or the publish path.

## Why a separate importer

`scripts/import_hadith.py` and the new `scripts/import_adkar.py` apply
opposite rules to the same source data, and merging them would mean one
script with a mode flag that inverts its own central invariant:

| | `import_hadith.py` | `import_adkar.py` |
| --- | --- | --- |
| The narration chain | preserved verbatim; only cut at an explicit speech marker | discarded entirely |
| What an entry is | the hadith as transmitted | the supplication alone |
| Selection | everything that passes the length and cross-reference filters | only text containing a dhikr or dua formula |

They share the diacritic-insensitive matching problem and the
cross-reference rejection. Those two pieces move to a small shared module,
`scripts/_arabic_text.py`, rather than being copied — the `flex()` helper in
particular carries a subtle correctness fix (a marker must begin its own
word) that must not be allowed to diverge between two copies.

## Extraction

### The boundary is the source's, not ours

The compiler delimits the Prophet's words with `"`. 57% of the hadith corpus
carries a paired quote. Taking that span is what separates the supplication
from its chain, and it is not a judgement call — the same principle as
`import_hadith.py`'s refusal to cut anywhere but at an explicit marker.

A segment is kept only if all of the following hold:

1. It lies between paired `"` marks.
2. It contains a **dhikr formula** — سبحان، الحمد لله، لا إله إلا الله،
   الله أكبر، بسم الله، استغفر، لا حول ولا قوة، تبارك، اللهم صل — **or** a
   **dua formula** — اللهم، ربنا، أعوذ، أسألك، أسأل الله، رب اغفر، رب زدني.
   Both families are in scope; they are different kinds of text and a list
   covering only one misses roughly a quarter of the material.
3. Its length is 40–450 characters, reusing the bounds already measured for
   legibility: at 450 the worst-case font size is 41px.
4. It contains **no** narration marker — حدثنا، أخبرنا، أنبأنا، عن فلان. A
   correctly quoted segment cannot contain one. If it does, the quotation
   marks were unreliable for that entry, and it is dropped rather than
   guessed at.
5. It is not a cross-reference stub (بهذا الإسناد، نحوه، مثله), reusing the
   existing `XREF` pattern.

All matching is diacritic-insensitive. The corpus is fully vocalised and a
plain substring search finds almost nothing — this is the trap already
documented in `import_hadith.py`, and the reason `flex()` exists.

Only the first qualifying segment in a hadith is taken. A hadith containing
several quoted passages is a narrative with dialogue, which is what this
importer exists to exclude.

### Sources

All 17 books from `AhmedBaset/hadith-json`, the dataset already used for the
hadith corpus: the nine books, Riyad as-Salihin, al-Adab al-Mufrad, Bulugh
al-Maram, Mishkat al-Masabih, Shamail al-Muhammadiyah, and the three Forty
collections. The importer takes a directory and processes every `*.json` it
recognises, so adding a book later needs no code change.

Licence status is unchanged from the existing corpus and unchanged by this
work: the text is public domain, the compilation states no licence.

### Identity and metadata

| Field | Value |
| --- | --- |
| `id` | `adkar-<book-slug>-<number>`, e.g. `adkar-bukhari-00141` |
| `text` | the extracted segment |
| `source` | the book's Arabic name, e.g. `صحيح البخاري` |
| `reference` | book name plus number in book, as the hadith importer does |
| `category` | the hadith's chapter (`كتاب الوضوء`) |

The `adkar-` prefix keeps the two corpora provably disjoint. There is already
a test asserting that disjointness, and without the prefix an extracted
Bukhari supplication would collide with the full hadith of the same number.

`category` is the honest fallback. The existing Hisn entries carry an
*occasion* there (`أَذْكَارُ الِاسْتِيقَاظِ مِنَ النَّوْمِ`), which is far
better for a channel of adkar, but an occasion cannot be derived from a
hadith's chapter without inventing it. Chapter is what the source actually
supports, and the field feeds a YouTube tag, not the video itself.

### Deduplication

The same supplication appears across many books — Hisn al-Muslim's own
references routinely cite two or three. Unmerged, the channel would repeat
itself within a week while appearing to hold a thousand entries.

Near-duplicates are merged above 80% similarity on diacritic-stripped,
whitespace-collapsed text. Measured within Bukhari and Muslim alone the
collapse rate is 11%; across all 17 books, where the Sunan restate the two
Sahihs heavily, it will be higher.

When a cluster merges, the surviving entry is chosen by source precedence:
Bukhari, then Muslim, then Abu Dawud, Nasa'i, Tirmidhi, Ibn Majah, Muwatta,
then the rest. The strongest available attribution is what ends up on screen.

New entries are also checked against the 206 existing Hisn entries and
dropped on a match. Those 206 are the hand-curated selection and always win.

## Review before publication

`scripts/review_adkar.py` prints every extracted entry — text, source,
reference, and the full hadith it came from — as a single document for
reading before any of it publishes.

This is not optional tooling. The README already warns that the corpus has
never been checked against a printed, scholarly-reviewed edition. This
project goes further and machine-extracts fragments of that text: a
mis-paired quotation mark in the source becomes a truncated supplication
published six times a day. Rules 4 and 3 above exist to catch exactly that,
but they are heuristics. Roughly 900 new entries is an evening's reading and
it is the only real defence.

The script writes `docs/adkar-review.md`. It is a reading aid, not a gate the
code enforces — nothing in the publish path consults it.

## Error handling

| Failure | Behaviour |
| --- | --- |
| Source directory missing or holds no recognised book | print usage, exit 2, write nothing |
| A book file is malformed JSON | name the file and exit 1, write nothing — a partial corpus that looks complete is worse than no corpus |
| A hadith has no `arabic` field, or it is empty | skip the entry, count it in the run summary |
| Extraction yields fewer than 400 new entries | write nothing and exit 1. A large silent drop means a source format change or a broken pattern, and overwriting a good corpus with a thin one is the failure that would reach the channel unnoticed |
| An id collides with an existing entry | exit 1 naming the id; ids are derived, so a collision means the derivation is wrong |

The importer merges into the existing file, as `import_hadith.py` does, so
re-running it is safe and adding a book later does not discard what is there.

## Testing

- Every produced entry contains at least one dhikr or dua formula.
- No produced entry contains a narration marker. This is the rule that keeps
  chains off the channel, and it gets a test with a real chain-bearing
  fixture.
- No produced entry contains an unbalanced `"`.
- Ids are unique, `adkar-`-prefixed, and disjoint from `data/hadith.json`.
- No surviving pair exceeds the 80% similarity threshold.
- The 206 Hisn entries are unchanged, compared byte for byte against the
  pre-run file.
- The merged file loads under `corpus.py` with no validation error.
- Diacritic-insensitive matching: a vocalised اللَّهُمَّ is found by the
  bare pattern اللهم. Without this the importer silently produces nothing,
  which is the exact trap already documented in `import_hadith.py`.
- The fewer-than-400 guard fires and writes nothing.

## Consequences for the running channel

`ADKAR_PUBLISH_COUNT` is currently `1`. Once the corpus lands it can go to
`6`, which is the cadence this work exists to support. The first repeat then
falls around six months out rather than 34 days.

`data/state-adkar.json` needs no migration. It records used ids, the new
entries are new ids, and nothing already published is affected.
