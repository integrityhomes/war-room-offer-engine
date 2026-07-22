from __future__ import annotations

from typing import Any

try:
    import deal_decision_logic as logic
    import property_location_guard as location
    import secret_transport_hardening as secret_transport
except ImportError:
    try:
        from . import deal_decision_logic as logic
        from . import property_location_guard as location
        from . import secret_transport_hardening as secret_transport
    except ImportError:
        from war_room_offer_engine import deal_decision_logic as logic
        from war_room_offer_engine import property_location_guard as location
        from war_room_offer_engine import secret_transport_hardening as secret_transport


_ORIGINAL_MISSING_ITEMS = getattr(
    logic,
    "_property_location_original_missing_items",
    logic.missing_items,
)


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on", "required"}


def _property_input(state: dict[str, Any]) -> str:
    return str(
        state.get("decision_property_input")
        or state.get("one_load_property_address")
        or state.get("one_load_listing_url")
        or state.get("requested_property_address")
        or state.get("address")
        or ""
    ).strip()


def missing_items_with_location(
    state: dict[str, Any],
    strategy: str,
) -> list[str]:
    missing = list(_ORIGINAL_MISSING_ITEMS(state, strategy))
    value = _property_input(state)
    complete, _ = location.validate_property_input(value)
    if not complete:
        missing.append("complete property location")
    if _bool(state.get("location_verification_failed")):
        missing.append("verified property location")
    return list(dict.fromkeys(missing))


def _install_start_new_property_hotfix() -> bool:
    # This guard loads before the final Stability v1 wrapper. The hotfix installs
    # only a deferred Streamlit title hook here, then patches the completed wrapper
    # chain on the first application render. That avoids circular startup imports.
    try:
        import start_new_property_reset_hotfix as reset_hotfix
    except ImportError:
        try:
            from . import start_new_property_reset_hotfix as reset_hotfix
        except ImportError:
            from war_room_offer_engine import start_new_property_reset_hotfix as reset_hotfix
    return bool(reset_hotfix.install_deferred_hook())


def install() -> bool:
    # Provider credential hardening is installed explicitly before data_sources and
    # Zillow safe wrappers capture their request functions. Installation is
    # idempotent and raises normally if a required security patch cannot be applied.
    secret_transport.install()
    if not getattr(logic, "_property_location_decision_guard_installed", False):
        logic._property_location_original_missing_items = _ORIGINAL_MISSING_ITEMS
        logic.missing_items = missing_items_with_location
        logic._property_location_decision_guard_installed = True
    _install_start_new_property_hotfix()
    return True


install()
