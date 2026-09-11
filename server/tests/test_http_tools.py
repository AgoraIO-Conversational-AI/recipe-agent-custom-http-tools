"""Local mock REST endpoint tests."""

import logging


def test_lookup_order_requires_api_key(client):
    assert client.get("/tools/orders/A-1001").status_code == 401
    response = client.get(
        "/tools/orders/A-1001", headers={"X-Tool-API-Key": "test-tool-key"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "order_id": "A-1001",
        "status": "shipped",
        "total": 42.5,
        "currency": "USD",
    }


def test_lookup_order_unknown_is_deterministic(client):
    response = client.get(
        "/tools/orders/unknown", headers={"X-Tool-API-Key": "test-tool-key"}
    )
    assert response.status_code == 200
    assert response.json() == {"order_id": "UNKNOWN", "status": "not_found"}


def test_create_ticket_validates_body_and_returns_ticket(client):
    response = client.post(
        "/tools/tickets",
        headers={"X-Tool-API-Key": "test-tool-key"},
        json={
            "order_id": "a-1001",
            "issue": "The package is late",
            "requester": "test-user",
            "tool_call_id": "call-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_id"].startswith("T-")
    assert len(body["ticket_id"]) == 6
    assert body["ticket_id"][2:].isdigit()
    assert body["status"] == "created"
    assert body["order_id"] == "A-1001"
    assert body["issue"] == "The package is late"
    assert body["requester"] == "test-user"
    assert body["tool_call_id"] == "call-1"

    lookup = client.get(
        f"/tools/tickets/{body['ticket_id']}",
        headers={"X-Tool-API-Key": "test-tool-key"},
    )
    assert lookup.status_code == 200
    assert lookup.json() == body

    for spoken_variant in (body["ticket_id"].replace("-", ""), body["ticket_id"][2:]):
        lookup = client.get(
            f"/tools/tickets/{spoken_variant}",
            headers={"X-Tool-API-Key": "test-tool-key"},
        )
        assert lookup.status_code == 200
        assert lookup.json() == body


def test_create_ticket_does_not_overwrite_an_existing_ticket(client):
    headers = {"X-Tool-API-Key": "test-tool-key"}
    first = client.post(
        "/tools/tickets",
        headers=headers,
        json={"order_id": "A-1000", "issue": "issue-54"},
    ).json()
    second = client.post(
        "/tools/tickets",
        headers=headers,
        json={"order_id": "A-1000", "issue": "issue-132"},
    ).json()

    assert first["ticket_id"] != second["ticket_id"]
    assert client.get(
        f"/tools/tickets/{first['ticket_id']}", headers=headers
    ).json() == first


def test_lookup_ticket_returns_not_found_for_unknown_id(client):
    response = client.get(
        "/tools/tickets/T-UNKNOWN",
        headers={"X-Tool-API-Key": "test-tool-key"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Ticket not found"}


def test_ticket_tool_calls_are_logged(client, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        created = client.post(
            "/tools/tickets",
            headers={"X-Tool-API-Key": "test-tool-key"},
            json={"order_id": "A-1002", "issue": "The item is damaged"},
        )
        ticket_id = created.json()["ticket_id"]
        client.get(
            f"/tools/tickets/{ticket_id}",
            headers={"X-Tool-API-Key": "test-tool-key"},
        )

    messages = [record.getMessage() for record in caplog.records]
    assert f"[HTTP TOOL CALLED] create_support_ticket ticket_id={ticket_id}" in messages
    assert f"[HTTP TOOL CALLED] get_support_ticket ticket_id={ticket_id}" in messages


def test_create_ticket_rejects_missing_issue(client):
    response = client.post(
        "/tools/tickets",
        headers={"X-Tool-API-Key": "test-tool-key"},
        json={"order_id": "A-1001", "issue": "  "},
    )
    assert response.status_code == 400
