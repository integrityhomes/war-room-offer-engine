from __future__ import annotations

import os
import sys
from typing import Any, Callable

try:
    import address_rentcast_bridge as bridge
    import data_sources as ds
    import rentcast_auto_enrichment as rentcast
    import rentcast_state_bootstrap as bootstrap
    from rentcast_intelligence_core import INTELLIGENCE_STATE_KEYS
except ImportError:
    try:
        from . import address_rentcast_bridge as bridge
        from . import data_sources as ds
        from . import rentcast_auto_enrichment as rentcast
        from . import rentcast_state_bootstrap as bootstrap
        from .rentcast_intelligence_core import INTELLIGENCE_STATE_KEYS
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge as bridge
        from war_room_offer_engine import data_sources as ds
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine import rentcast_state_bootstrap as bootstrap
        from war_room_offer_engine.rentcast_intelligence_core import INTELLIGENCE_STATE_KEYS


PREVIEW_STATE_KEY = "rentcast_intelligence_preview_enabled"
PREVIEW_ACTIVE_KEY = "rentcast_intelligence_preview_active"
PREVIEW_QUERY_KEY = "rentcast_preview"
PREVIEW_ENV_KEY = "RENTCAST_INTELLIGENCE_PREVIEW"
_TRUTHY = {"1", "true", "yes", "y", "on", "enabled", "preview"}

# Capture the already-merged production behavior before PR #67 installs its
# intelligence wrappers. one_load_sources_safe imports this module first.
_BASELINE_RENTCAST_GET_JSON = rentcast._get_json
_BASELINE_RENTCAST_NORMALIZE_RENT = rentcast.normalize_rent_comp
_BASELINE_RENTCAST_NORMALIZE_SOLD = rentcast.normalize_sold_comp
_BASELINE_RENTCAST_BUILD_SOLD = rentcast.build_sold_comp_intelligence
_BASELINE_RENTCAST_ENRICH = rentcast.enrich_property_with_rentcast
_BASELINE_BRIDGE_PROPERTY_FACTS = bridge._property_facts
_BASELINE_BRIDGE_ENRICH = bridge.enrich_property_with_rentcast
_BASELINE_BRIDGE_LOOKUP = bridge.lookup_rentcast_with_full_enrichment
_BASELINE_DATA_SOURCE_LOOKUP = ds.lookup_rentcast
_BASELINE_BOOTSTRAP_BUILD_SOLD = bootstrap.build_sold_comp_intelligence
_BASELINE_BOOTSTRAP_HYDRATE = bootstrap.hydrate_rentcast_state

# Changing engines clears calculated evidence so old and preview results cannot
# be mixed. Property input, lane, seller price, and negotiation notes remain.
_PREVIEW_RESET_KEYS = set(INTELLIGENCE_STATE_KEYS) | {
    PREVIEW_ACTIVE_KEY,
    "one_load_normalized", "last_auto_pull", "last_source_results",
    "decision_result", "decision_engine_result", "decision_last_run_at",
    "address", "city", "state", "zip", "market", "county", "latitude", "longitude",
    "beds", "baths", "sqft", "lot_size", "year_built", "property_type", "taxes",
    "tax_assessed_value", "last_sale_date", "last_sale_price", "assessor_id", "subdivision", "zoning",
    "rent", "rent_estimate", "rent_source", "rent_confidence", "rent_verification_needed",
    "rent_comps", "rentcast_rent_comps", "rent_comp_count", "rentcast_comp_count",
    "rentcast_rent_comp_count", "rent_comp_average", "rentcast_rent_comp_average",
    "rent_comp_median", "rentcast_rent_comp_median", "rent_low", "rent_high",
    "arv", "rentcast_arv", "sheet_arv", "arv_source", "arv_source_used", "value_source",
    "arv_confidence", "arv_fallback_reason", "arv_fallback_warnings",
    "rentcast_sold_comps", "rentcast_value_comps", "rentcast_sold_comp_count",
    "rentcast_value_comp_count", "auto_sold_comps", "auto_comp_count", "auto_arv_summary",
    "auto_recommended_arv", "auto_low_arv", "auto_conservative_arv", "auto_average_arv",
    "auto_high_arv", "strong_comp_count", "good_comp_count", "weak_comp_count",
    "excluded_comp_count", "auto_comp_radius", "auto_comp_date_range", "auto_comp_source",
    "auto_comp_messages", "auto_comp_summary_json", "excluded_comp_flags_json",
}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip().lower() in _TRUTHY


def _query_preview_value(st: Any) -> Any:
    try:
        return st.query_params.get(PREVIEW_QUERY_KEY, "")
    except Exception:
        try:
            values = st.experimental_get_query_params().get(PREVIEW_QUERY_KEY, [])
            return values[-1] if isinstance(values, list) and values else values
        except Exception:
            return ""


def preview_enabled(st: Any = None) -> bool:
    """Whether PR #67 is active for this process or browser session."""
    if _as_bool(os.getenv(PREVIEW_ENV_KEY, "")):
        return True
    try:
        if st is None:
            import streamlit as st  # type: ignore[no-redef]
        return _as_bool(_query_preview_value(st)) or _as_bool(
            st.session_state.get(PREVIEW_STATE_KEY, False)
        )
    except Exception:
        return False


def _clear_preview_analysis(st: Any) -> None:
    for key in _PREVIEW_RESET_KEYS:
        st.session_state.pop(key, None)


def _preview_mode_changed(st: Any) -> None:
    enabled = _as_bool(st.session_state.get(PREVIEW_STATE_KEY, False))
    _clear_preview_analysis(st)
    st.session_state[PREVIEW_STATE_KEY] = enabled
    st.session_state["rentcast_preview_mode_changed"] = True
    # Prevent a saved snapshot from replacing the live preview pull.
    st.session_state["deal_library_force_refresh"] = enabled
    st.session_state["deal_library_loaded_without_api"] = False


def render_preview_control(st: Any) -> None:
    query_enabled = _as_bool(_query_preview_value(st))
    if query_enabled and PREVIEW_STATE_KEY not in st.session_state:
        st.session_state[PREVIEW_STATE_KEY] = True
        st.session_state["deal_library_force_refresh"] = True

    st.checkbox(
        "Test the new rural RentCast intelligence",
        key=PREVIEW_STATE_KEY,
        on_change=_preview_mode_changed,
        args=(st,),
        help=(
            "Off uses the current production engine. On uses PR #67's recorded-sale ARV and "
            "adaptive rural rental search only in this browser session. Changing it clears the "
            "previous calculated analysis but keeps your property and price fields."
        ),
    )
    if preview_enabled(st):
        st.info(
            "Rural intelligence preview is ON. This run uses recorded public sales and adaptive "
            "rural rental searches. Preview results are not auto-saved to the Team Deal Library."
        )
    if st.session_state.pop("rentcast_preview_mode_changed", False):
        st.caption("The previous calculated analysis was cleared so the two engines cannot mix data.")


def _install_header_control() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False
    if getattr(st, "_rentcast_intelligence_preview_ui_installed", False):
        return True

    original_header = st.header

    def header_with_preview_control(body: Any, *args: Any, **kwargs: Any):
        result = original_header(body, *args, **kwargs)
        if str(body or "").strip() == "Deal Decision Center":
            render_preview_control(st)
        return result

    st.header = header_with_preview_control
    st._rentcast_intelligence_preview_ui_installed = True
    return True


def _install_auto_save_guard() -> bool:
    try:
        import deal_library_ui as library_ui
    except ImportError:
        try:
            from . import deal_library_ui as library_ui
        except ImportError:
            try:
                from war_room_offer_engine import deal_library_ui as library_ui
            except ImportError:
                return False

    original = getattr(
        library_ui,
        "_rentcast_intelligence_preview_original_auto_save",
        getattr(library_ui, "auto_save_completed_analysis", None),
    )
    if not callable(original):
        return False

    def guarded_auto_save(st: Any, *args: Any, **kwargs: Any):
        if preview_enabled(st):
            st.session_state["deal_library_last_message"] = (
                "Rural intelligence preview result was not auto-saved. Turn preview off after validation."
            )
            return {"ok": True, "preview_skipped": True}
        return original(st, *args, **kwargs)

    library_ui._rentcast_intelligence_preview_original_auto_save = original
    library_ui.auto_save_completed_analysis = guarded_auto_save
    for module_name in ("deal_decision_ui", "war_room_offer_engine.deal_decision_ui"):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.auto_save_completed_analysis = guarded_auto_save
    return True


def _install_decision_dispatch() -> bool:
    try:
        import deal_decision_logic as logic
    except ImportError:
        try:
            from . import deal_decision_logic as logic
        except ImportError:
            try:
                from war_room_offer_engine import deal_decision_logic as logic
            except ImportError:
                return False

    if getattr(logic, "_rentcast_intelligence_preview_dispatch_installed", False):
        return True

    intelligent_rent_verified = logic.rent_verified
    intelligent_sold_count = logic.sold_count
    intelligent_missing_items = logic.missing_items
    baseline_rent_verified = getattr(
        logic, "_rentcast_property_intelligence_original_rent_verified", intelligent_rent_verified
    )
    baseline_sold_count = getattr(
        logic, "_rentcast_property_intelligence_original_sold_count", intelligent_sold_count
    )
    baseline_missing_items = getattr(
        logic, "_rentcast_property_intelligence_original_missing_items", intelligent_missing_items
    )

    def rent_verified_dispatch(state: dict[str, Any]) -> bool:
        target = intelligent_rent_verified if preview_enabled() else baseline_rent_verified
        return target(state)

    def sold_count_dispatch(state: dict[str, Any]) -> int:
        target = intelligent_sold_count if preview_enabled() else baseline_sold_count
        return target(state)

    def missing_items_dispatch(state: dict[str, Any], strategy: str) -> list[str]:
        target = intelligent_missing_items if preview_enabled() else baseline_missing_items
        return target(state, strategy)

    logic.rent_verified = rent_verified_dispatch
    logic.sold_count = sold_count_dispatch
    logic.missing_items = missing_items_dispatch
    logic._rentcast_intelligence_preview_dispatch_installed = True
    return True


def _result_with_preview_marker(result: Any) -> Any:
    if isinstance(result, dict):
        result = dict(result)
        result[PREVIEW_ACTIVE_KEY] = True
    return result


def _dispatch(enabled_target: Callable, baseline_target: Callable, *args: Any, **kwargs: Any):
    target = enabled_target if preview_enabled() else baseline_target
    return target(*args, **kwargs)


def install_dispatch_gate(intelligence: Any = None) -> bool:
    """Put PR #67 behind the per-session preview switch after it installs."""
    if getattr(rentcast, "_rentcast_intelligence_preview_dispatch_installed", False):
        _install_decision_dispatch()
        _install_auto_save_guard()
        return True

    intelligent_get_json = rentcast._get_json
    intelligent_normalize_rent = rentcast.normalize_rent_comp
    intelligent_normalize_sold = rentcast.normalize_sold_comp
    intelligent_build_sold = rentcast.build_sold_comp_intelligence
    intelligent_enrich = rentcast.enrich_property_with_rentcast
    intelligent_bridge_property_facts = bridge._property_facts
    intelligent_bridge_enrich = bridge.enrich_property_with_rentcast
    intelligent_bridge_lookup = bridge.lookup_rentcast_with_full_enrichment
    intelligent_data_source_lookup = ds.lookup_rentcast
    intelligent_bootstrap_build = bootstrap.build_sold_comp_intelligence
    intelligent_bootstrap_hydrate = bootstrap.hydrate_rentcast_state

    def get_json_dispatch(*args: Any, **kwargs: Any):
        return _dispatch(intelligent_get_json, _BASELINE_RENTCAST_GET_JSON, *args, **kwargs)

    def normalize_rent_dispatch(item: dict[str, Any]) -> dict[str, Any]:
        return _dispatch(intelligent_normalize_rent, _BASELINE_RENTCAST_NORMALIZE_RENT, item)

    def normalize_sold_dispatch(item: dict[str, Any]) -> dict[str, Any]:
        return _dispatch(intelligent_normalize_sold, _BASELINE_RENTCAST_NORMALIZE_SOLD, item)

    def build_sold_dispatch(
        data: dict[str, Any], sold_comps: list[dict[str, Any]], full_address: str = ""
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return _dispatch(
            intelligent_build_sold, _BASELINE_RENTCAST_BUILD_SOLD,
            data, sold_comps, full_address,
        )

    def enrich_dispatch(data: dict[str, Any], api_key: str, session: Any = None):
        kwargs = {} if session is None else {"session": session}
        if preview_enabled():
            return _result_with_preview_marker(intelligent_enrich(data, api_key, **kwargs))
        return _BASELINE_RENTCAST_ENRICH(data, api_key, **kwargs)

    def property_facts_dispatch(address: str, api_key: str):
        return _dispatch(
            intelligent_bridge_property_facts, _BASELINE_BRIDGE_PROPERTY_FACTS,
            address, api_key,
        )

    def bridge_enrich_dispatch(data: dict[str, Any], api_key: str, session: Any = None):
        kwargs = {} if session is None else {"session": session}
        if preview_enabled():
            return _result_with_preview_marker(intelligent_bridge_enrich(data, api_key, **kwargs))
        return _BASELINE_BRIDGE_ENRICH(data, api_key, **kwargs)

    def bridge_lookup_dispatch(address: str, beds: float = 0, baths: float = 0, sqft: float = 0):
        if preview_enabled():
            return _result_with_preview_marker(
                intelligent_bridge_lookup(address, beds=beds, baths=baths, sqft=sqft)
            )
        return _BASELINE_BRIDGE_LOOKUP(address, beds=beds, baths=baths, sqft=sqft)

    def data_source_lookup_dispatch(address: str, beds: float = 0, baths: float = 0, sqft: float = 0):
        if preview_enabled():
            return _result_with_preview_marker(
                intelligent_data_source_lookup(address, beds=beds, baths=baths, sqft=sqft)
            )
        return _BASELINE_DATA_SOURCE_LOOKUP(address, beds=beds, baths=baths, sqft=sqft)

    def bootstrap_build_dispatch(
        data: dict[str, Any], sold_comps: list[dict[str, Any]], full_address: str = ""
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return _dispatch(
            intelligent_bootstrap_build, _BASELINE_BOOTSTRAP_BUILD_SOLD,
            data, sold_comps, full_address,
        )

    def bootstrap_hydrate_dispatch(st: Any) -> None:
        target = intelligent_bootstrap_hydrate if preview_enabled(st) else _BASELINE_BOOTSTRAP_HYDRATE
        target(st)
        if preview_enabled(st):
            st.session_state[PREVIEW_ACTIVE_KEY] = True

    rentcast._get_json = get_json_dispatch
    rentcast.normalize_rent_comp = normalize_rent_dispatch
    rentcast.normalize_sold_comp = normalize_sold_dispatch
    rentcast.build_sold_comp_intelligence = build_sold_dispatch
    rentcast.enrich_property_with_rentcast = enrich_dispatch

    bridge._property_facts = property_facts_dispatch
    bridge.enrich_property_with_rentcast = bridge_enrich_dispatch
    bridge.lookup_rentcast_with_full_enrichment = bridge_lookup_dispatch
    ds.lookup_rentcast = data_source_lookup_dispatch

    bootstrap.build_sold_comp_intelligence = bootstrap_build_dispatch
    bootstrap.hydrate_rentcast_state = bootstrap_hydrate_dispatch

    # Keep direct imports used by one_load_sources_safe routed through the gate.
    if intelligence is not None:
        intelligence.preview_enabled = preview_enabled
        intelligence.PREVIEW_ACTIVE_KEY = PREVIEW_ACTIVE_KEY

    rentcast._rentcast_intelligence_preview_dispatch_installed = True
    _install_decision_dispatch()
    _install_auto_save_guard()
    return True


def install() -> bool:
    ui_ok = _install_header_control()
    _install_auto_save_guard()
    return ui_ok


install()
