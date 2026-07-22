from __future__ import annotations

import re
import sys
from typing import Any
from urllib.parse import quote, quote_plus

import requests


_REDACTED = "[REDACTED]"
_SENSITIVE_QUERY_RE = re.compile(
    r"(?i)([?&](?:token|api[_-]?key|access[_-]?token|secret|password|authorization)=)([^&#\s]+)"
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)([\"']?(?:token|api[_-]?key|access[_-]?token|secret|password|authorization)[\"']?\s*[:=]\s*[\"']?)([^\"'\s,}&]+)"
)
_BEARER_RE = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._~+/=-]{6,})")


def redact_sensitive_text(value: Any, secrets: list[str] | tuple[str, ...] = ()) -> str:
    """Remove known credentials and common token shapes from user-visible text."""
    text = str(value or "")
    exact_values: set[str] = set()
    for secret in secrets:
        cleaned = str(secret or "")
        if not cleaned:
            continue
        exact_values.update({cleaned, quote(cleaned, safe=""), quote_plus(cleaned)})
    for secret in sorted(exact_values, key=len, reverse=True):
        text = text.replace(secret, _REDACTED)
    text = _SENSITIVE_QUERY_RE.sub(lambda match: match.group(1) + _REDACTED, text)
    text = _SENSITIVE_ASSIGNMENT_RE.sub(lambda match: match.group(1) + _REDACTED, text)
    text = _BEARER_RE.sub(lambda match: match.group(1) + _REDACTED, text)
    return text


def safe_request_error(provider: str, exc: BaseException, secrets: list[str] | tuple[str, ...] = ()) -> str:
    """Return a useful error without echoing exception URLs, headers, or bodies."""
    del secrets  # intentionally never include raw exception text in the UI
    kind = type(exc).__name__ or "RequestError"
    return f"{provider} request failed ({kind}). Check the connection and provider configuration."


def safe_response_excerpt(
    value: Any,
    secrets: list[str] | tuple[str, ...] = (),
    *,
    limit: int = 240,
) -> str:
    cleaned = redact_sensitive_text(value, secrets)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[: max(int(limit or 0), 0)]


def safe_http_error(
    provider: str,
    status_code: Any,
    response_text: Any = "",
    secrets: list[str] | tuple[str, ...] = (),
) -> str:
    excerpt = safe_response_excerpt(response_text, secrets)
    base = f"{provider} returned HTTP {status_code}."
    return f"{base} {excerpt}" if excerpt else base


def _bearer_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _load_targets():
    try:
        import apify_connector as apify
        import deal_library as library
        import zillow_url_import as zillow
    except ImportError:
        try:
            from . import apify_connector as apify
            from . import deal_library as library
            from . import zillow_url_import as zillow
        except ImportError:
            from war_room_offer_engine import apify_connector as apify
            from war_room_offer_engine import deal_library as library
            from war_room_offer_engine import zillow_url_import as zillow
    return apify, zillow, library


def secure_fetch_dataset_items(dataset_id: str, token: str, limit: int = 50) -> dict[str, Any]:
    apify, _, _ = _load_targets()
    if not token:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Missing Apify token"}
    if not dataset_id:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Bad dataset. Dataset id is required."}

    try:
        response = requests.get(
            f"{apify.APIFY_API_BASE}/datasets/{dataset_id}/items",
            headers=_bearer_headers(token),
            params={"clean": "true", "format": "json", "limit": max(int(limit or 50), 1)},
            timeout=30,
        )
    except requests.RequestException as exc:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": safe_request_error("Apify dataset", exc, [token])}
    except Exception as exc:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": safe_request_error("Apify dataset", exc, [token])}

    if response.status_code in [401, 403]:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Missing token or token does not have access to this dataset."}
    if response.status_code == 404:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Bad dataset. Dataset was not found."}
    if response.status_code < 200 or response.status_code >= 300:
        return {
            "ok": False,
            "source": "Apify Zillow Dataset",
            "error": safe_http_error("Apify dataset", response.status_code, response.text, [token]),
        }

    try:
        items = response.json()
    except Exception:
        excerpt = safe_response_excerpt(response.text, [token])
        suffix = f" Response: {excerpt}" if excerpt else ""
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Bad dataset. Apify returned non-JSON data." + suffix}
    if not isinstance(items, list) or not items:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Empty results"}

    normalized = apify.normalize_zillow_records(items)
    normalized.update(
        {
            "source": "Apify Zillow Dataset",
            "dataset_id": dataset_id,
            "pulled_at": apify.datetime.now().isoformat(timespec="seconds"),
        }
    )
    return normalized


def secure_run_actor_for_items(
    actor_id: str,
    actor_input: dict[str, Any],
    token: str,
    limit: int = 50,
) -> dict[str, Any]:
    apify, _, _ = _load_targets()
    if not token:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Missing Apify token"}
    if not actor_id:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Actor id is required."}

    try:
        response = requests.post(
            f"{apify.APIFY_API_BASE}/acts/{actor_id}/run-sync-get-dataset-items",
            headers=_bearer_headers(token),
            params={"clean": "true", "format": "json", "limit": max(int(limit or 50), 1)},
            json=actor_input or {},
            timeout=120,
        )
    except requests.RequestException as exc:
        return {"ok": False, "source": "Apify Zillow Actor", "error": safe_request_error("Apify actor", exc, [token])}
    except Exception as exc:
        return {"ok": False, "source": "Apify Zillow Actor", "error": safe_request_error("Apify actor", exc, [token])}

    if response.status_code in [401, 403]:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Missing token or token cannot run this actor."}
    if response.status_code < 200 or response.status_code >= 300:
        return {
            "ok": False,
            "source": "Apify Zillow Actor",
            "error": safe_http_error("Apify actor", response.status_code, response.text, [token]),
        }
    try:
        items = response.json()
    except Exception:
        excerpt = safe_response_excerpt(response.text, [token])
        suffix = f" Response: {excerpt}" if excerpt else ""
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Apify actor returned non-JSON data." + suffix}
    if not isinstance(items, list) or not items:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Empty results"}

    normalized = apify.normalize_zillow_records(items)
    normalized.update(
        {
            "source": "Apify Zillow Actor",
            "actor_id": actor_id,
            "pulled_at": apify.datetime.now().isoformat(timespec="seconds"),
        }
    )
    return normalized


def secure_fetch_task_input(task_id: str, token: str) -> dict[str, Any]:
    _, zillow, _ = _load_targets()
    if not task_id or not token:
        return {}
    encoded_id = quote(task_id, safe="~")
    try:
        response = requests.get(
            f"{zillow.APIFY_API_BASE}/actor-tasks/{encoded_id}",
            headers=_bearer_headers(token),
            timeout=20,
        )
    except Exception:
        return {}
    if response.status_code < 200 or response.status_code >= 300:
        return {}
    try:
        body = response.json()
    except Exception:
        return {}
    data = body.get("data", body) if isinstance(body, dict) else {}
    task_input = data.get("input", {}) if isinstance(data, dict) else {}
    return task_input if isinstance(task_input, dict) else {}


def secure_run_task_for_items(
    task_id: str,
    actor_input: dict[str, Any],
    token: str,
    limit: int = 10,
) -> dict[str, Any]:
    _, zillow, _ = _load_targets()
    if not token:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Missing Apify token"}
    if not task_id:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Apify Zillow task id is required."}

    encoded_id = quote(task_id, safe="~")
    try:
        response = requests.post(
            f"{zillow.APIFY_API_BASE}/actor-tasks/{encoded_id}/run-sync-get-dataset-items",
            headers=_bearer_headers(token),
            params={"clean": "true", "format": "json", "limit": max(int(limit or 10), 1)},
            json=actor_input or {},
            timeout=180,
        )
    except requests.RequestException as exc:
        return {"ok": False, "source": "Apify Zillow Task", "error": safe_request_error("Apify Zillow task", exc, [token])}
    except Exception as exc:
        return {"ok": False, "source": "Apify Zillow Task", "error": safe_request_error("Apify Zillow task", exc, [token])}

    if response.status_code in [401, 403]:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Apify token cannot run the configured Zillow task."}
    if response.status_code < 200 or response.status_code >= 300:
        return {
            "ok": False,
            "source": "Apify Zillow Task",
            "error": safe_http_error("Apify Zillow task", response.status_code, response.text, [token]),
        }
    try:
        items = response.json()
    except Exception:
        excerpt = safe_response_excerpt(response.text, [token])
        suffix = f" Response: {excerpt}" if excerpt else ""
        return {"ok": False, "source": "Apify Zillow Task", "error": "Apify Zillow task returned non-JSON data." + suffix}
    if not isinstance(items, list) or not items:
        return {"ok": False, "source": "Apify Zillow Task", "error": "Apify Zillow task returned no property rows."}

    normalized = zillow.normalize_zillow_records(items)
    normalized["source"] = "Apify Zillow Task"
    normalized["raw_items"] = items
    return normalized


def _sanitize_payload(value: Any, secrets: list[str] | tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize_payload(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload(item, secrets) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value, secrets)
    return value


def _decode_response(response: Any, token: str, provider: str) -> dict[str, Any]:
    if response.status_code < 200 or response.status_code >= 300:
        return {"ok": False, "error": safe_http_error(provider, response.status_code, response.text, [token])}
    try:
        data = response.json()
    except Exception:
        return {"ok": False, "error": f"{provider} returned non-JSON data."}
    if not isinstance(data, dict):
        return {"ok": False, "error": f"{provider} returned an invalid response."}
    return _sanitize_payload(data, [token])


def _legacy_get_required(action: str, data: dict[str, Any]) -> bool:
    if str(action or "").lower() == "upsert":
        return False
    error = str(data.get("error", "") or "").lower()
    return "unknown deal library action" in error


def _legacy_deal_library_get(
    library: Any,
    url: str,
    token: str,
    action: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    query = {"action": action, **params}
    if token:
        query["token"] = token
    try:
        response = requests.get(url, params=query, timeout=35)
    except requests.RequestException as exc:
        return {"ok": False, "error": safe_request_error("Deal Library", exc, [token])}
    except Exception as exc:
        return {"ok": False, "error": safe_request_error("Deal Library", exc, [token])}
    return _decode_response(response, token, "Deal Library")


def secure_deal_library_request(
    action: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _, _, library = _load_targets()
    url, token = library.connection_settings()
    if not url:
        return {"ok": False, "error": "Deal Library is not connected yet. Add DEAL_LIBRARY_WEBHOOK_URL to Streamlit secrets."}

    parameters = dict(params or {})
    body = {"action": action, "token": token, **parameters, **dict(payload or {})}
    timeout = 45 if payload is not None else 35
    try:
        response = requests.post(url, json=body, timeout=timeout)
    except requests.RequestException as exc:
        return {"ok": False, "error": safe_request_error("Deal Library", exc, [token])}
    except Exception as exc:
        return {"ok": False, "error": safe_request_error("Deal Library", exc, [token])}

    data = _decode_response(response, token, "Deal Library")
    if _legacy_get_required(action, data):
        return _legacy_deal_library_get(library, url, token, action, parameters)
    return data


def _patch_loaded_aliases(apify: Any, zillow: Any, library: Any) -> None:
    del library  # public Deal Library functions resolve _request dynamically
    for module in list(sys.modules.values()):
        if module is None:
            continue
        name = str(getattr(module, "__name__", ""))
        if name.endswith("data_sources") or name.endswith("zillow_url_import"):
            if hasattr(module, "fetch_dataset_items"):
                module.fetch_dataset_items = secure_fetch_dataset_items
            if hasattr(module, "run_actor_for_items"):
                module.run_actor_for_items = secure_run_actor_for_items
        if name.endswith("zillow_url_import"):
            module.fetch_task_input = secure_fetch_task_input
            module.run_task_for_items = secure_run_task_for_items

    apify.fetch_dataset_items = secure_fetch_dataset_items
    apify.run_actor_for_items = secure_run_actor_for_items
    zillow.fetch_dataset_items = secure_fetch_dataset_items
    zillow.run_actor_for_items = secure_run_actor_for_items
    zillow.fetch_task_input = secure_fetch_task_input
    zillow.run_task_for_items = secure_run_task_for_items


def install() -> bool:
    apify, zillow, library = _load_targets()
    if getattr(apify, "_secret_transport_hardening_installed", False):
        _patch_loaded_aliases(apify, zillow, library)
        library._request = secure_deal_library_request
        return True

    _patch_loaded_aliases(apify, zillow, library)
    library._request = secure_deal_library_request
    apify._secret_transport_hardening_installed = True
    zillow._secret_transport_hardening_installed = True
    library._secret_transport_hardening_installed = True
    return True
