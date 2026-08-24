# Agent 04 — Voice Production

## Purpose
Generate voice direction notes, select TTS settings, and produce (or commission) the final audio. Output `voice.json` with all parameters needed for the voice artist or TTS system.

---

## Input
- `videos/<slug>/script.md`
- `channel.md` (tone, character)

## Output
`videos/<slug>/voice.json`

---

## Voice Direction Principles

- **Pace:** Slightly slower than normal speech — about 130–150 words per minute (vs. 160–180 wpm normal)
- **Clarity:** Over-enunciate consonants; pause slightly between words when introducing new vocabulary
- **Warmth:** Smile while recording — it changes the voice quality
- **Enthusiasm:** Energetic but not hyperactive; think "favourite teacher" not "circus announcer"
- **Pauses:** Honour every [PAUSE] marker in the script — these are real wait times for child response (1–3 seconds each)
- **Repetition:** The second and third time a word is said, slow down slightly and emphasise it
- **Character consistency:** If using Zara vs Zaid voice, keep them distinct across all episodes

---

## TTS Settings (ElevenLabs example)

If using ElevenLabs or similar TTS:

| Setting | Recommended Value |
|---------|------------------|
| Voice model | Multilingual v2 or Turbo v2.5 |
| Voice style | Calm, warm, child-friendly (test "Rachel", "Aria", or a custom voice) |
| Stability | 0.75 (reduces variability for consistent character) |
| Similarity boost | 0.80 |
| Speaking rate | 0.85 (slightly slower than default) |
| Pause injection | Add `<break time="1.5s"/>` at every [PAUSE] marker |

---

## Prompt (paste into Claude or your AI tool)

```
I need voice production direction for a kids' educational video. Target audience: ages 2–6.

Here is the script: [PASTE script.md content]

Please:
1. Identify every [PAUSE] marker and note the recommended pause duration (1s, 2s, or 3s)
2. Identify words that should be emphasised (spoken slowly/clearly) — the key learning words
3. Suggest where music/SFX should be slightly lowered so voice is clear
4. For TTS: rewrite the script with SSML tags for:
   - <break time="Xs"/> at each pause
   - <emphasis level="strong"> on key vocabulary
   - <prosody rate="slow"> for repeated reinforcement phrases
5. Generate a voice brief (1 paragraph) describing the character's voice for a human voice artist

Also flag any lines that might be hard to say clearly or that children might misunderstand.
```

---

## Output Template — `voice.json`

```json
{
  "slug": "letter-a",
  "voice_brief": "Warm, clear, slightly slow-paced narrator. Think 'favourite nursery teacher' energy — enthusiastic but calm, never frantic. Smile while recording. Over-enunciate consonants, especially on first introduction of each vocabulary word. Honour every pause marker — these are real wait times (1–3 seconds) for the child at home to respond.",
  "characters": [
    {
      "name": "Narrator / Zara",
      "voice_style": "Female, warm, 28-35, primary storyteller",
      "tts_voice_id": "ElevenLabs_voice_id_here",
      "ssml_defaults": {
        "rate": "0.85",
        "stability": "0.75",
        "similarity_boost": "0.80"
      }
    }
  ],
  "emphasis_words": ["Apple", "Ant", "Alligator", "Letter A"],
  "pause_map": [
    { "marker": "[PAUSE]", "after_line": "Can you say it? Apple!", "duration_sec": 2 },
    { "marker": "[PAUSE]", "after_line": "Which one starts with A?", "duration_sec": 3 }
  ],
  "music_notes": "Lower background music by 6dB whenever narrator speaks. Full volume only during HOOK and OUTRO jingles.",
  "total_spoken_words": 410,
  "estimated_duration_min": 4.2,
  "tts_provider": "ElevenLabs",
  "ssml_script_file": "voice-ssml.xml",
  "audio_export_format": "WAV 44.1kHz 16-bit",
  "status": "voice",
  "production_notes": "",
  "approved": false
}
```

---

## Audio File Checklist

- [ ] All [PAUSE] markers respected — listen through and confirm dead air at each
- [ ] Key vocabulary words emphasised and slightly slower
- [ ] Background music ducked under voice by at least 6dB
- [ ] No clipping or distortion
- [ ] Exported as WAV (master) + MP3 320kbps (delivery)
- [ ] File named: `<slug>-voice-master.wav`
- [ ] Human approval before combining with visuals
