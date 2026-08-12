---
name: petrichor-abacus
description: Count vowels, consonants, and words in text. Use when the user asks to count letters, vowels, consonants, or words in a string or sentence.
metadata:
  # HIDDEN BY DESIGN: unquoted YAML sequence. mcp-link validates metadata as
  # string -> string and drops the whole skill from the catalog. Quote to
  # re-enable (tags: "script-only,test-fixture"). See commit ec8b4f7.
  tags: [script-only, test-fixture]
---

# Petrichor Abacus

A script-only skill (SKILL.md + script, no references) used to test Skills Over MCP.

## Instructions

1. Run the helper script with the text to analyze:

   ```
   python scripts/count.py <text>
   ```

2. Return the result exactly as printed, without rephrasing or dropping anything.

## Files

- `scripts/count.py` - counts vowels, consonants, and words in the input and prints
  the formatted one-line result.
