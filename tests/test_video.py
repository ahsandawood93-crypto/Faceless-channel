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
    """Like Vertex AI: the MP4 comes back inline as video_bytes."""

    def __init__(self, source):
        self.source, self.video_bytes, self.uri = source, b"inline", None

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
    assert video.estimate_cost(channel, 23) == pytest.approx(23 * 8 * 0.10)


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
    assert "2 clip(s) × 8 s × $0.10/s" in capsys.readouterr().out
    for scene in voiced.data["scenes"]:
        clip = voiced.dir / scene["clip_file"]
        assert clip.exists() and not has_audio(clip)

    first, second = client.requests
    assert first["model"] == channel["veo"]["model"]
    cfg = first["config"]
    assert cfg.aspect_ratio == "16:9" and cfg.resolution == "1080p" and cfg.duration_seconds == 8
    assert cfg.generate_audio is False and cfg.person_generation is None
    assert first["model"] == "veo-3.1-fast-generate-001"
    assert len(cfg.reference_images) == 2 and len(second["config"].reference_images) == 1
    ref = cfg.reference_images[0]
    assert ref.reference_type.value.lower() == "asset" and ref.image.mime_type == "image/png"
    assert first["prompt"].startswith(voiced.data["scenes"][0]["veo_prompt"])
    assert "No dialogue" in first["prompt"]
    assert client.downloads == 0 and client.polled == 4  # Vertex returns bytes inline


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


def test_vertex_client(monkeypatch):
    from google import genai

    import google.auth

    made = {}
    monkeypatch.setattr(google.auth, "default", lambda scopes=None: ("creds", "proj"))
    monkeypatch.setattr(genai, "Client", lambda **kw: made.update(kw) or "client")
    assert video.make_client() == "client"
    assert made == {"vertexai": True, "project": "test-google_cloud_project", "location": "us-central1"}
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west4")
    video.make_client()
    assert made["location"] == "europe-west4"


def test_vertex_needs_a_project(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT")
    with pytest.raises(ConfigError, match="GOOGLE_CLOUD_PROJECT"):
        video.make_client()


def test_person_generation_setting_is_passed(channel, voiced, veo_clip):
    channel["veo"]["person_generation"] = "allow_all"
    client = FakeGenai(veo_clip)
    video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert str(client.requests[0]["config"].person_generation).lower().endswith("allow_all")


def test_child_filter_gives_a_hint(channel, voiced, veo_clip, monkeypatch):
    client = FakeGenai(veo_clip, empty_for=[voiced.data["scenes"][0]["veo_prompt"]])
    original = client.get

    def get(operation):
        op = original(operation)
        if op.done and op.response.rai_media_filtered_reasons:
            op.response.rai_media_filtered_reasons = ["Child safety: minors cannot be generated"]
        return op

    client.operations.get = get
    voiced.data["scenes"][1]["veo_prompt"] = "A kitchen."
    with pytest.raises(StageError):
        video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert "Veo and child characters" in voiced.data["review_notes"][-1]["message"]


def test_missing_google_login_is_a_clear_error(monkeypatch):
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    def no_login(scopes=None):
        raise DefaultCredentialsError("none")

    monkeypatch.setattr(google.auth, "default", no_login)
    with pytest.raises(ConfigError, match="gcloud auth application-default login"):
        video.make_client()


def test_permission_error_stops_after_first_scene(channel, voiced, veo_clip):
    client = FakeGenai(veo_clip, fail=[ApiError(403, "Vertex AI API has not been used in project")])
    with pytest.raises(StageError, match="Vertex AI refused"):
        video.run_stage(voiced, channel, client=client, yes=True, sleep=NO_SLEEP)
    assert len(client.requests) == 1
