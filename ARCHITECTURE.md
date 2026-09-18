# Architecture — Custom HTTP Tools Recipe

This recipe demonstrates **inline LLM REST tools**, which are parallel to MCP
and configured directly in `OpenAI.tools` or `OpenAIRealtime.tools`. It supports
the normal Agora voice cascade and an OpenAI Realtime MLLM path.

```text
Browser
  │  Next.js /api proxy
  ▼
FastAPI agent backend
  │  Agent SDK creates the session
  ▼
Agora ConvoAI Engine
  │  model chooses a function
  │  Engine renders {{args.*}} and sends the HTTP request
  ▼
Business REST endpoint (public HTTPS)
  │  JSON result
  └──────────────▶ Engine → selected model path → RTC client
```

## Boundaries

- `server/src/agent.py` builds the selected Pipeline or Realtime SDK agent and
  the shared tool list.
- `server/src/http_tools.py` contains the tool schema builder and mock target
  routes. Its demo tickets live in process and can be queried until the backend
  restarts. The target routes can be replaced by a separate business service.
- `server/src/server.py` owns token generation and agent lifecycle routes.
- `web/` is the standard RTC/RTM client and does not execute tools.

## Tool rendering

The SDK supports these placeholders in URLs and POST bodies:

- `{{args.name}}` from the model function arguments
- `{{template_variables.name}}` from the Pipeline LLM configuration; Realtime
  uses a literal `requester` because its SDK vendor has no such field
- `{{tool_call_id}}` from the current call

Headers accept constants, template variables, or the tool call ID. They do not
accept `args` placeholders. `GET` tools put their arguments in the URL. `POST`
tools may provide a JSON `server.body`; only fields in that body are sent.

## Runtime and security

Engine must reach `HTTP_TOOLS_BASE_URL` directly. A local `localhost` URL works
for neither Engine nor a remote deployment, so use ngrok or another HTTPS
tunnel during local testing. The sample sends `X-Tool-API-Key` and validates it
with a constant-time comparison. Real services should use their normal
service-to-service authentication, rate limits, input validation, and logging
redaction.
