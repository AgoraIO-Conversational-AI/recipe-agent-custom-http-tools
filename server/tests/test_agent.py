"""Agent validation and lifecycle tests without Agora cloud calls."""

import asyncio
import sys

import httpx
import pytest


def _fresh_agent_module():
    sys.modules.pop("agent", None)
    import agent

    return agent


@pytest.mark.parametrize(
    "missing",
    [
        "AGORA_APP_ID",
        "AGORA_APP_CERTIFICATE",
        "HTTP_TOOLS_BASE_URL",
        "HTTP_TOOLS_API_KEY",
    ],
)
def test_agent_requires_configuration(fake_env, monkeypatch, missing):
    monkeypatch.delenv(missing, raising=False)
    agent_module = _fresh_agent_module()

    with pytest.raises(ValueError):
        agent_module.Agent()


@pytest.mark.parametrize(
    ("channel_name", "agent_uid", "user_uid", "error"),
    [
        ("", 111, 222, "channel_name"),
        ("   ", 111, 222, "channel_name"),
        ("channel", 0, 222, "agent_uid"),
        ("channel", -1, 222, "agent_uid"),
        ("channel", 111, 0, "user_uid"),
        ("channel", 111, -1, "user_uid"),
    ],
)
def test_start_validates_session_arguments(
    fake_env, channel_name, agent_uid, user_uid, error
):
    instance = _fresh_agent_module().Agent()

    with pytest.raises(ValueError, match=error):
        asyncio.run(instance.start(channel_name, agent_uid, user_uid))


def test_stop_uses_active_session_then_stateless_fallback(fake_env, monkeypatch):
    agent_module = _fresh_agent_module()

    class FakeSession:
        def __init__(self):
            self.stopped = False

        async def stop(self):
            self.stopped = True

    instance = agent_module.Agent()
    session = FakeSession()
    instance._sessions["active-agent"] = session
    fallback_calls = []

    async def fake_stop_agent(agent_id):
        fallback_calls.append(agent_id)

    monkeypatch.setattr(instance.client, "stop_agent", fake_stop_agent)

    asyncio.run(instance.stop("active-agent"))
    assert session.stopped is True
    assert fallback_calls == []

    asyncio.run(instance.stop("unknown-agent"))
    assert fallback_calls == ["unknown-agent"]


def test_stop_falls_back_when_active_session_stop_fails(fake_env, monkeypatch):
    agent_module = _fresh_agent_module()

    class FailingSession:
        async def stop(self):
            raise RuntimeError("session stop failed")

    instance = agent_module.Agent()
    instance._sessions["active-agent"] = FailingSession()
    fallback_calls = []

    async def fake_stop_agent(agent_id):
        fallback_calls.append(agent_id)

    monkeypatch.setattr(instance.client, "stop_agent", fake_stop_agent)

    asyncio.run(instance.stop("active-agent"))
    assert fallback_calls == ["active-agent"]


def test_engine_request_log_keeps_token_prefix_and_redacts_secrets(fake_env):
    agent_module = _fresh_agent_module()
    request = httpx.Request(
        "POST",
        "https://api.example/v2/projects/secret-app-id/join",
        headers={
            "Authorization": "agora token=007abcdefghijk",
            "X-Tool-API-Key": "secret-tool-key",
        },
        json={
            "properties": {
                "token": "007bodytokenvalue",
                "llm": {
                    "api_key": "secret-llm-key",
                    "params": {"model": "gpt-4o-mini"},
                    "tools": [
                        {
                            "server": {
                                "headers": {"X-Tool-API-Key": "secret-tool-key"}
                            }
                        }
                    ],
                },
            }
        },
    )

    safe_headers = agent_module._safe_request_headers(request.headers)
    safe_url = agent_module._safe_request_url(request.url)
    safe_body = agent_module._safe_request_body(request)

    assert safe_headers["authorization"] == "agora token=007abcde*** (length=14)"
    assert safe_headers["x-tool-api-key"] == "***"
    assert "secret-app-id" not in safe_url
    assert "secret-tool-key" not in str(safe_headers)
    assert safe_body["properties"]["token"] == "007bodyt*** (length=17)"
    assert safe_body["properties"]["llm"]["api_key"] == "***"
    assert (
        safe_body["properties"]["llm"]["tools"][0]["server"]["headers"][
            "X-Tool-API-Key"
        ]
        == "***"
    )
    assert safe_body["properties"]["llm"]["params"]["model"] == "gpt-4o-mini"
    assert "secret-tool-key" not in str(safe_body)
    assert "secret-llm-key" not in str(safe_body)
