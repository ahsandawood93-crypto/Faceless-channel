"""Shared test fixtures. Tests never touch real API keys or the real episodes/ folder."""

import copy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def channel():
    """The real channel.yaml with the TODO placeholders filled in."""
    with open(ROOT / "channel.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data = copy.deepcopy(data)
    data["characters"]["minsa"]["description"] = (
        "Minsa, a cheerful 5-year-old girl with short curly black hair, "
        "a yellow dress and red sneakers."
    )
    data["characters"]["mana"]["description"] = (
        "Mana, a small round blue baby elephant with big friendly eyes and a green bow."
    )
    return data


@pytest.fixture
def channel_file(tmp_path, channel):
    path = tmp_path / "channel.yaml"
    path.write_text(yaml.safe_dump(channel), encoding="utf-8")
    return path


@pytest.fixture
def episodes_dir(tmp_path):
    folder = tmp_path / "episodes"
    folder.mkdir()
    return folder


@pytest.fixture(autouse=True)
def no_real_env(monkeypatch, tmp_path):
    """Point .env at an empty temp file and clear any real keys from the shell."""
    import pipeline.config as config

    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    for key in [
        "ANTHROPIC_API_KEY", "CLAUDE_MODEL", "ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID",
        "ELEVENLABS_MODEL", "GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    ]:
        monkeypatch.delenv(key, raising=False)
