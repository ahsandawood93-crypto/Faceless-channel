"""Stage 4: build final/episode.mp4, episode.srt and thumbnail.jpg with ffmpeg.

Per scene: the clip (trimmed to clip_seconds) + its narration. If the voice is
longer than the clip, the last frame is frozen to cover the gap. On-screen
letters/numbers and captions are drawn as PNGs with Pillow and overlaid by
ffmpeg (no libass/subtitles-filter quirks, works the same on Windows).
Then: optional intro/outro, background music ducked under the voice with a
fade-out, and two-pass loudness normalisation to -14 LUFS.
"""

import json
import random
import re
import shutil
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from pipeline.config import ROOT
from pipeline.util import StageError, duration, ffmpeg, has_audio, info, require_ffmpeg, step, warn

W, H, FPS = 1920, 1080, 30
VIDEO_ARGS = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]
AUDIO_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
TARGET_LUFS = -14
TAIL_PAD = 0.3            # seconds of breathing room after each scene's narration
CAPTION_MAX_WORDS = 7
MUSIC_VOLUME = 0.30
MUSIC_FADE = 3.0
THUMB_SIZE = (1280, 720)
THUMB_MAX_BYTES = 2 * 1024 * 1024
ASSETS = ROOT / "assets"
MUSIC_TYPES = (".mp3", ".wav", ".m4a", ".ogg", ".flac")

OVERLAY_FILL = (255, 196, 0)       # sunny yellow letter
OVERLAY_STROKE = (40, 60, 160)     # deep blue outline
BUBBLE = (255, 255, 255, 235)
BUBBLE_EDGE = (255, 120, 170, 255)  # pink rim


# ---- fonts & images --------------------------------------------------------------

def find_font():
    fonts = sorted(p for p in (ASSETS / "fonts").glob("*") if p.suffix.lower() in (".ttf", ".otf"))
    return fonts[0] if fonts else None


def load_font(size):
    path = find_font()
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default(size=size)


def text_size(draw, text, font, stroke=0):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
    return right - left, bottom - top, left, top


def overlay_png(text, path):
    """Big rounded bubble with the scene's letter/number, top-right of the frame."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    size = int(H * (0.30 if len(text) <= 3 else 0.14))
    font = load_font(size)
    stroke = max(6, size // 18)
    while True:
        tw, th, left, top = text_size(draw, text, font, stroke)
        if tw <= W * 0.4 or size <= 40:
            break
        size = int(size * 0.85)
        font, stroke = load_font(size), max(6, size // 18)
    pad = int(size * 0.28)
    bw, bh = max(tw, th) + 2 * pad if len(text) <= 3 else tw + 2 * pad, th + 2 * pad
    x0, y0 = W - bw - 80, 70
    draw.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=min(bw, bh) // 3,
                           fill=BUBBLE, outline=BUBBLE_EDGE, width=14)
    draw.text((x0 + (bw - tw) / 2 - left, y0 + (bh - th) / 2 - top), text, font=font,
              fill=OVERLAY_FILL, stroke_width=stroke, stroke_fill=OVERLAY_STROKE)
    img.save(path)


def caption_png(text, path):
    """Caption line(s) on a rounded dark box near the bottom of the frame."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(66)
    lines = textwrap.wrap(text, width=38) or [text]
    sizes = [text_size(draw, line, font, 3) for line in lines]
    line_h = max(s[1] for s in sizes) + 16
    box_w = max(s[0] for s in sizes) + 80
    box_h = line_h * len(lines) + 40
    x0, y0 = (W - box_w) // 2, H - box_h - 60
    draw.rounded_rectangle([x0, y0, x0 + box_w, y0 + box_h], radius=34, fill=(20, 20, 50, 170))
    for i, (line, (tw, _, left, top)) in enumerate(zip(lines, sizes)):
        draw.text(((W - tw) / 2 - left, y0 + 20 + i * line_h - top), line, font=font,
                  fill="white", stroke_width=3, stroke_fill=(20, 20, 50))
    img.save(path)


# ---- captions & SRT ----------------------------------------------------------------

def caption_chunks(narration, seconds):
    """Split narration into short caption chunks timed by word count across the real audio length."""
    sentences = re.split(r"(?<=[.!?])\s+", narration.strip())
    chunks = []
    for sentence in sentences:
        words = sentence.split()
        while words:
            take = len(words) if len(words) <= CAPTION_MAX_WORDS + 2 else CAPTION_MAX_WORDS
            chunks.append(" ".join(words[:take]))
            words = words[take:]
    total_words = sum(len(c.split()) for c in chunks) or 1
    out, t = [], 0.0
    for chunk in chunks:
        length = seconds * len(chunk.split()) / total_words
        out.append((round(t, 2), round(t + length, 2), chunk))
        t += length
    return out


def srt_time(seconds):
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(entries):
    blocks = [f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n" for i, (a, b, text) in enumerate(entries, 1)]
    return "\n".join(blocks)


# ---- video pieces ------------------------------------------------------------------

def scene_segment(episode, scene, work):
    """Render one scene to work/scene_XX.mp4. Returns (seconds, caption chunks)."""
    clip = episode.dir / scene["clip_file"]
    audio = episode.dir / scene["audio_file"]
    voice = duration(audio)
    clip_len = min(scene["clip_seconds"], duration(clip))
    seg = round(max(scene["clip_seconds"], voice + TAIL_PAD), 2)
    freeze = max(0.0, seg - clip_len)

    inputs = ["-i", clip, "-i", audio]
    graph = [f"[0:v]trim=duration={clip_len},setpts=PTS-STARTPTS,"
             f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p,"
             f"tpad=stop_mode=clone:stop_duration={freeze:.2f}[v0]"]
    label, n_in = "v0", 2
    if scene.get("on_screen"):
        png = work / f"overlay_{scene['n']:02d}.png"
        overlay_png(scene["on_screen"], png)
        inputs += ["-i", png]
        graph.append(f"[{label}][{n_in}:v]overlay=0:0:enable='gte(t,0.25)'[o{n_in}]")
        label, n_in = f"o{n_in}", n_in + 1
    chunks = caption_chunks(scene["narration"], voice)
    for i, (a, b, text) in enumerate(chunks):
        png = work / f"caption_{scene['n']:02d}_{i}.png"
        caption_png(text, png)
        inputs += ["-i", png]
        graph.append(f"[{label}][{n_in}:v]overlay=0:0:enable='between(t,{a},{b})'[c{n_in}]")
        label, n_in = f"c{n_in}", n_in + 1
    graph.append(f"[1:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{seg}[a]")

    out = work / f"scene_{scene['n']:02d}.mp4"
    ffmpeg(*inputs, "-filter_complex", ";".join(graph), "-map", f"[{label}]", "-map", "[a]",
           "-t", seg, *VIDEO_ARGS, *AUDIO_ARGS, out)
    return seg, chunks, out


def normalise_bumper(src, out):
    """Re-encode intro/outro to the same format as the scenes (adds silence if it has no audio)."""
    seconds = duration(src)
    audio = ["-map", "0:a"] if has_audio(src) else ["-map", "1:a"]
    ffmpeg("-i", src, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,"
                  f"fps={FPS},format=yuv420p",
           "-map", "0:v", *audio, "-t", f"{seconds:.2f}", *VIDEO_ARGS, *AUDIO_ARGS, out)
    return duration(out)


def concat(parts, out, work):
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    ffmpeg("-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", out)


def pick_music(rng=random):
    tracks = sorted(p for p in (ASSETS / "music").glob("*") if p.suffix.lower() in MUSIC_TYPES)
    return rng.choice(tracks) if tracks else None


def measure_loudness(media, audio_filter=None):
    """Integrated loudness measurement via loudnorm's analysis pass (returns dict)."""
    af = (audio_filter + "," if audio_filter else "") + f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json"
    result = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(media), "-af", af,
                             "-vn", "-f", "null", "-"], capture_output=True, text=True)
    if result.returncode != 0:
        raise StageError(f"ffmpeg loudness pass failed:\n{result.stderr[-1500:]}")
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", result.stderr, re.S)
    if not match:
        raise StageError("Could not read the loudness measurement from ffmpeg.")
    return json.loads(match.group(0))


def mix_and_normalise(body, out, music, work):
    """Duck music under the voice, fade it out, then two-pass loudnorm to -14 LUFS."""
    total = duration(body)
    mixed = work / "mixed.mp4"
    if music:
        fade_start = max(0.0, total - MUSIC_FADE)
        graph = (f"[0:a]asplit=2[voice][key];"
                 f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={MUSIC_VOLUME},atrim=0:{total:.2f}[m];"
                 f"[m][key]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[duck];"
                 f"[duck]afade=t=out:st={fade_start:.2f}:d={MUSIC_FADE}[mf];"
                 f"[voice][mf]amix=inputs=2:duration=first:normalize=0[a]")
        ffmpeg("-i", body, "-stream_loop", "-1", "-i", music, "-filter_complex", graph,
               "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AUDIO_ARGS, "-t", f"{total:.2f}", mixed)
    else:
        shutil.copy(body, mixed)

    m = measure_loudness(mixed)
    if _lufs(m["input_i"]) < -70:  # silence (e.g. --no-voice placeholders): nothing to normalise
        shutil.copy(mixed, out)
        return _lufs(m["input_i"])
    loudnorm = (f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
                f"offset={m['target_offset']}:linear=true")
    ffmpeg("-i", mixed, "-map", "0:v", "-map", "0:a", "-c:v", "copy", "-af", loudnorm,
           *AUDIO_ARGS, "-movflags", "+faststart", out)
    return _lufs(measure_loudness(out)["input_i"])


def _lufs(value):
    value = float(value)  # ffmpeg reports "-inf" for pure silence
    return value if value > -99 else -99.0


# ---- thumbnail -----------------------------------------------------------------------

def thumbnail_scene(scenes):
    both = [s for s in scenes if len(s.get("characters") or []) >= 2]
    return both[0] if both else scenes[len(scenes) // 2]


def make_thumbnail(episode, out, work):
    scene = thumbnail_scene(episode.data["scenes"])
    clip = episode.dir / scene["clip_file"]
    frame = work / "thumb_frame.png"
    at = min(2.0, duration(clip) / 2)
    ffmpeg("-ss", f"{at:.2f}", "-i", clip, "-frames:v", "1",
           "-vf", f"scale={THUMB_SIZE[0]}:{THUMB_SIZE[1]}:force_original_aspect_ratio=increase,"
                  f"crop={THUMB_SIZE[0]}:{THUMB_SIZE[1]}", frame)
    img = Image.open(frame).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.35)
    img = ImageEnhance.Contrast(img).enhance(1.05)

    title = episode.data["title"] or episode.data["seo"]["title"]
    draw = ImageDraw.Draw(img, "RGBA")
    size = 120
    while True:
        font = load_font(size)
        lines = textwrap.wrap(title, width=max(8, int(1150 / (size * 0.55))))
        widths = [text_size(draw, line, font, 10)[0] for line in lines]
        if (max(widths) <= 1180 and len(lines) <= 3) or size <= 50:
            break
        size -= 8
    line_h = int(size * 1.1)
    block_h = line_h * len(lines) + 40
    y = THUMB_SIZE[1] - block_h - 30
    draw.rounded_rectangle([30, y - 10, THUMB_SIZE[0] - 30, y + block_h], radius=40, fill=(40, 70, 200, 200))
    for i, line in enumerate(lines):
        tw, _, left, top = text_size(draw, line, font, 10)
        draw.text(((THUMB_SIZE[0] - tw) / 2 - left, y + 15 + i * line_h - top), line, font=font,
                  fill=(255, 221, 0), stroke_width=10, stroke_fill=(20, 30, 90))
    for quality in (92, 85, 75, 65, 55):
        img.save(out, "JPEG", quality=quality, optimize=True)
        if out.stat().st_size < THUMB_MAX_BYTES:
            break


# ---- stage -----------------------------------------------------------------------------

def run_stage(episode, channel, rng=random):
    step(f"Stage 4 · Assembly · {episode.slug}")
    if not episode.reached("clips_ready"):
        raise StageError(f"Clips are not ready yet: python run.py video {episode.slug}")
    require_ffmpeg()
    if not find_font():
        warn("No font in assets/fonts/; using Pillow's default font (add a rounded .ttf, see assets/README.md).")
    scenes = episode.data["scenes"]
    for s in scenes:
        for key in ("audio_file", "clip_file"):
            if not s.get(key) or not (episode.dir / s[key]).exists():
                raise StageError(f"Scene {s['n']}: {key} missing. Rerun: python run.py "
                                 f"{'voice' if key == 'audio_file' else 'video'} {episode.slug}")

    episode.data["review_notes"] = [n for n in episode.data["review_notes"] if n.get("stage") != "assemble"]
    final = episode.path("final", "episode.mp4").parent
    work = final / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()
    parts, srt, t = [], [], 0.0

    intro = ASSETS / "intro.mp4"
    if intro.exists():
        out = work / "intro.mp4"
        t += normalise_bumper(intro, out)
        parts.append(out)
        info(f"Intro added ({t:.1f} s)")
    for scene in scenes:
        try:
            seconds, chunks, out = scene_segment(episode, scene, work)
        except StageError as e:
            raise StageError(f"Scene {scene['n']} failed to render: {e}\n"
                             f"Rerun: python run.py assemble {episode.slug}") from e
        srt += [(t + a, t + b, text) for a, b, text in chunks]
        parts.append(out)
        t += seconds
        frozen = " (last frame held)" if seconds > scene["clip_seconds"] else ""
        info(f"Scene {scene['n']:02d}: {seconds:.1f} s{frozen}")
    outro = ASSETS / "outro.mp4"
    if outro.exists():
        out = work / "outro.mp4"
        t += normalise_bumper(outro, out)
        parts.append(out)
        info("Outro added")

    body = work / "body.mp4"
    concat(parts, body, work)
    music = pick_music(rng)
    info(f"Music: {music.name if music else 'none (assets/music/ is empty)'}")
    video = final / "episode.mp4"
    lufs = mix_and_normalise(body, video, music, work)
    (final / "episode.srt").write_text(build_srt(srt), encoding="utf-8")
    make_thumbnail(episode, final / "thumbnail.jpg", work)
    shutil.rmtree(work, ignore_errors=True)

    placeholder = any(s.get("audio_placeholder") or s.get("clip_placeholder") for s in scenes)
    episode.data["final"] = {
        "video": "final/episode.mp4", "srt": "final/episode.srt", "thumbnail": "final/thumbnail.jpg",
        "seconds": round(duration(video), 2), "lufs": round(lufs, 1),
        "music": music.name if music else None, "placeholder": placeholder,
    }
    if not music:
        episode.add_review_note("No background music was added (assets/music/ is empty).", stage="assemble")
    if placeholder:
        episode.add_review_note("Contains placeholder voice/clips (dry run). Will not be uploaded.", stage="assemble")
    if not episode.reached("rendered"):
        episode.set_status("rendered")
    else:
        episode.save()
    info(f"Done: {video} ({episode.data['final']['seconds']:.0f} s, {lufs:.1f} LUFS)")
    info(f"Captions: {final / 'episode.srt'}   Thumbnail: {final / 'thumbnail.jpg'}")
    return episode
