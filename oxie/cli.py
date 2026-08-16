'''
Command line interface for oxie.

    oxie init myblog --title "My Blog" --author "Me"
    python -m oxie init myblog

`init` is the only command: a site's own build.py is its build entry point.
'''
import argparse
import sys

from . import __version__
from .scaffold import init_site


def _cmd_init(args) -> int:
    result = init_site(
        target=args.path,
        title=args.title,
        author=args.author,
        link=args.link,
        description=args.description,
        force=args.force,
    )

    for path in result["created"]:
        print(f"  created  {path}")
    for path in result["skipped"]:
        print(f"  skipped  {path} (exists — use --force to overwrite)")

    if not result["created"]:
        print("\nNothing to do: every file already exists.")
        return 0

    steps = []
    if args.path not in (".", ""):
        steps.append(f"cd {args.path}")
    steps.append("npm install       # Tailwind CSS v4")
    steps.append("python build.py   # writes docs/")

    print(f"\nSite created in {result['root']}\n")
    print("Next steps:")
    for step in steps:
        print(f"  {step}")
    print("\nThen open docs/index.html, or serve docs/ with a static file server.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="oxie",
        description="oxie — a small static site/blog generator.",
    )
    parser.add_argument("--version", action="version", version=f"oxie {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="create a new site (templates, Tailwind setup, sample content)",
    )
    init_parser.add_argument(
        "path", nargs="?", default=".",
        help="directory to create the site in (default: current directory)")
    init_parser.add_argument("--title", default="My Site", help="site title")
    init_parser.add_argument("--author", default="", help="author name")
    init_parser.add_argument(
        "--link", default="https://example.com",
        help="public base URL, used for absolute links in structured data")
    init_parser.add_argument(
        "--description", default="A site built with oxie.", help="site description")
    init_parser.add_argument(
        "--force", action="store_true", help="overwrite existing files")
    init_parser.set_defaults(func=_cmd_init)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
