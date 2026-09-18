# Agent Development Guide

This repository is the **custom HTTP tools** recipe. It shows Engine's inline
synchronous HTTP tools configured on either the managed OpenAI LLM or OpenAI
Realtime MLLM, a capability that is separate from MCP.

## System shape

- `server/` is a FastAPI backend on port 8000. It owns token generation and
  session lifecycle through `agora-agents`.
- `server/src/http_tools.py` defines the three inline REST tool dictionaries and
  the deterministic `/tools` demo API, including an in-process create/query
  ticket lifecycle that resets when the backend restarts.
- `web/` is the standard Next.js RTC/RTM client and calls `/api/*` rewrites.
- `HTTP_TOOLS_BASE_URL` must be publicly reachable by Agora Engine.

## SDK contract

`OpenAI.tools` and `OpenAIRealtime.tools` accept the same list of dictionaries
with `function` and `server` fields. The server method is `GET` or `POST`; the
only execution mode currently supported is `sync`. Both paths must call
`.with_tools()` so the Engine-level `enable_tools` flag is true. Pipeline is the
default and optionally supports `OPENAI_API_KEY` / `OPENAI_BASE_URL`; Realtime
requires the separate `OPENAI_REALTIME_API_KEY`.

Keep the tool schema and URL/body templates aligned with the SDK source. Do not
invent MCP transports or an OpenAI-compatible `/chat/completions` endpoint in
this recipe.

Before submitting Recipe changes, use a formally released `agora-agents`
version whose AgentKit vendors accept and serialize these tools on both LLM and
MLLM paths. Source dependencies are for local development only and must not be
submitted.

## Security

The sample uses `X-Tool-API-Key` as a minimal service-to-service guard. Never
log the key or put it in a URL. Production services should use HTTPS and their
normal authentication, authorization, rate limiting, validation, and redaction.

## Commands

```bash
bun run setup
bun run dev
bun run verify:backend
bun run verify:backend:pytest
bun run verify:local:tools
bun run verify:web:build
```
