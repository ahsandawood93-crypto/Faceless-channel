"""Shared test fixtures. Tests never touch real API keys, paid APIs or the real episodes/ folder."""

import copy
import subprocess
from pathlib import Path

import pytest
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

MINSA = "Minsa, a cheerful 5-year-old girl with short curly black hair, a yellow dress and red sneakers."
MANA = "Mana, a small round blue baby elephant with big friendly eyes and a green bow."


@pytest.fixture
def channel(tmp_path):
    """The real channel.yaml with the TODOs filled in and reference images in a temp folder."""
    with open(ROOT / "channel.yaml", encoding="utf-8") as f:
        data = copy.deepcopy(yaml.safe_load(f))
    data["characters"]["minsa"]["description"] = MINSA
    data["characters"]["mana"]["description"] = MANA
    refs = tmp_path / "refs"
    refs.mkdir()
    for key, colour in (("minsa", "yellow"), ("mana", "blue")):
        path = refs / f"{key}.png"
        Image.new("RGB", (64, 64), colour).save(path)
        data["characters"][key]["reference_image"] = str(path)
    return data


@pytest.fixture
def channel_file(tmp_path, channel):
    path = tmp_path / "channel.yaml"
    path.write_text(yaml.safe_dump(channel), encoding="utf-8")
    return path


@pytest.fixture
def episodes_dir(tmp_path):
    return tmp_path / "episodes"  # created and wired in by no_real_env


@pytest.fixture(autouse=True)
def no_real_env(monkeypatch, tmp_path):
    """Point .env and episodes/ at temp paths and give every key a fake value."""
    import pipeline.config as config
    import pipeline.episode as episode_module

    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    (tmp_path / "episodes").mkdir()
    monkeypatch.setattr(episode_module, "EPISODES_DIR", tmp_path / "episodes")
    for key in ["ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "GOOGLE_CLOUD_PROJECT",
                "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        monkeypatch.setenv(key, f"test-{key.lower()}")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    for key in ["CLAUDE_MODEL", "ELEVENLABS_MODEL", "YOUTUBE_CLIENT_SECRET_FILE", "YOUTUBE_TOKEN_FILE",
                "GOOGLE_CLOUD_LOCATION", "GOOGLE_APPLICATION_CREDENTIALS"]:
        monkeypatch.delenv(key, raising=False)


# ---- media helpers (real ffmpeg, tiny files) ---------------------------------------------

def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *map(str, args)], check=True)


def make_tone(path, seconds, freq=440, volume=0.3):
    """A real MP3 'voice' of the given length."""
    ffmpeg("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}", "-af", f"volume={volume}",
           "-c:a", "libmp3lame", "-b:a", "64k", path)
    return path


def make_clip(path, seconds, with_audio=True, size="320x180", colour="0x8ecae6"):
    """A real MP4 clip (optionally with an audio track, like Veo returns)."""
    args = ["-f", "lavfi", "-i", f"color=c={colour}:s={size}:r=30:d={seconds}"]
    if with_audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=880:duration={seconds}", "-c:a", "aac"]
    ffmpeg(*args, "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-t", seconds, path)
    return path


# ---- episode helpers ------------------------------------------------------------------------

def make_scene(n, narration="This is the letter A. A is for apple!", seconds=4, characters=("minsa",),
               on_screen=None, veo_prompt="A sunny garden."):
    return {"n": n, "narration": narration, "on_screen": on_screen, "characters": list(characters),
            "veo_prompt": veo_prompt, "clip_seconds": seconds, "audio_file": None, "audio_seconds": None,
            "audio_placeholder": False, "clip_file": None, "clip_placeholder": False}


@pytest.fixture
def drafted(episodes_dir):
    """A drafted episode with two short scenes."""
    from pipeline.episode import Episode

    ep = Episode.create("Letter A is for Apple", episodes_dir)
    ep.data["title"] = "Letter A is for Apple!"
    ep.data["seo"] = {"title": "Letter A for Toddlers | Minsa Kids TV",
                      "description": "Learn the letter A with Minsa and Mana.", "tags": ["abc", "letter a"]}
    ep.data["scenes"] = [
        make_scene(1, "Hello, friends! Let's learn!", 4, ("minsa", "mana")),
        make_scene(2, "This is the letter A. A is for apple!", 4, ("minsa",), on_screen="A"),
    ]
    ep.set_status("drafted")
    return ep
