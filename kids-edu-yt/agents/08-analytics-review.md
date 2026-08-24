# Agent 08 — Analytics & Performance Review

## Purpose
After a video has been published for 7, 30, and 90 days, review its performance and generate insights to improve future videos. This agent runs post-publish only.

---

## Input
- `videos/<slug>/upload.json` (must have `published_url` filled in)
- YouTube Studio analytics data (manually exported or via YouTube Data API v3 read-only)

## Output
Append to `videos/<slug>/upload.json` under an `analytics` block, or create a separate `analytics-<date>.json`.

---

## ⚠️ Made for Kids Analytics Limitations

Under Made-for-Kids designation:
- **Audience demographics are not available** (COPPA restriction)
- **Comments and likes data is limited**
- **Some analytics metrics are unavailable or aggregated only**
- You will primarily rely on: Views, Watch Time, Average View Duration, CTR (if available), Traffic Sources

---

## Metrics to Collect (from YouTube Studio)

| Metric | What it tells you |
|--------|------------------|
| Views (7d / 30d / 90d) | Absolute reach |
| Watch time (minutes) | Total engagement |
| Average view duration | Are kids watching through? |
| Average percentage viewed | % of video watched on average |
| CTR (click-through rate) | Thumbnail effectiveness (4–8% is healthy) |
| Impressions | How often YouTube surfaced the video |
| Traffic sources | How viewers found the video (Search, Browse, Suggested) |
| Top search terms that led here | SEO effectiveness |

---

## Prompt (paste into Claude or your AI tool)

```
You are a YouTube analytics consultant for a kids' educational channel (Made for Kids, ages 2–6).

Here is the performance data for video: [TITLE]
Published: [DATE]

7-day data:
- Views: [X]
- Watch time: [X] minutes
- Average view duration: [X:XX] ([X]%)
- CTR: [X]% (if available)
- Impressions: [X]
- Top traffic sources: [search / browse / suggested / external]

30-day data: [same fields]

Benchmarks for reference (kids educational, small new channel):
- CTR: 4–8% is healthy
- Average view duration: 40%+ is good for toddler content (kids rewatch)
- Traffic source mix goal: 30%+ from search (shows SEO is working)

Questions to answer:
1. Is this video performing above, at, or below expectations for a new kids channel?
2. What does the watch duration tell us about content quality? (Where are they dropping off?)
3. Is the thumbnail working (CTR)?
4. What traffic source is driving most views — and is that sustainable?
5. Top 3 actionable recommendations for the NEXT video in this series based on this data
6. Should we create a follow-up video on this exact topic? (Is there search demand evidence here?)

Also review:
- Does the title/keyword match what search traffic is coming from?
- Are there search terms showing up that we should target in future videos?

Output as a structured review with clear action items.
```

---

## Output Template — `analytics-review.json`

```json
{
  "slug": "letter-a",
  "published_date": "YYYY-MM-DD",
  "review_date": "YYYY-MM-DD",
  "review_period_days": 30,
  "data": {
    "views": 1240,
    "watch_time_minutes": 3800,
    "avg_view_duration_sec": 184,
    "avg_percentage_viewed": 73,
    "ctr_percent": 5.2,
    "impressions": 23800,
    "top_traffic_sources": {
      "youtube_search": "42%",
      "browse_features": "31%",
      "suggested_videos": "18%",
      "external": "9%"
    },
    "top_search_terms": [
      "letter a for kids",
      "letter a song toddlers",
      "abc letter a"
    ]
  },
  "ai_review": {
    "overall_verdict": "Above expectations for a new channel. 73% average view duration is strong for toddler content.",
    "thumbnail_verdict": "5.2% CTR is healthy — thumbnail is working.",
    "seo_verdict": "42% search traffic confirms keyword targeting is effective.",
    "top_recommendations": [
      "Publish Letter B within 7 days to capitalise on momentum",
      "Test a 'Letter A Song' standalone video targeting that specific keyword",
      "The drop-off at 2:30 (reinforcement section) suggests the game segment needs more energy"
    ],
    "follow_up_video_recommended": true,
    "follow_up_idea": "Letter A Song — standalone phonics song targeting 'letter a song for kids'"
  },
  "notes": ""
}
```

---

## Review Schedule

| Period | When to review | Key question |
|--------|---------------|--------------|
| 7 days | 1 week after publish | Is YouTube surfacing it? Is CTR healthy? |
| 30 days | 1 month after publish | Is search traffic growing? Watch duration stable? |
| 90 days | 3 months after publish | Long-tail performance — is it becoming evergreen? |

---

## Channel-Level Review (Monthly)

Once you have 5+ videos published, run a monthly channel review:

```
Review all videos published this month. Compare:
- Which videos have highest CTR? (thumbnail winner)
- Which videos have highest avg view duration? (content quality winner)
- Which videos have most search traffic? (SEO winner)
- Any topic cluster that's outperforming? (double down on it)
- Any topic that underperformed? (understand why before making more like it)

Generate a top-3 priority list for next month's production.
```
