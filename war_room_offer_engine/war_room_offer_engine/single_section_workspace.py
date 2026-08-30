from __future__ import annotations

import inspect
import re
from typing import Any


# Daily work comes first. The underlying section names remain unchanged so the
# stabilized renderers, saved session state, and existing integrations keep the
# same contracts.
SECTION_OPTIONS = [
    "🏠 Analyze Deal",
    "📡 Listing Radar",
    "✅ Decision & Save",
    "🔎 Property Data",
    "🏘️ Comps & Value",
    "🛠️ Repair Estimate",
    "🏷️ Rent & Rent Comps",
    "📈 Buyer Demand",
    "📣 Buyer Outreach",
    "🛡️ Deal Protection",
]

SECTION_NAMES = {
    "🏠 Analyze Deal": "One-Load",
    "📡 Listing Radar": "Listing Radar",
    "✅ Decision & Save": "QA / Decision",
    "🔎 Property Data": "Pull Data",
    "🏘️ Comps & Value": "Comps / ARV",
    "🛠️ Repair Estimate": "Repairs",
    "🏷️ Rent & Rent Comps": "Rent",
    "📈 Buyer Demand": "Buyer Demand",
    "📣 Buyer Outreach": "Dispo",
    "🛡️ Deal Protection": "Protection",
}

# Preserve sessions created by the prior developer-facing navigation labels.
LEGACY_SECTION_ALIASES = {
    "🏠 One-Load": "🏠 Analyze Deal",
    "📡 Listing Radar": "📡 Listing Radar",
    "🔎 Pull Data": "🔎 Property Data",
    "🛡️ Protection": "🛡️ Deal Protection",
    "🏷️ Rent": "🏷️ Rent & Rent Comps",
    "📈 Buyer Demand": "📈 Buyer Demand",
    "📣 Dispo": "📣 Buyer Outreach",
    "🛠️ Repairs": "🛠️ Repair Estimate",
    "🏘️ Comps / ARV": "🏘️ Comps & Value",
    "✅ QA / Decision": "✅ Decision & Save",
}

SECTION_DESCRIPTIONS = {
    "One-Load": "Start here for normal deal work: load one property, verify the evidence, and get the recommended offer path.",
    "Listing Radar": "Review incoming listings and send the right property into the Deal Analyzer.",
    "QA / Decision": "Review the final answer, offer range, risks, and saved deal record before taking action.",
    "Pull Data": "Review or refresh the property facts used by the analysis.",
    "Comps / ARV": "Review sold comps and the value evidence behind the ARV.",
    "Repairs": "Review photos, notes, repair scope, and the repair estimate.",
    "Rent": "Review rent evidence and rent comps, especially when Slow Flip depends on verified rent.",
    "Buyer Demand": "Review buyer-market strength and exit confidence.",
    "Dispo": "Review buyer feedback and outreach tools after the deal is protected appropriately.",
    "Protection": "Review what deal details may be shared before and after the property is under contract.",
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


def _normalize_display_section(value: Any) -> str:
    selected = str(value or "")
    if selected in SECTION_OPTIONS:
        return selected
    return LEGACY_SECTION_ALIASES.get(selected, SECTION_OPTIONS[0])


def active_section(st) -> str:
    selected = _normalize_display_section(st.session_state.get("war_room_active_section", SECTION_OPTIONS[0]))
    return SECTION_NAMES.get(selected, "One-Load")


def render_workspace_selector(st, original_radio) -> None:
    """Render the user-facing work-area picker once per Streamlit rerun.

    The selector keeps every specialist tool available, but puts the three
    normal operator destinations first: Analyze Deal, Listing Radar, and
    Decision & Save. Legacy session labels are migrated before the widget is
    instantiated so existing saved sessions remain usable.
    """
    if getattr(st, "_war_room_workspace_radio_rendered", False):
        return
    st._war_room_workspace_radio_rendered = True

    current = _normalize_display_section(st.session_state.get("war_room_active_section", SECTION_OPTIONS[0]))
    st.session_state["war_room_active_section"] = current
    selected = original_radio(
        "Work area",
        SECTION_OPTIONS,
        key="war_room_active_section",
        help="Start with Analyze Deal for normal property work. Open the evidence tools only when you need to verify or adjust a specific part of the analysis.",
    )
    selected_display = _normalize_display_section(selected or st.session_state.get("war_room_active_section"))
    section_name = SECTION_NAMES.get(selected_display, "One-Load")
    caption = SECTION_DESCRIPTIONS.get(section_name, "")
    if caption and hasattr(st, "caption"):
        st.caption(caption)


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
    st.header("🏘️ Comps & Value")
    render_comps_section(st, ui)
    return st.session_state.get("repair_media_files", []) or []


def _install_listing_radar_bridge() -> None:
    try:
        import listing_radar_native_bridge as bridge
    except ImportError:
        try:
            from . import listing_radar_native_bridge as bridge
        except ImportError:
            from war_room_offer_engine import listing_radar_native_bridge as bridge
    bridge.install()


def _render_listing_radar(st) -> None:
    if getattr(st, "_war_room_listing_radar_rendered", False):
        return
    st._war_room_listing_radar_rendered = True
    _install_listing_radar_bridge()
    try:
        import listing_radar_ui
    except ImportError:
        try:
            from . import listing_radar_ui
        except ImportError:
            from war_room_offer_engine import listing_radar_ui
    listing_radar_ui.render(st)


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
        st._war_room_listing_radar_rendered = False
        result = original_title(*args, **kwargs)
        install_renderer_router_from_caller(st)
        render_workspace_selector(st, original_radio)
        if active_section(st) == "Listing Radar":
            _render_listing_radar(st)
        return result

    def markdown_with_workspace(body, *args, **kwargs):
        text = str(body or "").strip()
        match = QUICK_LINK_PATTERN.match(text)
        if match and match.group(1) in {
            "One-Load", "Listing Radar", "Pull Data", "Protection", "Rent",
            "Buyer Demand", "Dispo", "Repairs", "Comps / ARV", "QA / Decision",
            "Analyze Deal", "Decision & Save", "Property Data", "Comps & Value",
            "Repair Estimate", "Rent & Rent Comps", "Buyer Outreach", "Deal Protection",
        }:
            render_workspace_selector(st, original_radio)
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
