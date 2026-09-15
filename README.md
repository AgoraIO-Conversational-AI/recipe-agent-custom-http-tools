# Agora Conversational AI — Custom HTTP Tools Recipe (Python)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![Bun](https://img.shields.io/badge/bun-latest-black)](https://bun.sh/)

The **custom HTTP tools** recipe in the Agora Conversational AI recipes family.
It demonstrates Engine's inline LLM REST tools capability: a managed OpenAI
model selects a function, and Agora Engine calls the HTTP endpoint declared
directly in that function's SDK configuration. The JSON result is returned to
the LLM, which speaks a natural response.

This capability is separate from MCP: it uses inline `OpenAI.tools` definitions,
not `mcp_servers` or an MCP transport. It is also separate from a custom LLM
tool loop because Agora Engine executes the REST request.

The recipe includes three deterministic mock business endpoints:

- `GET /tools/orders/{order_id}` — look up an order
- `POST /tools/tickets` — create and store a support ticket
- `GET /tools/tickets/{ticket_id}` — retrieve a created ticket

**Pipeline:** `DeepgramSTT(nova-3, en)` → `OpenAI(gpt-4o-mini, inline tools)` → `MiniMaxTTS`

No external model API key is required. `HTTP_TOOLS_API_KEY` is a random shared
secret for authenticating Engine requests to the example tool endpoints.

## Prerequisites

- [Python 3.10+](https://www.python.org/)
- [Bun](https://bun.sh/)
- [Agora CLI](https://github.com/AgoraIO/cli) — makes configuring an App ID and App Certificate easy
- [ngrok](https://ngrok.com/) or another HTTPS tunnel — Agora Engine must reach the tool endpoints

The same commands work on macOS, Linux, and Windows. On macOS/Linux, setup uses
`python3`; on Windows, it uses the Python launcher (`py`) or `python`. WSL and
virtualenv activation are not required.

## Run It

```bash
# 1. Install web dependencies and create the server Python venv
bun run setup

# 2. Add Agora credentials, or edit server/.env.local by hand
agora login
agora project use <your-project>          # select which project to use
agora project env write server/.env.local # writes App ID + Certificate

# 3. Expose the backend. Agora Engine calls /tools on this tunnel.
ngrok http 8000

# 4. Add the public URL and a random shared secret to server/.env.local
#    HTTP_TOOLS_BASE_URL=https://<your-tunnel>.ngrok-free.dev
#    HTTP_TOOLS_API_KEY=<random-secret>

# 5. Run backend + web
bun run dev
```

Open [http://localhost:3000](http://localhost:3000) → **Start Conversation** →
ask “Where is order A-1001?”, then “Create a ticket because order A-1001 is
late.” Ask for the returned ticket ID to verify the same ticket can be retrieved.

### Working from a clone

If you cloned this repo rather than scaffolding via the Agora CLI, the steps
above are complete as written: `bun run setup` creates the Python venv and
installs web dependencies, then `bun run dev` starts both services. A
conversation additionally needs Agora credentials, a public HTTPS tool URL,
and the tool API key in `server/.env.local`.

Services:

- Frontend — http://localhost:3000
- Backend + mock REST tools — http://localhost:8000 (including `/tools`)
- API docs — http://localhost:8000/docs

## Deploy

Deploy `web` (Next.js) and `server` (a publicly reachable FastAPI backend).
Set `HTTP_TOOLS_BASE_URL` to the backend's HTTPS base URL. Set
`AGENT_BACKEND_URL` in the web deployment so the Next rewrites reach the same
backend.

A backend-only Docker image is published to
`ghcr.io/AgoraIO-Conversational-AI/recipe-agent-custom-http-tools` on `v*` tags.
It exposes port 8000 and serves both the lifecycle API and `/tools`.

> **Co-public caveat:** exposing `/tools` also exposes the lifecycle routes on
> port 8000. The sample authenticates `/tools` with `X-Tool-API-Key`; add
> application authentication and rate limiting to the lifecycle routes before
> production deployment.

## Environment variables

Backend env file: [`server/.env.example`](server/.env.example).

| Variable | Required | Default | Notes |
| --- | :---: | :---: | --- |
| `AGORA_APP_ID` | Yes | — | Agora Console → Project → App ID |
| `AGORA_APP_CERTIFICATE` | Yes | — | Agora Console → Project → App Certificate; server only |
| `HTTP_TOOLS_BASE_URL` | Yes | — | Public HTTPS base URL for this server, without `/tools` |
| `HTTP_TOOLS_API_KEY` | Yes | — | Random shared secret sent as `X-Tool-API-Key` |
| `HTTP_TOOLS_TIMEOUT_MS` | | `10000` | SDK-supported range: 1000–100000 ms |
| `OPENAI_MODEL` | | `gpt-4o-mini` | Agora-managed OpenAI model |
| `AGENT_GREETING` | | built-in | Optional opening line override |
| `PORT` | | `8000` | FastAPI backend port |
| `AGENT_BACKEND_URL` | web deploy only | — | Backend URL used by deployed Next.js `/api/*` rewrites |

## Commands

```bash
bun run setup                 # install web deps + create server/ venv
bun run dev                   # run backend (:8000, including /tools) + web (:3000)

bun run doctor                # prerequisite check (no credentials needed)
bun run doctor:local          # + local env, credentials, and public HTTPS URL checks

bun run verify                # web-only gate (no Agora credentials needed)
bun run verify:backend:pytest # standalone backend tests, no Agora cloud calls
bun run verify:local          # full local gate: backend tests + smoke tests + web build
bun run clean                 # remove venvs and build artifacts
```

Tests run standalone with no Agora cloud session: `pytest` in `server/` and
`bun test` in `web/`. CI runs them on Linux, macOS, and Windows with Python
3.10 and 3.13 where applicable.

The mock tool endpoint can also be checked independently:

```bash
TOOL_BASE_URL="https://your-tunnel.ngrok-free.dev"
TOOL_API_KEY="replace-with-the-value-from-server-env-local"
curl -H "X-Tool-API-Key: $TOOL_API_KEY" \
  "$TOOL_BASE_URL/tools/orders/A-1001"
```

## Inline tool contract

The managed LLM receives normal function definitions plus an inline `server`
configuration. `with_tools()` is also required to enable tool execution at the
Engine level:

```python
llm = OpenAI(
    model="gpt-4o-mini",
    tools=[{
        "type": "function",
        "function": {
            "name": "lookup_order",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
        "execution": {"mode": "sync"},
        "server": {
            "method": "GET",
            "url": "https://example.com/orders/{{args.order_id}}",
            "headers": {"X-Tool-API-Key": "secret"},
            "timeout_ms": 10000,
        },
    }],
    template_variables={"requester": "inline-rest-tools-recipe"},
)
agent = Agent(client=client).with_llm(llm).with_tools()
```

URLs and POST bodies support `{{args.name}}`,
`{{template_variables.name}}`, and `{{tool_call_id}}`. Headers support constants,
template variables, and the tool call ID, but not `args` placeholders. The
current execution mode is `sync`; `server.body` is only valid for POST tools.

## Architecture

```text
Browser (localhost:3000)
  │  fetch /api/*
  ▼
Next.js  ──rewrite──▶  Agent backend (server/, localhost:8000)
                          │  starts session with OpenAI.tools + with_tools()
                          ▼
                       Agora ConvoAI Engine
                          │  model selects a function
                          │  Engine renders templates and sends GET/POST
                          ▼
                       Public HTTPS /tools endpoint
                          │  authenticated JSON result
                          ▼
                       Engine → LLM → MiniMax TTS → RTC user
```

The browser does not execute tools. Agora Engine calls
`HTTP_TOOLS_BASE_URL` directly, so a local `localhost` URL cannot be used for a
cloud session. See [ARCHITECTURE.md](./ARCHITECTURE.md).

## What You Get

- A **Next.js** web client (:3000) that drives the RTC/RTM lifecycle and only calls `/api/*`.
- A **FastAPI** backend (:8000) that owns Agora token generation, agent sessions, and the mock REST endpoints.
- The standard `/api/get_config` · `/api/startAgent` · `/api/stopAgent` contract through Next rewrites.
- Managed **Deepgram STT**, **OpenAI LLM**, and **MiniMax TTS** with no external model API key.
- Three authenticated inline REST tools covering GET URL arguments, POST bodies, template variables, and tool call IDs.

## How It Works

1. The browser calls `/api/get_config`; Next rewrites the request to FastAPI,
   which mints an Agora token from the App ID and App Certificate.
2. The browser joins RTC, then calls `/api/startAgent`. The backend starts an
   SDK session with managed OpenAI, the inline tool definitions, and
   `enable_tools`.
3. The user speaks. Agora runs Deepgram STT and sends the transcript to the LLM.
4. When the LLM selects a function, Engine renders the tool templates and calls
   the configured public HTTPS endpoint with `X-Tool-API-Key`.
5. Engine returns the endpoint's JSON to the LLM. MiniMax TTS speaks the final
   response in the RTC channel.
6. The demo backend keeps created tickets in process so the user can ask for a
   returned ticket ID and retrieve the same ticket. Restarting the backend clears them.
7. `/api/stopAgent` stops the active session, with the SDK's stateless stop path
   available as a fallback.

### Replacing the mock

Replace the in-process demo handlers in
[`server/src/http_tools.py`](server/src/http_tools.py) or point the inline
`server.url` values at your own HTTPS APIs. The demo ticket store is not durable;
use your business system for production. Keep each tool's JSON schema, URL/body
templates, authentication, and response contract aligned with the target service.

## Repo Map

- `web/` — Next.js frontend (:3000); RTC/RTM lifecycle and UI.
- `server/` — FastAPI backend (:8000); Agora tokens, agent lifecycle, and mock REST tools.
- `server/src/http_tools.py` — inline SDK tool definitions and `/tools` handlers.
- `ARCHITECTURE.md` — system shape and component boundaries.
- `AGENTS.md` — guide for coding agents working in this repo.

## Security

Use HTTPS, authenticate every request, validate tool arguments, apply
least-privilege credentials, rate-limit endpoints, and redact sensitive data
from logs. Do not put secrets in URLs or LLM-generated function arguments.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `doctor:local` rejects the tool URL | Use a public `https://` URL; localhost and plain HTTP are not accepted. |
| Agent starts but tools are never called | Confirm the tunnel points to the running backend and `HTTP_TOOLS_BASE_URL` does not include `/tools`. |
| Tool calls return 401 | Use the same `HTTP_TOOLS_API_KEY` in the SDK tool headers and backend environment. |
| A created demo ticket cannot be found | Demo tickets are kept in process and are cleared when the backend restarts. Create a new ticket or connect a durable business API. |
| The deployed web app cannot start an agent | Set `AGENT_BACKEND_URL` to the public backend URL and rebuild the web app. |
| Local verification reports a missing venv | Run `bun run setup`. |

## More Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [AGENTS.md](./AGENTS.md)
- [server/README.md](./server/README.md)

## License

Released under the [MIT License](./LICENSE).
