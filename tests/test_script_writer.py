import copy
import json
from types import SimpleNamespace

import pytest

from pipeline import script_writer as sw
from pipeline.episode import Episode
from pipeline.util import StageError
from tests.conftest import MANA, MINSA


def good_result(channel, scenes=23):
    style = channel["visual_style"]
    out = []
    for n in range(1, scenes + 1):
        chars = ["minsa", "mana"] if n % 2 else ["minsa"]
        desc = " ".join(channel["characters"][c]["description"] for c in chars)
        narration = "A is for apple. Can you say apple?"
        if n == 1:
            narration = channel["intro_line"]
        if n == scenes:
            narration = channel["outro_line"]
        out.append({"narration": narration, "on_screen": "A" if n == 2 else None, "characters": chars,
                    "veo_prompt": f"{desc} They play in a garden. {style} Wide shot, slow pan.",
                    "clip_seconds": 8})
    return {"title": "Letter A is for Apple!", "scenes": out,
            "seo": {"title": "Letter A for Toddlers | Minsa Kids TV", "description": "Learn A.",
                    "tags": ["abc", "letter a"]},
            "review_notes": ["Check that the apple looks red."]}


# ---- fake Anthropic client ---------------------------------------------------------------

def tool_response(result, stop_reason="tool_use", tool_id="toolu_1"):
    block = SimpleNamespace(type="tool_use", name="write_episode", id=tool_id, input=result)
    return SimpleNamespace(stop_reason=stop_reason, content=[block])


def text_response(text="Here you go", stop_reason="end_turn"):
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])


class FakeStream:
    def __init__(self, response):
        self.response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.response


class FakeAnthropic:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": copy.copy(kwargs["messages"])})
        return FakeStream(self.responses.pop(0))


# ---- validation ---------------------------------------------------------------------------

def test_good_script_has_no_problems(channel):
    assert sw.validate(good_result(channel), channel) == []


def test_word_caps(channel):
    assert sw.word_cap(channel, 8) == 16
    assert sw.word_cap(channel, 6) == 12
    assert sw.word_cap(channel, 4) == 8
    result = good_result(channel)
    result["scenes"][3]["narration"] = " ".join(["apple"] * 17)
    assert "Scene 4: narration has 17 words; max for 8 s is 16" in sw.validate(result, channel)


def test_missing_character_description(channel):
    result = good_result(channel)
    result["scenes"][2]["veo_prompt"] = result["scenes"][2]["veo_prompt"].replace(MANA, "Mana the elephant.")
    assert any(p.startswith("Scene 3: veo_prompt must include Mana's full description")
               for p in sw.validate(result, channel))


def test_description_match_ignores_case_and_spacing(channel):
    result = good_result(channel)
    result["scenes"][0]["veo_prompt"] = result["scenes"][0]["veo_prompt"].replace(MINSA, MINSA.upper().replace(" ", "  "))
    assert sw.validate(result, channel) == []


def test_missing_visual_style(channel):
    result = good_result(channel)
    result["scenes"][1]["veo_prompt"] = MINSA + " In a garden."
    assert any("VISUAL STYLE" in p and p.startswith("Scene 2") for p in sw.validate(result, channel))


def test_every_character_must_appear(channel):
    result = good_result(channel)
    for s in result["scenes"]:
        s["characters"] = ["minsa"]
    assert "Mana does not appear in any scene" in sw.validate(result, channel)


def test_intro_outro_title_and_length(channel):
    result = good_result(channel, scenes=10)
    result["scenes"][0]["narration"] = "Hi kids."
    result["scenes"][-1]["narration"] = "The end."
    result["seo"]["title"] = "x" * 61
    problems = sw.validate(result, channel)
    assert any(p.startswith("Scene 1 narration must start with the intro line") for p in problems)
    assert any(p.startswith("The final scene's narration must end with the outro line") for p in problems)
    assert "seo.title is 61 characters; it must be under 60" in problems
    assert any(p.startswith("Total length is 80 s") for p in problems)


def test_tool_schema_is_strict(channel):
    tool = sw.episode_tool(channel)
    assert tool["strict"] is True
    scene = tool["input_schema"]["properties"]["scenes"]["items"]
    assert scene["additionalProperties"] is False
    assert scene["properties"]["clip_seconds"]["enum"] == [4, 6, 8]
    assert scene["properties"]["characters"]["items"]["enum"] == ["minsa", "mana"]


def test_system_prompt_contains_channel_bible(channel):
    prompt = sw.system_prompt(channel)
    for text in (MINSA, MANA, channel["visual_style"], channel["intro_line"], channel["outro_line"],
                 "8 s clip = max 16 words"):
        assert text in prompt


# ---- Claude loop --------------------------------------------------------------------------

def test_first_answer_valid(channel):
    client = FakeAnthropic([tool_response(good_result(channel))])
    result, problems = sw.ask_claude("Letter A", channel, client=client)
    assert problems == [] and result["title"] == "Letter A is for Apple!"
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["tool_choice"] == {"type": "auto"}   # forced tool_choice is rejected by current models
    assert call["fallbacks"] == "default" and call["betas"] == [sw.FALLBACK_BETA]


def test_problems_are_sent_back_as_tool_result_error(channel):
    bad = good_result(channel)
    bad["seo"]["title"] = "y" * 70
    client = FakeAnthropic([tool_response(bad, tool_id="toolu_bad"), tool_response(good_result(channel))])
    result, problems = sw.ask_claude("Letter A", channel, client=client)
    assert problems == []
    retry_messages = client.calls[1]["messages"]
    tool_result = retry_messages[-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["is_error"] is True
    assert tool_result["tool_use_id"] == "toolu_bad"
    assert "seo.title is 70 characters" in tool_result["content"]
    assert retry_messages[-2]["role"] == "assistant"


def test_no_tool_call_reprompts(channel):
    client = FakeAnthropic([text_response(), tool_response(good_result(channel))])
    result, problems = sw.ask_claude("Letter A", channel, client=client)
    assert problems == [] and len(client.calls) == 2
    assert "write_episode" in client.calls[1]["messages"][-1]["content"]


def test_gives_up_after_two_retries(channel):
    bad = good_result(channel)
    bad["scenes"][4]["narration"] = " ".join(["word"] * 30)
    client = FakeAnthropic([tool_response(bad)] * 3)
    result, problems = sw.ask_claude("Letter A", channel, client=client)
    assert len(client.calls) == sw.MAX_RETRIES + 1
    assert problems == ["Scene 5: narration has 30 words; max for 8 s is 16"]


def test_refusal_and_cutoff_stop(channel):
    with pytest.raises(StageError, match="declined"):
        sw.ask_claude("x", channel, client=FakeAnthropic([text_response(stop_reason="refusal")]))
    with pytest.raises(StageError, match="cut off"):
        sw.ask_claude("x", channel, client=FakeAnthropic([text_response(stop_reason="max_tokens")]))


def test_custom_model_from_env(channel, monkeypatch):
    monkeypatch.setenv("CLAUDE_MODEL", "claude-haiku-4-5")
    client = FakeAnthropic([tool_response(good_result(channel))])
    sw.ask_claude("Letter A", channel, client=client)
    assert client.calls[0]["model"] == "claude-haiku-4-5" and "fallbacks" not in client.calls[0]


# ---- stage output ---------------------------------------------------------------------------

def test_run_stage_writes_episode_json_and_md(channel, episodes_dir):
    bad = good_result(channel)
    bad["scenes"][4]["narration"] = " ".join(["word"] * 30)
    ep = Episode.create("Letter A is for Apple", episodes_dir)
    sw.run_stage(ep, channel, client=FakeAnthropic([tool_response(bad)] * 3))

    data = json.loads(ep.file.read_text())
    assert data["status"] == "drafted"
    assert len(data["scenes"]) == 23 and data["scenes"][0]["n"] == 1
    assert data["scenes"][1]["on_screen"] == "A" and data["scenes"][0]["on_screen"] is None
    assert data["seo"]["title"] == "Letter A for Toddlers | Minsa Kids TV"
    messages = [(n["stage"], n["scene"], n["message"]) for n in data["review_notes"]]
    assert ("script", None, "Claude: Check that the apple looks red.") in messages
    assert ("script", 5, "Unresolved: Scene 5: narration has 30 words; max for 8 s is 16") in messages

    md = (ep.dir / "episode.md").read_text()
    assert md.index("## Review checklist") < md.index("## Scenes") < md.index("## SEO")
    assert "- [ ] Scene 5: Unresolved" in md and "**Veo prompt:**" in md


def test_run_stage_skips_when_drafted(channel, drafted):
    client = FakeAnthropic([])
    sw.run_stage(drafted, channel, client=client)
    assert client.calls == []
