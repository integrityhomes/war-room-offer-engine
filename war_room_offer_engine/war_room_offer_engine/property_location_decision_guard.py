from __future__ import annotations

from typing import Any

try:
    import deal_decision_logic as logic
    import property_location_guard as location
except ImportError:
    try:
        from . import deal_decision_logic as logic
        from . import property_location_guard as location
    except ImportError:
        from war_room_offer_engine import deal_decision_logic as logic
        from war_room_offer_engine import property_location_guard as location


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


def _install_stability_base() -> bool:
    try:
        import app_stability as stability
    except ImportError:
        try:
            from . import app_stability as stability
        except ImportError:
            from war_room_offer_engine import app_stability as stability
    return bool(stability.install_base())


def install() -> bool:
    if not getattr(logic, "_property_location_decision_guard_installed", False):
        logic._property_location_original_missing_items = _ORIGINAL_MISSING_ITEMS
        logic.missing_items = missing_items_with_location
        logic._property_location_decision_guard_installed = True
    # This module is loaded after verified-intelligence dispatch and before the
    # request-counting and team-identity wrappers. Installing the stable base UI
    # here gives every later safety wrapper one clean render target.
    _install_stability_base()
    return True


install()
