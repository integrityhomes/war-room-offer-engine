from __future__ import annotations

from typing import Any

try:
    from deal_library import (
        get_deal,
        is_connected,
        normalize_property_key,
        search_deals,
        stable_deal_id,
    )
except ImportError:
    try:
        from .deal_library import (
            get_deal,
            is_connected,
            normalize_property_key,
            search_deals,
            stable_deal_id,
        )
    except ImportError:
        from war_room_offer_engine.deal_library import (
            get_deal,
            is_connected,
            normalize_property_key,
            search_deals,
            stable_deal_id,
        )


def _queue_snapshot(st, snapshot: dict[str, Any], message: str) -> None:
    st.session_state["deal_library_pending_snapshot"] = snapshot
    st.session_state["deal_library_last_message"] = message
    st.session_state["deal_library_last_error"] = ""
    st.rerun()


def open_saved_before_paid_pull(st) -> bool:
    """Open an existing saved property before any paid source is called.

    Returns False only when no saved match exists or the Deal Library is not
    connected. A successful match reruns Streamlit immediately.
    """
    if not is_connected() or st.session_state.get("deal_library_force_refresh", False):
        return False

    property_input = str(st.session_state.get("decision_property_input", "") or "").strip()
    if not property_input:
        return False

    direct_id = stable_deal_id({"address": property_input})
    direct = get_deal(direct_id)
    if direct.get("ok") and isinstance(direct.get("snapshot"), dict):
        _queue_snapshot(
            st,
            direct["snapshot"],
            "A saved analysis was found and opened before paid sources ran. No property-data credits were used.",
        )
        return True

    search = search_deals(property_input, limit=10)
    if not search.get("ok"):
        # A library outage should not block analysis of a genuinely new lead.
        st.session_state["deal_library_last_error"] = search.get("error", "Saved-deal preflight could not run.")
        return False

    deals = search.get("deals", []) or []
    input_key = normalize_property_key(property_input)
    exact = []
    for deal in deals:
        address_key = normalize_property_key(deal.get("address", ""))
        url_key = normalize_property_key(deal.get("listing_url", ""))
        if input_key and input_key in [address_key, url_key]:
            exact.append(deal)

    chosen = exact[0] if exact else deals[0] if len(deals) == 1 else None
    if not chosen:
        if deals:
            st.session_state["deal_library_search"] = property_input
            st.session_state["deal_library_search_results"] = deals
            st.session_state["deal_library_last_message"] = (
                "Multiple saved properties matched. Open the correct saved deal below before using paid data."
            )
        return False

    result = get_deal(str(chosen.get("deal_id", "")))
    if result.get("ok") and isinstance(result.get("snapshot"), dict):
        _queue_snapshot(
            st,
            result["snapshot"],
            "A saved analysis was found and opened before paid sources ran. No property-data credits were used.",
        )
        return True
    return False
