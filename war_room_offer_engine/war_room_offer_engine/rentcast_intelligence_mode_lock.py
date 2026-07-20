from __future__ import annotations

import sys
from typing import Any

try:
    import deal_library as library
    import deal_library_ui as library_ui
    import rentcast_intelligence_comps_ui_fix as comps_ui_fix
    import rentcast_intelligence_preview as preview
    import rentcast_intelligence_rent_ui_fix as rent_ui_fix
except ImportError:
    try:
        from . import deal_library as library
        from . import deal_library_ui as library_ui
        from . import rentcast_intelligence_comps_ui_fix as comps_ui_fix
        from . import rentcast_intelligence_preview as preview
        from . import rentcast_intelligence_rent_ui_fix as rent_ui_fix
    except ImportError:
        from war_room_offer_engine import deal_library as library
        from war_room_offer_engine import deal_library_ui as library_ui
        from war_room_offer_engine import rentcast_intelligence_comps_ui_fix as comps_ui_fix
        from war_room_offer_engine import rentcast_intelligence_preview as preview
        from war_room_offer_engine import rentcast_intelligence_rent_ui_fix as rent_ui_fix


MODE_KEY = "rentcast_intelligence_mode_used"
MODE_VERIFIED = "verified"
MODE_STANDARD = "standard"

_ORIGINAL_PREVIEW_ENABLED = getattr(
    preview,
    "_verified_mode_original_preview_enabled",
    preview.preview_enabled,
)
_ORIGINAL_RESULT_MARKER = getattr(
    preview,
    "_verified_mode_original_result_marker",
    preview._result_with_preview_marker,
)
_ORIGINAL_AUTO_SAVE = getattr(
    library_ui,
    "_rentcast_intelligence_preview_original_auto_save",
    library_ui.auto_save_completed_analysis,
)


def _normalized_data(state: Any) -> dict[str, Any]:
    if not hasattr(state, "get"):
        return {}
    normalized = state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    return data if isinstance(data, dict) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _state_value(state: Any, key: str) -> Any:
    if hasattr(state, "get") and key in state:
        return state.get(key)
    return _normalized_data(state).get(key)


def result_uses_verified_intelligence(state: Any) -> bool:
    """Whether the loaded evidence was produced by the verified engine.

    The result marker is intentionally independent of the current checkbox. A
    team member must never be able to view recorded-sale or rural-rental data
    through the legacy UI merely because the mode control changed after a pull.
    """
    if not hasattr(state, "get"):
        return False

    mode = _text(_state_value(state, MODE_KEY)).lower()
    if mode == MODE_VERIFIED:
        return True
    if bool(_state_value(state, preview.PREVIEW_ACTIVE_KEY)):
        return True

    summary = _state_value(state, "auto_arv_summary") or {}
    if isinstance(summary, dict) and summary.get("comp_data_type") == "RentCast public-record closed sales":
        return True

    arv_source = _text(
        _state_value(state, "arv_source")
        or _state_value(state, "arv_source_used")
        or _state_value(state, "value_source")
    ).lower()
    if "recorded sale" in arv_source or "public-record closed sale" in arv_source:
        return True

    for row in _rows(_state_value(state, "auto_sold_comps")) + _rows(
        _state_value(state, "rentcast_sold_comps")
    ):
        if row.get("record_type") == "recorded_sale" or _text(row.get("source")).startswith(
            "RentCast Recorded Sale"
        ):
            return True

    for row in _rows(_state_value(state, "rent_comps")) + _rows(
        _state_value(state, "rentcast_rent_comps")
    ):
        if row.get("record_type") == "rental_listing" or _text(row.get("source")).startswith(
            "RentCast Rental Listing"
        ):
            return True

    if _state_value(state, "arv_search_trail") or _state_value(state, "rent_search_trail"):
        provenance = _state_value(state, "rentcast_data_provenance")
        if isinstance(provenance, dict) and provenance:
            return True

    return False


def verified_intelligence_enabled(st: Any = None) -> bool:
    """Use the requested mode or the mode that produced the loaded evidence."""
    try:
        if _ORIGINAL_PREVIEW_ENABLED(st):
            return True
    except Exception:
        pass
    try:
        if st is None:
            import streamlit as st  # type: ignore[no-redef]
        return result_uses_verified_intelligence(st.session_state)
    except Exception:
        return False


def _mark_verified_result(result: Any) -> Any:
    marked = _ORIGINAL_RESULT_MARKER(result)
    if isinstance(marked, dict):
        marked = dict(marked)
        marked[preview.PREVIEW_ACTIVE_KEY] = True
        marked[MODE_KEY] = MODE_VERIFIED
    return marked


def _clear_and_change_mode(st: Any) -> None:
    enabled = preview._as_bool(st.session_state.get(preview.PREVIEW_STATE_KEY, False))
    preview._clear_preview_analysis(st)
    st.session_state[preview.PREVIEW_STATE_KEY] = enabled
    st.session_state[MODE_KEY] = MODE_VERIFIED if enabled else MODE_STANDARD
    st.session_state["rentcast_preview_mode_changed"] = True
    # Changing calculation mode does not itself authorize a paid refresh. The
    # saved-deal preflight should still get the first opportunity to reuse data.
    st.session_state["deal_library_force_refresh"] = False
    st.session_state["deal_library_loaded_without_api"] = False


def render_verified_intelligence_control(st: Any) -> None:
    state = st.session_state
    loaded_verified = result_uses_verified_intelligence(state)
    query_enabled = preview._as_bool(preview._query_preview_value(st))

    if preview.PREVIEW_STATE_KEY not in state:
        # Accuracy-first default for the team. Basic AVM/listing mode remains an
        # explicit lower-cost choice before a property analysis is loaded.
        state[preview.PREVIEW_STATE_KEY] = True
    if query_enabled:
        state[preview.PREVIEW_STATE_KEY] = True
    if loaded_verified:
        state[preview.PREVIEW_STATE_KEY] = True
        state[preview.PREVIEW_ACTIVE_KEY] = True
        state[MODE_KEY] = MODE_VERIFIED

    st.checkbox(
        "Use verified RentCast intelligence (recommended)",
        key=preview.PREVIEW_STATE_KEY,
        on_change=_clear_and_change_mode,
        args=(st,),
        disabled=loaded_verified,
        help=(
            "Uses RentCast property records, recorded public sales, and adaptive rental evidence. "
            "A loaded verified analysis is locked to this mode so its evidence cannot be mixed with "
            "the legacy AVM/listing workflow. Use Start New Property before changing modes."
        ),
    )

    if loaded_verified:
        st.info(
            "Verified RentCast intelligence produced the loaded analysis. Recorded-sale and rural-rent "
            "evidence remain locked to the matching decision rules and will be saved to the Team Deal Library."
        )
    elif verified_intelligence_enabled(st):
        st.info(
            "Verified RentCast intelligence is ON. The next pull uses recorded public sales and adaptive "
            "rental verification, with the displayed request budget and hard cap."
        )
    else:
        st.warning(
            "Basic RentCast mode is ON. It uses fewer requests, but value comparables may be listing-based "
            "and are not equivalent to verified closed sales."
        )

    if state.pop("rentcast_preview_mode_changed", False):
        st.caption("The previous calculated evidence was cleared so the two intelligence modes cannot mix.")


def _recorded_result_active(st: Any) -> bool:
    summary = st.session_state.get("auto_arv_summary", {}) or {}
    if isinstance(summary, dict) and summary.get("comp_data_type") == "RentCast public-record closed sales":
        return True
    return any(
        row.get("record_type") == "recorded_sale"
        or _text(row.get("source")).startswith("RentCast Recorded Sale")
        for row in _rows(st.session_state.get("auto_sold_comps"))
    )


def _rural_rent_result_active(st: Any, data: dict[str, Any] | None = None) -> bool:
    data = data or rent_ui_fix._intelligence_data(st)
    if result_uses_verified_intelligence(st.session_state):
        if any(
            [
                bool(data.get("rent_search_trail")),
                bool(data.get("rent_comp_quality_summary")),
                int(float(data.get("verified_rent_comp_count", 0) or 0)) > 0,
                float(data.get("rentcast_rent_avm", 0) or 0) > 0,
            ]
        ):
            return True
    return any(
        row.get("record_type") == "rental_listing"
        or _text(row.get("source")).startswith("RentCast Rental Listing")
        for row in rent_ui_fix._rent_rows(data)
    )


def _auto_save_verified_analysis(st: Any, *args: Any, **kwargs: Any):
    if result_uses_verified_intelligence(st.session_state):
        st.session_state[preview.PREVIEW_ACTIVE_KEY] = True
        st.session_state[MODE_KEY] = MODE_VERIFIED
    return _ORIGINAL_AUTO_SAVE(st, *args, **kwargs)


def _install_auto_save() -> bool:
    library_ui.auto_save_completed_analysis = _auto_save_verified_analysis
    library_ui._rentcast_intelligence_preview_original_auto_save = _ORIGINAL_AUTO_SAVE
    for module_name in (
        "deal_decision_ui",
        "war_room_offer_engine.deal_decision_ui",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.auto_save_completed_analysis = _auto_save_verified_analysis
    # Prevent a later idempotent preview installation from restoring the old
    # preview-only save block.
    preview._install_auto_save_guard = _install_auto_save
    return True


def _extend_deal_library() -> None:
    for key in (
        preview.PREVIEW_ACTIVE_KEY,
        MODE_KEY,
        "rentcast_credit_guard_last_run_stats",
    ):
        if key not in library.PERSISTED_STATE_KEYS:
            library.PERSISTED_STATE_KEYS.append(key)


def install() -> bool:
    if getattr(preview, "_verified_intelligence_mode_lock_installed", False):
        _install_auto_save()
        return True

    preview._verified_mode_original_preview_enabled = _ORIGINAL_PREVIEW_ENABLED
    preview._verified_mode_original_result_marker = _ORIGINAL_RESULT_MARKER
    preview.preview_enabled = verified_intelligence_enabled
    preview._result_with_preview_marker = _mark_verified_result
    preview._preview_mode_changed = _clear_and_change_mode
    preview.render_preview_control = render_verified_intelligence_control
    preview._PREVIEW_RESET_KEYS.add(MODE_KEY)

    comps_ui_fix._recorded_preview_active = _recorded_result_active
    rent_ui_fix._rural_preview_active = _rural_rent_result_active

    _extend_deal_library()
    _install_auto_save()
    preview._verified_intelligence_mode_lock_installed = True
    return True


install()
