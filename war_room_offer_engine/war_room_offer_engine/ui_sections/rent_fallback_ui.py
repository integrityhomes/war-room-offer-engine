from __future__ import annotations

try:
    import address_rentcast_bridge  # noqa: F401 - upgrade plain-address RentCast lookups
except ImportError:
    try:
        from .. import address_rentcast_bridge  # noqa: F401
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge  # noqa: F401


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


_EMPTY = [None, "", 0, 0.0, [], {}]


def _text(value) -> str:
    return str(value or "").strip()


def _source_is_rentcast(value) -> bool:
    source = _text(value).lower()
    return "rentcast" in source and not any(
        marker in source for marker in ["missing", "unavailable"]
    )


def _rentcast_evidence_present(data: dict, comps: list[dict] | None = None) -> bool:
    comps = comps if isinstance(comps, list) else data.get("rent_comps", [])
    if isinstance(comps, list) and any(isinstance(row, dict) for row in comps):
        return True
    if _source_is_rentcast(data.get("rent_source")):
        return True
    return any(
        data.get(key) not in _EMPTY
        for key in [
            "rentcast_submitted_address",
            "rentcast_rent_avm",
            "rentcast_rent_error",
            "verified_rent_comp_count",
            "rent_search_mode",
            "rent_search_trail",
        ]
    )


def _state_rentcast_evidence_present(st) -> bool:
    state = st.session_state
    if _source_is_rentcast(state.get("rent_source")):
        return True
    rows = state.get("rentcast_rent_comps") or []
    if isinstance(rows, list) and rows:
        return True
    return any(
        state.get(key) not in _EMPTY
        for key in [
            "rentcast_submitted_address",
            "rentcast_rent_avm",
            "rentcast_rent_error",
            "verified_rent_comp_count",
            "rent_search_mode",
            "rent_search_trail",
        ]
    )


def _normalized_data(st) -> dict:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    original = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    data = dict(original) if isinstance(original, dict) else {}

    # Plain-address pulls store returned RentCast fields directly in session
    # state. A Streamlit restart also restores legacy demo defaults (notably
    # rent=$900), so only merge the state rent when there is real RentCast
    # provenance. This prevents a default number from being labeled verified.
    state_has_rentcast = _state_rentcast_evidence_present(st)
    state_rent = st.session_state.get("rent", 0) if state_has_rentcast else 0
    state_fallbacks = {
        "rent": state_rent,
        "rent_estimate": state_rent,
        "rent_source": st.session_state.get("rent_source", "") if state_has_rentcast else "",
        "rent_comps": st.session_state.get("rentcast_rent_comps", []) or st.session_state.get("rent_comps", []),
        "rent_comp_count": st.session_state.get("rentcast_rent_comp_count", 0) or st.session_state.get("rentcast_comp_count", 0),
        "rent_comp_average": st.session_state.get("rentcast_rent_comp_average", 0) or st.session_state.get("rent_comp_average", 0),
        "rent_comp_median": st.session_state.get("rentcast_rent_comp_median", 0) or st.session_state.get("rent_comp_median", 0),
        "rentcast_submitted_address": st.session_state.get("rentcast_submitted_address", ""),
        "rentcast_rent_avm": st.session_state.get("rentcast_rent_avm", 0),
        "verified_rent_comp_count": st.session_state.get("verified_rent_comp_count", 0),
        "rent_search_mode": st.session_state.get("rent_search_mode", ""),
        "rent_search_trail": st.session_state.get("rent_search_trail", []),
        "rentcast_rent_error": st.session_state.get("rentcast_rent_error", ""),
        "rentcast_lookup_retry_used": st.session_state.get("rentcast_lookup_retry_used", False),
    }
    for key, value in state_fallbacks.items():
        if data.get(key) in _EMPTY and value not in _EMPTY:
            data[key] = value
    return data


def _rentcast_comps(st) -> list[dict]:
    data = _normalized_data(st)
    comps = data.get("rent_comps", []) or []
    clean = []
    for item in comps:
        if not isinstance(item, dict):
            continue
        try:
            rent = float(item.get("rent", 0) or 0)
        except Exception:
            rent = 0
        if rent > 0:
            clean.append(item)
    return clean


def _apply_rentcast_state(st, data: dict, comps: list[dict]) -> None:
    rent = int(float(data.get("rent") or data.get("rent_estimate") or 0))
    if rent > 0:
        st.session_state["rent"] = rent
    source = _text(data.get("rent_source"))
    if not _source_is_rentcast(source):
        source = "RentCast" if comps else "RentCast AVM only" if rent > 0 else "Missing"
    st.session_state["rent_source"] = source
    st.session_state["rent_confidence"] = (
        "Strong verified rent comps"
        if len(comps) >= 3
        else "Medium fallback comps"
        if len(comps) in [1, 2]
        else "AVM only"
        if rent > 0
        else "Missing"
    )
    st.session_state["rent_verification_needed"] = "No" if len(comps) >= 3 else "Yes"
    st.session_state["rentcast_comp_count"] = len(comps)
    st.session_state["rentcast_rent_comp_count"] = len(comps)
    st.session_state["rent_comp_count"] = len(comps)
    st.session_state["rentcast_submitted_address"] = data.get("rentcast_submitted_address", "")


def render_rent_fallback_section(st, ui) -> None:
    st.subheader("Rent Verification")
    st.caption("RentCast results populate automatically. Manual fallback is only needed when the API returns no usable estimate or comparables.")

    data = _normalized_data(st)
    comps = _rentcast_comps(st)
    rentcast_rent = int(float(data.get("rent") or data.get("rent_estimate") or 0))
    rentcast_error = str(data.get("rentcast_rent_error") or "")
    submitted_address = str(data.get("rentcast_submitted_address") or "")
    has_rentcast_evidence = _rentcast_evidence_present(data, comps)

    if has_rentcast_evidence and (rentcast_rent > 0 or comps):
        _apply_rentcast_state(st, data, comps)
        if rentcast_rent > 0 and len(comps) >= 3:
            st.success(
                f"RentCast supports ${rentcast_rent:,.0f}/month with {len(comps)} comparable rental(s)."
            )
        elif rentcast_rent > 0 and comps:
            st.warning(
                f"RentCast estimates ${rentcast_rent:,.0f}/month, but only {len(comps)} comparable rental(s) were returned. Verify rent before committing."
            )
        elif rentcast_rent > 0:
            st.warning(
                f"RentCast estimates ${rentcast_rent:,.0f}/month, but returned no comparable rentals. Treat this as AVM-only evidence and verify locally."
            )
        else:
            st.info(f"RentCast returned {len(comps)} comparable rental(s), but no usable rent estimate.")
        if submitted_address:
            st.caption(f"Address submitted to RentCast: {submitted_address}")
        if data.get("rentcast_lookup_retry_used"):
            st.caption("RentCast needed an automatic address-only retry after the subject-attribute lookup returned no usable rental result.")
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
    if rentcast_rent > 0 and not has_rentcast_evidence:
        st.caption(
            f"The current ${rentcast_rent:,.0f} rent field has no RentCast provenance and was not treated as verified API data."
        )
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
