from __future__ import annotations

from typing import Any

import requests

try:
    from data_sources import get_secret
except ImportError:
    try:
        from .data_sources import get_secret
    except ImportError:
        from war_room_offer_engine.data_sources import get_secret

try:
    from secret_transport_hardening import redact_sensitive_text, safe_request_error
except ImportError:
    try:
        from .secret_transport_hardening import redact_sensitive_text, safe_request_error
    except ImportError:
        from war_room_offer_engine.secret_transport_hardening import redact_sensitive_text, safe_request_error


def connection_settings() -> tuple[str, str]:
    return (
        get_secret("LISTING_RADAR_WEBHOOK_URL", ""),
        get_secret("LISTING_RADAR_TOKEN", ""),
    )


def is_connected() -> bool:
    url, token = connection_settings()
    return bool(url and token)


def _sanitize(value: Any, token: str) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize(item, token) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, token) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value, [token])
    return value


def _request(action: str, payload: dict[str, Any] | None = None, timeout: int = 35) -> dict[str, Any]:
    url, token = connection_settings()
    if not url or not token:
        return {
            "ok": False,
            "not_connected": True,
            "error": "Listing Radar is not connected yet. Add LISTING_RADAR_WEBHOOK_URL and LISTING_RADAR_TOKEN to Streamlit secrets.",
        }
    body = {"action": action, "token": token, **dict(payload or {})}
    try:
        response = requests.post(url, json=body, timeout=timeout)
    except requests.RequestException as exc:
        return {"ok": False, "error": safe_request_error("Listing Radar", exc, [token])}
    except Exception as exc:
        return {"ok": False, "error": safe_request_error("Listing Radar", exc, [token])}
    if response.status_code < 200 or response.status_code >= 300:
        return {"ok": False, "error": f"Listing Radar returned HTTP {response.status_code}."}
    try:
        data = response.json()
    except Exception:
        return {"ok": False, "error": "Listing Radar returned non-JSON data."}
    if not isinstance(data, dict):
        return {"ok": False, "error": "Listing Radar returned an invalid response."}
    return _sanitize(data, token)


def health() -> dict[str, Any]:
    return _request("health")


def list_listings(
    *,
    query: str = "",
    market_id: str = "",
    feed_status: str = "",
    workflow_status: str = "",
    limit: int = 100,
) -> dict[str, Any]:
    return _request(
        "list",
        {
            "query": str(query or "").strip(),
            "market_id": str(market_id or "").strip(),
            "feed_status": str(feed_status or "").strip(),
            "workflow_status": str(workflow_status or "").strip(),
            "limit": max(1, min(int(limit or 100), 500)),
        },
    )


def list_markets() -> dict[str, Any]:
    return _request("list_markets")


def get_listing(listing_key: str) -> dict[str, Any]:
    return _request("get", {"listing_key": str(listing_key or "").strip()})


def update_queue(listing_key: str, changes: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "assigned_to",
        "workflow_status",
        "last_contact_at",
        "next_follow_up",
        "agent_response",
        "team_notes",
        "dismiss_reason",
        "deal_id",
        "updated_by",
    }
    safe_changes = {key: value for key, value in dict(changes or {}).items() if key in allowed}
    return _request(
        "update_queue",
        {"listing_key": str(listing_key or "").strip(), "changes": safe_changes},
        timeout=45,
    )
