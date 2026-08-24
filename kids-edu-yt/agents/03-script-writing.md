# Agent 03 — Script Writing

## Purpose
Write a complete, production-ready script for one video. Output `script.md` with speaker notes, on-screen text cues, and scene markers.

---

## Input
- `videos/<slug>/topic.json`
- `videos/<slug>/research.json`
- `channel.md` (tone, age range, character notes)

## Output
`videos/<slug>/script.md`

---

## Script Structure (Kids Education Format)

Every video follows this structure. Do not skip sections.

```
1. HOOK          — Song or character intro (0:00–0:30)
2. OBJECTIVE     — State what we're learning today (0:30–0:45)
3. CORE LEARNING — Main content with repetition (0:45–2:30)
4. REINFORCEMENT — Repeat key concept through example/game (2:30–3:30)
5. RECAP         — Review what we learned (3:30–4:00)
6. CTA           — Gentle subscribe/watch-next prompt (4:00–4:15)
```

**Total target length:** 3.5–5 minutes (shorter for 2–3 year olds, up to 5 min for 4–6 year olds)

---

## Language Rules

- Max sentence length: 8 words
- No idioms, metaphors, or abstract concepts
- Use the child's name (or character name) frequently
- Repeat the key concept at least 5 times per video
- Use questions the child can answer aloud ("Can you say...?", "What letter is this?")
- Celebrate effort: "Great job!", "You did it!", "Well done!"

---

## Prompt (paste into Claude or your AI tool)

```
You are a kids' educational video scriptwriter. Target audience: ages 2–6.
Channel tone: warm, gentle, clear, repetitive for learning retention.
Character: [INSERT CHARACTER NAME — e.g. "Zara and Zaid" or TBD]

Topic: [INSERT from topic.json]
Primary keyword: [INSERT from research.json]
Differentiation angle: [INSERT from research.json]

Write a complete video script following this EXACT structure:

1. HOOK (0:00–0:30)
   - Start with a short, catchy song or jingle introducing the topic
   - Character greets the viewer by name ("Hello friends!")
   - 1–2 sentences max, warm and excited

2. LEARNING OBJECTIVE (0:30–0:45)
   - State what the child will learn: "Today we are going to learn about [TOPIC]"
   - Simple, one sentence

3. CORE LEARNING (0:45–2:30)
   - Introduce the concept clearly
   - Show 3–5 examples (words, objects, numbers, etc.)
   - For each example: name it, show it, repeat it, have child say it back
   - Use on-screen text cues [SCREEN: show word in large bold text]

4. REINFORCEMENT (2:30–3:30)
   - A simple activity or game: "Let's count together!", "Can you find the letter?"
   - Repeat the core concept 2–3 more times
   - Encourage the child: "Great job!", "You're so smart!"

5. RECAP (3:30–4:00)
   - "Today we learned about [TOPIC]"
   - Quick review of 2–3 key points
   - End with celebration: clapping, music sting

6. CTA (4:00–4:15)
   - "If you had fun, ask a grown-up to press subscribe!"
   - "Watch our next video about [RELATED TOPIC]"
   - Keep it gentle — this is a Made-for-Kids channel

Script format:
- [NARRATOR]: spoken words
- [SCREEN]: on-screen text or visual cue
- [MUSIC]: music note
- [SFX]: sound effect
- [PAUSE]: deliberate pause for child response

Keep sentences under 8 words. Use the word "[TOPIC WORD]" at least 8 times.
Total script should be 350–500 words spoken (≈ 3.5–5 minutes at a slow, clear pace).
```

---

## Output Template — `script.md`

```markdown
# Script: [VIDEO TITLE]
**Slug:** letter-a  
**Target length:** 4 minutes  
**Word count:** ~400 words  
**Status:** script

---

## HOOK (0:00–0:30)

[MUSIC: Upbeat, simple intro jingle]
[SCREEN: Channel logo + character animation]

[NARRATOR]: Hello friends! It's Zara and Zaid!
[PAUSE: 1 second]
[NARRATOR]: Today we are going to learn something really fun!

---

## LEARNING OBJECTIVE (0:30–0:45)

[SCREEN: Big letter "A" appears]
[NARRATOR]: Today — we are learning about the letter A!
[NARRATOR]: The letter A!
[PAUSE: child responds]

---

## CORE LEARNING (0:45–2:30)

[SCREEN: Letter A with an apple next to it]
[NARRATOR]: A is for Apple!
[NARRATOR]: Can you say it? Apple!
[PAUSE: child responds]
[NARRATOR]: Great job! Apple starts with A.

... (continue for each example)

---

## REINFORCEMENT (2:30–3:30)

[NARRATOR]: Now let's play a game!
[SCREEN: Three pictures — apple, ball, ant]
[NARRATOR]: Which one starts with A?
[PAUSE: 3 seconds]
[NARRATOR]: That's right! Apple and Ant!

---

## RECAP (3:30–4:00)

[NARRATOR]: Today we learned about the letter A!
[NARRATOR]: A is for Apple. A is for Ant. A is for Alligator!
[MUSIC: Celebration sting]
[SCREEN: "A A A" bouncing on screen]

---

## CTA (4:00–4:15)

[NARRATOR]: Did you have fun? Ask a grown-up to press subscribe!
[SCREEN: Subscribe button animation]
[NARRATOR]: See you next time, friends!
[MUSIC: Outro jingle]
```

---

## Quality Checklist

Before marking status as `voice`:
- [ ] Hook is catchy and under 30 seconds
- [ ] Key concept repeated ≥ 5 times
- [ ] All sentences ≤ 8 words
- [ ] Child is invited to respond at least 3 times
- [ ] No copyrighted songs or characters referenced
- [ ] CTA is gentle and appropriate for Made-for-Kids
- [ ] Script includes all 6 sections
