# adkar-shorts-bot

Renders Arabic dhikr (adkar) text as vertical YouTube Shorts and uploads
them to your own channel on a daily schedule via GitHub Actions.

## 1. Google Cloud setup

1. Create a Google Cloud project (or reuse one).
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

```
py -3 scripts/authorize.py client_secret.json
```

This opens a browser for you to sign in and consent, then prints three
values. Add them to the GitHub repository:

- **Repository secrets** (Settings -> Secrets and variables -> Actions ->
  Secrets):
  - `YT_CLIENT_ID`
  - `YT_CLIENT_SECRET`
  - `YT_REFRESH_TOKEN`
- **Repository variable** (same page, Variables tab):
  - `CHANNEL_HANDLE` — your channel handle, e.g. `@your-channel`

Never commit `client_secret.json` or the refresh token to the repo.

## 3. The one manual step per video

Because the OAuth app is unverified, **every upload lands as `private`**,
regardless of what the code requests. Flip the video to public yourself in
YouTube Studio once you're happy with it. Takes a few seconds per video.

Note: this bot does not post a comment on the uploaded video. YouTube does
not permit posting comments on private videos, and Google forces every
upload from an unverified app to `private` — so a comment call would 403 on
every single run. The video description already carries the full dhikr
text plus its `source` and `reference`, so nothing is lost. Don't
re-introduce comment posting without first getting the app verified (which
would also lift the forced-private upload).

## 4. Local usage

```
py -3 -m adkar_bot.cli render
```

Renders the next dhikr in rotation to an MP4 in `output/`. This does not
touch the network and does not modify `data/state.json`, so it's safe to
run repeatedly while iterating on layout or fonts.

To actually publish (uploads to YouTube and updates rotation state):

```
py -3 -m adkar_bot.cli publish
```

This requires `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`, and
`CHANNEL_HANDLE` to be set in the environment.

## 5. The corpus

`data/adkar.json` holds 7,888 entries — **3.6 years at the current 6 shorts a
day**, or 2.16 years if the quota is ever raised to 10 — before anything
repeats:

| Source | Entries |
|---|---|
| Hisn al-Muslim (adkar) | 206 |
| Sahih al-Bukhari | 4,066 |
| Sahih Muslim | 3,616 |

Rebuild the hadith portion with `py scripts/import_hadith.py <dir>`, pointing
at `bukhari.json` / `muslim.json` from
[AhmedBaset/hadith-json](https://github.com/AhmedBaset/hadith-json).

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

The YouTube Data API gives 10,000 units/day by default and each upload costs
`videos.insert`: 1,600 units. That makes **six uploads per day a hard ceiling** —
the seventh returns `quotaExceeded`. Going beyond six needs a quota increase
from Google, which is a separate audit, not a setting.

`PUBLISH_COUNT` (repo variable, default `6` — the ceiling above) sets how many
adkar one run uploads; `--count N` overrides it locally. State is written after every upload,
so a run that fails partway keeps the videos it already published and the next
run continues past them rather than repeating.

## Workflow

`.github/workflows/publish.yml` runs on a daily cron (06:00 UTC) and can
also be triggered manually via `workflow_dispatch`. It has two jobs:

- `test` — installs dev dependencies and runs the full test suite. This
  needs no real credentials; `tests/conftest.py` sets dummy `YT_*`
  environment variables so `cmd_publish`'s env lookups don't raise in CI.
- `publish` — runs only if `test` passes, calls
  `python -m adkar_bot.cli publish`, then commits the updated
  `data/state.json` back to the repo so rotation state persists between
  runs.

`concurrency: {group: publish}` prevents an overlapping run (e.g. a
delayed scheduled run colliding with a manual dispatch) from double
publishing.

`.github/workflows/test.yml` runs the same suite on every `push` and
`pull_request`, independent of the daily cron, so a regression is caught at
review time rather than sitting undetected until the schedule fires.

The branch this workflow runs on (the repo's default branch, normally)
**must be directly pushable by `GITHUB_TOKEN`** — no branch protection rule
or ruleset that blocks pushes from Actions, and no required status check
that a bot commit can't satisfy. The commit-back step retries `git pull
--rebase` + `git push` a few times to absorb races with other commits, but
if the branch itself refuses the push (protected branch, required review,
etc.), every retry fails the same way and the step exits with an
`::error::` annotation. When that happens, `data/state.json` was never
updated even though the video already uploaded successfully — the next run
will pick the same dhikr again and re-upload it, burning another 1,650
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
public anyway, so an occasional duplicate is caught there.

## Licensing

This project's code is licensed under the MIT License — see `LICENSE`.

The bundled font, `assets/fonts/Amiri-Regular.ttf`, is the Amiri typeface
and is licensed separately under the SIL Open Font License 1.1, **not**
MIT. Its full license text and copyright notice are in
`assets/fonts/OFL.txt` and travel with the font file as required by the
OFL; if you redistribute the font itself (not just the video output), that
notice must go with it.
