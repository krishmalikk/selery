"""Opt-in delivery of existing research alerts; no sends occur on import or registration.

Provider acceptance is not device delivery. A durable, atomic claim prevents automatic
resubmission after a timeout/crash where the external delivery result is unknown.
"""

import asyncio
import hashlib
import os
import re
import smtplib
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, Request
from selery_shared.models import DeviceRegistration, DeviceRegistrationResult
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from .storage import Store, tables

EXPO_API = "https://exp.host/--/api/v2/push"
TOKEN_PATTERN = r"^(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{10,200}\]$"


@dataclass(frozen=True)
class NotificationConfig:
    enabled: bool = False
    expo_access_token: str = ""
    discord_webhook: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_tls: Literal["starttls", "ssl"] = "starttls"

    @classmethod
    def load(cls):
        mode = os.getenv("SELERY_SMTP_TLS", "starttls")
        if mode not in ("starttls", "ssl"):
            raise ValueError("SELERY_SMTP_TLS must be starttls or ssl")
        return cls(
            enabled=os.getenv("SELERY_NOTIFICATIONS_ENABLED", "false").lower() == "true",
            expo_access_token=os.getenv("EXPO_ACCESS_TOKEN", ""),
            discord_webhook=os.getenv("SELERY_DISCORD_WEBHOOK", ""),
            telegram_bot_token=os.getenv("SELERY_TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("SELERY_TELEGRAM_CHAT_ID", ""),
            smtp_host=os.getenv("SELERY_SMTP_HOST", ""),
            smtp_port=int(os.getenv("SELERY_SMTP_PORT", "587")),
            smtp_user=os.getenv("SELERY_SMTP_USER", ""),
            smtp_password=os.getenv("SELERY_SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SELERY_SMTP_FROM", ""),
            smtp_to=os.getenv("SELERY_SMTP_TO", ""),
            smtp_tls=mode,
        )

    def __post_init__(self):
        if self.discord_webhook:
            parsed = urlparse(self.discord_webhook)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "discord.com"
                or parsed.port
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or not re.fullmatch(r"/api/webhooks/\d+/[A-Za-z0-9_-]+", parsed.path)
            ):
                raise ValueError("Discord webhook must be a standard HTTPS discord.com webhook")
        if self.telegram_bot_token and not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", self.telegram_bot_token):
            raise ValueError("Telegram bot token format is invalid")
        if self.telegram_chat_id and not re.fullmatch(r"-?\d+|@[A-Za-z0-9_]+", self.telegram_chat_id):
            raise ValueError("Telegram chat identifier is invalid")
        if not 1 <= self.smtp_port <= 65535:
            raise ValueError("SMTP port is invalid")
        if self.smtp_tls not in ("starttls", "ssl"):
            raise ValueError("SMTP requires TLS")


def now():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def register_device(store: Store, body: DeviceRegistration):
    if not re.fullmatch(TOKEN_PATTERN, body.token):
        raise ValueError("Invalid Expo push token")
    identifier = digest(body.token)
    record = {"id": identifier, **body.model_dump(), "registered_at": now()}
    # One row per token: repeat registration re-enables a previously revoked device.
    try:
        store.put("devices", record, identifier)
    except IntegrityError:
        store.put("devices", record, identifier)
    return DeviceRegistrationResult(id=identifier, enabled=body.enabled)


def disable_device(store: Store, identifier: str):
    record = store.get("devices", identifier)
    if not record:
        raise HTTPException(404, "Device registration not found")
    record["enabled"] = False
    store.put("devices", record, identifier)
    return DeviceRegistrationResult(id=identifier, enabled=False)


def notification_status(store: Store, config: NotificationConfig):
    return {
        "enabled": config.enabled,
        "channels": {
            "expo": any(d.get("enabled") for d in store.list("devices", 10000)),
            "discord": bool(config.discord_webhook),
            "telegram": bool(config.telegram_bot_token and config.telegram_chat_id),
            "email": bool(config.smtp_host and config.smtp_from and config.smtp_to),
        },
        "delivery_semantics": "Provider acceptance does not confirm receipt by a user.",
    }


def register_routes(app, authorized):
    """Integration: call once from create_app, after defining authorized dependency."""

    @app.post(
        "/api/v1/notifications/devices", response_model=DeviceRegistrationResult, dependencies=[Depends(authorized)]
    )
    def register(body: DeviceRegistration, request: Request):
        return register_device(request.app.state.store, body)

    @app.post(
        "/api/v1/notifications/devices/{identifier}/disable",
        response_model=DeviceRegistrationResult,
        dependencies=[Depends(authorized)],
    )
    def disable(identifier: str, request: Request):
        return disable_device(request.app.state.store, identifier)

    @app.get("/api/v1/notifications/status", dependencies=[Depends(authorized)])
    def status(request: Request):
        config = getattr(request.app.state, "notification_config", None) or NotificationConfig.load()
        return notification_status(request.app.state.store, config)


def claim_delivery(store, alert_id, channel, recipient):
    identifier = "notification:" + digest(f"{alert_id}:{channel}:{recipient}")
    record = {
        "id": identifier,
        "kind": "notification_delivery",
        "alert_id": alert_id,
        "channel": channel,
        "recipient_id": recipient,
        "status": "unknown",
        "created_at": now(),
    }
    try:
        with store.engine.begin() as conn:
            conn.execute(insert(tables["settings"]).values(id=identifier, created_at=datetime.now(UTC), payload=record))
    except IntegrityError:
        return None
    return record


def save_delivery(store, record, status, **detail):
    record.update({"status": status, "updated_at": now(), **detail})
    store.put("settings", record, record["id"])
    store.audit("notification_status", {"id": record["id"], "channel": record["channel"], "status": status})


def _send_email(config, title, body):
    message = EmailMessage()
    message["Subject"] = title.replace("\r", " ").replace("\n", " ")[:160]
    message["From"] = config.smtp_from
    message["To"] = config.smtp_to
    message.set_content(body)
    connection = (
        smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15, context=ssl.create_default_context())
        if config.smtp_tls == "ssl"
        else smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
    )
    with connection as smtp:
        if config.smtp_tls == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        if config.smtp_user:
            smtp.login(config.smtp_user, config.smtp_password)
        smtp.send_message(message)


async def deliver_alert(
    store: Store, alert_id: str, config: NotificationConfig | None = None, *, client: httpx.AsyncClient | None = None
):
    """Explicitly invoked delivery, gated off by default. Never sends a fabricated alert.

    Calling twice cannot send twice for the same alert/channel/recipient. Timeout results
    remain unknown without retries, since providers have no universal idempotency key.
    """
    config = config or NotificationConfig.load()
    result = {"accepted": 0, "failed": 0, "skipped": 0, "unknown": 0}
    if not config.enabled:
        result["skipped"] = 1
        return result
    alert = store.get("alerts", alert_id)
    if not alert:
        raise ValueError("Existing research alert required")
    if client is None:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as owned:
            return await deliver_alert(store, alert_id, config, client=owned)
    title = str(alert["title"])[:160]
    body = str(alert["body"])[:1500]
    destinations = [("expo", d["id"], d["token"]) for d in store.list("devices", 10000) if d.get("enabled")]
    if config.discord_webhook:
        destinations.append(("discord", digest(config.discord_webhook), config.discord_webhook))
    if config.telegram_bot_token and config.telegram_chat_id:
        destinations.append(("telegram", digest(config.telegram_chat_id), config.telegram_chat_id))
    if config.smtp_host and config.smtp_from and config.smtp_to:
        destinations.append(("email", digest(config.smtp_to), config.smtp_to))
    for channel, recipient, address in destinations:
        record = claim_delivery(store, alert_id, channel, recipient)
        if record is None:
            result["skipped"] += 1
            continue
        try:
            if channel == "expo":
                headers = {"Authorization": f"Bearer {config.expo_access_token}"} if config.expo_access_token else {}
                response = await client.post(
                    EXPO_API + "/send",
                    headers=headers,
                    json={
                        "to": address,
                        "title": title,
                        "body": body,
                        "channelId": "research",
                        "data": {
                            "symbol": alert.get("symbol"),
                            "signal_id": alert.get("signal_id"),
                            "alert_id": alert_id,
                        },
                    },
                )
                response.raise_for_status()
                ticket = response.json().get("data", {})
                if not isinstance(ticket, dict) or ticket.get("status") not in ("ok", "error"):
                    raise ValueError("Unknown provider response")
                if ticket.get("status") == "ok" and not isinstance(ticket.get("id"), str):
                    raise ValueError("Provider acceptance cannot be reconciled")
                if ticket.get("status") == "ok":
                    save_delivery(store, record, "accepted", ticket_id=ticket["id"])
                    result["accepted"] += 1
                    continue
                if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                    device = store.get("devices", recipient)
                    if device and device.get("registered_at", "") <= record["created_at"]:
                        disable_device(store, recipient)
                save_delivery(store, record, "failed", reason="provider_rejected")
                result["failed"] += 1
                continue
            if channel == "discord":
                response = await client.post(
                    address, json={"content": f"{title}\n{body}", "allowed_mentions": {"parse": []}}
                )
                response.raise_for_status()
            elif channel == "telegram":
                response = await client.post(
                    f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage",
                    json={"chat_id": address, "text": f"{title}\n{body}"},
                )
                response.raise_for_status()
                if response.json().get("ok") is not True:
                    raise ValueError("Provider rejected")
            elif channel == "email":
                await asyncio.to_thread(_send_email, config, title, body)
            save_delivery(store, record, "accepted")
            result["accepted"] += 1
        except httpx.HTTPStatusError as exc:
            # No upstream messages, URLs, headers, tokens, or credentials enter audit output.
            status = "failed" if 400 <= exc.response.status_code < 500 else "unknown"
            save_delivery(store, record, status, reason="provider_http_error")
            result[status] += 1
        except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError, AttributeError):
            save_delivery(store, record, "unknown", reason="delivery_result_unknown")
            result["unknown"] += 1
    return result


async def reconcile_receipts(
    store: Store, config: NotificationConfig | None = None, *, client: httpx.AsyncClient | None = None
):
    """Read provider receipts; call from a worker approximately 15 minutes after sending."""
    config = config or NotificationConfig.load()
    if not config.enabled:
        return {"checked": 0, "pending": 0}
    pending = [
        r
        for r in store.list("settings", 10000)
        if r.get("kind") == "notification_delivery"
        and r.get("channel") == "expo"
        and r.get("status") == "accepted"
        and r.get("ticket_id")
    ]
    if not pending:
        return {"checked": 0, "pending": 0}
    if client is None:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as owned:
            return await reconcile_receipts(store, config, client=owned)
    checked = 0
    for start in range(0, len(pending), 1000):
        batch = pending[start : start + 1000]
        headers = {"Authorization": f"Bearer {config.expo_access_token}"} if config.expo_access_token else {}
        try:
            response = await client.post(
                EXPO_API + "/getReceipts", headers=headers, json={"ids": [r["ticket_id"] for r in batch]}
            )
            response.raise_for_status()
            receipts = response.json()["data"]
            if not isinstance(receipts, dict):
                continue
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            store.audit("notification_receipt_check_failed", {"reason": "provider_response_unavailable"})
            continue
        for record in batch:
            receipt = receipts.get(record["ticket_id"])
            if not isinstance(receipt, dict) or receipt.get("status") not in ("ok", "error"):
                continue
            detail = receipt.get("details")
            if isinstance(detail, dict) and detail.get("error") == "DeviceNotRegistered":
                device = store.get("devices", record["recipient_id"])
                if device and device.get("registered_at", "") <= record["created_at"]:
                    disable_device(store, record["recipient_id"])
            status = "provider_delivered" if receipt["status"] == "ok" else "failed"
            save_delivery(store, record, status, reason="receipt_checked")
            checked += 1
    return {"checked": checked, "pending": len(pending) - checked}
