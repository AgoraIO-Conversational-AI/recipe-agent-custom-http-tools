"""Agora agent wiring for the inline REST tools recipe."""

import json
import logging
import os
import re
from typing import Any, Dict, Literal, Optional

import httpx
from agora_agent import Area, AsyncAgora
from agora_agent.agentkit import Agent as AgoraAgent
from agora_agent.agentkit.vendors import (
    DeepgramSTT,
    MiniMaxTTS,
    OpenAI,
    OpenAIRealtime,
)

from http_tools import build_inline_tools

logger = logging.getLogger("uvicorn.error")

_TOKEN_PREFIX_LENGTH = 8
_REDACTED_HEADERS = {
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "x-tool-api-key",
}
_REDACTED_BODY_KEYS = {
    "api_key",
    "app_certificate",
    "authorization",
    "customer_secret",
    "key",
    "password",
    "secret",
}


def _token_preview(value: str) -> str:
    visible = value[:_TOKEN_PREFIX_LENGTH]
    return f"{visible}*** (length={len(value)})"


def _authorization_preview(value: str) -> str:
    prefix = "agora token="
    if value.startswith(prefix):
        token = value[len(prefix) :]
        return f"{prefix}{_token_preview(token)}"
    return "***"


def _safe_request_headers(headers: httpx.Headers) -> Dict[str, str]:
    safe_headers: Dict[str, str] = {}
    for name, value in headers.items():
        normalized = name.lower()
        if normalized == "authorization":
            safe_headers[name] = _authorization_preview(value)
        elif normalized in _REDACTED_HEADERS:
            safe_headers[name] = "***"
        else:
            safe_headers[name] = value
    return safe_headers


def _safe_request_url(url: httpx.URL) -> str:
    return re.sub(r"(/v2/projects/)[^/]+", r"\1<redacted>", str(url))


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _safe_body_value(value: Any, *, key: Optional[str] = None) -> Any:
    normalized = _normalized_key(key) if key else ""
    if normalized == "token" and isinstance(value, str):
        return _token_preview(value)
    if (
        normalized in _REDACTED_BODY_KEYS
        or normalized.endswith("_api_key")
        or normalized.endswith("_access_token")
    ):
        return "***"
    if isinstance(value, dict):
        return {
            child_key: _safe_body_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_safe_body_value(item) for item in value]
    return value


def _safe_request_body(request: httpx.Request) -> Any:
    if not request.content:
        return None
    try:
        return _safe_body_value(json.loads(request.content))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "<non-JSON body omitted>"


async def _log_engine_request(request: httpx.Request) -> None:
    logger.info(
        "Agora Engine request method=%s url=%s headers=%s body=%s",
        request.method,
        _safe_request_url(request.url),
        _safe_request_headers(request.headers),
        json.dumps(_safe_request_body(request), ensure_ascii=True),
    )

AGENT_INSTRUCTIONS = """You are a helpful voice assistant for an order support demo.

Use lookup_order when the user asks about an order and has an order ID.
Use create_support_ticket when the user asks to report an issue or request help.
Use get_support_ticket when the user asks for the status or details of an existing ticket ID.
Read the tool result back in a concise, natural sentence. Never invent order or
ticket details when a tool call is available.
Ticket IDs use the format T-1234. When saying a ticket ID, say the letter T,
then read each digit separately.
"""

AgentMode = Literal["pipeline", "realtime"]
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1/chat/completions"
TOOL_REQUESTER = "inline-rest-tools-recipe"


class Agent:
    """High-level wrapper around the Agora Agent SDK.

    The tools are declared on the selected OpenAI LLM or Realtime MLLM and
    executed synchronously by Agora Engine. The Engine, rather than the browser,
    calls the public REST endpoint configured by ``HTTP_TOOLS_BASE_URL``.
    """

    def __init__(self):
        self.app_id = os.getenv("AGORA_APP_ID")
        self.app_certificate = os.getenv("AGORA_APP_CERTIFICATE")
        self.greeting = os.getenv(
            "AGENT_GREETING",
            "Hi! I can look up an order or create a support ticket for you.",
        )
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL")
        self.openai_realtime_api_key = os.getenv("OPENAI_REALTIME_API_KEY")
        self.openai_realtime_model = os.getenv(
            "OPENAI_REALTIME_MODEL", "gpt-realtime"
        )
        self.http_tools_base_url = os.getenv("HTTP_TOOLS_BASE_URL")
        self.http_tools_api_key = os.getenv("HTTP_TOOLS_API_KEY")
        self.http_tools_timeout_ms = int(os.getenv("HTTP_TOOLS_TIMEOUT_MS", "10000"))

        if not self.app_id or not self.app_certificate:
            raise ValueError("AGORA_APP_ID and AGORA_APP_CERTIFICATE are required")
        if not self.http_tools_base_url:
            raise ValueError(
                "HTTP_TOOLS_BASE_URL is required (public HTTPS URL of this server, "
                "for example https://<tunnel>.ngrok-free.dev)"
            )
        if not self.http_tools_api_key:
            raise ValueError(
                "HTTP_TOOLS_API_KEY is required so the REST tool endpoint can be protected"
            )
        if not 1000 <= self.http_tools_timeout_ms <= 100000:
            raise ValueError("HTTP_TOOLS_TIMEOUT_MS must be between 1000 and 100000")

        self._http_client = httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,
            event_hooks={"request": [_log_engine_request]},
        )
        self.client = AsyncAgora(
            area=Area.US,
            app_id=self.app_id,
            app_certificate=self.app_certificate,
            httpx_client=self._http_client,
        )
        self._sessions: Dict[str, Any] = {}

    async def start(
        self,
        channel_name: str,
        agent_uid: int,
        user_uid: int,
        output_audio_codec: Optional[str] = None,
        agent_mode: AgentMode = "pipeline",
    ) -> Dict[str, Any]:
        """Start a Pipeline or Realtime agent with inline REST tools."""
        if not channel_name or not str(channel_name).strip():
            raise ValueError("channel_name is required and cannot be empty")
        if agent_uid <= 0:
            raise ValueError("agent_uid is required and cannot be empty")
        if user_uid <= 0:
            raise ValueError("user_uid is required and cannot be empty")
        if agent_mode not in ("pipeline", "realtime"):
            raise ValueError("agent_mode must be 'pipeline' or 'realtime'")
        if agent_mode == "realtime" and not self.openai_realtime_api_key:
            raise ValueError("OPENAI_REALTIME_API_KEY is required for realtime mode")

        tools = build_inline_tools(
            self.http_tools_base_url,
            self.http_tools_api_key,
            timeout_ms=self.http_tools_timeout_ms,
            # OpenAIRealtime has no template_variables configuration field.
            requester=(
                TOOL_REQUESTER if agent_mode == "realtime"
                else "{{template_variables.requester}}"
            ),
        )

        parameters = {
            "audio_scenario": "chorus",
            "data_channel": "rtm",
            "enable_error_message": True,
            "enable_metrics": True,
        }
        if isinstance(output_audio_codec, str) and output_audio_codec.strip():
            parameters["output_audio_codec"] = output_audio_codec.strip()

        agent_options = {
            "client": self.client,
            "greeting": self.greeting,
            "failure_message": "Please wait a moment.",
            "max_history": 50,
            "advanced_features": {"enable_rtm": True},
            "parameters": parameters,
        }
        if agent_mode == "pipeline":
            agent_options["instructions"] = AGENT_INSTRUCTIONS
            agent_options["turn_detection"] = {
                "config": {
                    "speech_threshold": 0.5,
                    "start_of_speech": {
                        "mode": "vad",
                        "vad_config": {
                            "interrupt_duration_ms": 160,
                            "prefix_padding_ms": 300,
                        },
                    },
                    "end_of_speech": {
                        "mode": "vad",
                        "vad_config": {"silence_duration_ms": 480},
                    },
                },
            }
        agora_agent = AgoraAgent(**agent_options)

        # with_tools() is required in addition to LLM.tools. It sets the
        # Engine-level enable_tools flag that permits tool execution.
        if agent_mode == "pipeline":
            llm_options = {
                "model": self.openai_model,
                "system_messages": [{"role": "system", "content": AGENT_INSTRUCTIONS}],
                "greeting_message": self.greeting,
                "max_history": 15,
                "max_tokens": 1024,
                "temperature": 0.2,
                "tools": tools,
                "template_variables": {"requester": TOOL_REQUESTER},
            }
            if self.openai_api_key:
                llm_options["api_key"] = self.openai_api_key
                llm_options["base_url"] = (
                    self.openai_base_url or DEFAULT_OPENAI_BASE_URL
                )
            llm = OpenAI(**llm_options)
            stt = DeepgramSTT(model="nova-3", language="en")
            tts = MiniMaxTTS(
                model="speech_2_6_turbo",
                voice_id="English_captivating_female1",
            )
            agora_agent = (
                agora_agent.with_stt(stt).with_llm(llm).with_tts(tts).with_tools()
            )
        else:
            mllm = OpenAIRealtime(
                api_key=self.openai_realtime_api_key,
                model=self.openai_realtime_model,
                instructions=AGENT_INSTRUCTIONS,
                greeting_message=self.greeting,
                failure_message="Please wait a moment.",
                turn_detection={"mode": "server_vad"},
                tools=tools,
            )
            agora_agent = agora_agent.with_mllm(mllm).with_tools()

        session = agora_agent.create_async_session(
            channel=channel_name,
            agent_uid=str(agent_uid),
            remote_uids=[str(user_uid)],
            enable_string_uid=False,
            idle_timeout=30,
            expires_in=3600,
        )

        logger.info(
            "Starting inline REST tools agent channel=%s agent_uid=%s user_uid=%s mode=%s tools_base=%s",
            channel_name,
            agent_uid,
            user_uid,
            agent_mode,
            self.http_tools_base_url,
        )
        try:
            agent_id = await session.start()
        except Exception:
            logger.exception(
                "Failed to start inline REST tools agent channel=%s agent_uid=%s user_uid=%s",
                channel_name,
                agent_uid,
                user_uid,
            )
            raise

        self._sessions[agent_id] = session
        return {
            "agent_id": agent_id,
            "channel_name": channel_name,
            "status": "started",
            "agent_mode": agent_mode,
        }

    async def stop(self, agent_id: str) -> None:
        """Stop a running agent, falling back to the stateless SDK path."""
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id is required and cannot be empty")

        session = self._sessions.pop(agent_id, None)
        if session:
            try:
                await session.stop()
                return
            except Exception:
                logger.warning("Active session stop failed; using fallback", exc_info=True)
        await self.client.stop_agent(agent_id)

    async def close(self) -> None:
        """Release the HTTP client owned by this agent wrapper."""
        await self._http_client.aclose()
