"""Small shared helpers: ffmpeg/ffprobe, retries, console output."""

import json
import random
import shutil
import subprocess
import sys
import time


class StageError(Exception):
    """A stage could not finish. The message says what failed and how to rerun."""


# ---- console -----------------------------------------------------------------

def step(text):
    print(f"\n== {text}", flush=True)


def info(text):
    print(f"   {text}", flush=True)


def warn(text):
    print(f"   ! {text}", flush=True)


def confirm(question):
    """Ask y/N. Refuses (returns False) when nobody is at the keyboard."""
    if not sys.stdin or not sys.stdin.isatty():
        warn("No terminal to ask for confirmation; pass --yes to run unattended.")
        return False
    return input(f"   {question} [y/N] ").strip().lower() in ("y", "yes")


# ---- ffmpeg ------------------------------------------------------------------

def require_ffmpeg():
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise StageError(f"{tool} not found on PATH. Install ffmpeg (see README, Setup).")


def run(cmd):
    """Run a command; on failure raise StageError with the tail of its output."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-15:])
        raise StageError(f"{cmd[0]} failed:\n{tail}")
    return result.stdout


def ffmpeg(*args):
    return run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)])


def probe(path):
    out = run(["ffprobe", "-v", "error", "-print_format", "json",
               "-show_format", "-show_streams", str(path)])
    return json.loads(out)


def duration(path):
    """Media duration in seconds, measured by ffprobe."""
    return float(probe(path)["format"]["duration"])


def has_audio(path):
    return any(s.get("codec_type") == "audio" for s in probe(path)["streams"])


# ---- retries -----------------------------------------------------------------

def with_retries(fn, is_transient, attempts=4, base_delay=5.0, sleep=time.sleep, label=""):
    """Call fn(); retry transient errors with exponential backoff and jitter."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - we re-raise anything not transient
            if attempt == attempts or not is_transient(e):
                raise
            delay = base_delay * 2 ** (attempt - 1) + random.uniform(0, 1)
            warn(f"{label}temporary error ({e}); retry {attempt}/{attempts - 1} in {delay:.0f}s")
            sleep(delay)


def status_code(error):
    """Best-effort HTTP status from SDK exceptions (anthropic, elevenlabs, genai, googleapiclient)."""
    for attr in ("status_code", "code", "status"):
        value = getattr(error, attr, None)
        if isinstance(value, int):
            return value
    resp = getattr(error, "resp", None)  # googleapiclient.errors.HttpError
    if resp is not None and getattr(resp, "status", None):
        return int(resp.status)
    return None


def is_transient_http(error):
    code = status_code(error)
    if code is not None:
        return code in (408, 409, 429) or code >= 500
    name = type(error).__name__.lower()
    return any(word in name for word in ("timeout", "connection", "temporar"))
