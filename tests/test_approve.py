import json

import pytest

from pipeline import approve
from pipeline.episode import Episode
from pipeline.util import StageError


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data, self.status_code = data, status_code

    def json(self):
        return self.data

    def raise_for_status(self):
        pass


class FakeSession:
    """Records Telegram calls; getUpdates returns queued batches."""

    def __init__(self, updates=None):
        self.calls, self.updates, self.next_id = [], list(updates or []), 100

    def post(self, url, data=None, files=None, timeout=None):
        method = url.rsplit("/", 1)[-1]
        self.calls.append((method, data, files))
        if method == "getUpdates":
            return FakeResponse({"ok": True, "result": self.updates.pop(0) if self.updates else []})
        self.next_id += 1
        return FakeResponse({"ok": True, "result": {"message_id": self.next_id}})

    def sent(self, method):
        return [d for m, d, _ in self.calls if m == method]


def bot(session):
    return approve.Telegram("TOKEN", "42", session=session)


@pytest.fixture
def uploaded(drafted):
    final = drafted.path("final", "thumbnail.jpg").parent
    (final / "thumbnail.jpg").write_bytes(b"\xff\xd8jpg")
    drafted.data["final"] = {"video": "final/episode.mp4", "thumbnail": "final/thumbnail.jpg",
                             "srt": "final/episode.srt", "seconds": 186, "placeholder": False}
    drafted.data["youtube"] = {"video_id": "vid123", "url": "https://youtu.be/vid123", "publish_at": None}
    drafted.add_review_note("Voice is 9.1 s, 1.1 s longer than the 8 s clip", stage="voice", scene=2)
    for status in ("voiced", "clips_ready", "rendered"):
        drafted.set_status(status)
    return drafted


def callback(data, chat=42, update_id=1, message_id=101):
    return {"update_id": update_id, "callback_query": {"id": "cb1", "data": data,
                                                       "message": {"message_id": message_id, "chat": {"id": chat}}}}


def text_message(text, chat=42, update_id=2, reply_to=None):
    msg = {"message_id": 500, "chat": {"id": chat}, "text": text}
    if reply_to:
        msg["reply_to_message"] = {"message_id": reply_to}
    return {"update_id": update_id, "message": msg}


def test_send_for_approval(uploaded):
    session = FakeSession()
    approve.send_for_approval(uploaded, bot=bot(session))
    photo = session.calls[0]
    assert photo[0] == "sendPhoto" and "photo" in photo[2] and "youtu.be/vid123" in photo[1]["caption"]
    message = session.sent("sendMessage")[0]
    assert "Letter A for Toddlers | Minsa Kids TV" in message["text"]
    assert "☐ Scene 2: Voice is 9.1 s" in message["text"]
    keyboard = json.loads(message["reply_markup"])["inline_keyboard"][0]
    assert [b["callback_data"] for b in keyboard] == [f"approve:{uploaded.slug}", f"reject:{uploaded.slug}"]
    assert uploaded.status == "awaiting_approval"


def test_needs_upload_first(drafted):
    with pytest.raises(StageError, match="python run.py upload"):
        approve.send_for_approval(drafted, bot=bot(FakeSession()))


def test_approve_tap_schedules(uploaded, channel, episodes_dir):
    approve.send_for_approval(uploaded, bot=bot(FakeSession()))
    scheduled = []

    def fake_schedule(episode, ch):
        scheduled.append(episode.slug)
        episode.data["youtube"]["publish_at"] = "2026-10-14T12:00:00Z"
        episode.set_status("scheduled")
        return "slot"

    session = FakeSession([[callback(f"approve:{uploaded.slug}")]])
    approve.process_updates(channel, bot(session), episodes_dir, timeout=0, schedule_fn=fake_schedule)
    assert scheduled == [uploaded.slug]
    assert Episode.load(uploaded.slug, episodes_dir).status == "scheduled"
    assert "Approved" in session.sent("sendMessage")[-1]["text"]
    assert (episodes_dir / ".telegram_offset").read_text() == "2"


def test_reject_asks_for_reason_and_records_it(uploaded, channel, episodes_dir):
    approve.send_for_approval(uploaded, bot=bot(FakeSession()))
    session = FakeSession([[callback(f"reject:{uploaded.slug}")]])
    approve.process_updates(channel, bot(session), episodes_dir, timeout=0)
    prompt_id = session.next_id - 1  # sendMessage (reason prompt) came before editMessageReplyMarkup
    assert "Why are you rejecting" in session.sent("sendMessage")[0]["text"]
    assert Episode.load(uploaded.slug, episodes_dir).status == "awaiting_approval"

    session = FakeSession([[text_message("The apple looks scary", reply_to=prompt_id, update_id=5)]])
    approve.process_updates(channel, bot(session), episodes_dir, timeout=0)
    ep = Episode.load(uploaded.slug, episodes_dir)
    assert ep.status == "rejected" and ep.data["rejection_reason"] == "The apple looks scary"


def test_strangers_are_ignored(uploaded, channel, episodes_dir):
    approve.send_for_approval(uploaded, bot=bot(FakeSession()))
    session = FakeSession([[callback(f"approve:{uploaded.slug}", chat=999)]])
    approve.process_updates(channel, bot(session), episodes_dir, timeout=0,
                            schedule_fn=lambda e, c: pytest.fail("must not schedule"))
    assert Episode.load(uploaded.slug, episodes_dir).status == "awaiting_approval"


def test_double_tap_is_harmless(uploaded, channel, episodes_dir):
    uploaded.set_status("scheduled")
    session = FakeSession([[callback(f"approve:{uploaded.slug}")]])
    approve.process_updates(channel, bot(session), episodes_dir, timeout=0,
                            schedule_fn=lambda e, c: pytest.fail("must not schedule twice"))
    assert session.sent("answerCallbackQuery")[0]["text"] == "Already scheduled"


def test_schedule_error_is_reported_in_chat(uploaded, channel, episodes_dir):
    approve.send_for_approval(uploaded, bot=bot(FakeSession()))

    def broken(episode, ch):
        raise StageError("quota exceeded")

    session = FakeSession([[callback(f"approve:{uploaded.slug}")]])
    approve.process_updates(channel, bot(session), episodes_dir, timeout=0, schedule_fn=broken)
    assert "quota exceeded" in session.sent("sendMessage")[-1]["text"]
    assert Episode.load(uploaded.slug, episodes_dir).status == "awaiting_approval"


def test_telegram_error_is_raised():
    class Bad(FakeSession):
        def post(self, url, data=None, files=None, timeout=None):
            return FakeResponse({"ok": False, "description": "chat not found"})

    with pytest.raises(StageError, match="chat not found"):
        bot(Bad()).send("hi")
