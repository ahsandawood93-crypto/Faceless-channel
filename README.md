# Minsa Kids TV Autopilot

Turns one topic line into a finished, scheduled YouTube Kids episode for
**Minsa Kids TV** (English, ages 2–6, original characters Minsa and Mana).
Nothing goes public without your approval.

```
topic → 1 Script (Claude) → 2 Voiceover (ElevenLabs) → 3 Clips (Veo 3.1)
      → 4 Assembly (ffmpeg) → 5 Approval (Telegram) → 6 Upload & schedule (YouTube)
```

> **Build status:** Stage 0 (project setup) is done. Stages 1–7 are being built one at a time.

## How it works

- **`channel.yaml`** is the channel bible: audience, narrator, characters,
  visual style, content rules, publish schedule, Veo settings. Every stage reads it.
- **`episodes/<slug>/episode.json`** is the single source of truth for one
  episode. Every stage reads it, does its work, writes results back and moves
  the `status` forward:

  `new → drafted → voiced → clips_ready → rendered → awaiting_approval → scheduled / rejected`

- **`review_notes`** in episode.json collects everything a human should check
  (validation problems, voice too long for a clip, failed clips…). It is sent
  to you with the approval request.
- Re-running a command resumes from the current status and skips files that
  already exist, so retries are cheap.

## Setup

1. **Python 3.11+** and **ffmpeg** (includes `ffprobe`) on your PATH.
   - Windows: `winget install Gyan.FFmpeg` · macOS: `brew install ffmpeg` · Ubuntu: `sudo apt install ffmpeg`
2. Install:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # macOS / Linux
   pip install -r requirements.txt
   ```
3. Secrets: copy `.env.example` to `.env` and fill in the keys (table below).
4. Edit **`channel.yaml`**: replace the two `TODO` character descriptions.
   They are pasted word for word into every Veo prompt, so be specific
   (age, size, hair, clothes, colours). The pipeline refuses to run while
   any `TODO` is left.
5. Add assets; see [`assets/README.md`](assets/README.md).
6. Check everything works: `python -m pytest`

## API keys

| Key (`.env`) | Stage | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | 1 Script | https://console.anthropic.com/settings/keys |
| `CLAUDE_MODEL` | 1 Script | Optional, defaults to `claude-sonnet-5-5` |
| `ELEVENLABS_API_KEY` | 2 Voice | https://elevenlabs.io/app/settings/api-keys |
| `ELEVENLABS_VOICE_ID` | 2 Voice | ElevenLabs Voice Library → voice → "Copy voice ID" |
| `ELEVENLABS_MODEL` | 2 Voice | Optional |
| `GEMINI_API_KEY` | 3 Clips | https://aistudio.google.com/apikey (billing required) |
| `TELEGRAM_BOT_TOKEN` | 5 Approval | Telegram: message @BotFather → `/newbot` |
| `TELEGRAM_CHAT_ID` | 5 Approval | Message your bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` → `chat.id` |
| `YOUTUBE_CLIENT_SECRET_FILE` | 6 Upload | Google Cloud OAuth client (Desktop app) JSON; git-ignored |
| `YOUTUBE_TOKEN_FILE` | 6 Upload | Created on first login; git-ignored |

Each stage only asks for its own keys, so you can start with just the Anthropic key.

## Commands

```bash
python run.py init "Letter A is for Apple"   # create episodes/letter-a-is-for-apple/
python run.py -h                             # all commands
```

More commands are added as each stage is built.

## Project layout

```
run.py            command line
channel.yaml      channel bible
topics.txt        queue of upcoming topics (one per line)
pipeline/         one plain Python module per stage
  config.py       loads/checks channel.yaml and .env
  episode.py      episode.json: create, load, save, status, review notes
assets/           characters/, music/, fonts/, optional intro.mp4 / outro.mp4
episodes/         generated episodes (git-ignored)
tests/            pytest, all external APIs mocked
```

## Costs (estimates; check current prices)

| Item | Approx. cost per 3-minute episode |
|---|---|
| Veo 3.1 Fast, 1080p, ~23 clips × 8 s at $0.12/s | ~$22 |
| Veo 3.1 Standard, same | ~$74 |

Veo is by far the largest cost. The price per second lives in `channel.yaml`
(`veo.usd_per_second`) and is used for the estimate shown before generating.
Claude, ElevenLabs and YouTube costs are added as those stages are built.

## Tests

```bash
python -m pytest
```

Tests use temp folders and mocked APIs. They never call a paid API and never
touch your real `episodes/` folder or `.env`.
