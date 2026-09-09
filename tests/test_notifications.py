import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError
from selery_api.notifications import (
    DeviceRegistration,
    NotificationConfig,
    claim_delivery,
    deliver_alert,
    notification_status,
    reconcile_receipts,
    register_device,
    register_routes,
)
from selery_api.storage import Store

TOKEN = "ExpoPushToken[offline_fixture_12345]"


@pytest.fixture
def store():
    store = Store("sqlite:///:memory:")
    store.put(
        "alerts",
        {
            "id": "signal-1",
            "title": "SPY research observation",
            "body": "A price crossover was observed.",
            "symbol": "SPY",
            "signal_id": "signal-1",
        },
        "signal-1",
    )
    yield store
    store.engine.dispose()


def device(store):
    return register_device(store, DeviceRegistration(token=TOKEN, platform="ios"))


def run_delivery(store, handler, config=None):
    async def invoke():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await deliver_alert(store, "signal-1", config or NotificationConfig(enabled=True), client=client)

    return asyncio.run(invoke())


def test_device_registration_validation_deduplication_and_private_status(store):
    with pytest.raises(ValidationError):
        DeviceRegistration(token="arbitrary-token", platform="ios")
    first = device(store)
    assert device(store).id == first.id
    assert len(store.list("devices")) == 1
    assert TOKEN not in json.dumps(notification_status(store, NotificationConfig()))
    assert TOKEN not in first.model_dump_json()


def test_registration_routes_are_authenticated_and_cannot_send(store):
    app = FastAPI()
    app.state.store = store
    app.state.notification_config = NotificationConfig()

    def authorized(request: Request):
        if request.headers.get("Authorization") != "Bearer test-session":
            raise HTTPException(401)

    register_routes(app, authorized)
    with TestClient(app) as client:
        data = {"token": TOKEN, "platform": "ios"}
        assert client.post("/api/v1/notifications/devices", json=data).status_code == 401
        client.headers["Authorization"] = "Bearer test-session"
        response = client.post("/api/v1/notifications/devices", json=data)
        assert response.status_code == 200
        identifier = response.json()["id"]
        assert client.post(f"/api/v1/notifications/devices/{identifier}/disable").json()["enabled"] is False
        assert client.get("/api/v1/notifications/status").json()["enabled"] is False
        assert store.list("settings") == []


def test_disabled_configuration_never_contacts_provider(store):
    device(store)

    def forbidden(request):
        pytest.fail("Disabled notifications must not make requests")

    assert run_delivery(store, forbidden, NotificationConfig()) == {
        "accepted": 0,
        "failed": 0,
        "skipped": 1,
        "unknown": 0,
    }


def test_ticket_acceptance_deduplicates_and_preserves_deep_link(store):
    device(store)
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["data"] == {"symbol": "SPY", "signal_id": "signal-1", "alert_id": "signal-1"}
        assert request.url.host == "exp.host"
        return httpx.Response(200, json={"data": {"status": "ok", "id": "receipt-1"}})

    assert run_delivery(store, handler)["accepted"] == 1
    assert run_delivery(store, handler)["skipped"] == 1
    assert len(calls) == 1
    assert store.list("settings")[0]["status"] == "accepted"
    assert TOKEN not in json.dumps(store.list("audit"))


def test_atomic_claim_survives_worker_reentry(store):
    assert claim_delivery(store, "signal-1", "expo", "device") is not None
    assert claim_delivery(store, "signal-1", "expo", "device") is None
    assert store.list("settings")[0]["status"] == "unknown"


def test_timeout_does_not_trigger_duplicate_delivery(store):
    device(store)

    def handler(request):
        raise httpx.ReadTimeout("sensitive upstream content must not be retained")

    assert run_delivery(store, handler)["unknown"] == 1
    assert run_delivery(store, handler)["skipped"] == 1
    assert "sensitive upstream" not in json.dumps(store.list("settings"))


def test_unregistered_ticket_disables_device(store):
    registered = device(store)
    response = lambda request: httpx.Response(
        200, json={"data": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}
    )
    assert run_delivery(store, response)["failed"] == 1
    assert store.get("devices", registered.id)["enabled"] is False


@pytest.mark.parametrize("receipt_status,expected", [("ok", "provider_delivered"), ("error", "failed")])
def test_receipts_and_token_invalidation(store, receipt_status, expected):
    registered = device(store)
    run_delivery(store, lambda request: httpx.Response(200, json={"data": {"status": "ok", "id": "receipt-1"}}))

    async def invoke():
        handler = lambda request: httpx.Response(
            200,
            json={
                "data": {
                    "receipt-1": {
                        "status": receipt_status,
                        "details": {"error": "DeviceNotRegistered"} if receipt_status == "error" else {},
                    }
                }
            },
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await reconcile_receipts(store, NotificationConfig(enabled=True), client=client)

    assert asyncio.run(invoke()) == {"checked": 1, "pending": 0}
    assert store.list("settings")[0]["status"] == expected
    assert store.get("devices", registered.id)["enabled"] is (receipt_status == "ok")


def test_late_invalid_receipt_does_not_disable_reregistered_device(store):
    registered = device(store)
    run_delivery(store, lambda request: httpx.Response(200, json={"data": {"status": "ok", "id": "receipt-1"}}))
    device(store)

    async def invoke():
        handler = lambda request: httpx.Response(
            200, json={"data": {"receipt-1": {"status": "error", "details": {"error": "DeviceNotRegistered"}}}}
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await reconcile_receipts(store, NotificationConfig(enabled=True), client=client)

    asyncio.run(invoke())
    assert store.get("devices", registered.id)["enabled"] is True


def test_missing_receipt_stays_pending(store):
    device(store)
    run_delivery(store, lambda request: httpx.Response(200, json={"data": {"status": "ok", "id": "receipt-1"}}))

    async def invoke():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": {}}))
        ) as client:
            return await reconcile_receipts(store, NotificationConfig(enabled=True), client=client)

    assert asyncio.run(invoke()) == {"checked": 0, "pending": 1}


def test_explicit_optional_channels_and_smtp_are_mocked(store, monkeypatch):
    sent = []
    monkeypatch.setattr("selery_api.notifications._send_email", lambda *args: sent.append("email"))
    config = NotificationConfig(
        enabled=True,
        discord_webhook="https://discord.com/api/webhooks/123/offline_fixture",
        telegram_bot_token="123:offline_fixture",
        telegram_chat_id="12345",
        smtp_host="mail.example.test",
        smtp_from="research@example.test",
        smtp_to="owner@example.test",
    )

    def handler(request):
        sent.append(request.url.host)
        if request.url.host == "discord.com":
            assert json.loads(request.content)["allowed_mentions"] == {"parse": []}
            return httpx.Response(204)
        return httpx.Response(200, json={"ok": True})

    assert run_delivery(store, handler, config)["accepted"] == 3
    assert set(sent) == {"discord.com", "api.telegram.org", "email"}
    assert run_delivery(store, handler, config)["skipped"] == 3


@pytest.mark.parametrize(
    "url",
    [
        "http://discord.com/api/webhooks/123/key",
        "https://evil.example/api/webhooks/123/key",
        "https://discord.com.evil.example/api/webhooks/123/key",
    ],
)
def test_webhook_host_validation(url):
    with pytest.raises(ValueError):
        NotificationConfig(discord_webhook=url)
