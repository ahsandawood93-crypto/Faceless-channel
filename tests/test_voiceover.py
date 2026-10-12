from types import SimpleNamespace

import pytest

from pipeline import voiceover
from pipeline.util import StageError, duration
from tests.conftest import make_tone

NO_SLEEP = lambda s: None  # noqa: E731


class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class FakeEleven:
    """Returns real MP3 bytes; seconds_by_text controls each clip's length."""

    def __init__(self, tmp_path, seconds=2.0, seconds_by_text=None, fail=None):
        self.tmp, self.seconds, self.by_text = tmp_path, seconds, seconds_by_text or {}
        self.fail = list(fail or [])
        self.calls = []
        self.text_to_speech = SimpleNamespace(convert=self.convert)

    def convert(self, voice_id, text, model_id, output_format):
        self.calls.append(dict(voice_id=voice_id, text=text, model_id=model_id, output_format=output_format))
        if self.fail:
            raise self.fail.pop(0)
        path = make_tone(self.tmp / f"tts_{len(self.calls)}.mp3", self.by_text.get(text, self.seconds))
        data = path.read_bytes()
        return iter([data[:100], data[100:]])  # the SDK yields chunks


def test_generates_one_mp3_per_scene(channel, drafted, tmp_path):
    client = FakeEleven(tmp_path)
    voiceover.run_stage(drafted, channel, client=client, sleep=NO_SLEEP)
    assert drafted.status == "voiced"
    for scene in drafted.data["scenes"]:
        assert (drafted.dir / scene["audio_file"]).exists()
        assert scene["audio_seconds"] == pytest.approx(2.0, abs=0.15)
    assert client.calls[0]["voice_id"] == "test-elevenlabs_voice_id"
    assert client.calls[0]["model_id"] == voiceover.DEFAULT_MODEL
    full = drafted.dir / "full_narration.mp3"
    assert duration(full) == pytest.approx(4.8, abs=0.3)  # 2 + 2 + two 0.4 s pauses


def test_existing_files_are_skipped(channel, drafted, tmp_path):
    voiceover.run_stage(drafted, channel, client=FakeEleven(tmp_path), sleep=NO_SLEEP)
    again = FakeEleven(tmp_path)
    voiceover.run_stage(drafted, channel, client=again, sleep=NO_SLEEP)
    assert again.calls == []


def test_voice_longer_than_clip_is_flagged(channel, drafted, tmp_path):
    long_text = drafted.data["scenes"][1]["narration"]
    voiceover.run_stage(drafted, channel, client=FakeEleven(tmp_path, seconds_by_text={long_text: 5.5}),
                        sleep=NO_SLEEP)
    notes = [n for n in drafted.data["review_notes"] if n["stage"] == "voice"]
    assert len(notes) == 1 and notes[0]["scene"] == 2
    assert "longer than the 4 s clip" in notes[0]["message"]


def test_transient_errors_are_retried(channel, drafted, tmp_path):
    client = FakeEleven(tmp_path, fail=[HttpError(503), HttpError(429)])
    voiceover.run_stage(drafted, channel, client=client, sleep=NO_SLEEP)
    assert drafted.status == "voiced" and len(client.calls) == 4


def test_failure_is_logged_and_names_the_scene(channel, drafted, tmp_path):
    client = FakeEleven(tmp_path, fail=[HttpError(401)])
    with pytest.raises(StageError, match=r"scene\(s\) \[1\].*python run.py voice letter-a-is-for-apple"):
        voiceover.run_stage(drafted, channel, client=client, sleep=NO_SLEEP)
    assert drafted.status == "drafted"
    assert (drafted.dir / "audio/scene_02.mp3").exists()  # the other scene still got done
    note = drafted.data["review_notes"][-1]
    assert note["scene"] == 1 and "Voiceover failed" in note["message"]


def test_placeholders_then_real_run_replaces_them(channel, drafted, tmp_path):
    voiceover.run_stage(drafted, channel, placeholder=True)
    assert all(s["audio_placeholder"] for s in drafted.data["scenes"])
    assert drafted.status == "voiced"
    client = FakeEleven(tmp_path)
    voiceover.run_stage(drafted, channel, client=client, sleep=NO_SLEEP)
    assert len(client.calls) == 2
    assert not any(s["audio_placeholder"] for s in drafted.data["scenes"])


def test_needs_a_script_first(channel, episodes_dir):
    from pipeline.episode import Episode

    with pytest.raises(StageError, match="python run.py write"):
        voiceover.run_stage(Episode.create("x", episodes_dir), channel)
