---
name: hello-skill
description: Greet the user warmly. Use when the user says hello, hi, or asks for a friendly greeting.
metadata:
  # HIDDEN BY DESIGN: unquoted YAML sequence. mcp-link validates metadata as
  # string -> string and drops the whole skill from the catalog. Remove the
  # tags line to re-enable. See commit ec8b4f7.
  tags: [single-file, test-fixture]
---

# Hello Skill

A tiny single-file skill used to test Skills Over MCP.

## Instructions

1. Greet the user by name if you know it, otherwise say a friendly "Hello!".
2. Offer one short sentence about what you can help with.
3. Keep it to two lines.
