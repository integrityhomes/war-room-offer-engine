from __future__ import annotations

from typing import Any


def _money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except Exception:
        return "$0"


def render_rentcast_rent_comps_panel(st) -> bool:
    comps = st.session_state.get("rentcast_rent_comps", []) or []
    submitted = st.session_state.get("rentcast_submitted_address", "")
    estimate = st.session_state.get("rent", 0) if st.session_state.get("rent_source") == "RentCast" else 0
    status = st.session_state.get("rentcast_rent_http_status", 0)
    error = st.session_state.get("rentcast_rent_error", "")

    st.markdown("### Automatic RentCast Rent & Comparables")
    if submitted:
        st.caption(f"Address submitted to RentCast: {submitted}")

    if comps:
        metrics = st.columns(4)
        metrics[0].metric("RentCast estimate", _money(estimate))
        metrics[1].metric("Comparable rentals", len(comps))
        metrics[2].metric("Comp average", _money(st.session_state.get("rentcast_rent_comp_average", 0)))
        metrics[3].metric("Comp median", _money(st.session_state.get("rentcast_rent_comp_median", 0)))
        st.success("RentCast estimate and comparable rentals were pulled automatically. No manual comp entry is required.")
        rows = []
        for comp in comps:
            rows.append(
                {
                    "Address": comp.get("address", ""),
                    "Beds": comp.get("beds", 0),
                    "Baths": comp.get("baths", 0),
                    "Sqft": comp.get("sqft", 0),
                    "Listed Rent": _money(comp.get("rent", 0)),
                    "Distance (mi)": comp.get("distance_miles", 0),
                    "Correlation": comp.get("correlation", 0),
                    "Property Type": comp.get("property_type", ""),
                    "Listed Date": comp.get("listed_date", ""),
                }
            )
        st.dataframe(rows, use_container_width=True)
        st.caption(
            f"Rent confidence: {st.session_state.get('rent_confidence', 'Strong verified rent comps')} | "
            f"RentCast HTTP status: {status or 'Not recorded'}"
        )
        return True

    if error:
        st.warning(f"RentCast rent lookup failed: {error}")
    else:
        st.warning(
            "RentCast returned no usable comparable rentals. The exact submitted address and HTTP status are shown above for troubleshooting."
        )
    if status:
        st.caption(f"RentCast rent HTTP status: {status}")
    return False


def render_rentcast_value_comps_panel(st) -> bool:
    comps = st.session_state.get("rentcast_value_comps", []) or []
    submitted = st.session_state.get("rentcast_submitted_address", "")
    estimate = st.session_state.get("rentcast_arv", 0)
    status = st.session_state.get("rentcast_value_http_status", 0)
    error = st.session_state.get("rentcast_value_error", "")

    st.markdown("### Automatic RentCast Value & Sold Comparables")
    if submitted:
        st.caption(f"Address submitted to RentCast: {submitted}")

    if comps:
        summary = st.session_state.get("auto_arv_summary", {}) or {}
        metrics = st.columns(4)
        metrics[0].metric("RentCast value estimate", _money(estimate))
        metrics[1].metric("Sold comparables", len(comps))
        metrics[2].metric("Comp-based ARV", _money(summary.get("recommended_arv", 0)))
        metrics[3].metric("ARV confidence", summary.get("arv_confidence", "Not enough data"))
        st.success("RentCast value and sold comparables were pulled automatically and sent into the ARV scoring engine.")
        rows = []
        for comp in comps:
            rows.append(
                {
                    "Address": comp.get("comp_address", ""),
                    "Sold Price": _money(comp.get("sold_price", 0)),
                    "Sold Date": comp.get("sold_date", ""),
                    "Beds": comp.get("beds", 0),
                    "Baths": comp.get("baths", 0),
                    "Sqft": comp.get("square_feet", 0),
                    "Distance (mi)": comp.get("distance_miles", 0),
                    "Property Type": comp.get("property_type", ""),
                    "Source": comp.get("source", "RentCast"),
                }
            )
        st.dataframe(rows, use_container_width=True)
        st.caption(f"RentCast value HTTP status: {status or 'Not recorded'}")
        return True

    if error:
        st.warning(f"RentCast value/sold-comp lookup failed: {error}")
    else:
        st.info("RentCast returned a value estimate without usable sold comparables, or returned no value data.")
    if status:
        st.caption(f"RentCast value HTTP status: {status}")
    return False
