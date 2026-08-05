from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from googleapiclient.errors import HttpError
from adkar_bot import config
from adkar_bot.youtube import (
    UploadError,
    build_client,
    upload_video,
)


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


def http_error(status: int) -> HttpError:
    """An HttpError whose .resp.status is what the retry logic inspects."""
    return HttpError(SimpleNamespace(status=status, reason="test"), b"{}")


class FlakyInsert:
    """next_chunk() raises the queued errors, then returns the final response."""

    def __init__(self, errors, final):
        self.errors = list(errors)
        self.final = final
        self.calls = 0

    def next_chunk(self):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return None, self.final


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


def test_upload_retries_on_retryable_status(tmp_path, monkeypatch):
    monkeypatch.setattr("adkar_bot.youtube.time.sleep", lambda _: None)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    insert = FlakyInsert([http_error(503), http_error(429)], {"id": "ok1"})
    client = MagicMock()
    client.videos.return_value.insert.return_value = insert

    assert upload_video(client, f, "t", "d", ["a"]) == "ok1"
    assert insert.calls == 3  # two failures then success


def test_upload_does_not_retry_non_retryable_status(tmp_path, monkeypatch):
    monkeypatch.setattr("adkar_bot.youtube.time.sleep", lambda _: None)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    insert = FlakyInsert([http_error(403)], {"id": "never"})
    client = MagicMock()
    client.videos.return_value.insert.return_value = insert

    with pytest.raises(UploadError):
        upload_video(client, f, "t", "d", ["a"])
    assert insert.calls == 1  # gave up immediately, did not retry


def test_upload_gives_up_after_the_attempt_bound(tmp_path, monkeypatch):
    monkeypatch.setattr("adkar_bot.youtube.time.sleep", lambda _: None)
    f = tmp_path / "v.mp4"
    f.write_bytes(b"x")
    insert = FlakyInsert([http_error(500)] * 20, {"id": "never"})
    client = MagicMock()
    client.videos.return_value.insert.return_value = insert

    with pytest.raises(UploadError):
        upload_video(client, f, "t", "d", ["a"])
    assert insert.calls == 6  # attempt=0..5 retried, attempt=5 gives up: 6 calls


def test_build_client_uses_upload_scope_only(monkeypatch):
    """Commenting is gone, so upload is the only scope the client needs."""
    captured = {}

    def fake_build(serviceName, version, credentials=None, **kwargs):
        captured["creds"] = credentials
        return MagicMock()

    monkeypatch.setattr("adkar_bot.youtube.build", fake_build)
    build_client("cid", "csecret", "rtoken")

    creds = captured["creds"]
    assert creds.refresh_token == "rtoken"
    assert creds.token is None  # refreshed lazily, not fetched eagerly
    assert set(creds.scopes) == {
        "https://www.googleapis.com/auth/youtube.upload",
    }
