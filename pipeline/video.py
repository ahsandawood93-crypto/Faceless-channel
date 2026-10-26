"""Stage 3: one Veo 3.1 clip per scene through Vertex AI (Google Cloud), google-genai SDK.

Google shut down the Veo 3.1 *preview* models on the Gemini API on 2026-10-22,
so this uses the GA Veo models on Vertex AI (e.g. veo-3.1-fast-generate-001).

- Character reference images (assets/characters/*.png) are sent as "asset"
  reference images so Minsa and Mana look the same in every clip. With
  reference images Veo returns 8-second clips; assembly trims to clip_seconds.
- Audio generation is switched off (cheaper video-only rate) and any audio
  track is stripped with ffmpeg anyway; narration comes from Stage 2.
- Existing clips are skipped. Shows the estimated cost and asks first.
- --no-video writes free solid-colour placeholders instead.
"""

import time

from pipeline.config import ROOT, ConfigError, env, require_env
from pipeline.util import (StageError, confirm, ffmpeg, info, is_transient_http, require_ffmpeg,
                           status_code, step, warn, with_retries)

POLL_SECONDS = 10
TIMEOUT_SECONDS = 15 * 60
NEGATIVE_PROMPT = ("text, letters, numbers, words, captions, subtitles, watermark, logo, "
                   "talking, lip sync, scary, dark, violent, sad")
PROMPT_SUFFIX = " No dialogue or speech. No text, letters, numbers or signs anywhere in the scene."
PLACEHOLDER_COLOURS = ["0x8ecae6", "0xffb703", "0x90be6d", "0xf4a3c4", "0xcdb4db"]
DEFAULT_LOCATION = "us-central1"
CHILD_SAFETY_HINT = ("Veo's people filter may be blocking a child character. See README "
                     "'Veo and child characters'.")


class ClipFailed(Exception):
    """Veo finished but gave no usable video (e.g. blocked by its safety filter)."""


def clip_name(scene):
    return f"clips/scene_{scene['n']:02d}.mp4"


def todo_scenes(episode, placeholder=False):
    """Scenes that still need a clip. Placeholders count as missing for real runs."""
    out = []
    for scene in episode.data["scenes"]:
        exists = (episode.dir / clip_name(scene)).exists()
        if not exists or (scene.get("clip_placeholder") and not placeholder):
            out.append(scene)
    return out


def estimate_cost(channel, n_clips):
    veo = channel["veo"]
    return n_clips * veo["generated_seconds"] * veo["usd_per_second"]


def reference_images(scene, channel):
    """(key, path) for each character in the scene that has a reference image."""
    refs = []
    for key in scene.get("characters") or []:
        path = ROOT / channel["characters"][key]["reference_image"]
        if not path.exists():
            raise ConfigError(f"Missing reference image for {key}: {path} (see assets/README.md)")
        refs.append((key, path))
    return refs[:3]  # Veo accepts up to 3 reference images


def make_client():
    """Vertex AI client. Auth comes from `gcloud auth application-default login`
    or a service-account JSON in GOOGLE_APPLICATION_CREDENTIALS."""
    from google import genai

    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    project = require_env("GOOGLE_CLOUD_PROJECT")["GOOGLE_CLOUD_PROJECT"]
    location = env("GOOGLE_CLOUD_LOCATION", DEFAULT_LOCATION)
    try:
        google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    except DefaultCredentialsError:
        raise ConfigError("No Google Cloud login found for Vertex AI. Run once: "
                          "gcloud auth application-default login   (README 'Vertex AI setup')") from None
    return genai.Client(vertexai=True, project=project, location=location)


def _image(path):
    from google.genai import types

    return types.Image(image_bytes=path.read_bytes(), mime_type="image/png")


def _is_reference_unsupported(error):
    text = str(error).lower()
    return "reference" in text and ("not supported" in text or "unsupported" in text)


def generate_clip(client, scene, channel, out_path, use_references=True, sleep=time.sleep):
    """Generate, download and de-audio one clip. Returns a note if a fallback was used."""
    from google.genai import types

    veo = channel["veo"]
    refs = reference_images(scene, channel)
    config = dict(aspect_ratio=veo["aspect_ratio"], resolution=veo["resolution"],
                  duration_seconds=veo["generated_seconds"], number_of_videos=1,
                  negative_prompt=NEGATIVE_PROMPT, generate_audio=bool(veo.get("generate_audio", False)))
    if veo.get("person_generation"):
        config["person_generation"] = veo["person_generation"]
    kwargs = {}
    if refs and use_references:
        config["reference_images"] = [
            types.VideoGenerationReferenceImage(image=_image(p), reference_type="asset") for _, p in refs
        ]
    elif refs:
        kwargs["image"] = _image(refs[0][1])  # fallback: first character as the starting frame

    operation = client.models.generate_videos(
        model=veo["model"], prompt=scene["veo_prompt"] + PROMPT_SUFFIX,
        config=types.GenerateVideosConfig(**config), **kwargs,
    )
    waited = 0
    while not operation.done:
        if waited >= TIMEOUT_SECONDS:
            raise TimeoutError(f"Veo took longer than {TIMEOUT_SECONDS // 60} minutes")
        sleep(POLL_SECONDS)
        waited += POLL_SECONDS
        operation = client.operations.get(operation)

    if operation.error:
        raise ClipFailed(f"Veo error: {operation.error}")
    response = operation.response
    videos = getattr(response, "generated_videos", None) if response else None
    if not videos:
        reasons = getattr(response, "rai_media_filtered_reasons", None) if response else None
        message = f"Veo returned no video (safety filter?) {reasons or ''}".strip()
        if any(w in str(reasons).lower() for w in ("child", "minor", "person", "people")):
            message += " " + CHILD_SAFETY_HINT
        raise ClipFailed(message)

    video = videos[0].video
    raw = out_path.with_suffix(".raw.mp4")
    if not getattr(video, "video_bytes", None):
        if not str(getattr(video, "uri", "")).startswith("http"):
            raise ClipFailed(f"Veo returned the video at {video.uri!r}, which can't be downloaded here")
        client.files.download(file=video)  # Gemini-API style URI
    video.save(str(raw))  # Vertex returns the MP4 bytes inline
    ffmpeg("-i", raw, "-an", "-c:v", "copy", "-movflags", "+faststart", out_path)  # strip audio
    raw.unlink(missing_ok=True)


def write_placeholder(path, scene, channel):
    colour = PLACEHOLDER_COLOURS[scene["n"] % len(PLACEHOLDER_COLOURS)]
    ffmpeg("-f", "lavfi", "-i", f"color=c={colour}:s=1920x1080:r=30",
           "-t", channel["veo"]["generated_seconds"], "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", path)


def run_stage(episode, channel, client=None, yes=False, placeholder=False, sleep=time.sleep):
    step(f"Stage 3 · Veo clips · {episode.slug}" + (" (placeholders, --no-video)" if placeholder else ""))
    if not episode.reached("voiced"):
        raise StageError(f"Make the voiceover first: python run.py voice {episode.slug}")
    require_ffmpeg()
    todo = todo_scenes(episode, placeholder)
    done = len(episode.data["scenes"]) - len(todo)
    if done:
        info(f"{done} clip(s) already exist, skipped")

    if todo and not placeholder:
        for scene in todo:
            reference_images(scene, channel)  # fail on a missing image before spending money
        cost = estimate_cost(channel, len(todo))
        veo = channel["veo"]
        info(f"{len(todo)} clip(s) × {veo['generated_seconds']} s × ${veo['usd_per_second']:.2f}/s "
             f"({veo['model']}, {veo['resolution']}) ≈ ${cost:.2f}")
        cap = veo.get("max_usd_per_run")
        if cap is not None and cost > cap:
            raise StageError(f"Estimated ${cost:.2f} is over veo.max_usd_per_run (${cap}) in channel.yaml. "
                             "Raise the limit or shorten the episode.")
        if not yes and not confirm(f"Generate {len(todo)} clip(s) for about ${cost:.2f}?"):
            raise StageError(f"Cancelled. Rerun when ready: python run.py video {episode.slug}")

    episode.data["review_notes"] = [n for n in episode.data["review_notes"] if n.get("stage") != "video"]
    failed = []
    for scene in todo:
        path = episode.path(clip_name(scene))
        label = f"Scene {scene['n']:02d}: "
        if placeholder:
            write_placeholder(path, scene, channel)
            scene.update(clip_file=clip_name(scene), clip_placeholder=True)
            episode.save()
            info(f"{label}placeholder")
            continue
        client = client or make_client()
        info(f"{label}generating (this takes a few minutes)...")
        try:
            try:
                with_retries(lambda: generate_clip(client, scene, channel, path, sleep=sleep),
                             is_transient_http, sleep=sleep, label=label)
            except Exception as e:  # noqa: BLE001
                if not _is_reference_unsupported(e):
                    raise
                warn(f"{label}reference images not accepted; retrying with a starting image instead")
                with_retries(lambda: generate_clip(client, scene, channel, path, use_references=False,
                                                   sleep=sleep), is_transient_http, sleep=sleep, label=label)
                episode.add_review_note("Reference images were rejected; used the character image as the "
                                        "starting frame. Check character consistency.",
                                        stage="video", scene=scene["n"])
        except Exception as e:  # noqa: BLE001 - log every failure and continue with other scenes
            failed.append(scene["n"])
            episode.add_review_note(f"Clip failed: {e}", stage="video", scene=scene["n"])
            warn(f"{label}FAILED ({e})")
            if status_code(e) in (401, 403, 404):  # same for every scene: stop instead of repeating it
                raise StageError(
                    f"Vertex AI refused the request ({e}). Check: Vertex AI API enabled, billing on, "
                    f"your login (gcloud auth application-default login), and that veo.model "
                    f"'{channel['veo']['model']}' still exists. Then rerun: python run.py video {episode.slug}"
                ) from e
            continue
        scene.update(clip_file=clip_name(scene), clip_placeholder=False)
        episode.save()
        info(f"{label}saved {clip_name(scene)}")

    if failed:
        raise StageError(
            f"Clips failed for scene(s) {failed}. See review_notes. You can edit those scenes' veo_prompt in "
            f"episode.json, then rerun (finished clips are kept): python run.py video {episode.slug}")
    if not episode.reached("clips_ready"):
        episode.set_status("clips_ready")
    info(f"All {len(episode.data['scenes'])} clips ready.")
    return episode
