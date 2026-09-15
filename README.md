# adkar-shorts-bot

Renders Arabic religious text as vertical YouTube Shorts and uploads them on
a daily schedule via GitHub Actions. It now feeds **two** channels, each
with its own corpus, its own credentials, and its own scheduled workflow:

| Profile  | Channel                                                        | Corpus                          | Daily count |
|----------|-----------------------------------------------------------------|----------------------------------|-------------|
| `hadith` | [@ZainKhairAllahChannel](https://www.youtube.com/@ZainKhairAllahChannel) (existing) | `data/hadith.json` — 7,682 entries (4,066 Sahih al-Bukhari + 3,616 Sahih Muslim) | 6 |
| `adkar`  | [@DIKR-o6k](https://www.youtube.com/@DIKR-o6k) (new)             | `data/adkar.json` — 206 entries (Hisn al-Muslim) | 1 |

Every command below takes `--profile {hadith,adkar}` to say which channel
it acts on; there is no default.

## 1. Google Cloud setup

The YouTube Data API quota (section 6) is granted **per Google Cloud
project, not per channel** — so each channel needs its own project to get
its own quota, rather than splitting one project's allowance between two
channels. Do the following once per channel, each in its own project:

1. Create a Google Cloud project (or reuse one already dedicated to that
   channel).
2. Enable the **YouTube Data API v3** for that project.
3. Configure the **OAuth consent screen**:
   - Set the publishing status to **In production**, not *Testing*.
     This matters more than it sounds: in *Testing* status, Google expires
     refresh tokens after **7 days**, so the daily cron job would silently
     die about once a week. Moving to *In production* does **not** require
     completing Google's app verification review — since you are the only
     user, you just click through a one-time "Google hasn't verified this
     app" interstitial during the bootstrap step below.
4. Create an **OAuth client ID** of type **Desktop app**, and download the
   `client_secret.json` file.

## 2. Bootstrap (one-time, run locally — not in CI)

Run this once per channel, against that channel's own `client_secret.json`,
selecting that channel's account when the browser prompts for one:

```
py -3 scripts/authorize.py client_secret.json
```

This opens a browser for you to sign in and consent, then prints three
values. Add them to the GitHub repository:

- **Repository secrets** (Settings -> Secrets and variables -> Actions ->
  Secrets):
  - `hadith` (`@ZainKhairAllahChannel`): `YT_CLIENT_ID`, `YT_CLIENT_SECRET`,
    `YT_REFRESH_TOKEN`
  - `adkar` (`@DIKR-o6k`): `YT_ADKAR_CLIENT_ID`, `YT_ADKAR_CLIENT_SECRET`,
    `YT_ADKAR_REFRESH_TOKEN`
- **Repository variables** (same page, Variables tab):
  - `PRIVACY_STATUS` — shared by both channels.
  - `PUBLISH_COUNT` — overrides the `hadith` channel's daily count
    (default `6`).
  - `ADKAR_PUBLISH_COUNT` — overrides the `adkar` channel's daily count
    (default `1`).

There is no `CHANNEL_HANDLE` repository variable any more — each profile
carries its own channel handle in `src/adkar_bot/profiles.py`, so nothing
reads the handle from the environment.

Never commit `client_secret.json` or a refresh token to the repo.

## 3. The one manual step per video

Because the OAuth app is unverified, **every upload lands as `private`**,
regardless of what the code requests. Flip the video to public yourself in
YouTube Studio once you're happy with it. Takes a few seconds per video.
This applies to both channels.

Note: this bot does not post a comment on the uploaded video. YouTube does
not permit posting comments on private videos, and Google forces every
upload from an unverified app to `private` — so a comment call would 403 on
every single run. The video description already carries the full dhikr
text plus its `source` and `reference`, so nothing is lost. Don't
re-introduce comment posting without first getting the app verified (which
would also lift the forced-private upload).

## 4. Local usage

```
py -3 -m adkar_bot.cli render --profile hadith
py -3 -m adkar_bot.cli render --profile adkar
```

Renders the next dhikr in that profile's rotation to an MP4 in `output/`.
This does not touch the network and does not modify either state file, so
it's safe to run repeatedly while iterating on layout or fonts.

To actually publish (uploads to YouTube and updates that profile's rotation
state):

```
py -3 -m adkar_bot.cli publish --profile hadith
py -3 -m adkar_bot.cli publish --profile adkar
```

`--count N` overrides the daily count locally. Each profile requires its
own credentials in the environment: `hadith` needs `YT_CLIENT_ID`,
`YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`; `adkar` needs `YT_ADKAR_CLIENT_ID`,
`YT_ADKAR_CLIENT_SECRET`, `YT_ADKAR_REFRESH_TOKEN`.

## 5. The corpus

The corpus that was once one 7,888-entry file is now split by channel:

**`data/hadith.json`** — 7,682 entries, **~3.5 years at the `hadith`
channel's 6 shorts a day** before anything repeats:

| Source | Entries |
|---|---|
| Sahih al-Bukhari | 4,066 |
| Sahih Muslim | 3,616 |

**`data/adkar.json`** — 206 entries (Hisn al-Muslim), all that the `adkar`
channel has. At its 1/day default that's **~7 months** before anything
repeats. Growing this corpus is tracked separately (see "Out of scope:
Project B" in the design spec) — it needs its own source vetting and
shortening rules, not a quick add.

Rebuild the hadith corpus with `py scripts/import_hadith.py <dir>`, pointing
at `bukhari.json` / `muslim.json` from
[AhmedBaset/hadith-json](https://github.com/AhmedBaset/hadith-json). It
writes to `data/hadith.json` only — it never touches `data/adkar.json`.

Three rules the importer follows, all about not misquoting:

- An entry is **only shortened** when it explicitly says the Prophet spoke
  (`قال رسول الله صلى الله عليه وسلم` and close variants), and the cut starts
  at that phrase. 3,130 entries qualify. Everything else is copied **verbatim,
  chain and all** — nothing is ever cut on a guess.
- A marker must begin its own word. Without that guard `ان رسول الله` matches
  the tail of `وكان` and the cut lands mid-word, which silently misquotes the
  text. There is a test for this.
- Entries that only point at another hadith's chain (`بهذا الإسناد`, `نحوه`)
  are dropped: standalone they carry nothing to read. 1,555 removed.

Entries longer than 450 characters are skipped. That is a legibility limit,
measured rather than guessed: at 450 the worst-case font size is 41px and the
median 72px, and it degrades from there.

**Still outstanding:** none of this has been checked against a printed,
scholarly-reviewed edition. The hadith text comes from a compilation with no
stated licence (the text itself is public domain). This is an automated
pipeline — any error in the corpus gets reproduced on every single run.

## 6. Quota

The YouTube Data API gives 10,000 units/day by default, **per Google Cloud
project** — not per channel — and each upload costs `videos.insert`: 1,600
units. That makes **six uploads per day a hard ceiling per project**; the
seventh returns `quotaExceeded`. Because `hadith` and `adkar` now live in
separate Cloud projects, each channel gets its own six rather than sharing
one — `hadith` uses its ceiling fully by default, and `adkar` deliberately
uses only one of its own six so the smaller Hisn corpus lasts longer before
repeating. Going beyond six for a given channel needs a quota increase from
Google for that channel's project, which is a separate audit, not a
setting.

`PUBLISH_COUNT` (repo variable, default `6`) sets how many hadith one
`hadith` run uploads; `ADKAR_PUBLISH_COUNT` (repo variable, default `1`)
does the same for `adkar`. `--count N` overrides either locally. State is
written after every upload, so a run that fails partway keeps the videos it
already published and the next run continues past them rather than
repeating.

## Workflows

Each channel has its own scheduled workflow, because each has its own
credentials, its own quota, its own corpus, and its own state file:

- `.github/workflows/publish.yml` — the `hadith` channel. Cron `0 6 * * *`
  (06:00 UTC), concurrency group `publish`, commits back
  `data/state-hadith.json` only.
- `.github/workflows/publish-adkar.yml` — the `adkar` channel. Cron
  `0 7 * * *` (07:00 UTC), concurrency group `publish-adkar`, commits back
  `data/state-adkar.json` only.

The two crons are staggered an hour apart, and each has its **own**
concurrency group rather than sharing `publish`. Both reasons come from the
same fact: both jobs commit state to the same branch. The hour gap keeps
the commit-back retry loop (below) a rare safety net instead of a daily
occurrence, and the separate concurrency groups mean an `adkar` run is
never blocked waiting on an in-flight `hadith` run or vice versa — the two
channels have nothing to serialise, since they touch different state files
and different quotas.

Both workflows are otherwise the same shape. Each has two jobs:

- `test` — installs dev dependencies and runs the full test suite. This
  needs no real credentials; `tests/conftest.py` sets dummy `YT_*` and
  `YT_ADKAR_*` environment variables so `cmd_publish`'s env lookups don't
  raise in CI.
- `publish` — runs only if `test` passes, calls
  `python -m adkar_bot.cli publish --profile {hadith,adkar}`, then commits
  that profile's own state file back to the repo so its rotation state
  persists between runs. Neither workflow ever `git add`s the other
  channel's state file.

`.github/workflows/test.yml` runs the same suite on every `push` and
`pull_request`, independent of either cron, so a regression is caught at
review time rather than sitting undetected until a schedule fires.

The branch these workflows run on (the repo's default branch, normally)
**must be directly pushable by `GITHUB_TOKEN`** — no branch protection rule
or ruleset that blocks pushes from Actions, and no required status check
that a bot commit can't satisfy. Each commit-back step retries `git pull
--rebase` + `git push` a few times to absorb races with other commits
(including the other channel's own commit-back step), but if the branch
itself refuses the push (protected branch, required review, etc.), every
retry fails the same way and the step exits with an `::error::` annotation.
When that happens, that channel's state file was never updated even though
the video already uploaded successfully — the next run for that channel
will pick the same dhikr again and re-upload it, burning another 1,600+
quota units. Watch for that error annotation in the Actions log if a video
looks duplicated.

### Residual failure mode: duplicate videos

If `upload_video` succeeds (the video is live on YouTube) but something
after it fails — the process is killed, the runner dies, state-saving is
somehow skipped, etc. — the rotation entry is not marked used, and the
next run publishes the *same* dhikr again as a second video. This is a
deliberate tradeoff, not an
oversight: the alternative (marking the entry used before or during upload)
risks the opposite failure — silently skipping a dhikr whose video never
actually went live. Duplicates are visible and harmless to fix by hand;
silent skips are not. The owner reviews every upload before making it
public anyway, so an occasional duplicate is caught there. This applies
independently to each channel's own state file.

## Migrating from the single-channel setup

This repository used to run one channel from one corpus, one state file,
and one workflow. These are the steps that took it from that setup to the
current two-channel one, in order, because some of them are irreversible:

1. Create the new Google Cloud project, enable YouTube Data API v3, set the
   consent screen to **In production**, create a Desktop OAuth client.
2. Run `scripts/authorize.py` against the new client, selecting
   `@DIKR-o6k`. Store the results as `YT_ADKAR_CLIENT_ID` /
   `YT_ADKAR_CLIENT_SECRET` / `YT_ADKAR_REFRESH_TOKEN` repository secrets.
3. Re-run `scripts/authorize.py` against the **existing** client, which now
   requests `youtube.readonly` too, selecting `@ZainKhairAllahChannel`.
   Replace `YT_REFRESH_TOKEN`.
4. Split the corpus and the state files; delete `data/state.json`; commit.
5. Delete the `CHANNEL_HANDLE` repository variable. Add
   `ADKAR_PUBLISH_COUNT` = `1`.
6. Dispatch each workflow manually once before trusting the cron.

**Step 3 is the one that breaks the running bot if skipped:** the old
refresh token lacks `youtube.readonly`, which the channel-verification
guard now requires, so the `hadith` publish job will 403 on every run until
that token is replaced — this is not a hypothetical, it is exactly what an
un-migrated `hadith` deployment does the moment this code ships.

Step 4 in this repository was performed by `scripts/split_corpus.py`, and
that step is already done — `data/hadith.json`, `data/adkar.json`,
`data/state-hadith.json`, and `data/state-adkar.json` are what's committed
today; `data/state.json` no longer exists. **Do not run
`scripts/split_corpus.py` again.** It is a one-time migration script and is
destructively non-idempotent: a second run reads the already-split
`data/adkar.json`, finds no hadith entries left in it, and overwrites
`data/hadith.json` with an **empty** file, wiping the preserved publish
history along with it. It has no built-in guard against being re-run — the
guard is this warning.

## Licensing

This project's code is licensed under the MIT License — see `LICENSE`.

The bundled font, `assets/fonts/Amiri-Regular.ttf`, is the Amiri typeface
and is licensed separately under the SIL Open Font License 1.1, **not**
MIT. Its full license text and copyright notice are in
`assets/fonts/OFL.txt` and travel with the font file as required by the
OFL; if you redistribute the font itself (not just the video output), that
notice must go with it.
