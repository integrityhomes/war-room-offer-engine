from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from typing import Any, Callable

try:
    import deal_decision_ui as decision_ui
    import deal_library as library
    import deal_library_ui as library_ui
    import property_location_guard as location_guard
    import rentcast_intelligence_mode_lock as mode_lock
    import rentcast_intelligence_preview as preview
    import team_offer_identity as identity
    from ui_sections import one_load_deal_ui as one_load_ui
except ImportError:
    try:
        from . import deal_decision_ui as decision_ui
        from . import deal_library as library
        from . import deal_library_ui as library_ui
        from . import property_location_guard as location_guard
        from . import rentcast_intelligence_mode_lock as mode_lock
        from . import rentcast_intelligence_preview as preview
        from . import team_offer_identity as identity
        from .ui_sections import one_load_deal_ui as one_load_ui
    except ImportError:
        from war_room_offer_engine import deal_decision_ui as decision_ui
        from war_room_offer_engine import deal_library as library
        from war_room_offer_engine import deal_library_ui as library_ui
        from war_room_offer_engine import property_location_guard as location_guard
        from war_room_offer_engine import rentcast_intelligence_mode_lock as mode_lock
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import team_offer_identity as identity
        from war_room_offer_engine.ui_sections import one_load_deal_ui as one_load_ui


STABILITY_VERSION = "Stability Release 1"
ANALYSIS_PROPERTY_KEY = "stable_analysis_property_key"
CURRENT_INPUT_KEY = "stable_current_property_key"
ANALYSIS_RUN_ID_KEY = "stable_analysis_run_id"
ANALYSIS_STATUS_KEY = "stable_analysis_status"
ANALYSIS_COMPLETED_AT_KEY = "stable_analysis_completed_at"
ANALYSIS_ERRORS_KEY = "stable_analysis_errors"
ANALYSIS_WARNINGS_KEY = "stable_analysis_warnings"
RESET_PENDING_KEY = "stable_new_property_reset_pending"
NOTICE_KEY = "stable_operator_notice"

STATUS_COMPLETE = "Complete"
STATUS_PARTIAL = "Partial — verify missing evidence"
STATUS_BLOCKED = "Blocked — location or identity failed"
STATUS_FAILED = "Failed — no usable property evidence"


_ORIGINAL_DECISION_RENDER = getattr(
    decision_ui,
    "_stability_original_render",
    decision_ui.render,
)
_ORIGINAL_LIBRARY_RENDER = getattr(
    library_ui,
    "_stability_original_render_deal_library_box",
    library_ui.render_deal_library_box,
)
_ORIGINAL_PREVIEW_CONTROL = getattr(
    preview,
    "_stability_original_preview_control",
    preview.render_preview_control,
)


_GLOBAL_SETTING_KEYS = {
    identity.ACTIVE_MEMBER_KEY,
    identity.MEMBER_SELECTION_KEY,
    identity.CUSTOM_MEMBER_KEY,
    preview.PREVIEW_STATE_KEY,
    "war_room_active_section",
    "deal_library_auto_save",
    "repair_market",
    "repair_level",
    "repair_pricing_mode",
    "repair_contingency",
    "repair_cushion_percent",
    "market_labor_cost",
    "show_full_repair_math",
    "manual_wholesale_override",
    "wholesale_buyer_percent_arv",
    "slow_flip_rent_multiple",
    "slow_flip_max_offer_cap",
    "slow_flip_first_offer_gap",
    "min_assignment_fee",
    "exception_assignment_fee",
    "close_title_buffer",
    "target_offer_discount",
    "deal_protection_mode",
}

_EXTRA_PROPERTY_KEYS = {
    ANALYSIS_PROPERTY_KEY,
    ANALYSIS_RUN_ID_KEY,
    ANALYSIS_STATUS_KEY,
    ANALYSIS_COMPLETED_AT_KEY,
    ANALYSIS_ERRORS_KEY,
    ANALYSIS_WARNINGS_KEY,
    "decision_offer_made_by",
    identity.DEAL_OFFER_MAKER_KEY,
    "rentcast_credit_guard_last_run_stats",
    "rentcast_credit_guard_last_property",
    "rentcast_credit_guard_last_pull_epoch",
    "rentcast_credit_guard_confirm_refresh",
    "rentcast_credit_guard_confirmation_property",
    "rentcast_credit_guard_estimated_min",
    "rentcast_credit_guard_estimated_max",
    "rentcast_credit_guard_limit",
    "property_input_location_valid",
    "property_input_location_error",
    "deal_library_pending_snapshot",
    "deal_library_query_loaded_id",
    "rentcast_pull_attempted",
    "rentcast_pull_status",
}

_PROPERTY_PREFIXES = (
    "rentcast_",
    "rent_",
    "auto_",
    "arv",
    "one_load_",
    "decision_",
    "deal_library_",
    "location_",
    "requested_property_",
    "resolved_property_",
    "manual_rent_comp_",
    "manual_comp_",
    "repair_",
    "seller_",
    "listing_",
    "buyer_",
    "dispo_",
    "field_source_",
    "apify_",
)

_DEMO_DEFAULTS = {
    "asking_price": 35000,
    "contract_price": 35000,
    "rent": 900,
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def property_key(value: Any) -> str:
    return library.normalize_property_key(_text(value))


def _normalized_data(state: Any) -> dict[str, Any]:
    if not hasattr(state, "get"):
        return {}
    normalized = state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    return data if isinstance(data, dict) else {}


def _state_value(state: Any, key: str, default: Any = None) -> Any:
    if hasattr(state, "get") and key in state:
        return state.get(key)
    return _normalized_data(state).get(key, default)


def _analysis_evidence_present(state: Any) -> bool:
    if not hasattr(state, "get"):
        return False
    return bool(
        state.get("one_load_normalized")
        or state.get("decision_result")
        or state.get(ANALYSIS_RUN_ID_KEY)
        or state.get("rentcast_rent_comps")
        or state.get("auto_sold_comps")
        or _number(state.get("rent")) > 0
        or _number(state.get("arv")) > 0
    )


def _property_reset_keys() -> set[str]:
    keys = set(getattr(decision_ui, "RESET_KEYS", []) or [])
    keys.update(getattr(preview, "_PREVIEW_RESET_KEYS", set()) or set())
    keys.update(getattr(library, "PERSISTED_STATE_KEYS", []) or [])
    keys.update(_EXTRA_PROPERTY_KEYS)
    keys.update(
        {
            "address",
            "city",
            "state",
            "zip",
            "market",
            "county",
            "latitude",
            "longitude",
            "asking_price",
            "contract_price",
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
            "occupancy",
            "livable",
            "notes",
            "status",
            "days_on_market",
            "source_mode",
            "lead_source",
            "lead_type",
            "listing_url",
            "owner_name",
        }
    )
    return keys


def _should_clear_key(key: str, reset_keys: set[str]) -> bool:
    if key in _GLOBAL_SETTING_KEYS or key == CURRENT_INPUT_KEY:
        return False
    return key in reset_keys or key.startswith(_PROPERTY_PREFIXES)


def _clear_query_deal(st: Any) -> None:
    try:
        if "deal_id" in st.query_params:
            del st.query_params["deal_id"]
    except Exception:
        pass


def clear_property_state(
    state: Any,
    *,
    input_value: str = "",
    preserve_strategy: bool = True,
    notice: str = "",
) -> None:
    """Clear every property-scoped result while keeping the current teammate.

    The app historically accumulated multiple aliases for rent, ARV, comps, saved
    deals, and paid-request state. Clearing only the visible fields allowed a new
    property to inherit evidence from the previous one. This reset is intentionally
    broad and preserves only operator identity and true global assumptions.
    """
    if not hasattr(state, "get"):
        return

    reset_keys = _property_reset_keys()
    strategy = state.get("decision_strategy", decision_ui.AUTO) if preserve_strategy else decision_ui.AUTO
    source = state.get("decision_lead_source", "Zillow / On-Market") if preserve_strategy else "Zillow / On-Market"
    preserved = {key: state.get(key) for key in _GLOBAL_SETTING_KEYS if key in state}

    for key in list(state.keys()):
        if _should_clear_key(str(key), reset_keys):
            state.pop(key, None)

    for key, value in preserved.items():
        state[key] = value

    state["decision_property_input"] = _text(input_value)
    state["decision_strategy"] = strategy
    state["decision_lead_source"] = source
    state["decision_asking_price"] = 0
    state["decision_current_negotiated_price"] = 0
    state["decision_latest_counter"] = 0
    state["decision_seller_bottom_line"] = 0
    state["decision_negotiation_status"] = "Not contacted"
    state["decision_negotiated_with"] = ""
    state["decision_last_negotiation"] = ""
    state["decision_next_follow_up"] = ""
    state["decision_negotiation_notes"] = ""
    state["decision_other_terms"] = ""
    state["deal_library_force_refresh"] = False
    state[CURRENT_INPUT_KEY] = property_key(input_value)
    state.pop(identity.DEAL_OFFER_MAKER_KEY, None)
    state.pop("decision_offer_made_by", None)
    if notice:
        state[NOTICE_KEY] = notice


def clean_demo_defaults(state: Any) -> None:
    """Remove historical demo numbers before any property widget is rendered."""
    if not hasattr(state, "get"):
        return
    current_property = _text(
        state.get("decision_property_input")
        or state.get("one_load_property_address")
        or state.get("address")
    )
    if current_property or _analysis_evidence_present(state) or state.get("deal_library_loaded_without_api"):
        return

    for key, demo in _DEMO_DEFAULTS.items():
        if str(state.get(key, "")).strip() == str(demo):
            state[key] = 0
    state.setdefault("asking_price", 0)
    state.setdefault("contract_price", 0)
    state.setdefault("rent", 0)
    state.setdefault("beds", 0.0)
    state.setdefault("baths", 0.0)
    state.setdefault("sqft", 0)
    if _text(state.get("rent_source")).lower() in {"", "missing / rentcast unavailable"}:
        state["rent_source"] = "Missing / not analyzed"
    if _text(state.get("rent_confidence")).lower() in {"", "weak"}:
        state["rent_confidence"] = "Missing"
    state["rent_verification_needed"] = "Yes"


def property_input_changed(st: Any) -> None:
    state = st.session_state
    new_value = _text(state.get("decision_property_input"))
    new_key = property_key(new_value)
    old_key = _text(state.get(CURRENT_INPUT_KEY))
    if old_key and new_key != old_key:
        clear_property_state(
            state,
            input_value=new_value,
            preserve_strategy=True,
            notice="Property changed. All prior rent, ARV, comps, repairs, decision, and request state were cleared.",
        )
    state[CURRENT_INPUT_KEY] = new_key


def _bind_restored_or_legacy_analysis(state: Any) -> None:
    current_input = _text(state.get("decision_property_input"))
    current_key = property_key(current_input)
    if state.get("deal_library_loaded_without_api"):
        state[CURRENT_INPUT_KEY] = current_key
    if state.get(ANALYSIS_PROPERTY_KEY) or not _analysis_evidence_present(state):
        return
    data = _normalized_data(state)
    evidence_address = _text(
        data.get("resolved_property_address")
        or data.get("requested_property_address")
        or data.get("formatted_address")
        or data.get("address")
        or state.get("resolved_property_address")
        or state.get("requested_property_address")
        or state.get("address")
    )
    key = property_key(evidence_address)
    if key:
        state[ANALYSIS_PROPERTY_KEY] = key
        state.setdefault(ANALYSIS_STATUS_KEY, "Saved / legacy analysis")


def analysis_matches_input(state: Any) -> bool:
    if not hasattr(state, "get"):
        return False
    _bind_restored_or_legacy_analysis(state)
    current = property_key(state.get("decision_property_input"))
    analyzed = property_key(state.get(ANALYSIS_PROPERTY_KEY))
    return bool(current and analyzed and current == analyzed)


def _collect_messages(*values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        rows = value if isinstance(value, (list, tuple, set)) else [value]
        for row in rows:
            text = _text(row)
            if text and text not in result:
                result.append(text)
    return result


def _verified_rent_count(state: Any) -> int:
    data = _normalized_data(state)
    quality = _state_value(state, "rent_comp_quality_summary", {}) or {}
    direct = int(_number(_state_value(state, "verified_rent_comp_count", 0)))
    if direct > 0:
        return direct
    if isinstance(quality, dict):
        return int(_number(quality.get("strong"))) + int(_number(quality.get("good")))
    rows = _rows(_state_value(state, "rent_comps", []))
    return sum(
        bool(row.get("include_default")) and row.get("score") in {"Strong Comp", "Good Comp"}
        for row in rows
    )


def _total_rent_count(state: Any) -> int:
    return max(
        int(_number(_state_value(state, "rentcast_total_listing_count", 0))),
        int(_number(_state_value(state, "rent_comp_count", 0))),
        len(_rows(_state_value(state, "rent_comps", []))),
    )


def _verified_sale_count(state: Any) -> int:
    direct = int(_number(_state_value(state, "verified_sold_comp_count", 0)))
    if direct > 0:
        return direct
    summary = _state_value(state, "auto_arv_summary", {}) or {}
    if isinstance(summary, dict):
        direct = int(_number(summary.get("verified_sold_comp_count")))
        if direct > 0:
            return direct
    rows = _rows(_state_value(state, "auto_sold_comps", []))
    return sum(
        bool(row.get("include_default"))
        and row.get("score") in {"Strong Comp", "Good Comp"}
        and (
            row.get("record_type") == "recorded_sale"
            or _text(row.get("source")).startswith("RentCast Recorded Sale")
        )
        for row in rows
    )


def classify_analysis(state: Any, normalized: dict[str, Any] | None = None) -> tuple[str, list[str], list[str]]:
    normalized = normalized if isinstance(normalized, dict) else state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    data = data if isinstance(data, dict) else {}

    errors = _collect_messages(
        normalized.get("errors", []) if isinstance(normalized, dict) else [],
        data.get("location_verification_error"),
        state.get("location_verification_error"),
        data.get("rentcast_property_error"),
        data.get("rentcast_rent_error"),
        data.get("rentcast_value_error"),
    )
    warnings = _collect_messages(
        normalized.get("warnings", []) if isinstance(normalized, dict) else [],
        data.get("rent_verification_reasons", []),
        data.get("arv_verification_reasons", []),
        state.get("rent_verification_reasons", []),
        state.get("arv_verification_reasons", []),
    )

    location_failed = bool(
        data.get("location_verification_failed")
        or state.get("location_verification_failed")
    )
    address = _text(
        data.get("resolved_property_address")
        or data.get("formatted_address")
        or data.get("address")
        or state.get("resolved_property_address")
        or state.get("address")
        or state.get("decision_property_input")
    )
    rent = _number(data.get("rent") or data.get("rent_estimate") or state.get("rent"))
    arv = _number(data.get("arv") or data.get("auto_recommended_arv") or state.get("arv"))
    facts = any(
        _number(data.get(key) or state.get(key)) > 0
        for key in ("beds", "baths", "sqft", "taxes", "year_built")
    )
    evidence = bool(
        rent > 0
        or arv > 0
        or _verified_rent_count(state) > 0
        or _verified_sale_count(state) > 0
        or facts
    )

    if location_failed:
        return STATUS_BLOCKED, errors, warnings
    if not address or not evidence:
        return STATUS_FAILED, errors, warnings
    if errors or (rent <= 0 and arv <= 0):
        return STATUS_PARTIAL, errors, warnings
    return STATUS_COMPLETE, errors, warnings


def stamp_analysis(state: Any, normalized: dict[str, Any]) -> str:
    current = _text(state.get("decision_property_input"))
    key = property_key(current)
    now = datetime.now(timezone.utc)
    digest = hashlib.sha1(f"{key}|{now.isoformat()}".encode("utf-8")).hexdigest()[:8]
    run_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{digest}"
    status, errors, warnings = classify_analysis(state, normalized)

    state[ANALYSIS_PROPERTY_KEY] = key
    state[CURRENT_INPUT_KEY] = key
    state[ANALYSIS_RUN_ID_KEY] = run_id
    state[ANALYSIS_STATUS_KEY] = status
    state[ANALYSIS_COMPLETED_AT_KEY] = now.isoformat()
    state[ANALYSIS_ERRORS_KEY] = errors
    state[ANALYSIS_WARNINGS_KEY] = warnings

    if isinstance(normalized, dict):
        normalized["analysis_run_id"] = run_id
        normalized["analysis_status"] = status
        data = normalized.get("data")
        if isinstance(data, dict):
            data[ANALYSIS_PROPERTY_KEY] = key
            data[ANALYSIS_RUN_ID_KEY] = run_id
            data[ANALYSIS_STATUS_KEY] = status
    return status


def _run_stable(st: Any, ui: Any, media_files: list[Any]) -> dict[str, Any]:
    try:
        from ui_sections import one_load_deal_ui as one_load
    except ImportError:
        try:
            from .ui_sections import one_load_deal_ui as one_load
        except ImportError:
            from war_room_offer_engine.ui_sections import one_load_deal_ui as one_load

    chosen_exit = decision_ui._prepare_input(st)
    with st.expander("Live source activity and error details", expanded=False):
        normalized = one_load._run_one_load(st, ui, None, chosen_exit, True)
    normalized = normalized if isinstance(normalized, dict) else {}

    price = (
        decision_ui.number(st.session_state.get("decision_current_negotiated_price"))
        or decision_ui.number(st.session_state.get("decision_latest_counter"))
        or decision_ui.number(st.session_state.get("decision_seller_bottom_line"))
        or decision_ui.number(st.session_state.get("decision_asking_price"))
        or decision_ui.number(st.session_state.get("asking_price"))
    )
    if price > 0:
        st.session_state["contract_price"] = int(price)

    decision_ui._analyze_media(st, ui, media_files or [])
    assumptions = one_load._build_assumptions(st, ui)
    wholesale_deal = one_load._build_deal(st, ui, "Wholesale Only")
    engine_result = ui.analyze_deal(wholesale_deal, assumptions)
    decision = decision_ui.build_decision(
        dict(st.session_state),
        assumptions,
        engine_result,
        st.session_state.get("decision_strategy", decision_ui.AUTO),
    )

    st.session_state["one_load_normalized"] = normalized
    st.session_state["decision_result"] = decision
    st.session_state["decision_engine_result"] = engine_result
    st.session_state["decision_last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state["deal_library_loaded_without_api"] = False
    status = stamp_analysis(st.session_state, normalized)

    if status not in {STATUS_BLOCKED, STATUS_FAILED}:
        library_ui.auto_save_completed_analysis(st)
    else:
        st.session_state["deal_library_last_message"] = ""
        st.session_state["deal_library_last_error"] = (
            "The analysis was not auto-saved because no trustworthy property result was produced."
        )
    return normalized


def _live_decision_stable(st: Any, ui: Any) -> dict[str, Any]:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    if not normalized or not analysis_matches_input(st.session_state):
        return {}
    try:
        from ui_sections import one_load_deal_ui as one_load
    except ImportError:
        try:
            from .ui_sections import one_load_deal_ui as one_load
        except ImportError:
            from war_room_offer_engine.ui_sections import one_load_deal_ui as one_load
    assumptions = one_load._build_assumptions(st, ui)
    engine = st.session_state.get("decision_engine_result", {}) or {}
    decision = decision_ui.build_decision(
        dict(st.session_state),
        assumptions,
        engine,
        st.session_state.get("decision_strategy", decision_ui.AUTO),
    )
    st.session_state["decision_result"] = decision
    return decision


def _quality_snapshot(state: Any, decision: dict[str, Any] | None = None) -> dict[str, Any]:
    decision = decision if isinstance(decision, dict) else state.get("decision_result", {}) or {}
    data = _normalized_data(state)
    stats = state.get("rentcast_credit_guard_last_run_stats", {}) or {}
    stats = stats if isinstance(stats, dict) else {}
    status = _text(state.get(ANALYSIS_STATUS_KEY)) or "Not analyzed"
    matched = analysis_matches_input(state)
    location_failed = bool(data.get("location_verification_failed") or state.get("location_verification_failed"))
    location_status = (
        "Mismatch / blocked"
        if location_failed
        else "Matched"
        if matched and _text(data.get("location_verification_status") or state.get("location_verification_status"))
        else "Bound to input"
        if matched
        else "Not verified"
    )

    verified_rent = _verified_rent_count(state)
    rent_total = _total_rent_count(state)
    rent_confidence = _text(_state_value(state, "rent_confidence", "Missing")) or "Missing"
    rent = _number(_state_value(state, "rent", 0))

    verified_sales = _verified_sale_count(state)
    arv_confidence = _text(_state_value(state, "arv_confidence", "Not enough data")) or "Not enough data"
    arv = _number(_state_value(state, "arv", 0))

    condition = _text(
        _state_value(state, "condition_evidence", "")
        or state.get("repair_scope_confidence")
        or "Unverified"
    )
    successful = int(_number(stats.get("successful_requests")))
    hits = int(_number(stats.get("cache_hits")))
    blocked = int(_number(stats.get("blocked_requests")))

    decision_name = _text(decision.get("decision"))
    missing = list(decision.get("missing", []) or [])
    flags = list(decision.get("review_flags", []) or [])
    if not matched or status in {STATUS_BLOCKED, STATUS_FAILED}:
        readiness = "Not ready"
    elif decision_name == "BUY" and not missing and not flags:
        readiness = "Offer ready"
    elif decision_name == "BUY":
        readiness = "Conditional offer"
    elif decision_name == "DO NOT BUY":
        readiness = "Pass / renegotiate"
    else:
        readiness = "Human review"

    return {
        "status": status,
        "matched": matched,
        "location_status": location_status,
        "rent": rent,
        "verified_rent": verified_rent,
        "rent_total": rent_total,
        "rent_confidence": rent_confidence,
        "arv": arv,
        "verified_sales": verified_sales,
        "arv_confidence": arv_confidence,
        "condition": condition,
        "successful_requests": successful,
        "cache_hits": hits,
        "blocked_requests": blocked,
        "readiness": readiness,
        "run_id": _text(state.get(ANALYSIS_RUN_ID_KEY)),
        "completed_at": _text(state.get(ANALYSIS_COMPLETED_AT_KEY)),
        "errors": list(state.get(ANALYSIS_ERRORS_KEY, []) or []),
        "warnings": list(state.get(ANALYSIS_WARNINGS_KEY, []) or []),
    }


def render_data_quality(st: Any, decision: dict[str, Any] | None = None) -> None:
    if not _analysis_evidence_present(st.session_state):
        return
    quality = _quality_snapshot(st.session_state, decision)
    st.markdown("### Data Quality & Offer Readiness")
    with st.container(border=True):
        row = st.columns(6)
        row[0].metric("Analysis", quality["status"])
        row[1].metric("Subject", quality["location_status"])
        row[2].metric(
            "Rent Evidence",
            f"${quality['rent']:,.0f}" if quality["rent"] > 0 else "Missing",
            f"{quality['verified_rent']} verified / {quality['rent_total']} total • {quality['rent_confidence']}",
        )
        row[3].metric(
            "Sale Evidence",
            f"${quality['arv']:,.0f}" if quality["arv"] > 0 else "Missing",
            f"{quality['verified_sales']} verified • {quality['arv_confidence']}",
        )
        row[4].metric("Condition", quality["condition"])
        row[5].metric("Offer Readiness", quality["readiness"])

        request_text = (
            f"RentCast usage: {quality['successful_requests']} new request(s), "
            f"{quality['cache_hits']} cache hit(s)"
        )
        if quality["blocked_requests"]:
            request_text += f", {quality['blocked_requests']} blocked by budget"
        st.caption(request_text + ".")
        if quality["run_id"]:
            st.caption(
                f"Analysis ID: {quality['run_id']}"
                + (f" | Completed: {quality['completed_at']}" if quality["completed_at"] else "")
                + f" | App: {STABILITY_VERSION}"
            )

        if not quality["matched"]:
            st.error(
                "The loaded evidence does not match the current property input. No decision or comp result should be used."
            )
        messages = _collect_messages(quality["errors"], quality["warnings"])
        if messages:
            with st.expander("Data warnings and provider errors", expanded=False):
                for message in messages:
                    st.warning(message)


def render_compact_verified_control(st: Any) -> None:
    state = st.session_state
    loaded_verified = mode_lock.result_uses_verified_intelligence(state)
    if preview.PREVIEW_STATE_KEY not in state:
        state[preview.PREVIEW_STATE_KEY] = True
    if loaded_verified:
        state[preview.PREVIEW_STATE_KEY] = True
        state[preview.PREVIEW_ACTIVE_KEY] = True
        state[mode_lock.MODE_KEY] = mode_lock.MODE_VERIFIED

    enabled = preview._as_bool(state.get(preview.PREVIEW_STATE_KEY, True))
    status = "Verified intelligence" if enabled else "Basic data mode"
    st.caption(
        f"Data mode: **{status}**"
        + (" — locked to the loaded verified evidence." if loaded_verified else " — verified mode is recommended for accuracy.")
    )
    if not loaded_verified:
        with st.expander("Data accuracy mode", expanded=False):
            st.checkbox(
                "Use verified RentCast intelligence (recommended)",
                key=preview.PREVIEW_STATE_KEY,
                on_change=mode_lock._clear_and_change_mode,
                args=(st,),
                help=(
                    "Verified mode uses recorded public sales and adaptive rental evidence. "
                    "Basic mode uses fewer requests but is less reliable for final underwriting."
                ),
            )
            if preview._as_bool(state.get(preview.PREVIEW_STATE_KEY, True)):
                st.info("Verified mode is ON. The request budget and hard cap remain visible above the property form.")
            else:
                st.warning("Basic mode is ON. Treat its value evidence as preliminary screening only.")
    if state.pop("rentcast_preview_mode_changed", False):
        st.caption("Prior calculated evidence was cleared so the two data modes cannot mix.")


def render_compact_library(st: Any) -> None:
    version = int(st.session_state.get("deal_library_version", 0) or 0)
    saved_at = _text(st.session_state.get("deal_library_last_saved_at"))
    label = "Team Deal Library — save, assign, notes, and reopen"
    if version:
        st.caption(f"Team Deal Library: saved version {version}" + (f" at {saved_at}" if saved_at else ""))

    with st.expander(label, expanded=False):
        original_markdown = st.markdown
        original_caption = st.caption

        def markdown_without_duplicate_heading(body: Any, *args: Any, **kwargs: Any):
            if _text(body) == "## 💾 Team Deal Library":
                return None
            return original_markdown(body, *args, **kwargs)

        def caption_without_duplicate_intro(body: Any, *args: Any, **kwargs: Any):
            text = _text(body)
            if text.startswith("Save the complete deal once"):
                return None
            return original_caption(body, *args, **kwargs)

        st.markdown = markdown_without_duplicate_heading
        st.caption = caption_without_duplicate_intro
        try:
            return _ORIGINAL_LIBRARY_RENDER(st)
        finally:
            st.markdown = original_markdown
            st.caption = original_caption


def render_stable_operator_workflow(
    st: Any,
    ui: Any,
    original_renderer: Callable,
    exit_mode_value: str = "Auto",
) -> None:
    library_ui.initialize_deal_library_state(st)

    if st.session_state.pop(RESET_PENDING_KEY, False):
        clear_property_state(
            st.session_state,
            input_value="",
            preserve_strategy=False,
            notice="New property started. Prior property evidence and deal-specific offer attribution were cleared.",
        )
        _clear_query_deal(st)

    library_ui.apply_pending_restore(st)
    library_ui.load_query_deal_if_requested(st)
    clean_demo_defaults(st.session_state)
    decision_ui.initialize(st)
    _bind_restored_or_legacy_analysis(st.session_state)

    if st.session_state.pop("deal_library_force_refresh_reset_pending", False):
        st.session_state["deal_library_force_refresh"] = False
    st.session_state.setdefault("deal_library_force_refresh", False)
    decision_ui._install_log_fields(st, ui)

    st.header("Deal Decision Center")
    st.caption(
        "Simple workflow: select the teammate, enter one complete property, set the price, run once, then review the evidence. "
        f"{STABILITY_VERSION}."
    )
    if st.session_state.get("deal_library_loaded_without_api"):
        st.success("Saved deal loaded from the Team Deal Library. No paid property-data credits were used.")
    notice = _text(st.session_state.pop(NOTICE_KEY, ""))
    if notice:
        st.info(notice)

    st.text_input(
        "Property address or listing link",
        key="decision_property_input",
        placeholder="404 4th St, Montgomery, AL 36110 or a listing link",
        on_change=property_input_changed,
        args=(st,),
        help="Use the complete street, city, state, and ZIP for plain-address pulls.",
    )
    st.session_state.setdefault(
        CURRENT_INPUT_KEY,
        property_key(st.session_state.get("decision_property_input")),
    )

    core = st.columns([1.25, 1, 1])
    with core[0]:
        st.selectbox("Deal Lane", decision_ui.STRATEGIES, key="decision_strategy")
    with core[1]:
        st.number_input("Seller Asking Price", min_value=0, step=1000, key="decision_asking_price")
    with core[2]:
        st.number_input(
            "Current Negotiated Price",
            min_value=0,
            step=500,
            key="decision_current_negotiated_price",
            help="Enter only a price actually negotiated with the seller or agent.",
        )

    with st.expander("More deal details — optional", expanded=False):
        details = st.columns(3)
        with details[0]:
            st.selectbox("Lead Source", decision_ui.SOURCE_OPTIONS, key="decision_lead_source")
        with details[1]:
            st.number_input("Latest Seller Counter", min_value=0, step=500, key="decision_latest_counter")
        with details[2]:
            st.number_input("Seller Bottom-Line Price", min_value=0, step=500, key="decision_seller_bottom_line")

        n1, n2 = st.columns(2)
        with n1:
            st.selectbox("Negotiation Status", decision_ui.NEGOTIATION_STATUSES, key="decision_negotiation_status")
            st.text_input("Negotiated With", key="decision_negotiated_with", placeholder="Agent or seller name")
            st.text_input("Last Negotiation", key="decision_last_negotiation", placeholder="Date/time or short note")
        with n2:
            st.text_input("Next Follow-Up", key="decision_next_follow_up", placeholder="Date/time or next step")
            st.text_area("Negotiation Notes", height=80, key="decision_negotiation_notes")
            st.text_area("Other Important Terms", height=80, key="decision_other_terms")

        media = st.file_uploader(
            "Optional property photos or walkthrough video",
            type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"],
            accept_multiple_files=True,
            key="decision_media",
        )

    with st.expander("Paid data refresh and cost controls", expanded=False):
        st.checkbox(
            "Refresh live paid data even if this property is already saved",
            key="deal_library_force_refresh",
            help=(
                "Leave this off for normal use. Turn it on only when you intentionally need fresh Zillow, "
                "RentCast, or Apify data. The request confirmation appears above the form."
            ),
        )
        st.caption(
            "Changing the negotiated price or deal lane does not require another property-data pull. "
            "Saved deals and fresh cache hits should be reused first."
        )

    buttons = st.columns([3, 1])
    analyze = buttons[0].button("Pull Everything & Tell Me", type="primary", use_container_width=True)
    reset = buttons[1].button("Start New Property", type="secondary", use_container_width=True)

    if reset:
        st.session_state[RESET_PENDING_KEY] = True
        st.rerun()

    if analyze:
        if not _text(st.session_state.get("decision_property_input")):
            st.error("Enter a complete property address or listing link first.")
        else:
            if not st.session_state.get("deal_library_force_refresh", False):
                decision_ui.open_saved_before_paid_pull(st)
            with st.spinner(
                "Verifying the subject property, rent evidence, recorded sales, condition inputs, and offer numbers..."
            ):
                _run_stable(st, ui, media or [])
            st.session_state["deal_library_force_refresh_reset_pending"] = True
            status = _text(st.session_state.get(ANALYSIS_STATUS_KEY))
            if status == STATUS_COMPLETE:
                st.success("Analysis completed and was bound to this exact property.")
            elif status == STATUS_PARTIAL:
                st.warning("Analysis completed with missing or weak evidence. Review Data Quality before making an offer.")
            elif status == STATUS_BLOCKED:
                st.error("Analysis was blocked because the property identity or location could not be trusted.")
            else:
                st.error("No usable property evidence was returned. Do not use an offer from this run.")

    decision = _live_decision_stable(st, ui)
    decision_ui._render_decision(st, decision)
    render_data_quality(st, decision)
    library_ui.render_deal_library_box(st)

    with st.expander("Advanced engine controls and full audit details", expanded=False):
        st.caption(
            "Use these controls only for documented overrides, manual comp work, repairs, or audit review. "
            "The normal team workflow should remain in the simple screen above."
        )
        original_renderer(st, ui, exit_mode_value)


def render_compact_credit_panel(st: Any) -> None:
    """A smaller location-aware request panel installed after the credit guard."""
    try:
        import rentcast_credit_guard as credit_guard
    except ImportError:
        try:
            from . import rentcast_credit_guard as credit_guard
        except ImportError:
            from war_room_offer_engine import rentcast_credit_guard as credit_guard

    state = st.session_state
    credit_guard._reset_confirmation_for_property(st)
    preview_on = preview.preview_enabled(st)
    minimum, maximum = credit_guard.estimate_request_range(state, preview_on=preview_on)
    limit = credit_guard._configured_limit(maximum)
    state["rentcast_credit_guard_estimated_min"] = minimum
    state["rentcast_credit_guard_estimated_max"] = maximum
    state["rentcast_credit_guard_limit"] = limit

    mode = "Verified" if preview_on else "Basic"
    last = state.get(credit_guard.LAST_STATS_KEY, {}) or {}
    last = last if isinstance(last, dict) else {}
    actual = int(_number(last.get("successful_requests")))
    hits = int(_number(last.get("cache_hits")))
    blocked = int(_number(last.get("blocked_requests")))

    with st.container(border=True):
        cols = st.columns(4)
        cols[0].metric("Data Mode", mode)
        cols[1].metric("Fresh Pull Budget", f"{minimum}–{maximum}", f"hard cap {limit}")
        cols[2].metric("Last New Requests", actual)
        cols[3].metric("Last Cache Hits", hits)

        value = _text(
            state.get("decision_property_input")
            or state.get("one_load_property_address")
            or state.get("one_load_listing_url")
        )
        if value:
            complete, message = location_guard.validate_property_input(value)
            state["property_input_location_valid"] = complete
            state["property_input_location_error"] = message
            if not complete:
                st.warning(message + " The paid pull is disabled until the location is complete.")
        else:
            state["property_input_location_valid"] = False
            state["property_input_location_error"] = "Enter a property address or listing URL."

        if blocked:
            st.warning(f"The last analysis blocked {blocked} request(s) before they could exceed the budget.")
        if credit_guard.duplicate_analysis_is_fresh(state) and not state.get("deal_library_force_refresh", False):
            st.success(
                "A fresh analysis for this property is already loaded. Change price or lane without repurchasing data."
            )
        if state.get("deal_library_force_refresh", False):
            st.warning("Fresh paid refresh is enabled and may consume the full displayed request budget.")
            st.checkbox(
                f"I understand this refresh may use up to {maximum} RentCast requests",
                key=credit_guard.CONFIRM_KEY,
            )


def _install_title_cleanup() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, "_app_stability_title_cleanup_installed", False):
        return
    original_title = st.title

    def title_with_clean_state(*args: Any, **kwargs: Any):
        clean_demo_defaults(st.session_state)
        return original_title(*args, **kwargs)

    st.title = title_with_clean_state
    st._app_stability_title_cleanup_installed = True


def _patch_loaded_aliases() -> None:
    for module_name in (
        "deal_decision_ui",
        "war_room_offer_engine.deal_decision_ui",
        "war_room_offer_engine.war_room_offer_engine.deal_decision_ui",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.render = render_stable_operator_workflow
            loaded.render_deal_library_box = render_compact_library
    for module_name in (
        "deal_library_ui",
        "war_room_offer_engine.deal_library_ui",
        "war_room_offer_engine.war_room_offer_engine.deal_library_ui",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.render_deal_library_box = render_compact_library


def install_base() -> bool:
    if getattr(decision_ui, "_app_stability_base_installed", False):
        _patch_loaded_aliases()
        return True

    # Remove dangerous demo defaults without changing historical import-detection
    # lists. Real property data may still legitimately equal one of these numbers.
    one_load_ui.ONE_LOAD_DEFAULTS.update(
        {
            "asking_price": 0,
            "contract_price": 0,
            "rent": 0,
            "beds": 0.0,
            "baths": 0.0,
            "sqft": 0,
        }
    )

    preview._stability_original_preview_control = _ORIGINAL_PREVIEW_CONTROL
    preview.render_preview_control = render_compact_verified_control
    mode_lock.render_verified_intelligence_control = render_compact_verified_control

    library_ui._stability_original_render_deal_library_box = _ORIGINAL_LIBRARY_RENDER
    library_ui.render_deal_library_box = render_compact_library
    decision_ui.render_deal_library_box = render_compact_library

    decision_ui._stability_original_render = _ORIGINAL_DECISION_RENDER
    decision_ui.render = render_stable_operator_workflow

    for key in (
        ANALYSIS_PROPERTY_KEY,
        ANALYSIS_RUN_ID_KEY,
        ANALYSIS_STATUS_KEY,
        ANALYSIS_COMPLETED_AT_KEY,
        ANALYSIS_ERRORS_KEY,
        ANALYSIS_WARNINGS_KEY,
    ):
        if key not in library.PERSISTED_STATE_KEYS:
            library.PERSISTED_STATE_KEYS.append(key)

    _install_title_cleanup()
    _patch_loaded_aliases()
    decision_ui._app_stability_base_installed = True
    return True


def install_post_guards() -> bool:
    """Install UI compaction after location and credit wrappers are configured."""
    try:
        import property_location_safety as location_safety
        import rentcast_credit_guard as credit_guard
    except ImportError:
        try:
            from . import property_location_safety as location_safety
            from . import rentcast_credit_guard as credit_guard
        except ImportError:
            from war_room_offer_engine import property_location_safety as location_safety
            from war_room_offer_engine import rentcast_credit_guard as credit_guard

    credit_guard.render_credit_panel = render_compact_credit_panel
    location_safety.render_credit_panel_with_location_guard = render_compact_credit_panel
    return True
