from __future__ import annotations

import time
from typing import Any

try:
    import address_rentcast_bridge as bridge
    import data_sources as ds
    import deal_library as library
    import property_location_guard as location
    import rentcast_auto_enrichment as rentcast
    import rentcast_credit_guard as credit_guard
    import rentcast_intelligence_core as core
    import rentcast_intelligence_preview as preview
    import rentcast_intelligence_rent_reconciliation as rent_reconciliation
    import rentcast_property_enrichment as enrichment
    import rentcast_recorded_sales as recorded_sales
except ImportError:
    try:
        from . import address_rentcast_bridge as bridge
        from . import data_sources as ds
        from . import deal_library as library
        from . import property_location_guard as location
        from . import rentcast_auto_enrichment as rentcast
        from . import rentcast_credit_guard as credit_guard
        from . import rentcast_intelligence_core as core
        from . import rentcast_intelligence_preview as preview
        from . import rentcast_intelligence_rent_reconciliation as rent_reconciliation
        from . import rentcast_property_enrichment as enrichment
        from . import rentcast_recorded_sales as recorded_sales
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge as bridge
        from war_room_offer_engine import data_sources as ds
        from war_room_offer_engine import deal_library as library
        from war_room_offer_engine import property_location_guard as location
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine import rentcast_credit_guard as credit_guard
        from war_room_offer_engine import rentcast_intelligence_core as core
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import rentcast_intelligence_rent_reconciliation as rent_reconciliation
        from war_room_offer_engine import rentcast_property_enrichment as enrichment
        from war_room_offer_engine import rentcast_recorded_sales as recorded_sales


_NEUTRAL_SOLD_STAGES = (
    {"name": "Local", "radius": 1.0, "days": 365, "sqft_tolerance": 0.25},
    {"name": "Expanded", "radius": 3.0, "days": 730, "sqft_tolerance": 0.35},
    {"name": "Wide area", "radius": 10.0, "days": 1095, "sqft_tolerance": 0.45},
    {"name": "Extended area", "radius": 25.0, "days": 1825, "sqft_tolerance": 0.55},
    {"name": "Remote area", "radius": 50.0, "days": 2555, "sqft_tolerance": 0.65},
)


class LocationMismatchError(RuntimeError):
    pass


_ORIGINAL_ENRICH = getattr(
    rentcast,
    "_location_safety_original_enrich",
    rentcast.enrich_property_with_rentcast,
)
_ORIGINAL_BRIDGE_LOOKUP = getattr(
    bridge,
    "_location_safety_original_lookup",
    bridge.lookup_rentcast_with_full_enrichment,
)
_ORIGINAL_SUBJECT_LOOKUP = getattr(
    enrichment,
    "_location_safety_original_subject_lookup",
    enrichment._lookup_subject_record,
)
_ORIGINAL_RENT_ANALYSIS = getattr(
    enrichment,
    "_location_safety_original_rent_analysis",
    enrichment.analyze_rent_intelligence,
)
_ORIGINAL_CREDIT_PANEL = getattr(
    credit_guard,
    "_location_safety_original_credit_panel",
    credit_guard.render_credit_panel,
)
_ORIGINAL_BUTTON_GUARD = getattr(
    credit_guard,
    "_location_safety_original_button_guard",
    credit_guard._button_should_be_disabled,
)


def _full_address(data: dict[str, Any] | None) -> str:
    data = data if isinstance(data, dict) else {}
    try:
        built = rentcast.build_full_address(data)
    except Exception:
        built = ""
    return str(
        built
        or data.get("formatted_address")
        or data.get("address")
        or data.get("property_address")
        or ""
    ).strip()


def _safe_subject_lookup(
    address: str,
    api_key: str,
    session: Any = None,
) -> tuple[dict[str, Any], str, bool]:
    facts, error, cache_hit = _ORIGINAL_SUBJECT_LOOKUP(address, api_key, session=session)
    if facts:
        valid, mismatch = location.validate_resolved_location(address, facts)
        if not valid:
            raise LocationMismatchError(mismatch)
    return facts, error, cache_hit


def _safe_enrich(
    data: dict[str, Any],
    api_key: str,
    session: Any = None,
) -> dict[str, Any]:
    data = dict(data or {})
    address = _full_address(data)
    complete, message = location.validate_property_input(address)
    if not complete:
        return {**data, **location.invalid_location_result(address, message)}
    try:
        result = _ORIGINAL_ENRICH(
            data,
            api_key,
            **({} if session is None else {"session": session}),
        )
    except LocationMismatchError as exc:
        return {**data, **location.invalid_location_result(address, str(exc))}
    result = dict(result or {})
    summary = result.get("rentcast_property_record_summary")
    resolved = summary if isinstance(summary, dict) else {
        "formatted_address": result.get("formatted_address"),
        "address": result.get("address"),
        "city": result.get("city"),
        "state": result.get("state"),
        "zip": result.get("zip"),
    }
    valid, mismatch = location.validate_resolved_location(address, resolved)
    if not valid:
        return {**data, **location.invalid_location_result(address, mismatch)}
    result["location_verification_failed"] = False
    result["location_verification_error"] = ""
    result["location_verification_status"] = "Matched requested city/state/ZIP"
    result["requested_property_address"] = address
    result["resolved_property_address"] = (
        resolved.get("formatted_address")
        or ", ".join(
            part for part in [
                str(resolved.get("address") or "").strip(),
                str(resolved.get("city") or "").strip(),
                str(resolved.get("state") or "").strip(),
                str(resolved.get("zip") or "").strip(),
            ] if part
        )
    )
    return result


def _safe_bridge_lookup(
    address: str,
    beds: float = 0,
    baths: float = 0,
    sqft: float = 0,
) -> dict[str, Any]:
    complete, message = location.validate_property_input(address)
    if not complete:
        result = location.invalid_location_result(address, message)
        try:
            bridge._hydrate_state(result)
        except Exception:
            pass
        return result
    result = _ORIGINAL_BRIDGE_LOOKUP(address, beds=beds, baths=baths, sqft=sqft)
    if isinstance(result, dict) and result.get("location_verification_failed"):
        try:
            bridge._hydrate_state(result)
        except Exception:
            pass
    return result


def _neutral_rent_analysis(
    subject: dict[str, Any],
    comps: list[dict[str, Any]],
    avm_rent: float = 0,
) -> dict[str, Any]:
    result = dict(_ORIGINAL_RENT_ANALYSIS(subject, comps, avm_rent) or {})
    mapping = {
        "Rural": "Wide area",
        "Deep rural": "Remote area",
        "Remote rural": "Remote area",
    }
    mode = mapping.get(str(result.get("rent_search_mode") or ""), result.get("rent_search_mode"))
    result["rent_search_mode"] = mode
    if str(result.get("rent_confidence") or "") == "Weak rural fallback comps":
        result["rent_confidence"] = "Weak wide-area fallback comps"
    result["wide_area_search_used"] = mode in {"Wide area", "Extended area", "Remote area"}
    result["search_scope_note"] = (
        "Search mode describes how far the comp search expanded; it does not classify the city as rural."
    )
    return result


def _neutral_search_mode(max_distance: float, max_days: int, missing_age: bool) -> str:
    if not missing_age and max_distance <= 5 and max_days <= 270:
        return "Local"
    if not missing_age and max_distance <= 10 and max_days <= 540:
        return "Expanded"
    if max_distance <= 25:
        return "Wide area"
    return "Remote area"


def _input_value(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    return str(
        state.get("decision_property_input")
        or state.get("one_load_property_address")
        or state.get("one_load_listing_url")
        or ""
    ).strip()


def render_credit_panel_with_location_guard(st: Any) -> None:
    state = st.session_state
    credit_guard._reset_confirmation_for_property(st)
    preview_on = preview.preview_enabled(st)
    minimum, maximum = credit_guard.estimate_request_range(state, preview_on=preview_on)
    limit = credit_guard._configured_limit(maximum)
    state["rentcast_credit_guard_estimated_min"] = minimum
    state["rentcast_credit_guard_estimated_max"] = maximum
    state["rentcast_credit_guard_limit"] = limit

    mode = "Verified intelligence" if preview_on else "Basic RentCast"
    st.info(
        f"RentCast request budget — {mode}: an uncached fresh pull is estimated to use "
        f"{minimum}–{maximum} successful API request(s). Saved deals and fresh cache hits use 0 new requests. "
        f"This run is hard-capped at {limit}."
    )
    if preview_on:
        st.caption(
            "Verified intelligence expands distance only when tighter evidence is insufficient. "
            "A Wide-area search label describes radius, not whether the property is in a rural city."
        )

    value = _input_value(state)
    if value:
        complete, message = location.validate_property_input(value)
        state["property_input_location_valid"] = complete
        state["property_input_location_error"] = message
        if not complete:
            st.warning(message + " The paid pull is disabled until the location is complete.")
    else:
        state["property_input_location_valid"] = False
        state["property_input_location_error"] = "Enter a property address or listing URL."

    last = state.get(credit_guard.LAST_STATS_KEY, {}) or {}
    if isinstance(last, dict) and last:
        actual = int(last.get("successful_requests", 0) or 0)
        hits = int(last.get("cache_hits", 0) or 0)
        blocked = int(last.get("blocked_requests", 0) or 0)
        text = f"Last analysis: {actual} new RentCast request(s), {hits} cache hit(s)"
        if blocked:
            text += f", {blocked} request(s) blocked by the budget"
        st.caption(text + ".")

    if credit_guard.duplicate_analysis_is_fresh(state) and not state.get("deal_library_force_refresh", False):
        age_minutes = max(
            int((time.time() - float(state.get(credit_guard.LAST_PULL_EPOCH_KEY, 0) or 0)) / 60),
            0,
        )
        st.success(
            f"This property's current analysis is about {age_minutes} minute(s) old. Reuse it; changing "
            "price or deal lane does not require another paid pull."
        )

    if state.get("deal_library_force_refresh", False):
        st.warning(
            "Refresh live paid data bypasses the saved Deal Library result and may consume the full request budget."
        )
        st.checkbox(
            f"I understand this refresh may use up to {maximum} RentCast requests",
            key=credit_guard.CONFIRM_KEY,
        )


def button_guard_with_location(st: Any) -> tuple[bool, str]:
    value = _input_value(st.session_state)
    complete, message = location.validate_property_input(value)
    if not complete:
        return True, message
    return _ORIGINAL_BUTTON_GUARD(st)


def install_engine() -> bool:
    if getattr(enrichment, "_property_location_safety_engine_installed", False):
        return True

    enrichment._location_safety_original_subject_lookup = _ORIGINAL_SUBJECT_LOOKUP
    enrichment._location_safety_original_rent_analysis = _ORIGINAL_RENT_ANALYSIS
    enrichment._lookup_subject_record = _safe_subject_lookup
    enrichment.analyze_rent_intelligence = _neutral_rent_analysis

    rentcast._location_safety_original_enrich = _ORIGINAL_ENRICH
    bridge._location_safety_original_lookup = _ORIGINAL_BRIDGE_LOOKUP
    rentcast.enrich_property_with_rentcast = _safe_enrich
    bridge.enrich_property_with_rentcast = _safe_enrich
    bridge.lookup_rentcast_with_full_enrichment = _safe_bridge_lookup
    ds.lookup_rentcast = _safe_bridge_lookup

    core.SOLD_SEARCH_STAGES = _NEUTRAL_SOLD_STAGES
    recorded_sales.SOLD_SEARCH_STAGES = _NEUTRAL_SOLD_STAGES
    rent_reconciliation._search_mode = _neutral_search_mode

    for key in (
        "location_verification_failed",
        "location_verification_error",
        "location_verification_status",
        "requested_property_address",
        "resolved_property_address",
        "wide_area_search_used",
        "search_scope_note",
    ):
        core.INTELLIGENCE_STATE_KEYS.add(key)
        if key not in library.PERSISTED_STATE_KEYS:
            library.PERSISTED_STATE_KEYS.append(key)

    enrichment._property_location_safety_engine_installed = True
    return True


def install_ui() -> bool:
    if getattr(credit_guard, "_property_location_safety_ui_installed", False):
        return True
    credit_guard._location_safety_original_credit_panel = _ORIGINAL_CREDIT_PANEL
    credit_guard._location_safety_original_button_guard = _ORIGINAL_BUTTON_GUARD
    credit_guard.render_credit_panel = render_credit_panel_with_location_guard
    credit_guard._button_should_be_disabled = button_guard_with_location
    credit_guard._property_location_safety_ui_installed = True
    return True
