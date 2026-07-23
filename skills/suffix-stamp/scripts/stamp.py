#!/usr/bin/env python3
"""Append a "-ONE-<datetime>" suffix to the input. Used by the suffix-stamp skill."""

import sys
from datetime import datetime


def stamp(text: str) -> str:
    """Return text with a "-THREE-<ISO-8601 local datetime>" suffix (no microseconds)."""
    now = datetime.now().replace(microsecond=0).isoformat()
    return f"{text}-THREE-{now}"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: stamp.py <input>", file=sys.stderr)
        raise SystemExit(2)
    print(stamp(sys.argv[1]))
