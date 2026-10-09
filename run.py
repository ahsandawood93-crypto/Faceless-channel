"""Minsa Kids TV Autopilot — command line.

    python run.py init "Letter A is for Apple"   # create an episode folder
    python run.py <stage> <slug>                  # run one stage (built stage by stage)
    python run.py next                            # next topic from topics.txt, up to approval

Run `python run.py -h` for the full list.
"""

import argparse
import sys

from pipeline.config import ConfigError, load_channel
from pipeline.episode import Episode

STAGES = ["write", "voice", "video", "assemble", "upload", "approve", "all"]


def cmd_init(args):
    load_channel()  # fail early if channel.yaml still has TODOs
    episode = Episode.create(args.topic)
    print(f"Created episodes/{episode.slug}/episode.json (status: {episode.status})")
    print(f"Next: python run.py write {episode.slug}")


def cmd_not_built(args):
    print(f"'{args.command}' is not built yet.")
    return 1


def build_parser():
    parser = argparse.ArgumentParser(prog="run.py", description="Minsa Kids TV Autopilot")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a new episode from a topic line")
    p.add_argument("topic")
    p.set_defaults(func=cmd_init)

    for name in STAGES:
        p = sub.add_parser(name, help=f"run the '{name}' stage for an episode")
        p.add_argument("episode", help="episode slug (folder name in episodes/)")
        p.set_defaults(func=cmd_not_built)

    p = sub.add_parser("next", help="take the next topic from topics.txt and run it to approval")
    p.set_defaults(func=cmd_not_built)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except ConfigError as e:
        print(f"Config problem: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
