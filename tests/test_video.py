import shutil
from types import SimpleNamespace

import pytest

from pipeline import video
from pipeline.config import ConfigError
from pipeline.util import StageError, has_audio
from tests.conftest import make_clip

NO_SLEEP = lambda s: None  # noqa: E731


class ApiError(Exception):
    def __init__(self, code, message="error"):
        super().__init__(f"{code} {message}")
        self.code = code


class FakeVideo:
    def __init__(self, source):
        self.source = source

    def save(self, path):
        shutil.copy(self.source, path)


class FakeGenai:
    """Mimics client.models.generate_videos + operations.get + files.download."""

    def __init__(self, clip, fail=None, empty_for=(), polls=2):
        self.clip, self.fail, self.empty_for, self.polls = clip, list(fail or []), set(empty_for), polls
        self.requests, self.polled, self.downloads = [], 0, 0
        self.models = SimpleNamespace(generate_videos=self.generate_videos)
        self.operations = SimpleNamespace(get=self.get)
        self.files = SimpleNamespace(download=self.download)

    def generate_videos(self, model, prompt, config, image=None):
        self.requests.append(dict(model=model, prompt=prompt, config=config, image=image))
        if self.fail:
            raise self.fail.pop(0)
        empty = any(text in prompt for text in self.empty_for)
        return SimpleNamespace(done=False, error=None, response=None, _left=self.polls, _empty=empty)

    def get(self, operation):
        self.polled += 1
        operation._left -= 1
        if operation._left <= 0:
            operation.done = True
            videos = [] if operation._empty else [SimpleNamespace(video=FakeVideo(self.clip))]
            operation.response = SimpleNamespace(generated_videos=videos,
                                                 rai_media_filtered_reasons=["blocked"] if operation._empty else None)
        return operation

    def download(self, file):
        self.downloads += 1


@pytest.fixture
def voiced(drafted, channel):
    from pipeline import voiceover

    voiceover.run_stage(drafted, channel, placeholder=True)
    return drafted


@pytest.fixture
def veo_clip(tmp_path):
    return make_clip(tmp_path / "veo.mp4", 8, with_audio=True)


def test_cost_estimate(channel):
    assert video.estimate_cost(channel, 23) == pytest.approx(23 * 8 * 0.12)


def test_declining_the_cost_prompt_spends_nothing(channel, voiced, veo_clip, monkeypatch):
    monkeypatch.setattr(video, "confirm", lambda q: False)
    client = FakeGenai(veo_clip)
    with pytest.raises(StageError, match="Cancelled"):
        video.run_stage(voiced, channel, client=client, sleep=NO_SLEEP)
    assert client.requests == []


def test_generates_clips_with_references_and_strips_audio(channel, voiced, veo_clip, capsys):
    client = FakeGenai(veo_clip)
    video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert voiced.status == "clips_ready"
    assert "2 clip(s) × 8 s × $0.12/s" in capsys.readouterr().out
    for scene in voiced.data["scenes"]:
        clip = voiced.dir / scene["clip_file"]
        assert clip.exists() and not has_audio(clip)

    first, second = client.requests
    assert first["model"] == channel["veo"]["model"]
    cfg = first["config"]
    assert cfg.aspect_ratio == "16:9" and cfg.resolution == "1080p" and cfg.duration_seconds == 8
    assert len(cfg.reference_images) == 2 and len(second["config"].reference_images) == 1
    ref = cfg.reference_images[0]
    assert ref.reference_type.value.lower() == "asset" and ref.image.mime_type == "image/png"
    assert first["prompt"].startswith(voiced.data["scenes"][0]["veo_prompt"])
    assert "No dialogue" in first["prompt"]
    assert client.downloads == 2 and client.polled == 4


def test_existing_clips_are_skipped(channel, voiced, veo_clip):
    video.run_stage(voiced, channel, client=FakeGenai(veo_clip), yes=True, sleep=NO_SLEEP)
    again = FakeGenai(veo_clip)
    video.run_stage(voiced, channel, client=again, yes=True, sleep=NO_SLEEP)
    assert again.requests == []


def test_missing_reference_image_stops_before_spending(channel, voiced, veo_clip):
    channel["characters"]["mana"]["reference_image"] = "/nope/mana.png"
    client = FakeGenai(veo_clip)
    with pytest.raises(ConfigError, match="Missing reference image for mana"):
        video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert client.requests == []


def test_transient_errors_retried(channel, voiced, veo_clip):
    client = FakeGenai(veo_clip, fail=[ApiError(503), ApiError(429)])
    video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert voiced.status == "clips_ready" and len(client.requests) == 4


def test_blocked_clip_is_logged_others_continue(channel, voiced, veo_clip):
    blocked = voiced.data["scenes"][0]["veo_prompt"] = "A garden where scene one happens."
    voiced.data["scenes"][1]["veo_prompt"] = "A kitchen."
    client = FakeGenai(veo_clip, empty_for=[blocked])
    with pytest.raises(StageError, match=r"scene\(s\) \[1\].*python run.py video"):
        video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert voiced.status == "voiced"
    assert (voiced.dir / "clips/scene_02.mp4").exists()
    note = voiced.data["review_notes"][-1]
    assert note["stage"] == "video" and note["scene"] == 1 and "no video" in note["message"]


def test_reference_images_rejected_falls_back_to_start_image(channel, voiced, veo_clip):
    client = FakeGenai(veo_clip, fail=[ApiError(400, "referenceImages is not supported for this model")])
    video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    fallback = client.requests[1]
    assert fallback["config"].reference_images is None and fallback["image"] is not None
    assert any("starting frame" in n["message"] for n in voiced.data["review_notes"])


def test_cost_cap(channel, voiced, veo_clip):
    channel["veo"]["max_usd_per_run"] = 1
    with pytest.raises(StageError, match="max_usd_per_run"):
        video.run_stage(voiced, channel, client=FakeGenai(veo_clip), yes=True, sleep=NO_SLEEP)


def test_placeholders_are_free_and_replaced_later(channel, voiced, veo_clip):
    video.run_stage(voiced, channel, placeholder=True)
    assert voiced.status == "clips_ready" and all(s["clip_placeholder"] for s in voiced.data["scenes"])
    client = FakeGenai(veo_clip)
    video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert len(client.requests) == 2
    assert not any(s["clip_placeholder"] for s in voiced.data["scenes"])


def test_needs_voice_first(channel, drafted):
    with pytest.raises(StageError, match="python run.py voice"):
        video.run_stage(drafted, channel, yes=True)
