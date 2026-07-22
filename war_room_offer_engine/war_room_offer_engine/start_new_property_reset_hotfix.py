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


def apply_pending_reset(st: Any, reset_fn: Callable[[Any], None]) -> bool:
    """Execute a scheduled reset at the next safe render boundary."""
    if not st.session_state.pop(PENDING_RESET_KEY, False):
        return False
    reset_fn(st)
    return True


def clear_property_state_without_rewriting_preferences(
    state: Any,
    *,
    preserve_current_inputs: bool,
) -> list[str]:
    """Clear property evidence while leaving preserved widget keys untouched.

    Stability v1 already skipped session-preference keys while removing property
    data, but then redundantly wrote those saved values back. Some preferences,
    especially the active workspace selector, are instantiated before the Deal
    Decision Center renders. Streamlit therefore rejects the redundant assignment.

    Preserving a value only requires not deleting it. This implementation never
    rewrites teammate, workspace, search, auto-save, or verified-mode preferences.
    It also leaves current property/price inputs untouched during an automatic
    cross-property cleanup.
    """
    stability = _load_stability()
    if not hasattr(state, "get"):
        return []

    preserve = set(stability._SESSION_PREFERENCE_KEYS)
    if preserve_current_inputs:
        preserve.update(stability._CURRENT_INPUT_KEYS)

    removed: list[str] = []
    for key in list(state.keys()):
        if key in preserve:
            continue
        if stability._is_property_state_key(key):
            state.pop(key, None)
            removed.append(str(key))
    return removed


def reset_property_without_rewriting_preferences(st: Any) -> None:
    """Run the complete property reset without assigning preserved widget keys."""
    stability = _load_stability()
    stability._ORIGINAL_RESET(st)
    clear_property_state_without_rewriting_preferences(
        st.session_state,
        preserve_current_inputs=False,
    )


def install_runtime_patch() -> bool:
    """Move reset to the next rerun and remove every redundant preference write."""
    stability = _load_stability()
    if getattr(stability, _PATCH_FLAG, False):
        stability._patch_loaded_aliases()
        return True

    original_render = stability.render_with_stability

    def reset_after_rerun(st: Any) -> None:
        request_reset(st)

    def render_with_safe_pending_reset(
        st: Any,
        ui: Any,
        original_renderer: Callable,
        exit_mode_value: str = "Auto",
    ) -> Any:
        # Other app controls, including the workspace selector, may already exist
        # on this rerun. The safe reset deletes property keys only and never writes
        # preserved widget values, so it remains valid at this render boundary.
        apply_pending_reset(st, reset_property_without_rewriting_preferences)
        return original_render(st, ui, original_renderer, exit_mode_value)

    stability.clear_property_state = clear_property_state_without_rewriting_preferences
    stability.reset_with_stability = reset_after_rerun
    stability.render_with_stability = render_with_safe_pending_reset
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
