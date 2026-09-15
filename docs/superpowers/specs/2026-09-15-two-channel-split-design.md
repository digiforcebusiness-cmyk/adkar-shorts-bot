# Two-Channel Split — Design

**Date:** 2026-09-15
**Status:** Approved
**Supersedes:** the "multi-channel support" non-goal in
`2026-08-04-adkar-shorts-bot-design.md`. That decision was right when there
was one channel and a 206-entry corpus. The corpus is now 7,888 entries
across two unrelated bodies of text, and there are two channels to feed.

## Purpose

Split the single mixed rotation into two independently scheduled channels, so
that hadith and adkar each get a channel of their own instead of being
interleaved on one.

| Profile | Channel | Corpus | Entries | Cloud project |
| --- | --- | --- | --- | --- |
| `hadith` | `@ZainKhairAllahChannel` (existing) | Sahih al-Bukhari + Sahih Muslim | 7,682 | existing |
| `adkar` | `@DIKR-o6k` (new) | Hisn al-Muslim | 206 | **new** |

The existing channel keeps the existing Cloud project, the existing `YT_*`
secrets, the existing workflow file and the existing teal palette — it has 33
videos already published and there is no reason to disturb any of that. Every
new thing in this design attaches to the new channel.

## Success criteria

1. `publish --profile hadith` and `publish --profile adkar` each render from
   their own corpus, upload to their own channel, and persist their own
   rotation state, with no shared mutable state between them.
2. Neither profile can publish to the other's channel, even when invoked by
   hand with the wrong environment loaded.
3. The two channels are visually distinguishable at a glance while sharing
   one render implementation.
4. The 33 videos already published are not re-published to the channel that
   already hosts them.
5. A run of one profile cannot corrupt or lose the other profile's state,
   including when both run on the same day.

## Non-goals

Growing the adkar corpus beyond its 206 entries (that is Project B, its own
spec). A third channel. Per-profile render *layout* — only the palette
differs. Automating the manual publish step. Runtime-editable profiles.

## Platform constraints

| Constraint | Consequence |
| --- | --- |
| YouTube API quota is per **Cloud project**, not per channel: 10,000 units/day divided by 1,600 per `videos.insert` = 6 uploads | Two channels on one project would share 6/day. A second Cloud project is required to get 6 + 6. |
| `channels.list` is not covered by the `youtube.upload` scope | Handle verification requires adding `youtube.readonly`, which means re-running `scripts/authorize.py` for **both** channels once. |
| Unverified OAuth apps upload forced-`private` | Unchanged, and now true of the new project too — it starts its own unverified-app clock. Both channels need the manual publish step. |
| GitHub Actions runs commit state back to the same branch | The two scheduled runs are staggered by an hour so their commit-back steps cannot race. |

## Architecture

### `profiles.py` (new)

A frozen `Profile` dataclass and a `PROFILES: dict[str, Profile]` holding two
literal instances. Two profiles, both authored in-repo, both changing about
never — so they are literals in a module, not JSON loaded and validated at
runtime. A typo fails at import, which is the strongest failure mode
available and costs nothing.

```python
@dataclass(frozen=True)
class Profile:
    name: str                      # "hadith" | "adkar"
    corpus_path: Path
    state_path: Path
    channel_handle: str
    gradient: tuple[RGB, RGB]      # (top, bottom)
    base_tags: tuple[str, ...]
    hashtags: str                  # description footer line
    default_count: int
    env_prefix: str                # "YT" | "YT_ADKAR"
```

`base_tags` is a tuple, not a list: the dataclass is frozen, and a mutable
default inside a frozen instance is frozen in name only. `build_tags` already
copies into a new list, so callers are unaffected.

Values:

| Field | `hadith` | `adkar` |
| --- | --- | --- |
| `corpus_path` | `data/hadith.json` | `data/adkar.json` |
| `state_path` | `data/state-hadith.json` | `data/state-adkar.json` |
| `channel_handle` | `@ZainKhairAllahChannel` | `@DIKR-o6k` |
| `gradient` | `(14,34,48)` to `(6,12,20)` (current teal, unchanged) | `(16,44,34)` to `(6,18,14)` (deep green) |
| `default_count` | `6` | `1` |
| `env_prefix` | `YT` | `YT_ADKAR` |

`hadith` inherits today's exact values for gradient, count and credential
names. This is deliberate: the migration is then provably a no-op for the
channel that is already live, and every behavioural change is confined to the
new one.

### What stays in `config.py`

Everything that is identical for both channels: frame geometry, safe areas,
typography, `LINE_SPACING`, colours other than the gradient, fps/CRF,
animation timing, audio levels, category id, and the quota arithmetic. Roughly
30 constants stay; 8 move.

Removed from `config.py`: `CORPUS_PATH`, `STATE_PATH`, `CHANNEL_HANDLE`,
`CHANNEL_HANDLE_PLACEHOLDER`, `GRADIENT_TOP`, `GRADIENT_BOTTOM`,
`PUBLISH_COUNT`, `_RAW_PUBLISH_COUNT`.

`assert_configured()` becomes `assert_configured(profile)`. The
`CHANNEL_HANDLE` placeholder check disappears — a profile always has a real
handle, so the condition it guarded cannot arise. The `PUBLISH_COUNT` and
`PRIVACY_STATUS` checks survive, including the empty-string-from-Actions
handling, which is still live for both.

### Threading

`cli.py` resolves the profile once, from `--profile` or the `PROFILE`
environment variable, and passes it down. No module-level profile global:
that is the pattern this design exists to get away from.

Signatures that gain a `profile` parameter:

- `cli._pick(profile)`
- `render.render(dhikr, out, profile)`
- `render.gradient_background(profile)`
- `metadata.build_description(dhikr, profile)`
- `metadata.build_tags(dhikr, profile)`
- `config.assert_configured(profile)`
- `youtube.verify_channel(client, profile)` (new)

`metadata.build_title` does not: the title is the text plus `#shorts`, with
nothing channel-specific in it.

### Corpus split

`data/adkar.json` currently holds all 7,888 entries. It becomes:

- `data/hadith.json` — the 4,066 `bukhari-*` and 3,616 `muslim-*` entries.
- `data/adkar.json` — the 206 `hisn-*` entries.

A one-off script performs the split. `scripts/import_hadith.py` then
retargets its `ADKAR` constant to `data/hadith.json`, after which it never
writes to the adkar corpus again. Its `MAX_CHARS`/`MIN_CHARS` limits, the
marker rules and the cross-reference dropping are all unchanged — that logic
is about not misquoting hadith and is correct as it stands.

The `count` field present on Hisn entries and absent on hadith entries is
left alone; `corpus.py` already ignores unknown fields and requires only the
five it validates.

### Rotation state

`data/state.json` holds 33 used ids — all `hisn-*` — and 33 publish records.
Under the new mapping those are adkar videos that live on the hadith channel.
The split is therefore **not** a clean partition of the existing file:

- `data/state-hadith.json` — `used: []`, `cycle: 0`, and the 33 publish
  records **preserved**. No hadith entry has ever been published, so nothing
  is used; but those 33 uploads genuinely happened through that channel's
  credentials, and the record of them is the only audit trail of what is on
  the channel.
- `data/state-adkar.json` — empty. `@DIKR-o6k` has published nothing, so all
  206 entries are available to it.

Carrying the 33 used ids across to the adkar profile was considered and
rejected: it would permanently hide 16% of a 206-entry corpus from a channel
that never showed them. The accepted cost is 33 adkar existing on both
channels, which the owner can delete by hand from the old channel.

`data/state.json` is deleted once both successors are written.

A consequence worth stating plainly: `state-hadith.json` will hold publish
records whose ids (`hisn-*`) do not exist in `data/hadith.json`. Nothing
reads `published` back — `_effective` and `next_dhikr` consult `used` only —
so this is inert. It is recorded here so a future reader does not "fix" it.

### Wrong-channel guards

Two, layered, because the failure they prevent is expensive and partly
irreversible: hadith uploaded to the adkar channel is 1,600 quota units spent
and a video to delete by hand.

**Guard 1 — credential binding.** Each profile reads its credentials from
names derived from `env_prefix`: hadith from `YT_CLIENT_ID`,
`YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`; adkar from `YT_ADKAR_CLIENT_ID` and
so on. `publish --profile adkar` with only the hadith credentials exported
fails in `_require_env` with *"YT_ADKAR_CLIENT_ID is not set"* before any
network call. Costs nothing, requires no scope change, and catches the
realistic mistake — running the wrong profile against a shell that still has
the other channel's `.env` loaded.

**Guard 2 — handle verification.** `SCOPES` gains
`https://www.googleapis.com/auth/youtube.readonly`. Before the first upload
of a run, `verify_channel` calls `channels.list(mine=true, part="snippet")`,
reads `snippet.customUrl`, and compares it case-insensitively to
`profile.channel_handle`. A mismatch raises before any `videos.insert`. Costs
1 quota unit per run and catches what guard 1 cannot: correct variable names
holding the wrong token.

Google's documentation does not state which scopes `channels.list` accepts;
`youtube.upload` is upload-only and is reported to return
`insufficientPermissions`. Adding `youtube.readonly` is the reason both
channels must re-authorize once. If verification turns out to work under the
existing scope, the scope addition can be reverted without touching the
guard.

`customUrl` is returned without the leading `@` in some responses and with it
in others. The comparison normalises both sides by stripping a leading `@`
and lowercasing, rather than assuming either form.

### Metadata

`metadata.BASE_TAGS` moves to `Profile.base_tags`, and the hard-coded
`#shorts #أذكار #أدعية` footer to `Profile.hashtags`.

- `adkar`: today's tags and footer, unchanged.
- `hadith`: `حديث، أحاديث، صحيح البخاري، صحيح مسلم، السنة، hadith، sunnah، shorts`,
  footer `#shorts #حديث #السنة`.

`build_description`'s `المصدر:` / `التخريج:` block already carries the book
and the reference number, which is exactly the attribution hadith needs. It
is unchanged apart from taking the handle from the profile.

### Workflows

`publish.yml` becomes the hadith run: adds `--profile hadith`, commits
`data/state-hadith.json`, keeps 06:00 UTC, keeps `concurrency: {group:
publish}`, keeps its secrets. The `CHANNEL_HANDLE` repo variable is dropped
from its env — the profile owns the handle now, and leaving the variable in
place would let it silently disagree with the profile, which is precisely the
inconsistency guard 2 exists to catch.

`publish-adkar.yml` is new and mirrors it: `--profile adkar`, commits
`data/state-adkar.json`, `concurrency: {group: publish-adkar}`, `YT_ADKAR_*`
secrets, `PUBLISH_COUNT` from an `ADKAR_PUBLISH_COUNT` repo variable, and
cron **07:00 UTC**. The hour of separation is the point: both jobs push to
the same branch, and the existing three-attempt `pull --rebase` retry should
be a safety net rather than a daily occurrence.

`test.yml` drops the `CHANNEL_HANDLE` env it currently passes to `pytest`;
the handle is no longer read from the environment by anything. Nothing else
in it changes.

## Error handling

Unchanged in shape from the current design, which is sound:

- State is saved after every individual upload, so a run that dies partway
  keeps what it published.
- The duplicate-over-silent-skip tradeoff documented in the README stands.
- `ConfigError` exits 2; anything else exits 1.

New failure modes and their handling:

| Failure | Behaviour |
| --- | --- |
| Unknown `--profile` value | `argparse` rejects it against the `PROFILES` keys; exit 2. |
| No profile given, `PROFILE` unset | `argparse` requires the argument; exit 2. Defaulting was rejected — a default here means a wrong-channel upload when someone forgets the flag. |
| Missing `YT_ADKAR_*` credential | `ConfigError` naming the exact variable; exit 2, no network call. |
| `channels.list` returns a handle that is not the profile's | Raises before the first `videos.insert`; exit 1, no upload, no state change. |
| `channels.list` returns 403 `insufficientPermissions` | Raises with a message pointing at re-authorization; exit 1. This is what an un-migrated refresh token looks like. |

## Testing

New:

- `test_profiles.py` — both profiles construct; each `name` matches its dict
  key; corpus and state paths are distinct across profiles; `env_prefix`
  values are distinct.
- Corpus integrity — `data/adkar.json` is entirely `hisn-*`,
  `data/hadith.json` entirely `bukhari-*`/`muslim-*`, the two id sets are
  disjoint, and their union matches the pre-split corpus exactly.
- `test_metadata.py` — each profile yields its own tags and footer.
- `test_render.py` — `gradient_background` differs between profiles at a
  sampled pixel.
- `test_cli.py` — adkar profile with only `YT_*` set raises `ConfigError`
  naming `YT_ADKAR_CLIENT_ID`; each profile reads and writes only its own
  state path.
- `test_youtube.py` — `verify_channel` passes on a matching handle, on a
  `customUrl` that lacks the leading `@`, and on differing case; raises on a
  mismatch; raises a re-authorization message on 403.

Updated: every existing test that calls the signatures listed under
*Threading*. Two changes in `tests/conftest.py`:

- The autouse `_yt_oauth_env` fixture gains dummy `YT_ADKAR_*` variables
  alongside the existing dummy `YT_*` ones, so `_require_env` keeps quiet for
  either profile.
- `corpus_sample()` reads `config.CORPUS_PATH`, which this design removes. It
  takes a profile argument instead, defaulting to the hadith profile — that
  is the larger corpus and holds the long entries the sample exists to
  exercise. Its `n=120` bound and the longest-first/seeded-random split are
  unchanged; the reasoning in its docstring still holds, only more so now
  that each profile has its own corpus.

## Migration

Ordered, because some steps are irreversible:

1. Create the new Google Cloud project, enable YouTube Data API v3, set the
   consent screen to **In production**, create a Desktop OAuth client.
2. Run `scripts/authorize.py` against the new client, selecting `@DIKR-o6k`.
   Store the results as `YT_ADKAR_CLIENT_ID` / `YT_ADKAR_CLIENT_SECRET` /
   `YT_ADKAR_REFRESH_TOKEN` repository secrets.
3. Re-run `scripts/authorize.py` against the **existing** client, which now
   requests `youtube.readonly` too, selecting `@ZainKhairAllahChannel`.
   Replace `YT_REFRESH_TOKEN`.
4. Split the corpus and the state files; delete `data/state.json`; commit.
5. Delete the `CHANNEL_HANDLE` repository variable. Add
   `ADKAR_PUBLISH_COUNT` = `1`.
6. Dispatch each workflow manually once before trusting the cron.

Step 3 is the one that breaks the running bot if skipped: the old refresh
token lacks `youtube.readonly`, so guard 2 will 403 and the hadith run will
publish nothing until the token is replaced.

## Naming

The package stays `adkar_bot` and the repository stays `adkar-shorts-bot`,
even though the package now serves a mostly-hadith workload. Renaming means
touching every import, the `pyproject.toml` entry points, both workflow
command lines and the git remote, for no behavioural gain. Noted here so the
mismatch reads as a decision rather than an oversight.

## Out of scope: Project B

The adkar corpus is 206 entries. At the interim 1/day that is ~7 months
before the rotation cycles; at 6/day it would be 34. Growing it — al-Nawawi's
*al-Adhkar*, *al-Kalim al-Tayyib*, the dua books of the four Sunan — needs
source vetting, a new importer with its own shortening rules, and it inherits
the unresolved caveat already in the README: none of this has been checked
against a printed, scholarly-reviewed edition. That is a separate spec and a
separate implementation cycle.
