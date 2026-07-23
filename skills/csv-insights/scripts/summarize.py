#!/usr/bin/env python3
"""Print a tiny summary of a CSV file. Used by the csv-insights skill."""

import csv
import sys
from pathlib import Path


def summarize(path: str) -> None:
    p = Path(path)
    with p.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        rows = list(reader)

    if not rows:
        print(f"File: {p.name}\nRows: 0\nColumns: 0")
        return

    header, data = rows[0], rows[1:]
    print(f"File: {p.name}")
    print(f"Rows: {len(data)}")
    print(f"Columns: {len(header)}")
    for col in header:
        print(f"  - {col}")
    if data:
        print("Sample:")
        for key, value in zip(header, data[0]):
            print(f"  {key}: {value}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: summarize.py <path-to.csv>", file=sys.stderr)
        raise SystemExit(2)
    summarize(sys.argv[1])
