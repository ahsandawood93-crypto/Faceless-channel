# Agent 02 — Trend Research

## Purpose
Scan what parents and kids are actively searching. Score and shortlist keywords. Enrich `research.json` with search demand data, competitor analysis, and a differentiation angle.

---

## Input
- `videos/<slug>/topic.json` (from Agent 01)
- YouTube Data API (read-only) or manual YouTube search
- Google Trends / Serper search data

## Output
`videos/<slug>/research.json`

---

## Three-Phase Process: Scan → Score → Shortlist

### Phase 1 — SCAN
Search YouTube and Google for variations of the topic keyword. Collect:
- Top 10 YouTube videos for the main keyword (title, views, channel, age of video)
- Related search suggestions (YouTube autocomplete)
- Google Trends 12-month interest data

### Phase 2 — SCORE
Score each keyword variation on:
| Criterion | Score 1–10 |
|-----------|------------|
| Search volume (estimated) | 10 = very high |
| Competition (fewer big channels = higher score) | 10 = low competition |
| Relevance to our pillars | 10 = perfect fit |
| Parent intent match | 10 = clearly what parents search |

### Phase 3 — SHORTLIST
Select the primary keyword + 2–3 secondary keywords to target.

---

## Prompt (paste into Claude or your AI tool)

```
You are a YouTube SEO researcher specializing in kids' educational content (ages 2–6).

Topic: [INSERT TOPIC — e.g. "Letter A for kids"]

Tasks:
1. Generate 10 keyword variations parents might search on YouTube for this topic.
   (e.g. "letter a song", "letter a for toddlers", "abc letter a", "phonics letter a", "learn letter a")

2. For each keyword, estimate:
   - Search volume (high/medium/low based on YouTube suggest patterns)
   - Competition level (high/medium/low — are there many large channels dominating?)
   - Parent intent (is this what a parent would type when looking for educational content for their 2-6 year old?)

3. Identify the top 3 competitor videos for the primary keyword:
   - Title, estimated views (if known), what makes them strong
   - What gap exists that a new channel could fill?

4. Recommend:
   - Primary keyword (best balance of demand + competition)
   - 2 secondary keywords
   - One differentiation angle (what would make our video better or different?)

Output as JSON.
```

---

## Output Template — `research.json`

```json
{
  "slug": "letter-a",
  "topic_title": "Letter A — Apple, Ant, Alligator",
  "primary_keyword": "letter a for kids",
  "secondary_keywords": [
    "letter a song for toddlers",
    "learn letter a abc"
  ],
  "keyword_variations": [
    {
      "keyword": "letter a for kids",
      "search_volume": "high",
      "competition": "high",
      "parent_intent": "high"
    },
    {
      "keyword": "letter a song toddlers",
      "search_volume": "medium",
      "competition": "medium",
      "parent_intent": "high"
    }
  ],
  "competitor_analysis": [
    {
      "title": "The Letter A Song — Have Fun Teaching",
      "estimated_views": "50M+",
      "strengths": "Simple animation, clear phonics, repetitive song",
      "gap": "Generic characters; no narrative story around the letter"
    }
  ],
  "differentiation_angle": "Use a consistent character (Zara/Zaid) who 'discovers' each letter through a mini-adventure, adding story hooks that drive rewatch",
  "trending_searches": [
    "letter a song",
    "phonics for toddlers letter a",
    "abc song letter a"
  ],
  "google_trends_note": "Steady year-round interest; slight peaks in August-September (back to school) and January",
  "research_date": "YYYY-MM-DD",
  "status": "research"
}
```

---

## Manual Research Shortcuts (no API needed)

1. Open YouTube, search your topic, note the top 5 video titles and approximate view counts
2. Use YouTube autocomplete: type the keyword and note all suggestions
3. Check Google Trends (trends.google.com) for 12-month interest
4. Note which channels dominate — are they large established brands or small creators?
