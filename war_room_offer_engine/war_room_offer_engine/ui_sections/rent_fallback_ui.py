from __future__ import annotations


RENT_FALLBACK_SOURCES = [
    "Manual rent comps",
    "Zillow rental listings",
    "Facebook Marketplace rentals",
    "HUD Fair Market Rent / Section 8 reference",
    "Property manager estimate",
    "PropStream rent estimate if available",
    "Seller-stated rent",
    "Prior known local rent",
]

RENT_CONFIDENCE_LEVELS = [
    "Strong verified rent comps",
    "Medium fallback comps",
    "Weak / seller stated only",
    "Missing",
]


def render_rent_fallback_section(st, ui) -> None:
    st.subheader("Rent Fallback Mode")
    st.caption("Use this when RentCast cannot verify rental comps.")

    with st.container(border=True):
        st.warning("RentCast could not verify rent. Slow Flip numbers are not reliable until rent comps are manually verified.")
        top = st.columns(3)
        with top[0]:
            st.selectbox("Fallback rent source", RENT_FALLBACK_SOURCES, key="rent_fallback_source")
        with top[1]:
            st.selectbox("Fallback rent confidence", RENT_CONFIDENCE_LEVELS, key="manual_rent_confidence")
        with top[2]:
            st.number_input("Seller-stated rent", min_value=0, step=50, key="seller_stated_rent")

        st.caption("Manual rent comp inputs")
        for idx in range(1, 4):
            with st.expander(f"Manual rent comp {idx}", expanded=idx == 1):
                cols = st.columns([2, 1, 1, 1, 1, 1])
                with cols[0]:
                    st.text_input("Rent comp address / area", key=f"manual_rent_comp_{idx}_area")
                with cols[1]:
                    st.number_input("Beds", min_value=0.0, step=0.5, key=f"manual_rent_comp_{idx}_beds")
                with cols[2]:
                    st.number_input("Baths", min_value=0.0, step=0.5, key=f"manual_rent_comp_{idx}_baths")
                with cols[3]:
                    st.number_input("Sqft", min_value=0, step=50, key=f"manual_rent_comp_{idx}_sqft")
                with cols[4]:
                    st.number_input("Listed rent", min_value=0, step=50, key=f"manual_rent_comp_{idx}_rent")
                with cols[5]:
                    st.selectbox(
                        "Confidence",
                        ["Verified listing", "Likely comparable", "Weak / unverified"],
                        key=f"manual_rent_comp_{idx}_confidence",
                    )
                st.selectbox("Source", RENT_FALLBACK_SOURCES, key=f"manual_rent_comp_{idx}_source")
                st.text_input("Notes", key=f"manual_rent_comp_{idx}_notes")

        apply_rent_fallback_state = getattr(ui, "apply_rent_fallback_state", None)
        if st.button("Apply Rent Fallback", type="secondary"):
            state = apply_rent_fallback_state() if apply_rent_fallback_state else _resolve_rent_fallback_state(st, ui)
            if state.get("manual_rent_comp_average", 0) > 0:
                st.session_state["rent"] = int(state["manual_rent_comp_average"])
            st.success("Rent fallback applied. Review rent confidence before analyzing.")

        state = apply_rent_fallback_state() if apply_rent_fallback_state else _resolve_rent_fallback_state(st, ui)
        st.session_state.update(state)
        cols = st.columns(4)
        cols[0].metric("Rent Source", state.get("rent_source", "Missing / RentCast unavailable"))
        cols[1].metric("Rent Confidence", state.get("rent_confidence", "Weak"))
        cols[2].metric("Rent Fallback Mode", state.get("rent_fallback_mode", "Yes"))
        cols[3].metric("Fallback Average", ui.money(state.get("manual_rent_comp_average", 0)))
        detail_cols = st.columns(3)
        detail_cols[0].metric("Manual Rent Comps", state.get("manual_rent_comp_count", 0))
        detail_cols[1].metric("Rent Verification Needed", state.get("rent_verification_needed", "Yes"))
        detail_cols[2].metric("Slow Flip Rent Risk", "Yes" if state.get("slow_flip_rent_risk") else "No")
        if state.get("rent_verification_needed") == "Yes":
            st.warning(state.get("slow_flip_rent_risk", "Verify rent comps manually."))


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _resolve_rent_fallback_state(st, ui) -> dict:
    rents = []
    verified_count = 0
    for idx in range(1, 4):
        rent = _safe_float(st.session_state.get(f"manual_rent_comp_{idx}_rent", 0))
        if rent <= 0:
            continue
        rents.append(rent)
        if st.session_state.get(f"manual_rent_comp_{idx}_confidence") == "Verified listing":
            verified_count += 1

    average = sum(rents) / len(rents) if rents else 0
    seller_rent = _safe_float(st.session_state.get("seller_stated_rent", 0))
    current_rent = _safe_float(st.session_state.get("rent", 0))
    manual_confidence = st.session_state.get("manual_rent_confidence", "Missing")
    if len(rents) >= 3 and verified_count >= 2:
        rent_source = "Manual rent comps"
        rent_confidence = "Strong verified rent comps"
        verification_needed = "No"
    elif len(rents) >= 2:
        rent_source = "Manual rent comps"
        rent_confidence = "Medium fallback comps"
        verification_needed = "No" if manual_confidence != "Weak / seller stated only" else "Yes"
    elif len(rents) == 1:
        rent_source = "Manual rent comps"
        rent_confidence = "Weak / seller stated only"
        verification_needed = "Yes"
    elif seller_rent > 0 or current_rent > 0:
        rent_source = "Seller-stated rent" if seller_rent > 0 else st.session_state.get("rent_source", "Missing / RentCast unavailable")
        rent_confidence = "Weak / seller stated only"
        verification_needed = "Yes"
    else:
        rent_source = "Missing / RentCast unavailable"
        rent_confidence = "Missing"
        verification_needed = "Yes"

    risk = ""
    if verification_needed == "Yes":
        risk = "RentCast could not verify rent. Slow Flip numbers are not reliable until rent comps are manually verified."

    money = getattr(ui, "money", lambda value: f"${value:,.0f}")
    return {
        "rent_source": rent_source,
        "rent_confidence": rent_confidence,
        "rent_fallback_mode": "Yes" if verification_needed == "Yes" or rents else "No",
        "manual_rent_comp_count": len(rents),
        "manual_rent_comp_average": average,
        "rent_verification_needed": verification_needed,
        "slow_flip_rent_risk": risk,
        "rent_fallback_summary": f"{rent_source}; {rent_confidence}; average {money(average)}",
    }
