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


DEAL_STATUSES = [
    "New Lead",
    "Analyzing",
    "Offer Ready",
    "Offer Sent",
    "Negotiating",
    "Verbal Agreement",
    "Under Contract",
    "Dispo",
    "Closed",
    "Dead / Pass",
]

# These fields contain the complete reusable deal analysis. Saving them prevents
# another Zillow/RentCast/Apify pull when a team member reopens the property.
PERSISTED_STATE_KEYS = [
    "address", "city", "state", "zip", "market", "county", "listing_url",
    "apify_zpid", "source_mode", "lead_source", "lead_type", "status",
    "days_on_market", "asking_price", "contract_price", "beds", "baths",
    "sqft", "lot_size", "year_built", "property_type", "taxes",
    "tax_assessed_value", "last_sale_date", "last_sale_price", "occupancy",
    "livable", "listing_agent_name", "listing_agent_phone",
    "listing_agent_email", "listing_brokerage", "owner_name", "notes",
    "seller_name", "seller_phone", "seller_email", "seller_motivation",
    "seller_timeline", "seller_desired_price", "seller_condition_notes",
    "seller_repair_notes", "repair_notes", "manual_repair_notes", "repairs",
    "repair_source", "repair_analysis", "recommended_repairs_from_analyzer",
    "repair_scope_confidence", "repair_market", "repair_level",
    "repair_contingency", "repair_cushion_percent", "rent", "rent_source",
    "rent_confidence", "rent_verification_needed", "rentcast_rent_comps",
    "rent_comps", "rentcast_comp_count", "rentcast_rent_comp_count",
    "rent_comp_count", "manual_rent_comp_count", "rentcast_submitted_address",
    "rentcast_rent_error", "rentcast_rent_comp_average",
    "rentcast_rent_comp_median", "rent_low", "rent_high", "arv",
    "rentcast_arv", "sheet_arv", "manual_arv_override", "value_source",
    "arv_source_used", "arv_confidence", "arv_fallback_reason",
    "arv_fallback_warnings", "rentcast_sold_comps", "rentcast_value_comps",
    "rentcast_sold_comp_count", "rentcast_value_comp_count", "auto_sold_comps",
    "auto_comp_count", "auto_arv_summary", "auto_recommended_arv",
    "auto_low_arv", "auto_conservative_arv", "auto_average_arv",
    "auto_high_arv", "strong_comp_count", "good_comp_count", "weak_comp_count",
    "excluded_comp_count", "auto_comp_radius", "auto_comp_date_range",
    "auto_comp_source", "use_auto_arv_over_manual_comps", "buyer_demand_score",
    "buyer_demand_confidence", "wholesale_buyer_list_strength",
    "slow_flip_buyer_demand", "rental_demand_confidence",
    "wholesale_exit_confidence", "slow_flip_exit_confidence",
    "overall_exit_confidence", "recommended_exit_strategy",
    "backup_exit_strategy", "buyer_outreach_needed", "exit_risk_warnings",
    "exit_verification_items", "decision_property_input", "decision_strategy",
    "decision_lead_source", "decision_asking_price",
    "decision_current_negotiated_price", "decision_latest_counter",
    "decision_seller_bottom_line", "decision_negotiation_status",
    "decision_negotiated_with", "decision_last_negotiation",
    "decision_next_follow_up", "decision_negotiation_notes",
    "decision_other_terms", "decision_result", "decision_engine_result",
    "decision_last_run_at", "one_load_normalized", "one_load_final_answer",
    "one_load_next_action", "last_source_results", "last_auto_pull",
    "manual_slow_flip_max_override", "slow_flip_max_buy_price_used",
    "buyer_target_price_confirmed", "confirmed_buyer_target_price",
    "buyer_outreach_status", "buyer_response_level", "buyer_concerns",
    "dispo_test_summary", "dispo_test_recommendation",
    "deal_protection_mode", "contract_status", "address_sharing_level",
    "listing_source_sharing_level", "property_marketability", "exit_obstacles",
    "buyer_proof", "field_source_map_json", "apify_field_sources",
]


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    return str(value)


def normalize_property_key(value: str) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"https?://(?:www\.)?", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    replacements = {
        " street ": " st ", " avenue ": " ave ", " road ": " rd ",
        " drive ": " dr ", " lane ": " ln ", " court ": " ct ",
        " boulevard ": " blvd ", " place ": " pl ",
    }
    text = f" {text} "
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def stable_deal_id(state: dict[str, Any]) -> str:
    address = str(state.get("address") or state.get("decision_property_input") or "").strip()
    listing_url = str(state.get("listing_url") or "").strip()
    zpid = str(state.get("apify_zpid") or "").strip()
    identity = normalize_property_key(address or listing_url or zpid)
    if not identity:
        identity = f"unsaved-{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:18]


def build_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    persisted = {
        key: _json_safe(state.get(key))
        for key in PERSISTED_STATE_KEYS
        if key in state
    }
    decision = state.get("decision_result", {}) or {}
    deal_id = str(state.get("deal_library_deal_id") or stable_deal_id(state))
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "deal_id": deal_id,
        "base_version": int(state.get("deal_library_version", 0) or 0),
        "saved_at": now,
        "address": str(state.get("address") or state.get("decision_property_input") or ""),
        "city": str(state.get("city") or ""),
        "property_state": str(state.get("state") or ""),
        "zip": str(state.get("zip") or ""),
        "listing_url": str(state.get("listing_url") or ""),
        "lead_source": str(state.get("decision_lead_source") or state.get("lead_source") or ""),
        "deal_lane": str(decision.get("strategy") or state.get("decision_strategy") or ""),
        "decision": str(decision.get("decision") or state.get("one_load_final_answer") or ""),
        "confidence": str(decision.get("confidence") or state.get("overall_exit_confidence") or ""),
        "deal_status": str(state.get("deal_library_status") or state.get("decision_negotiation_status") or "Analyzing"),
        "assigned_to": str(state.get("deal_library_assigned_to") or ""),
        "team_notes": str(state.get("deal_library_team_notes") or ""),
        "updated_by": str(state.get("deal_library_updated_by") or ""),
        "asking_price": state.get("decision_asking_price") or state.get("asking_price") or 0,
        "current_negotiated_price": state.get("decision_current_negotiated_price") or state.get("contract_price") or 0,
        "starting_offer": decision.get("first_offer", 0),
        "absolute_maximum": decision.get("hard_max", 0),
        "rent": state.get("rent", 0),
        "rent_comp_count": max(
            int(state.get("rentcast_rent_comp_count", 0) or 0),
            int(state.get("rentcast_comp_count", 0) or 0),
            len(state.get("rentcast_rent_comps", []) or []),
        ),
        "arv": state.get("arv", 0),
        "sold_comp_count": max(
            int(state.get("rentcast_value_comp_count", 0) or 0),
            int(state.get("auto_comp_count", 0) or 0),
            len(state.get("auto_sold_comps", []) or []),
        ),
        "repairs": state.get("repairs", 0),
        "session_state": persisted,
    }


def restore_snapshot(state: Any, snapshot: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("Saved deal is not a valid snapshot.")
    # Backward compatibility for any early prototype rows that used `state`.
    payload = snapshot.get("session_state", snapshot.get("state", {}))
    if not isinstance(payload, dict):
        raise ValueError("Saved deal does not contain a valid state snapshot.")
    for key, value in payload.items():
        state[key] = value
    state["deal_library_deal_id"] = snapshot.get("deal_id", "")
    state["deal_library_version"] = int(snapshot.get("version", snapshot.get("base_version", 0)) or 0)
    state["deal_library_status"] = snapshot.get("deal_status", "Analyzing")
    state["deal_library_assigned_to"] = snapshot.get("assigned_to", "")
    state["deal_library_team_notes"] = snapshot.get("team_notes", "")
    state["deal_library_updated_by"] = snapshot.get("updated_by", "")
    state["deal_library_last_saved_at"] = snapshot.get("updated_at", snapshot.get("saved_at", ""))
    state["deal_library_loaded_without_api"] = True


def connection_settings() -> tuple[str, str]:
    return (
        get_secret("DEAL_LIBRARY_WEBHOOK_URL", ""),
        get_secret("DEAL_LIBRARY_TOKEN", ""),
    )


def is_connected() -> bool:
    url, _ = connection_settings()
    return bool(url)


def _request(action: str, *, params: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url, token = connection_settings()
    if not url:
        return {"ok": False, "error": "Deal Library is not connected yet. Add DEAL_LIBRARY_WEBHOOK_URL to Streamlit secrets."}
    query = {"action": action, **(params or {})}
    if token:
        query["token"] = token
    try:
        if payload is None:
            response = requests.get(url, params=query, timeout=35)
        else:
            body = {"action": action, "token": token, **payload}
            response = requests.post(url, json=body, timeout=45)
    except Exception as exc:
        return {"ok": False, "error": f"Deal Library request failed: {exc}"}
    if response.status_code < 200 or response.status_code >= 300:
        return {"ok": False, "error": f"Deal Library HTTP {response.status_code}: {response.text[:300]}"}
    try:
        data = response.json()
    except Exception:
        return {"ok": False, "error": "Deal Library returned non-JSON data."}
    return data if isinstance(data, dict) else {"ok": False, "error": "Deal Library returned an invalid response."}


def health() -> dict[str, Any]:
    return _request("health")


def search_deals(query: str = "", limit: int = 25) -> dict[str, Any]:
    return _request("search", params={"q": query, "limit": max(1, min(int(limit), 100))})


def get_deal(deal_id: str) -> dict[str, Any]:
    return _request("get", params={"deal_id": deal_id})


def save_deal(snapshot: dict[str, Any]) -> dict[str, Any]:
    return _request("upsert", payload={"snapshot": snapshot})
