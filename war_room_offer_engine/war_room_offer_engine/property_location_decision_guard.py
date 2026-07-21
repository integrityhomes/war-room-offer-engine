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
        import app_stability_runtime as stability_runtime
        import property_location_safety as location_safety
        import rentcast_credit_guard as credit_guard
    except ImportError:
        try:
            from . import app_stability as stability
            from . import app_stability_runtime as stability_runtime
            from . import property_location_safety as location_safety
            from . import rentcast_credit_guard as credit_guard
        except ImportError:
            from war_room_offer_engine import app_stability as stability
            from war_room_offer_engine import app_stability_runtime as stability_runtime
            from war_room_offer_engine import property_location_safety as location_safety
            from war_room_offer_engine import rentcast_credit_guard as credit_guard

    stability.install_base()
    stability_runtime.install()

    # property_location_safety imports the credit module before this guard loads,
    # so the credit module may have captured the old Deal Decision render even
    # though its install() has not run yet. Point that pending wrapper at the new
    # stable render before the request-counting guard is installed.
    if not getattr(credit_guard.records, "_rentcast_credit_guard_installed", False):
        credit_guard._ORIGINAL_DECISION_RENDER = stability.render_stable_operator_workflow
        credit_guard.decision_ui.render = stability.render_stable_operator_workflow

    # The location-aware credit panel is installed later in one_load_sources_safe.
    # Wrap that installation once so the final compact panel is applied only after
    # both the request guard and location guard have completed their wiring.
    if not getattr(location_safety, "_app_stability_post_guard_hook", False):
        original_install_ui = location_safety.install_ui

        def install_ui_with_stability() -> bool:
            result = original_install_ui()
            stability.install_post_guards()
            return bool(result)

        location_safety.install_ui = install_ui_with_stability
        location_safety._app_stability_post_guard_hook = True
    return True


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
