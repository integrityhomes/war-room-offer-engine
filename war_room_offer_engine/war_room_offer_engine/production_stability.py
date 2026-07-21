from __future__ import annotations

import sys
from typing import Any, Callable

try:
    import deal_decision_ui as decision_ui
    import deal_library as library
    import rentcast_intelligence_mode_lock as mode_lock
    import rentcast_intelligence_preview as preview
    import team_offer_identity as identity
except ImportError:
    try:
        from . import deal_decision_ui as decision_ui
        from . import deal_library as library
        from . import rentcast_intelligence_mode_lock as mode_lock
        from . import rentcast_intelligence_preview as preview
        from . import team_offer_identity as identity
    except ImportError:
        from war_room_offer_engine import deal_decision_ui as decision_ui
        from war_room_offer_engine import deal_library as library
        from war_room_offer_engine import rentcast_intelligence_mode_lock as mode_lock
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import team_offer_identity as identity


RELEASE_NAME = "Stability v1"
ANALYSIS_PROPERTY_KEY = "stability_analysis_property_key"
LAST_RUN_OK_KEY = "stability_last_run_ok"
LAST_RUN_MESSAGE_KEY = "stability_last_run_message"
STALE_ANALYSIS_KEY = "stability_analysis_is_stale"

_ORIGINAL_RENDER = getattr(
    decision_ui,
    "_production_stability_original_render",
    decision_ui.render,
)
_ORIGINAL_RUN = getattr(
    decision_ui,
    "_production_stability_original_run",
    decision_ui._run,
)
_ORIGINAL_RESET = getattr(
    decision_ui,
    "_production_stability_original_reset",
    decision_ui._reset,
)
_ORIGINAL_LIVE_DECISION = getattr(
    decision_ui,
    "_production_stability_original_live_decision",
    decision_ui._live_decision,
)


# Values inherited from the original prototype. They are useful in unit fixtures,
# but must never appear as real production property evidence before a pull.
_LEGACY_DEMO_VALUES = {
    "asking_price": 35000,
    "contract_price": 35000,
    "rent": 900,
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
}
_LEGACY_DEMO_ADDRESSES = {
    "123 main st",
    "123 main st decatur il 62522",
}

# Fields that identify the person using the browser and global workflow choices.
# They survive Start New Property and automatic new-address cleanup.
_SESSION_PREFERENCE_KEYS = {
    identity.ACTIVE_MEMBER_KEY,
    identity.MEMBER_SELECTION_KEY,
    identity.CUSTOM_MEMBER_KEY,
    "war_room_active_section",
    "deal_library_auto_save",
    "deal_library_search",
    "deal_library_search_results",
    preview.PREVIEW_STATE_KEY,
}

# Inputs already visible above the analysis button. They are preserved when a
# teammate types a different property and runs it without first clicking reset.
_CURRENT_INPUT_KEYS = {
    "decision_property_input",
    "decision_strategy",
    "decision_lead_source",
    "decision_asking_price",
    "decision_current_negotiated_price",
    "decision_latest_counter",
    "decision_seller_bottom_line",
    "decision_negotiation_status",
    "decision_negotiated_with",
    "decision_last_negotiation",
    "decision_next_follow_up",
    "decision_negotiation_notes",
    "decision_other_terms",
    "decision_media",
    "one_load_input_method",
    "one_load_property_address",
    "one_load_listing_url",
    "one_load_lead_type",
    "one_load_lead_source",
    "one_load_asking_price",
    "one_load_seller_desired_price",
    "one_load_contact_name",
    "one_load_contact_phone",
    "one_load_contact_email",
    "one_load_seller_notes",
    "one_load_repairs_mentioned",
    "one_load_motivation_notes",
    "one_load_timeline",
    "one_load_access_notes",
    "one_load_occupancy",
    "deal_library_force_refresh",
    "rentcast_credit_guard_refresh_confirmed",
}

_PROPERTY_PREFIXES = (
    "rentcast_",
    "rent_",
    "arv_",
    "auto_",
    "location_",
    "requested_property_",
    "resolved_property_",
    "one_load_",
    "decision_",
    "seller_",
    "listing_",
    "owner_",
    "apify_",
    "buyer_",
    "dispo_",
    "deal_library_",
    "deal_protection_",
    "contract_",
    "address_sharing_",
    "listing_source_sharing_",
)

_PROPERTY_EXACT_KEYS = {
    "address",
    "city",
    "state",
    "zip",
    "market",
    "county",
    "latitude",
    "longitude",
    "beds",
    "baths",
    "sqft",
    "lot_size",
    "year_built",
    "property_type",
    "taxes",
    "tax_assessed_value",
    "last_sale_date",
    "last_sale_price",
    "assessor_id",
    "subdivision",
    "zoning",
    "hoa_fee",
    "hoa_frequency",
    "status",
    "days_on_market",
    "occupancy",
    "livable",
    "lead_source",
    "lead_type",
    "source_mode",
    "asking_price",
    "contract_price",
    "rent",
    "rent_estimate",
    "arv",
    "sheet_arv",
    "repairs",
    "repair_analysis",
    "repair_notes",
    "manual_repair_notes",
    "recommended_repairs_from_analyzer",
    "repair_source",
    "notes",
    "last_source_results",
    "last_auto_pull",
    "field_source_map_json",
    identity.DEAL_OFFER_MAKER_KEY,
    "decision_offer_made_by",
    ANALYSIS_PROPERTY_KEY,
    LAST_RUN_OK_KEY,
    LAST_RUN_MESSAGE_KEY,
    STALE_ANALYSIS_KEY,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _normalized_data(state: Any) -> dict[str, Any]:
    if not hasattr(state, "get"):
        return {}
    normalized = state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    return data if isinstance(data, dict) else {}


def current_property_input(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    return _text(
        state.get("decision_property_input")
        or state.get("one_load_listing_url")
        or state.get("one_load_property_address")
    )


def loaded_property_identity(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    data = _normalized_data(state)
    direct = _text(
        state.get("requested_property_address")
        or data.get("requested_property_address")
        or state.get("resolved_property_address")
        or data.get("resolved_property_address")
        or state.get("listing_url")
        or data.get("listing_url")
    )
    if direct:
        return direct

    address = _text(data.get("formattedAddress") or data.get("formatted_address") or state.get("address") or data.get("address"))
    city = _text(state.get("city") or data.get("city"))
    region = _text(state.get("state") or data.get("state"))
    zipcode = _text(state.get("zip") or data.get("zip") or data.get("zipCode"))
    if address and (city or region or zipcode):
        locality = ", ".join(part for part in [city, region] if part)
        return " ".join(part for part in [f"{address}, {locality}" if locality else address, zipcode] if part)
    return address


def canonical_property(value: Any) -> str:
    return library.normalize_property_key(_text(value))


def _loaded_analysis_present(state: Any) -> bool:
    if not hasattr(state, "get"):
        return False
    return bool(
        state.get("one_load_normalized")
        or state.get("decision_result")
        or state.get("last_auto_pull")
        or state.get("deal_library_loaded_without_api")
    )


def ensure_analysis_property_key(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    existing = canonical_property(state.get(ANALYSIS_PROPERTY_KEY))
    if existing:
        state[ANALYSIS_PROPERTY_KEY] = existing
        return existing
    if not _loaded_analysis_present(state):
        return ""
    loaded = canonical_property(loaded_property_identity(state))
    if loaded:
        state[ANALYSIS_PROPERTY_KEY] = loaded
    return loaded


def analysis_matches_current_input(state: Any) -> bool:
    current = canonical_property(current_property_input(state))
    loaded = ensure_analysis_property_key(state)
    return bool(current and loaded and current == loaded)


def _has_positive_provenance(state: Any) -> bool:
    data = _normalized_data(state)
    return bool(
        state.get("deal_library_loaded_without_api")
        or state.get("last_auto_pull")
        or state.get("rentcast_submitted_address")
        or data.get("rentcast_submitted_address")
        or state.get("location_verification_status")
        or data.get("location_verification_status")
        or state.get("rentcast_rent_comps")
        or data.get("rent_comps")
        or state.get("auto_sold_comps")
        or data.get("auto_sold_comps")
        or _number(state.get("rentcast_rent_avm")) > 0
        or _number(data.get("rentcast_rent_avm")) > 0
        or _number(state.get("rentcast_arv")) > 0
        or _number(data.get("rentcast_arv")) > 0
    )


def sanitize_legacy_demo_defaults(state: Any) -> list[str]:
    """Remove prototype numbers before they can look like property evidence."""
    if not hasattr(state, "get") or _loaded_analysis_present(state) or _has_positive_provenance(state):
        return []

    cleared: list[str] = []
    address_key = canonical_property(state.get("address"))
    if address_key in _LEGACY_DEMO_ADDRESSES:
        state["address"] = ""
        cleared.append("address")

    for key, demo in _LEGACY_DEMO_VALUES.items():
        if _number(state.get(key)) != float(demo):
            continue
        if key == "rent":
            source = _text(state.get("rent_source")).lower()
            if source and "missing" not in source and "unavailable" not in source:
                continue
        state[key] = 0
        cleared.append(key)

    if "rent" in cleared:
        state["rent_source"] = "Missing / no verified data loaded"
        state["rent_confidence"] = "Missing"
        state["rent_verification_needed"] = "Yes"
    return cleared


def _is_property_state_key(key: Any) -> bool:
    text = str(key or "")
    return text in _PROPERTY_EXACT_KEYS or text.startswith(_PROPERTY_PREFIXES)


def clear_property_state(state: Any, *, preserve_current_inputs: bool) -> list[str]:
    """Clear one property's evidence without losing the current teammate."""
    if not hasattr(state, "get"):
        return []
    preserve = set(_SESSION_PREFERENCE_KEYS)
    if preserve_current_inputs:
        preserve.update(_CURRENT_INPUT_KEYS)
    saved = {key: state.get(key) for key in preserve if key in state}

    removed: list[str] = []
    for key in list(state.keys()):
        if key in preserve:
            continue
        if _is_property_state_key(key):
            state.pop(key, None)
            removed.append(str(key))

    for key, value in saved.items():
        state[key] = value
    state[preview.PREVIEW_STATE_KEY] = True
    state["deal_library_force_refresh"] = bool(saved.get("deal_library_force_refresh", False)) if preserve_current_inputs else False
    state[STALE_ANALYSIS_KEY] = False
    return removed


def _location_failed(state: Any) -> bool:
    data = _normalized_data(state)
    return bool(
        state.get("location_verification_failed")
        or data.get("location_verification_failed")
        or state.get("location_verification_error")
        or data.get("location_verification_error")
    )


def _usable_property_evidence(state: Any) -> bool:
    data = _normalized_data(state)
    rows = [
        state.get("rentcast_rent_comps"),
        data.get("rent_comps"),
        state.get("auto_sold_comps"),
        data.get("auto_sold_comps"),
        state.get("rentcast_sold_comps"),
        data.get("rentcast_sold_comps"),
    ]
    if any(isinstance(value, list) and value for value in rows):
        return True
    if any(
        _number(value) > 0
        for value in [
            state.get("rentcast_rent_avm"),
            data.get("rentcast_rent_avm"),
            state.get("rent"),
            data.get("rent"),
            state.get("rentcast_arv"),
            data.get("rentcast_arv"),
            state.get("arv"),
            data.get("arv"),
            state.get("taxes"),
            data.get("taxes"),
            state.get("beds"),
            data.get("beds"),
            state.get("sqft"),
            data.get("sqft"),
        ]
    ):
        return True
    return bool(
        state.get("location_verification_status")
        or data.get("location_verification_status")
        or data.get("property_type")
        or data.get("formattedAddress")
        or data.get("formatted_address")
    )


def record_run_status(state: Any) -> bool:
    current = canonical_property(current_property_input(state))
    ok = bool(current and not _location_failed(state) and _usable_property_evidence(state))
    state[LAST_RUN_OK_KEY] = ok
    if ok:
        state[ANALYSIS_PROPERTY_KEY] = current
        state[STALE_ANALYSIS_KEY] = False
        state[LAST_RUN_MESSAGE_KEY] = "Verified analysis complete. Review evidence confidence before sending an offer."
    else:
        error = _text(
            state.get("location_verification_error")
            or _normalized_data(state).get("location_verification_error")
            or state.get("rentcast_rent_error")
            or _normalized_data(state).get("rentcast_rent_error")
        )
        state[LAST_RUN_MESSAGE_KEY] = error or (
            "The analysis finished without usable verified property evidence. No clean BUY should be used."
        )
    return ok


def run_with_stability(st: Any, ui: Any, media_files: list[Any]) -> Any:
    state = st.session_state
    sanitize_legacy_demo_defaults(state)
    current = canonical_property(current_property_input(state))
    loaded = ensure_analysis_property_key(state)
    if current and loaded and current != loaded:
        clear_property_state(state, preserve_current_inputs=True)

    result = _ORIGINAL_RUN(st, ui, media_files)
    record_run_status(state)
    return result


def reset_with_stability(st: Any) -> None:
    preferences = {
        key: st.session_state.get(key)
        for key in _SESSION_PREFERENCE_KEYS
        if key in st.session_state
    }
    _ORIGINAL_RESET(st)
    clear_property_state(st.session_state, preserve_current_inputs=False)
    for key, value in preferences.items():
        st.session_state[key] = value
    st.session_state[preview.PREVIEW_STATE_KEY] = True


def live_decision_with_property_match(st: Any, ui: Any) -> dict[str, Any]:
    state = st.session_state
    if _loaded_analysis_present(state) and not analysis_matches_current_input(state):
        state[STALE_ANALYSIS_KEY] = True
        return {}
    state[STALE_ANALYSIS_KEY] = False
    return _ORIGINAL_LIVE_DECISION(st, ui)


def render_accuracy_first_control(st: Any) -> None:
    """Keep the normal team workflow on the most accurate engine."""
    state = st.session_state
    state[preview.PREVIEW_STATE_KEY] = True
    if mode_lock.result_uses_verified_intelligence(state):
        st.info(
            "Accuracy mode: verified RentCast intelligence is locked to this loaded analysis. "
            "Recorded sales and adaptive rental evidence will stay with the matching decision rules."
        )
    else:
        st.info(
            "Accuracy mode: verified RentCast intelligence is ON. The app starts local, expands only when needed, "
            "and keeps the displayed request hard cap."
        )


def render_with_stability(
    st: Any,
    ui: Any,
    original_renderer: Callable,
    exit_mode_value: str = "Auto",
) -> Any:
    sanitize_legacy_demo_defaults(st.session_state)
    ensure_analysis_property_key(st.session_state)
    st.session_state[preview.PREVIEW_STATE_KEY] = True

    original_checkbox = st.checkbox
    original_success = st.success

    def checkbox_with_simple_copy(label: Any, *args: Any, **kwargs: Any):
        if str(label or "") == "Refresh live paid data even if this property is already saved":
            label = "Advanced: force a fresh paid-data pull"
            kwargs["help"] = (
                "Leave this off for normal use. Turn it on only when the saved analysis is outdated and you intentionally "
                "want to repurchase current Zillow/RentCast/Apify data."
            )
        return original_checkbox(label, *args, **kwargs)

    def success_with_verified_status(body: Any, *args: Any, **kwargs: Any):
        if str(body or "").strip() == "Automatic analysis complete.":
            message = _text(st.session_state.get(LAST_RUN_MESSAGE_KEY))
            if st.session_state.get(LAST_RUN_OK_KEY):
                return original_success(message or "Verified analysis complete.", *args, **kwargs)
            return st.warning(message or "Analysis stopped without usable verified evidence.")
        return original_success(body, *args, **kwargs)

    st.checkbox = checkbox_with_simple_copy
    st.success = success_with_verified_status
    try:
        result = _ORIGINAL_RENDER(st, ui, original_renderer, exit_mode_value)
        if st.session_state.get(STALE_ANALYSIS_KEY):
            st.info(
                "The property input changed, so the prior property's decision is hidden. "
                "Run Pull Everything & Tell Me for the current property."
            )
        return result
    finally:
        st.checkbox = original_checkbox
        st.success = original_success


def _install_title_sanitizer() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False
    if getattr(st, "_production_stability_title_hook", False):
        return True
    original_title = st.title

    def title_with_stability(*args: Any, **kwargs: Any):
        sanitize_legacy_demo_defaults(st.session_state)
        st.session_state[preview.PREVIEW_STATE_KEY] = True
        return original_title(*args, **kwargs)

    st.title = title_with_stability
    st._production_stability_title_hook = True
    return True


def _patch_loaded_aliases() -> None:
    for module_name in (
        "deal_decision_ui",
        "war_room_offer_engine.deal_decision_ui",
        "war_room_offer_engine.war_room_offer_engine.deal_decision_ui",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.render = render_with_stability
            loaded._run = run_with_stability
            loaded._reset = reset_with_stability
            loaded._live_decision = live_decision_with_property_match


def install() -> bool:
    if getattr(decision_ui, "_production_stability_installed", False):
        _patch_loaded_aliases()
        _install_title_sanitizer()
        return True

    decision_ui._production_stability_original_render = _ORIGINAL_RENDER
    decision_ui._production_stability_original_run = _ORIGINAL_RUN
    decision_ui._production_stability_original_reset = _ORIGINAL_RESET
    decision_ui._production_stability_original_live_decision = _ORIGINAL_LIVE_DECISION
    decision_ui.render = render_with_stability
    decision_ui._run = run_with_stability
    decision_ui._reset = reset_with_stability
    decision_ui._live_decision = live_decision_with_property_match

    # The preview header hook resolves this module global at runtime, so replacing
    # the function removes a confusing mode checkbox without rewriting the UI.
    preview.render_preview_control = render_accuracy_first_control

    _patch_loaded_aliases()
    _install_title_sanitizer()
    decision_ui._production_stability_installed = True
    return True


install()
