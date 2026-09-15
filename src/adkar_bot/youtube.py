import time
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config
from .profiles import Profile

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


class WrongChannel(UploadError):
    """The authenticated channel is not the profile's channel."""


class VerificationFailed(UploadError):
    """Verification encountered a transient or unknown error."""


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
    Retries transient errors on the same schedule as upload_video.
    """
    response, attempt = None, 0
    while response is None:
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
            if exc.resp.status not in RETRYABLE or attempt >= 5:
                raise VerificationFailed(
                    f"could not verify the channel for profile {profile.name!r}: {exc}"
                ) from exc
            attempt += 1
            time.sleep(2 ** attempt)

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
