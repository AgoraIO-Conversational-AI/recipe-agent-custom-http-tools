# Agora Agent Backend — Custom HTTP Tools Recipe

FastAPI service that owns Agora token generation and agent session lifecycle for
the custom HTTP tools recipe. It is the service the web client reaches through
the Next.js `/api/*` rewrite proxy on port 8000. It also serves the example
`/tools` endpoints called directly by Agora Engine.

## What's different from the base quickstart

The managed `OpenAI` LLM includes inline function definitions with `server`
configuration. When the model selects a function, Agora Engine renders the
configured templates and sends the HTTP request. This is separate from MCP:
there is no `mcp_servers` configuration or MCP transport.

**Pipeline:** `DeepgramSTT(nova-3, en)` → `OpenAI(gpt-4o-mini, inline tools)` → `MiniMaxTTS`

`src/http_tools.py` provides deterministic mock endpoints for order lookup and
a create-then-query support ticket flow. Tickets are kept in the current backend
process and cleared on restart. The backend must be exposed through public HTTPS
for end-to-end testing because Engine, not the browser, calls those routes.

## Run

Use the repo-root `README.md` for the full local flow (`bun run dev`). To work
on this module directly, use the root commands below; virtualenv activation is
not required:

```shell
bun run setup:server
bun run backend
```

## Environment

`server/.env.example` is the template. Required:

- `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE` — Agora project credentials.
- `HTTP_TOOLS_BASE_URL` — public HTTPS base URL of this service, without
  `/tools`. Agora Engine calls it directly; localhost and plain HTTP are invalid.
- `HTTP_TOOLS_API_KEY` — shared secret sent as `X-Tool-API-Key` and validated by
  the mock endpoints.

Optional:

| Variable | Default | Notes |
| --- | :---: | --- |
| `HTTP_TOOLS_TIMEOUT_MS` | `10000` | SDK-supported range: 1000–100000 ms |
| `OPENAI_MODEL` | `gpt-4o-mini` | Agora-managed OpenAI model |
| `AGENT_GREETING` | built-in | Optional opening line override |
| `PORT` | `8000` | Backend port |

## API

- `GET /get_config` — token + channel/UID config
- `POST /startAgent` — start an agent session with inline REST tools
- `POST /stopAgent` — stop an agent session
- `GET /tools/health` — tool endpoint health check
- `GET /tools/orders/{order_id}` — deterministic order lookup
- `POST /tools/tickets` — create and store a demo support ticket
- `GET /tools/tickets/{ticket_id}` — retrieve a created demo ticket

The `/tools` routes require `X-Tool-API-Key`. The repo-root
`bun run verify:local:fastapi` checks the lifecycle routes with a fake agent;
`bun run verify:local:tools` checks the mounted tool routes; and
`bun run verify:backend:pytest` covers SDK construction, validation, endpoint
authentication, and session stop behavior. None starts a live Agora session.

## Key files

| File | Purpose |
| --- | --- |
| `src/server.py` | FastAPI app, lifecycle routes, and token generation |
| `src/agent.py` | Agent SDK pipeline, inline tools, and session lifecycle |
| `src/http_tools.py` | Inline tool dictionaries and mock `/tools` handlers |
| `scripts/run_fake_server.py` | Deterministic lifecycle server for proxy tests |
| `tests/` | Backend contract and lifecycle tests |
