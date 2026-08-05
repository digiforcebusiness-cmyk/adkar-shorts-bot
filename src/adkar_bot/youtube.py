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
