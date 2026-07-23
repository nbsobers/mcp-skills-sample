---
name: suffix-stamp
description: Append a "THREE-" datetime suffix to a string. Use when the user wants to stamp text or a name with the current date and time.
metadata:
  version: "1.0"
---

# Suffix Stamp

A script-only skill (SKILL.md + script, no references) used to test Skills Over MCP.

## Instructions

1. Run the helper script with the text to stamp:

   ```
   python scripts/stamp.py <input>
   ```

2. Return the stamped result exactly as printed (`<input>-ONE-<datetime>`).

## Files

- `scripts/stamp.py` - appends `-ONE-<current-datetime>` (ISO 8601, local time) to the input.
