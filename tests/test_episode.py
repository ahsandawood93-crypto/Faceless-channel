import json

import pytest
import yaml

import run
from pipeline import episode as episode_module
from pipeline.config import load_channel
from pipeline.episode import Episode, slugify


@pytest.mark.parametrize("topic, slug", [
    ("Letter A is for Apple", "letter-a-is-for-apple"),
    ("  Red, Yellow & Blue!  ", "red-yellow-blue"),
    ("Café ñ colours", "cafe-n-colours"),
    ("!!!", "episode"),
])
def test_slugify(topic, slug):
    assert slugify(topic) == slug


def test_slug_is_capped():
    assert len(slugify("word " * 40)) <= 50


def test_create_writes_episode_json(episodes_dir):
    ep = Episode.create("Counting to 5", episodes_dir)
    data = json.loads((episodes_dir / "counting-to-5" / "episode.json").read_text())
    assert data["topic"] == "Counting to 5"
    assert data["status"] == "new"
    assert data["scenes"] == [] and data["review_notes"] == []
    assert data["youtube"] == {"video_id": None, "publish_at": None}
    assert ep.slug == "counting-to-5"


def test_duplicate_topics_get_numbered(episodes_dir):
    assert Episode.create("Shapes", episodes_dir).slug == "shapes"
    assert Episode.create("Shapes", episodes_dir).slug == "shapes-2"
    assert Episode.create("Shapes", episodes_dir).slug == "shapes-3"


def test_empty_topic_rejected(episodes_dir):
    with pytest.raises(ValueError):
        Episode.create("   ", episodes_dir)


def test_save_load_roundtrip(episodes_dir):
    ep = Episode.create("Shapes", episodes_dir)
    ep.data["title"] = "Shapes with Minsa"
    ep.save()
    assert Episode.load("shapes", episodes_dir).data["title"] == "Shapes with Minsa"
    assert Episode.load(ep.dir).slug == "shapes"
    assert Episode.load(ep.file).slug == "shapes"
    assert not list(ep.dir.glob("*.tmp"))


def test_load_missing(episodes_dir):
    with pytest.raises(FileNotFoundError):
        Episode.load("nope", episodes_dir)


def test_status_history_and_order(episodes_dir):
    ep = Episode.create("Shapes", episodes_dir)
    ep.set_status("drafted")
    ep.set_status("voiced")
    assert ep.reached("drafted") and ep.reached("voiced")
    assert not ep.reached("clips_ready")
    assert [h["status"] for h in Episode.load(ep.dir).data["history"]] == ["new", "drafted", "voiced"]


def test_rejected_counts_as_past_rendering(episodes_dir):
    ep = Episode.create("Shapes", episodes_dir)
    ep.set_status("rejected")
    assert ep.reached("rendered") and ep.reached("rejected")
    assert not ep.reached("scheduled")


def test_unknown_status(episodes_dir):
    with pytest.raises(ValueError):
        Episode.create("Shapes", episodes_dir).set_status("published")


def test_review_note_is_saved(episodes_dir):
    ep = Episode.create("Shapes", episodes_dir)
    ep.add_review_note("Voice runs 1.2 s past clip", stage="voice", scene=3)
    note = Episode.load(ep.dir).data["review_notes"][0]
    assert note["message"] == "Voice runs 1.2 s past clip"
    assert note["stage"] == "voice" and note["scene"] == 3 and note["at"]


def test_path_creates_parent_folders(episodes_dir):
    ep = Episode.create("Shapes", episodes_dir)
    p = ep.path("audio", "scene_01.mp3")
    assert p.parent.is_dir() and p == ep.dir / "audio" / "scene_01.mp3"


def test_cli_init(monkeypatch, episodes_dir, capsys):
    monkeypatch.setattr(run, "load_channel", lambda: None)
    monkeypatch.setattr(episode_module, "EPISODES_DIR", episodes_dir)
    assert run.main(["init", "Letter B"]) == 0
    assert (episodes_dir / "letter-b" / "episode.json").exists()
    assert "letter-b" in capsys.readouterr().out


def test_cli_init_stops_on_todo(monkeypatch, tmp_path, channel, capsys):
    channel["characters"]["minsa"]["description"] = "TODO"
    todo_file = tmp_path / "todo.yaml"
    todo_file.write_text(yaml.safe_dump(channel))
    monkeypatch.setattr(run, "load_channel", lambda: load_channel(todo_file))
    assert run.main(["init", "Letter B"]) == 2
    assert "still TODO" in capsys.readouterr().err
