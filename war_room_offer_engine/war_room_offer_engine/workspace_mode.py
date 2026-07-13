from __future__ import annotations

import inspect
from typing import Any, Callable


WORKSPACE_KEY = "_war_room_workspace"
EXIT_MODE_KEY = "_war_room_exit_mode"
DEFAULT_WORKSPACE = "🏠 One-Load"

WORKSPACE_OPTIONS = [
    "🏠 One-Load",
    "🔎 Pull Data",
    "🛡️ Protection",
    "🏷️ Rent",
    "📈 Buyer Demand",
    "📣 Dispo",
    "🛠️ Repairs",
    "🏘️ Comps / ARV",
    "✅ QA / Decision",
]

RENDERER_WORKSPACES = {
    "render_one_load_deal_section": "🏠 One-Load",
    "render_lead_intake_section": "🔎 Pull Data",
    "render_deal_protection_section": "🛡️ Protection",
    "render_rent_fallback_section": "🏷️ Rent",
    "render_buyer_demand_section": "📈 Buyer Demand",
    "render_buyer_outreach_section": "📣 Dispo",
    "render_repair_section": "🛠️ Repairs",
    "render_decision_section": "✅ QA / Decision",
}


def selected_workspace(st) -> str:
    value = str(st.session_state.get(WORKSPACE_KEY) or DEFAULT_WORKSPACE)
    return value if value in WORKSPACE_OPTIONS else DEFAULT_WORKSPACE


def _inside_old_quick_tools() -> bool:
    """Detect the older duplicate quick-tool renderer from realtor_outreach_ui."""
    frame = inspect.currentframe()
    try:
        while frame is not None:
            if frame.f_code.co_name == "_render_quick_tools":
                module_name = str(frame.f_globals.get("__name__", ""))
                if module_name.endswith("realtor_outreach_ui"):
                    return True
            frame = frame.f_back
    finally:
        del frame
    return False


def _render_sidebar_workspace_selector(st, original_markdown, original_radio) -> None:
    st.session_state.setdefault(WORKSPACE_KEY, DEFAULT_WORKSPACE)
    with st.sidebar:
        original_markdown(
            """
            <style>
            div[data-testid="stSidebar"] div[role="radiogroup"] {
                gap: 0.35rem;
            }
            div[data-testid="stSidebar"] div[role="radiogroup"] label {
                border: 1px solid rgba(128,128,128,.30);
                border-radius: .65rem;
                padding: .55rem .65rem;
                background: rgba(128,128,128,.06);
                transition: all .15s ease-in-out;
            }
            div[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
                border-color: #ff4b4b;
                background: rgba(255,75,75,.08);
            }
            div[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
                border-color: #ff4b4b;
                background: rgba(255,75,75,.14);
                font-weight: 750;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        original_radio(
            "Quick Tools",
            WORKSPACE_OPTIONS,
            key=WORKSPACE_KEY,
            help="Choose one workspace. Only that section stays open.",
        )
        st.caption("One workspace stays open at a time.")


def _render_comps_only(st, ui) -> list[Any]:
    try:
        from ui_sections.comps_ui import render_comps_section
    except ImportError:
        try:
            from .ui_sections.comps_ui import render_comps_section
        except ImportError:
            from war_room_offer_engine.ui_sections.comps_ui import render_comps_section

    st.header("🏘️ Comps / ARV")
    st.caption("Review sold comps and establish the ARV without opening the repair workspace.")
    render_comps_section(st, ui)
    return []


def _render_repairs_without_comps(original: Callable[..., Any], *args, **kwargs):
    """Run the repair workspace without its embedded sold-comps section."""
    namespace = getattr(original, "__globals__", {})
    embedded_comps = namespace.get("render_comps_section") if isinstance(namespace, dict) else None
    if not callable(embedded_comps):
        return original(*args, **kwargs)

    namespace["render_comps_section"] = lambda *unused_args, **unused_kwargs: None
    try:
        return original(*args, **kwargs)
    finally:
        namespace["render_comps_section"] = embedded_comps


def _make_workspace_guard(name: str, original: Callable[..., Any]):
    expected_workspace = RENDERER_WORKSPACES[name]

    def guarded(*args, **kwargs):
        st_arg = args[0] if args else None
        if st_arg is None or not hasattr(st_arg, "session_state"):
            return original(*args, **kwargs)

        current = selected_workspace(st_arg)
        if name == "render_repair_section":
            if current == "🏘️ Comps / ARV":
                ui_arg = args[1] if len(args) > 1 else kwargs.get("ui")
                return _render_comps_only(st_arg, ui_arg)
            if current != expected_workspace:
                return []
            return _render_repairs_without_comps(original, *args, **kwargs)

        if current != expected_workspace:
            return None
        return original(*args, **kwargs)

    guarded._war_room_single_workspace_guard = True
    guarded._war_room_original_renderer = original
    guarded.__name__ = getattr(original, "__name__", name)
    return guarded


def _install_workspace_guards_from_caller() -> None:
    """Replace the app's render functions with single-workspace guards."""
    frame = inspect.currentframe()
    try:
        while frame is not None:
            namespace = frame.f_globals
            found = sum(callable(namespace.get(name)) for name in RENDERER_WORKSPACES)
            if found >= 6:
                for name in RENDERER_WORKSPACES:
                    render = namespace.get(name)
                    if not callable(render):
                        continue
                    if getattr(render, "_war_room_single_workspace_guard", False):
                        continue
                    namespace[name] = _make_workspace_guard(name, render)
                return
            frame = frame.f_back
    finally:
        del frame


def install_workspace_mode() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False

    if getattr(st, "_war_room_single_workspace_installed", False):
        return True

    original_title = st.title
    original_markdown = st.markdown
    original_caption = st.caption
    original_divider = st.divider
    original_radio = st.radio

    def markdown_without_old_floating_tools(*args, **kwargs):
        if _inside_old_quick_tools():
            return None
        return original_markdown(*args, **kwargs)

    def caption_without_old_quick_tools(*args, **kwargs):
        if _inside_old_quick_tools():
            return None
        return original_caption(*args, **kwargs)

    def divider_without_old_quick_tools(*args, **kwargs):
        if _inside_old_quick_tools():
            return None
        return original_divider(*args, **kwargs)

    def radio_with_hidden_global_deal_type(label, options, *args, **kwargs):
        if str(label) != "Deal type":
            return original_radio(label, options, *args, **kwargs)

        values = list(options)
        current = str(st.session_state.get(EXIT_MODE_KEY) or (values[0] if values else "Slow Flip Only"))
        if current not in values and values:
            current = values[0]

        if selected_workspace(st) != "✅ QA / Decision":
            st.session_state[EXIT_MODE_KEY] = current
            return current

        if "index" not in kwargs and current in values:
            kwargs["index"] = values.index(current)
        selected = original_radio(label, options, *args, **kwargs)
        st.session_state[EXIT_MODE_KEY] = selected
        return selected

    def title_with_workspace(*args, **kwargs):
        result = original_title(*args, **kwargs)
        _render_sidebar_workspace_selector(st, original_markdown, original_radio)
        _install_workspace_guards_from_caller()
        return result

    st.markdown = markdown_without_old_floating_tools
    st.caption = caption_without_old_quick_tools
    st.divider = divider_without_old_quick_tools
    st.radio = radio_with_hidden_global_deal_type
    st.title = title_with_workspace
    st._war_room_single_workspace_installed = True
    return True


install_workspace_mode()
