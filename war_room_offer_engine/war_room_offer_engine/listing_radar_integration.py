from __future__ import annotations

import sys
from typing import Any
from urllib.parse import urlencode

try:
    import listing_radar_client as client
    import team_offer_identity as identity
except ImportError:
    try:
        from . import listing_radar_client as client
        from . import team_offer_identity as identity
    except ImportError:
        from war_room_offer_engine import listing_radar_client as client
        from war_room_offer_engine import team_offer_identity as identity

try:
    from data_sources import get_secret
except ImportError:
    try:
        from .data_sources import get_secret
    except ImportError:
        from war_room_offer_engine.data_sources import get_secret


PENDING_HANDOFF_KEY = "listing_radar_pending_handoff"
ANALYSIS_RECORD_KEY = "listing_radar_analysis_record"
SELECTED_KEY = "listing_radar_selected_key"
MARKET_KEY = "listing_radar_market_id"
HANDOFF_MESSAGE_KEY = "listing_radar_handoff_message"
HANDOFF_ERROR_KEY = "listing_radar_handoff_error"

_FILTER_KEYS = {
    "listing_radar_query",
    "listing_radar_market",
    "listing_radar_feed_status",
    "listing_radar_workflow_status",
    "listing_radar_limit",
    "listing_radar_health",
    "listing_radar_market_result",
    "listing_radar_last_result",
}


def _number(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _analysis_record(listing: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": listing.get("address", ""),
        "city": listing.get("city", ""),
        "state": listing.get("state", ""),
        "zip": listing.get("zip", ""),
        "market": listing.get("market_id", ""),
        "asking_price": _number(listing.get("asking_price")),
        "beds": listing.get("beds", 0),
        "baths": listing.get("baths", 0),
        "sqft": listing.get("sqft", 0),
        "lot_size": listing.get("lot_size", ""),
        "year_built": listing.get("year_built", 0),
        "property_type": listing.get("property_type", ""),
        "status": listing.get("listing_status", ""),
        "days_on_market": listing.get("days_on_market", 0),
        "listing_url": listing.get("listing_url", ""),
        "listing_agent_name": listing.get("agent_name", ""),
        "listing_agent_phone": listing.get("agent_phone", ""),
        "listing_agent_email": listing.get("agent_email", ""),
        "listing_brokerage": listing.get("agent_brokerage", ""),
        "primary_photo": listing.get("primary_photo", ""),
        "zpid": listing.get("zpid", ""),
    }


def queue_for_one_load(st: Any, listing: dict[str, Any]) -> bool:
    state = st.session_state
    teammate = identity.active_team_member(state)
    if not teammate:
        state[HANDOFF_ERROR_KEY] = "Select the current team member before opening a Listing Radar property."
        return False

    listing = dict(listing or {})
    property_input = str(listing.get("listing_url") or listing.get("address") or "").strip()
    if not property_input:
        state[HANDOFF_ERROR_KEY] = "This listing has no usable address or listing link."
        return False

    state[PENDING_HANDOFF_KEY] = {
        "listing": listing,
        "queued_by": teammate,
    }
    state[HANDOFF_ERROR_KEY] = ""
    state["war_room_active_section"] = "🏠 One-Load"

    if client.is_connected() and listing.get("listing_key"):
        result = client.update_queue(
            str(listing.get("listing_key") or ""),
            {
                "assigned_to": teammate,
                "workflow_status": "Analyze",
                "updated_by": teammate,
            },
        )
        if not result.get("ok"):
            state[HANDOFF_MESSAGE_KEY] = (
                "The property was opened in the Deal Engine, but Listing Radar could not update its team status: "
                + str(result.get("error", "Unknown error"))
            )
    return True


def _clear_prior_property(state: Any) -> None:
    saved_filters = {key: state.get(key) for key in _FILTER_KEYS if key in state}
    try:
        try:
            import production_stability as stability
        except ImportError:
            try:
                from . import production_stability as stability
            except ImportError:
                from war_room_offer_engine import production_stability as stability
        stability.clear_property_state(state, preserve_current_inputs=False)
    except Exception:
        prefixes = (
            "decision_", "one_load_", "rentcast_", "rent_", "arv_", "auto_",
            "location_", "requested_property_", "resolved_property_", "seller_",
            "listing_agent_", "buyer_", "deal_library_", "repair_",
        )
        exact = {
            "address", "city", "state", "zip", "market", "asking_price",
            "contract_price", "beds", "baths", "sqft", "lot_size", "year_built",
            "property_type", "status", "days_on_market", "rent", "arv", "repairs",
            "notes", "listing_url", "last_source_results", "last_auto_pull",
        }
        for key in list(state.keys()):
            text = str(key)
            if text in exact or text.startswith(prefixes):
                state.pop(key, None)
    for key, value in saved_filters.items():
        state[key] = value


def apply_pending_handoff(st: Any) -> bool:
    state = st.session_state
    pending = state.pop(PENDING_HANDOFF_KEY, None)
    if not isinstance(pending, dict):
        return False
    listing = pending.get("listing")
    if not isinstance(listing, dict):
        state[HANDOFF_ERROR_KEY] = "Listing Radar handoff did not include a valid property record."
        return False

    queued_by = identity.clean_name(pending.get("queued_by")) or identity.active_team_member(state)
    _clear_prior_property(state)

    record = _analysis_record(listing)
    listing_url = str(record.get("listing_url") or "").strip()
    address = str(record.get("address") or "").strip()
    asking = _number(record.get("asking_price"))
    property_input = listing_url or address

    state[SELECTED_KEY] = str(listing.get("listing_key") or "")
    state[MARKET_KEY] = str(listing.get("market_id") or "")
    state[ANALYSIS_RECORD_KEY] = record
    state["decision_property_input"] = property_input
    state["decision_lead_source"] = "Zillow / On-Market"
    state["decision_asking_price"] = asking
    state["one_load_input_method"] = "Listing URL" if listing_url else "Property address"
    state["one_load_listing_url"] = listing_url
    state["one_load_property_address"] = address if not listing_url else ""
    state["one_load_lead_type"] = "On-market listing"
    state["one_load_lead_source"] = "Zillow"
    state["one_load_asking_price"] = asking
    state["one_load_contact_name"] = str(record.get("listing_agent_name") or "")
    state["one_load_contact_phone"] = str(record.get("listing_agent_phone") or "")
    state["one_load_contact_email"] = str(record.get("listing_agent_email") or "")
    state["deal_library_assigned_to"] = queued_by
    state[HANDOFF_MESSAGE_KEY] = (
        "Listing Radar property loaded into One-Load. Review the listing facts, then press Pull Everything & Tell Me. "
        "The existing Listing Radar record will be reused, so the Deal Engine does not need another Zillow/Apify listing scrape."
    )
    state[HANDOFF_ERROR_KEY] = ""
    return True


def analysis_record(state: Any) -> dict[str, Any] | None:
    if not hasattr(state, "get"):
        return None
    record = state.get(ANALYSIS_RECORD_KEY)
    return dict(record) if isinstance(record, dict) and record else None


def mark_analysis_completed(st: Any) -> dict[str, Any]:
    state = st.session_state
    listing_key_value = str(state.get(SELECTED_KEY) or "").strip()
    if not listing_key_value or not client.is_connected():
        return {"ok": True, "skipped": True}
    teammate = identity.active_team_member(state)
    result = client.update_queue(
        listing_key_value,
        {
            "assigned_to": teammate,
            "workflow_status": "Analyze",
            "deal_id": str(state.get("deal_library_deal_id") or ""),
            "updated_by": teammate,
        },
    )
    if not result.get("ok"):
        state[HANDOFF_MESSAGE_KEY] = (
            "The Deal Engine completed, but Listing Radar could not record the analysis status: "
            + str(result.get("error", "Unknown error"))
        )
    return result


def agent_contact_finder_url(listing: dict[str, Any]) -> str:
    base = str(get_secret("AGENT_CONTACT_FINDER_URL", "") or "").strip()
    if not base:
        return ""
    query = urlencode(
        {
            "agent_name": str(listing.get("agent_name") or ""),
            "brokerage": str(listing.get("agent_brokerage") or ""),
            "address": str(listing.get("address") or ""),
            "city": str(listing.get("city") or ""),
            "state": str(listing.get("state") or ""),
            "zip": str(listing.get("zip") or ""),
        }
    )
    separator = "&" if "?" in base else "?"
    return base + separator + query


def _decision_modules():
    try:
        import deal_decision_ui as decision_ui
    except ImportError:
        try:
            from . import deal_decision_ui as decision_ui
        except ImportError:
            from war_room_offer_engine import deal_decision_ui as decision_ui
    try:
        from ui_sections import one_load_deal_ui as one_load
    except ImportError:
        try:
            from .ui_sections import one_load_deal_ui as one_load
        except ImportError:
            from war_room_offer_engine.ui_sections import one_load_deal_ui as one_load
    return decision_ui, one_load


def render_with_listing_radar(st: Any, ui: Any, original_renderer: Any, exit_mode_value: str = "Auto") -> Any:
    applied = apply_pending_handoff(st)
    if applied:
        message = st.session_state.pop(HANDOFF_MESSAGE_KEY, "")
        if message:
            st.success(message)
    elif st.session_state.get(HANDOFF_ERROR_KEY):
        st.error(st.session_state.pop(HANDOFF_ERROR_KEY))
    return _ORIGINAL_DECISION_RENDER(st, ui, original_renderer, exit_mode_value)


def run_with_listing_radar(st: Any, ui: Any, media_files: list[Any]) -> Any:
    record = analysis_record(st.session_state)
    if not record:
        return _ORIGINAL_DECISION_RUN(st, ui, media_files)

    _, one_load = _decision_modules()
    original_one_load_run = one_load._run_one_load

    def run_one_load_with_radar_record(
        st_arg: Any,
        ui_arg: Any,
        csv_record: dict[str, Any] | None,
        exit_mode: str,
        overwrite_demo_values: bool = True,
    ) -> dict[str, Any]:
        chosen_record = csv_record if isinstance(csv_record, dict) and csv_record else record
        return original_one_load_run(
            st_arg,
            ui_arg,
            chosen_record,
            exit_mode,
            overwrite_demo_values,
        )

    one_load._run_one_load = run_one_load_with_radar_record
    try:
        result = _ORIGINAL_DECISION_RUN(st, ui, media_files)
    finally:
        one_load._run_one_load = original_one_load_run
    mark_analysis_completed(st)
    return result


def _patch_loaded_aliases() -> None:
    for module_name in (
        "deal_decision_ui",
        "war_room_offer_engine.deal_decision_ui",
        "war_room_offer_engine.war_room_offer_engine.deal_decision_ui",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.render = render_with_listing_radar
            loaded._run = run_with_listing_radar


def install() -> bool:
    global _ORIGINAL_DECISION_RENDER, _ORIGINAL_DECISION_RUN
    decision_ui, _ = _decision_modules()
    if getattr(decision_ui, "_listing_radar_native_integration_installed", False):
        _patch_loaded_aliases()
        return True

    _ORIGINAL_DECISION_RENDER = decision_ui.render
    _ORIGINAL_DECISION_RUN = decision_ui._run
    decision_ui._listing_radar_original_render = _ORIGINAL_DECISION_RENDER
    decision_ui._listing_radar_original_run = _ORIGINAL_DECISION_RUN
    decision_ui.render = render_with_listing_radar
    decision_ui._run = run_with_listing_radar

    try:
        import deal_library as library
    except ImportError:
        try:
            from . import deal_library as library
        except ImportError:
            from war_room_offer_engine import deal_library as library
    for key in (SELECTED_KEY, MARKET_KEY):
        if key not in library.PERSISTED_STATE_KEYS:
            library.PERSISTED_STATE_KEYS.append(key)

    _patch_loaded_aliases()
    decision_ui._listing_radar_native_integration_installed = True
    return True
