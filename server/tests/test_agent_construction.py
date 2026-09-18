"""Exercise the real SDK agent construction without calling Agora cloud."""

import asyncio
import sys

import pytest


def _fresh_agent_module():
    sys.modules.pop("agent", None)
    import agent

    return agent


def test_start_wires_inline_tools_and_enables_tool_execution(fake_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "pipeline-key")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    agent_module = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-agent-id"

        async def stop(self):
            pass

    def fake_create_async_session(self, **kwargs):
        captured["llm"] = self.llm
        captured["mllm"] = self.mllm
        captured["advanced_features"] = self.advanced_features
        captured["channel"] = kwargs["channel"]
        captured["agent_uid"] = kwargs["agent_uid"]
        captured["remote_uids"] = kwargs["remote_uids"]
        return FakeSession()

    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", fake_create_async_session)
    result = asyncio.run(agent_module.Agent().start("ch", 111, 222))

    assert result["agent_id"] == "test-agent-id"
    assert captured["channel"] == "ch"
    assert captured["agent_uid"] == "111"
    assert captured["remote_uids"] == ["222"]
    assert len(captured["llm"]["tools"]) == 3
    assert captured["llm"]["tools"][0]["server"]["method"] == "GET"
    assert captured["llm"]["tools"][1]["server"]["method"] == "POST"
    assert captured["llm"]["tools"][2]["server"]["method"] == "GET"
    assert captured["llm"]["template_variables"] == {
        "requester": "inline-rest-tools-recipe"
    }
    assert captured["llm"]["api_key"] == "pipeline-key"
    assert (
        captured["llm"]["url"]
        == "https://api.openai.com/v1/chat/completions"
    )
    assert captured["advanced_features"]["enable_rtm"] is True
    assert captured["advanced_features"]["enable_tools"] is True


def test_start_wires_inline_tools_to_realtime_mllm(fake_env, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "pipeline-key")
    monkeypatch.setenv("OPENAI_REALTIME_API_KEY", "realtime-key")
    agent_module = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-realtime-agent-id"

    def fake_create_async_session(self, **kwargs):
        captured["llm"] = self.llm
        captured["mllm"] = self.mllm
        captured["advanced_features"] = self.advanced_features
        return FakeSession()

    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", fake_create_async_session)
    result = asyncio.run(
        agent_module.Agent().start("ch", 111, 222, agent_mode="realtime")
    )

    assert result["agent_mode"] == "realtime"
    assert captured["llm"] is None
    assert captured["mllm"]["vendor"] == "openai"
    assert captured["mllm"]["api_key"] == "realtime-key"
    assert captured["mllm"]["params"]["model"] == "gpt-realtime"
    assert len(captured["mllm"]["tools"]) == 3
    ticket_tool = next(
        tool for tool in captured["mllm"]["tools"]
        if tool["function"]["name"] == "create_support_ticket"
    )
    assert ticket_tool["server"]["body"]["requester"] == "inline-rest-tools-recipe"
    assert "tools" not in captured["mllm"].get("params", {})
    assert captured["advanced_features"]["enable_tools"] is True


def test_realtime_mode_requires_openai_api_key(fake_env, monkeypatch):
    monkeypatch.delenv("OPENAI_REALTIME_API_KEY", raising=False)
    instance = _fresh_agent_module().Agent()

    with pytest.raises(ValueError, match="OPENAI_REALTIME_API_KEY"):
        asyncio.run(instance.start("ch", 111, 222, agent_mode="realtime"))


def test_pipeline_remains_managed_without_openai_api_key(fake_env, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    agent_module = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-managed-agent-id"

    def fake_create_async_session(self, **kwargs):
        captured["llm"] = self.llm
        return FakeSession()

    from agora_agent.agentkit import Agent as AgoraAgent

    monkeypatch.setattr(AgoraAgent, "create_async_session", fake_create_async_session)
    asyncio.run(agent_module.Agent().start("ch", 111, 222))

    assert captured["llm"].get("api_key") is None
