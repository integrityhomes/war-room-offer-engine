from __future__ import annotations

from typing import Any


_HOOK_FLAG = "_app_stability_deferred_hook_installed"
_INSTALLED_FLAG = "_app_stability_runtime_composed"


def _load_modules():
    try:
        import app_stability as stability
        import app_stability_runtime as stability_runtime
        import deal_decision_ui as decision_ui
        import deal_library_ui as library_ui
        import property_location_safety as location_safety
        import rentcast_credit_guard as credit_guard
        import team_offer_integration as team_offer
    except ImportError:
        try:
            from . import app_stability as stability
            from . import app_stability_runtime as stability_runtime
            from . import deal_decision_ui as decision_ui
            from . import deal_library_ui as library_ui
            from . import property_location_safety as location_safety
            from . import rentcast_credit_guard as credit_guard
            from . import team_offer_integration as team_offer
        except ImportError:
            from war_room_offer_engine import app_stability as stability
            from war_room_offer_engine import app_stability_runtime as stability_runtime
            from war_room_offer_engine import deal_decision_ui as decision_ui
            from war_room_offer_engine import deal_library_ui as library_ui
            from war_room_offer_engine import property_location_safety as location_safety
            from war_room_offer_engine import rentcast_credit_guard as credit_guard
            from war_room_offer_engine import team_offer_integration as team_offer
    return (
        stability,
        stability_runtime,
        decision_ui,
        library_ui,
        location_safety,
        credit_guard,
        team_offer,
    )


def install_runtime_composition(st: Any = None) -> bool:
    """Compose stability under the existing location, credit, and team wrappers.

    one_load_sources_safe is imported while One-Load UI modules are still being
    created. Importing the full stability module at that moment creates a circular
    import. This function runs on the first Streamlit title render, after startup
    imports are complete, then explicitly rebuilds the intended wrapper order.
    """
    if st is not None and getattr(st, _INSTALLED_FLAG, False):
        return True

    (
        stability,
        stability_runtime,
        decision_ui,
        library_ui,
        location_safety,
        credit_guard,
        team_offer,
    ) = _load_modules()

    stability_runtime.install()
    stability.install_base()
    stability.install_post_guards()

    # Stable workflow is the innermost application render. Request accounting and
    # duplicate-pull protection wrap it, then the current teammate identity wraps
    # the request guard. The wrappers use these globals at call time, so rewiring
    # is deterministic even though their modules were imported earlier.
    credit_guard._ORIGINAL_DECISION_RENDER = stability.render_stable_operator_workflow
    credit_guard.decision_ui.render = stability.render_stable_operator_workflow
    team_offer._ORIGINAL_DECISION_RENDER = credit_guard.render_with_credit_guard
    decision_ui.render = team_offer.render_decision_with_team_identity

    # Keep the team audit behavior around the newly collapsed Deal Library.
    team_offer._ORIGINAL_LIBRARY_RENDER = stability.render_compact_library
    library_ui.render_deal_library_box = team_offer.render_deal_library_with_identity
    decision_ui.render_deal_library_box = team_offer.render_deal_library_with_identity

    stability.render_compact_credit_panel  # keep explicit reference for audits
    location_safety.render_credit_panel_with_location_guard = stability.render_compact_credit_panel
    credit_guard.render_credit_panel = stability.render_compact_credit_panel

    team_offer._patch_loaded_aliases()
    stability.clean_demo_defaults(getattr(st, "session_state", {}) if st is not None else {})

    if st is not None:
        setattr(st, _INSTALLED_FLAG, True)
    return True


def install_deferred_hook() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False
    if getattr(st, _HOOK_FLAG, False):
        return True

    original_title = st.title

    def title_with_stability(*args: Any, **kwargs: Any):
        install_runtime_composition(st)
        return original_title(*args, **kwargs)

    st.title = title_with_stability
    setattr(st, _HOOK_FLAG, True)
    return True


install_deferred_hook()
