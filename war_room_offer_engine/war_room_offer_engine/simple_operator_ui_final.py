from __future__ import annotations

try:
    from simple_operator_ui_v2 import render_simple_operator_section as render_v2
except ImportError:
    try:
        from .simple_operator_ui_v2 import render_simple_operator_section as render_v2
    except ImportError:
        from war_room_offer_engine.simple_operator_ui_v2 import render_simple_operator_section as render_v2


def render_simple_operator_section(st, ui, original_renderer, exit_mode: str = "Auto") -> None:
    st.session_state["min_assignment_fee_snapshot"] = float(getattr(ui, "min_assignment_fee", 10000) or 10000)
    st.session_state["exception_assignment_fee_snapshot"] = float(getattr(ui, "exception_assignment_fee", 5000) or 5000)
    st.session_state["slow_flip_rent_multiple_snapshot"] = float(getattr(ui, "slow_flip_rent_multiple", 45) or 45)
    st.session_state["close_title_buffer_snapshot"] = float(getattr(ui, "close_title_buffer", 1500) or 1500)
    st.session_state["target_offer_discount_snapshot"] = float(getattr(ui, "target_offer_discount", 0.85) or 0.85)
    st.session_state["slow_flip_max_offer_cap_snapshot"] = float(getattr(ui, "slow_flip_max_offer_cap", 32000) or 32000)
    st.session_state["slow_flip_first_offer_gap_snapshot"] = float(getattr(ui, "slow_flip_first_offer_gap", 4000) or 4000)
    render_v2(st, ui, original_renderer, exit_mode=exit_mode)
