from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

import requests

try:
    from data_sources import get_secret
except ImportError:
    try:
        from .data_sources import get_secret
    except ImportError:
        from war_room_offer_engine.data_sources import get_secret


WEB_APP_SECRET = "DEAL_LIBRARY_WEB_APP_URL"
TOKEN_SECRET = "DEAL_LIBRARY_TOKEN"
MAX_STRING_LENGTH = 8000
MAX_LIST_ITEMS = 50
MAX_DICT_ITEMS = 120

TEAM_STATUSES = [
    "New",
    "Researching",
    "Negotiating",
    "Offer Sent",
    "Follow-Up",
    "Verbal Agreement",
    "Contract Sent",
    "Under Contract",
    "Passed",
    "Closed",
]
PRIORITIES = ["Hot", "Warm", "Cold", "Watch"]

EXACT_STATE_KEYS = {
    "address", "city", "state", "zip", "county", "market", "property_type",
    "beds", "baths", "sqft", "lot_size", "year_built", "listing_url",
    "asking_price", "contract_price", "rent", "rent_source", "rent_confidence",
    "rent_verification_needed", "arv", "arv_source_used", "arv_confidence",
    "value_source", "rentcast_arv", "sheet_arv", "taxes", "tax_assessed_value",
    "repairs", "repair_source", "repair_notes", "notes", "status", "occupancy",
    "livable", "lead_source", "lead_type", "source_mode", "days_on_market",
    "listing_agent_name", "listing_agent_phone", "listing_agent_email",
    "listing_brokerage", "seller_name", "seller_phone", "seller_email",
    "seller_motivation", "seller_timeline", "seller_desired_price",
    "seller_condition_notes", "seller_repair_notes", "last_sale_date",
    "last_sale_price", "owner_name", "county_tax_gis_link",
}
ALLOWED_PREFIXES = (
    "decision_", "one_load_", "rentcast_", "rent_", "auto_", "manual_",
    "repair_", "buyer_", "dispo_", "seller_", "apify_", "deal_protection_",
    "exit_", "wholesale_", "slow_flip_", "property_", "confirmed_",
)
EXCLUDED_KEYS = {
    "decision_media", "one_load_quick_media", "repair_media_files",
    "auto_comp_csv_upload", "apify_zillow_preview", "apify_actor_input_json",
}
EXCLUDED_SUFFIXES = ("_upload", "_uploaded_file", "_file_uploader")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_address(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    replacements = {
        " street ": " st ", " avenue ": " ave ", " road ": " rd ",
        " drive ": " dr ", " lane ": " ln ", " court ": " ct ",
        " boulevard ": " blvd ", " place ": " pl ",
    }
    text = f" {text} "
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def deal_id_for(address: str, listing_url: str = "") -> str:
    identity = normalize_address(address) or str(listing_url or "").strip().lower()
    if not identity:
        return ""
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]


def _uploaded_file_names(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    names = []
    for item in values:
        name = getattr(item, "name", "")
        if name:
            names.append(str(name))
    return names


def json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return str(value)[:MAX_STRING_LENGTH]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_STRING_LENGTH]
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item, depth + 1) for item in list(value)[:MAX_LIST_ITEMS]]
    if isinstance(value, dict):
        items = list(value.items())[:MAX_DICT_ITEMS]
        return {str(key): json_safe(item, depth + 1) for key, item in items}
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    name = getattr(value, "name", "")
    if name:
        return {"uploaded_filename": str(name)}
    return str(value)[:MAX_STRING_LENGTH]


def should_save_state_key(key: str) -> bool:
    if key in EXCLUDED_KEYS or key.endswith(EXCLUDED_SUFFIXES):
        return False
    return key in EXACT_STATE_KEYS or key.startswith(ALLOWED_PREFIXES)


def build_snapshot(state: Any) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    try:
        keys = list(state.keys())
    except Exception:
        keys = []
    for raw_key in keys:
        key = str(raw_key)
        if not should_save_state_key(key):
            continue
        try:
            snapshot[key] = json_safe(state.get(raw_key))
        except Exception:
            continue

    media_names = []
    for media_key in ["decision_media", "one_load_quick_media", "repair_media_files"]:
        try:
            media_names.extend(_uploaded_file_names(state.get(media_key)))
        except Exception:
            continue
    if media_names:
        snapshot["deal_library_media_filenames"] = list(dict.fromkeys(media_names))
    snapshot["deal_library_snapshot_version"] = 1
    return snapshot


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _comp_count(state: Any, keys: list[str], list_keys: list[str]) -> int:
    counts = []
    for key in keys:
        try:
            counts.append(int(_number(state.get(key))))
        except Exception:
            pass
    for key in list_keys:
        try:
            value = state.get(key)
            counts.append(len(value) if isinstance(value, list) else 0)
        except Exception:
            pass
    return max(counts or [0])


def build_record(state: Any) -> dict[str, Any]:
    decision = state.get("decision_result", {}) or {}
    address = str(state.get("address") or state.get("decision_property_input") or "").strip()
    listing_url = str(state.get("listing_url") or "").strip()
    deal_id = deal_id_for(address, listing_url)
    snapshot = build_snapshot(state)
    record = {
        "deal_id": deal_id,
        "property_address": address,
        "city": str(state.get("city") or ""),
        "state": str(state.get("state") or ""),
        "zip": str(state.get("zip") or ""),
        "listing_url": listing_url,
        "lead_source": str(state.get("decision_lead_source") or state.get("lead_source") or ""),
        "deal_lane": str(decision.get("strategy") or state.get("decision_strategy") or ""),
        "decision": str(decision.get("decision") or ""),
        "confidence": str(decision.get("confidence") or ""),
        "asking_price": _number(state.get("decision_asking_price") or state.get("asking_price")),
        "current_price": _number(decision.get("price") or state.get("decision_current_negotiated_price") or state.get("contract_price")),
        "starting_offer": _number(decision.get("first_offer")),
        "absolute_max": _number(decision.get("hard_max")),
        "room_left": _number(decision.get("room_left")),
        "projected_margin": _number(decision.get("projected_margin")),
        "rent": _number(state.get("rent")),
        "rent_comp_count": _comp_count(
            state,
            ["rentcast_rent_comp_count", "rentcast_comp_count", "rent_comp_count", "manual_rent_comp_count"],
            ["rentcast_rent_comps", "rent_comps"],
        ),
        "arv": _number(state.get("arv")),
        "sold_comp_count": _comp_count(
            state,
            ["rentcast_value_comp_count", "rentcast_sold_comp_count", "auto_comp_count"],
            ["rentcast_sold_comps", "auto_sold_comps"],
        ),
        "repairs": _number(state.get("repairs")),
        "negotiation_status": str(state.get("decision_negotiation_status") or ""),
        "assigned_to": str(state.get("deal_library_assigned_to") or ""),
        "team_status": str(state.get("deal_library_team_status") or "New"),
        "priority": str(state.get("deal_library_priority") or "Warm"),
        "next_follow_up": str(state.get("decision_next_follow_up") or ""),
        "saved_by": str(state.get("deal_library_saved_by") or ""),
        "updated_at": utc_now(),
        "snapshot": snapshot,
    }
    return json_safe(record)


def backend_config() -> tuple[str, str]:
    return get_secret(WEB_APP_SECRET, ""), get_secret(TOKEN_SECRET, "")


def configured() -> bool:
    url, token = backend_config()
    return bool(url and token)


def _request_json(response: requests.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        return {"ok": False, "error": f"Deal Library returned non-JSON data (HTTP {response.status_code})."}
    if not isinstance(payload, dict):
        return {"ok": False, "error": "Deal Library returned an unexpected response."}
    return payload


def list_deals(search: str = "", limit: int = 200, session=requests) -> dict[str, Any]:
    url, token = backend_config()
    if not url or not token:
        return {"ok": False, "error": "Deal Library is not configured.", "deals": []}
    try:
        response = session.get(
            url,
            params={"action": "list", "token": token, "search": search, "limit": int(limit)},
            timeout=30,
        )
        return _request_json(response)
    except Exception as exc:
        return {"ok": False, "error": f"Could not load saved deals: {exc}", "deals": []}


def get_deal(deal_id: str, session=requests) -> dict[str, Any]:
    url, token = backend_config()
    if not url or not token:
        return {"ok": False, "error": "Deal Library is not configured."}
    try:
        response = session.get(
            url,
            params={"action": "get", "token": token, "deal_id": deal_id},
            timeout=30,
        )
        return _request_json(response)
    except Exception as exc:
        return {"ok": False, "error": f"Could not open saved deal: {exc}"}


def save_deal(record: dict[str, Any], session=requests) -> dict[str, Any]:
    url, token = backend_config()
    if not url or not token:
        return {"ok": False, "error": "Deal Library is not configured."}
    if not record.get("deal_id"):
        return {"ok": False, "error": "A property address or listing URL is required before saving."}
    try:
        response = session.post(
            url,
            json={"action": "upsert", "token": token, "record": record},
            timeout=45,
        )
        return _request_json(response)
    except Exception as exc:
        return {"ok": False, "error": f"Could not save deal: {exc}"}


def restore_snapshot(st: Any, snapshot: dict[str, Any]) -> int:
    if not isinstance(snapshot, dict):
        return 0
    restored = 0
    for key, value in snapshot.items():
        if key in ["deal_library_snapshot_version", "deal_library_media_filenames"]:
            continue
        if not should_save_state_key(str(key)):
            continue
        try:
            st.session_state[str(key)] = value
            restored += 1
        except Exception:
            continue
    st.session_state["deal_library_media_filenames"] = snapshot.get("deal_library_media_filenames", [])
    return restored


def backup_json(state: Any) -> str:
    return json.dumps(build_record(state), indent=2, default=str)


def parse_backup(value: bytes | str) -> dict[str, Any]:
    try:
        text = value.decode("utf-8") if isinstance(value, bytes) else str(value)
        payload = json.loads(text)
    except Exception as exc:
        return {"ok": False, "error": f"Invalid deal backup: {exc}"}
    if not isinstance(payload, dict) or not isinstance(payload.get("snapshot"), dict):
        return {"ok": False, "error": "The backup does not contain a valid deal snapshot."}
    return {"ok": True, "record": payload}
