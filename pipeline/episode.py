"""episodes/<slug>/episode.json: the single source of truth for one episode."""

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config import ROOT

EPISODES_DIR = ROOT / "episodes"

# The normal path through the pipeline, in order. "new" means only the topic
# is known (folder created, script not written yet). "rejected" is a dead end
# reached from awaiting_approval.
STATUSES = ["new", "drafted", "voiced", "clips_ready", "rendered", "awaiting_approval", "scheduled"]
REJECTED = "rejected"


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slugify(topic, max_length=50):
    """'The Letter A — Apples!' -> 'the-letter-a-apples'"""
    text = unicodedata.normalize("NFKD", topic).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    text = text[:max_length].rstrip("-")
    return text or "episode"


def new_episode_data(slug, topic):
    created = now_iso()
    return {
        "slug": slug,
        "topic": topic,
        "status": "new",
        "created_at": created,
        "title": "",
        "scenes": [],
        "seo": {"title": "", "description": "", "tags": []},
        "review_notes": [],
        "youtube": {"video_id": None, "publish_at": None},
        "rejection_reason": None,
        "history": [{"at": created, "status": "new"}],
    }


class Episode:
    """One episode folder plus its episode.json contents (in .data)."""

    def __init__(self, folder, data):
        self.dir = Path(folder)
        self.data = data

    # ---- create / load / save -------------------------------------------

    @classmethod
    def create(cls, topic, episodes_dir=None):
        """Make a new episode folder for a topic. Repeated topics get -2, -3..."""
        topic = topic.strip()
        if not topic:
            raise ValueError("Topic is empty")
        episodes_dir = Path(episodes_dir or EPISODES_DIR)
        base = slugify(topic)
        slug, n = base, 2
        while (episodes_dir / slug).exists():
            slug, n = f"{base}-{n}", n + 1
        folder = episodes_dir / slug
        folder.mkdir(parents=True)
        episode = cls(folder, new_episode_data(slug, topic))
        episode.save()
        return episode

    @classmethod
    def load(cls, slug_or_path, episodes_dir=None):
        """Load by slug ('letter-a') or by folder / episode.json path."""
        path = Path(slug_or_path)
        if path.name == "episode.json":
            path = path.parent
        elif not path.is_dir():
            path = Path(episodes_dir or EPISODES_DIR) / str(slug_or_path)
        file = path / "episode.json"
        if not file.exists():
            raise FileNotFoundError(f"No episode.json in {path}")
        with open(file, encoding="utf-8") as f:
            return cls(path, json.load(f))

    @property
    def file(self):
        return self.dir / "episode.json"

    @property
    def slug(self):
        return self.data["slug"]

    def save(self):
        """Write to a temp file, then rename, so a crash never leaves half a file."""
        tmp = self.file.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, self.file)

    def path(self, *parts):
        """Path inside the episode folder, creating parent folders as needed."""
        p = self.dir.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # ---- status -----------------------------------------------------------

    @property
    def status(self):
        return self.data["status"]

    def set_status(self, status):
        if status not in STATUSES and status != REJECTED:
            raise ValueError(f"Unknown status {status!r}")
        self.data["status"] = status
        self.data["history"].append({"at": now_iso(), "status": status})
        self.save()

    def reached(self, status):
        """True if the episode is at `status` or further along the normal path."""
        if status == REJECTED:
            return self.status == REJECTED
        current = "awaiting_approval" if self.status == REJECTED else self.status
        return STATUSES.index(current) >= STATUSES.index(status)

    # ---- review notes -------------------------------------------------------

    def add_review_note(self, message, stage=None, scene=None):
        """Something a human should check before approving. Saved immediately."""
        note = {"at": now_iso(), "stage": stage, "scene": scene, "message": message}
        self.data["review_notes"].append(note)
        self.save()
        return note

    def __repr__(self):
        return f"Episode({self.slug!r}, status={self.status!r})"
