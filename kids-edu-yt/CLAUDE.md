# Kids Educational YouTube Channel — AI Orchestrator

**Channel:** kids-edu-yt  
**Niche:** Alphabet · Numbers · STEM Basics  
**Target Age:** 2–6 years  
**Tone:** Warm, simple, repetitive-for-learning  

---

## Pipeline Overview

Each video moves through these stages in order. Every stage reads the previous file and writes its own.

```
topic.json → research.json → script.md → voice.json → visuals.json → thumbnail.json → upload.json
```

All video files live in `videos/<slug>/`.

---

## Stages & Agents

| Stage | File | Agent Prompt File |
|-------|------|-------------------|
| 1. Idea | `topic.json` | `agents/01-topic-research.md` |
| 2. Research | `research.json` | `agents/02-trend-research.md` |
| 3. Script | `script.md` | `agents/03-script-writing.md` |
| 4. Voice | `voice.json` | `agents/04-voice-production.md` |
| 5. Visuals | `visuals.json` | `agents/05-visual-planning.md` |
| 6. Thumbnail | `thumbnail.json` | `agents/06-thumbnail-creation.md` |
| 7. Upload Prep | `upload.json` | `agents/07-upload-prep.md` |
| 8. Analytics | *(post-publish)* | `agents/08-analytics-review.md` |

---

## How to Run a Video

### Step 1 — Create a topic
Create `videos/<slug>/topic.json` by hand or run the Topic Research agent.

```bash
# Example slug: letter-a
mkdir -p videos/letter-a
```

Populate `videos/letter-a/topic.json` (see template in `agents/01-topic-research.md`).

### Step 2 — Run each agent in sequence
Open each agent prompt in `agents/` and follow the instructions. Each agent tells you exactly what to read and what to write.

```
Agent 01 → writes research.json
Agent 02 → writes trend data into research.json (or a separate trends block)
Agent 03 → writes script.md
Agent 04 → writes voice.json
Agent 05 → writes visuals.json
Agent 06 → writes thumbnail.json
Agent 07 → writes upload.json
```

### Step 3 — Check dashboard
Open `dashboard/index.html` in a browser to see all videos and their current stage.

### Step 4 — Human approval gate
**STOP before any of these without explicit approval:**
- Uploading to YouTube
- Publishing, scheduling, or making anything public
- Posting comments or community posts
- Spending money / triggering paid API calls beyond your budget
- Changing channel settings

---

## Keys & Environment

All API keys live in `.env`. Never commit `.env` to git. See `.env.example` for required keys.

```bash
cp .env.example .env
# Then fill in your keys
```

---

## Legal & Compliance Reminders

- **COPPA / Made for Kids:** This channel will likely be designated "Made for Kids" on YouTube. This disables personalized ads, comments, and certain features. CPMs are lower than standard channels. Flag `made_for_kids: true` in every `upload.json`.
- **YouTube Policies:** Policies, COPPA rules, content restrictions, and AI-content disclosure requirements change frequently. Check YouTube's official policy pages before every publish cycle.
- **Copyright:** All music, characters, and visuals must be original or properly licensed. Never use copyrighted songs, characters, or imagery without permission.
- **AI Disclosure:** YouTube requires disclosure when AI is materially involved in creating realistic content. Review the current policy and add disclosure where required.
- **No Guarantees:** This system prepares content. It does not guarantee views, subscribers, revenue, or monetization. Kids-content CPMs under Made-for-Kids restrictions are typically lower than general-audience content.

---

## Dashboard

Open `dashboard/index.html` locally in any browser. Update video status in each video's `upload.json` (`status` field) — the dashboard reads from a `videos-manifest.json` you maintain.

---

## First Run

When you have 5 topic ideas, paste them here or into the Topic Research agent. Good starter ideas:
- "Letter A"
- "Counting 1–5"
- "What is a shadow?"
- "Letter B"
- "Shapes: Circle, Square, Triangle"
