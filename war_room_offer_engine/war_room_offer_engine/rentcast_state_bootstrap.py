from __future__ import annotations


def _number(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def hydrate_rentcast_state(st) -> None:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    if not isinstance(data, dict):
        return

    rent = data.get("rent") or data.get("rent_estimate") or 0
    rent_comps = data.get("rent_comps", []) or []
    sold_comps = data.get("rentcast_sold_comps", []) or []
    rentcast_arv = data.get("rentcast_arv") or 0

    try:
        rent = int(float(rent or 0))
    except Exception:
        rent = 0
    try:
        rentcast_arv = int(float(rentcast_arv or 0))
    except Exception:
        rentcast_arv = 0

    rent_count = max(
        len(rent_comps),
        int(_number(data.get("rent_comp_count"))),
        int(_number(st.session_state.get("rentcast_rent_comp_count"))),
        int(_number(st.session_state.get("rentcast_comp_count"))),
    )
    rent_confidence = str(data.get("rent_confidence") or st.session_state.get("rent_confidence") or "")

    if rent > 0:
        st.session_state["rent"] = rent
        st.session_state["rent_source"] = "RentCast"
        st.session_state["rent_confidence"] = (
            "Strong verified rent comps"
            if rent_count >= 3
            else rent_confidence or "Medium fallback comps"
        )
        st.session_state["rent_verification_needed"] = "No" if rent_count >= 3 else "Yes"

    st.session_state["rentcast_rent_comps"] = rent_comps
    st.session_state["rentcast_rent_comp_count"] = rent_count
    st.session_state["rentcast_comp_count"] = rent_count
    st.session_state["rent_comp_count"] = rent_count
    st.session_state["rentcast_submitted_address"] = data.get("rentcast_submitted_address", "")
    st.session_state["rentcast_rent_error"] = data.get("rentcast_rent_error", "")

    sold_count = max(
        len(sold_comps),
        int(_number(data.get("rentcast_sold_comp_count"))),
        int(_number(st.session_state.get("rentcast_value_comp_count"))),
    )
    st.session_state["rentcast_sold_comp_count"] = sold_count
    st.session_state["rentcast_value_comp_count"] = sold_count
    if sold_comps:
        st.session_state["auto_sold_comps"] = sold_comps
        st.session_state["auto_comp_source"] = "RentCast"
        st.session_state["auto_comp_messages"] = [f"Automatically loaded {sold_count} RentCast sold comparable(s)."]
    if rentcast_arv > 0:
        st.session_state["rentcast_arv"] = rentcast_arv
        st.session_state["arv_source_used"] = data.get("arv_source", "RentCast AVM")
        st.session_state["arv_confidence"] = data.get("arv_confidence", "AVM only")


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
