"""FastAPI route tests via TestClient + FakeAgent (no Agora cloud)."""


def test_lifespan_closes_agent(server_module):
    from fastapi.testclient import TestClient

    class ClosingAgent:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    fake = ClosingAgent()
    server_module.agent = fake
    with TestClient(server_module.app):
        pass

    assert fake.closed is True


def test_get_config_returns_envelope_and_token(client):
    response = client.get("/get_config")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["msg"] == "success"
    data = body["data"]
    assert data["app_id"] == "0123456789abcdef0123456789abcdef"
    assert isinstance(data["token"], str) and len(data["token"]) > 0
    assert data["uid"] and data["uid"] != "0"
    assert data["channel_name"].startswith("inline-rest-tools-")
    assert data["agent_uid"]


def test_get_config_remaps_zero_uid_and_honors_channel(client):
    response = client.get("/get_config", params={"uid": 0, "channel": "test-channel"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["uid"] != "0"
    assert data["channel_name"] == "test-channel"


def test_start_agent_calls_agent_and_returns_shape(client):
    response = client.post(
        "/startAgent",
        json={"channelName": "ch", "rtcUid": 111, "userUid": 222},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == {
        "agent_id": "fake-agent-111",
        "channel_name": "ch",
        "status": "started",
        "agent_mode": "pipeline",
    }
    assert client.fake_agent.started == [("ch", 111, 222, None, "pipeline")]


def test_start_agent_forwards_output_audio_codec(client):
    client.post(
        "/startAgent",
        json={
            "channelName": "ch",
            "rtcUid": 111,
            "userUid": 222,
            "parameters": {"output_audio_codec": "opus"},
        },
    )
    assert client.fake_agent.started[-1] == ("ch", 111, 222, "opus", "pipeline")


def test_start_agent_forwards_realtime_mode(client):
    response = client.post(
        "/startAgent",
        json={
            "channelName": "ch",
            "rtcUid": 111,
            "userUid": 222,
            "agentMode": "realtime",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["agent_mode"] == "realtime"
    assert client.fake_agent.started[-1] == ("ch", 111, 222, None, "realtime")


def test_start_agent_rejects_unknown_mode(client):
    response = client.post(
        "/startAgent",
        json={
            "channelName": "ch",
            "rtcUid": 111,
            "userUid": 222,
            "agentMode": "unknown",
        },
    )

    assert response.status_code == 422


def test_stop_agent(client):
    response = client.post("/stopAgent", json={"agentId": "fake-agent-111"})
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert client.fake_agent.stopped == ["fake-agent-111"]


def test_value_error_maps_to_400(client, server_module):
    class BadAgent:
        async def start(self, **kwargs):
            raise ValueError("bad input")

        async def stop(self, *args):
            pass

    server_module.agent = BadAgent()
    response = client.post(
        "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
    )
    assert response.status_code == 400
    assert "bad input" in response.json()["detail"]


def test_runtime_error_maps_to_500(client, server_module):
    class BoomAgent:
        async def start(self, **kwargs):
            raise RuntimeError("explode")

        async def stop(self, *args):
            pass

    server_module.agent = BoomAgent()
    response = client.post(
        "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
    )
    assert response.status_code == 500


def test_misconfigured_agent_returns_500(client, server_module):
    server_module.agent = None
    assert client.get("/get_config").status_code == 500
    assert (
        client.post(
            "/startAgent", json={"channelName": "c", "rtcUid": 1, "userUid": 2}
        ).status_code
        == 500
    )
    assert client.post("/stopAgent", json={"agentId": "x"}).status_code == 500
