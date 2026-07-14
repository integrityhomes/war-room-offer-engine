from __future__ import annotations


def _list_value(*values):
    for value in values:
        if isinstance(value, list) and value:
            return value
    return []


def _first_value(*values):
    for value in values:
        if value not in [None, "", 0, 0.0, [], {}]:
            return value
    return 0


def hydrate_rentcast_state(st) -> None:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    normalized_data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    data = normalized_data if isinstance(normalized_data, dict) else {}
    last_pull = st.session_state.get("last_auto_pull", {}) or {}
    if not isinstance(last_pull, dict):
        last_pull = {}

    # Zillow-link results live in normalized.data. Plain-address results are
    # hydrated directly into session state by address_rentcast_bridge. Prefer
    # non-empty returned lists and never erase them merely because the other
    # intake path has an empty list.
    rent = _first_value(
        data.get("rent"),
        data.get("rent_estimate"),
        last_pull.get("rent"),
        st.session_state.get("rent"),
    )
    rent_comps = _list_value(
        data.get("rent_comps"),
        last_pull.get("rent_comps"),
        st.session_state.get("rentcast_rent_comps"),
        st.session_state.get("rent_comps"),
    )
    sold_comps = _list_value(
        data.get("rentcast_sold_comps"),
        last_pull.get("rentcast_sold_comps"),
        st.session_state.get("rentcast_sold_comps"),
        st.session_state.get("auto_sold_comps"),
    )
    rentcast_arv = _first_value(
        data.get("rentcast_arv"),
        last_pull.get("rentcast_arv"),
        st.session_state.get("rentcast_arv"),
    )

    try:
        rent = int(float(rent or 0))
    except Exception:
        rent = 0
    try:
        rentcast_arv = int(float(rentcast_arv or 0))
    except Exception:
        rentcast_arv = 0

    rent_comp_count = len(rent_comps)
    sold_comp_count = len(sold_comps)

    if rent > 0:
        st.session_state["rent"] = rent
        st.session_state["rent_source"] = "RentCast"
        st.session_state["rent_confidence"] = (
            "Strong verified rent comps" if rent_comp_count >= 3 else "Medium fallback comps"
        )
        st.session_state["rent_verification_needed"] = "No" if rent_comp_count >= 3 else "Yes"

    st.session_state["rentcast_rent_comps"] = rent_comps
    st.session_state["rent_comps"] = rent_comps
    st.session_state["rentcast_comp_count"] = rent_comp_count
    st.session_state["rentcast_rent_comp_count"] = rent_comp_count
    st.session_state["rent_comp_count"] = rent_comp_count
    st.session_state["rentcast_submitted_address"] = _first_value(
        data.get("rentcast_submitted_address"),
        last_pull.get("rentcast_submitted_address"),
        st.session_state.get("rentcast_submitted_address"),
    ) or ""
    st.session_state["rentcast_rent_error"] = _first_value(
        data.get("rentcast_rent_error"),
        last_pull.get("rentcast_rent_error"),
        st.session_state.get("rentcast_rent_error"),
    ) or ""

    st.session_state["rentcast_sold_comps"] = sold_comps
    st.session_state["rentcast_sold_comp_count"] = sold_comp_count
    st.session_state["rentcast_value_comp_count"] = sold_comp_count
    if sold_comps:
        st.session_state["auto_sold_comps"] = sold_comps
        st.session_state["auto_comp_count"] = sold_comp_count
        st.session_state["auto_comp_source"] = "RentCast"
        st.session_state["auto_comp_messages"] = [f"Automatically loaded {sold_comp_count} RentCast sold comparable(s)."]
    if rentcast_arv > 0:
        st.session_state["rentcast_arv"] = rentcast_arv
        st.session_state["arv_source_used"] = _first_value(
            data.get("arv_source"),
            last_pull.get("arv_source"),
            st.session_state.get("arv_source_used"),
        ) or "RentCast AVM"
        st.session_state["arv_confidence"] = _first_value(
            data.get("arv_confidence"),
            last_pull.get("arv_confidence"),
            st.session_state.get("arv_confidence"),
        ) or "AVM only"


def install() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False
    if getattr(st, "_rentcast_state_bootstrap_installed", False):
        return True

    original_title = st.title

    def title_with_rentcast_state(*args, **kwargs):
        hydrate_rentcast_state(st)
        return original_title(*args, **kwargs)

    st.title = title_with_rentcast_state
    st._rentcast_state_bootstrap_installed = True
    return True


install()
