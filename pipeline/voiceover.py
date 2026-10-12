"""Stage 2: narration MP3 per scene with ElevenLabs, plus full_narration.mp3.

Existing MP3s are skipped, so reruns only pay for what is missing.
--no-voice writes silent placeholders of the estimated length instead
(free dry run); a later real run replaces them.
"""

from pipeline.config import env, require_env
from pipeline.util import (StageError, duration, ffmpeg, info, is_transient_http, require_ffmpeg,
                           step, warn, with_retries)

DEFAULT_MODEL = "eleven_multilingual_v2"   # ElevenLabs' long-form narration model
OUTPUT_FORMAT = "mp3_44100_128"


def audio_name(scene):
    return f"audio/scene_{scene['n']:02d}.mp3"


def make_client():
    from elevenlabs.client import ElevenLabs

    key = require_env("ELEVENLABS_API_KEY")["ELEVENLABS_API_KEY"]
    return ElevenLabs(api_key=key)


def synthesize(client, text, voice_id, model_id):
    chunks = client.text_to_speech.convert(
        voice_id=voice_id, text=text, model_id=model_id, output_format=OUTPUT_FORMAT,
    )
    return chunks if isinstance(chunks, bytes) else b"".join(chunks)


def write_placeholder(path, seconds):
    ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{seconds:.2f}",
           "-c:a", "libmp3lame", "-b:a", "64k", path)


def estimated_seconds(scene, channel):
    from pipeline.script_writer import count_words

    words = count_words(scene["narration"])
    return max(1.0, words * 60 / channel["narrator"]["words_per_minute"])


def build_full_narration(episode, gap=0.4):
    """Concatenate all scene MP3s with a short pause between them."""
    files = [episode.dir / s["audio_file"] for s in episode.data["scenes"]]
    args, parts = [], []
    for i, f in enumerate(files):
        args += ["-i", f]
        parts.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur={gap}[a{i}]")
    joined = "".join(f"[a{i}]" for i in range(len(files)))
    graph = ";".join(parts) + f";{joined}concat=n={len(files)}:v=0:a=1[out]"
    ffmpeg(*args, "-filter_complex", graph, "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k",
           episode.path("full_narration.mp3"))


def run_stage(episode, channel, client=None, placeholder=False, sleep=None):
    step(f"Stage 2 · Voiceover · {episode.slug}" + (" (placeholders, --no-voice)" if placeholder else ""))
    if not episode.reached("drafted"):
        raise StageError(f"Write the script first: python run.py write {episode.slug}")
    require_ffmpeg()
    if not placeholder:
        voice_id = require_env("ELEVENLABS_VOICE_ID")["ELEVENLABS_VOICE_ID"]
        model_id = env("ELEVENLABS_MODEL", DEFAULT_MODEL)
    retry_kwargs = {"sleep": sleep} if sleep else {}

    episode.data["review_notes"] = [n for n in episode.data["review_notes"] if n.get("stage") != "voice"]
    failed = []
    for scene in episode.data["scenes"]:
        path = episode.path(audio_name(scene))
        is_placeholder = scene.get("audio_placeholder")
        if path.exists() and (placeholder or not is_placeholder):
            info(f"Scene {scene['n']:02d}: exists, skipped")
        elif placeholder:
            write_placeholder(path, estimated_seconds(scene, channel))
            scene["audio_placeholder"] = True
            info(f"Scene {scene['n']:02d}: silent placeholder")
        else:
            client = client or make_client()
            try:
                audio = with_retries(lambda: synthesize(client, scene["narration"], voice_id, model_id),
                                     is_transient_http, label=f"Scene {scene['n']:02d}: ", **retry_kwargs)
            except Exception as e:  # noqa: BLE001 - log every failure, keep going
                failed.append(scene["n"])
                episode.add_review_note(f"Voiceover failed: {e}", stage="voice", scene=scene["n"])
                warn(f"Scene {scene['n']:02d}: FAILED ({e})")
                continue
            tmp = path.with_suffix(".tmp.mp3")
            tmp.write_bytes(audio)
            tmp.replace(path)
            scene["audio_placeholder"] = False
            info(f"Scene {scene['n']:02d}: generated")

        scene["audio_file"] = audio_name(scene)
        scene["audio_seconds"] = round(duration(path), 2)
        if scene["audio_seconds"] > scene["clip_seconds"]:
            over = scene["audio_seconds"] - scene["clip_seconds"]
            episode.add_review_note(
                f"Voice is {scene['audio_seconds']:.1f} s, {over:.1f} s longer than the "
                f"{scene['clip_seconds']} s clip (last frame will be frozen to cover it)",
                stage="voice", scene=scene["n"])
        episode.save()

    if failed:
        raise StageError(f"Voiceover failed for scene(s) {failed}. See review_notes, then rerun: "
                         f"python run.py voice {episode.slug}")
    build_full_narration(episode)
    if not episode.reached("voiced"):
        episode.set_status("voiced")
    total = sum(s["audio_seconds"] for s in episode.data["scenes"])
    info(f"Narration total {total:.1f} s. Quick listen: {episode.path('full_narration.mp3')}")
    long_ones = [n for n in episode.data["review_notes"] if n["stage"] == "voice"]
    if long_ones:
        warn(f"{len(long_ones)} scene(s) run longer than their clip; see review_notes.")
    return episode
