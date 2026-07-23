---
name: csv-insights
description: Summarize a CSV file. Use when the user has a .csv file and wants a quick overview of its columns, row count, and basic stats.
metadata:
  version: "1.0"
---

# CSV Insights

A multi-file skill used to test Skills Over MCP (sibling files + later directory reads).

## Instructions

1. Read the reference guide at `references/GUIDE.md` for the summary format to follow.
2. Run the helper script to produce the summary:

   ```
   python scripts/summarize.py <path-to.csv>
   ```

3. Present the result using the format from the guide.

## Files

- `references/GUIDE.md` - the output format and what to report.
- `scripts/summarize.py` - the helper that computes the summary.
