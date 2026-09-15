from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from googleapiclient.errors import HttpError
from adkar_bot import config
from adkar_bot.profiles import ADKAR, HADITH
from adkar_bot.youtube import (
    UploadError,
    VerificationFailed,
    WrongChannel,
    build_client,
    upload_video,
    verify_channel,
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


def test_build_client_passes_correct_scopes(monkeypatch):
    """build_client passes config.SCOPES to the credentials.

    This test guards against accidental scope broadening, which is a
    security surface. It validates the exact scope list, not just that
    some scopes are passed.
    """
    captured = {}

    def fake_build(serviceName, version, credentials=None, **kwargs):
        captured["creds"] = credentials
        return MagicMock()

    monkeypatch.setattr("adkar_bot.youtube.build", fake_build)
    build_client("cid", "csecret", "rtoken")

    creds = captured["creds"]
    assert creds.refresh_token == "rtoken"
    assert creds.token is None  # refreshed lazily, not fetched eagerly
    # Literal assertion to guard against accidental scope broadening
    assert config.SCOPES == [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
    assert set(creds.scopes) == set(config.SCOPES)


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


def test_verify_channel_retries_on_retryable_status(monkeypatch):
    """verify_channel should retry transient errors with exponential backoff."""
    monkeypatch.setattr("adkar_bot.youtube.time.sleep", lambda _: None)

    call_count = [0]
    def execute_with_retries():
        call_count[0] += 1
        if call_count[0] <= 2:
            # First two calls fail with retryable errors
            response = MagicMock()
            response.status = 503
            raise HttpError(response, b"{}")
        # Third call succeeds
        return {"items": [{"snippet": {"customUrl": "@DIKR-o6k"}}]}

    client = MagicMock()
    client.channels.return_value.list.return_value.execute.side_effect = execute_with_retries

    # Should succeed after retries
    assert verify_channel(client, ADKAR) is None
    assert call_count[0] == 3


def test_transient_error_raises_verification_failed():
    """A transient HTTP error should raise VerificationFailed, not WrongChannel."""
    with pytest.raises(VerificationFailed):
        # A 500 error on the final attempt after retries exhausted
        client = MagicMock()
        response = MagicMock()
        response.status = 500
        client.channels.return_value.list.return_value.execute.side_effect = (
            HttpError(response, b"{}")
        )
        verify_channel(client, HADITH)
