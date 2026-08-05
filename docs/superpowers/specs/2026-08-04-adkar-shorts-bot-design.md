# Adkar Shorts Bot — Design

**Date:** 2026-08-04
**Status:** Approved

## Purpose

Automatically produce and upload a YouTube Short containing a single Arabic
dhikr or duaa, once per day, to the owner's own channel. The channel owner
publishes each uploaded video manually.

This project deliberately replaces an earlier idea: a bot that would post
comments on other people's YouTube videos. That approach is prohibited
automated bulk commenting, and is out of scope permanently.

## Success criteria

1. A scheduled run produces a valid 1080×1920 H.264 MP4 with correctly shaped
   Arabic text and uploads it to the owner's channel.
2. No dhikr repeats until the entire corpus has been used.
3. Arabic renders with connected letterforms and correct right-to-left order.
4. A run that fails at any stage does not consume a corpus entry.
5. The whole system runs unattended on GitHub Actions with no local machine.

## Non-goals

Recitation or background audio, translations, transliteration, custom
thumbnails (Shorts ignore them), analytics, multi-channel support, a web UI,
and any interaction with videos or comment sections the owner does not own.

## Platform constraints

These are properties of Google's platform, not choices, and the design is
shaped around them.

| Constraint | Consequence |
| --- | --- |
| OAuth consent screen in *Testing* expires refresh tokens after 7 days | Consent screen must be set to **In production**. Verification is not required; the one-time "unverified app" interstitial is clicked through by the owner. |
| `youtube.upload` from an unverified app forces `privacyStatus: private` | The bot always uploads private. The owner publishes from YouTube Studio. `PRIVACY_STATUS` is a config constant so this flips in one line after verification. |
| `ubuntu-latest` ships ffmpeg but no Arabic fonts | The font is vendored into the repository. |
| `videos.insert` = 1600 units, `commentThreads.insert` = 50, daily quota 10,000 | Hard ceiling ≈ 6 uploads/day. At 1/day the bot uses 1,650. |
| GitHub disables scheduled workflows after 60 days of repo inactivity | Committing `state.json` on every run keeps the repo active automatically. |
| GitHub Actions `schedule` cron is best-effort and can be delayed | Exact publish time is not a requirement. |
| Shorts classification is automatic from aspect ratio and duration | No API flag exists or is needed. |

## Architecture

Six stages. Only `upload`, `annotate` and `persist` touch the outside world;
everything before them is pure and directly testable.

```
select  →  compose  →  render  →  upload  →  annotate  →  persist
 (io)      (pure)     (ffmpeg)    (net)      (net)        (git)
```

```
adkar-shorts-bot/
├── .github/workflows/publish.yml
├── src/adkar_bot/
│   ├── config.py     # constants and environment
│   ├── corpus.py     # load and validate adkar.json
│   ├── selector.py   # rotation cursor, picks next entry
│   ├── arabic.py     # wrap → reshape → bidi
│   ├── layout.py     # adaptive font sizing, safe-area fitting
│   ├── render.py     # Pillow overlays, ffmpeg encode
│   ├── metadata.py   # title, description, tags
│   ├── youtube.py    # OAuth, videos.insert, commentThreads.insert
│   └── cli.py        # entrypoints
├── scripts/authorize.py   # one-time local OAuth bootstrap
├── data/
│   ├── adkar.json
│   └── state.json
├── assets/fonts/Amiri-Regular.ttf
└── tests/
```

## Data model

### `data/adkar.json`

```json
{
  "id": "hisn-0042",
  "text": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ",
  "category": "tasbih",
  "source": "متفق عليه",
  "reference": "البخاري ٦٤٠٦، مسلم ٢٦٩٤"
}
```

`source` and `reference` appear in the video description and the pinned
comment. They are deliberately kept off the card itself, which shows only the
dhikr text and the channel handle.

Seeded with approximately 60 well-known adkar from Hisn al-Muslim. At one per
day that is roughly two months before any repeat.

### `data/state.json`

```json
{
  "cycle": 0,
  "used": ["hisn-0042"],
  "published": [
    { "id": "hisn-0042", "video_id": "dQw4w9WgXcQ", "at": "2026-08-04T06:00:00Z" }
  ]
}
```

### Rotation

The corpus is shuffled with `seed = cycle`, then walked in order. When `used`
covers the whole corpus, `cycle` increments, `used` resets, and the corpus is
reshuffled under the new seed. This guarantees no repeat within a cycle and a
different order in each subsequent cycle.

`state.json` is written and committed **only after a successful upload**, so a
failed run never consumes an entry.

## Arabic text handling

This is the module most likely to be got wrong, and the reason it is isolated.

The order is **wrap → reshape → bidi, applied per line**.

Wrapping operates on logical-order source text. Reshaping converts characters
to their contextual presentation forms, and bidi reorders for display. Doing
either of the latter two before wrapping splits presentation forms mid-word and
produces disconnected or reversed glyphs.

Wrapping is by **measured width, not character count** — Arabic glyph widths
vary far too much for a fixed character budget to be meaningful. The module
therefore does not own the font; it takes a predicate from the layout stage:

```python
def wrap_logical(text: str, fits: Callable[[str], bool]) -> list[str]:
    """Greedy word wrap on logical-order text. `fits` measures a candidate line."""

def shape(line: str) -> str:
    """Reshape to presentation forms, then apply bidi. One line at a time."""
```

This split keeps the ordering rule enforceable in one place while letting
`layout.py` own all font metrics.

Note that `fits` measures the **shaped** form of a candidate line, since that is
what actually gets drawn; shaping is applied inside the predicate for
measurement, and again to the final chosen lines. Shaping is pure, so applying
it twice is safe.

Tashkeel (diacritics) in the source text is preserved through all three steps.

## Layout

Font size and line breaking are solved together, not separately. For a
candidate font size, `layout.py` builds a `fits` predicate from that font's
metrics and the safe box width, calls `wrap_logical` to get the line breaks
that size implies, then checks whether the resulting block height also fits.
Binary search over `[36, 96]` returns the largest size where both hold.

Font size alone cannot be searched independently of wrapping, because changing
the size changes the line count, which changes the required height.

The safe box excludes the bottom ~280 px and right ~140 px of the 1080×1920
frame, which the Shorts player overlays with the title, description and action
rail. Horizontal margin is 96 px per side.

Duration is `clamp(2.2 × word_count, 8s, 30s)`, approximating reading pace.

Short adkar therefore render large and centered; longer duaa render smaller
across more lines and run longer. This is the adaptive behaviour the design
calls for, and it comes from one code path rather than two templates.

## Rendering

Pillow generates a vertical gradient background with a subtle vignette, then
draws each prepared line to its own transparent RGBA PNG.

ffmpeg composites the line overlays onto the background, staggering each in
with `fade=alpha=1` at roughly 0.8 s intervals, and encodes:

- `libx264`, `yuv420p`, 30 fps, CRF 20
- a silent AAC track from `anullsrc`

The silent track is attached deliberately rather than producing a video-only
file; it costs nothing and avoids edge cases in YouTube's processing of streams
with no audio.

## Metadata

- **Title:** first ~40 characters of the dhikr, plus `#shorts`. Truncated to
  YouTube's 100-character limit.
- **Description:** full dhikr text, then `source` and `reference`, then a fixed
  footer.
- **Tags:** a fixed Arabic set plus the entry's `category`.
- **categoryId:** `22` (People & Blogs).

## Error handling

- Corpus is validated on load. Duplicate ids, missing `id`, or missing `text`
  fail the run immediately.
- Non-zero ffmpeg exit captures stderr and fails the job.
- Uploads are resumable, with exponential backoff on 5xx and 429.
- If the upload succeeds but the pinned comment fails, the failure is logged,
  state is still persisted, and the upload is **not** retried.
- The workflow declares `concurrency: { group: publish }` so a delayed run
  cannot overlap with the next and double-publish.

## Workflow

```yaml
on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:
concurrency:
  group: publish
  cancel-in-progress: false
permissions:
  contents: write
```

Tests run as a prior job; publish runs only if they pass.

Secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

## Required configuration

`CHANNEL_HANDLE` in `src/adkar_bot/config.py` sets the handle rendered at the
bottom of every card. It ships as `@your-channel` and **must be set to the
owner's real handle before the first run.** A test asserts it is no longer the
placeholder value, so an unconfigured deployment fails loudly rather than
publishing cards with placeholder text.

## OAuth bootstrap

`scripts/authorize.py` is run once on the owner's machine. It executes an
installed-app OAuth flow with `access_type=offline` and `prompt=consent`, then
prints the refresh token for pasting into GitHub repository secrets.

Prerequisite setup, performed once by the owner: create a Google Cloud project,
enable YouTube Data API v3, configure the OAuth consent screen and set its
publishing status to **In production**, and create an OAuth client of type
Desktop app.

## Testing

Unit tests:

- `arabic.py` — a known word reshapes to expected presentation forms; wrapping
  never splits inside a word; tashkeel survives; and a regression test asserts
  that reshape-then-wrap differs from wrap-then-reshape, so the ordering cannot
  be "simplified" away later.
- `selector.py` — no repeat within a cycle; cycle rollover reshuffles; a failed
  run does not consume an entry.
- `layout.py` — chosen font size always fits the safe box, for both the
  shortest and longest corpus entries.
- `metadata.py` — title never exceeds 100 characters.
- `config.py` — `CHANNEL_HANDLE` is not the placeholder.

Integration test: render one video end to end and assert via `ffprobe` that it
is 1080×1920, that duration falls in the expected range, and that both a video
and an audio stream are present.

A golden-image test renders a fixed dhikr and compares against a committed
reference PNG within tolerance, guarding the visual result.

`youtube.py` is mocked. No test performs network I/O.
