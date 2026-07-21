from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from typing import Any, Callable


ANALYSIS_PROPERTY_KEY = "stability_analysis_property"
RUN_STATUS_KEY = "stability_run_status"
COMPLETED_AT_KEY = "stability_analysis_completed_at"
LAST_ERROR_KEY = "stability_last_error"
NOTICE_KEY = "stability_notice"
TITLE_HOOK_FLAG = "_war_room_stability_title_hook_installed"
RUNTIME_FLAG = "_war_room_stability_runtime_installed"


# The original prototype started fresh sessions with realistic-looking demo
# numbers. Those defaults repeatedly leaked into real properties and looked like
# verified evidence. Production blank state must be genuinely blank.
DEMO_DEFAULTS = {
    "asking_price": 35000,
    "rent": 900,
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
}


# Evidence and computed state that may never travel from one property to another.
# User identity, market settings, intelligence mode, and section navigation are
# intentionally absent from this list.
EVIDENCE_KEYS = {
    "one_load_normalized",
    "one_load_run_success",
    "one_load_missing_fields",
    "one_load_data_sources_used",
    "one_load_final_answer",
    "one_load_next_action",
    "one_load_last_error",
    "decision_result",
    "decision_engine_result",
    "decision_last_run_at",
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
    "status",
    "days_on_market",
    "occupancy",
    "livable",
    "taxes",
    "tax_assessed_value",
    "last_sale_date",
    "last_sale_price",
    "owner_name",
    "listing_url",
    "listing_agent_name",
    "listing_agent_phone",
    "listing_agent_email",
    "listing_brokerage",
    "rent",
    "rent_estimate",
    "rent_source",
    "rent_confidence",
    "rent_verification_needed",
    "rent_requires_human_verification",
    "rent_verification_reasons",
    "rent_comps",
    "rentcast_rent_comps",
    "rent_comp_count",
    "rentcast_comp_count",
    "rentcast_rent_comp_count",
    "verified_rent_comp_count",
    "rent_comp_average",
    "rentcast_rent_comp_average",
    "rent_comp_median",
    "rentcast_rent_comp_median",
    "rent_low",
    "rent_high",
    "rent_search_mode",
    "rent_search_radius",
    "rent_search_days",
    "rent_search_trail",
    "rent_comp_quality_summary",
    "rentcast_total_listing_count",
    "rental_demand_confidence",
    "rentcast_submitted_address",
    "rentcast_rent_avm",
    "rentcast_rent_error",
    "rentcast_lookup_retry_used",
    "rentcast_pull_attempted",
    "rentcast_pull_status",
    "arv",
    "rentcast_arv",
    "sheet_arv",
    "manual_arv_override",
    "value_source",
    "arv_source",
    "arv_source_used",
    "arv_confidence",
    "arv_fallback_reason",
    "arv_fallback_warnings",
    "arv_requires_human_verification",
    "arv_verification_reasons",
    "condition_evidence",
    "rentcast_sold_comps",
    "rentcast_value_comps",
    "rentcast_sold_comp_count",
    "rentcast_value_comp_count",
    "verified_sold_comp_count",
    "auto_sold_comps",
    "auto_comp_count",
    "auto_arv_summary",
    "auto_recommended_arv",
    "auto_low_arv",
    "auto_conservative_arv",
    "auto_average_arv",
    "auto_high_arv",
    "strong_comp_count",
    "good_comp_count",
    "weak_comp_count",
    "excluded_comp_count",
    "auto_comp_radius",
    "auto_comp_date_range",
    "auto_comp_source",
    "auto_comp_messages",
    "auto_comp_summary_json",
    "excluded_comp_flags_json",
    "rentcast_value_error",
    "rentcast_property_error",
    "repairs",
    "manual_repair_estimate",
    "manual_repair_notes",
    "repair_notes",
    "repair_source",
    "repair_analysis",
    "recommended_repairs_from_analyzer",
    "repair_scope_confidence",
    "last_source_results",
    "last_auto_pull",
    "requested_property_address",
    "resolved_property_address",
    "location_verification_status",
    "location_verification_failed",
    "location_verification_error",
    "property_input_location_valid",
    "property_input_location_error",
    "wide_area_search_used",
    "search_scope_note",
}


PROPERTY_INPUT_KEYS = {
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
    "one_load_property_address",
    "one_load_listing_url",
    "one_load_asking_price",
    "asking_price",
    "contract_price",
    "notes",
    "seller_name",
    "seller_phone",
    "seller_email",
    "seller_motivation",
    "seller_timeline",
    "seller_desired_price",
    "seller_condition_notes",
    "seller_repair_notes",
    "deal_library_deal_id",
    "deal_library_version",
    "deal_library_team_notes",
    "deal_library_assigned_to",
    "deal_library_last_saved_at",
    "deal_library_loaded_without_api",
    "deal_offer_made_by",
    "decision_offer_made_by",
}


CREDIT_KEYS = {
    "rentcast_credit_guard_last_property",
    "rentcast_credit_guard_last_pull_epoch",
    "rentcast_credit_guard_last_run_stats",
    "rentcast_credit_guard_confirmation_property",
    "rentcast_credit_guard_confirm_refresh",
    "deal_library_force_refresh_reset_pending",
}


# These prototype defaults must be explicitly zeroed rather than removed because
# app.py uses setdefault() on each rerun and would otherwise recreate them.
ZERO_AFTER_CLEAR = {
    "asking_price",
    "contract_price",
    "decision_asking_price",
    "decision_current_negotiated_price",
    "decision_latest_counter",
    "decision_seller_bottom_line",
    "one_load_asking_price",
    "rent",
    "rent_estimate",
    "beds",
    "baths",
    "sqft",
    "taxes",
    "tax_assessed_value",
    "arv",
    "rentcast_arv",
    "sheet_arv",
    "manual_arv_override",
    "repairs",
    "manual_repair_estimate",
}


ALL_PROPERTY_KEYS = EVIDENCE_KEYS | PROPERTY_INPUT_KEYS | CREDIT_KEYS | {
    ANALYSIS_PROPERTY_KEY,
    RUN_STATUS_KEY,
    COMPLETED_AT_KEY,
    LAST_ERROR_KEY,
}


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def canonical_property(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"https?://(?:www\.)?", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    aliases = {
        " street ": " st ",
        " avenue ": " ave ",
        " road ": " rd ",
        " drive ": " dr ",
        " lane ": " ln ",
        " court ": " ct ",
        " boulevard ": " blvd ",
        " place ": " pl ",
        " highway ": " hwy ",
    }
    text = f" {text} "
    for old, new in aliases.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


def current_property_input(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    return str(
        state.get("decision_property_input")
        or state.get("one_load_property_address")
        or state.get("one_load_listing_url")
        or state.get("address")
        or ""
    ).strip()


def current_property_key(state: Any) -> str:
    return canonical_property(current_property_input(state))


def analysis_price(state: Any) -> float:
    if not hasattr(state, "get"):
        return 0.0
    for key in (
        "decision_current_negotiated_price",
        "decision_latest_counter",
        "decision_seller_bottom_line",
        "decision_asking_price",
        "contract_price",
        "asking_price",
    ):
        value = _number(state.get(key))
        if value > 0:
            return value
    return 0.0


def _has_real_property_state(state: Any) -> bool:
    if not hasattr(state, "get"):
        return False
    return bool(
        current_property_input(state)
        or state.get("one_load_normalized")
        or state.get("decision_result")
        or state.get("requested_property_address")
        or state.get("rentcast_submitted_address")
    )


def sanitize_demo_defaults(state: Any) -> list[str]:
    """Remove realistic-looking prototype defaults from a genuinely blank session."""
    if not hasattr(state, "get") or _has_real_property_state(state):
        return []
    # A real user-entered Decision Center price is a signal not to alter inputs.
    if any(
        _number(state.get(key)) > 0
        for key in (
            "decision_asking_price",
            "decision_current_negotiated_price",
            "decision_latest_counter",
            "decision_seller_bottom_line",
        )
    ):
        return []

    changed: list[str] = []
    for key, demo_value in DEMO_DEFAULTS.items():
        if _number(state.get(key)) == float(demo_value):
            state[key] = 0
            changed.append(key)
    if changed:
        state[NOTICE_KEY] = (
            "Production blank state was cleaned. Demo asking price, rent, beds, baths, and square footage "
            "are no longer treated as property facts."
        )
    return changed


def _patch_prototype_default_dicts() -> None:
    replacements = {
        "asking_price": 0,
        "rent": 0,
        "beds": 0.0,
        "baths": 0.0,
        "sqft": 0,
    }
    for module in list(sys.modules.values()):
        if module is None:
            continue
        for attribute in ("FIELD_DEFAULTS", "ONE_LOAD_DEFAULTS"):
            defaults = getattr(module, attribute, None)
            if isinstance(defaults, dict):
                for key, value in replacements.items():
                    if key in defaults:
                        defaults[key] = value


def readiness(state: Any) -> dict[str, Any]:
    try:
        import property_location_guard as location
        import team_offer_identity as identity
    except ImportError:
        try:
            from . import property_location_guard as location
            from . import team_offer_identity as identity
        except ImportError:
            from war_room_offer_engine import property_location_guard as location
            from war_room_offer_engine import team_offer_identity as identity

    raw_property = current_property_input(state)
    location_ok, location_message = location.validate_property_input(raw_property)
    operator = identity.active_team_member(state)
    price = analysis_price(state)
    missing: list[str] = []
    if not operator:
        missing.append("select the current team member")
    if not location_ok:
        missing.append(location_message or "enter the complete property location")
    if price <= 0:
        missing.append("enter the seller asking price or a real negotiated/counter price")

    analyzed_key = canonical_property(state.get(ANALYSIS_PROPERTY_KEY, "")) if hasattr(state, "get") else ""
    current_key = current_property_key(state)
    loaded = bool(
        current_key
        and analyzed_key
        and current_key == analyzed_key
        and (state.get("one_load_normalized") or state.get("decision_result"))
    )
    return {
        "ready": not missing,
        "missing": missing,
        "operator": operator,
        "property_complete": bool(location_ok),
        "location_message": location_message,
        "price": price,
        "analysis_loaded": loaded,
    }


def _clear_keys(state: Any, keys: set[str]) -> None:
    for key in keys:
        if key in ZERO_AFTER_CLEAR:
            state[key] = 0
        else:
            state.pop(key, None)


def clear_property_state(
    state: Any,
    *,
    preserve_property_input: bool = True,
    preserve_prices: bool = False,
    preserve_library_identity: bool = False,
) -> None:
    if not hasattr(state, "get"):
        return
    property_input = state.get("decision_property_input", "")
    preserved: dict[str, Any] = {}
    if preserve_prices:
        for key in (
            "decision_asking_price",
            "decision_current_negotiated_price",
            "decision_latest_counter",
            "decision_seller_bottom_line",
            "asking_price",
            "contract_price",
            "one_load_asking_price",
        ):
            preserved[key] = state.get(key)
    if preserve_library_identity:
        for key in ("deal_library_deal_id", "deal_library_version"):
            preserved[key] = state.get(key)

    _clear_keys(state, ALL_PROPERTY_KEYS)
    state["deal_library_force_refresh"] = False
    state["deal_library_status"] = "Analyzing"
    state["decision_negotiation_status"] = "Not contacted"
    if preserve_property_input:
        state["decision_property_input"] = property_input
    for key, value in preserved.items():
        state[key] = value


def clear_evidence_for_forced_refresh(state: Any) -> None:
    """Start a paid refresh from clean evidence without erasing negotiation inputs."""
    _clear_keys(state, EVIDENCE_KEYS | {"decision_result", "decision_engine_result", "decision_last_run_at", LAST_ERROR_KEY})
    for key in ("rent", "rent_estimate", "beds", "baths", "sqft", "arv", "rentcast_arv", "sheet_arv", "repairs"):
        state[key] = 0


def reconcile_property_state(state: Any) -> bool:
    """Clear prior-property evidence as soon as the operator changes the property."""
    if not hasattr(state, "get"):
        return False
    current = current_property_key(state)
    analyzed = canonical_property(state.get(ANALYSIS_PROPERTY_KEY, ""))
    if not analyzed and (state.get("one_load_normalized") or state.get("decision_result")):
        analyzed = canonical_property(
            state.get("rentcast_credit_guard_last_property")
            or state.get("requested_property_address")
            or state.get("rentcast_submitted_address")
            or ""
        )
        if analyzed:
            state[ANALYSIS_PROPERTY_KEY] = analyzed

    if not current or not analyzed or current == analyzed:
        return False

    raw_input = current_property_input(state)
    clear_property_state(state, preserve_property_input=True)
    state["decision_property_input"] = raw_input
    state[NOTICE_KEY] = (
        "A different property was entered. The prior property's rent, comps, ARV, repairs, contacts, "
        "negotiation, and BUY decision were cleared before they could carry into this property."
    )
    return True


def _fatal_integrity_issues(state: Any) -> list[str]:
    issues: list[str] = []
    if state.get("location_verification_failed"):
        issues.append(str(state.get("location_verification_error") or "subject property location was not verified"))
    current = current_property_key(state)
    analyzed = canonical_property(state.get(ANALYSIS_PROPERTY_KEY, ""))
    if current and analyzed and current != analyzed:
        issues.append("the displayed analysis belongs to a different property")
    if analysis_price(state) <= 0:
        issues.append("no real seller/negotiated price is loaded")
    return list(dict.fromkeys(issue for issue in issues if issue))


def enforce_fatal_decision_guard(state: Any) -> bool:
    decision = state.get("decision_result") if hasattr(state, "get") else None
    if not isinstance(decision, dict) or not decision:
        return False
    issues = _fatal_integrity_issues(state)
    if not issues or str(decision.get("decision", "")).upper() != "BUY":
        return False

    guarded = dict(decision)
    flags = [str(value) for value in (guarded.get("review_flags", []) or []) if str(value).strip()]
    flags.extend(issues)
    guarded["decision"] = "HUMAN REVIEW"
    guarded["confidence"] = "Weak"
    guarded["review_flags"] = list(dict.fromkeys(flags))
    guarded["next_action"] = (
        "Stop. Correct the property identity and price, then run one clean analysis before making or sending an offer."
    )
    guarded["reason"] = "The stability guard blocked a BUY because " + "; ".join(issues) + "."
    state["decision_result"] = guarded
    return True


def mark_restored_snapshot(state: Any, snapshot: dict[str, Any]) -> None:
    raw = str(
        snapshot.get("address")
        or snapshot.get("listing_url")
        or state.get("decision_property_input")
        or state.get("address")
        or ""
    ).strip()
    key = canonical_property(raw)
    if key:
        state[ANALYSIS_PROPERTY_KEY] = key
    state[RUN_STATUS_KEY] = "Loaded from Team Deal Library"
    state[COMPLETED_AT_KEY] = str(snapshot.get("updated_at") or snapshot.get("saved_at") or "")
    state[LAST_ERROR_KEY] = ""


def render_readiness_panel(st: Any) -> None:
    state = st.session_state
    info = readiness(state)
    with st.container(border=True):
        st.markdown("#### Simple Analysis Status")
        columns = st.columns(4)
        columns[0].metric("Team Member", info["operator"] or "Select name")
        columns[1].metric("Property", "Complete" if info["property_complete"] else "Incomplete")
        columns[2].metric("Working Price", f"${info['price']:,.0f}" if info["price"] > 0 else "Missing")
        if info["analysis_loaded"]:
            decision = state.get("decision_result", {}) or {}
            data_label = str(decision.get("decision") or state.get(RUN_STATUS_KEY) or "Loaded")
        else:
            data_label = "Ready to pull" if info["ready"] else "Not ready"
        columns[3].metric("Analysis", data_label)
        st.caption(
            "Workflow: select teammate → enter complete property and price → pull once → review Rent and Comps / ARV → save for the team."
        )
        if info["missing"]:
            st.warning("Before analysis: " + "; ".join(info["missing"]) + ".")
        notice = str(state.pop(NOTICE_KEY, "") or "").strip()
        if notice:
            st.info(notice)
        error = str(state.get(LAST_ERROR_KEY, "") or "").strip()
        if error:
            st.error("Last analysis stopped safely: " + error)


def _is_streamlit_control_exception(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    module = exc.__class__.__module__.lower()
    return "rerun" in name or name in {"stopexception", "stop"} or "scriptrunner" in module and "exception" in module


def install_runtime_patches() -> bool:
    try:
        import deal_decision_ui as decision_ui
        import deal_library as library
        import deal_library_ui as library_ui
        import rentcast_credit_guard as credit_guard
    except ImportError:
        try:
            from . import deal_decision_ui as decision_ui
            from . import deal_library as library
            from . import deal_library_ui as library_ui
            from . import rentcast_credit_guard as credit_guard
        except ImportError:
            from war_room_offer_engine import deal_decision_ui as decision_ui
            from war_room_offer_engine import deal_library as library
            from war_room_offer_engine import deal_library_ui as library_ui
            from war_room_offer_engine import rentcast_credit_guard as credit_guard

    if getattr(decision_ui, RUNTIME_FLAG, False):
        return True

    original_render = decision_ui.render
    original_run = decision_ui._run
    original_credit_panel = credit_guard.render_credit_panel
    original_button_guard = credit_guard._button_should_be_disabled
    original_restore = library.restore_snapshot

    def button_guard_stable(st: Any) -> tuple[bool, str]:
        disabled, reason = original_button_guard(st)
        if disabled:
            return disabled, reason
        info = readiness(st.session_state)
        if not info["ready"]:
            return True, "Before pulling data: " + "; ".join(info["missing"]) + "."
        return False, ""

    def credit_panel_stable(st: Any) -> None:
        original_credit_panel(st)
        render_readiness_panel(st)

    def run_stable(st: Any, ui: Any, media_files: list[Any]) -> Any:
        state = st.session_state
        reconcile_property_state(state)
        info = readiness(state)
        if not info["ready"]:
            raise RuntimeError("Analysis is not ready: " + "; ".join(info["missing"]))
        if state.get("deal_library_force_refresh", False):
            clear_evidence_for_forced_refresh(state)
        state[ANALYSIS_PROPERTY_KEY] = current_property_key(state)
        state[RUN_STATUS_KEY] = "Running"
        state[LAST_ERROR_KEY] = ""
        result = original_run(st, ui, media_files)
        state[ANALYSIS_PROPERTY_KEY] = current_property_key(state)
        state[COMPLETED_AT_KEY] = datetime.now(timezone.utc).isoformat()
        state[RUN_STATUS_KEY] = "Complete" if state.get("one_load_normalized") else "Needs review"
        enforce_fatal_decision_guard(state)
        normalized = state.get("one_load_normalized")
        if isinstance(normalized, dict):
            data = normalized.get("data")
            if isinstance(data, dict):
                data[ANALYSIS_PROPERTY_KEY] = state.get(ANALYSIS_PROPERTY_KEY, "")
                data[RUN_STATUS_KEY] = state.get(RUN_STATUS_KEY, "")
        return result

    def render_stable(
        st: Any,
        ui: Any,
        original_renderer: Callable,
        exit_mode_value: str = "Auto",
    ) -> Any:
        state = st.session_state
        _patch_prototype_default_dicts()
        sanitize_demo_defaults(state)
        reconcile_property_state(state)

        original_expander = st.expander

        def simpler_expander(label: Any, *args: Any, **kwargs: Any):
            if str(label or "").strip() in {
                "Negotiation Center",
                "Automatic engine work",
                "Advanced engine controls and full audit details",
            }:
                kwargs["expanded"] = False
            return original_expander(label, *args, **kwargs)

        st.expander = simpler_expander
        try:
            return original_render(st, ui, original_renderer, exit_mode_value)
        except Exception as exc:
            if _is_streamlit_control_exception(exc):
                raise
            state[RUN_STATUS_KEY] = "Failed safely"
            state[LAST_ERROR_KEY] = f"{exc.__class__.__name__}: {exc}"
            state.pop("decision_result", None)
            state.pop("decision_engine_result", None)
            st.error(
                "The analysis stopped safely before an offer was accepted. No BUY decision was kept. "
                "Review the message below, correct the input, and retry once."
            )
            with st.expander("Technical details for support", expanded=False):
                st.code(state[LAST_ERROR_KEY])
            return None
        finally:
            st.expander = original_expander

    def restore_stable(state: Any, snapshot: dict[str, Any]) -> None:
        original_restore(state, snapshot)
        mark_restored_snapshot(state, snapshot)

    decision_ui._stability_original_render = original_render
    decision_ui._stability_original_run = original_run
    credit_guard._stability_original_credit_panel = original_credit_panel
    credit_guard._stability_original_button_guard = original_button_guard
    library._stability_original_restore_snapshot = original_restore

    decision_ui._run = run_stable
    decision_ui.render = render_stable
    credit_guard.render_credit_panel = credit_panel_stable
    credit_guard._button_should_be_disabled = button_guard_stable
    library.restore_snapshot = restore_stable
    library_ui.restore_snapshot = restore_stable

    # Start New Property must clear every current-property field but keep the
    # selected browser-session teammate and global settings.
    for key in ALL_PROPERTY_KEYS:
        if key not in decision_ui.RESET_KEYS:
            decision_ui.RESET_KEYS.append(key)

    for key in (ANALYSIS_PROPERTY_KEY, RUN_STATUS_KEY, COMPLETED_AT_KEY):
        if key not in library.PERSISTED_STATE_KEYS:
            library.PERSISTED_STATE_KEYS.append(key)

    for module_name in (
        "deal_decision_ui",
        "war_room_offer_engine.deal_decision_ui",
        "war_room_offer_engine.war_room_offer_engine.deal_decision_ui",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded._run = run_stable
            loaded.render = render_stable

    decision_ui.__dict__[RUNTIME_FLAG] = True
    return True


def install_title_hook() -> bool:
    """Install runtime patches after all existing compatibility wrappers load."""
    try:
        import streamlit as st
    except Exception:
        return False
    if getattr(st, TITLE_HOOK_FLAG, False):
        return True

    original_title = st.title

    def title_with_stability(*args: Any, **kwargs: Any):
        install_runtime_patches()
        _patch_prototype_default_dicts()
        sanitize_demo_defaults(st.session_state)
        reconcile_property_state(st.session_state)
        return original_title(*args, **kwargs)

    st.title = title_with_stability
    setattr(st, TITLE_HOOK_FLAG, True)
    return True
