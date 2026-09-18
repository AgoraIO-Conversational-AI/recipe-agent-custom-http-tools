"""Inline REST tool definitions and their local demo endpoints.

The tool definitions are sent to the Agora Engine as part of the LLM or MLLM
configuration. Engine makes the HTTP requests; these FastAPI routes are only a
deterministic demo target and can be replaced with a business API.
"""

import hmac
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

TOOL_API_KEY_HEADER = "X-Tool-API-Key"
router = APIRouter(prefix="/tools", tags=["inline-rest-tools"])
logger = logging.getLogger("uvicorn.error")
_tickets: Dict[str, Dict[str, Any]] = {}
_next_ticket_number = 1000


def _allocate_ticket_id() -> str:
    """Allocate an unused, voice-friendly ticket ID for this process."""
    global _next_ticket_number

    for _ in range(9000):
        ticket_id = f"T-{_next_ticket_number}"
        _next_ticket_number = 1000 if _next_ticket_number == 9999 else _next_ticket_number + 1
        if ticket_id not in _tickets:
            return ticket_id
    raise HTTPException(status_code=503, detail="Ticket capacity reached")


def _base_url(value: str) -> str:
    """Normalize a public base URL while preserving its configured path."""
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("HTTP_TOOLS_BASE_URL must be an absolute HTTP(S) URL")
    if parsed.hostname and parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("HTTP_TOOLS_BASE_URL must be publicly reachable by Agora Engine")
    if parsed.scheme != "https":
        raise ValueError("HTTP_TOOLS_BASE_URL must use HTTPS")
    return normalized


def build_inline_tools(
    base_url: str,
    api_key: str,
    *,
    timeout_ms: int = 10000,
    requester: str = "{{template_variables.requester}}",
) -> list[Dict[str, Any]]:
    """Build the SDK's public inline REST tool dictionary shape."""
    if not api_key:
        raise ValueError("HTTP_TOOLS_API_KEY is required")
    if not 1000 <= timeout_ms <= 100000:
        raise ValueError("timeout_ms must be between 1000 and 100000")
    root = _base_url(base_url)
    headers = {TOOL_API_KEY_HEADER: api_key}
    execution = {"mode": "sync"}
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup_order",
                "description": "Look up the current status and total for an order.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "The order identifier, such as A-1001.",
                        }
                    },
                    "required": ["order_id"],
                },
            },
            "execution": execution,
            "server": {
                "method": "GET",
                "url": f"{root}/tools/orders/{{{{args.order_id}}}}",
                "headers": headers,
                "timeout_ms": timeout_ms,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_support_ticket",
                "description": "Create a support ticket for an order issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "issue": {
                            "type": "string",
                            "description": "A short description of the issue.",
                        },
                    },
                    "required": ["order_id", "issue"],
                },
            },
            "execution": execution,
            "server": {
                "method": "POST",
                "url": f"{root}/tools/tickets",
                "headers": headers,
                "body": {
                    "order_id": "{{args.order_id}}",
                    "issue": "{{args.issue}}",
                    "requester": requester,
                    "tool_call_id": "{{tool_call_id}}",
                },
                "timeout_ms": timeout_ms,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_support_ticket",
                "description": "Look up a previously created support ticket by its ticket ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticket_id": {
                            "type": "string",
                            "description": (
                                "The ticket ID returned when the ticket was created, in T-1234 "
                                "format. Normalize spoken input to this format, for example "
                                "'T four eight two one' to 'T-4821'."
                            ),
                        }
                    },
                    "required": ["ticket_id"],
                },
            },
            "execution": execution,
            "server": {
                "method": "GET",
                "url": f"{root}/tools/tickets/{{{{args.ticket_id}}}}",
                "headers": headers,
                "timeout_ms": timeout_ms,
            },
        },
    ]


def _check_key(received: Optional[str]) -> None:
    expected = os.getenv("HTTP_TOOLS_API_KEY")
    if not expected or not received or not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=401, detail="Invalid tool credentials")


class TicketRequest(BaseModel):
    order_id: str
    issue: str
    requester: Optional[str] = None
    tool_call_id: Optional[str] = None


def _normalize_ticket_id(value: str) -> str:
    normalized = value.strip().upper().replace(" ", "")
    digits = normalized[2:] if normalized.startswith("T-") else normalized
    if digits.startswith("T"):
        digits = digits[1:]
    if len(digits) == 4 and digits.isdigit():
        return f"T-{digits}"
    return normalized


@router.get("/orders/{order_id}")
async def lookup_order(
    order_id: str,
    x_tool_api_key: Optional[str] = Header(default=None, alias=TOOL_API_KEY_HEADER),
):
    _check_key(x_tool_api_key)
    normalized = order_id.strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="order_id is required")
    known = {
        "A-1001": {"status": "shipped", "total": 42.50, "currency": "USD"},
        "A-1002": {"status": "processing", "total": 18.00, "currency": "USD"},
    }
    order = known.get(normalized, {"status": "not_found"})
    return {"order_id": normalized, **order}


@router.post("/tickets")
async def create_support_ticket(
    request: TicketRequest,
    x_tool_api_key: Optional[str] = Header(default=None, alias=TOOL_API_KEY_HEADER),
):
    _check_key(x_tool_api_key)
    order_id = request.order_id.strip().upper()
    issue = request.issue.strip()
    if not order_id or not issue:
        raise HTTPException(status_code=400, detail="order_id and issue are required")
    ticket_id = _allocate_ticket_id()
    ticket = {
        "ticket_id": ticket_id,
        "status": "created",
        "order_id": order_id,
        "issue": issue,
        "requester": request.requester or "unknown",
        "tool_call_id": request.tool_call_id,
    }
    _tickets[ticket["ticket_id"]] = ticket
    logger.info(
        "[HTTP TOOL CALLED] create_support_ticket ticket_id=%s",
        ticket["ticket_id"],
    )
    return ticket


@router.get("/tickets/{ticket_id}")
async def get_support_ticket(
    ticket_id: str,
    x_tool_api_key: Optional[str] = Header(default=None, alias=TOOL_API_KEY_HEADER),
):
    _check_key(x_tool_api_key)
    normalized = _normalize_ticket_id(ticket_id)
    ticket = _tickets.get(normalized)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    logger.info("[HTTP TOOL CALLED] get_support_ticket ticket_id=%s", normalized)
    return ticket


@router.get("/health")
async def tools_health() -> Dict[str, str]:
    return {"status": "ok", "service": "inline-rest-tools"}
