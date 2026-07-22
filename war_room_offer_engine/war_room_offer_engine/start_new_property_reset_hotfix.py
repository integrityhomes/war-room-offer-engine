from __future__ import annotations

from typing import Any, Callable


PENDING_RESET_KEY = "stability_start_new_property_reset_pending"
_TITLE_HOOK_FLAG = "_start_new_property_reset_title_hook_installed"
_PATCH_FLAG = "_start_new_property_reset_hotfix_installed"


def _load_stability():
    try:
        import production_stability as stability
    except ImportError:
        try:
            from . import production_stability as stability
        except ImportError:
            from war_room_offer_engine import production_stability as stability
    return stability


def request_reset(st: Any) -> None:
    """Schedule the property reset for the beginning of the next rerun.

    Streamlit widgets already exist when the Start New Property button callback is
    handled. Rewriting or restoring any of those keyed values during that same run
    raises StreamlitAPIException. A non-widget pending flag is safe to set here.
    """
    st.session_state[PENDING_RESET_KEY] = True


def install_runtime_patch() -> bool:
    """Move the real reset to the next rerun, before any widgets are created."""
    stability = _load_stability()
    if getattr(stability, _PATCH_FLAG, False):
        stability._patch_loaded_aliases()
        return True

    original_reset = stability.reset_with_stability
    original_render = stability.render_with_stability

    def reset_after_rerun(st: Any) -> None:
        request_reset(st)

    def render_with_pre_widget_reset(
        st: Any,
        ui: Any,
        original_renderer: Callable,
        exit_mode_value: str = "Auto",
    ) -> Any:
        if st.session_state.pop(PENDING_RESET_KEY, False):
            # This now runs at the start of a fresh rerun, before Deal Decision,
            # team identity, or Deal Library widgets are instantiated. The
            # existing Stability v1 reset can therefore clear and restore all
            # property/session fields without violating Streamlit widget rules.
            original_reset(st)
        return original_render(st, ui, original_renderer, exit_mode_value)

    stability.reset_with_stability = reset_after_rerun
    stability.render_with_stability = render_with_pre_widget_reset
    stability._patch_loaded_aliases()
    setattr(stability, _PATCH_FLAG, True)
    return True


def install_deferred_hook() -> bool:
    """Install the runtime patch after the application import chain completes."""
    try:
        import streamlit as st
    except Exception:
        return False
    if getattr(st, _TITLE_HOOK_FLAG, False):
        return True

    original_title = st.title

    def title_with_reset_hotfix(*args: Any, **kwargs: Any):
        install_runtime_patch()
        return original_title(*args, **kwargs)

    st.title = title_with_reset_hotfix
    setattr(st, _TITLE_HOOK_FLAG, True)
    return True


install_deferred_hook()
