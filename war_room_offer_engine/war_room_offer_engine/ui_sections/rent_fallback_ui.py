from __future__ import annotations


RENT_FALLBACK_SOURCES = [
    "RentCast comparables",
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


def _normalized_data(st) -> dict:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    return data if isinstance(data, dict) else {}


def _rentcast_comps(st) -> list[dict]:
    data = _normalized_data(st)
    comps = data.get("rent_comps", []) or []
    return [item for item in comps if isinstance(item, dict) and float(item.get("rent", 0) or 0) > 0]


def _apply_rentcast_state(st, data: dict, comps: list[dict]) -> None:
    rent = int(float(data.get("rent") or data.get("rent_estimate") or 0))
    if rent > 0:
        st.session_state["rent"] = rent
    st.session_state["rent_source"] = "RentCast"
    st.session_state["rent_confidence"] = (
        "Strong verified rent comps" if len(comps) >= 3 else "Medium fallback comps" if rent > 0 else "Missing"
    )
    st.session_state["rent_verification_needed"] = "No" if len(comps) >= 3 else "Yes"
    st.session_state["rentcast_comp_count"] = len(comps)
    st.session_state["rentcast_submitted_address"] = data.get("rentcast_submitted_address", "")


def render_rent_fallback_section(st, ui) -> None:
    st.subheader("Rent Verification")
    st.caption("RentCast results populate automatically. Manual fallback is only needed when the API returns no usable estimate or comparables.")

    data = _normalized_data(st)
    comps = _rentcast_comps(st)
    rentcast_rent = int(float(data.get("rent") or data.get("rent_estimate") or 0))
    rentcast_error = str(data.get("rentcast_rent_error") or "")
    submitted_address = str(data.get("rentcast_submitted_address") or "")

    if rentcast_rent > 0 or comps:
        _apply_rentcast_state(st, data, comps)
        st.success(
            f"RentCast verified ${rentcast_rent:,.0f}/month with {len(comps)} comparable rental(s)."
            if rentcast_rent > 0
            else f"RentCast returned {len(comps)} comparable rental(s)."
        )
        if submitted_address:
            st.caption(f"Address submitted to RentCast: {submitted_address}")
        if comps:
            rows = []
            for item in comps:
                rows.append(
                    {
                        "Address": item.get("address", ""),
                        "Beds": item.get("beds", 0),
                        "Baths": item.get("baths", 0),
                        "Sqft": item.get("sqft", 0),
                        "Rent": ui.money(item.get("rent", 0)),
                        "Distance": item.get("distance", 0),
                        "Source": item.get("source", "RentCast comparable"),
                    }
                )
            st.dataframe(ui.pd.DataFrame(rows), use_container_width=True)
        metrics = st.columns(4)
        metrics[0].metric("RentCast Rent", ui.money(rentcast_rent))
        metrics[1].metric("Comparable Count", len(comps))
        metrics[2].metric("Comp Average", ui.money(data.get("rent_comp_average", 0)))
        metrics[3].metric("Comp Median", ui.money(data.get("rent_comp_median", 0)))
        st.info(f"Rent confidence: {st.session_state.get('rent_confidence', 'Missing')}")
        return

    st.warning("RentCast did not return a usable rent estimate or comparable rentals for the submitted property.")
    if submitted_address:
        st.caption(f"Address submitted to RentCast: {submitted_address}")
    if rentcast_error:
        st.error(rentcast_error)

    with st.container(border=True):
        top = st.columns(3)
        with top[0]:
            st.selectbox("Fallback rent source", RENT_FALLBACK_SOURCES[1:], key="rent_fallback_source")
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
                st.selectbox("Source", RENT_FALLBACK_SOURCES[1:], key=f"manual_rent_comp_{idx}_source")
                st.text_input("Notes", key=f"manual_rent_comp_{idx}_notes")

        if st.button("Apply Rent Fallback", type="secondary"):
            state = ui.apply_rent_fallback_state()
            if state.get("manual_rent_comp_average", 0) > 0:
                st.session_state["rent"] = int(state["manual_rent_comp_average"])
            st.success("Rent fallback applied. Review rent confidence before analyzing.")

        state = ui.apply_rent_fallback_state()
        cols = st.columns(4)
        cols[0].metric("Rent Source", state.get("rent_source", "Missing / RentCast unavailable"))
        cols[1].metric("Rent Confidence", state.get("rent_confidence", "Weak"))
        cols[2].metric("Manual Comps", state.get("manual_rent_comp_count", 0))
        cols[3].metric("Fallback Average", ui.money(state.get("manual_rent_comp_average", 0)))
        if state.get("rent_verification_needed") == "Yes":
            st.warning(state.get("slow_flip_rent_risk", "Verify rent comps manually."))
