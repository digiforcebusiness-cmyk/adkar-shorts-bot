# Privacy Policy — Adkar Shorts Bot

**Last updated:** 7 August 2026
**Contact:** digiforcebusiness@gmail.com

## What this application is

Adkar Shorts Bot is a personal automation tool operated by a single person: the
owner of the YouTube channels [@ZainKhairAllahChannel](https://www.youtube.com/@ZainKhairAllahChannel)
and [@DIKR-o6k](https://www.youtube.com/@DIKR-o6k). It is not distributed, not
offered as a service, and has no users other than its owner.

The application generates short vertical videos containing Arabic Islamic
supplications (adkar) and hadith (prophetic traditions) rendered as text, and
uploads them to the owner's own YouTube channels on daily schedules.

## What data the application accesses

The application authenticates with Google using OAuth 2.0 and requests two scopes:

- `https://www.googleapis.com/auth/youtube.upload` — permits uploading videos
- `https://www.googleapis.com/auth/youtube.readonly` — permits reading the
  authenticated channel's public metadata (specifically its handle)

The `youtube.readonly` scope is used once per run to read the authenticated
channel's handle via the channels.list API. This confirms the credentials belong
to the intended channel before uploading, protecting against accidental publishes
to the wrong channel if credentials are misconfigured.

The application accesses **no data belonging to any other person**. It does not
read other users' videos, comments, channels, playlists, subscriber information,
or analytics. It does not read the owner's own viewing history or analytics.

## What data the application stores

| Data | Where | Purpose |
| --- | --- | --- |
| OAuth refresh token | GitHub Actions encrypted secrets | Authenticate scheduled uploads |
| OAuth client ID and secret | GitHub Actions encrypted secrets | Authenticate scheduled uploads |
| YouTube video IDs of its own uploads | `data/state-hadith.json`, `data/state-adkar.json` in the source repository | Prevent re-publishing the same supplication |
| Channel handle | `src/adkar_bot/profiles.py` in the source repository | Rendered as a caption on each video |

No personal information, viewer data, or third-party user data is stored at any
point. The application maintains no database and no server.

## What data is shared

None. The application transmits data only to the YouTube Data API, and only in
order to upload the owner's own videos. Nothing is shared with, sold to, or
disclosed to any third party. There is no analytics, telemetry, or advertising
of any kind.

## Data retention and deletion

Stored credentials exist only as GitHub Actions secrets under the owner's
control and can be deleted at any time from the repository settings.

The owner may revoke the application's access to their Google account at any
time at [myaccount.google.com/permissions](https://myaccount.google.com/permissions).
Revoking access immediately and permanently ends the application's ability to
upload, and no further data is accessed.

Uploaded videos remain the property of the channel owner and are managed through
YouTube directly.

## YouTube API Services

This application uses YouTube API Services. By using it, its owner is bound by
the [YouTube Terms of Service](https://www.youtube.com/t/terms) and the
[Google Privacy Policy](https://policies.google.com/privacy).

## Changes

Any change to this policy will be published in this file in the application's
source repository, with the revision date above updated.
