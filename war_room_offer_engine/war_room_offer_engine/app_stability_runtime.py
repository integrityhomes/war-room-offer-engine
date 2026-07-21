from __future__ import annotations

from typing import Any

try:
    import app_stability as stability
except ImportError:
    try:
        from . import app_stability as stability
    except ImportError:
        from war_room_offer_engine import app_stability as stability


_EMPTY = [None, "", 0, 0.0, [], {}]


def state_value_with_normalized_fallback(
    state: Any,
    key: str,
    default: Any = None,
) -> Any:
    """Prefer meaningful session state, then meaningful normalized evidence.

    Streamlit keeps historical aliases for many fields. A stale zero or empty list
    must not override the non-empty value returned by the current One-Load record.
    """
    state_value = state.get(key) if hasattr(state, "get") else None
    if state_value not in _EMPTY:
        return state_value
    data_value = stability._normalized_data(state).get(key, default)
    return data_value if data_value not in _EMPTY else state_value if state_value is not None else default


def analysis_evidence_present_without_demo_defaults(state: Any) -> bool:
    """Require provenance before a positive legacy field counts as evidence."""
    if not hasattr(state, "get"):
        return False
    if any(
        [
            bool(state.get("one_load_normalized")),
            bool(state.get("decision_result")),
            bool(state.get(stability.ANALYSIS_RUN_ID_KEY)),
            bool(state.get("rentcast_rent_comps")),
            bool(state.get("auto_sold_comps")),
            bool(state.get("rentcast_submitted_address")),
            bool(state.get("requested_property_address")),
            bool(state.get("resolved_property_address")),
        ]
    ):
        return True

    rent = stability._number(state.get("rent"))
    rent_source = stability._text(state.get("rent_source")).lower()
    rent_provenance = rent > 0 and rent_source not in {
        "",
        "weak",
        "missing",
        "missing / rentcast unavailable",
        "missing / not analyzed",
    }
    arv = stability._number(state.get("arv"))
    arv_source = stability._text(
        state.get("arv_source")
        or state.get("arv_source_used")
        or state.get("value_source")
    ).lower()
    arv_provenance = arv > 0 and arv_source not in {"", "missing", "not enough data"}
    return bool(rent_provenance or arv_provenance)


def install() -> bool:
    stability._state_value = state_value_with_normalized_fallback
    stability._analysis_evidence_present = analysis_evidence_present_without_demo_defaults
    return True


install()
