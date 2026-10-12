import pytest

import run
from pipeline.episode import Episode
from pipeline.util import StageError


@pytest.fixture
def topics(tmp_path, monkeypatch):
    path = tmp_path / "topics.txt"
    path.write_text("# comment\n\nLetter B is for Ball\nCounting to 3\n", encoding="utf-8")
    monkeypatch.setattr(run, "TOPICS_FILE", path)
    return path


@pytest.fixture
def fake_stages(monkeypatch, channel):
    """Replace every paid/slow stage with a recorder that just moves the status forward."""
    calls = []
    monkeypatch.setattr(run, "load_channel", lambda: channel)

    def stage(name, status=None, extra=None):
        def fn(episode, ch=None, **kwargs):
            calls.append((name, episode.slug, kwargs))
            if extra:
                extra(episode, kwargs)
            if status and not episode.reached(status):
                episode.set_status(status)
        return fn

    def write_scenes(ep, kw):
        ep.data["scenes"] = [{"n": 1, "audio_placeholder": False, "clip_placeholder": False}]

    def mark_final(ep, kw):
        ep.data["final"] = {"placeholder": False}

    monkeypatch.setattr(run.script_writer, "run_stage", stage("write", "drafted", write_scenes))
    monkeypatch.setattr(run.voiceover, "run_stage", stage("voice", "voiced"))
    monkeypatch.setattr(run.video, "run_stage", stage("video", "clips_ready"))
    monkeypatch.setattr(run.assemble, "run_stage", stage("assemble", "rendered", mark_final))
    monkeypatch.setattr(run.upload, "upload_private", stage("upload"))
    monkeypatch.setattr(run.approve, "send_for_approval", stage("send", "awaiting_approval"))
    return calls


def test_pop_topic_skips_comments_and_removes_the_line(topics):
    assert run.pop_topic() == "Letter B is for Ball"
    assert topics.read_text() == "# comment\n\nCounting to 3\n"
    assert run.pop_topic() == "Counting to 3"
    assert run.pop_topic() is None


def test_next_runs_everything_up_to_the_approval_gate(fake_stages, topics, episodes_dir):
    assert run.main(["next", "--yes"]) == 0
    assert [c[0] for c in fake_stages] == ["write", "voice", "video", "assemble", "upload", "send"]
    assert fake_stages[2][2]["yes"] is True
    ep = Episode.load("letter-b-is-for-ball", episodes_dir)
    assert ep.status == "awaiting_approval"           # stops at the gate: never schedules by itself
    assert "Letter B" not in topics.read_text()


def test_next_resumes_an_unfinished_episode_first(fake_stages, topics, drafted):
    drafted.set_status("voiced")
    run.main(["next", "--yes"])
    assert [c[0] for c in fake_stages] == ["video", "assemble", "upload", "send"]
    assert {c[1] for c in fake_stages} == {drafted.slug}
    assert "Letter B" in topics.read_text()          # topic queue untouched


def test_next_with_empty_queue(fake_stages, tmp_path, monkeypatch, episodes_dir):
    monkeypatch.setattr(run, "TOPICS_FILE", tmp_path / "missing.txt")
    assert run.main(["next"]) == 0 and fake_stages == []


def test_all_on_a_finished_episode_does_nothing(fake_stages, drafted):
    drafted.set_status("scheduled")
    run.main(["all", drafted.slug])
    assert fake_stages == []


def test_dry_run_flags_reach_the_stages_and_skip_upload(fake_stages, topics, monkeypatch):
    def placeholder_final(episode, ch=None, **kwargs):
        fake_stages.append(("assemble", episode.slug, kwargs))
        episode.data["final"] = {"placeholder": True, "video": "final/episode.mp4"}
        episode.set_status("rendered")

    monkeypatch.setattr(run.assemble, "run_stage", placeholder_final)
    run.main(["all", "Shapes", "--no-voice", "--no-video"])
    names = [c[0] for c in fake_stages]
    assert names == ["write", "voice", "video", "assemble"]
    assert fake_stages[1][2]["placeholder"] is True and fake_stages[2][2]["placeholder"] is True


def test_real_run_after_dry_run_replaces_placeholders(fake_stages, drafted):
    drafted.data["scenes"] = [{"n": 1, "audio_placeholder": True, "clip_placeholder": True}]
    drafted.data["final"] = {"placeholder": True}
    for status in ("voiced", "clips_ready", "rendered"):
        drafted.set_status(status)
    run.main(["all", drafted.slug, "--yes"])
    assert [c[0] for c in fake_stages] == ["voice", "video", "assemble", "upload", "send"]


def test_failure_exit_code_and_telegram_alert(fake_stages, topics, monkeypatch, capsys):
    def boom(episode, ch=None, **kwargs):
        raise StageError("Clips failed for scene(s) [3]. Rerun: python run.py video x")

    monkeypatch.setattr(run.video, "run_stage", boom)
    alerts = []
    monkeypatch.setattr(run, "notify_failure", lambda ep, e: alerts.append(str(e)))
    assert run.main(["next", "--yes"]) == 1
    assert "scene(s) [3]" in capsys.readouterr().err and alerts


def test_approve_from_terminal(fake_stages, drafted, monkeypatch, capsys):
    run.main(["approve", drafted.slug, "--reject", "Too fast"])
    ep = Episode.load(drafted.slug)
    assert ep.status == "rejected" and ep.data["rejection_reason"] == "Too fast"


def test_list(fake_stages, drafted, capsys):
    run.main(["list"])
    assert drafted.slug in capsys.readouterr().out
