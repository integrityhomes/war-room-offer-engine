from __future__ import annotations

try:
    from rentcast_auto_comps_ui import render_rentcast_rent_comps_panel
except ImportError:
    try:
        from ..rentcast_auto_comps_ui import render_rentcast_rent_comps_panel
    except ImportError:
        from war_room_offer_engine.rentcast_auto_comps_ui import render_rentcast_rent_comps_panel


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
    st.subheader("Rent Analysis")
    st.caption(
        "RentCast is the primary source. Manual fallback inputs appear only when RentCast returns no usable comparable rentals."
    )

    automatic_comps_found = render_rentcast_rent_comps_panel(st)

    with st.expander(
        "Manual rent fallback" if automatic_comps_found else "Manual rent fallback — RentCast needs help",
        expanded=not automatic_comps_found,
    ):
        if automatic_comps_found:
            st.info("Automatic RentCast comps are available above. Use this section only to override or document a different rent conclusion.")
        else:
            st.warning("RentCast could not verify rent. Slow Flip numbers are not reliable until rent comps are verified.")

        top = st.columns(3)
        with top[0]:
            st.selectbox("Fallback rent source", RENT_FALLBACK_SOURCES, key="rent_fallback_source")
        with top[1]:
            st.selectbox("Fallback rent confidence", RENT_CONFIDENCE_LEVELS, key="manual_rent_confidence")
        with top[2]:
            st.number_input("Seller-stated rent", min_value=0, step=50, key="seller_stated_rent")

        st.caption("Manual rent comp inputs")
        for idx in range(1, 4):
            with st.expander(f"Manual rent comp {idx}", expanded=(idx == 1 and not automatic_comps_found)):
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
        if state.get("rent_verification_needed") == "Yes" and not automatic_comps_found:
            st.warning(state.get("slow_flip_rent_risk", "Verify rent comps manually."))
