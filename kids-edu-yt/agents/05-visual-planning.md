# Agent 05 — Visual Planning

## Purpose
Plan every scene: scene-by-scene table, b-roll list, AI image/video prompts, and edit plan. Output `visuals.json`.

---

## Input
- `videos/<slug>/script.md`
- `videos/<slug>/voice.json` (for timing)
- `channel.md` (character design, visual style)

## Output
`videos/<slug>/visuals.json`

---

## Visual Design Principles

- **Colours:** High-contrast primary/secondary palette. Never dark or muted.
- **Shapes:** Simple, rounded, child-friendly. No sharp angles on characters.
- **On-screen text:** Matches spoken word exactly. Large, bold, easy font (e.g. Nunito, Fredoka One, Baloo).
- **Character consistency:** Same character design, same colours across ALL episodes.
- **Background:** Clean, uncluttered. Max 2–3 elements per scene.
- **Motion:** Gentle, predictable. No sudden cuts or jarring transitions. Fade/dissolve preferred.
- **One concept per frame:** Never overload a single scene with multiple new things.

---

## Scene Table Format

| # | Timecode | Script line | Visual description | On-screen text | Motion notes |
|---|----------|-------------|-------------------|----------------|--------------|
| 1 | 0:00–0:08 | "Hello friends! It's Zara and Zaid!" | Character wave animation, bright background | "Hello!" in large font | Bounce in from bottom |

---

## Prompt (paste into Claude or your AI tool)

```
You are a kids' educational video visual director. Target audience: ages 2–6.
Visual style: bright colours, simple shapes, consistent character design, on-screen text matches spoken words.

Here is the full script: [PASTE script.md]
Estimated total duration: [X] minutes

For each section of the script (HOOK, OBJECTIVE, CORE LEARNING, REINFORCEMENT, RECAP, CTA):

1. Create a scene table with columns:
   Scene # | Timecode | Script line | Visual description | On-screen text | Motion/transition notes

2. For each scene needing AI-generated imagery (Veo / Stable Diffusion / Ideogram / DALL-E), write a detailed prompt:
   - Style: [cartoon, 2D animation, bright, child-friendly, simple background]
   - Subject: [exact description]
   - Colours: [specific palette]
   - Mood: [warm, cheerful, educational]
   - What NOT to include: [no dark themes, no scary elements, no clutter]

3. List all b-roll needs:
   - Static illustrations needed (objects that match vocabulary words)
   - Character animation states needed (waving, pointing, clapping, excited)
   - Text animations needed (letter bounce, number count-up, word reveal)

4. Write an edit plan:
   - Scene order
   - Transition type between each scene (cut / fade / slide)
   - Music timing cues
   - Text animation timing

Output as JSON.
```

---

## AI Visual Prompt Examples

### For a letter episode (Letter A)
```
Style: Bright 2D cartoon illustration, flat design, child-friendly, no shadows, thick outlines
Subject: A large, friendly red apple with a smiling face, sitting on a green leaf
Background: Clean white with soft blue sky gradient
Text overlay area: Top 20% of frame (reserved for on-screen text)
Mood: Cheerful, warm, educational
Avoid: Realistic textures, dark colours, scary elements, clutter, adult imagery
Reference style: Similar to Sesame Street illustration style
```

### For a number episode (Counting 1–5)
```
Style: Bright 2D cartoon, flat design, thick outlines, bold colours
Subject: 3 yellow rubber ducks in a row on blue water, each duck has a simple smiley face
Numbers: Bold white number "3" in bottom-right corner with colourful outline
Background: Light blue water, simple white clouds
Mood: Playful, counting game, fun
Avoid: Realistic rendering, complex backgrounds, more than one concept per frame
```

---

## Output Template — `visuals.json`

```json
{
  "slug": "letter-a",
  "total_scenes": 18,
  "visual_style": {
    "colour_palette": ["#FF4D4D", "#FFD700", "#4CAF50", "#2196F3", "#FF9800"],
    "font": "Fredoka One",
    "character_design": "TBD — awaiting Ahsan's decision on Zara/Zaid design",
    "animation_style": "2D flat cartoon, bright, simple"
  },
  "scenes": [
    {
      "scene_number": 1,
      "timecode": "0:00–0:08",
      "script_line": "Hello friends! It's Zara and Zaid!",
      "visual_description": "Characters wave from centre of screen, bright background with stars",
      "on_screen_text": "Hello Friends!",
      "motion": "Characters bounce in from bottom, text fades in from top",
      "transition_to_next": "fade",
      "ai_prompt": "Style: Bright 2D cartoon flat design, child-friendly, thick outlines. Two friendly child characters (boy and girl, simple rounded features) waving at the camera. Background: Bright yellow gradient with colourful stars. Mood: Exciting, welcoming. Avoid: Realistic textures, dark colours, adult imagery."
    }
  ],
  "broll_list": [
    { "item": "Apple illustration", "used_in_scenes": [4, 5, 14], "ai_prompt": "..." },
    { "item": "Ant illustration", "used_in_scenes": [6, 7, 14], "ai_prompt": "..." }
  ],
  "text_animations": [
    { "text": "A", "animation": "bounce in, scale 50%→100%", "timecode": "0:45" },
    { "text": "Apple", "animation": "slide in from right", "timecode": "1:10" }
  ],
  "edit_plan": {
    "software_suggestion": "CapCut / DaVinci Resolve / Adobe Premiere",
    "total_clips": 18,
    "transition_default": "fade 0.3s",
    "music_track": "royalty-free upbeat children's background music",
    "music_timing": "full volume at HOOK and OUTRO, -6dB under narration"
  },
  "veo_flow_notes": "Reuse Qasas ul Ambiya Veo pipeline if character style is compatible. Otherwise commission new 2D assets matching spec above.",
  "status": "visuals",
  "approved": false
}
```

---

## Visual Checklist

- [ ] Every script line has a corresponding visual description
- [ ] On-screen text matches spoken words exactly at each scene
- [ ] All AI image prompts are written and ready to run
- [ ] Character design is consistent across all scenes
- [ ] No copyrighted characters or imagery referenced
- [ ] Edit plan includes all timing cues
- [ ] Human approval before sending to production
