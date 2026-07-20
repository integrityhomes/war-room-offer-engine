from __future__ import annotations

import copy
import sys
from statistics import median
from typing import Any, Callable

try:
    import deal_decision_logic as logic
    import deal_decision_ui as decision_ui
    import rentcast_credit_guard as credit_guard
    import rentcast_intelligence_comps_ui_fix as comps_fix
    import rentcast_intelligence_core as core
    import rentcast_intelligence_preview as preview
    import rentcast_intelligence_rent_reconciliation as reconciliation
    import rentcast_intelligence_rent_ui_fix as rent_ui
    import rentcast_recorded_sales as recorded_sales
    import rentcast_rural_rentals as rural_rentals
    from ui_sections import comps_ui
except ImportError:
    try:
        from . import deal_decision_logic as logic
        from . import deal_decision_ui as decision_ui
        from . import rentcast_credit_guard as credit_guard
        from . import rentcast_intelligence_comps_ui_fix as comps_fix
        from . import rentcast_intelligence_core as core
        from . import rentcast_intelligence_preview as preview
        from . import rentcast_intelligence_rent_reconciliation as reconciliation
        from . import rentcast_intelligence_rent_ui_fix as rent_ui
        from . import rentcast_recorded_sales as recorded_sales
        from . import rentcast_rural_rentals as rural_rentals
        from .ui_sections import comps_ui
    except ImportError:
        from war_room_offer_engine import deal_decision_logic as logic
        from war_room_offer_engine import deal_decision_ui as decision_ui
        from war_room_offer_engine import rentcast_credit_guard as credit_guard
        from war_room_offer_engine import rentcast_intelligence_comps_ui_fix as comps_fix
        from war_room_offer_engine import rentcast_intelligence_core as core
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import rentcast_intelligence_rent_reconciliation as reconciliation
        from war_room_offer_engine import rentcast_intelligence_rent_ui_fix as rent_ui
        from war_room_offer_engine import rentcast_recorded_sales as recorded_sales
        from war_room_offer_engine import rentcast_rural_rentals as rural_rentals
        from war_room_offer_engine.ui_sections import comps_ui


POST_RUN_RERUN_KEY = "rentcast_credit_guard_post_run_rerun"

_ORIGINAL_RENT_BUILD = getattr(
    reconciliation,
    "_final_trust_original_rent_build",
    rent_ui.build_rent_display_model,
)
_ORIGINAL_BUILD_DECISION = getattr(
    logic,
    "_final_trust_original_build_decision",
    logic.build_decision,
)
_ORIGINAL_COMPS_RENDER = getattr(
    comps_ui,
    "_final_trust_original_comps_render",
    comps_ui.render_automatic_sold_comps_section,
)
_ORIGINAL_CREDIT_RENDER = getattr(
    decision_ui,
    "_final_trust_original_credit_render",
    decision_ui.render,
)


def _normalized_data(state: dict[str, Any]) -> dict[str, Any]:
    normalized = state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    return data if isinstance(data, dict) else {}


def _state_value(state: dict[str, Any], key: str, default: Any = None) -> Any:
    value = state.get(key, default)
    if value not in [None, "", [], {}]:
        return value
    return _normalized_data(state).get(key, default)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "required"}


def _row_age_days(row: dict[str, Any]) -> int | None:
    explicit = int(core._number(row.get("days_old"))) if core._number(row.get("days_old")) > 0 else None
    if explicit is not None:
        return explicit
    for key in ("last_seen_date", "removed_date", "listed_date"):
        value = row.get(key)
        if core._clean_text(value):
            age = core._days_old(value)
            if age is not None:
                return int(age)
    return None


def _rent_rows_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    data = _normalized_data(state)
    for value in (
        state.get("rent_comps"),
        state.get("rentcast_rent_comps"),
        data.get("rent_comps"),
    ):
        if isinstance(value, list) and value:
            return [dict(row) for row in value if isinstance(row, dict)]
    return []


def _prepare_rent_data(st: Any, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if data is None:
        try:
            prepared = dict(rent_ui._intelligence_data(st) or {})
        except Exception:
            prepared = {}
    else:
        prepared = dict(data or {})
    rows = prepared.get("rent_comps")
    if not isinstance(rows, list):
        rows = _rent_rows_from_state(dict(st.session_state))
    updated: list[dict[str, Any]] = []
    for raw in rows or []:
        if not isinstance(raw, dict):
            continue
        row = dict(raw)
        age = _row_age_days(row)
        if age is not None:
            row["days_old"] = age
        updated.append(row)
    prepared["rent_comps"] = updated
    return prepared


def build_rent_display_model_with_dates(
    st: Any,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive listing age from dates before rural confidence is calculated."""
    prepared = _prepare_rent_data(st, data)
    return dict(_ORIGINAL_RENT_BUILD(st, prepared) or {})


def _rent_assessment(state: dict[str, Any]) -> dict[str, Any]:
    rows = _rent_rows_from_state(state)
    selected = [row for row in rows if bool(row.get("include_default"))]
    if not selected and rows and int(core._number(_state_value(state, "rent_comp_count", 0))) == len(rows):
        selected = rows
    verified = sum(row.get("score") in {"Strong Comp", "Good Comp"} for row in selected)
    distances = [
        core._number(row.get("distance"))
        for row in selected
        if core._optional_number(row.get("distance")) is not None
    ]
    max_distance = max(distances, default=0.0)
    ages = [_row_age_days(row) for row in selected]
    missing_age = bool(selected) and any(age is None for age in ages)
    known_ages = [int(age) for age in ages if age is not None]
    max_days = max(known_ages, default=0)
    inactive = sum(core._clean_text(row.get("status")).lower() == "inactive" for row in selected)

    explicit_review = _as_bool(_state_value(state, "rent_requires_human_verification", False))
    reasons: list[str] = []
    if verified < 3:
        reasons.append("Fewer than three quality rental listings support the underwritten rent.")
    if max_distance > 25:
        reasons.append(f"Rental evidence expanded as far as {max_distance:.1f} miles.")
    if missing_age:
        reasons.append("One or more selected rental listings have no verifiable listing age.")
    if max_days > 730:
        reasons.append(f"Selected rental evidence includes listings up to {max_days} days old.")
    if selected and inactive == len(selected):
        reasons.append("Only inactive historical rental listings support the rent.")
    if explicit_review:
        reasons.extend(str(item) for item in (_state_value(state, "rent_verification_reasons", []) or []))
    reasons = list(dict.fromkeys(item for item in reasons if str(item).strip()))
    requires_review = explicit_review or bool(reasons)

    if not requires_review and verified >= 5 and max_distance <= 10 and max_days <= 365:
        confidence = "Strong"
    elif not requires_review and verified >= 3 and max_distance <= 25 and max_days <= 730:
        confidence = "Medium"
    else:
        confidence = "Weak"
    return {
        "rows": rows,
        "selected": selected,
        "verified": verified,
        "max_distance": max_distance,
        "max_days": max_days,
        "missing_age": missing_age,
        "requires_review": requires_review,
        "reasons": reasons,
        "confidence": confidence,
    }


def _verified_sold_count(state: dict[str, Any]) -> int:
    if "verified_sold_comp_count" in state or "verified_sold_comp_count" in _normalized_data(state):
        return int(core._number(_state_value(state, "verified_sold_comp_count", 0)))
    return int(logic.sold_count(state))


def _replace_evaluation(chosen: dict[str, Any]) -> None:
    evaluations = chosen.get("evaluations", [])
    if not isinstance(evaluations, list):
        return
    for row in evaluations:
        if isinstance(row, dict) and row.get("strategy") == chosen.get("strategy"):
            for key in ("decision", "reason", "next_action"):
                row[key] = chosen.get(key)


def build_decision_lane_confidence(
    state: dict[str, Any],
    assumptions: Any,
    engine: dict[str, Any],
    selected: str,
) -> dict[str, Any]:
    """Keep confidence tied to the evidence required by the selected exit lane."""
    chosen = dict(_ORIGINAL_BUILD_DECISION(state, assumptions, engine, selected) or {})
    strategy = str(chosen.get("strategy", ""))

    if logic.is_slow(strategy):
        assessment = _rent_assessment(state)
        if assessment["requires_review"]:
            if chosen.get("decision") == "BUY":
                chosen["decision"] = "HUMAN REVIEW"
                chosen["reason"] = (
                    "Price works, but rural rental support still needs verification before committing."
                )
                chosen["next_action"] = "Verify current local rent support before moving to contract."
            chosen["confidence"] = "Weak"
            chosen["rent_evidence_reasons"] = assessment["reasons"]
        else:
            chosen["confidence"] = assessment["confidence"]
    else:
        verified = _verified_sold_count(state)
        arv_review = _as_bool(_state_value(state, "arv_requires_human_verification", False))
        arv_confidence = core._clean_text(_state_value(state, "arv_confidence", "")).lower()
        listing_only = any(
            term in core._clean_text(
                _state_value(state, "arv_source_used", "")
                or _state_value(state, "value_source", "")
                or _state_value(state, "arv_source", "")
            ).lower()
            for term in ("avm", "listing-based", "dates unverified")
        )
        if arv_review or verified < 3 or listing_only:
            if chosen.get("decision") == "BUY":
                chosen["decision"] = "HUMAN REVIEW"
                chosen["reason"] = "Wholesale pricing still needs verified recorded-sale ARV support."
                chosen["next_action"] = "Verify recorded sold comps and condition before committing."
            chosen["confidence"] = "Weak"
        elif arv_confidence == "strong":
            chosen["confidence"] = "Strong"
        else:
            chosen["confidence"] = "Medium"

    if chosen.get("decision") == "HUMAN REVIEW":
        chosen["confidence"] = "Weak"
    _replace_evaluation(chosen)
    return chosen


def _is_recorded_row(row: dict[str, Any]) -> bool:
    return bool(
        row.get("record_type") == "recorded_sale"
        or core._clean_text(row.get("source")).startswith("RentCast Recorded Sale")
    )


def _listing_value_rows(state: Any) -> list[dict[str, Any]]:
    if not hasattr(state, "get"):
        return []
    candidates = state.get("rentcast_value_listing_comps", [])
    if not isinstance(candidates, list) or not candidates:
        candidates = state.get("auto_sold_comps", [])
    rows: list[dict[str, Any]] = []
    for raw in candidates or []:
        if not isinstance(raw, dict) or _is_recorded_row(raw):
            continue
        price = core._number(raw.get("listing_price") or raw.get("sold_price") or raw.get("price"))
        if price <= 0:
            continue
        row = dict(raw)
        row["listing_price"] = price
        row["comp_address"] = core._clean_text(
            raw.get("comp_address") or raw.get("address") or raw.get("formattedAddress")
        )
        rows.append(row)
    return rows


def _render_listing_value_fallback(st: Any, ui: Any, rows: list[dict[str, Any]]) -> None:
    state = st.session_state
    prices = [core._number(row.get("listing_price")) for row in rows if core._number(row.get("listing_price")) > 0]
    listing_median = median(prices) if prices else 0
    avm = core._number(state.get("rentcast_arv"))

    state["verified_sold_comp_count"] = 0
    state["arv_requires_human_verification"] = True
    state["arv_verification_reasons"] = list(dict.fromkeys(
        list(state.get("arv_verification_reasons", []) or [])
        + ["Only listing-based value evidence is available; no verified recorded closed sales support ARV."]
    ))
    state["arv_confidence"] = "AVM only"
    state["arv_source_used"] = "RentCast AVM — listing-based"
    state["value_source"] = "RentCast AVM — listing-based"
    state["use_auto_arv_over_manual_comps"] = False
    state["auto_recommended_arv"] = 0
    state["strong_comp_count"] = 0
    state["good_comp_count"] = 0
    state["weak_comp_count"] = len(rows)
    state["auto_arv_summary"] = {
        "recommended_arv": 0,
        "arv_confidence": "AVM only",
        "strong_comp_count": 0,
        "good_comp_count": 0,
        "weak_comp_count": len(rows),
        "excluded_comp_count": 0,
        "verified_sold_comp_count": 0,
        "comp_data_type": "RentCast sale listings; not recorded closed sales",
        "arv_requires_human_verification": True,
        "verification_reasons": list(state["arv_verification_reasons"]),
        "explanation": "Listing prices are market context only and are not verified closed-sale ARV support.",
    }

    st.markdown("### Listing-Based Value Evidence — Not Closed Sales")
    st.warning(
        "RentCast returned value listings or an AVM, but no verified public-record closed sales were loaded. "
        "Do not treat these asking/listing prices as ARV."
    )
    table_rows = []
    for row in rows:
        table_rows.append(
            {
                "Address": row.get("comp_address", ""),
                "Listing Price": ui.money(row.get("listing_price", 0)),
                "Beds": row.get("beds", 0),
                "Baths": row.get("baths", 0),
                "Sqft": row.get("square_feet") or row.get("sqft", 0),
                "Distance": row.get("distance_miles") or row.get("distance", 0),
                "Status": row.get("status", ""),
                "Evidence": "Listing price — sale date not verified",
            }
        )
    if table_rows:
        st.dataframe(ui.pd.DataFrame(table_rows), use_container_width=True)
    metrics = st.columns(4)
    metrics[0].metric("RentCast AVM Reference", ui.money(avm) if avm > 0 else "Unavailable")
    metrics[1].metric("Listing Median", ui.money(listing_median))
    metrics[2].metric("Verified Recorded Sales", 0)
    metrics[3].metric("ARV Confidence", "AVM only")
    st.info("Use manual verified sold comps or a later recorded-sale pull before setting a wholesale ARV.")


def render_comps_with_safe_listing_fallback(st: Any, ui: Any) -> None:
    if preview.preview_enabled(st) and not comps_fix._recorded_preview_active(st):
        rows = _listing_value_rows(st.session_state)
        if rows:
            _render_listing_value_fallback(st, ui, rows)
            return
    return _ORIGINAL_COMPS_RENDER(st, ui)


def render_with_post_run_stats(
    st: Any,
    ui: Any,
    original_renderer: Callable,
    exit_mode_value: str = "Auto",
) -> Any:
    previous = st.session_state.get(credit_guard.LAST_STATS_KEY, {}) or {}
    previous_completed = previous.get("completed_at") if isinstance(previous, dict) else None
    result = _ORIGINAL_CREDIT_RENDER(st, ui, original_renderer, exit_mode_value)
    current = st.session_state.get(credit_guard.LAST_STATS_KEY, {}) or {}
    current_completed = current.get("completed_at") if isinstance(current, dict) else None
    changed = bool(current_completed and current_completed != previous_completed)
    if changed and not st.session_state.get(POST_RUN_RERUN_KEY, False):
        st.session_state[POST_RUN_RERUN_KEY] = True
        rerun = getattr(st, "rerun", None)
        if callable(rerun):
            rerun()
    elif not changed and st.session_state.get(POST_RUN_RERUN_KEY, False):
        st.session_state.pop(POST_RUN_RERUN_KEY, None)
    return result


def _sync_module_request_helpers() -> None:
    recorded_sales._request_json = credit_guard.request_json_budgeted
    rural_rentals._request_json = credit_guard.request_json_budgeted
    for module_name in (
        "rentcast_recorded_sales",
        "war_room_offer_engine.rentcast_recorded_sales",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded._request_json = credit_guard.request_json_budgeted
    for module_name in (
        "rentcast_rural_rentals",
        "war_room_offer_engine.rentcast_rural_rentals",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded._request_json = credit_guard.request_json_budgeted


def install() -> bool:
    if getattr(core, "_rentcast_final_trust_patch_installed", False):
        return True

    reconciliation._final_trust_original_rent_build = _ORIGINAL_RENT_BUILD
    logic._final_trust_original_build_decision = _ORIGINAL_BUILD_DECISION
    comps_ui._final_trust_original_comps_render = _ORIGINAL_COMPS_RENDER
    decision_ui._final_trust_original_credit_render = _ORIGINAL_CREDIT_RENDER

    rent_ui.build_rent_display_model = build_rent_display_model_with_dates
    reconciliation.build_rent_display_model_reconciled = build_rent_display_model_with_dates
    logic.build_decision = build_decision_lane_confidence
    comps_ui.render_automatic_sold_comps_section = render_comps_with_safe_listing_fallback
    decision_ui.render = render_with_post_run_stats
    _sync_module_request_helpers()

    core._rentcast_final_trust_patch_installed = True
    return True


install()
