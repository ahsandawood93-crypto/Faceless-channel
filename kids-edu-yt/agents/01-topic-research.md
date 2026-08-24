# Agent 01 — Niche & Topic Research

## Purpose
Score and rank topic ideas for the kids-edu-yt channel. Output a `topic.json` for each approved idea.

---

## Input
- Raw topic idea (e.g. "Letter A", "Counting 1–5", "What is a shadow?")
- `channel.md` for context on age range, tone, and pillars

## Output
`videos/<slug>/topic.json`

---

## Scoring Rubric (score each 1–10, then average)

| Criterion | What to assess |
|-----------|---------------|
| **Age-appropriateness** | Is this genuinely understandable by a 2–6 year old? Simple concept, concrete, no abstraction |
| **Learning value** | Does watching this episode teach one clear, measurable thing? |
| **Repeat-watchability** | Will kids want to watch this 10+ times? (songs, characters, rhythm help) |
| **Search demand** | Do parents actively search for this? (use YouTube search suggest + keyword tools) |
| **Competition** | How saturated is this keyword/topic? Lower competition = easier to rank early |

**Composite score = average of 5 criteria**  
**Threshold:** Score ≥ 7.0 to proceed to production.

---

## Prompt (paste into Claude or your AI tool)

```
You are a kids' educational YouTube channel strategist. I am building a channel targeting ages 2–6.
Content pillars: Alphabet (A-Z), Numbers (1-20+), STEM basics, Shapes & Colors.

Evaluate this topic idea: [INSERT TOPIC]

Score it on:
1. Age-appropriateness (1-10): Is it understandable by a 2–6 year old?
2. Learning value (1-10): Does it teach one clear concept?
3. Repeat-watchability (1-10): Will kids want to rewatch it?
4. Search demand (1-10): Do parents search for this on YouTube?
5. Competition (1-10, where 10 = low competition): How saturated is this?

For each score, give a one-sentence rationale.
Calculate the composite average.
If composite ≥ 7.0, recommend proceeding. If < 7.0, suggest a modification or alternative.
Also suggest 3 related topic ideas in the same pillar.

Output as JSON.
```

---

## Output Template — `topic.json`

```json
{
  "slug": "letter-a",
  "title": "Letter A — Apple, Ant, Alligator",
  "pillar": "alphabet",
  "episode_number": 1,
  "concept": "The letter A, its sound, and 3–5 words that start with A",
  "target_age": "2-6",
  "scores": {
    "age_appropriateness": 9,
    "learning_value": 9,
    "repeat_watchability": 8,
    "search_demand": 9,
    "competition": 5
  },
  "composite_score": 8.0,
  "proceed": true,
  "rationale": "Letter A is the entry point of any alphabet series. High parental search demand. Competitive but essential — differentiate with character and song.",
  "related_topics": [
    "Letter B — Ball, Bear, Butterfly",
    "Letter A Song — Phonics for Toddlers",
    "Short A vs Long A Sound"
  ],
  "notes": "",
  "created_date": "YYYY-MM-DD",
  "status": "idea"
}
```

---

## Batch Scoring

To evaluate 5+ topics at once, paste this prompt:

```
Score the following topic ideas for a kids' educational YouTube channel (ages 2–6).
Pillars: Alphabet, Numbers, STEM, Shapes.

Topics:
1. Letter A
2. Counting 1–5
3. What is a shadow?
4. Letter B
5. Shapes: Circle, Square, Triangle

For each, provide: composite score (avg of 5 criteria), one-line rationale, proceed yes/no.
Rank them best-to-worst. Output as a ranked JSON array.
```

---

## Status Values (used across all agents)
`idea` → `research` → `script` → `voice` → `visuals` → `thumbnail` → `ready_to_upload` → `published`
