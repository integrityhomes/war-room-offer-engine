from __future__ import annotations

import json

try:
    from rentcast_auto_enrichment import build_sold_comp_intelligence
    from sold_comps import comp_summary_json
except ImportError:
    try:
        from .rentcast_auto_enrichment import build_sold_comp_intelligence
        from .sold_comps import comp_summary_json
    except ImportError:
        from war_room_offer_engine.rentcast_auto_enrichment import build_sold_comp_intelligence
        from war_room_offer_engine.sold_comps import comp_summary_json


def _list_value(*values):
    for value in values:
        if isinstance(value, list) and value:
            return value
    return []


def _dict_value(*values):
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _first_value(*values):
    for value in values:
        if value not in [None, "", 0, 0.0, [], {}]:
            return value
    return 0


def _number(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _store_auto_arv_state(st, scored_comps, summary) -> None:
    summary = dict(summary or {})
    excluded_flags = []
    for comp in scored_comps or []:
        if not comp.get("include_default", False) or comp.get("score") == "Bad Comp":
            excluded_flags.extend(comp.get("flags", []) or [])

    auto_arv = _number(summary.get("recommended_arv"))
    st.session_state["auto_sold_comps"] = scored_comps or []
    st.session_state["auto_comp_count"] = len(scored_comps or [])
    st.session_state["auto_comp_source"] = "RentCast"
    st.session_state["auto_arv_summary"] = summary
    st.session_state["auto_recommended_arv"] = int(auto_arv) if auto_arv > 0 else 0
    st.session_state["auto_low_arv"] = int(_number(summary.get("low_arv")))
    st.session_state["auto_conservative_arv"] = int(_number(summary.get("conservative_arv")))
    st.session_state["auto_average_arv"] = int(_number(summary.get("average_arv")))
    st.session_state["auto_high_arv"] = int(_number(summary.get("high_arv")))
    st.session_state["strong_comp_count"] = int(summary.get("strong_comp_count", 0) or 0)
    st.session_state["good_comp_count"] = int(summary.get("good_comp_count", 0) or 0)
    st.session_state["weak_comp_count"] = int(summary.get("weak_comp_count", 0) or 0)
    st.session_state["excluded_comp_count"] = int(summary.get("excluded_comp_count", 0) or 0)
    st.session_state["auto_comp_radius"] = summary.get("search_radius") or st.session_state.get("auto_comp_radius", "1 mile")
    st.session_state["auto_comp_date_range"] = summary.get("date_range") or st.session_state.get("auto_comp_date_range", "Last 12 months")
    st.session_state["auto_comp_summary_json"] = comp_summary_json(scored_comps or [])
    st.session_state["excluded_comp_flags_json"] = json.dumps(sorted(set(str(flag) for flag in excluded_flags)))

    if scored_comps:
        st.session_state["auto_comp_messages"] = [
            f"Automatically scored {len(scored_comps)} RentCast sold comparable(s)."
        ]
    if auto_arv > 0:
        st.session_state["arv"] = int(auto_arv)
        st.session_state["arv_source_used"] = "Automatic Sold Comps"
        st.session_state["value_source"] = "Automatic Sold Comps"
        st.session_state["arv_confidence"] = summary.get("arv_confidence", "Weak")
        st.session_state["arv_fallback_reason"] = summary.get("explanation", "Automatic RentCast sold comps were scored and applied.")


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
    raw_sold_comps = _list_value(
        data.get("rentcast_sold_comps"),
        last_pull.get("rentcast_sold_comps"),
        st.session_state.get("rentcast_sold_comps"),
    )
    scored_comps = _list_value(
        data.get("auto_sold_comps"),
        last_pull.get("auto_sold_comps"),
        st.session_state.get("auto_sold_comps"),
    )
    auto_summary = _dict_value(
        data.get("auto_arv_summary"),
        last_pull.get("auto_arv_summary"),
        st.session_state.get("auto_arv_summary"),
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

    if raw_sold_comps and (not scored_comps or not auto_summary):
        subject_data = {
            "address": data.get("address") or st.session_state.get("address", ""),
            "city": data.get("city") or st.session_state.get("city", ""),
            "state": data.get("state") or st.session_state.get("state", ""),
            "zip": data.get("zip") or st.session_state.get("zip", ""),
            "beds": data.get("beds") or st.session_state.get("beds", 0),
            "baths": data.get("baths") or st.session_state.get("baths", 0),
            "sqft": data.get("sqft") or st.session_state.get("sqft", 0),
            "property_type": data.get("property_type") or st.session_state.get("property_type", ""),
            "notes": st.session_state.get("notes", ""),
            "repair_notes": st.session_state.get("repair_notes", ""),
            "manual_repair_notes": st.session_state.get("manual_repair_notes", ""),
        }
        scored_comps, auto_summary = build_sold_comp_intelligence(subject_data, raw_sold_comps)

    rent_comp_count = len(rent_comps)
    sold_comp_count = len(raw_sold_comps)

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

    st.session_state["rentcast_sold_comps"] = raw_sold_comps
    st.session_state["rentcast_sold_comp_count"] = sold_comp_count
    st.session_state["rentcast_value_comp_count"] = sold_comp_count

    if scored_comps or auto_summary:
        _store_auto_arv_state(st, scored_comps, auto_summary)

    if rentcast_arv > 0:
        st.session_state["rentcast_arv"] = rentcast_arv
        if not st.session_state.get("auto_recommended_arv"):
            st.session_state["arv"] = rentcast_arv
            st.session_state["arv_source_used"] = _first_value(
                data.get("arv_source"),
                last_pull.get("arv_source"),
                st.session_state.get("arv_source_used"),
            ) or "RentCast AVM"
            st.session_state["value_source"] = st.session_state["arv_source_used"]
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
