"""Minimal SEP-2640 "Skills Over MCP" server for Airia gateway testing.

Serves skills from ./skills over Streamable HTTP, supporting every discovery mechanism
observed in the wild (the draft churns weekly, so serve them all):

  - resources/list                -> enumerates every skill file as a plain resource.
                                     This is what goose-cli 1.42.0 ACTUALLY uses (verified
                                     from this server's RPC log, 2026-07-20): plain
                                     resources/list + direct resources/read of SKILL.md —
                                     it never called skills/list.
  - skill://index.json            -> the July-8 SEP-2640 index (url / digest / frontmatter),
                                     the shape the Airia gateway synthesizes/aggregates.
  - skills/list (method)          -> {"skills": [{uri, frontmatter, resources[]}]} with
                                     per-file digests; kept for experimentation (no host
                                     has been observed calling it).
  - skill://<skill-path>/<file>   -> each file in a skill folder, read on demand. The
                                     skill-path may be a single segment (hello-skill) or
                                     nested to arbitrary depth (acme/billing/refunds),
                                     per the 2026-07 draft's nested-skill-path rules.

Run:  uv run server.py      (listens on http://127.0.0.1:8000/mcp)
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
import yaml
from mcp.server.lowlevel import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
import mcp.types as types
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.routing import Mount

SKILLS_DIR = Path(__file__).parent / "skills"
SKILLS_EXTENSION = "io.modelcontextprotocol/skills"
TEXT_SUFFIXES = {".md", ".py", ".txt", ".json", ".csv", ".yaml", ".yml", ".toml"}

# ---------------------------------------------------------------------------
# JSON-RPC request logging
#
# uvicorn's access log only shows `POST /mcp ... 200 OK`, which hides the
# actual MCP call. The middleware below buffers each POST body, parses the
# JSON-RPC envelope, and logs the method + a short param summary. The client
# `host:port` is included so each line correlates with uvicorn's access line.
# ---------------------------------------------------------------------------
logger = logging.getLogger("mcp.rpc")


def _configure_logging() -> None:
    """Attach a formatted handler to the mcp.rpc logger (once)."""
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s  MCP  %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _summarize_params(method: str, params: dict) -> str:
    """Pull the most useful field out of a JSON-RPC params object per method."""
    if not isinstance(params, dict):
        return ""
    if method in ("resources/read", "resources/subscribe", "resources/unsubscribe"):
        return f"uri={params.get('uri')}"
    if method == "tools/call":
        return f"tool={params.get('name')}"
    if method == "prompts/get":
        return f"prompt={params.get('name')}"
    if method == "initialize":
        info = params.get("clientInfo") or {}
        return f"client={info.get('name')} {info.get('version')}".rstrip()
    return ""


def _log_rpc_message(peer: str, message) -> None:
    """Log one JSON-RPC object, or each object in a batch array."""
    if isinstance(message, list):
        for item in message:
            _log_rpc_message(peer, item)
        return
    if not isinstance(message, dict):
        return

    method = message.get("method")
    if method is None:  # a response, not a request/notification — nothing to log here
        return

    summary = _summarize_params(method, message.get("params") or {})
    if "id" in message:  # request (expects a response)
        logger.info("%s  → %-22s id=%-4s %s", peer, method, message.get("id"), summary)
    else:  # notification (fire-and-forget)
        logger.info("%s  → %-22s (notification) %s", peer, method, summary)
    logger.info("-" * 72)


def _parse_frontmatter(text: str) -> dict:
    """Return the YAML frontmatter of a SKILL.md as a dict (empty if none)."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            data = yaml.safe_load(parts[1]) or {}
            if isinstance(data, dict):
                return data
    return {}


def _mime_for(uri: str) -> str:
    if uri.endswith(".md"):
        return "text/markdown"
    if uri.endswith(".py"):
        return "text/x-python"
    if uri.endswith(".json"):
        return "application/json"
    guessed, _ = mimetypes.guess_type(uri)
    return guessed or "text/plain"


def _digest(path: Path) -> str:
    """SHA-256 of a file's raw bytes, formatted `sha256:<64 lowercase hex>` per SEP-2640."""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _find_skill_dirs(root: Path) -> list[Path]:
    """Recursively find every directory under `root` that holds a SKILL.md.

    SEP-2640 allows the skill-path to nest to arbitrary depth
    (`skill://acme/billing/refunds/SKILL.md`), but skills themselves must not
    nest: the skill directory is the boundary, so once a directory holds a
    SKILL.md its descendants belong to that skill and are not scanned further.
    """
    found: list[Path] = []

    def walk(directory: Path) -> None:
        if (directory / "SKILL.md").exists():
            found.append(directory)
            return
        for child in sorted(p for p in directory.iterdir() if p.is_dir()):
            walk(child)

    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        walk(child)
    return found


def load_skills() -> tuple[dict[str, Path], dict, dict]:
    """Walk skills/ and return (uri -> file path), the `skills/list` result, and the index.

    Skill directories may sit at the top of skills/ or nested at any depth; the
    skill-path in each URI is the directory's path relative to skills/. Per the
    spec, the final path segment must equal `frontmatter.name` (violations are
    served anyway, with a warning, since this is a test server).

    Two discovery payloads are built from the same walk:
      - the `skills/list` method result, `{"skills": [{uri, frontmatter, resources[]}]}`,
        with a per-file SHA-256 digest (experimental shape; no host observed calling it)
      - the July-8 SEP-2640 `skill://index.json` content,
        `{"skills": [{url, digest, frontmatter}]}` where `digest` covers SKILL.md only —
        the shape the Airia gateway implements
    """
    files: dict[str, Path] = {}
    skills: list[dict] = []
    index_entries: list[dict] = []

    for skill_dir in _find_skill_dirs(SKILLS_DIR):
        skill_md = skill_dir / "SKILL.md"
        skill_path = skill_dir.relative_to(SKILLS_DIR).as_posix()

        frontmatter = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        name = frontmatter.get("name", skill_dir.name)
        if name != skill_dir.name:
            logger.warning(
                "skill %s: frontmatter name %r != final path segment %r (SEP-2640 requires they match)",
                skill_path, name, skill_dir.name,
            )

        # resources[] must list every file of the skill exactly once, including SKILL.md.
        resources: list[dict] = []
        for file_path in sorted(skill_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.name == "SKILL.md" and file_path.parent != skill_dir:
                logger.warning(
                    "skill %s: nested SKILL.md at %s (SEP-2640 forbids skills inside skills)",
                    skill_path, file_path.relative_to(skill_dir).as_posix(),
                )
            rel = file_path.relative_to(skill_dir).as_posix()
            uri = f"skill://{skill_path}/{rel}"
            files[uri] = file_path
            resources.append({"uri": uri, "digest": _digest(file_path)})

        skills.append(
            {
                "uri": f"skill://{skill_path}/SKILL.md",
                "frontmatter": frontmatter,
                "resources": resources,
            }
        )

        index_entries.append(
            {
                "url": f"skill://{skill_path}/SKILL.md",
                "digest": _digest(skill_md),
                "frontmatter": frontmatter,
            }
        )

    return files, {"skills": skills}, {"skills": index_entries}


INDEX_URI = "skill://index.json"

FILES, SKILLS_LIST, SKILLS_INDEX = load_skills()

server = Server("mcp-skills-server")


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    # Enumerate the index plus every skill file. goose 1.42.0 discovers skills from
    # exactly this listing (then reads SKILL.md files directly by URI).
    resources = [
        types.Resource(
            uri=AnyUrl(INDEX_URI),
            name="index.json",
            mimeType="application/json",
        )
    ]
    for uri in FILES:
        resources.append(
            types.Resource(
                uri=AnyUrl(uri),
                name=uri.rsplit("/", 1)[-1],
                mimeType=_mime_for(uri),
            )
        )
    return resources


@server.read_resource()
async def read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
    key = str(uri)

    # The well-known July-8 index: generated, not a file on disk.
    if key == INDEX_URI:
        return [ReadResourceContents(content=json.dumps(SKILLS_INDEX), mime_type="application/json")]

    file_path = FILES.get(key)
    if file_path is None:
        raise ValueError(f"Unknown resource: {key}")

    mime = _mime_for(key)
    if file_path.suffix.lower() in TEXT_SUFFIXES:
        return [ReadResourceContents(content=file_path.read_text(encoding="utf-8"), mime_type=mime)]
    return [ReadResourceContents(content=file_path.read_bytes(), mime_type=mime)]


# Advertise the skills extension under capabilities.experimental (what real hosts such as
# skillsovermcp.com do today). The July-8 spec places it at top-level capabilities.extensions,
# but the Python SDK has no native API for that, so experimental is the pragmatic marker.
_original_init_options = server.create_initialization_options


def _create_initialization_options(notification_options=None, experimental_capabilities=None):
    return _original_init_options(notification_options, {SKILLS_EXTENSION: {}})


server.create_initialization_options = _create_initialization_options  # type: ignore[method-assign]

session_manager = StreamableHTTPSessionManager(app=server)


async def handle_mcp(scope, receive, send) -> None:
    await session_manager.handle_request(scope, receive, send)


@asynccontextmanager
async def lifespan(app: Starlette):
    async with session_manager.run():
        yield


_starlette = Starlette(routes=[Mount("/mcp", app=handle_mcp)], lifespan=lifespan)


async def _logging_receive(scope, receive):
    """Buffer the full request body, log its JSON-RPC content, then replay it.

    An ASGI body can only be consumed once, so we read every `http.request`
    event up front, log the parsed envelope, and hand back a `(receive, message)`
    pair: a `receive` callable that replays the buffered events before deferring
    to the original, plus the parsed JSON-RPC message (or None) so the caller can
    route on its `method` without re-reading the body.
    """
    events = []
    while True:
        event = await receive()
        events.append(event)
        if event["type"] != "http.request" or not event.get("more_body", False):
            break

    body = b"".join(e.get("body", b"") for e in events if e["type"] == "http.request")
    client = scope.get("client")
    peer = f"{client[0]}:{client[1]}" if client else "-"
    message = None
    if body:
        try:
            message = json.loads(body)
            _log_rpc_message(peer, message)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.info("%s  → POST /mcp (non-JSON body, %d bytes)", peer, len(body))

    queue = list(events)

    async def replay():
        return queue.pop(0) if queue else await receive()

    return replay, message


async def _send_json_rpc(send, req_id, result: dict, session_id: str | None) -> None:
    """Reply to a POST with a single application/json JSON-RPC response.

    Streamable HTTP lets a server answer a POSTed request with either an SSE
    stream or a lone `application/json` body; we use the latter. The session id,
    if the client sent one, is echoed back on the response.
    """
    payload = json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode("utf-8")
    headers = [(b"content-type", b"application/json")]
    if session_id:
        headers.append((b"mcp-session-id", session_id.encode("utf-8")))
    await send({"type": "http.response.start", "status": 200, "headers": headers})
    await send({"type": "http.response.body", "body": payload})


async def app(scope, receive, send):
    # Serve /mcp without the 307 redirect that Mount("/mcp") issues to /mcp/,
    # so clients (incl. the gateway) can POST to /mcp directly.
    if scope["type"] == "http" and scope.get("path") == "/mcp":
        scope = dict(scope, path="/mcp/", raw_path=b"/mcp/")

    # Log the JSON-RPC method + params for each POST (GET is the SSE stream).
    if scope["type"] == "http" and scope.get("method") == "POST":
        receive, message = await _logging_receive(scope, receive)

        # Answer `skills/list` (SEP-2640, 2026-07-13) here at the ASGI layer: the
        # low-level SDK validates incoming methods against a fixed ClientRequest union
        # and rejects unknown ones before any handler runs, so it can't route this.
        if isinstance(message, dict) and message.get("method") == "skills/list":
            headers = dict(scope.get("headers") or [])
            sid = headers.get(b"mcp-session-id")
            await _send_json_rpc(send, message.get("id"), SKILLS_LIST, sid.decode() if sid else None)
            return

    await _starlette(scope, receive, send)


if __name__ == "__main__":
    _configure_logging()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    print(f"Loaded {len(SKILLS_LIST['skills'])} skills, {len(FILES)} files. Serving at http://{host}:{port}/mcp")
    uvicorn.run(app, host=host, port=port)
