from __future__ import annotations

import inspect
import re
from typing import Any


SECTION_OPTIONS = [
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

SECTION_NAMES = {
    "🏠 One-Load": "One-Load",
    "🔎 Pull Data": "Pull Data",
    "🛡️ Protection": "Protection",
    "🏷️ Rent": "Rent",
    "📈 Buyer Demand": "Buyer Demand",
    "📣 Dispo": "Dispo",
    "🛠️ Repairs": "Repairs",
    "🏘️ Comps / ARV": "Comps / ARV",
    "✅ QA / Decision": "QA / Decision",
}

RENDER_SECTION_MAP = {
    "render_one_load_deal_section": "One-Load",
    "render_lead_intake_section": "Pull Data",
    "render_deal_protection_section": "Protection",
    "render_rent_fallback_section": "Rent",
    "render_buyer_demand_section": "Buyer Demand",
    "render_buyer_outreach_section": "Dispo",
    "render_repair_section": "Repairs",
    "render_decision_section": "QA / Decision",
}

QUICK_LINK_PATTERN = re.compile(r"^\[[^\]]*\*\*(.+?)\*\*\]\(#.+\)$")


def active_section(st) -> str:
    selected = st.session_state.get("war_room_active_section", SECTION_OPTIONS[0])
    return SECTION_NAMES.get(str(selected), "One-Load")


def _hidden_return(function_name: str, st):
    if function_name == "render_repair_section":
        return st.session_state.get("repair_media_files", []) or []
    return None


def _render_decision_center(st, ui, original, exit_mode_value: str = "Auto"):
    try:
        from deal_decision_ui import render
    except ImportError:
        try:
            from .deal_decision_ui import render
        except ImportError:
            from war_room_offer_engine.deal_decision_ui import render
    return render(st, ui, original, exit_mode_value)


def _render_comps_only(st, ui):
    try:
        from ui_sections.comps_ui import render_comps_section
    except ImportError:
        try:
            from .ui_sections.comps_ui import render_comps_section
        except ImportError:
            from war_room_offer_engine.ui_sections.comps_ui import render_comps_section
    st.header("🏘️ Comps / ARV")
    render_comps_section(st, ui)
    return st.session_state.get("repair_media_files", []) or []


def _wrap_renderer(namespace: dict[str, Any], function_name: str, st) -> None:
    renderer = namespace.get(function_name)
    if not callable(renderer) or getattr(renderer, "_war_room_single_section", False):
        return

    expected_section = RENDER_SECTION_MAP[function_name]
    original = renderer

    def guarded(*args, **kwargs):
        current = active_section(st)
        st_arg = args[0] if args else st
        ui_arg = args[1] if len(args) > 1 else kwargs.get("ui")
        if function_name == "render_one_load_deal_section" and current == "One-Load":
            exit_value = args[2] if len(args) > 2 else kwargs.get("exit_mode", "Auto")
            return _render_decision_center(st_arg, ui_arg, original, exit_value)
        if function_name == "render_repair_section" and current == "Comps / ARV":
            return _render_comps_only(st_arg, ui_arg)
        if current != expected_section:
            return _hidden_return(function_name, st)
        return original(*args, **kwargs)

    guarded._war_room_single_section = True
    guarded._war_room_original_renderer = original
    namespace[function_name] = guarded


def install_renderer_router_from_caller(st) -> None:
    frame = inspect.currentframe()
    try:
        while frame is not None:
            namespace = frame.f_globals
            if "render_one_load_deal_section" in namespace and "render_repair_section" in namespace:
                for function_name in RENDER_SECTION_MAP:
                    _wrap_renderer(namespace, function_name, st)
                return
            frame = frame.f_back
    finally:
        del frame


def install_workspace() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False

    if getattr(st, "_war_room_single_section_workspace", False):
        return True

    original_title = st.title
    original_markdown = st.markdown
    original_radio = st.radio

    def title_with_workspace(*args, **kwargs):
        st._war_room_workspace_radio_rendered = False
        result = original_title(*args, **kwargs)
        install_renderer_router_from_caller(st)
        return result

    def markdown_with_workspace(body, *args, **kwargs):
        text = str(body or "").strip()
        match = QUICK_LINK_PATTERN.match(text)
        if match and match.group(1) in {
            "One-Load", "Pull Data", "Protection", "Rent", "Buyer Demand",
            "Dispo", "Repairs", "Comps / ARV", "QA / Decision",
        }:
            if not getattr(st, "_war_room_workspace_radio_rendered", False):
                st._war_room_workspace_radio_rendered = True
                st.session_state.setdefault("war_room_active_section", SECTION_OPTIONS[0])
                original_radio(
                    "Open section",
                    SECTION_OPTIONS,
                    key="war_room_active_section",
                    label_visibility="collapsed",
                )
            return None
        return original_markdown(body, *args, **kwargs)

    def radio_with_workspace(label, options, *args, **kwargs):
        if str(label) == "Deal type":
            if active_section(st) != "QA / Decision":
                return st.session_state.get("war_room_exit_mode", "Auto")
            kwargs.setdefault("key", "war_room_exit_mode")
        return original_radio(label, options, *args, **kwargs)

    st.title = title_with_workspace
    st.markdown = markdown_with_workspace
    st.radio = radio_with_workspace
    st._war_room_single_section_workspace = True
    return True


install_workspace()
