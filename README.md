# mcp-skills-server

A minimal **Skills Over MCP (SEP-2640)** server for testing the Airia MCP Gateway.

It serves the skills in [`skills/`](./skills) over **Streamable HTTP** as MCP resources:

- `skill://index.json` — the July-8 index (`url` / `digest` / `frontmatter`)
- `skill://<skill-path>/<file>` — every file in a skill folder, read on demand. The
  skill-path may be a single segment (`hello-skill`) or **nested** to arbitrary depth
  (`acme/billing/refunds`), per the spec's nested-skill-path rules

It advertises `capabilities.resources` and the skills extension under
`capabilities.experimental` (`io.modelcontextprotocol/skills`), matching what real hosts
like skillsovermcp.com do today.

## Skills included

| Skill | Shape | Files |
|-------|-------|-------|
| `hello-skill` | single-file | `SKILL.md` |
| `csv-insights` | multi-file | `SKILL.md`, `references/GUIDE.md`, `scripts/summarize.py` |
| `suffix-stamp` | script-only | `SKILL.md`, `scripts/stamp.py` |
| `petrichor-abacus` | script-only | `SKILL.md`, `scripts/count.py` |
| `acme/billing/refunds` | nested-path | `SKILL.md`, `scripts/refund.py` |
| `name-signature` | binary asset | `SKILL.md`, `references/STYLES.md`, `scripts/sign.py`, `assets/sample-ada-lovelace.svg` |

### Intentionally hidden from the gateway catalog 🙈

Four skills are currently **hidden on purpose**:

| Skill | Hidden via |
|-------|-----------|
| `petrichor-abacus` | `tags:` as an unquoted YAML sequence |
| `acme/billing/refunds` | `tags:` as an unquoted YAML sequence |
| `weather-helper` | `threat:` bool + `tags:` sequence |
| `note-encoder` | `threat:` bool + `tags:` sequence |

The mechanism is the one commit `ec8b4f7` fixed, applied deliberately in reverse.
The Agent Skills spec defines `metadata` as a map of string → string, and
`mcp-link` enforces that strictly: **any** non-string value makes it reject the
entire skill and omit it from `skill://index.json`. So expect
**`invalid_candidates: 4`** from the gateway — that count is by design, not a bug.
Each hidden `SKILL.md` carries a `HIDDEN BY DESIGN` comment in its frontmatter.

Scope: this hides them from the **gateway** only. `server.py` does no frontmatter
validation, so all four are still served locally via `resources/list`,
`resources/read`, `skills/list`, and this server's own `skill://index.json` — a
client talking straight to the server still sees them. To hide them there too,
move the directories out of `skills/` or filter in `_find_skill_dirs`.

**To re-enable:** quote the values (`threat: "true"`, `tags: "a,b,c"`) or drop the
added `tags` line, matching the style `ec8b4f7` established. Restart the server —
`load_skills()` runs at import and there is no reload path.

### `name-signature` — the binary-resource fixture ✍️

Turns a typed name into a cursive signature SVG:

```bash
python3 skills/name-signature/scripts/sign.py "Ada Lovelace" > sig.svg
python3 skills/name-signature/scripts/sign.py "Ada Lovelace" bold "#111111" > sig.svg
```

Letterforms are composed from cursive gestures (hump, bowl, ascender loop, descender loop),
chained into one pen stroke, smoothed with Catmull-Rom, slanted, then filled as a
variable-width outline so downstrokes read heavier than cross-strokes. Pure stdlib — no
fonts, no image packages, no network — which matters because the server only *serves*
files; the client runs the script. Output is deterministic: the hand-wobble is seeded from
a SHA-256 of the name, so the same name always yields byte-identical SVG.

It is also the **first skill here carrying a non-text file**. `.svg` is absent from
`TEXT_SUFFIXES` in `server.py`, so `assets/sample-ada-lovelace.svg` takes the `read_bytes()`
path and `resources/read` returns it as a base64 `blob` with `mimeType: image/svg+xml`,
rather than the `text` every other resource in this repo returns. That makes it the fixture
for checking whether the gateway proxies binary resource content intact:

```bash
# expect: image/svg+xml, blob, and a body that still parses as SVG
... resources/read skill://name-signature/assets/sample-ada-lovelace.svg
```

### Threat fixtures (prompt-injection) ⚠️

These skills are **deliberately malicious** — each plants a prompt-injection
payload in its `SKILL.md` `name`/`description` (the two fields the Airia gateway
scans), so a working scanner should flag/quarantine every one. They're inert
data (nothing executes; the one exfil host is the placeholder
`exfil.example.com`). Each is tagged in frontmatter with `metadata.threat: true`,
an `attack_type`, and `tags: [prompt-injection, threat, test-fixture]` (surfaced
in `skill://index.json` → `frontmatter`) so scanner hits can be correlated.

| Skill (`name`) | `attack_type` | What it tests |
|----------------|---------------|----------------|
| `ignore-all-previous-instructions` | instruction-override | Jailbreak; payload in **name + description** |
| `weather-helper` | hidden-override-benign-name | Injection hidden in **description only** |
| `system-admin-override` | authority-impersonation | Fake SYSTEM/admin/vendor authorization |
| `secret-collector` | data-exfiltration | Harvest env/SSH/AWS secrets → POST to attacker URL |
| `cleanup-assistant` | destructive-tool-hijack | `rm -rf` / delete emails, skip confirmation |
| `note-encoder` | encoded-payload | Base64-obfuscated injection (decode-then-scan) |

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/)

## Start the server

```bash
cd /Users/sobers/Dev/Poc/Python/mcp-skills-server
uv sync          # first time only: creates .venv and installs deps
uv run server.py
```

It listens on **`http://127.0.0.1:8000/mcp`** (POST, no trailing slash needed).

Host and port are configurable via env vars:

```bash
PORT=5000 uv run server.py            # listen on a different port
HOST=0.0.0.0 PORT=5000 uv run server.py   # bind all interfaces (for Docker/ngrok)
```

To reach it from a gateway running in Docker/k8s, either bind to `0.0.0.0` and use
`host.docker.internal` (e.g. `http://host.docker.internal:8000/mcp`), or expose it with
ngrok (below).

## Expose it publicly with ngrok

ngrok gives a public HTTPS URL, which is the easiest way for a hosted gateway to reach
this local server. The port ngrok forwards to just has to match the server's port (8000
by default):

```bash
# terminal 1: run the server (defaults to :8000)
uv run server.py

# terminal 2: forward the public URL to that same port
ngrok http --url=sunny-wasp-selected.ngrok-free.app 8000
```

(If port 8000 is taken, run the server on another port with `PORT=5000 uv run server.py`
and use that same number in the ngrok command.)

The gateway then connects to:

```
https://sunny-wasp-selected.ngrok-free.app/mcp
```

## Quick smoke test (curl)

Streamable HTTP needs the SSE `Accept` header and a session id from `initialize`. This
block grabs the session id automatically, so you can copy-paste the whole thing:

```bash
EP=http://127.0.0.1:8000/mcp
H='Accept: application/json, text/event-stream'
CT='Content-Type: application/json'

# initialize + capture the Mcp-Session-Id from the response headers
SID=$(curl -sD - -o /dev/null -X POST "$EP" -H "$CT" -H "$H" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' \
  | awk -F': ' 'tolower($1)=="mcp-session-id"{print $2}' | tr -d '\r')
echo "session: $SID"

curl -s -X POST "$EP" -H "$CT" -H "$H" -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

echo; echo "--- resources/list ---"
curl -s -X POST "$EP" -H "$CT" -H "$H" -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":2,"method":"resources/list"}'

echo; echo "--- Layer 1: resources/read skill://index.json (the catalog) ---"
curl -s -X POST "$EP" -H "$CT" -H "$H" -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":3,"method":"resources/read","params":{"uri":"skill://index.json"}}'

echo; echo "--- Layer 2: resources/read skill://csv-insights/SKILL.md (the instructions) ---"
curl -s -X POST "$EP" -H "$CT" -H "$H" -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":4,"method":"resources/read","params":{"uri":"skill://csv-insights/SKILL.md"}}'

echo; echo "--- Layer 3: resources/read skill://csv-insights/scripts/summarize.py (a referenced file) ---"
curl -s -X POST "$EP" -H "$CT" -H "$H" -H "Mcp-Session-Id: $SID" \
  -d '{"jsonrpc":"2.0","id":5,"method":"resources/read","params":{"uri":"skill://csv-insights/scripts/summarize.py"}}'
echo
```

Streamable HTTP replies come back as SSE, so response bodies are prefixed with `data: `.
Each `resources/read` returns the file in `result.contents[0].text` (a string). To pull
just the file body out of the SSE frame, pipe any of the reads through:

```bash
| sed -n 's/^data: //p' \
| python3 -c "import sys,json; print(json.load(sys.stdin)['result']['contents'][0]['text'])"
```

## Start goose (client)

goose authenticates with `ANTHROPIC_API_KEY`. This one-liner pulls the Airia key from the
`x-airia-key` value inside `ANTHROPIC_CUSTOM_HEADERS` in `~/.claude/settings.json` and
launches goose with it:

```bash
export ANTHROPIC_API_KEY=$(python3 -c "import json,re,os;h=json.load(open(os.path.expanduser('~/.claude/settings.json')))['env']['ANTHROPIC_CUSTOM_HEADERS'];print(re.search(r'x-airia-key:\s*(\S+)',h).group(1))")
goose
```

## Use it with the gateway

Register `http://127.0.0.1:8000/mcp` (or `http://host.docker.internal:8000/mcp`) as a
custom remote MCP server, then drive `resources/list` and `resources/read` through the
gateway. The two skills should surface and reads should proxy through.

## Adding more skills

Drop a new folder under `skills/` containing a `SKILL.md` with YAML frontmatter
(`name` + `description`). The server rebuilds the index on restart.

Folders may nest to any depth (e.g. `skills/acme/billing/refunds/`); the skill's URI uses
the full relative path as the skill-path (`skill://acme/billing/refunds/SKILL.md`). Two
spec rules apply (the server serves violations anyway but logs a warning, since it exists
to test the gateway):

- the **final** path segment must equal `frontmatter.name`
- a `SKILL.md` must not appear inside another skill's directory (skills don't nest,
  only paths do)

Every file in a skill folder is published, via `rglob("*")` — there is no allowlist and
`.gitignore` is not consulted. So importing or running a skill's script in place leaves a
`scripts/__pycache__/*.pyc` that becomes a real MCP resource on the next restart. Clear
them before starting the server:

```bash
find skills -name __pycache__ -type d -prune -exec rm -rf {} +
```

## Notes

- The July-8 spec places the extension at top-level `capabilities.extensions`; the Python
  SDK has no native API for that yet, so this server uses `experimental` as the marker.
- `resources/directory/read` is not implemented (net-new in the spec); this server serves
  each file as an individual resource.
