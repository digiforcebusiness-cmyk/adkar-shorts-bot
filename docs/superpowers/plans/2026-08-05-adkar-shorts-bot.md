# Adkar Shorts Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bot that renders one Arabic dhikr per day as a 1080×1920 animated-text Short and uploads it to the owner's own YouTube channel from GitHub Actions.

**Architecture:** Six stages — `select → compose → render → upload → annotate → persist`. Everything before `upload` is pure and unit-tested with no network or filesystem surprises. Pillow draws a gradient background plus one transparent PNG per text line; ffmpeg fades them in and encodes. Rotation state lives in `data/state.json` and is committed back to the repo after each successful upload.

**Tech Stack:** Python 3.12, Pillow, arabic-reshaper, python-bidi, google-api-python-client, google-auth-oauthlib, pytest, ffmpeg (system binary), GitHub Actions.

## Global Constraints

- Python 3.12. Locally the interpreter is `py -3` — bare `python` on this machine is the Microsoft Store stub and does not work. On `ubuntu-latest` runners use `python`.
- Frame is exactly 1080×1920, 30 fps, H.264, `yuv420p`, CRF 20, with a silent AAC track.
- Arabic text ordering is **wrap → reshape → bidi, applied per line**. Never reshape or bidi before wrapping.
- `arabic_reshaper` must be configured with `delete_harakat: False`. The default deletes tashkeel.
- Safe area excludes the bottom 280 px and right 140 px of the frame (Shorts UI chrome).
- OAuth scopes are exactly `youtube.upload` **and** `youtube.force-ssl`. The second is required for `commentThreads.insert`.
- Uploads always use `privacyStatus: private` until the OAuth app is verified. Google forces this regardless of what is sent.
- The YouTube Data API **cannot pin a comment.** The bot posts a top comment; pinning is manual.
- Quota: `videos.insert` = 1600 units, `commentThreads.insert` = 50, daily budget 10,000.
- `data/state.json` is written **only after a successful upload**.
- All tests run offline. `youtube.py` is always mocked in tests.

---

### Task 1: Project scaffolding and configuration

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/adkar_bot/__init__.py`, `src/adkar_bot/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: module `adkar_bot.config` exposing the constants below, plus
  `assert_configured() -> None` which raises `ConfigError` when
  `CHANNEL_HANDLE` is still the placeholder.

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "adkar-bot"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pillow>=10.4",
    "arabic-reshaper>=3.0.0",
    "python-bidi>=0.4.2",
    "google-api-python-client>=2.140",
    "google-auth>=2.33",
    "google-auth-oauthlib>=1.2",
]

[project.optional-dependencies]
dev = ["pytest>=8.3"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
output/
*.egg-info/
.pytest_cache/
client_secret*.json
token.json
```

- [ ] **Step 3: Write the failing test**

`tests/test_config.py`:

```python
import pytest
from adkar_bot import config
from adkar_bot.config import ConfigError, assert_configured


def test_frame_is_vertical_1080x1920():
    assert (config.WIDTH, config.HEIGHT) == (1080, 1920)


def test_content_box_excludes_shorts_ui_chrome():
    assert config.CONTENT_W == 1080 - 2 * 96 - 140
    assert config.CONTENT_H == 1920 - config.SAFE_TOP - 280


def test_assert_configured_raises_on_placeholder(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", config.CHANNEL_HANDLE_PLACEHOLDER)
    with pytest.raises(ConfigError, match="CHANNEL_HANDLE"):
        assert_configured()


def test_assert_configured_passes_on_real_handle(monkeypatch):
    monkeypatch.setattr(config, "CHANNEL_HANDLE", "@adkar")
    assert_configured() is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot'`

- [ ] **Step 5: Create `src/adkar_bot/__init__.py`**

```python
"""Adkar Shorts bot."""
```

- [ ] **Step 6: Write `src/adkar_bot/config.py`**

```python
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
ASSETS_DIR = ROOT / "assets"
OUTPUT_DIR = ROOT / "output"

CORPUS_PATH = DATA_DIR / "adkar.json"
STATE_PATH = DATA_DIR / "state.json"
FONT_PATH = ASSETS_DIR / "fonts" / "Amiri-Regular.ttf"

# Frame
WIDTH, HEIGHT = 1080, 1920
MARGIN_X = 96
SAFE_TOP = 220
SAFE_BOTTOM = 280   # Shorts title/description overlay
SAFE_RIGHT = 140    # Shorts action rail
CONTENT_W = WIDTH - 2 * MARGIN_X - SAFE_RIGHT
CONTENT_H = HEIGHT - SAFE_TOP - SAFE_BOTTOM

# Typography
FONT_MIN, FONT_MAX = 36, 96
LINE_SPACING = 1.6
TEXT_COLOR = (255, 255, 255, 255)
HANDLE_COLOR = (255, 255, 255, 170)
HANDLE_SIZE = 34
GRADIENT_TOP = (14, 34, 48)
GRADIENT_BOTTOM = (6, 12, 20)

# Animation / encode
FPS = 30
CRF = 20
LINE_FADE_D = 0.6
LINE_STAGGER = 0.8
DUR_PER_WORD = 2.2
DUR_MIN, DUR_MAX = 8.0, 30.0

# YouTube
CHANNEL_HANDLE_PLACEHOLDER = "@your-channel"
CHANNEL_HANDLE = os.environ.get("CHANNEL_HANDLE", CHANNEL_HANDLE_PLACEHOLDER)
PRIVACY_STATUS = os.environ.get("PRIVACY_STATUS", "private")
CATEGORY_ID = "22"  # People & Blogs
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


class ConfigError(RuntimeError):
    pass


def assert_configured() -> None:
    """Fail loudly rather than publishing cards reading '@your-channel'."""
    if CHANNEL_HANDLE == CHANNEL_HANDLE_PLACEHOLDER:
        raise ConfigError(
            "CHANNEL_HANDLE is still the placeholder. Set it in config.py "
            "or via the CHANNEL_HANDLE environment variable."
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore src tests
git commit -m "feat: project scaffolding and configuration"
```

---

### Task 2: Arabic text shaping

**Files:**
- Create: `src/adkar_bot/arabic.py`
- Test: `tests/test_arabic.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `shape(line: str) -> str` — reshape to presentation forms then bidi. One line at a time.
  - `wrap_logical(text: str, fits: Callable[[str], bool]) -> list[str]` — greedy word wrap on logical-order text.

This is the module most likely to be got wrong. It owns the ordering rule and nothing else. It never touches fonts.

- [ ] **Step 1: Install dependencies**

```bash
py -3 -m pip install -e ".[dev]"
```

- [ ] **Step 2: Write the failing tests**

`tests/test_arabic.py`:

```python
from adkar_bot.arabic import shape, wrap_logical

BASMALA = "بسم الله الرحمن الرحيم"
WITH_HARAKAT = "سُبْحَانَ اللَّهِ"


def test_shape_connects_letterforms():
    # Isolated forms must be replaced by contextual presentation forms.
    out = shape(BASMALA)
    assert out != BASMALA
    # U+FEFB is the LAM-ALEF ligature; it appears in shaped output only.
    assert any(0xFE70 <= ord(c) <= 0xFEFF for c in out)


def test_shape_preserves_harakat():
    # arabic_reshaper deletes tashkeel by default. It must not here.
    assert "ْ" in shape(WITH_HARAKAT)  # sukun
    assert "َ" in shape(WITH_HARAKAT)  # fatha


def test_shape_is_pure():
    assert shape(BASMALA) == shape(BASMALA)


def test_wrap_never_splits_a_word():
    fits = lambda s: len(s) <= 10
    lines = wrap_logical("aaa bbb ccc ddd", fits)
    for line in lines:
        for word in line.split():
            assert word in {"aaa", "bbb", "ccc", "ddd"}
    assert " ".join(lines).split() == "aaa bbb ccc ddd".split()


def test_wrap_keeps_oversized_word_on_its_own_line():
    fits = lambda s: len(s) <= 3
    assert wrap_logical("aa bbbbbbbb cc", fits) == ["aa", "bbbbbbbb", "cc"]


def test_wrap_of_empty_text_is_empty():
    assert wrap_logical("   ", lambda s: True) == []


def test_reshape_then_wrap_differs_from_wrap_then_reshape():
    """Regression guard: the ordering rule must not be 'simplified' away.

    Reshaping before wrapping splits presentation forms mid-word.
    """
    fits = lambda s: len(s) <= 12
    correct = [shape(l) for l in wrap_logical(BASMALA, fits)]
    wrong = wrap_logical(shape(BASMALA), fits)
    assert correct != wrong
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_arabic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.arabic'`

- [ ] **Step 4: Write `src/adkar_bot/arabic.py`**

```python
from collections.abc import Callable

from arabic_reshaper import ArabicReshaper
from bidi.algorithm import get_display

# delete_harakat=False is essential — the default strips tashkeel.
_reshaper = ArabicReshaper(
    configuration={"delete_harakat": False, "support_ligatures": True}
)


def shape(line: str) -> str:
    """Reshape one line to presentation forms, then apply bidi for display.

    Must be called on an already-wrapped line. Shaping a multi-line block or
    shaping before wrapping splits presentation forms mid-word.
    """
    return get_display(_reshaper.reshape(line))


def wrap_logical(text: str, fits: Callable[[str], bool]) -> list[str]:
    """Greedy word wrap over logical-order source text.

    `fits` decides whether a candidate line is acceptable; it is supplied by
    the layout stage, which owns all font metrics. A single word wider than
    the box is placed on its own line and left overflowing — the caller's
    binary search resolves that by choosing a smaller font.
    """
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if fits(candidate):
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_arabic.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add src/adkar_bot/arabic.py tests/test_arabic.py
git commit -m "feat: Arabic shaping with wrap-before-reshape ordering"
```

---

### Task 3: Corpus loading, validation, and seed data

**Files:**
- Create: `src/adkar_bot/corpus.py`, `data/adkar.json`
- Test: `tests/test_corpus.py`

**Interfaces:**
- Consumes: `adkar_bot.config.CORPUS_PATH`
- Produces:
  - `@dataclass(frozen=True) Dhikr` with fields `id: str`, `text: str`, `category: str`, `source: str`, `reference: str`
  - `load_corpus(path: Path | None = None) -> list[Dhikr]`
  - `CorpusError(Exception)`

- [ ] **Step 1: Write the failing tests**

`tests/test_corpus.py`:

```python
import json
import pytest
from adkar_bot.corpus import CorpusError, Dhikr, load_corpus
from adkar_bot import config


def write(tmp_path, entries):
    p = tmp_path / "adkar.json"
    p.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return p


VALID = {
    "id": "hisn-0001",
    "text": "سُبْحَانَ اللَّهِ",
    "category": "tasbih",
    "source": "متفق عليه",
    "reference": "البخاري ٦٤٠٦",
}


def test_loads_valid_entries(tmp_path):
    corpus = load_corpus(write(tmp_path, [VALID]))
    assert corpus == [Dhikr(**VALID)]


def test_rejects_duplicate_ids(tmp_path):
    with pytest.raises(CorpusError, match="duplicate"):
        load_corpus(write(tmp_path, [VALID, VALID]))


def test_rejects_missing_text(tmp_path):
    bad = {**VALID, "text": "  "}
    with pytest.raises(CorpusError, match="text"):
        load_corpus(write(tmp_path, [bad]))


def test_rejects_missing_id(tmp_path):
    bad = {k: v for k, v in VALID.items() if k != "id"}
    with pytest.raises(CorpusError, match="id"):
        load_corpus(write(tmp_path, [bad]))


def test_rejects_empty_corpus(tmp_path):
    with pytest.raises(CorpusError, match="empty"):
        load_corpus(write(tmp_path, []))


def test_real_corpus_loads_and_is_nontrivial():
    corpus = load_corpus(config.CORPUS_PATH)
    assert len(corpus) >= 12
    assert len({d.id for d in corpus}) == len(corpus)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_corpus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.corpus'`

- [ ] **Step 3: Write `src/adkar_bot/corpus.py`**

```python
import json
from dataclasses import dataclass
from pathlib import Path

from . import config


class CorpusError(RuntimeError):
    pass


@dataclass(frozen=True)
class Dhikr:
    id: str
    text: str
    category: str
    source: str
    reference: str


_REQUIRED = ("id", "text", "category", "source", "reference")


def load_corpus(path: Path | None = None) -> list[Dhikr]:
    path = path or config.CORPUS_PATH
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    if not raw:
        raise CorpusError(f"corpus at {path} is empty")

    seen: set[str] = set()
    out: list[Dhikr] = []
    for i, entry in enumerate(raw):
        for field in _REQUIRED:
            if field not in entry:
                raise CorpusError(f"entry {i} is missing required field {field!r}")
            if not str(entry[field]).strip():
                raise CorpusError(f"entry {i} has blank field {field!r}")
        if entry["id"] in seen:
            raise CorpusError(f"duplicate id {entry['id']!r}")
        seen.add(entry["id"])
        out.append(Dhikr(**{f: entry[f] for f in _REQUIRED}))
    return out
```

- [ ] **Step 4: Create `data/adkar.json` with the seed corpus**

Twelve well-known adkar spanning short and long forms, so the adaptive layout
is exercised from day one.

```json
[
  {"id": "hisn-0001", "text": "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ، سُبْحَانَ اللَّهِ الْعَظِيمِ", "category": "tasbih", "source": "متفق عليه", "reference": "البخاري ٦٤٠٦، مسلم ٢٦٩٤"},
  {"id": "hisn-0002", "text": "لَا إِلَهَ إِلَّا اللَّهُ وَحْدَهُ لَا شَرِيكَ لَهُ، لَهُ الْمُلْكُ وَلَهُ الْحَمْدُ وَهُوَ عَلَى كُلِّ شَيْءٍ قَدِيرٌ", "category": "tahlil", "source": "متفق عليه", "reference": "البخاري ٦٤٠٣، مسلم ٢٦٩١"},
  {"id": "hisn-0003", "text": "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ الَّذِي لَا إِلَهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ وَأَتُوبُ إِلَيْهِ", "category": "istighfar", "source": "سنن", "reference": "أبو داود ١٥١٧، الترمذي ٣٥٧٧"},
  {"id": "hisn-0004", "text": "سُبْحَانَ اللَّهِ وَالْحَمْدُ لِلَّهِ وَلَا إِلَهَ إِلَّا اللَّهُ وَاللَّهُ أَكْبَرُ", "category": "tasbih", "source": "مسلم", "reference": "مسلم ٢٦٩٥"},
  {"id": "hisn-0005", "text": "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ", "category": "dhikr", "source": "متفق عليه", "reference": "البخاري ٦٤٠٩، مسلم ٢٧٠٤"},
  {"id": "hisn-0006", "text": "حَسْبِيَ اللَّهُ لَا إِلَهَ إِلَّا هُوَ عَلَيْهِ تَوَكَّلْتُ وَهُوَ رَبُّ الْعَرْشِ الْعَظِيمِ", "category": "duaa", "source": "القرآن والسنة", "reference": "التوبة ١٢٩، أبو داود ٥٠٨١"},
  {"id": "hisn-0007", "text": "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً وَفِي الْآخِرَةِ حَسَنَةً وَقِنَا عَذَابَ النَّارِ", "category": "duaa", "source": "القرآن", "reference": "البقرة ٢٠١"},
  {"id": "hisn-0008", "text": "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَفْوَ وَالْعَافِيَةَ فِي الدُّنْيَا وَالْآخِرَةِ", "category": "duaa", "source": "سنن", "reference": "ابن ماجه ٣٨٧١"},
  {"id": "hisn-0009", "text": "بِسْمِ اللَّهِ الَّذِي لَا يَضُرُّ مَعَ اسْمِهِ شَيْءٌ فِي الْأَرْضِ وَلَا فِي السَّمَاءِ وَهُوَ السَّمِيعُ الْعَلِيمُ", "category": "duaa", "source": "سنن", "reference": "أبو داود ٥٠٨٨، الترمذي ٣٣٨٨"},
  {"id": "hisn-0010", "text": "رَضِيتُ بِاللَّهِ رَبًّا، وَبِالْإِسْلَامِ دِينًا، وَبِمُحَمَّدٍ صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ نَبِيًّا", "category": "dhikr", "source": "سنن", "reference": "أبو داود ١٥٢٩"},
  {"id": "hisn-0011", "text": "اللَّهُمَّ أَعِنِّي عَلَى ذِكْرِكَ وَشُكْرِكَ وَحُسْنِ عِبَادَتِكَ", "category": "duaa", "source": "سنن", "reference": "أبو داود ١٥٢٢"},
  {"id": "hisn-0012", "text": "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ، وَأَعُوذُ بِكَ مِنَ الْعَجْزِ وَالْكَسَلِ، وَأَعُوذُ بِكَ مِنَ الْجُبْنِ وَالْبُخْلِ", "category": "duaa", "source": "البخاري", "reference": "البخاري ٦٣٦٩"}
]
```

⚠️ **Before the first public upload, the channel owner must verify every
`text` and `reference` against a printed or scholarly-reviewed edition of
Hisn al-Muslim.** This is religious content; hadith numbering varies between
editions, and an automated pipeline will reproduce any error 60 times. Growing
the corpus from 12 to ~60 entries is content work, not code work, and it does
not block any task in this plan.

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_corpus.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add src/adkar_bot/corpus.py data/adkar.json tests/test_corpus.py
git commit -m "feat: corpus loading with validation and seed adkar"
```

---

### Task 4: Rotation and state

**Files:**
- Create: `src/adkar_bot/selector.py`
- Test: `tests/test_selector.py`

**Interfaces:**
- Consumes: `Dhikr` from `corpus.py`
- Produces:
  - `@dataclass State` with `cycle: int`, `used: list[str]`, `published: list[dict]`
  - `load_state(path) -> State` (returns a fresh `State(0, [], [])` if the file is absent)
  - `save_state(state, path) -> None`
  - `next_dhikr(corpus: list[Dhikr], state: State) -> Dhikr`
  - `record(state: State, dhikr: Dhikr, video_id: str, at: str) -> State`

`next_dhikr` must be pure — it does not mutate state. `record` returns a new
state. This is what makes "a failed run never consumes an entry" trivially
true: nothing is persisted until `save_state` is called after upload.

- [ ] **Step 1: Write the failing tests**

`tests/test_selector.py`:

```python
import json
import pytest
from adkar_bot.corpus import Dhikr
from adkar_bot.selector import State, load_state, next_dhikr, record, save_state


def make_corpus(n):
    return [
        Dhikr(id=f"d{i}", text=f"t{i}", category="c", source="s", reference="r")
        for i in range(n)
    ]


def test_fresh_state_when_file_absent(tmp_path):
    assert load_state(tmp_path / "nope.json") == State(cycle=0, used=[], published=[])


def test_roundtrip(tmp_path):
    p = tmp_path / "state.json"
    s = State(cycle=2, used=["a"], published=[{"id": "a"}])
    save_state(s, p)
    assert load_state(p) == s


def test_no_repeat_within_a_cycle():
    corpus = make_corpus(5)
    state = State(cycle=0, used=[], published=[])
    picked = []
    for _ in range(5):
        d = next_dhikr(corpus, state)
        picked.append(d.id)
        state = record(state, d, "vid", "2026-01-01T00:00:00Z")
    assert sorted(picked) == sorted(d.id for d in corpus)


def test_cycle_rolls_over_when_exhausted():
    corpus = make_corpus(3)
    state = State(cycle=0, used=[d.id for d in corpus], published=[])
    d = next_dhikr(corpus, state)
    after = record(state, d, "vid", "2026-01-01T00:00:00Z")
    assert after.cycle == 1
    assert after.used == [d.id]


def test_different_cycles_use_different_orders():
    corpus = make_corpus(12)
    def order(cycle):
        state, out = State(cycle=cycle, used=[], published=[]), []
        for _ in range(12):
            d = next_dhikr(corpus, state)
            out.append(d.id)
            state = record(state, d, "v", "t")
        return out
    assert order(0) != order(1)


def test_next_dhikr_does_not_mutate_state():
    corpus = make_corpus(3)
    state = State(cycle=0, used=[], published=[])
    next_dhikr(corpus, state)
    assert state == State(cycle=0, used=[], published=[])


def test_order_is_deterministic_for_a_given_cycle():
    corpus = make_corpus(8)
    s = State(cycle=4, used=[], published=[])
    assert next_dhikr(corpus, s).id == next_dhikr(corpus, s).id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_selector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.selector'`

- [ ] **Step 3: Write `src/adkar_bot/selector.py`**

```python
import json
import random
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from .corpus import Dhikr


@dataclass(frozen=True)
class State:
    cycle: int = 0
    used: list[str] = field(default_factory=list)
    published: list[dict] = field(default_factory=list)


def load_state(path: Path) -> State:
    path = Path(path)
    if not path.exists():
        return State()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return State(
        cycle=raw.get("cycle", 0),
        used=raw.get("used", []),
        published=raw.get("published", []),
    )


def save_state(state: State, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(state), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _shuffled(corpus: list[Dhikr], cycle: int) -> list[Dhikr]:
    ordered = sorted(corpus, key=lambda d: d.id)
    random.Random(cycle).shuffle(ordered)
    return ordered


def _effective(state: State, corpus: list[Dhikr]) -> tuple[int, set[str]]:
    """Roll the cycle over if every id has been used."""
    ids = {d.id for d in corpus}
    if ids and ids.issubset(set(state.used)):
        return state.cycle + 1, set()
    return state.cycle, set(state.used)


def next_dhikr(corpus: list[Dhikr], state: State) -> Dhikr:
    cycle, used = _effective(state, corpus)
    for dhikr in _shuffled(corpus, cycle):
        if dhikr.id not in used:
            return dhikr
    raise RuntimeError("unreachable: cycle rollover guarantees an unused entry")


def record(state: State, dhikr: Dhikr, video_id: str, at: str,
           corpus: list[Dhikr] | None = None) -> State:
    """Return a new state with `dhikr` marked used and the publish logged.

    `corpus` lets this reproduce the same rollover decision `next_dhikr` made.
    Without it, rollover is inferred from `dhikr` already being in `used`,
    which is the only way that can happen after a correct `next_dhikr` call.
    """
    if corpus is not None:
        cycle, used = _effective(state, corpus)
    elif dhikr.id in set(state.used):
        cycle, used = state.cycle + 1, set()
    else:
        cycle, used = state.cycle, set(state.used)

    return State(
        cycle=cycle,
        used=sorted(used | {dhikr.id}),
        published=[*state.published,
                   {"id": dhikr.id, "video_id": video_id, "at": at}],
    )
```

Note the tests in Step 1 pass `corpus=corpus` to `record` wherever rollover
matters — `test_no_repeat_within_a_cycle`,
`test_cycle_rolls_over_when_exhausted`, and
`test_different_cycles_use_different_orders`. Write them that way from the
start:

```python
state = record(state, d, "vid", "2026-01-01T00:00:00Z", corpus=corpus)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_selector.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/selector.py tests/test_selector.py
git commit -m "feat: deterministic rotation with cycle rollover"
```

---

### Task 5: Adaptive layout

**Files:**
- Create: `src/adkar_bot/layout.py`, `assets/fonts/Amiri-Regular.ttf`
- Test: `tests/test_layout.py`

**Interfaces:**
- Consumes: `shape`, `wrap_logical` from `arabic.py`; constants from `config.py`
- Produces:
  - `@dataclass(frozen=True) Layout` with `font_size: int`, `lines: list[str]` (already shaped, display order), `line_height: int`, `block_height: int`
  - `fit(text: str) -> Layout`
  - `LayoutError(RuntimeError)`
  - `duration_for(text: str) -> float`

Font size and wrapping are solved **together**. Changing the size changes the
line count, which changes the required height, so they cannot be searched
independently.

- [ ] **Step 1: Vendor the font**

Amiri is licensed under the SIL Open Font License, which permits redistribution
inside this repository.

```bash
mkdir -p assets/fonts
curl -L -o /tmp/amiri.zip https://github.com/aliftype/amiri/releases/download/1.001/Amiri-1.001.zip
unzip -j /tmp/amiri.zip '*/Amiri-Regular.ttf' -d assets/fonts/
```

Verify: `py -3 -c "from PIL import ImageFont; print(ImageFont.truetype('assets/fonts/Amiri-Regular.ttf', 48).getname())"`
Expected: `('Amiri', 'Regular')`

If that release URL 404s, download Amiri from https://fonts.google.com/specimen/Amiri and place `Amiri-Regular.ttf` at the same path. Any Naskh face with full tashkeel coverage works; only the path matters.

- [ ] **Step 2: Write the failing tests**

`tests/test_layout.py`:

```python
import pytest
from adkar_bot import config
from adkar_bot.corpus import load_corpus
from adkar_bot.layout import Layout, LayoutError, duration_for, fit

SHORT = "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ"
LONG = ("اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ، وَأَعُوذُ بِكَ مِنَ الْعَجْزِ "
        "وَالْكَسَلِ، وَأَعُوذُ بِكَ مِنَ الْجُبْنِ وَالْبُخْلِ")


def test_short_text_gets_a_larger_font_than_long_text():
    assert fit(SHORT).font_size > fit(LONG).font_size


def test_layout_always_fits_the_content_box():
    for text in (SHORT, LONG):
        layout = fit(text)
        assert layout.block_height <= config.CONTENT_H
        assert config.FONT_MIN <= layout.font_size <= config.FONT_MAX


def test_every_corpus_entry_lays_out():
    for dhikr in load_corpus(config.CORPUS_PATH):
        layout = fit(dhikr.text)
        assert layout.lines
        assert layout.block_height <= config.CONTENT_H


def test_lines_are_shaped_not_raw():
    layout = fit(SHORT)
    assert "".join(layout.lines) != SHORT


def test_impossible_text_raises():
    with pytest.raises(LayoutError):
        fit("م " * 4000)


def test_duration_is_clamped():
    assert duration_for("كلمة") == config.DUR_MIN
    assert duration_for("كلمة " * 500) == config.DUR_MAX


def test_duration_scales_with_length():
    assert duration_for("كلمة " * 6) > duration_for("كلمة " * 3)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_layout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.layout'`

- [ ] **Step 4: Write `src/adkar_bot/layout.py`**

```python
from dataclasses import dataclass

from PIL import ImageFont

from . import config
from .arabic import shape, wrap_logical


class LayoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class Layout:
    font_size: int
    lines: list[str]      # already shaped, display order
    line_height: int
    block_height: int


def _try_size(text: str, size: int) -> Layout | None:
    font = ImageFont.truetype(str(config.FONT_PATH), size)

    def fits(candidate: str) -> bool:
        return font.getlength(shape(candidate)) <= config.CONTENT_W

    logical_lines = wrap_logical(text, fits)
    if not logical_lines:
        return None

    shaped = [shape(line) for line in logical_lines]
    if max(font.getlength(line) for line in shaped) > config.CONTENT_W:
        return None  # a single word overflows at this size

    line_height = int(size * config.LINE_SPACING)
    block_height = line_height * len(shaped)
    if block_height > config.CONTENT_H:
        return None

    return Layout(
        font_size=size,
        lines=shaped,
        line_height=line_height,
        block_height=block_height,
    )


def fit(text: str) -> Layout:
    """Largest font size at which the wrapped text fits the content box."""
    lo, hi = config.FONT_MIN, config.FONT_MAX
    best: Layout | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        attempt = _try_size(text, mid)
        if attempt is not None:
            best, lo = attempt, mid + 1
        else:
            hi = mid - 1

    if best is None:
        raise LayoutError(
            f"text does not fit at minimum size {config.FONT_MIN}px: {text[:40]!r}..."
        )
    return best


def duration_for(text: str) -> float:
    words = len(text.split())
    return min(config.DUR_MAX, max(config.DUR_MIN, config.DUR_PER_WORD * words))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_layout.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add src/adkar_bot/layout.py assets/fonts/Amiri-Regular.ttf tests/test_layout.py
git commit -m "feat: adaptive layout with joint font-size and wrap search"
```

---

### Task 6: Rendering

**Files:**
- Create: `src/adkar_bot/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `Layout`, `fit`, `duration_for` from `layout.py`; `Dhikr` from `corpus.py`
- Produces: `render(dhikr: Dhikr, out_path: Path) -> Path`, `RenderError(RuntimeError)`

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:

```python
import json
import shutil
import subprocess
import pytest
from adkar_bot import config
from adkar_bot.corpus import Dhikr
from adkar_bot.render import gradient_background, line_overlay, render
from adkar_bot.layout import fit

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)

DHIKR = Dhikr(
    id="t1", text="لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ",
    category="dhikr", source="متفق عليه", reference="البخاري ٦٤٠٩",
)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def test_gradient_is_frame_sized():
    assert gradient_background().size == (config.WIDTH, config.HEIGHT)


def test_line_overlay_is_frame_sized_and_transparent():
    img = line_overlay(fit(DHIKR.text), index=0)
    assert img.size == (config.WIDTH, config.HEIGHT)
    assert img.mode == "RGBA"
    assert img.getpixel((5, 5))[3] == 0


def test_text_never_enters_the_shorts_action_rail():
    """The regression that matters: drawn pixels must stay in the safe box.

    Deliberately not a golden-image comparison — Windows and Ubuntu rasterize
    the same font differently, so byte or per-pixel equality fails in CI for
    reasons unrelated to any real defect. This asserts placement instead,
    which is what actually breaks.
    """
    img = line_overlay(fit(DHIKR.text), index=0)
    alpha = img.getchannel("A")
    box = alpha.getbbox()  # tight bounds of everything drawn
    assert box is not None, "nothing was drawn"
    left, top, right, bottom = box
    assert left >= config.MARGIN_X
    assert right <= config.WIDTH - config.SAFE_RIGHT
    assert top >= config.SAFE_TOP
    assert bottom <= config.HEIGHT - config.SAFE_BOTTOM


def test_overlay_rendering_is_deterministic():
    layout = fit(DHIKR.text)
    assert line_overlay(layout, 0).tobytes() == line_overlay(layout, 0).tobytes()


def test_render_produces_a_valid_short(tmp_path):
    out = render(DHIKR, tmp_path / "out.mp4")
    info = probe(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")

    assert (video["width"], video["height"]) == (1080, 1920)
    assert video["codec_name"] == "h264"
    assert video["pix_fmt"] == "yuv420p"
    assert audio["codec_name"] == "aac"

    duration = float(info["format"]["duration"])
    assert config.DUR_MIN - 1 <= duration <= config.DUR_MAX + 1
    assert duration <= 180  # Shorts hard limit
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_render.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.render'`

- [ ] **Step 3: Write `src/adkar_bot/render.py`**

```python
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config
from .corpus import Dhikr
from .layout import Layout, duration_for, fit


class RenderError(RuntimeError):
    pass


def gradient_background() -> Image.Image:
    """Vertical linear gradient, drawn one row at a time."""
    img = Image.new("RGB", (config.WIDTH, config.HEIGHT))
    draw = ImageDraw.Draw(img)
    top, bottom = config.GRADIENT_TOP, config.GRADIENT_BOTTOM
    for y in range(config.HEIGHT):
        t = y / (config.HEIGHT - 1)
        draw.line(
            [(0, y), (config.WIDTH, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return img


def _block_top(layout: Layout) -> int:
    free = config.CONTENT_H - layout.block_height
    return config.SAFE_TOP + free // 2


def _center_x() -> int:
    return config.MARGIN_X + config.CONTENT_W // 2


def line_overlay(layout: Layout, index: int) -> Image.Image:
    """A full-frame transparent image containing only line `index`."""
    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(config.FONT_PATH), layout.font_size)
    y = _block_top(layout) + index * layout.line_height
    draw.text(
        (_center_x(), y),
        layout.lines[index],
        font=font,
        fill=config.TEXT_COLOR,
        anchor="ma",  # middle-ascender: horizontally centered
    )
    return img


def _handle_layer() -> Image.Image:
    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(config.FONT_PATH), config.HANDLE_SIZE)
    # Above the bottom safe line, not inside it — the Shorts title overlay
    # covers everything below HEIGHT - SAFE_BOTTOM.
    baseline = config.HEIGHT - config.SAFE_BOTTOM - config.HANDLE_SIZE - 24
    draw.text(
        (_center_x(), baseline),
        config.CHANNEL_HANDLE,
        font=font,
        fill=config.HANDLE_COLOR,
        anchor="ma",
    )
    return img


def _filter_complex(n_overlays: int) -> tuple[str, str]:
    """Fade each overlay in on its own schedule, then stack them.

    Returns the filter graph and the label of its final video output.
    """
    parts, prev = [], "0:v"
    for i in range(n_overlays):
        start = i * config.LINE_STAGGER
        parts.append(
            f"[{i + 1}:v]fade=t=in:st={start:.2f}:d={config.LINE_FADE_D}:alpha=1[l{i}]"
        )
        parts.append(f"[{prev}][l{i}]overlay=0:0[v{i}]")
        prev = f"v{i}"
    return ";".join(parts), prev


def render(dhikr: Dhikr, out_path: Path) -> Path:
    layout = fit(dhikr.text)
    duration = duration_for(dhikr.text)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bg = tmp / "bg.png"
        gradient_background().save(bg)

        overlays = []
        for i in range(len(layout.lines)):
            p = tmp / f"line{i}.png"
            line_overlay(layout, i).save(p)
            overlays.append(p)
        handle = tmp / "handle.png"
        _handle_layer().save(handle)
        overlays.append(handle)

        chain, last = _filter_complex(len(overlays))
        cmd = ["ffmpeg", "-y", "-loop", "1", "-t", f"{duration}", "-i", str(bg)]
        for p in overlays:
            cmd += ["-loop", "1", "-t", f"{duration}", "-i", str(p)]
        cmd += [
            "-f", "lavfi", "-t", f"{duration}",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-filter_complex", chain,
            "-map", f"[{last}]", "-map", f"{len(overlays) + 1}:a",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", str(config.FPS), "-crf", str(config.CRF),
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-shortest",
            str(out_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RenderError(f"ffmpeg failed:\n{result.stderr[-2000:]}")

    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_render.py -v`
Expected: 5 passed

- [ ] **Step 5: Eyeball the output once**

```bash
py -3 -c "from pathlib import Path; from adkar_bot.corpus import load_corpus; from adkar_bot.render import render; render(load_corpus()[1], Path('output/sample.mp4'))"
```

Open `output/sample.mp4`. Confirm the Arabic letterforms are **connected**, read
right-to-left, tashkeel is present, and no text sits under the bottom-right
action rail. This is the one check no automated test replaces.

- [ ] **Step 6: Commit**

```bash
git add src/adkar_bot/render.py tests/test_render.py
git commit -m "feat: gradient and animated-text rendering via ffmpeg"
```

---

### Task 7: Metadata

**Files:**
- Create: `src/adkar_bot/metadata.py`
- Test: `tests/test_metadata.py`

**Interfaces:**
- Consumes: `Dhikr`
- Produces: `build_title(dhikr) -> str`, `build_description(dhikr) -> str`, `build_tags(dhikr) -> list[str]`, `build_comment(dhikr) -> str`

- [ ] **Step 1: Write the failing tests**

`tests/test_metadata.py`:

```python
from adkar_bot.corpus import Dhikr
from adkar_bot.metadata import build_comment, build_description, build_tags, build_title

LONG = Dhikr(
    id="x", text="اللَّهُمَّ " * 40, category="duaa",
    source="سنن", reference="أبو داود ١٥٢٢",
)
SHORT = Dhikr(
    id="y", text="لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ", category="dhikr",
    source="متفق عليه", reference="البخاري ٦٤٠٩",
)


def test_title_within_youtube_limit():
    assert len(build_title(LONG)) <= 100


def test_title_tagged_as_short():
    assert "#shorts" in build_title(SHORT)


def test_title_does_not_end_mid_word():
    title = build_title(LONG)
    assert "…" in title or "#shorts" in title
    assert "  " not in title


def test_description_carries_attribution():
    desc = build_description(SHORT)
    assert SHORT.text in desc
    assert SHORT.source in desc
    assert SHORT.reference in desc


def test_tags_include_category_and_are_unique():
    tags = build_tags(SHORT)
    assert SHORT.category in tags
    assert len(tags) == len(set(tags))


def test_comment_carries_full_text_and_reference():
    comment = build_comment(SHORT)
    assert SHORT.text in comment
    assert SHORT.reference in comment
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_metadata.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.metadata'`

- [ ] **Step 3: Write `src/adkar_bot/metadata.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_metadata.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/metadata.py tests/test_metadata.py
git commit -m "feat: title, description, tags and comment text"
```

---

### Task 8: YouTube client

**Files:**
- Create: `src/adkar_bot/youtube.py`
- Test: `tests/test_youtube.py`

**Interfaces:**
- Consumes: `config.SCOPES`, `config.PRIVACY_STATUS`, `config.CATEGORY_ID`
- Produces:
  - `build_client(client_id, client_secret, refresh_token)` → googleapiclient resource
  - `upload_video(client, path, title, description, tags) -> str` (returns video id)
  - `post_comment(client, video_id, text) -> None`
  - `UploadError(RuntimeError)`

No test in this file performs network I/O. The client is always a fake.

- [ ] **Step 1: Write the failing tests**

`tests/test_youtube.py`:

```python
from unittest.mock import MagicMock
import pytest
from adkar_bot import config
from adkar_bot.youtube import UploadError, post_comment, upload_video


class FakeInsert:
    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.body = None

    def next_chunk(self):
        return self.chunks.pop(0)


def fake_client(chunks):
    client = MagicMock()
    client.videos.return_value.insert.return_value = FakeInsert(chunks)
    return client


def test_upload_returns_video_id(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    client = fake_client([(None, {"id": "abc123"})])
    assert upload_video(client, f, "t", "d", ["a"]) == "abc123"


def test_upload_sends_private_status(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    client = fake_client([(None, {"id": "abc123"})])
    upload_video(client, f, "t", "d", ["a"])
    body = client.videos.return_value.insert.call_args.kwargs["body"]
    assert body["status"]["privacyStatus"] == config.PRIVACY_STATUS
    assert body["snippet"]["categoryId"] == config.CATEGORY_ID


def test_upload_raises_when_no_id_returned(tmp_path):
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    client = fake_client([(None, {})])
    with pytest.raises(UploadError):
        upload_video(client, f, "t", "d", ["a"])


def test_upload_missing_file_raises(tmp_path):
    with pytest.raises(UploadError, match="not found"):
        upload_video(fake_client([]), tmp_path / "nope.mp4", "t", "d", [])


def test_post_comment_sends_expected_body():
    client = MagicMock()
    post_comment(client, "vid1", "assalam")
    body = client.commentThreads.return_value.insert.call_args.kwargs["body"]
    assert body["snippet"]["videoId"] == "vid1"
    assert (body["snippet"]["topLevelComment"]["snippet"]["textOriginal"]
            == "assalam")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_youtube.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.youtube'`

- [ ] **Step 3: Write `src/adkar_bot/youtube.py`**

```python
import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config

TOKEN_URI = "https://oauth2.googleapis.com/token"
RETRYABLE = {429, 500, 502, 503, 504}


class UploadError(RuntimeError):
    pass


def build_client(client_id: str, client_secret: str, refresh_token: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client_id,
        client_secret=client_secret,
        scopes=config.SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(client, path: Path, title: str, description: str,
                 tags: list[str]) -> str:
    path = Path(path)
    if not path.exists():
        raise UploadError(f"video file not found: {path}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": config.CATEGORY_ID,
        },
        # Google forces private for unverified apps regardless of this value.
        "status": {"privacyStatus": config.PRIVACY_STATUS,
                   "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(path), chunksize=4 * 1024 * 1024, resumable=True)
    request = client.videos().insert(part="snippet,status", body=body,
                                     media_body=media)

    response, attempt = None, 0
    while response is None:
        try:
            _status, response = request.next_chunk()
        except HttpError as exc:
            if exc.resp.status not in RETRYABLE or attempt >= 5:
                raise UploadError(f"upload failed: {exc}") from exc
            attempt += 1
            time.sleep(2 ** attempt)

    video_id = (response or {}).get("id")
    if not video_id:
        raise UploadError(f"upload returned no video id: {response!r}")
    return video_id


def post_comment(client, video_id: str, text: str) -> None:
    """Post a top-level comment.

    The Data API has no endpoint for pinning; pinning stays manual.
    """
    client.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }
        },
    ).execute()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_youtube.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/youtube.py tests/test_youtube.py
git commit -m "feat: YouTube upload and comment client"
```

---

### Task 9: Pipeline CLI

**Files:**
- Create: `src/adkar_bot/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: every module above
- Produces: `main(argv) -> int`, subcommands `render` and `publish`

`publish` persists state **only after** a successful upload. A failed comment
post is logged and does not roll back the upload or the state write.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
from unittest.mock import MagicMock, patch
from adkar_bot import cli
from adkar_bot.selector import State, load_state


def test_failed_upload_does_not_consume_an_entry(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(cli.config, "STATE_PATH", state_path)
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE", "@adkar")

    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "upload_video", side_effect=RuntimeError("boom")):
        assert cli.main(["publish"]) != 0

    assert not state_path.exists()


def test_comment_failure_still_persists_state(tmp_path, monkeypatch):
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(cli.config, "STATE_PATH", state_path)
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE", "@adkar")

    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "upload_video", return_value="vid42"), \
         patch.object(cli, "post_comment", side_effect=RuntimeError("nope")):
        assert cli.main(["publish"]) == 0

    state = load_state(state_path)
    assert len(state.used) == 1
    assert state.published[0]["video_id"] == "vid42"


def test_publish_refuses_placeholder_handle(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.config, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(cli.config, "CHANNEL_HANDLE",
                        cli.config.CHANNEL_HANDLE_PLACEHOLDER)
    assert cli.main(["publish"]) != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.cli'`

- [ ] **Step 3: Write `src/adkar_bot/cli.py`**

```python
import argparse
import logging
import os
import sys
from datetime import datetime, timezone

from . import config
from .config import ConfigError, assert_configured
from .corpus import load_corpus
from .metadata import build_comment, build_description, build_tags, build_title
from .render import render
from .selector import load_state, next_dhikr, record, save_state
from .youtube import build_client, post_comment, upload_video

log = logging.getLogger("adkar_bot")


def _pick():
    corpus = load_corpus(config.CORPUS_PATH)
    state = load_state(config.STATE_PATH)
    return corpus, state, next_dhikr(corpus, state)


def cmd_render(_args) -> int:
    _corpus, _state, dhikr = _pick()
    out = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4")
    log.info("rendered %s -> %s", dhikr.id, out)
    return 0


def cmd_publish(_args) -> int:
    assert_configured()
    corpus, state, dhikr = _pick()
    video = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4")

    client = build_client(
        os.environ["YT_CLIENT_ID"],
        os.environ["YT_CLIENT_SECRET"],
        os.environ["YT_REFRESH_TOKEN"],
    )
    video_id = upload_video(
        client, video,
        build_title(dhikr), build_description(dhikr), build_tags(dhikr),
    )
    log.info("uploaded %s as %s (private)", dhikr.id, video_id)

    try:
        post_comment(client, video_id, build_comment(dhikr))
    except Exception:
        # The upload succeeded; never retry it just because the comment failed.
        log.warning("comment failed for %s; post it manually", video_id,
                    exc_info=True)

    now = datetime.now(timezone.utc).isoformat()
    save_state(record(state, dhikr, video_id, now, corpus=corpus),
               config.STATE_PATH)
    log.info("state saved; publish and pin %s manually", video_id)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="adkar-bot")
    subs = parser.add_subparsers(dest="cmd", required=True)
    subs.add_parser("render").set_defaults(func=cmd_render)
    subs.add_parser("publish").set_defaults(func=cmd_publish)
    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except ConfigError as exc:
        log.error("%s", exc)
        return 2
    except Exception:
        log.exception("run failed; state not modified")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the full suite**

Run: `py -3 -m pytest -v`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/cli.py tests/test_cli.py
git commit -m "feat: render and publish pipeline CLI"
```

---

### Task 10: OAuth bootstrap, workflow, and README

**Files:**
- Create: `scripts/authorize.py`, `.github/workflows/publish.yml`, `README.md`

**Interfaces:**
- Consumes: `config.SCOPES`
- Produces: nothing importable; this task wires the system for unattended runs.

- [ ] **Step 1: Write `scripts/authorize.py`**

```python
"""One-time local OAuth bootstrap.

Run on your own machine, not in CI:
    py -3 scripts/authorize.py client_secret.json
Then copy the printed refresh token into the GitHub repository secrets.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    # access_type=offline + prompt=consent is what actually returns a refresh
    # token. Without prompt=consent, a re-auth returns none.
    creds = flow.run_local_server(
        port=0, access_type="offline", prompt="consent"
    )

    print("\nAdd these as GitHub repository secrets:\n")
    print(f"YT_CLIENT_ID     = {flow.client_config['client_id']}")
    print(f"YT_CLIENT_SECRET = {flow.client_config['client_secret']}")
    print(f"YT_REFRESH_TOKEN = {creds.refresh_token}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write `.github/workflows/publish.yml`**

```yaml
name: publish

on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch:

concurrency:
  group: publish
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: sudo apt-get update && sudo apt-get install -y ffmpeg
      - run: pip install -e ".[dev]"
      - run: pytest -v
        env:
          CHANNEL_HANDLE: ${{ vars.CHANNEL_HANDLE }}

  publish:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: sudo apt-get update && sudo apt-get install -y ffmpeg
      - run: pip install -e .
      - run: python -m adkar_bot.cli publish
        env:
          CHANNEL_HANDLE: ${{ vars.CHANNEL_HANDLE }}
          YT_CLIENT_ID: ${{ secrets.YT_CLIENT_ID }}
          YT_CLIENT_SECRET: ${{ secrets.YT_CLIENT_SECRET }}
          YT_REFRESH_TOKEN: ${{ secrets.YT_REFRESH_TOKEN }}
      - name: Commit rotation state
        run: |
          git config user.name  "adkar-bot"
          git config user.email "adkar-bot@users.noreply.github.com"
          git add data/state.json
          git diff --staged --quiet || git commit -m "chore: rotation state [skip ci]"
          git push
```

- [ ] **Step 3: Write `README.md`**

Must document, in this order:

1. **Google Cloud setup** — create a project, enable YouTube Data API v3,
   configure the OAuth consent screen, and set publishing status to
   **In production**. In *Testing* status refresh tokens expire after 7 days
   and the cron job dies weekly. Create an OAuth client of type **Desktop app**.
2. **Bootstrap** — `py -3 scripts/authorize.py client_secret.json`, then add
   `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` as repository
   *secrets* and `CHANNEL_HANDLE` as a repository *variable*.
3. **The two manual steps per video** — every upload lands **private** because
   the app is unverified, and the API cannot pin comments. So in YouTube Studio
   you flip the video to public and pin the bot's comment. Both take seconds.
4. **Local usage** — `py -3 -m adkar_bot.cli render` writes an MP4 to
   `output/` without touching the network or state.
5. **Growing the corpus** — append entries to `data/adkar.json` with unique
   ids; validation and layout tests cover new entries automatically.
6. **Quota** — 10,000 units/day, 1,650 per run, so roughly six runs/day is the
   ceiling.

- [ ] **Step 4: Verify the workflow file parses**

Run: `py -3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/publish.yml')); print('ok')"`
Expected: `ok` (install with `py -3 -m pip install pyyaml` if needed)

- [ ] **Step 5: Run the full suite one last time**

Run: `py -3 -m pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add scripts .github README.md
git commit -m "feat: OAuth bootstrap, scheduled workflow, and setup docs"
```

---

## Manual verification before the first real run

Automated tests do not cover these:

1. Open a rendered MP4 and confirm Arabic letterforms connect, read
   right-to-left, and retain tashkeel.
2. Confirm no text falls under the Shorts action rail or the bottom overlay.
3. Verify every `text` and `reference` in `data/adkar.json` against a
   scholarly-reviewed edition of Hisn al-Muslim.
4. Trigger the workflow with `workflow_dispatch` once and confirm the video
   appears as private on the channel with the comment posted.
