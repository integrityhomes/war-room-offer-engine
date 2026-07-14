from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from datetime import date, datetime
from typing import Any, Mapping


SNAPSHOT_VERSION = 1
MAX_SHEET_CELL_CHARS = 45_000

CORE_KEYS = {
    "address", "city", "state", "zip", "market", "county", "property_type",
    "beds", "baths", "sqft", "lot_size", "year_built", "listing_url",
    "asking_price", "contract_price", "rent", "rent_source", "rent_confidence",
    "rent_verification_needed", "taxes", "tax_assessed_value", "arv", "sheet_arv",
    "rentcast_arv", "arv_source_used", "arv_confidence", "repairs", "repair_source",
    "repair_notes", "notes", "status", "occupancy", "livable", "days_on_market",
    "lead_source", "source_mode", "lead_type", "listing_agent_name",
    "listing_agent_phone", "listing_agent_email", "listing_brokerage",
    "value_source", "buyer_demand_confidence", "exit_strategy_confidence",
    "slow_flip_max_buy_price_used", "slow_flip_max_buy_price_source",
}

PREFIXES = (
    "decision_", "one_load_", "rentcast_", "rent_", "auto_", "manual_comp_",
    "manual_rent_", "repair_", "seller_", "listing_", "apify_", "deal_protection_",
    "buyer_", "source_", "field_", "wholesale_", "slow_flip_",
)

EXCLUDED_KEYS = {
    "decision_media", "repair_media_files", "one_load_quick_media",
    "auto_comp_csv_upload", "manual_csv_upload",
}

HEAVY_TRIM_KEYS = {
    "last_source_results", "last_auto_pull", "apify_zillow_preview",
    "apify_raw_rows", "one_load_raw_record", "auto_comp_summary_json",
    "excluded_comp_flags_json", "field_source_map_json",
}


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_address_key(value: Any) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"https?://(?:www\.)?", "", text)
    replacements = {
        " street ": " st ", " avenue ": " ave ", " road ": " rd ",
        " drive ": " dr ", " lane ": " ln ", " court ": " ct ",
        " boulevard ": " blvd ", " place ": " pl ",
    }
    text = f" {text} "
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def deal_identity(address: Any = "", listing_url: Any = "", property_input: Any = "") -> tuple[str, str]:
    source = normalize_text(address) or normalize_text(listing_url) or normalize_text(property_input)
    key = normalize_address_key(source)
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:14] if key else ""
    return (f"DV-{digest}" if digest else "", key)


def _safe_value(value: Any, depth: int = 0) -> Any:
    if depth > 7:
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            safe = _safe_value(item, depth + 1)
            if safe is not None:
                output[str(key)] = safe
        return output
    if isinstance(value, (list, tuple, set)):
        output = []
        for item in value:
            safe = _safe_value(item, depth + 1)
            if safe is not None:
                output.append(safe)
        return output
    name = getattr(value, "name", None)
    size = getattr(value, "size", None)
    mime_type = getattr(value, "type", None)
    if name:
        return {"file_name": str(name), "size": int(size or 0), "mime_type": str(mime_type or "")}
    return None


def should_capture(key: str) -> bool:
    if key in EXCLUDED_KEYS or "upload" in key.lower() or key.endswith("_files"):
        return False
    return key in CORE_KEYS or key.startswith(PREFIXES)


def build_snapshot(session_state: Mapping[str, Any], media_files: list[Any] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key, value in dict(session_state).items():
        if not should_capture(str(key)):
            continue
        safe = _safe_value(value)
        if safe is not None:
            state[str(key)] = safe

    media = []
    for file in media_files or []:
        media.append(
            {
                "file_name": str(getattr(file, "name", "") or ""),
                "size": int(getattr(file, "size", 0) or 0),
                "mime_type": str(getattr(file, "type", "") or ""),
            }
        )

    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "saved_state": state,
        "media_references": media,
    }


def snapshot_hash(snapshot: Mapping[str, Any]) -> str:
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compress(snapshot: Mapping[str, Any]) -> str:
    raw = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    packed = zlib.compress(raw, level=9)
    return "z1:" + base64.urlsafe_b64encode(packed).decode("ascii")


def encode_snapshot(snapshot: Mapping[str, Any]) -> tuple[str, bool]:
    payload = _compress(snapshot)
    if len(payload) <= MAX_SHEET_CELL_CHARS:
        return payload, False

    trimmed = dict(snapshot)
    state = dict(trimmed.get("saved_state", {}) or {})
    for key in HEAVY_TRIM_KEYS:
        state.pop(key, None)
    normalized = state.get("one_load_normalized")
    if isinstance(normalized, dict):
        normalized = dict(normalized)
        normalized.pop("record", None)
        normalized.pop("raw", None)
        state["one_load_normalized"] = normalized
    trimmed["saved_state"] = state
    trimmed["snapshot_trimmed"] = True
    payload = _compress(trimmed)
    if len(payload) > MAX_SHEET_CELL_CHARS:
        raise ValueError("Deal snapshot is too large for one Google Sheets cell even after safe trimming.")
    return payload, True


def decode_snapshot(payload: str) -> dict[str, Any]:
    text = str(payload or "").strip()
    if not text:
        return {}
    try:
        if text.startswith("z1:"):
            packed = base64.urlsafe_b64decode(text[3:].encode("ascii"))
            return json.loads(zlib.decompress(packed).decode("utf-8"))
        return json.loads(text)
    except Exception as exc:
        raise ValueError(f"Saved deal snapshot could not be decoded: {exc}") from exc


def restore_snapshot(session_state: Any, snapshot: Mapping[str, Any]) -> int:
    state = snapshot.get("saved_state", {}) if isinstance(snapshot, Mapping) else {}
    if not isinstance(state, Mapping):
        return 0
    restored = 0
    for key, value in state.items():
        if key in EXCLUDED_KEYS or "upload" in key.lower() or key.endswith("_files"):
            continue
        session_state[str(key)] = value
        restored += 1
    media = snapshot.get("media_references", []) if isinstance(snapshot, Mapping) else []
    session_state["deal_vault_media_references"] = media if isinstance(media, list) else []
    session_state["deal_vault_loaded_without_api_pull"] = True
    return restored


def changed_fields(previous: Mapping[str, Any] | None, current: Mapping[str, Any]) -> list[str]:
    previous_state = (previous or {}).get("saved_state", {}) if isinstance(previous, Mapping) else {}
    current_state = current.get("saved_state", {}) if isinstance(current, Mapping) else {}
    if not isinstance(previous_state, Mapping):
        previous_state = {}
    if not isinstance(current_state, Mapping):
        current_state = {}
    keys = sorted(set(previous_state) | set(current_state))
    return [key for key in keys if previous_state.get(key) != current_state.get(key)]


def summary_from_state(session_state: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(session_state)
    decision = state.get("decision_result", {}) or {}
    if not isinstance(decision, dict):
        decision = {}
    address = normalize_text(state.get("address"))
    listing_url = normalize_text(state.get("listing_url") or state.get("one_load_listing_url"))
    property_input = normalize_text(state.get("decision_property_input"))
    deal_id, address_key = deal_identity(address, listing_url, property_input)
    return {
        "deal_id": deal_id,
        "address_key": address_key,
        "address": address or (property_input if not property_input.lower().startswith("http") else ""),
        "city": normalize_text(state.get("city")),
        "state": normalize_text(state.get("state")),
        "zip": normalize_text(state.get("zip")),
        "listing_url": listing_url or (property_input if property_input.lower().startswith("http") else ""),
        "lead_source": normalize_text(state.get("decision_lead_source") or state.get("lead_source")),
        "decision": normalize_text(decision.get("decision")),
        "deal_lane": normalize_text(decision.get("strategy") or state.get("decision_strategy")),
        "asking_price": state.get("decision_asking_price") or state.get("asking_price") or 0,
        "negotiated_price": state.get("decision_current_negotiated_price") or state.get("contract_price") or 0,
        "starting_offer": decision.get("first_offer", 0),
        "absolute_max": decision.get("hard_max", 0),
        "rent": state.get("rent", 0),
        "rent_comp_count": state.get("rentcast_rent_comp_count") or state.get("rentcast_comp_count") or 0,
        "arv": state.get("arv", 0),
        "arv_confidence": normalize_text(state.get("arv_confidence")),
        "sold_comp_count": state.get("rentcast_value_comp_count") or state.get("auto_comp_count") or 0,
        "repairs": state.get("repairs", 0),
    }
