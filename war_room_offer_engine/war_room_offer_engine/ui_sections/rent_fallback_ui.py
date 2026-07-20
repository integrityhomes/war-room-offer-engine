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


def _number(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _source_is_rentcast(value) -> bool:
    source = _text(value).lower()
    return "rentcast" in source and not any(
        marker in source for marker in ["missing", "unavailable"]
    )


def _usable_comp_rows(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [
        dict(row)
        for row in value
        if isinstance(row, dict) and _number(row.get("rent")) > 0
    ]


def _rentcast_value_evidence(data: dict, comps: list[dict] | None = None) -> bool:
    """Whether a positive rent value has enough provenance to be called RentCast.

    Metadata that merely proves a lookup was attempted (an address, an error, or
    empty quality fields) is not value evidence. This distinction prevents the
    application's historical $900 default from becoming an AVM after restart.
    """
    comps = _usable_comp_rows(comps if isinstance(comps, list) else data.get("rent_comps", []))
    if comps:
        return True
    if _number(data.get("rentcast_rent_avm")) > 0:
        return True

    rent = _number(data.get("rent") or data.get("rent_estimate"))
    if rent <= 0:
        return False

    submitted = bool(_text(data.get("rentcast_submitted_address")))
    source = _source_is_rentcast(data.get("rent_source"))
    trail = data.get("rent_search_trail")
    trail_present = isinstance(trail, list) and bool(trail)
    search_mode = bool(_text(data.get("rent_search_mode")))
    preview_marker = bool(data.get("rentcast_intelligence_preview_active"))

    return bool(
        (source and submitted)
        or trail_present
        or (submitted and search_mode)
        or (preview_marker and (submitted or search_mode))
    )


def _rentcast_context_present(data: dict) -> bool:
    """Whether there is RentCast context worth displaying, even without value."""
    return bool(
        _rentcast_value_evidence(data)
        or _text(data.get("rentcast_submitted_address"))
        or _text(data.get("rentcast_rent_error"))
        or data.get("rentcast_lookup_retry_used")
        or (isinstance(data.get("rent_search_trail"), list) and data.get("rent_search_trail"))
    )


def _state_has_rentcast_evidence(st) -> bool:
    state = st.session_state
    rows = state.get("rentcast_rent_comps", []) or state.get("rent_comps", [])
    data = {
        "rent": state.get("rent", 0),
        "rent_estimate": state.get("rent_estimate", 0),
        "rent_source": state.get("rent_source", ""),
        "rent_comps": rows,
        "rentcast_rent_avm": state.get("rentcast_rent_avm", 0),
        "rentcast_submitted_address": state.get("rentcast_submitted_address", ""),
        "rent_search_mode": state.get("rent_search_mode", ""),
        "rent_search_trail": state.get("rent_search_trail", []),
        "rentcast_intelligence_preview_active": state.get("rentcast_intelligence_preview_active", False),
    }
    return _rentcast_value_evidence(data, rows)


def _normalized_data(st) -> dict:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    original = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    data = dict(original) if isinstance(original, dict) else {}

    # Plain-address pulls store returned RentCast data directly in session state.
    # A restart can also restore legacy defaults and empty quality keys. Only a
    # value with positive RentCast provenance may populate this RentCast panel.
    state_has_value_evidence = _state_has_rentcast_evidence(st)
    state_comps = st.session_state.get("rentcast_rent_comps", []) or st.session_state.get("rent_comps", [])
    state_rent = st.session_state.get("rent", 0) if state_has_value_evidence else 0
    state_fallbacks = {
        "rent": state_rent,
        "rent_estimate": state_rent,
        "rent_source": st.session_state.get("rent_source", "") if state_has_value_evidence else "",
        "rent_confidence": st.session_state.get("rent_confidence", "") if state_has_value_evidence else "",
        "rent_verification_needed": st.session_state.get("rent_verification_needed", "") if state_has_value_evidence else "",
        "rent_comps": state_comps,
        "rent_comp_count": st.session_state.get("rentcast_rent_comp_count", 0) or st.session_state.get("rentcast_comp_count", 0),
        "rent_comp_average": st.session_state.get("rentcast_rent_comp_average", 0) or st.session_state.get("rent_comp_average", 0),
        "rent_comp_median": st.session_state.get("rentcast_rent_comp_median", 0) or st.session_state.get("rent_comp_median", 0),
        "rentcast_rent_avm": st.session_state.get("rentcast_rent_avm", 0),
        "verified_rent_comp_count": st.session_state.get("verified_rent_comp_count", 0),
        "rent_search_mode": st.session_state.get("rent_search_mode", ""),
        "rent_search_trail": st.session_state.get("rent_search_trail", []),
        "rent_requires_human_verification": st.session_state.get("rent_requires_human_verification"),
        "rent_comp_quality_summary": st.session_state.get("rent_comp_quality_summary", {}),
        "rentcast_submitted_address": st.session_state.get("rentcast_submitted_address", ""),
        "rentcast_rent_error": st.session_state.get("rentcast_rent_error", ""),
        "rentcast_lookup_retry_used": st.session_state.get("rentcast_lookup_retry_used", False),
        "rentcast_intelligence_preview_active": st.session_state.get("rentcast_intelligence_preview_active", False),
    }
    for key, value in state_fallbacks.items():
        if data.get(key) in _EMPTY and value not in _EMPTY:
            data[key] = value
    return data


def _rentcast_comps(st) -> list[dict]:
    data = _normalized_data(st)
    return _usable_comp_rows(data.get("rent_comps", []) or [])


def _data_has_rentcast_evidence(st, data: dict, comps: list[dict]) -> bool:
    del st  # retained for backward-compatible callers and regression tests
    return _rentcast_value_evidence(data, comps)


def _apply_rentcast_state(st, data: dict, comps: list[dict]) -> None:
    rent = int(_number(data.get("rent") or data.get("rent_estimate")))
    if rent > 0:
        st.session_state["rent"] = rent
    if len(comps) >= 3:
        source = "RentCast Rental Comps"
        confidence = "Strong verified rent comps"
        verification_needed = "No"
    elif comps:
        source = "RentCast Rental Comps"
        confidence = "Medium fallback comps"
        verification_needed = "Yes"
    elif rent > 0:
        source = "RentCast AVM only"
        confidence = "Weak / AVM only"
        verification_needed = "Yes"
    else:
        source = "Missing / RentCast unavailable"
        confidence = "Missing"
        verification_needed = "Yes"
    st.session_state["rent_source"] = source
    st.session_state["rent_confidence"] = confidence
    st.session_state["rent_verification_needed"] = verification_needed
    st.session_state["rentcast_comp_count"] = len(comps)
    st.session_state["rentcast_rent_comp_count"] = len(comps)
    st.session_state["rent_comp_count"] = len(comps)
    st.session_state["rentcast_submitted_address"] = data.get("rentcast_submitted_address", "")


def render_rent_fallback_section(st, ui) -> None:
    st.subheader("Rent Verification")
    st.caption("RentCast results populate automatically. Manual fallback is only needed when the API returns no usable estimate or comparables.")

    data = _normalized_data(st)
    comps = _rentcast_comps(st)
    rentcast_rent = int(_number(data.get("rent") or data.get("rent_estimate")))
    rentcast_error = _text(data.get("rentcast_rent_error"))
    submitted_address = _text(data.get("rentcast_submitted_address"))
    has_rentcast_value = _data_has_rentcast_evidence(st, data, comps)

    if has_rentcast_value and (rentcast_rent > 0 or comps):
        _apply_rentcast_state(st, data, comps)
        if len(comps) >= 3:
            st.success(
                f"RentCast supports ${rentcast_rent:,.0f}/month with {len(comps)} comparable rental(s)."
                if rentcast_rent > 0
                else f"RentCast returned {len(comps)} comparable rental(s)."
            )
        elif comps:
            st.warning(
                f"RentCast estimates ${rentcast_rent:,.0f}/month with only {len(comps)} comparable rental(s). Verify rent before committing."
                if rentcast_rent > 0
                else f"RentCast returned only {len(comps)} comparable rental(s). Verify rent before committing."
            )
        else:
            st.warning(
                f"RentCast estimates ${rentcast_rent:,.0f}/month, but returned no comparable rentals. Treat this as AVM-only evidence and verify locally."
            )
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

    st.warning("No current RentCast rent result is loaded for this property. A default or manually entered rent is not an API verification.")
    current_field_rent = _number(st.session_state.get("rent", 0))
    if current_field_rent > 0 and not has_rentcast_value:
        st.caption(
            f"The current ${current_field_rent:,.0f} rent field has no RentCast provenance and was not treated as verified API data."
        )
    if submitted_address:
        st.caption(f"Address submitted to RentCast: {submitted_address}")
    if rentcast_error:
        st.error(rentcast_error)
    elif _rentcast_context_present(data):
        st.caption("A RentCast lookup context exists, but it did not provide a usable rent value or comparable rental evidence.")

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
