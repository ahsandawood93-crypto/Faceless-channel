# Minsa Kids TV Autopilot

Turns one topic line into a finished, scheduled YouTube Kids episode for
**Minsa Kids TV** (English, ages 2–6, original characters Minsa and Mana).
**Nothing goes public without your approval.**

```
topic → 1 Script (Claude) → 2 Voiceover (ElevenLabs) → 3 Clips (Veo 3.1)
      → 4 Assembly (ffmpeg) → upload PRIVATE (YouTube) → 5 Approval (Telegram)
      → 6 Schedule (publishAt = next free slot)
```

## How it works

- **`channel.yaml`** is the channel bible (audience, narrator, characters,
  visual style, content rules, schedule, Veo settings). Every stage reads it.
- **`episodes/<slug>/episode.json`** is the single source of truth for one
  episode. Each stage reads it, does its work, writes results back and moves
  `status` forward:

  `new → drafted → voiced → clips_ready → rendered → awaiting_approval → scheduled / rejected`

- **`review_notes`** collects everything you should check: validation
  problems Claude couldn't fix, voice longer than a clip, failed clips,
  missing music. They are sent to you with the approval request.
- Every command **resumes** from the episode's status and **skips files that
  already exist**, so reruns after an error only pay for what's missing.
- The video is uploaded **private** first so you can watch it on YouTube.
  Only your **Approve** tap in Telegram schedules it.

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
3. **`channel.yaml`**: replace the two `TODO` character descriptions. They are
   pasted word for word into every Veo prompt, so be specific (age, size,
   hair, clothes, colours). The pipeline refuses to run while a `TODO` is left.
4. **Assets** (see [`assets/README.md`](assets/README.md)):
   - `assets/characters/minsa.png`, `mana.png`: reference images (required for real clips)
   - `assets/fonts/`: one rounded `.ttf`, e.g. [Fredoka](https://fonts.google.com/specimen/Fredoka) (OFL)
   - `assets/music/`: a few royalty-free tracks (e.g. YouTube Audio Library)
   - optional `assets/intro.mp4`, `assets/outro.mp4`
5. **Keys**: copy `.env.example` to `.env` and fill it in (table below).
6. **Telegram** and **YouTube**: one-time setup below.
7. Check everything: `python -m pytest` (no keys needed, nothing is called for real).
8. Free dry run: `python run.py all "Letter A is for Apple" --no-voice --no-video`
   (writes the script with Claude, then uses silent audio and coloured
   placeholder clips; costs a few cents of Claude only).

## API keys (`.env`)

| Key | Stage | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | 1 Script | https://console.anthropic.com/settings/keys |
| `CLAUDE_MODEL` | 1 Script | Optional. Default `claude-sonnet-5-5` |
| `ELEVENLABS_API_KEY` | 2 Voice | https://elevenlabs.io/app/settings/api-keys |
| `ELEVENLABS_VOICE_ID` | 2 Voice | ElevenLabs → Voices → pick a warm narrator voice → "Copy voice ID" |
| `ELEVENLABS_MODEL` | 2 Voice | Optional. Default `eleven_multilingual_v2` (long-form narration) |
| `GEMINI_API_KEY` | 3 Clips | https://aistudio.google.com/apikey (**billing must be enabled**; Veo has no free tier) |
| `TELEGRAM_BOT_TOKEN` | 5 Approval | Telegram → @BotFather → `/newbot` |
| `TELEGRAM_CHAT_ID` | 5 Approval | Send your bot any message, open `https://api.telegram.org/bot<TOKEN>/getUpdates`, copy `message.chat.id` |
| `YOUTUBE_CLIENT_SECRET_FILE` | 6 Upload | Path to the OAuth client JSON (default `client_secret.json`, git-ignored) |
| `YOUTUBE_TOKEN_FILE` | 6 Upload | Where the login token is cached (default `youtube_token.json`, git-ignored) |

Each stage only asks for its own keys, so you can start with just the Anthropic key.

### Telegram setup (2 minutes)
1. In Telegram, message **@BotFather** → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`.
2. Open a chat with your new bot and send "hi".
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser; copy
   `"chat":{"id": ...}` into `TELEGRAM_CHAT_ID`. The bot ignores everyone else.

### YouTube setup (one time, ~15 minutes)
1. https://console.cloud.google.com → create a project (e.g. "Minsa Kids TV Autopilot").
2. APIs & Services → Library → enable **YouTube Data API v3**.
3. APIs & Services → OAuth consent screen → External → fill in the app name and
   your email → add yourself as a test user. Then set publishing status to
   **In production**: in "Testing" mode Google expires the login every 7 days.
   (You'll see an "unverified app" warning on login; for your own account click
   Advanced → continue.)
4. Credentials → Create credentials → **OAuth client ID** → *Desktop app* →
   download the JSON as `client_secret.json` in this folder.
5. Run the first upload by hand (`python run.py upload <slug>`): a browser
   opens to log in to the channel's Google account. The token is cached in
   `youtube_token.json`, so scheduled runs never need the browser again.

## YouTube: audit and quota (read this)

- **Unverified projects can only make private videos.** Google locks every
  video uploaded through `videos.insert` from an API project created after
  28 July 2020 to **private** until the project passes a compliance audit.
  Until then, `publishAt` scheduling will **not** make the video public; you
  would have to publish by hand in YouTube Studio. Everything else in this
  pipeline works.
- **How to apply:** fill in the YouTube API Services audit and quota extension
  form: https://support.google.com/youtube/contact/yt_api_form . Describe it
  as an internal tool that uploads your own channel's videos, explain that a
  human approves every video before it's scheduled, and link a short privacy
  policy page. Review usually takes a few weeks. The YouTube API Services
  Terms and Developer Policies are what they audit against.
- **Daily quota:** 10,000 units per Google Cloud project per day (resets at
  midnight Pacific). Per episode this pipeline uses `videos.insert` (1,600
  units in Google's cost table; some 2026 reports say uploads moved to a
  separate 100-uploads-per-day bucket), `thumbnails.set` (50),
  `captions.insert` (400) and `videos.update` (50) for scheduling: about 2,100
  units, so roughly 4 episodes a day at most. Check your real usage under
  APIs & Services → YouTube Data API v3 → Quotas.
- **Custom thumbnails** need a phone-verified channel (youtube.com/verify). If
  `thumbnails.set` fails, a review note tells you to set it in Studio.
- Videos are marked **made for kids** (`selfDeclaredMadeForKids: true`), as
  YouTube's COPPA rules require. That turns off comments and personalised ads.

## Commands

```bash
python run.py next --yes                     # next topic in topics.txt (or resume an unfinished episode), up to approval
python run.py all "Letter B is for Ball"     # one topic (or existing slug), up to approval
python run.py all letter-b-is-for-ball --no-voice --no-video   # free dry run with placeholders
python run.py approve --listen               # wait for your Approve / Reject taps (Ctrl+C to stop)
python run.py approve --once                 # handle taps waiting in Telegram, then exit (for schedulers)
python run.py list                           # all episodes and their status

# single stages (each resumes and skips existing work)
python run.py write  "<topic or slug>"  [--force]
python run.py voice  <slug>             [--no-voice]
python run.py video  <slug>             [--yes] [--no-video]
python run.py assemble <slug>
python run.py upload <slug>             # private upload + thumbnail + captions
python run.py approve <slug>            # (re)send the Telegram approval request
python run.py approve <slug> --schedule # approve from the terminal instead
python run.py approve <slug> --reject "reason"
```

- **Veo cost prompt:** `video` (and `all`/`next`) prints the estimated cost and asks
  before generating. `--yes` skips the question; scheduled runs need it.
  `veo.max_usd_per_run` in `channel.yaml` (default $40) refuses anything above
  that even with `--yes`.
- **When something fails**, the message names the scene and the command to rerun.
  Failed clips are logged in `review_notes`; you can edit that scene's
  `veo_prompt` in `episode.json` and rerun `video`; finished clips are kept.
  Unattended runs (`next`, `all`) also send the error to Telegram.
- **Rejected?** The reason is stored in `episode.json` (`rejection_reason`). Fix
  the script or prompts and run again, or add the topic back to `topics.txt`.

## Run it every day

`next` handles one episode per run and stops at the approval gate. A second
job picks up your Approve / Reject taps. All paths in the project are relative
to the project folder, so the jobs work from any working directory.

**Do the first real run by hand** (for the YouTube browser login), then:

### Windows Task Scheduler
Open *Command Prompt* and run (adjust the path):
```bat
set P=C:\Users\you\Faceless-channel
mkdir %P%\logs

schtasks /Create /TN "MinsaKidsTV next" /SC DAILY /ST 09:00 ^
  /TR "cmd /c \"cd /d %P% && .venv\Scripts\python.exe run.py next --yes >> logs\next.log 2>&1\""

schtasks /Create /TN "MinsaKidsTV approvals" /SC MINUTE /MO 15 ^
  /TR "cmd /c \"cd /d %P% && .venv\Scripts\python.exe run.py approve --once >> logs\approve.log 2>&1\""
```
Or in the Task Scheduler app: *Create Basic Task* → Daily 09:00 → *Start a
program* → Program `C:\Users\you\Faceless-channel\.venv\Scripts\python.exe`,
Arguments `run.py next --yes`, *Start in* `C:\Users\you\Faceless-channel`.
Tick "Run whether user is logged on or not" and "Wake the computer to run this task".

### cron (macOS / Linux)
`crontab -e`, then:
```cron
0 9 * * *    cd /home/you/Faceless-channel && .venv/bin/python run.py next --yes >> logs/next.log 2>&1
*/15 * * * * cd /home/you/Faceless-channel && .venv/bin/python run.py approve --once >> logs/approve.log 2>&1
```
(`mkdir logs` first.) Prefer instant replies? Run `python run.py approve --listen`
in a terminal (or as a startup task) instead of the 15-minute job.

## Costs (estimates, October 2026; check current prices)

| Item | Per 3-minute episode |
|---|---|
| **Veo 3.1 Fast**, 1080p: ~23 clips × 8 s × $0.12/s | **~$22** |
| Veo 3.1 Standard, 1080p ($0.40/s) | ~$74 |
| Claude Sonnet 5.5 script ($2 / $10 per million tokens in/out), 1–3 attempts | ~$0.10–0.50 |
| ElevenLabs: about 2,000 characters | part of your monthly character allowance |
| YouTube Data API, Telegram | free |

Veo is almost the whole bill, and failed or retried clips cost extra. Three
episodes a week on Veo Fast is roughly $270–300 a month. The price per second
lives in `channel.yaml` (`veo.usd_per_second`) and drives the estimate shown
before each run. Switch `veo.model` to `veo-3.1-generate-preview` for higher
quality at about 3× the cost.

## Things to know

- **Forced tool use:** Stage 1 asks Claude for structured output through a
  `write_episode` tool. Current Claude models (Sonnet 5.5, Opus 5.5) reject a
  *forced* `tool_choice`, so it uses `tool_choice: auto` with `strict: true`
  and retries if no tool call comes back. Refusals fall back server-side
  (`fallbacks: "default"`).
- **Veo** returns 8-second clips when reference images are used; scenes
  shorter than 8 s are trimmed during assembly. The Gemini API always
  generates audio, so it's stripped with ffmpeg. If Veo rejects reference
  images for your account, the scene is retried with the character image as
  its starting frame and a review note is added.
- **Captions** are timed by spreading each scene's words across its real
  (ffprobe-measured) narration length. They are burned in and uploaded as
  `episode.srt`.
- **Loudness** is normalised with ffmpeg's two-pass `loudnorm` to −14 LUFS.
- On a typical PC, assembling a 3-minute 1080p episode takes about 2–4 minutes.

## Project layout

```
run.py                command line (Stage 7)
channel.yaml          channel bible
topics.txt            queue of upcoming topics (one per line, # = comment)
pipeline/
  config.py           loads/checks channel.yaml and .env
  episode.py          episode.json: create, load, save, status, review notes
  util.py             ffmpeg/ffprobe helpers, retries, console output
  script_writer.py    Stage 1  Claude → episode.json + episode.md
  voiceover.py        Stage 2  ElevenLabs → audio/scene_XX.mp3, full_narration.mp3
  video.py            Stage 3  Veo 3.1 → clips/scene_XX.mp4
  assemble.py         Stage 4  ffmpeg → final/episode.mp4, episode.srt, thumbnail.jpg
  approve.py          Stage 5  Telegram approval gate
  upload.py           Stage 6  YouTube upload (private) and scheduling
assets/               characters/, music/, fonts/, optional intro.mp4 / outro.mp4
episodes/             generated episodes (git-ignored)
tests/                pytest, every external API mocked
```

## Tests

```bash
python -m pytest
```

95 tests. They use temp folders, fake API clients and real ffmpeg on tiny
files. They never call a paid API and never touch your `episodes/` folder or `.env`.
