"""Shared standalone fixtures; no Agora cloud or tunnel is required."""

import importlib
import os
import sys

import pytest

_SERVER_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _SERVER_SRC not in sys.path:
    sys.path.insert(0, _SERVER_SRC)

FAKE_ENV = {
    "AGORA_APP_ID": "0123456789abcdef0123456789abcdef",
    "AGORA_APP_CERTIFICATE": "fedcba9876543210fedcba9876543210",
    "HTTP_TOOLS_BASE_URL": "https://example.ngrok-free.dev",
    "HTTP_TOOLS_API_KEY": "test-tool-key",
    "HTTP_TOOLS_TIMEOUT_MS": "10000",
    "OPENAI_MODEL": "gpt-4o-mini",
}


@pytest.fixture
def fake_env(monkeypatch):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    for key, value in FAKE_ENV.items():
        monkeypatch.setenv(key, value)
    return dict(FAKE_ENV)


class FakeAgent:
    def __init__(self):
        self.started = []
        self.stopped = []
        self.closed = False

    async def start(self, channel_name, agent_uid, user_uid, output_audio_codec=None):
        self.started.append((channel_name, agent_uid, user_uid, output_audio_codec))
        return {
            "agent_id": f"fake-agent-{agent_uid}",
            "channel_name": channel_name,
            "status": "started",
        }

    async def stop(self, agent_id):
        self.stopped.append(agent_id)

    async def close(self):
        self.closed = True


@pytest.fixture
def server_module(fake_env):
    sys.modules.pop("server", None)
    sys.modules.pop("agent", None)
    import server

    importlib.reload(server)
    return server


@pytest.fixture
def client(server_module):
    from fastapi.testclient import TestClient

    fake = FakeAgent()
    server_module.agent = fake
    test_client = TestClient(server_module.app)
    test_client.fake_agent = fake
    return test_client
