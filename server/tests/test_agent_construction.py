"""Exercise the real SDK agent construction without calling Agora cloud."""

import asyncio
import sys


def _fresh_agent_module():
    sys.modules.pop("agent", None)
    import agent

    return agent


def test_start_wires_inline_tools_and_enables_tool_execution(fake_env, monkeypatch):
    agent_module = _fresh_agent_module()
    captured = {}

    class FakeSession:
        async def start(self):
            return "test-agent-id"

        async def stop(self):
            pass

    def fake_create_async_session(self, **kwargs):
        captured["llm"] = self.llm
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
    assert captured["advanced_features"]["enable_rtm"] is True
    assert captured["advanced_features"]["enable_tools"] is True
