import random

import pytest
from PIL import Image

from pipeline import assemble
from pipeline.util import StageError, duration, probe
from tests.conftest import make_clip, make_tone


@pytest.fixture
def assets(tmp_path, monkeypatch):
    folder = tmp_path / "assets"
    (folder / "fonts").mkdir(parents=True)
    (folder / "music").mkdir()
    monkeypatch.setattr(assemble, "ASSETS", folder)
    monkeypatch.setattr(assemble, "W", 320)    # small frames keep the tests fast
    monkeypatch.setattr(assemble, "H", 180)
    monkeypatch.setattr(assemble, "VIDEO_ARGS", ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                                                 "-pix_fmt", "yuv420p", "-r", "30"])
    return folder


@pytest.fixture
def ready(drafted):
    """Clips are 4 s (Veo-like 8 s trimmed to clip_seconds); scene 2's voice runs long (5.5 s)."""
    for scene, voice in zip(drafted.data["scenes"], (2.5, 5.5)):
        n = scene["n"]
        scene["audio_file"] = f"audio/scene_{n:02d}.mp3"
        scene["clip_file"] = f"clips/scene_{n:02d}.mp4"
        make_tone(drafted.path(scene["audio_file"]), voice, freq=300 + 100 * n)
        make_clip(drafted.path(scene["clip_file"]), 8, with_audio=False, size="640x360",
                  colour="0xffb703" if n == 1 else "0x90be6d")
    drafted.set_status("voiced")
    drafted.set_status("clips_ready")
    return drafted


def stream(path, kind):
    return next(s for s in probe(path)["streams"] if s["codec_type"] == kind)


def test_caption_chunks_follow_the_audio_length():
    chunks = assemble.caption_chunks("Hello, friends! This is the letter A, for apple.", 6.0)
    assert [c[2] for c in chunks] == ["Hello, friends!", "This is the letter A, for apple."]
    assert chunks[0][0] == 0 and chunks[-1][1] == pytest.approx(6.0, abs=0.01)
    assert chunks[0][1] == pytest.approx(6.0 * 2 / 9, abs=0.01)


def test_long_sentences_are_split():
    chunks = assemble.caption_chunks(" ".join(["word"] * 20), 10)
    assert all(len(c[2].split()) <= assemble.CAPTION_MAX_WORDS + 2 for c in chunks) and len(chunks) == 3


def test_srt_format():
    assert assemble.srt_time(3723.456) == "01:02:03,456"
    srt = assemble.build_srt([(0, 1.5, "Hello"), (1.5, 3, "Bye")])
    assert srt == "1\n00:00:00,000 --> 00:00:01,500\nHello\n\n2\n00:00:01,500 --> 00:00:03,000\nBye\n"


def test_full_assembly(channel, ready, assets):
    make_tone(assets / "music" / "song.mp3", 3, freq=660, volume=0.5)  # shorter than the video: must loop
    assemble.run_stage(ready, channel, rng=random.Random(1))
    final = ready.data["final"]
    video = ready.dir / final["video"]

    assert ready.status == "rendered"
    v, a = stream(video, "video"), stream(video, "audio")
    assert v["codec_name"] == "h264" and (v["width"], v["height"]) == (320, 180)
    assert a["codec_name"] == "aac" and a["sample_rate"] == "48000"
    # scene 1: 4 s clip; scene 2: 5.5 s voice + 0.3 s pad -> clip frozen to 5.8 s
    assert duration(video) == pytest.approx(4 + 5.8, abs=0.15)
    assert final["lufs"] == pytest.approx(-14, abs=1.0)
    assert final["music"] == "song.mp3" and final["placeholder"] is False

    srt = (ready.dir / final["srt"]).read_text()
    assert "Hello, friends!" in srt and "This is the letter A." in srt
    assert "00:00:04,000 --> " in srt  # scene 2 captions start where scene 2 starts

    thumb = ready.dir / final["thumbnail"]
    assert Image.open(thumb).size == (1280, 720) and thumb.stat().st_size < 2 * 1024 * 1024
    assert not (ready.dir / "final" / "work").exists()


def test_intro_shifts_captions_and_music_is_optional(channel, ready, assets):
    make_clip(assets / "intro.mp4", 2, with_audio=False, size="640x360")
    assemble.run_stage(ready, channel)
    final = ready.data["final"]
    assert duration(ready.dir / final["video"]) == pytest.approx(2 + 4 + 5.8, abs=0.2)
    assert (ready.dir / final["srt"]).read_text().startswith("1\n00:00:02,000 --> ")
    assert final["music"] is None
    assert any("No background music" in n["message"] for n in ready.data["review_notes"])


def test_overlay_png_is_drawn(tmp_path, assets):
    path = tmp_path / "overlay.png"
    assemble.overlay_png("A", path)
    img = Image.open(path)
    assert img.size == (320, 180) and img.getbbox() is not None  # something drawn, rest transparent
    assert img.getpixel((5, 175))[3] == 0


def test_missing_clip_names_the_scene(channel, ready, assets):
    (ready.dir / "clips/scene_02.mp4").unlink()
    with pytest.raises(StageError, match="Scene 2: clip_file missing.*python run.py video"):
        assemble.run_stage(ready, channel)


def test_needs_clips_first(channel, drafted, assets):
    with pytest.raises(StageError, match="python run.py video"):
        assemble.run_stage(drafted, channel)
