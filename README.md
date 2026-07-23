# mcp-skills-server

A minimal **Skills Over MCP (SEP-2640)** server for testing the Airia MCP Gateway.

It serves the skills in [`skills/`](./skills) over **Streamable HTTP** as MCP resources:

- `skill://index.json` — the July-8 index (`url` / `digest` / `frontmatter`)
- `skill://<name>/<file>` — every file in a skill folder, read on demand

It advertises `capabilities.resources` and the skills extension under
`capabilities.experimental` (`io.modelcontextprotocol/skills`), matching what real hosts
like skillsovermcp.com do today.

## Skills included

| Skill | Shape | Files |
|-------|-------|-------|
| `hello-skill` | single-file | `SKILL.md` |
| `csv-insights` | multi-file | `SKILL.md`, `references/GUIDE.md`, `scripts/summarize.py` |
| `suffix-stamp` | script-only | `SKILL.md`, `scripts/stamp.py` |

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
(`name` + `description`). The server rebuilds the index on restart. The folder name should
match `frontmatter.name`.

## Notes

- The July-8 spec places the extension at top-level `capabilities.extensions`; the Python
  SDK has no native API for that yet, so this server uses `experimental` as the marker.
- `resources/directory/read` is not implemented (net-new in the spec); this server serves
  each file as an individual resource.
