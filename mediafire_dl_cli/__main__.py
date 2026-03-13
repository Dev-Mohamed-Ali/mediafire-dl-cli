"""
mediafire_dl_cli.__main__
~~~~~~~~~~~~~~~~~~~~~
CLI usage:

    python -m mediafire_dl_cli <url> [url ...] [options]

Options:
    -o, --output DIR        Output directory (default: current dir)
    -w, --workers N         Parallel downloads for bulk mode (default: 3)
    -r, --retries N         HTTP retry count (default: 5)
    -H, --header KEY:VALUE  Extra request header (repeatable)
    --no-progress           Suppress progress output
"""

import argparse
import sys
from .downloader import Download, BulkDownload


def _parse_headers(raw: list[str]) -> dict[str, str]:
    headers = {}
    for item in raw or []:
        if ":" not in item:
            print(f"[WARN] Skipping malformed header (no colon): {item!r}", file=sys.stderr)
            continue
        k, _, v = item.partition(":")
        headers[k.strip()] = v.strip()
    return headers


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mediafire_dl_cli",
        description="Download files from MediaFire with auto-resume support.",
    )
    parser.add_argument("urls", nargs="+", metavar="URL", help="MediaFire page URL(s)")
    parser.add_argument("-o", "--output", default="", metavar="DIR", help="Output directory")
    parser.add_argument("-w", "--workers", type=int, default=3, metavar="N", help="Parallel workers for bulk")
    parser.add_argument("-r", "--retries", type=int, default=5, metavar="N", help="HTTP retry count")
    parser.add_argument("-H", "--header", action="append", metavar="KEY:VALUE", dest="headers", help="Extra HTTP header")
    parser.add_argument("--no-progress", action="store_true", help="Suppress progress bar")

    args = parser.parse_args()
    headers = _parse_headers(args.headers)
    show = not args.no_progress

    if len(args.urls) == 1:
        try:
            path = Download(
                args.urls[0],
                output=args.output,
                headers=headers or None,
                retries=args.retries,
                show_progress=show,
            )
            print(f"Saved to: {path}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        BulkDownload(
            args.urls,
            output=args.output,
            headers=headers or None,
            max_workers=args.workers,
            retries=args.retries,
            show_progress=show,
        )


if __name__ == "__main__":
    main()
