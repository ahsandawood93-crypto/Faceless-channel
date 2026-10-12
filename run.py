"""Minsa Kids TV Autopilot — command line.

    python run.py next                        # next topic from topics.txt, up to the approval gate
    python run.py all "Letter B is for Ball"  # one topic (or an existing slug), up to approval
    python run.py approve --listen            # wait for your Approve / Reject taps in Telegram
    python run.py list                        # every episode and its status

Single stages: write, voice, video, assemble, upload, approve. Every command
resumes from the episode's status and skips work that already exists.
Run `python run.py <command> -h` for options.
"""

import argparse
import sys
from pathlib import Path

from pipeline import approve, assemble, script_writer, upload, video, voiceover
from pipeline.config import ROOT, ConfigError, load_channel
from pipeline import episode as episode_module
from pipeline.episode import Episode
from pipeline.util import StageError, info, step, warn

TOPICS_FILE = ROOT / "topics.txt"
FINISHED = ("awaiting_approval", "scheduled", "rejected")


# ---- helpers ----------------------------------------------------------------------

def find_or_create(text):
    """Existing slug -> that episode; anything else is a new topic."""
    try:
        return Episode.load(text)
    except FileNotFoundError:
        return Episode.create(text)


def load(slug):
    try:
        return Episode.load(slug)
    except FileNotFoundError:
        raise StageError(f"No episode '{slug}'. See: python run.py list") from None


def all_episodes():
    return [Episode.load(f) for f in sorted(Path(episode_module.EPISODES_DIR).glob("*/episode.json"))]


def pop_topic(path=None):
    """Remove and return the first real topic line from topics.txt (None if empty)."""
    path = Path(path or TOPICS_FILE)
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        topic = line.strip()
        if topic and not topic.startswith("#"):
            path.write_text("".join(lines[:i] + lines[i + 1:]), encoding="utf-8")
            return topic
    return None


def has_placeholders(episode, kind):
    return any(s.get(f"{kind}_placeholder") for s in episode.data["scenes"])


def notify_failure(episode, error):
    """Best effort: tell you in Telegram when an unattended run stops."""
    try:
        bot = approve.Telegram.from_env()
        bot.send(f"⚠️ <b>Pipeline stopped</b> for <code>{episode.slug}</code> (status: {episode.status})\n"
                 f"{str(error)[:3000]}")
    except Exception:  # noqa: BLE001 - Telegram not set up yet, or offline
        pass


# ---- the pipeline up to the approval gate --------------------------------------------

def run_until_approval(episode, channel, yes=False, no_voice=False, no_video=False):
    if episode.status in FINISHED:
        info(f"{episode.slug} is {episode.status}; nothing to do.")
        return episode
    if not episode.reached("drafted"):
        script_writer.run_stage(episode, channel)
    if not episode.reached("voiced") or (has_placeholders(episode, "audio") and not no_voice):
        voiceover.run_stage(episode, channel, placeholder=no_voice)
    if not episode.reached("clips_ready") or (has_placeholders(episode, "clip") and not no_video):
        video.run_stage(episode, channel, yes=yes, placeholder=no_video)
    stale = (episode.data.get("final") or {}).get("placeholder") and not (no_voice or no_video)
    if not episode.reached("rendered") or stale:
        assemble.run_stage(episode, channel)
    if episode.data["final"].get("placeholder"):
        step("Dry run finished")
        info(f"Watch it: {episode.dir / episode.data['final']['video']}")
        info(f"Real run (paid voice/clips, then upload + Telegram): python run.py all {episode.slug} --yes")
        return episode
    upload.upload_private(episode)
    approve.send_for_approval(episode)
    return episode


# ---- commands ------------------------------------------------------------------------

def cmd_init(args, channel):
    episode = Episode.create(args.topic)
    print(f"Created episodes/{episode.slug}/episode.json (status: {episode.status})")
    print(f"Next: python run.py all {episode.slug}")


def cmd_write(args, channel):
    script_writer.run_stage(find_or_create(args.episode), channel, force=args.force)


def cmd_voice(args, channel):
    voiceover.run_stage(load(args.episode), channel, placeholder=args.no_voice)


def cmd_video(args, channel):
    video.run_stage(load(args.episode), channel, yes=args.yes, placeholder=args.no_video)


def cmd_assemble(args, channel):
    assemble.run_stage(load(args.episode), channel)


def cmd_upload(args, channel):
    upload.upload_private(load(args.episode))


def cmd_approve(args, channel):
    if args.listen or args.once:
        approve.listen(channel, once=args.once)
        return
    if not args.episode:
        raise StageError("Give an episode slug, or use --listen / --once.")
    episode = load(args.episode)
    if args.schedule:  # approve from the terminal instead of Telegram
        upload.schedule(episode, channel)
    elif args.reject is not None:
        episode.data["rejection_reason"] = args.reject
        episode.set_status("rejected")
        info(f"{episode.slug} rejected: {args.reject}")
    else:
        if not (episode.data.get("youtube") or {}).get("video_id"):
            upload.upload_private(episode)
        approve.send_for_approval(episode)


def cmd_all(args, channel):
    episode = find_or_create(args.episode)
    try:
        run_until_approval(episode, channel, yes=args.yes, no_voice=args.no_voice, no_video=args.no_video)
    except (StageError, ConfigError) as e:
        notify_failure(episode, e)
        raise


def cmd_next(args, channel):
    unfinished = [e for e in all_episodes() if e.status not in FINISHED
                  and not (e.data.get("final") or {}).get("placeholder")]
    if unfinished:
        episode = min(unfinished, key=lambda e: e.data["created_at"])
        info(f"Resuming unfinished episode {episode.slug} (status: {episode.status})")
    else:
        topic = pop_topic()
        if not topic:
            warn("topics.txt is empty. Add topics, one per line.")
            return 0
        episode = Episode.create(topic)
        info(f"New episode from topics.txt: {topic} -> {episode.slug}")
    try:
        run_until_approval(episode, channel, yes=args.yes, no_voice=args.no_voice, no_video=args.no_video)
    except (StageError, ConfigError) as e:
        notify_failure(episode, e)
        raise


def cmd_list(args, channel):
    episodes = all_episodes()
    if not episodes:
        print("No episodes yet. Try: python run.py next")
    for e in episodes:
        when = (e.data.get("youtube") or {}).get("publish_at") or ""
        print(f"{e.status:<18} {e.slug:<52} {when}")


# ---- parser --------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(prog="run.py", description="Minsa Kids TV Autopilot")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_text, episode=True, episode_help="episode slug"):
        p = sub.add_parser(name, help=help_text)
        if episode:
            p.add_argument("episode", help=episode_help)
        p.set_defaults(func=func)
        return p

    def dry_run_flags(p, yes=True):
        if yes:
            p.add_argument("--yes", action="store_true", help="skip the Veo cost confirmation (for scheduled runs)")
        p.add_argument("--no-voice", action="store_true", help="silent placeholder narration (free)")
        p.add_argument("--no-video", action="store_true", help="solid-colour placeholder clips (free)")

    p = add("init", cmd_init, "create an empty episode from a topic", episode=False)
    p.add_argument("topic")
    p = add("write", cmd_write, "Stage 1: write the script with Claude", episode_help="topic or existing slug")
    p.add_argument("--force", action="store_true", help="rewrite an existing script")
    p = add("voice", cmd_voice, "Stage 2: ElevenLabs voiceover")
    p.add_argument("--no-voice", action="store_true", help="silent placeholders instead (free)")
    p = add("video", cmd_video, "Stage 3: Veo clips")
    p.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    p.add_argument("--no-video", action="store_true", help="placeholder clips instead (free)")
    add("assemble", cmd_assemble, "Stage 4: final video, captions, thumbnail")
    add("upload", cmd_upload, "Stage 6: upload to YouTube as private (+ thumbnail, captions)")
    p = add("approve", cmd_approve, "Stage 5: send for approval, or listen for your answer", episode=False)
    p.add_argument("episode", nargs="?", help="episode slug (sends the approval request)")
    p.add_argument("--listen", action="store_true", help="keep waiting for Approve / Reject taps")
    p.add_argument("--once", action="store_true", help="handle waiting taps, then exit (for schedulers)")
    p.add_argument("--schedule", action="store_true", help="approve from the terminal and schedule now")
    p.add_argument("--reject", metavar="REASON", help="reject from the terminal with a reason")
    p = add("all", cmd_all, "run every stage up to the approval gate", episode_help="topic or existing slug")
    dry_run_flags(p)
    p = add("next", cmd_next, "next topic from topics.txt (or resume an unfinished one), up to approval",
            episode=False)
    dry_run_flags(p)
    add("list", cmd_list, "list episodes and their status", episode=False)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        channel = None if args.command == "list" else load_channel()
        return args.func(args, channel) or 0
    except ConfigError as e:
        print(f"\nConfig problem: {e}", file=sys.stderr)
        return 2
    except StageError as e:
        print(f"\nStopped: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted. Rerun the same command to continue where it stopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
