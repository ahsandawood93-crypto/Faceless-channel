# Agent 07 — Upload Preparation

## Purpose
Prepare everything needed for YouTube upload: title, description, chapters, tags, pinned comment draft, playlist assignment. Output `upload.json`. **Does NOT upload — that is a manual human step.**

---

## Input
- `videos/<slug>/topic.json`
- `videos/<slug>/research.json`
- `videos/<slug>/script.md`
- `videos/<slug>/thumbnail.json`
- `channel.md`

## Output
`videos/<slug>/upload.json`

---

## ⚠️ MADE FOR KIDS NOTICE

This channel is designated **"Made for Kids"** under YouTube's COPPA settings. This means:
- **Comments are disabled** — no pinned comment will appear
- **Personalized ads are disabled** — CPMs will be lower
- **Certain YouTube features are disabled** (end screens behaviour may differ, cards restricted)
- **You MUST select "Yes — this video is made for kids"** in YouTube Studio when uploading
- Do not collect personal data from viewers
- Review YouTube's Made for Kids policies before each upload: [https://support.google.com/youtube/answer/9527654](https://support.google.com/youtube/answer/9527654)

---

## Prompt (paste into Claude or your AI tool)

```
You are a YouTube SEO specialist for a kids' educational channel (ages 2–6, Made for Kids).

Topic: [INSERT from topic.json]
Primary keyword: [INSERT from research.json]
Secondary keywords: [INSERT from research.json]
Script summary: [PASTE 2–3 sentences describing the video content]
Video duration: [INSERT from voice.json]

Generate:

1. TITLE (max 60 characters)
   - Lead with the primary keyword
   - Add a benefit or hook
   - Example: "Letter A for Kids | Apple, Ant & Alligator | ABC Song"

2. DESCRIPTION (400–600 words)
   - First 2 lines: must include primary keyword (visible before "Show more")
   - Paragraph 1: What the video teaches (for parents scanning)
   - Paragraph 2: How the video is structured
   - Paragraph 3: Series context (this is Episode X of the Alphabet/Numbers/STEM series)
   - List: All words/concepts covered in this video
   - Playlist links: [placeholder — fill after creating playlists]
   - Subscribe CTA
   - Legal notice: "This video is designated Made for Kids."
   - AI disclosure: "This video was created with AI assistance for [script/visuals/voice — specify which]."

3. CHAPTERS (if video > 2 min)
   - 0:00 Introduction
   - 0:30 Learning [concept]
   - [Add timestamps for each section]

4. TAGS (15–20)
   - Mix: exact match keywords, broad category tags, series tags
   - Example: "letter a for kids", "abc song", "phonics for toddlers", "kids education", "alphabet learning"

5. PLAYLIST ASSIGNMENT
   - Which playlist does this video belong to? (Alphabet Series / Numbers Series / STEM Series)

6. END SCREEN plan (what to show in final 20 seconds)
   - Recommended next video
   - Subscribe button

Note: Comments are disabled (Made for Kids). Skip pinned comment.
Output as JSON.
```

---

## Output Template — `upload.json`

```json
{
  "slug": "letter-a",
  "made_for_kids": true,
  "coppa_note": "MUST select 'Yes — Made for Kids' in YouTube Studio. Comments disabled. Personalized ads disabled.",
  "ai_disclosure_note": "Disclose AI use in description per current YouTube policy. Check youtube.com/howyoutubeworks/policies/ai-generated-content/ for current requirements.",
  "title": "Letter A for Kids | Apple, Ant & Alligator | ABC Learning",
  "title_character_count": 56,
  "description": "Learn the Letter A with Zara and Zaid! 🍎 In this fun video, your child will learn the letter A sound and discover words that start with A — Apple, Ant, and Alligator!\n\nPerfect for toddlers and preschoolers ages 2–6. This video uses repetition, songs, and bright visuals to help early learners recognise the letter A and its sound.\n\n📚 What you'll learn:\n• The letter A (uppercase and lowercase)\n• The A sound (/æ/ as in Apple)\n• Words: Apple, Ant, Alligator\n• A simple letter A song\n\n🔤 This is Episode 1 of our Alphabet Series — one letter per video, A to Z!\n\n👉 Watch the full Alphabet Series: [PLAYLIST LINK]\n👉 Subscribe for new videos every week: [CHANNEL LINK]\n\n---\nThis video is designated Made for Kids.\nThis video was created with AI assistance for script writing and visual planning.",
  "chapters": [
    { "timecode": "0:00", "title": "Hello & Introduction" },
    { "timecode": "0:30", "title": "The Letter A" },
    { "timecode": "0:45", "title": "A is for Apple" },
    { "timecode": "1:10", "title": "A is for Ant" },
    { "timecode": "1:35", "title": "A is for Alligator" },
    { "timecode": "2:30", "title": "Letter A Game" },
    { "timecode": "3:30", "title": "Recap & Goodbye" }
  ],
  "tags": [
    "letter a for kids",
    "letter a",
    "abc song",
    "alphabet for toddlers",
    "phonics for kids",
    "learn letter a",
    "kids education",
    "preschool learning",
    "toddler learning videos",
    "abc learning",
    "alphabet song",
    "letter a song",
    "early childhood education",
    "educational videos for kids",
    "kids youtube"
  ],
  "playlist": "Alphabet Series — A to Z",
  "end_screen": {
    "next_video": "Letter B video",
    "subscribe_button": true
  },
  "thumbnail_file": "thumbnail-concept-1-final.png",
  "category": "Education",
  "language": "English",
  "upload_checklist": [
    "Final video file exported and named: letter-a-FINAL.mp4",
    "Thumbnail file ready: thumbnail-final.png",
    "Title confirmed (under 60 chars)",
    "Description pasted and links filled in",
    "Chapters added",
    "Tags added (15–20)",
    "Category: Education",
    "Made for Kids: YES selected",
    "Playlist assigned",
    "AI disclosure in description",
    "Human review and approval complete"
  ],
  "status": "ready_to_upload",
  "upload_date": null,
  "published_url": null,
  "approved_by": null,
  "approved_date": null
}
```

---

## Upload Checklist (Human Gate)

**Do not upload until all items are checked by a human:**

- [ ] Video file reviewed end-to-end
- [ ] Audio quality confirmed (no clipping, voice clear)
- [ ] Visuals reviewed (no errors, consistent style)
- [ ] Title, description, tags reviewed
- [ ] Made for Kids setting confirmed: **YES**
- [ ] AI disclosure present in description
- [ ] Thumbnail selected and uploaded
- [ ] No copyrighted content in video or audio
- [ ] Playlist assigned
- [ ] Ahsan has given explicit upload approval

---

## Policy Reminders

Check these before every publish cycle:
- YouTube Made for Kids: https://support.google.com/youtube/answer/9527654
- COPPA guidance: https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions
- YouTube AI content policy: https://support.google.com/youtube/answer/14328491
- YouTube monetization policies (kids content): https://support.google.com/youtube/answer/9383587
