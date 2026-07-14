from __future__ import annotations

try:
    from simple_operator_ui_v2 import render_simple_operator_section as render_v2
except ImportError:
    try:
        from .simple_operator_ui_v2 import render_simple_operator_section as render_v2
    except ImportError:
        from war_room_offer_engine.simple_operator_ui_v2 import render_simple_operator_section as render_v2


def _install_negotiation_log_fields(st, ui) -> None:
    if getattr(ui, "_strategy_log_fields_installed", False):
        return
    original = getattr(ui, "build_deal_log_row", None)
    if not callable(original):
        return

    def build_deal_log_row_with_negotiation(*args, **kwargs):
        row = original(*args, **kwargs)
        row.update(
            {
                "deal_strategy": st.session_state.get("simple_deal_strategy", "Auto — Best Exit"),
                "seller_asking_price_simple": st.session_state.get("simple_asking_price", 0),
                "current_negotiated_price": st.session_state.get("simple_negotiated_price", 0),
                "negotiation_status": st.session_state.get("simple_negotiation_status", "Not contacted"),
                "negotiation_notes": st.session_state.get("simple_negotiation_notes", ""),
                "closing_timeline_or_term": st.session_state.get("simple_closing_timeline", ""),
                "other_negotiated_terms": st.session_state.get("simple_other_terms", ""),
            }
        )
        return row

    ui.build_deal_log_row = build_deal_log_row_with_negotiation
    ui._strategy_log_fields_installed = True


def render_simple_operator_section(st, ui, original_renderer, exit_mode: str = "Auto") -> None:
    st.session_state["min_assignment_fee_snapshot"] = float(getattr(ui, "min_assignment_fee", 10000) or 10000)
    st.session_state["exception_assignment_fee_snapshot"] = float(getattr(ui, "exception_assignment_fee", 5000) or 5000)
    st.session_state["slow_flip_rent_multiple_snapshot"] = float(getattr(ui, "slow_flip_rent_multiple", 45) or 45)
    st.session_state["close_title_buffer_snapshot"] = float(getattr(ui, "close_title_buffer", 1500) or 1500)
    st.session_state["target_offer_discount_snapshot"] = float(getattr(ui, "target_offer_discount", 0.85) or 0.85)
    st.session_state["slow_flip_max_offer_cap_snapshot"] = float(getattr(ui, "slow_flip_max_offer_cap", 32000) or 32000)
    st.session_state["slow_flip_first_offer_gap_snapshot"] = float(getattr(ui, "slow_flip_first_offer_gap", 4000) or 4000)
    _install_negotiation_log_fields(st, ui)
    render_v2(st, ui, original_renderer, exit_mode=exit_mode)
