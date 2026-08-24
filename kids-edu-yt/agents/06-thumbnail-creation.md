# Agent 06 — Thumbnail Creation

## Purpose
Generate 10 thumbnail concepts. Select the best one for production. Output `thumbnail.json` with prompts, design specs, and the chosen concept.

---

## Input
- `videos/<slug>/topic.json`
- `videos/<slug>/research.json` (primary keyword)
- `channel.md` (visual style, character)

## Output
`videos/<slug>/thumbnail.json`

---

## Kids Educational Thumbnail Principles

- **One clear concept:** The letter, number, or STEM concept must be unmistakable at glance
- **High contrast:** Bright background + dark text, or vice versa. Never muted colours.
- **Large central element:** Letter, number, or main object fills 40–60% of the frame
- **Friendly face:** Character face in corner or centre — smiling, expressive, pointing at concept
- **Minimal text:** Young viewers may not read; parents scan — keep text to 2–3 words MAX
- **No clutter:** Maximum 3 elements on screen (character + concept + background)
- **1280×720 pixels** (YouTube standard thumbnail size)
- **Consistent style:** Same font, same character, same framing style across all episodes in a series

---

## Prompt (paste into Claude or your AI tool)

```
You are a YouTube thumbnail designer for a kids' educational channel targeting ages 2–6.
Parent audience scans thumbnails on mobile — design must work at 320px wide.
Channel visual style: bright, high-contrast, simple, consistent character.

Topic: [INSERT from topic.json]
Primary keyword: [INSERT from research.json]
Character: [Zara/Zaid or TBD]

Generate 10 thumbnail concepts. For each concept provide:
1. Layout description (what's where on the 1280×720 canvas)
2. Colour scheme (background + accent colours — use specific hex codes)
3. Text (2–3 words max, font style)
4. Character pose (if included)
5. Main visual element (the letter, number, or concept object)
6. Why this would perform well for this audience

Then rank the 10 concepts from best to worst based on:
- Clarity (is the concept instantly understood?)
- Visual appeal for kids (bright, friendly, exciting?)
- Parent click-worthiness (does it look like quality educational content?)
- Thumbnail test: Would this stand out next to 8 similar thumbnails on a mobile screen?

Provide the top 3 in full AI image generation prompts (Midjourney / DALL-E / Ideogram style).
Output as JSON.
```

---

## Output Template — `thumbnail.json`

```json
{
  "slug": "letter-a",
  "video_title": "Letter A — Apple, Ant, Alligator",
  "primary_keyword": "letter a for kids",
  "canvas_size": "1280x720",
  "chosen_concept": 1,
  "concepts": [
    {
      "concept_number": 1,
      "rank": 1,
      "layout": "Giant red letter 'A' centred-left (60% height). Friendly character (Zara) pointing at the A from right side. Three small icons (apple, ant, alligator) floating around the A.",
      "background": "#FFF9C4 (warm yellow)",
      "text": "Letter A",
      "text_font": "Fredoka One Bold",
      "text_colour": "#FFFFFF with #D32F2F outline",
      "text_position": "Bottom-left, large",
      "colour_scheme": {
        "background": "#FFF9C4",
        "accent_1": "#FF4D4D",
        "accent_2": "#4CAF50",
        "text": "#FFFFFF"
      },
      "character_pose": "Pointing at letter A, excited expression, looking at camera",
      "main_element": "Large red letter 'A' with apple texture",
      "why_it_works": "Instant letter recognition, warm colours, character engagement, clear minimal text",
      "ai_image_prompt": "Thumbnail design for kids YouTube video. 1280x720px. Style: bright 2D cartoon flat design, bold outlines. Centre: large bold red letter 'A' (takes up 50% of canvas). Right side: friendly cartoon child character (girl, simple rounded features, warm skin tone) pointing excitedly at the letter A. Small cartoon apple, ant, and alligator floating around the letter. Background: soft warm yellow (#FFF9C4). Text 'Letter A' in white Fredoka One font with red outline, bottom-left. Mood: educational, cheerful, age 2-6. Avoid: clutter, dark colours, text beyond 'Letter A', realistic imagery."
    }
  ],
  "series_consistency_notes": "All alphabet episode thumbnails use same layout: letter colour matches pillar colour (red for A, blue for B, etc.), same character pose (pointing), same font and position for text",
  "production_tool": "Canva / Photoshop / Ideogram AI",
  "status": "thumbnail",
  "approved": false
}
```

---

## Thumbnail A/B Testing Note

Once the channel reaches sufficient views, test two thumbnail variants per video using YouTube's built-in A/B test (YouTube Studio → Customization → Thumbnail test). Track CTR (click-through rate) — a healthy CTR for kids content is 4–8%.

---

## Thumbnail Checklist

- [ ] 10 concepts generated and ranked
- [ ] Concept 1 selected and AI prompt written
- [ ] Canvas is 1280×720 pixels
- [ ] Text is max 3 words
- [ ] High contrast — readable at 320px width
- [ ] Character face is friendly and expressive
- [ ] No copyrighted characters or logos
- [ ] Consistent with series style guide
- [ ] Human approval before using as thumbnail
