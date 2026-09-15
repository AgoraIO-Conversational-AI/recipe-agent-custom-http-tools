"""Contract tests for the SDK's inline REST tool dictionary shape."""

import pytest

from http_tools import build_inline_tools


def test_builds_get_and_post_tools_with_supported_templates():
    tools = build_inline_tools("https://demo.example/api/", "secret", timeout_ms=2500)

    assert [tool["function"]["name"] for tool in tools] == [
        "lookup_order",
        "create_support_ticket",
        "get_support_ticket",
    ]
    lookup, ticket, get_ticket = tools
    assert lookup["execution"] == {"mode": "sync"}
    assert lookup["server"] == {
        "method": "GET",
        "url": "https://demo.example/api/tools/orders/{{args.order_id}}",
        "headers": {"X-Tool-API-Key": "secret"},
        "timeout_ms": 2500,
    }
    assert ticket["server"]["method"] == "POST"
    assert ticket["server"]["url"] == "https://demo.example/api/tools/tickets"
    assert ticket["server"]["body"] == {
        "order_id": "{{args.order_id}}",
        "issue": "{{args.issue}}",
        "requester": "{{template_variables.requester}}",
        "tool_call_id": "{{tool_call_id}}",
    }
    assert ticket["function"]["parameters"]["type"] == "object"
    assert get_ticket["execution"] == {"mode": "sync"}
    assert get_ticket["server"] == {
        "method": "GET",
        "url": "https://demo.example/api/tools/tickets/{{args.ticket_id}}",
        "headers": {"X-Tool-API-Key": "secret"},
        "timeout_ms": 2500,
    }
    assert get_ticket["function"]["parameters"] == {
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
    }


@pytest.mark.parametrize("timeout", [999, 100001])
def test_rejects_timeout_outside_sdk_range(timeout):
    with pytest.raises(ValueError, match="between 1000 and 100000"):
        build_inline_tools("https://demo.example", "secret", timeout_ms=timeout)


def test_rejects_non_absolute_base_url():
    with pytest.raises(ValueError, match=r"absolute HTTP\(S\) URL"):
        build_inline_tools("localhost:8000", "secret")


def test_rejects_loopback_base_url():
    with pytest.raises(ValueError, match="publicly reachable"):
        build_inline_tools("http://127.0.0.1:8000", "secret")


def test_rejects_public_http_base_url():
    with pytest.raises(ValueError, match="HTTPS"):
        build_inline_tools("http://public.example", "secret")
