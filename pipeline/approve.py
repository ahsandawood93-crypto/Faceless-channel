"""Stage 5: approval gate in Telegram. Nothing goes public without your tap.

send:   after the private upload, sends you the thumbnail, SEO title, a link to
        the private video and the review_notes checklist, with Approve / Reject
        buttons. Status -> awaiting_approval.
listen: polls Telegram (no server, no webhook). Approve -> schedule (Stage 6)
        -> status scheduled. Reject -> asks for a reason, stores it in
        episode.json -> status rejected. Only your TELEGRAM_CHAT_ID is obeyed.
"""

import html
import time
from pathlib import Path

import requests

from pipeline.config import require_env
from pipeline import episode as episode_module
from pipeline.episode import Episode
from pipeline.util import StageError, info, step, warn, with_retries

API = "https://api.telegram.org/bot{token}/{method}"
CAPTION_LIMIT, MESSAGE_LIMIT = 1024, 4096


def _transient(error):
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return True
    response = getattr(error, "response", None)
    return response is not None and (response.status_code == 429 or response.status_code >= 500)


class Telegram:
    def __init__(self, token, chat_id, session=None):
        self.token, self.chat_id = token, str(chat_id)
        self.session = session or requests.Session()

    @classmethod
    def from_env(cls):
        keys = require_env("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
        return cls(keys["TELEGRAM_BOT_TOKEN"], keys["TELEGRAM_CHAT_ID"])

    def call(self, method, files=None, timeout=60, **params):
        def do():
            resp = self.session.post(API.format(token=self.token, method=method), data=params,
                                     files=files, timeout=timeout)
            if resp.status_code == 429 or resp.status_code >= 500:
                resp.raise_for_status()
            return resp.json()
        data = with_retries(do, _transient, label=f"Telegram {method}: ")
        if not data.get("ok"):
            raise StageError(f"Telegram {method} failed: {data.get('description')}")
        return data["result"]

    def send(self, text, **params):
        return self.call("sendMessage", chat_id=self.chat_id, text=text[:MESSAGE_LIMIT], parse_mode="HTML", **params)


# ---- message building ------------------------------------------------------------

def checklist(episode):
    notes = episode.data["review_notes"]
    if not notes:
        return "✅ Nothing flagged automatically."
    lines = []
    for note in notes:
        where = f"Scene {note['scene']}: " if note.get("scene") else ""
        lines.append(f"☐ {html.escape(where + note['message'])}")
    return "\n".join(lines)


def approval_text(episode):
    yt, final = episode.data["youtube"], episode.data.get("final", {})
    minutes = final.get("seconds", 0) / 60
    return (f"<b>Approve this episode?</b>\n"
            f"<b>{html.escape(episode.data['seo']['title'])}</b>\n"
            f"{minutes:.1f} min · <code>{episode.slug}</code>\n"
            f"Private video: {yt.get('url')}\n\n"
            f"<b>Review notes</b>\n{checklist(episode)}\n\n"
            f"Also check: facts, nothing scary, no brands/real people, recap + goodbye.")


def buttons(slug):
    import json

    return json.dumps({"inline_keyboard": [[
        {"text": "✅ Approve", "callback_data": f"approve:{slug}"},
        {"text": "❌ Reject", "callback_data": f"reject:{slug}"},
    ]]})


# ---- send for approval -------------------------------------------------------------

def send_for_approval(episode, bot=None):
    step(f"Stage 5 · Approval request · {episode.slug}")
    if not (episode.data.get("youtube") or {}).get("video_id"):
        raise StageError(f"Upload the private video first: python run.py upload {episode.slug}")
    bot = bot or Telegram.from_env()
    thumb = episode.dir / episode.data["final"]["thumbnail"]
    caption = f"<b>{html.escape(episode.data['title'])}</b>\n{episode.data['youtube'].get('url')}"
    with open(thumb, "rb") as f:
        bot.call("sendPhoto", files={"photo": f}, chat_id=bot.chat_id, caption=caption[:CAPTION_LIMIT],
                 parse_mode="HTML")
    message = bot.send(approval_text(episode), reply_markup=buttons(episode.slug))
    episode.data["approval"] = {"message_id": message["message_id"], "awaiting_reason": False,
                                "reason_prompt_id": None}
    episode.set_status("awaiting_approval")
    info("Sent to Telegram. Tap Approve or Reject, then run: python run.py approve --listen (or --once)")
    return message


# ---- handling taps and replies ------------------------------------------------------

def _episodes(episodes_dir):
    return [Episode.load(f) for f in sorted(Path(episodes_dir).glob("*/episode.json"))]


def _offset_file(episodes_dir):
    return Path(episodes_dir) / ".telegram_offset"


def handle_callback(query, bot, channel, episodes_dir, schedule_fn):
    action, _, slug = (query.get("data") or "").partition(":")
    try:
        episode = Episode.load(slug, episodes_dir)
    except FileNotFoundError:
        bot.call("answerCallbackQuery", callback_query_id=query["id"], text="Unknown episode")
        return
    if episode.status != "awaiting_approval":
        bot.call("answerCallbackQuery", callback_query_id=query["id"], text=f"Already {episode.status}")
        return
    message = query.get("message") or {}
    if action == "approve":
        bot.call("answerCallbackQuery", callback_query_id=query["id"], text="Scheduling...")
        try:
            slot = schedule_fn(episode, channel)
        except Exception as e:  # noqa: BLE001 - report back in the chat
            bot.send(f"⚠️ Could not schedule <code>{slug}</code>: {html.escape(str(e))}\n"
                     f"Fix it, then run: <code>python run.py approve {slug} --schedule</code>")
            warn(f"Scheduling {slug} failed: {e}")
            return
        if message:
            bot.call("editMessageReplyMarkup", chat_id=bot.chat_id, message_id=message["message_id"],
                     reply_markup='{"inline_keyboard": []}')
        bot.send(f"✅ <b>Approved.</b> <code>{slug}</code> publishes {episode.data['youtube']['publish_at']} "
                 f"(UTC).")
        info(f"{slug}: approved and scheduled for {slot}")
    elif action == "reject":
        bot.call("answerCallbackQuery", callback_query_id=query["id"], text="Rejected")
        prompt = bot.send(f"❌ Why are you rejecting <code>{slug}</code>? Reply to this message with the reason.",
                          reply_markup='{"force_reply": true}')
        episode.data.setdefault("approval", {}).update(awaiting_reason=True, reason_prompt_id=prompt["message_id"])
        episode.save()
        if message:
            bot.call("editMessageReplyMarkup", chat_id=bot.chat_id, message_id=message["message_id"],
                     reply_markup='{"inline_keyboard": []}')


def handle_message(msg, bot, episodes_dir):
    text = (msg.get("text") or "").strip()
    if not text or text.startswith("/"):
        return
    waiting = [e for e in _episodes(episodes_dir) if (e.data.get("approval") or {}).get("awaiting_reason")]
    reply_to = (msg.get("reply_to_message") or {}).get("message_id")
    match = [e for e in waiting if e.data["approval"].get("reason_prompt_id") == reply_to]
    if not match and len(waiting) == 1:
        match = waiting
    if not match:
        return
    episode = match[0]
    episode.data["rejection_reason"] = text
    episode.data["approval"]["awaiting_reason"] = False
    episode.set_status("rejected")
    bot.send(f"Recorded. <code>{episode.slug}</code> is rejected: {html.escape(text)}")
    info(f"{episode.slug}: rejected ({text})")


def process_updates(channel, bot=None, episodes_dir=None, timeout=30, schedule_fn=None):
    """Fetch and handle new Telegram updates once. Returns how many were handled."""
    from pipeline.upload import schedule

    bot = bot or Telegram.from_env()
    episodes_dir = Path(episodes_dir or episode_module.EPISODES_DIR)
    schedule_fn = schedule_fn or schedule
    offset_file = _offset_file(episodes_dir)
    offset = int(offset_file.read_text()) if offset_file.exists() else 0
    updates = bot.call("getUpdates", offset=offset, timeout=timeout,
                       allowed_updates='["callback_query","message"]')
    for update in updates:
        offset_file.write_text(str(update["update_id"] + 1))
        query, msg = update.get("callback_query"), update.get("message")
        chat = ((query or {}).get("message") or {}).get("chat", {}).get("id") if query else \
            (msg or {}).get("chat", {}).get("id")
        if str(chat) != bot.chat_id:
            continue  # ignore anyone else who finds the bot
        if query:
            handle_callback(query, bot, channel, episodes_dir, schedule_fn)
        elif msg:
            handle_message(msg, bot, episodes_dir)
    return len(updates)


def listen(channel, once=False, bot=None, episodes_dir=None):
    step("Stage 5 · Listening for Approve / Reject in Telegram" + (" (once)" if once else " (Ctrl+C to stop)"))
    bot = bot or Telegram.from_env()
    while True:
        handled = process_updates(channel, bot, episodes_dir, timeout=0 if once else 30)
        if once and handled == 0:
            info("No more Telegram updates.")
            return
        if not once:
            time.sleep(1)
