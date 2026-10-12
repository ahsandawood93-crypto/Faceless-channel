"""Stage 1: turn a topic into a scene-by-scene script with Claude.

Claude must answer by calling the `write_episode` tool. The current models
(Sonnet 5.5, Opus 5.5) reject a *forced* tool_choice, so we use tool_choice
"auto" + strict: true (schema-valid arguments) and tell Claude to call the
tool. The result is checked in code; problems go back to Claude as a
tool_result error, up to MAX_RETRIES times. Anything still wrong is written
to review_notes for a human.
"""

import re

from pipeline.config import env, require_env
from pipeline.util import StageError, info, step, warn

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_RETRIES = 2
CLIP_LENGTHS = [4, 6, 8]
SEO_TITLE_MAX = 59        # "under 60 characters"
LENGTH_TOLERANCE = 0.2    # total runtime may be +-20% of target_minutes
# Models that accept the server-side refusal fallback (`fallbacks: "default"`).
FALLBACK_MODELS = ("claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1")
FALLBACK_BETA = "server-side-fallback-2026-07-01"


# ---- prompt & tool -------------------------------------------------------------

def word_cap(channel, clip_seconds):
    return channel["narrator"]["words_per_minute"] * clip_seconds // 60


def episode_tool(channel):
    keys = list(channel["characters"])
    return {
        "name": "write_episode",
        "description": "Return the complete episode script. Call this exactly once with the whole episode.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "scenes", "seo", "review_notes"],
            "properties": {
                "title": {"type": "string", "description": "Episode title shown in the video and thumbnail."},
                "scenes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["narration", "on_screen", "characters", "veo_prompt", "clip_seconds"],
                        "properties": {
                            "narration": {"type": "string", "description": "What the narrator says in this scene."},
                            "on_screen": {
                                "type": ["string", "null"],
                                "description": "Short letter, number or word overlaid on screen (e.g. 'A', '3', 'Red'), or null.",
                            },
                            "characters": {
                                "type": "array",
                                "items": {"type": "string", "enum": keys},
                                "description": "Which channel characters appear in this scene's video.",
                            },
                            "veo_prompt": {"type": "string", "description": "Self-contained video prompt for this scene."},
                            "clip_seconds": {"type": "integer", "enum": CLIP_LENGTHS},
                        },
                    },
                },
                "seo": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "description", "tags"],
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "review_notes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Anything a human reviewer should double-check (facts, tricky visuals...).",
                },
            },
        },
    }


def system_prompt(channel):
    ch, narrator = channel["channel"], channel["narrator"]
    caps = ", ".join(f"{s} s clip = max {word_cap(channel, s)} words" for s in CLIP_LENGTHS)
    characters = "\n".join(
        f"- {key} ({c['name']}): {c['description']}" for key, c in channel["characters"].items()
    )
    rules = "\n".join(f"- {r}" for r in channel["content_rules"])
    target_seconds = int(ch["target_minutes"] * 60)
    return f"""You write scripts for {ch['name']}, an English YouTube Kids channel.
Audience: {ch['audience']}.

Narrator: {narrator['style']}
The narrator speaks at {narrator['words_per_minute']} words per minute.

CHARACTERS (original to this channel):
{characters}

VISUAL STYLE:
{channel['visual_style']}

CONTENT RULES:
{rules}

HOW AN EPISODE IS BUILT
- The episode is a list of scenes. One scene = one AI-generated video clip of
  clip_seconds (4, 6 or 8) with the scene's narration read over it.
- Aim for about {target_seconds} seconds in total (sum of clip_seconds).
- Narration word limits: {caps}. Short, simple sentences. Repeat key words.
- on_screen is a single letter, number or very short word to show big on
  screen while it is being taught; null when nothing should be shown.
- The first scene's narration must start with exactly: "{channel['intro_line']}"
- The last scenes recap what was learned. The final scene's narration must end
  with exactly: "{channel['outro_line']}"

VEO PROMPTS
The video model has no memory between clips, so every veo_prompt must stand
alone. Each veo_prompt must:
- include, word for word, the full description above of every character listed
  in that scene's `characters`;
- include, word for word, the VISUAL STYLE paragraph above;
- describe the setting, the action and the camera (shot type, movement);
- contain no dialogue or speech and no text, letters, numbers or signs drawn in
  the scene (on-screen text is added later in editing).

SEO
- seo.title: under 60 characters, clear and friendly, no clickbait or ALL CAPS.
- seo.description: 2-4 short paragraphs for parents describing what children learn.
- seo.tags: 10-15 relevant tags.

Always answer by calling the write_episode tool exactly once with the whole episode."""


# ---- validation ----------------------------------------------------------------

def _norm(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def count_words(text):
    return len(re.findall(r"[A-Za-z0-9']+", text or ""))


def validate(result, channel):
    """Return a list of problems with Claude's script (empty = all good)."""
    problems = []
    scenes = result.get("scenes") or []
    if not scenes:
        return ["scenes is empty"]
    style = _norm(channel["visual_style"])
    seen = set()
    for n, scene in enumerate(scenes, 1):
        seconds = scene.get("clip_seconds")
        if seconds not in CLIP_LENGTHS:
            problems.append(f"Scene {n}: clip_seconds must be one of {CLIP_LENGTHS}")
            continue
        words, cap = count_words(scene.get("narration")), word_cap(channel, seconds)
        if words > cap:
            problems.append(f"Scene {n}: narration has {words} words; max for {seconds} s is {cap}")
        if not words:
            problems.append(f"Scene {n}: narration is empty")
        prompt = _norm(scene.get("veo_prompt"))
        if style not in prompt:
            problems.append(f"Scene {n}: veo_prompt must include the VISUAL STYLE paragraph word for word")
        for key in scene.get("characters") or []:
            seen.add(key)
            char = channel["characters"].get(key)
            if char and _norm(char["description"]) not in prompt:
                problems.append(
                    f"Scene {n}: veo_prompt must include {char['name']}'s full description word for word"
                )
    for key, char in channel["characters"].items():
        if key not in seen:
            problems.append(f"{char['name']} does not appear in any scene")

    if not _norm(scenes[0].get("narration")).startswith(_norm(channel["intro_line"])):
        problems.append(f"Scene 1 narration must start with the intro line: {channel['intro_line']!r}")
    if not _norm(scenes[-1].get("narration")).endswith(_norm(channel["outro_line"])):
        problems.append(f"The final scene's narration must end with the outro line: {channel['outro_line']!r}")

    target = channel["channel"]["target_minutes"] * 60
    total = sum(s.get("clip_seconds") or 0 for s in scenes)
    if abs(total - target) > target * LENGTH_TOLERANCE:
        problems.append(f"Total length is {total} s; aim for about {int(target)} s (+-{int(LENGTH_TOLERANCE * 100)}%)")

    seo = result.get("seo") or {}
    title = (seo.get("title") or "").strip()
    if not title:
        problems.append("seo.title is empty")
    elif len(title) > SEO_TITLE_MAX:
        problems.append(f"seo.title is {len(title)} characters; it must be under 60")
    if not (result.get("title") or "").strip():
        problems.append("title is empty")
    if not seo.get("tags"):
        problems.append("seo.tags is empty")
    return problems


# ---- Claude call ---------------------------------------------------------------

def make_client():
    import anthropic

    key = require_env("ANTHROPIC_API_KEY")["ANTHROPIC_API_KEY"]
    return anthropic.Anthropic(api_key=key, max_retries=4)  # SDK retries 429/5xx itself


def _call(client, model, system, tools, messages):
    kwargs = dict(model=model, max_tokens=64000, system=system, tools=tools,
                  tool_choice={"type": "auto"}, messages=messages)
    if model in FALLBACK_MODELS:
        kwargs.update(betas=[FALLBACK_BETA], fallbacks="default")
    # Streaming avoids HTTP timeouts on long outputs (~25 detailed scenes).
    with client.beta.messages.stream(**kwargs) as stream:
        return stream.get_final_message()


def ask_claude(topic, channel, client=None, model=None):
    """Return (result_dict, unresolved_problems)."""
    client = client or make_client()
    model = model or env("CLAUDE_MODEL", DEFAULT_MODEL)
    system, tools = system_prompt(channel), [episode_tool(channel)]
    messages = [{"role": "user", "content": f"Write the episode for this topic: {topic}"}]
    result, problems = None, []

    for attempt in range(MAX_RETRIES + 1):
        info(f"Asking {model} (attempt {attempt + 1}/{MAX_RETRIES + 1})...")
        response = _call(client, model, system, tools, messages)
        if response.stop_reason == "refusal":
            raise StageError("Claude declined to write this topic. Try rewording it in topics.txt.")
        if response.stop_reason == "max_tokens":
            raise StageError("Claude's answer was cut off (max_tokens). Rerun, or ask for fewer scenes.")
        tool_use = next((b for b in response.content if b.type == "tool_use" and b.name == "write_episode"), None)
        messages.append({"role": "assistant", "content": response.content})

        if tool_use is None:
            problems = ["No write_episode tool call was returned"]
            messages.append({"role": "user", "content": "Please answer by calling the write_episode tool."})
            continue

        result = tool_use.input
        problems = validate(result, channel)
        if not problems:
            return result, []
        warn(f"{len(problems)} problem(s) found; sending them back to Claude")
        for p in problems:
            info(f"- {p}")
        messages.append({"role": "user", "content": [{
            "type": "tool_result", "tool_use_id": tool_use.id, "is_error": True,
            "content": "Please fix these problems and call write_episode again with the whole episode:\n- "
                       + "\n- ".join(problems),
        }]})

    if result is None:
        raise StageError("Claude never returned a script. Rerun: python run.py write <slug>")
    return result, problems


# ---- write files ---------------------------------------------------------------

def scenes_from_result(result):
    return [
        {
            "n": n,
            "narration": s["narration"].strip(),
            "on_screen": (s.get("on_screen") or None),
            "characters": list(s.get("characters") or []),
            "veo_prompt": s["veo_prompt"].strip(),
            "clip_seconds": s["clip_seconds"],
            "audio_file": None, "audio_seconds": None, "audio_placeholder": False,
            "clip_file": None, "clip_placeholder": False,
        }
        for n, s in enumerate(result["scenes"], 1)
    ]


def render_markdown(data):
    lines = [f"# {data['title']}", "", f"Topic: {data['topic']}  ", f"Status: {data['status']}", "",
             "## Review checklist", ""]
    notes = data["review_notes"] or [{"message": "Nothing flagged automatically."}]
    for note in notes:
        where = f"Scene {note['scene']}: " if note.get("scene") else ""
        lines.append(f"- [ ] {where}{note['message']}")
    lines += ["- [ ] Facts are correct and age-appropriate",
              "- [ ] Nothing scary, sad or dangerous; no brands, real people or copyrighted characters",
              "- [ ] Ends with a recap and a goodbye", ""]
    total = sum(s["clip_seconds"] for s in data["scenes"])
    lines += [f"## Scenes ({len(data['scenes'])} scenes, {total} s)", ""]
    for s in data["scenes"]:
        who = ", ".join(s["characters"]) or "no characters"
        lines += [f"### Scene {s['n']} · {s['clip_seconds']} s · {who}", "",
                  f"**Narration:** {s['narration']}", ""]
        if s["on_screen"]:
            lines += [f"**On screen:** {s['on_screen']}", ""]
        lines += ["**Veo prompt:**", "", f"> {s['veo_prompt']}", ""]
    seo = data["seo"]
    lines += ["## SEO", "", f"**Title:** {seo['title']}", "", "**Description:**", "",
              seo["description"], "", "**Tags:** " + ", ".join(seo["tags"]), ""]
    return "\n".join(lines)


def write_markdown(episode):
    episode.path("episode.md").write_text(render_markdown(episode.data), encoding="utf-8")


def run_stage(episode, channel, client=None, force=False):
    step(f"Stage 1 · Script · {episode.slug}")
    if episode.reached("drafted") and not force:
        info("Script already written (use --force to rewrite).")
        return episode
    result, problems = ask_claude(episode.data["topic"], channel, client=client)

    episode.data["title"] = result["title"].strip()
    episode.data["scenes"] = scenes_from_result(result)
    episode.data["seo"] = {
        "title": result["seo"]["title"].strip(),
        "description": result["seo"]["description"].strip(),
        "tags": [t.strip() for t in result["seo"]["tags"] if t.strip()],
    }
    episode.data["review_notes"] = [n for n in episode.data["review_notes"] if n.get("stage") != "script"]
    for note in result.get("review_notes") or []:
        episode.add_review_note(f"Claude: {note}", stage="script")
    for problem in problems:
        scene = re.match(r"Scene (\d+):", problem)
        episode.add_review_note(f"Unresolved: {problem}", stage="script",
                                scene=int(scene.group(1)) if scene else None)
    episode.set_status("drafted")
    write_markdown(episode)

    total = sum(s["clip_seconds"] for s in episode.data["scenes"])
    info(f"Title: {episode.data['title']}")
    info(f"{len(episode.data['scenes'])} scenes, {total} s. Review: {episode.path('episode.md')}")
    if problems:
        warn(f"{len(problems)} problem(s) left after {MAX_RETRIES} retries; listed in review_notes.")
    return episode
