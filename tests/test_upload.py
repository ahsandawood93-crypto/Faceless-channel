from datetime import datetime, timezone

import pytest

from pipeline import upload
from pipeline.util import StageError

DUBAI = {"timezone": "Asia/Dubai", "days": ["Mon", "Wed", "Fri"], "time": "16:00"}  # 16:00 Dubai = 12:00 UTC


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


# ---- schedule slots --------------------------------------------------------------------

def test_next_slot_same_day_if_time_left():
    # Mon 12 Oct 2026, 08:00 UTC (12:00 Dubai) -> today 16:00 Dubai
    assert upload.next_free_slot(DUBAI, now=utc(2026, 10, 12, 8)) == utc(2026, 10, 12, 12)


def test_next_slot_respects_min_lead_and_days():
    # Mon 11:00 UTC is less than 2 h before the 12:00 UTC slot -> Wed
    assert upload.next_free_slot(DUBAI, now=utc(2026, 10, 12, 11)) == utc(2026, 10, 14, 12)
    # Saturday -> Monday
    assert upload.next_free_slot(DUBAI, now=utc(2026, 10, 17, 9)) == utc(2026, 10, 19, 12)


def test_taken_slots_are_skipped():
    taken = {utc(2026, 10, 12, 12), utc(2026, 10, 14, 12)}
    assert upload.next_free_slot(DUBAI, taken, now=utc(2026, 10, 12, 8)) == utc(2026, 10, 16, 12)


def test_taken_slots_come_from_scheduled_episodes(drafted, episodes_dir):
    drafted.data["youtube"]["publish_at"] = "2026-10-12T12:00:00Z"
    drafted.set_status("scheduled")
    assert upload.taken_slots(episodes_dir) == {utc(2026, 10, 12, 12)}
    assert upload.taken_slots(episodes_dir, exclude=drafted.slug) == set()


# ---- fake YouTube service ------------------------------------------------------------------

class Call:
    def __init__(self, service, name, kwargs):
        self.service, self.name, self.kwargs = service, name, kwargs

    def execute(self):
        self.service.executed.append((self.name, self.kwargs))
        if self.name in self.service.fail:
            raise self.service.fail[self.name]
        return {}

    def next_chunk(self):
        self.service.executed.append((self.name, self.kwargs))
        return None, {"id": "vid123"}


class Resource:
    def __init__(self, service, prefix):
        self.service, self.prefix = service, prefix

    def __getattr__(self, method):
        return lambda **kwargs: Call(self.service, f"{self.prefix}.{method}", kwargs)


class FakeYouTube:
    def __init__(self, fail=None):
        self.executed, self.fail = [], fail or {}

    def videos(self):
        return Resource(self, "videos")

    def thumbnails(self):
        return Resource(self, "thumbnails")

    def captions(self):
        return Resource(self, "captions")

    def calls(self, name):
        return [kw for n, kw in self.executed if n == name]


@pytest.fixture
def rendered(drafted):
    final = drafted.path("final", "episode.mp4").parent
    for name, data in (("episode.mp4", b"\x00" * 1000), ("thumbnail.jpg", b"\xff\xd8jpg"),
                       ("episode.srt", b"1\n00:00:00,000 --> 00:00:01,000\nHi\n")):
        (final / name).write_bytes(data)
    drafted.data["final"] = {"video": "final/episode.mp4", "thumbnail": "final/thumbnail.jpg",
                             "srt": "final/episode.srt", "seconds": 180, "placeholder": False}
    for status in ("voiced", "clips_ready", "rendered"):
        drafted.set_status(status)
    return drafted


def test_upload_is_private_and_made_for_kids(rendered):
    yt = FakeYouTube()
    assert upload.upload_private(rendered, service=yt, sleep=lambda s: None) == "vid123"
    body = yt.calls("videos.insert")[0]["body"]
    assert body["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": True, "embeddable": True}
    assert body["snippet"]["categoryId"] == "27"
    assert body["snippet"]["defaultLanguage"] == "en"
    assert body["snippet"]["title"] == rendered.data["seo"]["title"]
    assert body["snippet"]["tags"] == ["abc", "letter a"]
    assert yt.calls("thumbnails.set")[0]["videoId"] == "vid123"
    caption = yt.calls("captions.insert")[0]["body"]["snippet"]
    assert caption == {"videoId": "vid123", "language": "en", "name": "English", "isDraft": False}
    assert rendered.data["youtube"]["url"] == "https://youtu.be/vid123"
    assert rendered.status == "rendered"  # uploading alone never publishes or schedules


def test_rerun_does_not_upload_twice(rendered):
    upload.upload_private(rendered, service=FakeYouTube(), sleep=lambda s: None)
    yt = FakeYouTube()
    upload.upload_private(rendered, service=yt, sleep=lambda s: None)
    assert yt.executed == []


def test_thumbnail_failure_is_a_review_note(rendered):
    class Forbidden(Exception):
        status_code = 403

    yt = FakeYouTube(fail={"thumbnails.set": Forbidden("forbidden")})
    upload.upload_private(rendered, service=yt, sleep=lambda s: None)
    assert any("Thumbnail upload failed" in n["message"] for n in rendered.data["review_notes"])
    assert yt.calls("captions.insert")  # carried on


def test_placeholders_are_never_uploaded(rendered):
    rendered.data["final"]["placeholder"] = True
    with pytest.raises(StageError, match="placeholders"):
        upload.upload_private(rendered, service=FakeYouTube())


def test_schedule_sets_publish_at(rendered, channel, episodes_dir):
    upload.upload_private(rendered, service=FakeYouTube(), sleep=lambda s: None)
    rendered.set_status("awaiting_approval")
    yt = FakeYouTube()
    upload.schedule(rendered, channel, service=yt, now=utc(2026, 10, 12, 8), episodes_dir=episodes_dir)
    body = yt.calls("videos.update")[0]["body"]
    assert body["id"] == "vid123"
    assert body["status"]["publishAt"] == "2026-10-12T12:00:00Z"
    assert body["status"]["privacyStatus"] == "private" and body["status"]["selfDeclaredMadeForKids"] is True
    assert rendered.status == "scheduled" and rendered.data["youtube"]["publish_at"] == "2026-10-12T12:00:00Z"


def test_schedule_needs_upload(drafted, channel):
    with pytest.raises(StageError, match="python run.py upload"):
        upload.schedule(drafted, channel, service=FakeYouTube())
