# Two-Channel Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single mixed rotation into two independently scheduled YouTube channels — hadith on `@ZainKhairAllahChannel`, adkar on `@DIKR-o6k` — sharing one render implementation.

**Architecture:** A frozen `Profile` dataclass holds the eight values that differ per channel (corpus, state, handle, gradient, tags, hashtags, count, credential prefix). `cli.py` resolves one profile per run and threads it explicitly into render, metadata and upload. Everything identical between channels stays as module constants in `config.py`. Two workflow files run the same code with different profiles and different secrets.

**Tech Stack:** Python 3.12, Pillow, ffmpeg/ffprobe, google-api-python-client, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-15-two-channel-split-design.md`

## Global Constraints

- **The hadith profile must be a behavioural no-op for the live channel.** It inherits today's exact gradient `((14,34,48),(6,12,20))`, today's count `6`, and today's credential names `YT_CLIENT_ID`/`YT_CLIENT_SECRET`/`YT_REFRESH_TOKEN`. Any diff that changes what `@ZainKhairAllahChannel` publishes is a bug.
- **No module-level profile global.** The profile is resolved once in `cli.py` and passed as a parameter. Never `profiles.CURRENT`, never an import-time branch on `os.environ["PROFILE"]`. Getting away from import-time global state is the reason this design exists.
- **`--profile` has no default.** Omitting it is an error, not a fallback. A default here means a wrong-channel upload when someone forgets the flag.
- **Arabic strings are copied verbatim** from this plan. Do not retype them, do not "fix" the spacing, do not reorder. Copy-paste the exact bytes.
- **Any Arabic drawn to a frame must go through `arabic.shape()`** before `draw.text()`. The fonts load with `Layout.BASIC`, which does no joining; unshaped Arabic renders as disconnected backwards letterforms.
- **`git mv`/`git rm` for tracked files**, so renames and deletions are recorded rather than appearing as an add plus an untracked leftover.
- Run the suite with `py -3 -m pytest` on Windows. Plain `python` is not on PATH — it resolves to the Microsoft Store shim.
- Python's default stdout encoding here is cp1252. Any script that prints Arabic needs `PYTHONIOENCODING=utf-8` set, or it dies with `UnicodeEncodeError`.

---

### Task 1: The `Profile` type

**Files:**
- Create: `src/adkar_bot/profiles.py`
- Test: `tests/test_profiles.py`

**Interfaces:**
- Consumes: `config.DATA_DIR` (existing).
- Produces: `Profile` (frozen dataclass), `HADITH`, `ADKAR`, `PROFILES: dict[str, Profile]`. Field names — `name, corpus_path, state_path, channel_handle, gradient, base_tags, hashtags, default_count, env_prefix` — are used verbatim by Tasks 3-6.

- [ ] **Step 1: Write the failing test**

Create `tests/test_profiles.py`:

```python
from adkar_bot.profiles import ADKAR, HADITH, PROFILES


def test_each_profile_name_matches_its_key():
    for key, profile in PROFILES.items():
        assert profile.name == key


def test_profiles_share_no_paths_handles_or_credentials():
    """Two channels that share any of these are one channel with a bug."""
    for field in ("corpus_path", "state_path", "channel_handle", "env_prefix"):
        values = [getattr(p, field) for p in PROFILES.values()]
        assert len(set(values)) == len(values), f"{field} collides across profiles"


def test_base_tags_is_immutable():
    """A list default inside a frozen dataclass is frozen in name only:
    profile.base_tags.append(...) would mutate the shared class-level value
    for every later caller in the process."""
    for profile in PROFILES.values():
        assert isinstance(profile.base_tags, tuple)


def test_hadith_profile_preserves_the_live_channels_appearance():
    """@ZainKhairAllahChannel already has videos published with this exact
    gradient. The split must not restyle a channel that is already running."""
    assert HADITH.gradient == ((14, 34, 48), (6, 12, 20))
    assert HADITH.env_prefix == "YT"
    assert HADITH.default_count == 6


def test_adkar_profile_is_distinct_and_paced_for_a_206_entry_corpus():
    assert ADKAR.gradient != HADITH.gradient
    assert ADKAR.env_prefix == "YT_ADKAR"
    assert ADKAR.default_count == 1
    assert ADKAR.channel_handle == "@DIKR-o6k"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_profiles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'adkar_bot.profiles'`

- [ ] **Step 3: Write minimal implementation**

Create `src/adkar_bot/profiles.py`:

```python
"""Per-channel settings. Everything identical between channels lives in
config.py; only what genuinely differs is here.

Two profiles, both authored in this repo, both changing about never - so
they are literals in a module rather than JSON loaded and validated at
runtime. A typo fails at import, which is the strongest failure mode
available and costs nothing.
"""
from dataclasses import dataclass
from pathlib import Path

from . import config

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Profile:
    name: str
    corpus_path: Path
    state_path: Path
    channel_handle: str
    gradient: tuple[RGB, RGB]   # (top, bottom)
    # A tuple, not a list. The dataclass is frozen, but a mutable default
    # inside it is frozen in name only - one caller appending would corrupt
    # the value for every later caller in the process.
    base_tags: tuple[str, ...]
    hashtags: str               # description footer line
    default_count: int
    env_prefix: str             # credentials are read as f"{env_prefix}_CLIENT_ID" etc.


# Inherits the running channel's exact gradient, count and credential names,
# so the split is provably a no-op for the channel that is already live.
HADITH = Profile(
    name="hadith",
    corpus_path=config.DATA_DIR / "hadith.json",
    state_path=config.DATA_DIR / "state-hadith.json",
    channel_handle="@ZainKhairAllahChannel",
    gradient=((14, 34, 48), (6, 12, 20)),
    base_tags=("حديث", "أحاديث", "صحيح البخاري", "صحيح مسلم", "السنة",
               "hadith", "sunnah", "shorts"),
    hashtags="#shorts #حديث #السنة",
    default_count=6,
    env_prefix="YT",
)

# default_count is 1, not 6: the Hisn corpus is 206 entries, which at 6/day
# cycles in 34 days. At 1/day it lasts ~7 months, which is the runway for
# growing the corpus (Project B) before anything repeats.
ADKAR = Profile(
    name="adkar",
    corpus_path=config.DATA_DIR / "adkar.json",
    state_path=config.DATA_DIR / "state-adkar.json",
    channel_handle="@DIKR-o6k",
    gradient=((16, 44, 34), (6, 18, 14)),
    base_tags=("أذكار", "أدعية", "ذكر", "دعاء", "إسلام",
               "adkar", "dua", "shorts"),
    hashtags="#shorts #أذكار #أدعية",
    default_count=1,
    env_prefix="YT_ADKAR",
)

PROFILES: dict[str, Profile] = {p.name: p for p in (HADITH, ADKAR)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_profiles.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/profiles.py tests/test_profiles.py
git commit -m "feat: add Profile type with hadith and adkar profiles"
```

---

### Task 2: Split the corpus and the rotation state

**Files:**
- Create: `scripts/split_corpus.py`
- Create: `tests/test_corpus_split.py`
- Modify: `scripts/import_hadith.py` (the `ADKAR` constant and its two uses)
- Data: writes `data/hadith.json`, rewrites `data/adkar.json`, writes `data/state-hadith.json` and `data/state-adkar.json`, deletes `data/state.json`

**Interfaces:**
- Consumes: nothing from Task 1 (the script hardcodes paths; it runs once and is then history).
- Produces: the four data files that Task 1's profiles already point at.

**Context an engineer needs:** `data/adkar.json` currently holds 7,888 entries — 206 `hisn-*`, 4,066 `bukhari-*`, 3,616 `muslim-*`. `data/state.json` holds 33 used ids, all `hisn-*`, and 33 publish records. Under the new mapping those 33 are adkar videos sitting on the hadith channel, so the state split is deliberately **not** a clean partition: hadith keeps the publish history but starts with `used: []`, and adkar starts completely empty so all 206 entries are available to a channel that has shown none of them.

- [ ] **Step 1: Write the failing test**

Create `tests/test_corpus_split.py`:

```python
import json

from adkar_bot import config
from adkar_bot.profiles import ADKAR, HADITH


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_each_corpus_holds_only_its_own_texts():
    adkar_ids = {e["id"] for e in _load(ADKAR.corpus_path)}
    hadith_ids = {e["id"] for e in _load(HADITH.corpus_path)}
    assert all(i.startswith("hisn-") for i in adkar_ids)
    assert all(i.startswith(("bukhari-", "muslim-")) for i in hadith_ids)


def test_the_two_corpora_are_disjoint():
    adkar_ids = {e["id"] for e in _load(ADKAR.corpus_path)}
    hadith_ids = {e["id"] for e in _load(HADITH.corpus_path)}
    assert adkar_ids.isdisjoint(hadith_ids)


def test_nothing_was_lost_in_the_split():
    """7,888 entries went in; 7,888 must come out. A partition that drops
    entries is the one failure mode here that is silent and unrecoverable."""
    total = len(_load(ADKAR.corpus_path)) + len(_load(HADITH.corpus_path))
    assert total == 7888


def test_the_mixed_state_file_is_gone():
    assert not (config.DATA_DIR / "state.json").exists()


def test_neither_channel_starts_with_entries_marked_used():
    """No hadith has ever published, and @DIKR-o6k has published nothing at
    all - so all 206 adkar must still be available to it."""
    for profile in (ADKAR, HADITH):
        assert _load(profile.state_path)["used"] == []


def test_the_hadith_channel_keeps_its_publish_history():
    """The 33 already-uploaded videos went out through that channel's
    credentials. The record of them is the only audit trail of what is on
    the channel, so it survives the split even though the ids no longer
    appear in that profile's corpus."""
    published = _load(HADITH.state_path)["published"]
    assert len(published) == 33
    assert all(record["id"].startswith("hisn-") for record in published)


def test_the_new_channel_starts_with_no_history():
    assert _load(ADKAR.state_path)["published"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_corpus_split.py -v`
Expected: FAIL — `data/hadith.json` does not exist, so `_load(HADITH.corpus_path)` raises `FileNotFoundError`.

- [ ] **Step 3: Write the split script**

Create `scripts/split_corpus.py`:

```python
"""One-off: split the mixed corpus and rotation state into two profiles.

Run once:  py -3 scripts/split_corpus.py

data/adkar.json holds 7,888 entries from three sources. After this it holds
only the 206 Hisn al-Muslim adkar; the 7,682 Bukhari and Muslim entries move
to data/hadith.json.

The state split is deliberately not a clean partition. data/state.json's 33
used ids are all hisn-*, but those videos are on the hadith channel. So:
hadith keeps the publish records (the only audit trail of what is on that
channel) but starts with used: [], because no hadith has ever published;
adkar starts empty, because @DIKR-o6k has published nothing and all 206
entries should be available to it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _write(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    source = DATA / "adkar.json"
    corpus = json.loads(source.read_text(encoding="utf-8"))

    hisn = [e for e in corpus if e["id"].startswith("hisn-")]
    hadith = [e for e in corpus if e["id"].startswith(("bukhari-", "muslim-"))]

    # Refuse rather than partition partially. Writing adkar.json is
    # destructive - anything matching neither prefix would be deleted with no
    # copy anywhere, and nothing downstream would ever notice.
    if len(hisn) + len(hadith) != len(corpus):
        known = {e["id"] for e in hisn} | {e["id"] for e in hadith}
        stray = sorted({e["id"] for e in corpus} - known)
        print(f"refusing to split: {len(stray)} entries match no known id "
              f"prefix, e.g. {stray[:5]}", file=sys.stderr)
        return 1

    _write(DATA / "hadith.json", hadith)
    _write(source, hisn)

    old_state = DATA / "state.json"
    history = []
    if old_state.exists():
        history = json.loads(old_state.read_text(encoding="utf-8")).get("published", [])
    _write(DATA / "state-hadith.json",
           {"cycle": 0, "used": [], "published": history})
    _write(DATA / "state-adkar.json",
           {"cycle": 0, "used": [], "published": []})
    old_state.unlink(missing_ok=True)

    print(f"hadith {len(hadith)} | adkar {len(hisn)} | "
          f"history preserved on hadith {len(history)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run the split**

```bash
py -3 scripts/split_corpus.py
```

Expected output exactly: `hadith 7682 | adkar 206 | history preserved on hadith 33`

If it prints `refusing to split`, stop — the corpus contains an id prefix this plan did not anticipate. Do not edit the guard away; report it.

- [ ] **Step 5: Retarget the hadith importer**

In `scripts/import_hadith.py`, the constant on line 25 currently reads:

```python
ADKAR = ROOT / "data" / "adkar.json"
```

Replace it with:

```python
# The hadith corpus, not data/adkar.json: since the two-channel split, the
# adkar file holds only Hisn al-Muslim and this importer never touches it.
HADITH = ROOT / "data" / "hadith.json"
```

Then in `main()`, change the one read from it:

```python
    existing = json.loads(ADKAR.read_text(encoding="utf-8"))
```

to:

```python
    existing = json.loads(HADITH.read_text(encoding="utf-8"))
```

Then find the remaining `ADKAR` in `main()` — the write near the end of the function — and change it to `HADITH` the same way. Verify none are left:

```bash
grep -n "ADKAR" scripts/import_hadith.py
```

Expected: no output.

- [ ] **Step 6: Run the tests**

Run: `py -3 -m pytest tests/test_corpus_split.py tests/test_import_hadith.py -v`
Expected: PASS. `tests/test_import_hadith.py` loads the module by path and exercises `convert()`/`MATN`/`XREF` only — it never referenced the constant you renamed, so it should be unaffected. If it fails, the rename hit something this plan missed; fix it rather than reverting the rename.

- [ ] **Step 7: Run the whole suite**

Run: `py -3 -m pytest -q`
Expected: PASS. Nothing else reads `data/state.json` (a missing state file makes `load_state` return a fresh `State()`), and `config.CORPUS_PATH` still points at `data/adkar.json`, which is now the 206 adkar — so `conftest.corpus_sample()` keeps working, just over a smaller corpus. Task 7 rewires it.

- [ ] **Step 8: Commit**

```bash
git add scripts/split_corpus.py scripts/import_hadith.py tests/test_corpus_split.py data/hadith.json data/adkar.json data/state-hadith.json data/state-adkar.json
git rm --cached data/state.json
git commit -m "feat: split corpus and rotation state into adkar and hadith"
```

---

### Task 3: Per-profile metadata

**Files:**
- Modify: `src/adkar_bot/metadata.py`
- Test: `tests/test_metadata.py`

**Interfaces:**
- Consumes: `profiles.Profile` — fields `channel_handle`, `base_tags`, `hashtags`.
- Produces: `build_description(dhikr, profile) -> str`, `build_tags(dhikr, profile) -> list[str]`. `build_title(dhikr) -> str` is unchanged and stays single-argument — the title is the text plus `#shorts`, with nothing channel-specific in it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_metadata.py`, and add `from adkar_bot.profiles import ADKAR, HADITH` to its imports:

```python
def test_description_carries_the_profiles_own_handle_and_hashtags():
    assert ADKAR.channel_handle in build_description(SHORT, ADKAR)
    assert ADKAR.hashtags in build_description(SHORT, ADKAR)
    assert HADITH.channel_handle in build_description(SHORT, HADITH)
    assert HADITH.hashtags in build_description(SHORT, HADITH)


def test_a_description_never_advertises_the_other_channel():
    assert HADITH.channel_handle not in build_description(SHORT, ADKAR)
    assert ADKAR.channel_handle not in build_description(SHORT, HADITH)


def test_tags_come_from_the_profile():
    assert set(HADITH.base_tags).issubset(build_tags(SHORT, HADITH))
    assert set(ADKAR.base_tags).issubset(build_tags(SHORT, ADKAR))


def test_building_tags_does_not_mutate_the_profile():
    """build_tags returns a list; if it returned the profile's own storage,
    a caller appending to the result would corrupt every later run in the
    process."""
    before = HADITH.base_tags
    build_tags(SHORT, HADITH).append("sabotage")
    assert HADITH.base_tags == before
```

Then update the four existing tests that call the changed functions:

```python
def test_description_carries_attribution():
    desc = build_description(SHORT, ADKAR)
    assert SHORT.text in desc
    assert SHORT.source in desc
    assert SHORT.reference in desc


def test_tags_include_category_and_are_unique():
    tags = build_tags(SHORT, ADKAR)
    assert SHORT.category in tags
    assert len(tags) == len(set(tags))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_metadata.py -v`
Expected: FAIL — `build_description() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Write minimal implementation**

In `src/adkar_bot/metadata.py`: delete the `BASE_TAGS` constant and the `from . import config` import, add `from .profiles import Profile`, and replace the two functions:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_metadata.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/metadata.py tests/test_metadata.py
git commit -m "feat: build description and tags from the active profile"
```

Note: `py -3 -m pytest -q` still fails at this point — `cli.py` calls `build_description(dhikr)` with one argument. Task 6 fixes it. Commit anyway; the suite is green again at Task 6.

---

### Task 4: Per-profile gradient and handle

**Files:**
- Modify: `src/adkar_bot/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `profiles.Profile` — fields `gradient`, `channel_handle`.
- Produces: `gradient_background(profile) -> Image`, `render(dhikr, out_path, profile) -> Path`. `_handle_layer(profile)` is private.

- [ ] **Step 1: Write the failing test**

In `tests/test_render.py`, add `from adkar_bot.profiles import ADKAR, HADITH` to the imports, change the existing `test_gradient_is_frame_sized` to pass a profile, and add two tests:

```python
def test_gradient_is_frame_sized():
    assert gradient_background(HADITH).size == (config.WIDTH, config.HEIGHT)


def test_each_profile_paints_its_own_gradient():
    """The two channels have to be tellable apart at a glance."""
    a = gradient_background(ADKAR).getpixel((540, 100))
    h = gradient_background(HADITH).getpixel((540, 100))
    assert a != h


def test_the_gradient_top_row_is_the_profiles_top_colour():
    """Guards the orientation: a flipped gradient still differs between
    profiles, so the test above would pass while the frame was upside down."""
    assert gradient_background(HADITH).getpixel((0, 0)) == HADITH.gradient[0]
    assert gradient_background(ADKAR).getpixel((0, 0)) == ADKAR.gradient[0]
```

Then update every other `render(...)` call in the file to pass a profile. There are six, at roughly lines 78, 158, 177, 178, 191 and 212 — for example:

```python
    out = render(DHIKR, tmp_path / "out.mp4", HADITH)
```

Find them all with `grep -n "render(DHIKR\|render(other" tests/test_render.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_render.py -v`
Expected: FAIL — `gradient_background() takes 0 positional arguments but 1 was given`

- [ ] **Step 3: Write minimal implementation**

In `src/adkar_bot/render.py`, add `from .profiles import Profile` to the imports and change three functions.

`gradient_background`:

```python
def gradient_background(profile: Profile) -> Image.Image:
    """Vertical linear gradient, drawn one row at a time."""
    img = Image.new("RGB", (config.WIDTH, config.HEIGHT))
    draw = ImageDraw.Draw(img)
    top, bottom = profile.gradient
    for y in range(config.HEIGHT):
        t = y / (config.HEIGHT - 1)
        draw.line(
            [(0, y), (config.WIDTH, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return img
```

`_handle_layer` — take the profile and read the handle from it. Change the signature to `def _handle_layer(profile: Profile) -> Image.Image:` and the one `config.CHANNEL_HANDLE` reference inside it to `profile.channel_handle`. Everything else in that function, including the `shape(config.LIKE_TEXT)` call for the CTA, is unchanged: the CTA is the same on both channels.

`render` — take the profile and pass it to the two calls that now need it. Change the signature to `def render(dhikr: Dhikr, out_path: Path, profile: Profile) -> Path:`, then inside:

```python
        gradient_background(profile).save(bg)
```

and

```python
        _handle_layer(profile).save(handle)
```

Nothing else in `render` changes.

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_render.py -v`
Expected: PASS. This suite shells out to ffmpeg and takes a couple of minutes.

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/render.py tests/test_render.py
git commit -m "feat: render the gradient and handle from the active profile"
```

---

### Task 5: Verify the authenticated channel before uploading

**Files:**
- Modify: `src/adkar_bot/youtube.py`
- Modify: `src/adkar_bot/config.py` (the `SCOPES` constant only)
- Test: `tests/test_youtube.py`

**Interfaces:**
- Consumes: `profiles.Profile` — field `channel_handle`.
- Produces: `verify_channel(client, profile) -> None`, raising `WrongChannel` (a subclass of `UploadError`) on mismatch. Task 6 calls it once per run, before the first upload.

**Context an engineer needs:** this is the second of two layered guards against publishing to the wrong channel. `channels.list` costs 1 quota unit against the 10,000/day budget, so calling it once per run is free in practice next to `videos.insert` at 1,600. The API returns the handle in `snippet.customUrl`, sometimes with a leading `@` and sometimes without, and case is not guaranteed — so both sides are normalised rather than compared raw.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_youtube.py`. It already has imports of its own — merge
these into them rather than adding a second import block partway down the
file:

```python
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from adkar_bot.profiles import ADKAR, HADITH
from adkar_bot.youtube import WrongChannel, verify_channel


def _client_returning(custom_url):
    client = MagicMock()
    client.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"snippet": {"customUrl": custom_url}}]
    }
    return client


def _client_raising(status):
    client = MagicMock()
    response = MagicMock()
    response.status = status
    client.channels.return_value.list.return_value.execute.side_effect = (
        HttpError(response, b"{}")
    )
    return client


def test_matching_handle_passes():
    assert verify_channel(_client_returning("@DIKR-o6k"), ADKAR) is None


def test_handle_without_the_at_sign_passes():
    """customUrl comes back both ways depending on the response; neither
    form means the credentials are wrong."""
    assert verify_channel(_client_returning("DIKR-o6k"), ADKAR) is None


def test_handle_in_a_different_case_passes():
    assert verify_channel(_client_returning("@dikr-o6k"), ADKAR) is None


def test_the_other_channels_handle_is_rejected():
    with pytest.raises(WrongChannel, match="DIKR-o6k"):
        verify_channel(_client_returning("@ZainKhairAllahChannel"), ADKAR)


def test_a_similar_but_different_handle_is_rejected():
    """Substring matching would accept this. It must not."""
    with pytest.raises(WrongChannel):
        verify_channel(_client_returning("@DIKR-o6k-backup"), ADKAR)


def test_an_empty_item_list_is_rejected_rather_than_passed():
    client = MagicMock()
    client.channels.return_value.list.return_value.execute.return_value = {"items": []}
    with pytest.raises(WrongChannel):
        verify_channel(client, HADITH)


def test_insufficient_scope_says_to_re_authorize():
    """This is exactly what a refresh token minted before youtube.readonly
    was added to SCOPES looks like. The message has to name the fix."""
    with pytest.raises(WrongChannel, match="authorize"):
        verify_channel(_client_raising(403), HADITH)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_youtube.py -v`
Expected: FAIL — `ImportError: cannot import name 'WrongChannel' from 'adkar_bot.youtube'`

- [ ] **Step 3: Write minimal implementation**

In `src/adkar_bot/config.py`, change `SCOPES`:

```python
# youtube.readonly is needed by channels.list, which verify_channel uses to
# confirm the refresh token belongs to the profile's channel before spending
# 1,600 quota units uploading to the wrong one. Adding it invalidates every
# refresh token minted under the old scope list: both channels must re-run
# scripts/authorize.py once. See the migration notes in the README.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
```

In `src/adkar_bot/youtube.py`, add `from .profiles import Profile` to the imports and append:

```python
class WrongChannel(UploadError):
    """The authenticated channel is not the profile's channel."""


def _normalise(handle: str) -> str:
    """@DIKR-o6k, DIKR-o6k and @dikr-o6k are the same channel.

    customUrl is returned with the leading @ in some responses and without it
    in others, and its case is not guaranteed.
    """
    return handle.strip().lstrip("@").casefold()


def verify_channel(client, profile: Profile) -> None:
    """Abort unless the credentials belong to `profile`'s channel.

    Costs 1 quota unit against the 10,000/day budget - nothing beside the
    1,600 an upload costs, and it is the only thing standing between a
    mis-set refresh token and a video published to the wrong channel.
    """
    try:
        response = client.channels().list(part="snippet", mine=True).execute()
    except HttpError as exc:
        if exc.resp.status == 403:
            raise WrongChannel(
                f"not allowed to read the channel for profile "
                f"{profile.name!r}: {exc}. A refresh token minted before "
                f"youtube.readonly was added to SCOPES looks exactly like "
                f"this - re-run scripts/authorize.py and replace the stored "
                f"{profile.env_prefix}_REFRESH_TOKEN."
            ) from exc
        raise WrongChannel(
            f"could not verify the channel for profile {profile.name!r}: {exc}"
        ) from exc

    items = response.get("items") or []
    if not items:
        raise WrongChannel(
            f"the credentials for profile {profile.name!r} are not attached "
            f"to any channel; expected {profile.channel_handle}"
        )

    actual = items[0].get("snippet", {}).get("customUrl", "")
    if _normalise(actual) != _normalise(profile.channel_handle):
        raise WrongChannel(
            f"profile {profile.name!r} publishes to "
            f"{profile.channel_handle}, but these credentials belong to "
            f"{actual or '(a channel with no handle)'}. Refusing to upload."
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_youtube.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/adkar_bot/youtube.py src/adkar_bot/config.py tests/test_youtube.py
git commit -m "feat: refuse to upload when the token is not the profile's channel"
```

---

### Task 6: Profile-driven CLI

**Files:**
- Modify: `src/adkar_bot/cli.py`
- Modify: `src/adkar_bot/config.py` (`assert_configured` signature and body)
- Modify: `tests/conftest.py` (the `_yt_oauth_env` fixture)
- Test: `tests/test_cli.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `PROFILES` (Task 1), `build_description`/`build_tags` (Task 3), `render` (Task 4), `verify_channel`/`WrongChannel` (Task 5).
- Produces: `adkar-bot render --profile {adkar,hadith}` and `adkar-bot publish --profile {adkar,hadith} [--count N]`. This is the task that makes `py -3 -m pytest -q` green again.

- [ ] **Step 1: Write the failing test**

In `tests/conftest.py`, extend the autouse fixture so `_require_env` stays quiet for either profile:

```python
    monkeypatch.setenv("YT_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("YT_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("YT_REFRESH_TOKEN", "test-refresh-token")
    monkeypatch.setenv("YT_ADKAR_CLIENT_ID", "test-adkar-client-id")
    monkeypatch.setenv("YT_ADKAR_CLIENT_SECRET", "test-adkar-client-secret")
    monkeypatch.setenv("YT_ADKAR_REFRESH_TOKEN", "test-adkar-refresh-token")
```

Replace the whole body of `tests/test_cli.py` with:

```python
from unittest.mock import MagicMock, patch

from adkar_bot import cli
from adkar_bot.profiles import ADKAR, HADITH


def _isolate(monkeypatch, tmp_path, profile):
    """Point a profile's state at a temp file without touching the real one."""
    import dataclasses
    isolated = dataclasses.replace(profile, state_path=tmp_path / "state.json")
    monkeypatch.setitem(cli.PROFILES, profile.name, isolated)
    return isolated


def test_publish_requires_a_profile(tmp_path, monkeypatch):
    """No default: forgetting the flag must not pick a channel for you."""
    monkeypatch.delenv("PROFILE", raising=False)
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish"]) == 2
    fake_render.assert_not_called()


def test_an_unknown_profile_name_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("PROFILE", "nasai")
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish"]) == 2
    fake_render.assert_not_called()


def test_the_profile_env_var_is_honoured(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path, ADKAR)
    monkeypatch.setenv("PROFILE", "adkar")
    monkeypatch.setattr(cli.config, "OUTPUT_DIR", tmp_path)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4") as fake_render:
        assert cli.main(["render"]) == 0
    assert fake_render.call_args.args[2].name == "adkar"


def test_failed_upload_does_not_consume_an_entry(tmp_path, monkeypatch):
    isolated = _isolate(monkeypatch, tmp_path, HADITH)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel"), \
         patch.object(cli, "upload_video", side_effect=RuntimeError("boom")):
        assert cli.main(["publish", "--profile", "hadith"]) != 0
    assert not isolated.state_path.exists()


def test_publish_fails_cleanly_when_a_secret_is_missing(tmp_path, monkeypatch):
    _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.delenv("YT_REFRESH_TOKEN", raising=False)
    assert cli.main(["publish", "--profile", "hadith"]) == 2


def test_each_profile_reads_only_its_own_credentials(tmp_path, monkeypatch):
    """Guard 1. With the hadith credentials present and the adkar ones gone,
    a run of the adkar profile must fail rather than quietly authenticate as
    the other channel."""
    _isolate(monkeypatch, tmp_path, ADKAR)
    monkeypatch.delenv("YT_ADKAR_CLIENT_ID", raising=False)
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish", "--profile", "adkar"]) == 2
    fake_render.assert_not_called()


def test_the_missing_credential_is_named_in_the_error(tmp_path, monkeypatch, caplog):
    _isolate(monkeypatch, tmp_path, ADKAR)
    monkeypatch.delenv("YT_ADKAR_CLIENT_ID", raising=False)
    with caplog.at_level("ERROR"):
        cli.main(["publish", "--profile", "adkar"])
    assert "YT_ADKAR_CLIENT_ID" in caplog.text


def test_publish_checks_secrets_before_rendering(tmp_path, monkeypatch):
    """A misconfigured run must not spend ~20s in ffmpeg first."""
    _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.delenv("YT_CLIENT_ID", raising=False)
    with patch.object(cli, "render") as fake_render:
        assert cli.main(["publish", "--profile", "hadith"]) == 2
    fake_render.assert_not_called()


def test_the_channel_is_verified_before_anything_is_rendered(tmp_path, monkeypatch):
    """Guard 2 is worth nothing if it fires after 1,600 units are spent."""
    _isolate(monkeypatch, tmp_path, HADITH)
    from adkar_bot.youtube import WrongChannel
    with patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel", side_effect=WrongChannel("nope")), \
         patch.object(cli, "render") as fake_render, \
         patch.object(cli, "upload_video") as fake_upload:
        assert cli.main(["publish", "--profile", "hadith"]) == 1
    fake_render.assert_not_called()
    fake_upload.assert_not_called()


def test_render_does_not_touch_the_network(tmp_path, monkeypatch):
    isolated = _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.setattr(cli.config, "OUTPUT_DIR", tmp_path)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4") as fake_render, \
         patch.object(cli, "build_client") as fake_client, \
         patch.object(cli, "upload_video") as fake_upload:
        assert cli.main(["render", "--profile", "hadith"]) == 0
    fake_render.assert_called_once()
    fake_client.assert_not_called()
    fake_upload.assert_not_called()
    assert not isolated.state_path.exists()   # render never writes state


def test_a_run_writes_only_its_own_profiles_state(tmp_path, monkeypatch):
    adkar = _isolate(monkeypatch, tmp_path / "a", ADKAR)
    hadith = _isolate(monkeypatch, tmp_path / "h", HADITH)
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel"), \
         patch.object(cli, "upload_video", return_value="vid1"):
        assert cli.main(["publish", "--profile", "adkar"]) == 0
    assert adkar.state_path.exists()
    assert not hadith.state_path.exists()


def test_publish_logs_the_actual_privacy_status(tmp_path, monkeypatch, caplog):
    """The log line must reflect config.PRIVACY_STATUS, not a hardcoded value."""
    _isolate(monkeypatch, tmp_path, HADITH)
    monkeypatch.setattr(cli.config, "PRIVACY_STATUS", "unlisted")
    with patch.object(cli, "render", return_value=tmp_path / "v.mp4"), \
         patch.object(cli, "build_client", return_value=MagicMock()), \
         patch.object(cli, "verify_channel"), \
         patch.object(cli, "upload_video", return_value="vid1"), \
         caplog.at_level("INFO"):
        assert cli.main(["publish", "--profile", "hadith"]) == 0
    assert "unlisted" in caplog.text
    assert "(private)" not in caplog.text
```

In `tests/test_config.py`, delete the six tests that exercise the removed `CHANNEL_HANDLE` constant — `test_assert_configured_raises_on_placeholder`, `test_assert_configured_passes_on_real_handle`, `test_assert_configured_raises_on_empty_handle`, `test_assert_configured_raises_on_whitespace_handle`, `test_channel_handle_empty_env_var_resolves_to_placeholder`, and the `_reload_config_after` fixture that only the last of those uses — and rewrite the remaining three to pass a profile:

```python
def test_assert_configured_rejects_invalid_privacy_status(monkeypatch):
    # Resolve through the module, not the name imported at file scope:
    # importlib.reload in a sibling test rebinds ConfigError to a NEW class
    # object, so a previously-imported reference stops matching what is raised.
    monkeypatch.setattr(config, "PRIVACY_STATUS", "publik")
    with pytest.raises(config.ConfigError, match="PRIVACY_STATUS"):
        config.assert_configured(HADITH)


def test_assert_configured_accepts_public(monkeypatch):
    monkeypatch.setattr(config, "PRIVACY_STATUS", "public")
    assert config.assert_configured(HADITH) is None


def test_assert_configured_rejects_a_count_below_one():
    import dataclasses
    with pytest.raises(config.ConfigError, match="count"):
        config.assert_configured(dataclasses.replace(HADITH, default_count=0))
```

Add `from adkar_bot.profiles import HADITH` to that file's imports. Keep `test_privacy_status_empty_env_falls_back_to_private` exactly as it is — it tests the empty-string-from-Actions handling, which still applies.

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_cli.py -v`
Expected: FAIL — `cli` has no attribute `PROFILES`.

- [ ] **Step 3: Rewrite `assert_configured`**

In `src/adkar_bot/config.py`, replace the function:

```python
def assert_configured(profile) -> None:
    """Fail loudly rather than publishing a run that cannot succeed."""
    if profile.default_count < 1:
        raise ConfigError(
            f"profile {profile.name!r} has an upload count of "
            f"{profile.default_count}; must be a whole number of 1 or more."
        )
    if PRIVACY_STATUS not in VALID_PRIVACY:
        raise ConfigError(
            f"PRIVACY_STATUS is {PRIVACY_STATUS!r}; must be one of "
            f"{VALID_PRIVACY}. An undefined GitHub repository variable arrives "
            f"as an empty string, which the API rejects."
        )
```

The handle check is gone: a profile always carries a real handle, so the condition it guarded cannot arise. The count check now reads the profile rather than the removed `PUBLISH_COUNT` global. Leave `PRIVACY_STATUS`, `VALID_PRIVACY`, `ConfigError`, `DAILY_QUOTA_UNITS`, `UPLOAD_COST_UNITS` and `MAX_UPLOADS_PER_DAY` untouched — Task 7 removes only what is genuinely dead.

Do not remove `CHANNEL_HANDLE` or `PUBLISH_COUNT` yet; `import` cycles are avoided by *not* importing `profiles` into `config` (note `assert_configured` takes an unannotated `profile` for exactly this reason — `profiles` imports `config`, so the reverse import would be circular).

- [ ] **Step 4: Rewrite the CLI**

In `src/adkar_bot/cli.py`, add to the imports:

```python
from .profiles import PROFILES
from .youtube import build_client, upload_video, verify_channel
```

Replace `_require_env`, `_pick`, `cmd_render`, `cmd_publish` and `main`:

```python
def _require_env(name: str) -> str:
    """Read a required secret, failing with an actionable message.

    os.environ[...] raises a bare KeyError that tells an operator nothing.
    """
    value = os.environ.get(name)
    if not value:
        raise ConfigError(
            f"{name} is not set. It is required to publish. "
            f"Set it as a GitHub repository secret, or export it locally."
        )
    return value


def _credentials(profile) -> tuple[str, str, str]:
    """Guard 1 against publishing to the wrong channel.

    Each profile reads credentials from names derived from its own prefix, so
    running one profile with the other's environment loaded fails by name
    before any network call rather than authenticating as the wrong channel.
    """
    return tuple(
        _require_env(f"{profile.env_prefix}_{suffix}")
        for suffix in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")
    )


def _resolve_profile(args):
    """--profile, else the PROFILE env var, else fail.

    No default. A default here means a wrong-channel upload the first time
    someone forgets the flag. Validated here rather than by argparse's
    `choices`, so a bad PROFILE env var takes the same path as a bad flag -
    argparse does not check `choices` against a value it did not parse.
    """
    name = getattr(args, "profile", None) or os.environ.get("PROFILE") or ""
    if name not in PROFILES:
        raise ConfigError(
            f"profile {name!r} is not one of {sorted(PROFILES)}. "
            f"Pass --profile, or set the PROFILE environment variable."
        )
    return PROFILES[name]


def _pick(profile):
    corpus = load_corpus(profile.corpus_path)
    state = load_state(profile.state_path)
    return corpus, state, next_dhikr(corpus, state)


def cmd_render(args) -> int:
    profile = _resolve_profile(args)
    assert_configured(profile)
    _corpus, _state, dhikr = _pick(profile)
    out = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4", profile)
    log.info("rendered %s -> %s", dhikr.id, out)
    return 0


def cmd_publish(args) -> int:
    profile = _resolve_profile(args)
    assert_configured(profile)
    client_id, client_secret, refresh_token = _credentials(profile)

    count = getattr(args, "count", None) or profile.default_count
    if count > config.MAX_UPLOADS_PER_DAY:
        log.warning(
            "asked for %d uploads; the default API quota affords %d "
            "(%d units/day / %d per videos.insert). The uploads past that "
            "will fail with quotaExceeded unless Google has raised the quota.",
            count, config.MAX_UPLOADS_PER_DAY,
            config.DAILY_QUOTA_UNITS, config.UPLOAD_COST_UNITS,
        )

    client = build_client(client_id, client_secret, refresh_token)
    # Guard 2, before the first render: a wrong-channel run must cost a
    # 1-unit API call, not 20 seconds of ffmpeg and 1,600 units of upload.
    verify_channel(client, profile)

    uploaded = 0
    for n in range(1, count + 1):
        # Re-read corpus and state every pass: the previous iteration wrote
        # state to disk, and reading it back is what guarantees the next pick
        # is a different dhikr. One code path, same as a sequence of runs.
        corpus, state, dhikr = _pick(profile)
        video = render(dhikr, config.OUTPUT_DIR / f"{dhikr.id}.mp4", profile)

        try:
            video_id = upload_video(
                client, video,
                build_title(dhikr),
                build_description(dhikr, profile),
                build_tags(dhikr, profile),
            )
        except Exception:
            # State for everything already uploaded is on disk, so the caller
            # can still commit it and the next run will not repeat those.
            log.error(
                "upload %d of %d failed on %s; %d already uploaded and saved",
                n, count, dhikr.id, uploaded,
            )
            raise

        now = datetime.now(timezone.utc).isoformat()
        save_state(record(state, dhikr, video_id, now, corpus=corpus),
                   profile.state_path)
        uploaded += 1
        log.info("uploaded %s as %s (%s) to %s - %d of %d",
                 dhikr.id, video_id, config.PRIVACY_STATUS,
                 profile.channel_handle, n, count)

    log.info("published %d video(s) to %s this run",
             uploaded, profile.channel_handle)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="adkar-bot")
    subs = parser.add_subparsers(dest="cmd", required=True)

    def _with_profile(sub):
        sub.add_argument(
            "--profile", choices=sorted(PROFILES), default=None,
            help="which channel to work against (env: PROFILE). Required.",
        )
        return sub

    _with_profile(subs.add_parser("render")).set_defaults(func=cmd_render)
    pub = _with_profile(subs.add_parser("publish"))
    pub.add_argument(
        "--count", type=int, default=None,
        help="how many to upload this run (default: the profile's own count)",
    )
    pub.set_defaults(func=cmd_publish)
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

Note `PUBLISH_COUNT` is gone from the CLI: the count now comes from `profile.default_count`, overridden by `--count`. Task 7 wires the `PUBLISH_COUNT` environment override back in at the profile level.

- [ ] **Step 5: Run the tests**

Run: `py -3 -m pytest tests/test_cli.py tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Run the whole suite**

Run: `py -3 -m pytest -q`
Expected: PASS — everything green again for the first time since Task 3.

- [ ] **Step 7: Commit**

```bash
git add src/adkar_bot/cli.py src/adkar_bot/config.py tests/test_cli.py tests/test_config.py tests/conftest.py
git commit -m "feat: resolve one profile per run and thread it through the CLI"
```

---

### Task 7: Remove the dead config globals

**Files:**
- Modify: `src/adkar_bot/config.py`
- Modify: `tests/conftest.py` (`corpus_sample`)
- Modify: `tests/test_corpus.py:81`, `tests/test_layout.py`, `tests/test_render.py` (the `corpus_sample()` callers)

**Interfaces:**
- Consumes: `profiles.HADITH` (Task 1).
- Produces: `corpus_sample(profile=None)` — the test helper, now profile-aware. No production interface changes; this task is subtraction plus one environment override restored.

**Context an engineer needs:** the constants being deleted are already unreferenced by production code after Task 6. This task removes them and fixes the last test-only consumers. `PUBLISH_COUNT` comes back, but as an override applied to whichever profile is active rather than a module global — the workflows need it to set the daily count per channel without editing `profiles.py`.

- [ ] **Step 1: Confirm the constants really are dead**

```bash
grep -rn "CORPUS_PATH\|STATE_PATH\|CHANNEL_HANDLE\|GRADIENT_TOP\|GRADIENT_BOTTOM\|PUBLISH_COUNT" src/ tests/ scripts/
```

Expected: hits only in `src/adkar_bot/config.py` itself, plus `config.CORPUS_PATH` in `tests/conftest.py` and `tests/test_corpus.py`. If anything in `src/adkar_bot/` outside `config.py` still appears, an earlier task is incomplete — finish it before deleting.

- [ ] **Step 2: Write the failing test**

Add to `tests/test_profiles.py`, extending its existing import line to
`from adkar_bot.profiles import ADKAR, HADITH, PROFILES, with_count_override`:

```python


def test_an_unset_override_leaves_the_profiles_own_count(monkeypatch):
    monkeypatch.delenv("PUBLISH_COUNT", raising=False)
    assert with_count_override(ADKAR).default_count == 1


def test_an_empty_override_leaves_the_profiles_own_count(monkeypatch):
    """An undefined GitHub repository variable arrives as "", not unset -
    so os.environ.get(name, default) never sees the default."""
    monkeypatch.setenv("PUBLISH_COUNT", "")
    assert with_count_override(ADKAR).default_count == 1


def test_a_numeric_override_wins(monkeypatch):
    monkeypatch.setenv("PUBLISH_COUNT", "4")
    assert with_count_override(ADKAR).default_count == 4


def test_a_malformed_override_is_caught_by_assert_configured(monkeypatch):
    """It must fail in assert_configured with an actionable message, not as
    a ValueError at import time."""
    monkeypatch.setenv("PUBLISH_COUNT", "six")
    assert with_count_override(ADKAR).default_count == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_profiles.py -v`
Expected: FAIL — `ImportError: cannot import name 'with_count_override'`

- [ ] **Step 4: Add the override helper**

Append to `src/adkar_bot/profiles.py`, and add `import dataclasses` and `import os` to its imports:

```python
def with_count_override(profile: Profile) -> Profile:
    """Apply the PUBLISH_COUNT environment override, if there is one.

    A function rather than an import-time constant so that reading the
    environment happens once per run, at the point the profile is resolved,
    and a test can set the variable without reloading a module.

    `or` rather than a get() default: an undefined GitHub repository variable
    arrives as "" rather than unset, and "" is falsy where a missing key is
    not. Parsed defensively - a malformed value becomes 0, which
    assert_configured rejects with an actionable message, rather than a
    ValueError from somewhere unhelpful.
    """
    raw = os.environ.get("PUBLISH_COUNT") or ""
    if not raw:
        return profile
    try:
        count = int(raw)
    except ValueError:
        count = 0
    return dataclasses.replace(profile, default_count=count)
```

- [ ] **Step 5: Call it from the CLI**

In `src/adkar_bot/cli.py`, change the import to `from .profiles import PROFILES, with_count_override` and the last line of `_resolve_profile`:

```python
    return with_count_override(PROFILES[name])
```

- [ ] **Step 6: Delete the dead constants**

From `src/adkar_bot/config.py`, delete these and their comments: `CORPUS_PATH`, `STATE_PATH`, `CHANNEL_HANDLE_PLACEHOLDER`, `CHANNEL_HANDLE`, `GRADIENT_TOP`, `GRADIENT_BOTTOM`, `_RAW_PUBLISH_COUNT`, `PUBLISH_COUNT`.

Keep: `ROOT`, `DATA_DIR`, `ASSETS_DIR`, `OUTPUT_DIR`, `FONT_PATH`, `AUDIO_DIR`, every frame/typography/animation/audio constant, `LIKE_TEXT`, `HANDLE_BAND`, `VALID_PRIVACY`, `PRIVACY_STATUS`, `DAILY_QUOTA_UNITS`, `UPLOAD_COST_UNITS`, `MAX_UPLOADS_PER_DAY`, `CATEGORY_ID`, `SCOPES`, `ConfigError`, `assert_configured`.

- [ ] **Step 7: Make the test helper profile-aware**

In `tests/conftest.py`, change `corpus_sample`:

```python
def corpus_sample(profile=None, n=120):
    """A bounded, deterministic slice of a corpus for the exhaustive tests.

    These tests used to walk all 206 entries. The corpus is now ~7,900, and
    rasterising every line of every one of them turned a 90-second suite into
    a many-minute one on the daily publish job.

    Defaults to the hadith profile: it is by far the larger corpus and holds
    the long entries this sample exists to exercise.

    The sample is half longest-first and half seeded-random. The longest
    entries are the point: overflow and handle collisions only ever happen at
    the small end of the font range, so the worst cases are always covered
    rather than left to chance.
    """
    from adkar_bot.corpus import load_corpus
    from adkar_bot.profiles import HADITH

    corpus = load_corpus((profile or HADITH).corpus_path)
    if len(corpus) <= n:
        return corpus
    longest = sorted(corpus, key=lambda d: -len(d.text))[: n // 2]
    rest = [d for d in corpus if d not in longest]
    return longest + random.Random(0).sample(rest, n - len(longest))
```

In `tests/test_corpus.py` line 81, replace `load_corpus(config.CORPUS_PATH)` with `load_corpus(HADITH.corpus_path)` and add `from adkar_bot.profiles import HADITH` to its imports. Drop the `config` import from that file if nothing else in it uses it.

- [ ] **Step 8: Run the whole suite**

Run: `py -3 -m pytest -q`
Expected: PASS.

- [ ] **Step 9: Verify the constants are gone**

```bash
grep -rn "CORPUS_PATH\|STATE_PATH\|CHANNEL_HANDLE\|GRADIENT_TOP\|GRADIENT_BOTTOM" src/ tests/ scripts/
```

Expected: no output.

- [ ] **Step 10: Commit**

```bash
git add src/adkar_bot/config.py src/adkar_bot/profiles.py src/adkar_bot/cli.py tests/conftest.py tests/test_corpus.py tests/test_profiles.py
git commit -m "refactor: drop the per-channel globals from config"
```

---

### Task 8: Workflows and documentation

**Files:**
- Modify: `.github/workflows/publish.yml`
- Create: `.github/workflows/publish-adkar.yml`
- Modify: `.github/workflows/test.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: the `--profile` CLI from Task 6.
- Produces: two scheduled jobs, staggered an hour apart, each committing only its own state file.

- [ ] **Step 1: Point the existing workflow at the hadith profile**

In `.github/workflows/publish.yml`, make four changes and nothing else.

Change the header comment's first line from `Publishes six adkar per day` to:

```yaml
# Publishes six hadith per day to @ZainKhairAllahChannel - the most the
# default API quota affords (10,000 units / 1,600 per videos.insert).
# The adkar channel has its own workflow: publish-adkar.yml.
```

In the `test` job, delete the two lines:

```yaml
        env:
          CHANNEL_HANDLE: ${{ vars.CHANNEL_HANDLE }}
```

so the `pytest` step has no `env:` block at all.

In the `publish` job, change the run line and drop `CHANNEL_HANDLE`:

```yaml
      - run: python -m adkar_bot.cli publish --profile hadith
        env:
          PRIVACY_STATUS: ${{ vars.PRIVACY_STATUS }}
          PUBLISH_COUNT: ${{ vars.PUBLISH_COUNT }}
          YT_CLIENT_ID: ${{ secrets.YT_CLIENT_ID }}
          YT_CLIENT_SECRET: ${{ secrets.YT_CLIENT_SECRET }}
          YT_REFRESH_TOKEN: ${{ secrets.YT_REFRESH_TOKEN }}
```

In the commit-back step, change the `git add` line and the error message:

```yaml
          git add data/state-hadith.json
          git diff --staged --quiet && exit 0
          git commit -m "chore: hadith rotation state [skip ci]"
```

and

```yaml
          echo "::error::could not persist data/state-hadith.json - the next run will repeat this hadith"
```

- [ ] **Step 2: Create the adkar workflow**

Create `.github/workflows/publish-adkar.yml`:

```yaml
# Publishes to @DIKR-o6k, which has its own Google Cloud project and so its
# own 10,000 units/day - the quota is per project, not per channel, so this
# does not eat into the hadith channel's six.
#
# ADKAR_PUBLISH_COUNT defaults to 1 via the adkar profile: the Hisn corpus is
# 206 entries, which at 6/day cycles in 34 days. Raise it once the corpus
# grows (Project B).
name: publish-adkar

on:
  schedule:
    # 07:00 UTC, an hour after the hadith run. Both jobs commit state to the
    # same branch; the hour keeps the commit-back retry loop a safety net
    # rather than a daily occurrence.
    - cron: "0 7 * * *"
  workflow_dispatch:

concurrency:
  # Its own group, not `publish`: the two channels have separate quotas and
  # separate state files, so there is nothing to serialise between them.
  group: publish-adkar
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
      - run: python -m adkar_bot.cli publish --profile adkar
        env:
          PRIVACY_STATUS: ${{ vars.PRIVACY_STATUS }}
          PUBLISH_COUNT: ${{ vars.ADKAR_PUBLISH_COUNT }}
          YT_ADKAR_CLIENT_ID: ${{ secrets.YT_ADKAR_CLIENT_ID }}
          YT_ADKAR_CLIENT_SECRET: ${{ secrets.YT_ADKAR_CLIENT_SECRET }}
          YT_ADKAR_REFRESH_TOKEN: ${{ secrets.YT_ADKAR_REFRESH_TOKEN }}
      - name: Commit rotation state
        # always(): a partial run still uploaded videos, and its
        # state must be committed or the next run repeats them.
        if: always()
        run: |
          git config user.name  "adkar-bot"
          git config user.email "adkar-bot@users.noreply.github.com"
          git add data/state-adkar.json
          git diff --staged --quiet && exit 0
          git commit -m "chore: adkar rotation state [skip ci]"
          for i in 1 2 3; do
            git pull --rebase origin "${GITHUB_REF_NAME}" && git push && exit 0
            echo "push attempt $i failed; retrying"
            sleep 5
          done
          echo "::error::could not persist data/state-adkar.json - the next run will repeat this dhikr"
          exit 1
```

- [ ] **Step 3: Drop the handle from the test workflow**

In `.github/workflows/test.yml`, find the `pytest` step and delete its `env:` block containing `CHANNEL_HANDLE`. Nothing reads the handle from the environment any more.

- [ ] **Step 4: Validate both workflow files parse**

```bash
py -3 -c "import yaml,pathlib; [yaml.safe_load(p.read_text(encoding='utf-8')) for p in pathlib.Path('.github/workflows').glob('*.yml')]; print('all workflows parse')"
```

Expected: `all workflows parse`. If PyYAML is not installed, `pip install pyyaml` first — it is a dev-only convenience, do not add it to `pyproject.toml`.

- [ ] **Step 5: Update the README**

Rewrite these sections of `README.md`:

- **Opening line** — it says the bot renders adkar to "your own channel". It now feeds two channels. Replace with a short paragraph plus the profile table from the spec (`hadith` → `@ZainKhairAllahChannel`, `adkar` → `@DIKR-o6k`).
- **Section 2 (Bootstrap)** — state that each channel needs its own Google Cloud project, because the quota is per project. Secrets are `YT_*` for hadith and `YT_ADKAR_*` for adkar. The `CHANNEL_HANDLE` repository variable is gone; add `ADKAR_PUBLISH_COUNT`.
- **Section 4 (Local usage)** — every command now takes `--profile`:
  ```
  py -3 -m adkar_bot.cli render --profile hadith
  py -3 -m adkar_bot.cli publish --profile adkar
  ```
- **Section 5 (The corpus)** — split the table in two. `data/hadith.json` holds 7,682 (4,066 Bukhari + 3,616 Muslim), `data/adkar.json` holds 206 Hisn al-Muslim. Keep the three importer rules and the "still outstanding" caveat verbatim — they are unchanged and still true. Note that 206 at 1/day is ~7 months and that growing it is tracked separately.
- **Section 6 (Quota)** — the 6/day ceiling is per Cloud project, so each channel gets its own six.
- **Workflow section** — describe both files and why they are staggered.

Add a new section **"Migrating from the single-channel setup"** with the six ordered steps from the spec's Migration section, copied faithfully, and its warning that skipping step 3 breaks the hadith channel because the old refresh token predates `youtube.readonly`.

- [ ] **Step 6: Run the whole suite one last time**

Run: `py -3 -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/publish.yml .github/workflows/publish-adkar.yml .github/workflows/test.yml README.md
git commit -m "feat: give each channel its own scheduled workflow"
```

---

## After the plan

The code is done but **the bot is not yet running correctly** — the migration steps in the spec are operator work that no task here can do:

1. New Google Cloud project for `@DIKR-o6k`; `py -3 scripts/authorize.py client_secret.json`; store `YT_ADKAR_*` secrets.
2. Re-run `scripts/authorize.py` for `@ZainKhairAllahChannel` — the old refresh token predates `youtube.readonly` and `verify_channel` will 403 until it is replaced.
3. Delete the `CHANNEL_HANDLE` repository variable; add `ADKAR_PUBLISH_COUNT` = `1`.
4. Dispatch each workflow manually once before trusting the cron.

Step 2 is the one that breaks a currently-working bot if skipped.
