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
