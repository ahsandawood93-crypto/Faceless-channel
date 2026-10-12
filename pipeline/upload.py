"""Stage 6: YouTube upload (always private) and scheduling after approval.

upload:   videos.insert as PRIVATE, madeForKids, Education, English, then
          thumbnails.set and captions.insert. Nothing is public at this point.
schedule: only after you approve in Telegram. Sets status.publishAt to the
          next free slot from channel.yaml's schedule; YouTube publishes it then.

NOTE: uploads from an unaudited Google API project stay locked to private,
even with publishAt. See README "YouTube: audit and quota".
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline.config import ROOT, WEEKDAYS, env
from pipeline import episode as episode_module
from pipeline.episode import Episode
from pipeline.util import StageError, info, is_transient_http, step, warn, with_retries

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.force-ssl"]
CATEGORY_EDUCATION = "27"
MIN_LEAD = timedelta(hours=2)   # never schedule a slot closer than this
SEARCH_DAYS = 120


# ---- auth ---------------------------------------------------------------------

def _path(name, default):
    p = Path(env(name, default))
    return p if p.is_absolute() else ROOT / p


def get_credentials():
    """OAuth in the browser on first run; afterwards the cached token is reused/refreshed."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    secret = _path("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
    token = _path("YOUTUBE_TOKEN_FILE", "youtube_token.json")
    creds = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        if not secret.exists():
            raise StageError(f"{secret} not found. Create an OAuth client (Desktop app) in Google Cloud "
                             "and download it; see README 'YouTube setup'.")
        info("Opening your browser to sign in to YouTube (first run only)...")
        creds = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES).run_local_server(port=0)
    token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def make_service():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=get_credentials(), cache_discovery=False)


# ---- schedule -------------------------------------------------------------------

def taken_slots(episodes_dir=None, exclude=None):
    """publishAt times already used by scheduled episodes (UTC datetimes)."""
    taken = set()
    for file in Path(episodes_dir or episode_module.EPISODES_DIR).glob("*/episode.json"):
        ep = Episode.load(file)
        at = ep.data.get("youtube", {}).get("publish_at")
        if at and ep.status == "scheduled" and ep.slug != exclude:
            taken.add(datetime.fromisoformat(at.replace("Z", "+00:00")))
    return taken


def next_free_slot(schedule, taken=(), now=None):
    """Next schedule slot (as an aware UTC datetime) that is not already taken."""
    tz = ZoneInfo(schedule["timezone"])
    hour, minute = map(int, schedule["time"].split(":"))
    days = {WEEKDAYS.index(d) for d in schedule["days"]}
    now = now or datetime.now(timezone.utc)
    taken = {t.astimezone(timezone.utc) for t in taken}
    local = now.astimezone(tz)
    for offset in range(SEARCH_DAYS):
        day = (local + timedelta(days=offset)).date()
        if day.weekday() not in days:
            continue
        slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz).astimezone(timezone.utc)
        if slot >= now + MIN_LEAD and slot not in taken:
            return slot
    raise StageError(f"No free publish slot in the next {SEARCH_DAYS} days.")


def utc_z(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- API calls ---------------------------------------------------------------------

def _upload_video(service, episode, sleep):
    from googleapiclient.http import MediaFileUpload

    seo = episode.data["seo"]
    body = {
        "snippet": {
            "title": seo["title"][:100], "description": seo["description"][:5000],
            "tags": seo["tags"], "categoryId": CATEGORY_EDUCATION,
            "defaultLanguage": "en", "defaultAudioLanguage": "en",
        },
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": True, "embeddable": True},
    }
    media = MediaFileUpload(str(episode.dir / episode.data["final"]["video"]), mimetype="video/mp4",
                            chunksize=8 * 1024 * 1024, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response, last = None, -1
    while response is None:
        progress, response = with_retries(request.next_chunk, is_transient_http, sleep=sleep, label="Upload: ")
        if progress and int(progress.progress() * 100) // 10 != last:
            last = int(progress.progress() * 100) // 10
            info(f"Uploading... {int(progress.progress() * 100)}%")
    return response["id"]


def upload_private(episode, service=None, sleep=None):
    """Upload as private (or resume after a partial run). Returns the video id."""
    import time

    sleep = sleep or time.sleep
    step(f"Stage 6 · Upload (private) · {episode.slug}")
    if not episode.reached("rendered"):
        raise StageError(f"Render the episode first: python run.py assemble {episode.slug}")
    final = episode.data.get("final") or {}
    if final.get("placeholder"):
        raise StageError("This render contains --no-voice/--no-video placeholders and will not be uploaded. "
                         f"Run the real stages first: python run.py all {episode.slug}")
    yt = episode.data.setdefault("youtube", {})
    service = service or make_service()

    if not yt.get("video_id"):
        yt["video_id"] = _upload_video(service, episode, sleep)
        yt["url"] = f"https://youtu.be/{yt['video_id']}"
        yt["studio_url"] = f"https://studio.youtube.com/video/{yt['video_id']}/edit"
        episode.save()
        info(f"Uploaded as private: {yt['url']}")
    else:
        info(f"Already uploaded: {yt.get('url')}")

    from googleapiclient.http import MediaFileUpload

    if not yt.get("thumbnail_set"):
        try:
            with_retries(lambda: service.thumbnails().set(
                videoId=yt["video_id"],
                media_body=MediaFileUpload(str(episode.dir / final["thumbnail"]), mimetype="image/jpeg"),
            ).execute(), is_transient_http, sleep=sleep, label="Thumbnail: ")
            yt["thumbnail_set"] = True
            info("Thumbnail set")
        except Exception as e:  # noqa: BLE001 - e.g. channel not phone-verified for custom thumbnails
            episode.add_review_note(f"Thumbnail upload failed: {e}. Custom thumbnails need a verified "
                                    "channel (youtube.com/verify). Set it in YouTube Studio.", stage="upload")
            warn(f"Thumbnail failed: {e}")
    if not yt.get("captions_set"):
        try:
            with_retries(lambda: service.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": yt["video_id"], "language": "en", "name": "English",
                                  "isDraft": False}},
                media_body=MediaFileUpload(str(episode.dir / final["srt"]), mimetype="application/octet-stream"),
            ).execute(), is_transient_http, sleep=sleep, label="Captions: ")
            yt["captions_set"] = True
            info("Captions uploaded")
        except Exception as e:  # noqa: BLE001
            episode.add_review_note(f"Captions upload failed: {e}. Upload final/episode.srt in YouTube Studio.",
                                    stage="upload")
            warn(f"Captions failed: {e}")
    episode.save()
    return yt["video_id"]


def schedule(episode, channel, service=None, now=None, episodes_dir=None):
    """Set publishAt to the next free slot. Only called after approval."""
    step(f"Stage 6 · Schedule · {episode.slug}")
    yt = episode.data.get("youtube") or {}
    if not yt.get("video_id"):
        raise StageError(f"Not uploaded yet: python run.py upload {episode.slug}")
    slot = next_free_slot(channel["schedule"], taken_slots(episodes_dir, exclude=episode.slug), now=now)
    service = service or make_service()
    with_retries(lambda: service.videos().update(part="status", body={
        "id": yt["video_id"],
        "status": {"privacyStatus": "private", "publishAt": utc_z(slot),
                   "selfDeclaredMadeForKids": True, "embeddable": True},
    }).execute(), is_transient_http, label="Schedule: ")
    yt["publish_at"] = utc_z(slot)
    episode.data["youtube"] = yt
    episode.set_status("scheduled")
    local = slot.astimezone(ZoneInfo(channel["schedule"]["timezone"]))
    info(f"Scheduled for {local:%a %d %b %Y %H:%M} {channel['schedule']['timezone']} ({yt['publish_at']})")
    return slot
