"""Load and check channel.yaml (the channel bible) and .env (secrets)."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CHANNEL_FILE = ROOT / "channel.yaml"
ENV_FILE = ROOT / ".env"

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# (dotted path, expected type) for every field the pipeline relies on.
REQUIRED_FIELDS = [
    ("channel.name", str),
    ("channel.language", str),
    ("channel.audience", str),
    ("channel.target_minutes", (int, float)),
    ("narrator.style", str),
    ("narrator.words_per_minute", int),
    ("characters", dict),
    ("visual_style", str),
    ("content_rules", list),
    ("intro_line", str),
    ("outro_line", str),
    ("schedule.timezone", str),
    ("schedule.days", list),
    ("schedule.time", str),
    ("veo.model", str),
    ("veo.resolution", str),
    ("veo.aspect_ratio", str),
    ("veo.generated_seconds", int),
    ("veo.usd_per_second", (int, float)),
]


class ConfigError(Exception):
    """channel.yaml or .env is missing something. The message says what."""


def _get(data, dotted):
    for key in dotted.split("."):
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def _is_todo(value):
    return isinstance(value, str) and value.strip().upper().startswith("TODO")


def check_channel(channel):
    """Return a list of human-readable problems (empty list = all good)."""
    problems = []
    for path, expected in REQUIRED_FIELDS:
        value = _get(channel, path)
        if value is None:
            problems.append(f"{path} is missing")
        elif isinstance(value, bool) or not isinstance(value, expected):
            problems.append(f"{path} has the wrong type ({type(value).__name__})")
        elif _is_todo(value):
            problems.append(f"{path} is still TODO")

    characters = channel.get("characters") if isinstance(channel, dict) else None
    if isinstance(characters, dict):
        if not characters:
            problems.append("characters is empty")
        for key, char in characters.items():
            for field in ("name", "description", "reference_image"):
                value = char.get(field) if isinstance(char, dict) else None
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"characters.{key}.{field} is missing")
                elif _is_todo(value):
                    problems.append(f"characters.{key}.{field} is still TODO")

    days = _get(channel, "schedule.days")
    if isinstance(days, list):
        bad = [d for d in days if d not in WEEKDAYS]
        if bad or not days:
            problems.append(f"schedule.days must use {WEEKDAYS}, got {days}")
    time = _get(channel, "schedule.time")
    if isinstance(time, str) and not _valid_time(time):
        problems.append(f"schedule.time must be HH:MM, got {time!r}")
    return problems


def _valid_time(text):
    parts = text.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return False
    return 0 <= int(parts[0]) < 24 and 0 <= int(parts[1]) < 60


def load_channel(path=None):
    """Read channel.yaml and raise ConfigError listing every problem found."""
    path = Path(path or CHANNEL_FILE)
    if not path.exists():
        raise ConfigError(f"{path} not found")
    with open(path, encoding="utf-8") as f:
        channel = yaml.safe_load(f) or {}
    problems = check_channel(channel)
    if problems:
        lines = "\n  - ".join(problems)
        raise ConfigError(f"Please fix {path.name}:\n  - {lines}")
    return channel


def load_env(path=None):
    """Load .env into os.environ. Real environment variables win."""
    load_dotenv(path or ENV_FILE, override=False)


def require_env(*names):
    """Return {name: value} for the given keys, or raise naming the missing ones."""
    load_env()
    missing = [n for n in names if not os.environ.get(n, "").strip()]
    if missing:
        raise ConfigError(
            "Missing in .env: " + ", ".join(missing)
            + "\nCopy .env.example to .env and fill them in (see README.md, 'API keys')."
        )
    return {n: os.environ[n].strip() for n in names}


def env(name, default=None):
    """Optional setting from .env, e.g. env('CLAUDE_MODEL', 'claude-sonnet-5-5')."""
    load_env()
    value = os.environ.get(name, "").strip()
    return value or default
