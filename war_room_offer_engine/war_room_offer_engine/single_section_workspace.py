from __future__ import annotations

import inspect
from typing import Any, Callable


TOOL_OPTIONS = [
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

DEFAULT_TOOL = TOOL_OPTIONS[0]


def active_tool(st) -> str:
    selected = str(st.session_state.get("war_room_active_tool", DEFAULT_TOOL) or DEFAULT_TOOL)
    return selected if selected in TOOL_OPTIONS else DEFAULT_TOOL


def _preserve_workspace_state(st) -> None:
    """Keep entered values when their workspace is temporarily not rendered."""
    prefixes = (
        "one_load_",
        "repair_",
        "manual_repair_",
        "manual_rent_",
        "manual_comp_",
        "buyer_",
        "wholesale_",
        "slow_flip_",
        "rent_",
        "apify_",
        "universal_",
        "auto_comp_",
        "listing_",
        "deal_",
    )
    exact_keys = {
        "address",
        "city",
        "state",
        "zip",
        "market",
        "market_type",
        "lead_source",
        "lead_type",
        "source_mode",
        "status",
        "asking_price",
        "contract_price",
        "beds",
        "baths",
        "sqft",
        "taxes",
        "occupancy",
        "livable",
        "arv",
        "rentcast_arv",
        "sheet_arv",
        "manual_arv_override",
        "repairs",
        "notes",
        "owner_name",
        "property_type",
        "year_built",
        "days_on_market",
        "lot_size",
        "contract_status",
        "address_sharing_level",
        "listing_source_sharing_level",
        "exit_strategy_confidence",
        "property_marketability",
        "exit_obstacles",
    }
    for key in list(st.session_state.keys()):
        key_text = str(key)
        if key_text.startswith("_war_room_") or key_text == "war_room_active_tool":
            continue
        if key_text in exact_keys or key_text.startswith(prefixes):
            try:
                st.session_state[key_text] = st.session_state[key_text]
            except Exception:
                # Button-like widgets cannot be assigned. They do not hold deal data.
                pass


def _render_sidebar_workspace_menu(st) -> None:
    with st.sidebar:
        st.divider()
        st.markdown("### Quick Tools")
        st.caption("Open one workspace at a time.")
        st.markdown(
            """
            <style>
            section[data-testid="stSidebar"] div[role="radiogroup"] > label {
                border: 1px solid rgba(128,128,128,.28);
                border-radius: .65rem;
                padding: .55rem .65rem;
                margin: .22rem 0;
                background: rgba(128,128,128,.06);
                font-weight: 650;
            }
            section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
                border-color: #ff4b4b;
                background: rgba(255,75,75,.08);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.radio(
            "Workspace",
            TOOL_OPTIONS,
            key="war_room_active_tool",
            label_visibility="collapsed",
        )
        st.caption("Your entered deal information stays saved while you switch sections.")


def _is_widget_state_order_error(exc: Exception) -> bool:
    text = f"{exc.__class__.__name__}: {exc}".lower()
    return (
        "streamlitapiexception" in text
        or "cannot be modified after the widget with key" in text
        or ("session_state" in text and "after the widget" in text)
    )


def _patch_ui_auto_pull(st, ui) -> None:
    """Preserve the PR #45 safe-rerun behavior for the Pull Data workspace."""
    if ui is None or not callable(getattr(ui, "update_state_from_auto_pull", None)):
        return

    original = getattr(ui, "_war_room_original_auto_pull_update", None)
    if original is None:
        original = ui.update_state_from_auto_pull
        ui._war_room_original_auto_pull_update = original

    pending = st.session_state.pop("_war_room_pending_auto_pull", None)
    if isinstance(pending, dict) and pending:
        original(pending)
        st.session_state["_war_room_auto_pull_notice"] = "Property data was safely applied after the page reran."

    if getattr(ui, "_war_room_safe_auto_pull_installed", False):
        return

    def safe_update(data: dict) -> None:
        try:
            original(data)
        except Exception as exc:
            if not _is_widget_state_order_error(exc):
                raise
            st.session_state["_war_room_pending_auto_pull"] = dict(data or {})
            st.session_state["_war_room_auto_pull_notice"] = "Property data was queued for a safe rerun."
            st.rerun()

    ui.update_state_from_auto_pull = safe_update
    ui._war_room_safe_auto_pull_installed = True


def _load_comps_renderer() -> Callable | None:
    try:
        from ui_sections.comps_ui import render_comps_section

        return render_comps_section
    except ImportError:
        try:
            from .ui_sections.comps_ui import render_comps_section

            return render_comps_section
        except ImportError:
            try:
                from war_room_offer_engine.ui_sections.comps_ui import render_comps_section

                return render_comps_section
            except ImportError:
                return None


def _find_app_namespace() -> dict[str, Any] | None:
    required = {
        "render_one_load_deal_section",
        "render_lead_intake_section",
        "render_deal_protection_section",
        "render_rent_fallback_section",
        "render_buyer_demand_section",
        "render_buyer_outreach_section",
        "render_repair_section",
        "render_decision_section",
    }
    frame = inspect.currentframe()
    try:
        while frame is not None:
            namespace = frame.f_globals
            if required.issubset(namespace.keys()):
                return namespace
            frame = frame.f_back
    finally:
        del frame
    return None


def _install_renderer_guards(st) -> None:
    namespace = _find_app_namespace()
    if namespace is None or namespace.get("_war_room_single_section_workspace_installed"):
        return

    original_one_load = namespace["render_one_load_deal_section"]
    original_pull_data = namespace["render_lead_intake_section"]
    original_protection = namespace["render_deal_protection_section"]
    original_rent = namespace["render_rent_fallback_section"]
    original_buyer_demand = namespace["render_buyer_demand_section"]
    original_dispo = namespace["render_buyer_outreach_section"]
    original_repairs = namespace["render_repair_section"]
    original_decision = namespace["render_decision_section"]
    comps_renderer = _load_comps_renderer()

    def one_load_guard(*args, **kwargs):
        if active_tool(st) == "🏠 One-Load":
            return original_one_load(*args, **kwargs)
        return None

    def pull_data_guard(st_arg, ui_arg, *args, **kwargs):
        if active_tool(st_arg) != "🔎 Pull Data":
            return None
        _patch_ui_auto_pull(st_arg, ui_arg)
        return original_pull_data(st_arg, ui_arg, *args, **kwargs)

    def protection_guard(*args, **kwargs):
        if active_tool(st) == "🛡️ Protection":
            return original_protection(*args, **kwargs)
        return None

    def rent_guard(*args, **kwargs):
        if active_tool(st) == "🏷️ Rent":
            return original_rent(*args, **kwargs)
        return None

    def buyer_demand_guard(*args, **kwargs):
        if active_tool(st) == "📈 Buyer Demand":
            return original_buyer_demand(*args, **kwargs)
        return None

    def dispo_guard(*args, **kwargs):
        if active_tool(st) == "📣 Dispo":
            return original_dispo(*args, **kwargs)
        return None

    def repair_guard(st_arg, ui_arg, *args, **kwargs):
        selected = active_tool(st_arg)
        cached_files = st_arg.session_state.get("_war_room_repair_media_cache", []) or []

        if selected == "🏘️ Comps / ARV":
            if comps_renderer is not None:
                st_arg.header("🏘️ Comps / ARV")
                comps_renderer(st_arg, ui_arg)
            else:
                st_arg.error("The Comps / ARV workspace could not be loaded.")
            return cached_files

        if selected != "🛠️ Repairs":
            return cached_files

        repair_globals = getattr(original_repairs, "__globals__", {})
        original_comps = repair_globals.get("render_comps_section")
        if original_comps is not None:
            repair_globals["render_comps_section"] = lambda *_a, **_k: None
        try:
            uploaded = original_repairs(st_arg, ui_arg, *args, **kwargs)
        finally:
            if original_comps is not None:
                repair_globals["render_comps_section"] = original_comps

        st_arg.session_state["_war_room_repair_media_cache"] = uploaded or []
        return uploaded or []

    def decision_guard(*args, **kwargs):
        if active_tool(st) == "✅ QA / Decision":
            return original_decision(*args, **kwargs)
        return None

    namespace["render_one_load_deal_section"] = one_load_guard
    namespace["render_lead_intake_section"] = pull_data_guard
    namespace["render_deal_protection_section"] = protection_guard
    namespace["render_rent_fallback_section"] = rent_guard
    namespace["render_buyer_demand_section"] = buyer_demand_guard
    namespace["render_buyer_outreach_section"] = dispo_guard
    namespace["render_repair_section"] = repair_guard
    namespace["render_decision_section"] = decision_guard
    namespace["_war_room_single_section_workspace_installed"] = True


def _install_deal_type_visibility_guard(st) -> None:
    if getattr(st, "_war_room_deal_type_visibility_guard", False):
        return

    original_radio = st.radio
    original_caption = st.caption

    def radio_guard(label, options, *args, **kwargs):
        if str(label) == "Deal type":
            key = kwargs.get("key") or "_war_room_exit_mode"
            if active_tool(st) != "✅ QA / Decision":
                current = st.session_state.get(key, options[0])
                if current not in options:
                    current = options[0]
                st.session_state[key] = current
                return current
            kwargs["key"] = key
        return original_radio(label, options, *args, **kwargs)

    def caption_guard(body, *args, **kwargs):
        text = str(body or "")
        if text.startswith("Works for Zillow, MLS, agent leads") and active_tool(st) not in {
            "🏠 One-Load",
            "🔎 Pull Data",
        }:
            return None
        return original_caption(body, *args, **kwargs)

    st.radio = radio_guard
    st.caption = caption_guard
    st._war_room_deal_type_visibility_guard = True


def install() -> bool:
    try:
        import streamlit as st
    except Exception:
        return False

    if getattr(st, "_war_room_single_section_title_hook", False):
        return True

    # Prevent the older anchor-link Quick Tools hook from installing later.
    st._war_room_quick_tools_title_hook = True
    _install_deal_type_visibility_guard(st)
    original_title = st.title

    def title_with_single_workspace(*args, **kwargs):
        result = original_title(*args, **kwargs)
        _preserve_workspace_state(st)
        _render_sidebar_workspace_menu(st)
        _install_renderer_guards(st)
        return result

    st.title = title_with_single_workspace
    st._war_room_single_section_title_hook = True
    return True


install()
