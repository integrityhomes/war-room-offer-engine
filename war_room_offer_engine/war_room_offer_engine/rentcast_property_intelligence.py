from __future__ import annotations

import copy
from typing import Any

try:
    import address_rentcast_bridge as bridge
    import data_sources as ds
    import rentcast_auto_enrichment as rentcast
    import rentcast_comp_normalization_fix as normalization
    import rentcast_state_bootstrap as bootstrap
    from rentcast_intelligence_core import INTELLIGENCE_STATE_KEYS, _clean_text, _normalize_address, _number
    from rentcast_listing_normalizers import normalize_rent_comp_intelligent, normalize_value_listing
    from rentcast_property_enrichment import _RESULT_CACHE, enrich_property_with_intelligence
    from rentcast_property_records import _RESPONSE_CACHE, _avm_get_json, property_facts
    from rentcast_recorded_sales import build_recorded_sold_intelligence
except ImportError:
    try:
        from . import address_rentcast_bridge as bridge
        from . import data_sources as ds
        from . import rentcast_auto_enrichment as rentcast
        from . import rentcast_comp_normalization_fix as normalization
        from . import rentcast_state_bootstrap as bootstrap
        from .rentcast_intelligence_core import INTELLIGENCE_STATE_KEYS, _clean_text, _normalize_address, _number
        from .rentcast_listing_normalizers import normalize_rent_comp_intelligent, normalize_value_listing
        from .rentcast_property_enrichment import _RESULT_CACHE, enrich_property_with_intelligence
        from .rentcast_property_records import _RESPONSE_CACHE, _avm_get_json, property_facts
        from .rentcast_recorded_sales import build_recorded_sold_intelligence
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge as bridge
        from war_room_offer_engine import data_sources as ds
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine import rentcast_comp_normalization_fix as normalization
        from war_room_offer_engine import rentcast_state_bootstrap as bootstrap
        from war_room_offer_engine.rentcast_intelligence_core import INTELLIGENCE_STATE_KEYS, _clean_text, _normalize_address, _number
        from war_room_offer_engine.rentcast_listing_normalizers import normalize_rent_comp_intelligent, normalize_value_listing
        from war_room_offer_engine.rentcast_property_enrichment import _RESULT_CACHE, enrich_property_with_intelligence
        from war_room_offer_engine.rentcast_property_records import _RESPONSE_CACHE, _avm_get_json, property_facts
        from war_room_offer_engine.rentcast_recorded_sales import build_recorded_sold_intelligence


_ORIGINAL_BRIDGE_LOOKUP = getattr(
    bridge, "_rentcast_property_intelligence_original_lookup", bridge.lookup_rentcast_with_full_enrichment
)
_ORIGINAL_BOOTSTRAP_HYDRATE = getattr(
    bootstrap, "_rentcast_property_intelligence_original_hydrate", bootstrap.hydrate_rentcast_state
)


def hydrate_intelligence_state(st: Any, result: dict[str, Any]) -> None:
    state = st.session_state
    for key in INTELLIGENCE_STATE_KEYS:
        if key in result:
            state[key] = copy.deepcopy(result.get(key))
    for key in (
        "rent", "rent_source", "rent_confidence", "rent_verification_needed", "rent_comps",
        "rent_comp_count", "rent_comp_average", "rent_comp_median", "rent_low", "rent_high",
        "arv", "arv_source", "arv_confidence", "arv_fallback_reason", "rentcast_sold_comps",
        "rentcast_sold_comp_count", "rentcast_value_comp_count", "auto_sold_comps", "auto_comp_count",
        "auto_arv_summary", "auto_recommended_arv", "auto_low_arv", "auto_conservative_arv",
        "auto_average_arv", "auto_high_arv", "strong_comp_count", "good_comp_count",
        "weak_comp_count", "excluded_comp_count",
    ):
        if key in result:
            state[key] = copy.deepcopy(result.get(key))
    if "rent_comps" in result:
        state["rentcast_rent_comps"] = copy.deepcopy(result.get("rent_comps") or [])
        state["rentcast_rent_comp_count"] = int(result.get("rent_comp_count", 0) or 0)
        state["rentcast_comp_count"] = int(result.get("rent_comp_count", 0) or 0)
    if result.get("arv_source"):
        state["arv_source_used"] = result.get("arv_source")
        state["value_source"] = result.get("arv_source")
    if result.get("rent_requires_human_verification"):
        state["rent_verification_needed"] = "Yes"
    elif int(result.get("verified_rent_comp_count", 0) or 0) >= 3:
        state["rent_verification_needed"] = "No"


def bridge_lookup_with_intelligence(address: str, beds: float = 0, baths: float = 0, sqft: float = 0) -> dict[str, Any]:
    result = _ORIGINAL_BRIDGE_LOOKUP(address, beds=beds, baths=baths, sqft=sqft)
    if not isinstance(result, dict):
        return result
    cached = _RESULT_CACHE.get(_normalize_address(result.get("rentcast_submitted_address") or address), {})
    if cached:
        result = {**result, **copy.deepcopy(cached)}
    try:
        import streamlit as st
        hydrate_intelligence_state(st, result)
    except Exception:
        pass
    return result


def bootstrap_hydrate_with_intelligence(st: Any) -> None:
    _ORIGINAL_BOOTSTRAP_HYDRATE(st)
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    last_pull = st.session_state.get("last_auto_pull", {}) or {}
    source = data if isinstance(data, dict) and any(key in data for key in INTELLIGENCE_STATE_KEYS) else (
        last_pull if isinstance(last_pull, dict) and any(key in last_pull for key in INTELLIGENCE_STATE_KEYS) else {}
    )
    if source:
        hydrate_intelligence_state(st, source)


def _state_value(state: dict[str, Any], key: str) -> tuple[bool, Any]:
    if key in state:
        return True, state.get(key)
    normalized = state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    if isinstance(data, dict) and key in data:
        return True, data.get(key)
    return False, None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _clean_text(value).lower() in {"1", "true", "yes", "y", "required"}


def _extend_deal_library_contract() -> bool:
    try:
        import deal_library as library
    except ImportError:
        try:
            from . import deal_library as library
        except ImportError:
            try:
                from war_room_offer_engine import deal_library as library
            except ImportError:
                return False
    keys = set(INTELLIGENCE_STATE_KEYS) | {
        "rentcast_rent_avm", "rentcast_value_listing_comps", "rentcast_value_listing_comp_count",
        "rentcast_value_listing_median", "verified_sold_comp_count", "verified_rent_comp_count",
        "arv_requires_human_verification", "rent_requires_human_verification",
        "arv_verification_reasons", "rent_verification_reasons",
    }
    persisted = getattr(library, "PERSISTED_STATE_KEYS", None)
    if isinstance(persisted, list):
        for key in sorted(keys):
            if key not in persisted:
                persisted.append(key)
        return True
    return False


def _install_decision_guards() -> bool:
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

    if getattr(logic, "_rentcast_property_intelligence_guard_installed", False):
        return True
    original_rent_verified = logic.rent_verified
    original_sold_count = logic.sold_count
    original_missing_items = logic.missing_items
    logic._rentcast_property_intelligence_original_rent_verified = original_rent_verified
    logic._rentcast_property_intelligence_original_sold_count = original_sold_count
    logic._rentcast_property_intelligence_original_missing_items = original_missing_items

    def rent_verified_guarded(state: dict[str, Any]) -> bool:
        flag_present, flag = _state_value(state, "rent_requires_human_verification")
        if flag_present and _as_bool(flag):
            return False
        count_present, verified_count = _state_value(state, "verified_rent_comp_count")
        if count_present:
            rent_value = _number(state.get("rent") or logic._normalized_data(state).get("rent"))
            return rent_value > 0 and int(_number(verified_count)) >= 3
        return original_rent_verified(state)

    def sold_count_guarded(state: dict[str, Any]) -> int:
        present_state, state_count = _state_value(state, "verified_sold_comp_count")
        if present_state:
            return int(_number(state_count))
        return original_sold_count(state)

    def missing_items_guarded(state: dict[str, Any], strategy: str) -> list[str]:
        missing = list(original_missing_items(state, strategy))
        if logic.is_slow(strategy):
            flag_present, flag = _state_value(state, "rent_requires_human_verification")
            if flag_present and _as_bool(flag):
                missing.append("verified rental comps")
        else:
            flag_present, flag = _state_value(state, "arv_requires_human_verification")
            source = _clean_text(
                state.get("arv_source_used")
                or state.get("value_source")
                or logic._normalized_data(state).get("arv_source")
            ).lower()
            listing_only = any(term in source for term in ["avm", "listing-based", "dates unverified"])
            if (flag_present and _as_bool(flag)) or (listing_only and sold_count_guarded(state) < 3):
                missing.append("verified ARV / recorded sold comps")
        return list(dict.fromkeys(missing))

    logic.rent_verified = rent_verified_guarded
    logic.sold_count = sold_count_guarded
    logic.missing_items = missing_items_guarded
    logic._rentcast_property_intelligence_guard_installed = True
    return True


def install() -> bool:
    if getattr(rentcast, "_rentcast_property_intelligence_installed", False):
        return True
    bridge._rentcast_property_intelligence_original_lookup = _ORIGINAL_BRIDGE_LOOKUP
    bootstrap._rentcast_property_intelligence_original_hydrate = _ORIGINAL_BOOTSTRAP_HYDRATE

    rentcast._get_json = _avm_get_json
    rentcast.normalize_rent_comp = normalize_rent_comp_intelligent
    rentcast.normalize_sold_comp = normalize_value_listing
    rentcast.build_sold_comp_intelligence = build_recorded_sold_intelligence
    rentcast.enrich_property_with_rentcast = enrich_property_with_intelligence

    bridge._property_facts = property_facts
    bridge.enrich_property_with_rentcast = enrich_property_with_intelligence
    bridge.lookup_rentcast_with_full_enrichment = bridge_lookup_with_intelligence
    ds.lookup_rentcast = bridge_lookup_with_intelligence

    bootstrap.build_sold_comp_intelligence = build_recorded_sold_intelligence
    bootstrap.hydrate_rentcast_state = bootstrap_hydrate_with_intelligence

    _install_decision_guards()
    _extend_deal_library_contract()

    reset_keys = getattr(normalization, "_RESET_STATE_KEYS", None)
    if isinstance(reset_keys, set):
        reset_keys.update(INTELLIGENCE_STATE_KEYS)
    rentcast._rentcast_property_intelligence_installed = True
    return True


install()
