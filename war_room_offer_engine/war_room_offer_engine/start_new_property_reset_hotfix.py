from __future__ import annotations

from typing import Any, Callable

try:
    import property_state_scope as scope
except ImportError:
    try:
        from . import property_state_scope as scope
    except ImportError:
        from war_room_offer_engine import property_state_scope as scope


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
    """Clear property evidence through the authoritative state-scope registry."""
    return scope.clear_property_state(
        state,
        preserve_current_inputs=preserve_current_inputs,
    )


def reset_property_without_rewriting_preferences(st: Any) -> None:
    """Run the complete property reset without assigning preserved widget keys."""
    stability = _load_stability()
    stability._ORIGINAL_RESET(st)
    scope.clear_property_state(
        st.session_state,
        preserve_current_inputs=False,
    )


def _install_scope_aliases(stability: Any) -> None:
    """Expose the authoritative registry through Stability v1 compatibility names."""
    stability._SESSION_PREFERENCE_KEYS = scope.SESSION_PREFERENCE_KEYS
    stability._CURRENT_INPUT_KEYS = scope.CURRENT_INPUT_KEYS
    stability._PROPERTY_PREFIXES = scope.PROPERTY_PREFIXES
    stability._PROPERTY_EXACT_KEYS = scope.PROPERTY_EXACT_KEYS
    stability._is_property_state_key = scope.is_property_state_key
    stability.clear_property_state = clear_property_state_without_rewriting_preferences


def install_runtime_patch() -> bool:
    """Move reset to the next rerun and install complete property-state isolation."""
    stability = _load_stability()
    _install_scope_aliases(stability)
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
