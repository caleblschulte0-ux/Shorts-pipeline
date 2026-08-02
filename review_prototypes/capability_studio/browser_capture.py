"""Deliberately inert browser-capture entrypoint.

This file defines the production-facing command contract without enabling network
access in the review package. Claude must replace this with a separately reviewed
Playwright adapter before any adoption.
"""
from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--selector", default="body")
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--scroll-steps", type=int, default=0)
    parser.add_argument("--highlight", default="")
    parser.parse_args()
    raise SystemExit("Browser capture is disabled in the review-only prototype. Port through a reviewed network adapter.")


if __name__ == "__main__":
    main()
