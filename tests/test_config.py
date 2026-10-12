import pytest
import yaml

from pipeline import config
from pipeline.config import ConfigError, check_channel, load_channel, require_env


def test_filled_channel_loads(channel_file):
    channel = load_channel(channel_file)
    assert channel["channel"]["name"] == "Minsa Kids TV"
    assert channel["narrator"]["words_per_minute"] == 120


def test_real_channel_yaml_has_no_problems_except_todos():
    with open(config.CHANNEL_FILE, encoding="utf-8") as f:
        problems = check_channel(yaml.safe_load(f))
    assert [p for p in problems if not p.endswith("is still TODO")] == []


def test_todo_blocks_loading(tmp_path, channel):
    channel["characters"]["mana"]["description"] = "TODO"
    path = tmp_path / "channel.yaml"
    path.write_text(yaml.safe_dump(channel))
    with pytest.raises(ConfigError, match="characters.mana.description is still TODO"):
        load_channel(path)


def test_reports_every_problem_at_once(channel):
    del channel["visual_style"]
    channel["narrator"]["words_per_minute"] = "fast"
    channel["schedule"]["days"] = ["Monday"]
    channel["schedule"]["time"] = "4pm"
    problems = check_channel(channel)
    assert "visual_style is missing" in problems
    assert "narrator.words_per_minute has the wrong type (str)" in problems
    assert any(p.startswith("schedule.days must use") for p in problems)
    assert "schedule.time must be HH:MM, got '4pm'" in problems


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_channel(tmp_path / "nope.yaml")


def test_require_env_names_missing_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        require_env("ANTHROPIC_API_KEY", "GEMINI_API_KEY")
    assert require_env("ANTHROPIC_API_KEY") == {"ANTHROPIC_API_KEY": "sk-test"}


def test_env_file_is_read(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("CLAUDE_MODEL=from-file\n")
    assert config.env("CLAUDE_MODEL") == "from-file"
    assert config.env("ELEVENLABS_MODEL", "default-model") == "default-model"
