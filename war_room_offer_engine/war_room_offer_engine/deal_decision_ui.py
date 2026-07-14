from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

try:
    from deal_decision_logic import (
        AUTO, NEGOTIATION_STATUSES, STRATEGIES, build_decision, exit_mode, money,
        number, source_settings,
    )
except ImportError:
    try:
        from .deal_decision_logic import (
            AUTO, NEGOTIATION_STATUSES, STRATEGIES, build_decision, exit_mode, money,
            number, source_settings,
        )
    except ImportError:
        from war_room_offer_engine.deal_decision_logic import (
            AUTO, NEGOTIATION_STATUSES, STRATEGIES, build_decision, exit_mode, money,
            number, source_settings,
        )

try:
    from deal_library_ui import (
        apply_pending_restore,
        auto_save_completed_analysis,
        initialize_deal_library_state,
        load_query_deal_if_requested,
        render_deal_library_box,
    )
except ImportError:
    try:
        from .deal_library_ui import (
            apply_pending_restore,
            auto_save_completed_analysis,
            initialize_deal_library_state,
            load_query_deal_if_requested,
            render_deal_library_box,
        )
    except ImportError:
        from war_room_offer_engine.deal_library_ui import (
            apply_pending_restore,
            auto_save_completed_analysis,
            initialize_deal_library_state,
            load_query_deal_if_requested,
            render_deal_library_box,
        )

try:
    from deal_library_preflight import open_saved_before_paid_pull
except ImportError:
    try:
        from .deal_library_preflight import open_saved_before_paid_pull
    except ImportError:
        from war_room_offer_engine.deal_library_preflight import open_saved_before_paid_pull


SOURCE_OPTIONS = [
    "Zillow / On-Market", "MLS / Agent", "XLeads / Cold Text",
    "Off-Market Seller", "Facebook / Referral", "Other",
]
RESET_KEYS = [
    "decision_property_input", "decision_strategy", "decision_lead_source",
    "decision_asking_price", "decision_current_negotiated_price", "decision_latest_counter",
    "decision_seller_bottom_line", "decision_negotiation_status", "decision_negotiated_with",
    "decision_last_negotiation", "decision_next_follow_up", "decision_negotiation_notes",
    "decision_other_terms", "decision_media", "decision_result", "decision_last_run_at",
    "one_load_normalized", "one_load_property_address", "one_load_listing_url",
    "one_load_asking_price", "address", "city", "state", "zip", "market",
    "asking_price", "contract_price", "rent", "rent_source", "rent_confidence",
    "rent_verification_needed", "rentcast_rent_comps", "rentcast_rent_comp_count",
    "arv", "rentcast_arv", "sheet_arv", "arv_source_used", "arv_confidence",
    "rentcast_value_comps", "rentcast_value_comp_count", "auto_sold_comps",
    "auto_arv_summary", "repairs", "repair_analysis", "recommended_repairs_from_analyzer",
    "repair_source", "repair_notes", "last_source_results", "last_auto_pull",
    "deal_library_deal_id", "deal_library_version", "deal_library_status",
    "deal_library_assigned_to", "deal_library_updated_by", "deal_library_team_notes",
    "deal_library_last_saved_at", "deal_library_loaded_without_api",
    "deal_library_last_message", "deal_library_last_error", "deal_library_force_refresh",
]


def initialize(st) -> None:
    defaults = {
        "decision_property_input": "",
        "decision_strategy": AUTO,
        "decision_lead_source": "Zillow / On-Market",
        "decision_asking_price": 0,
        "decision_current_negotiated_price": 0,
        "decision_latest_counter": 0,
        "decision_seller_bottom_line": 0,
        "decision_negotiation_status": "Not contacted",
        "decision_negotiated_with": "",
        "decision_last_negotiation": "",
        "decision_next_follow_up": "",
        "decision_negotiation_notes": "",
        "decision_other_terms": "",
        "decision_result": {},
        "decision_last_run_at": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if not st.session_state.get("decision_property_input"):
        st.session_state["decision_property_input"] = st.session_state.get("listing_url") or st.session_state.get("address", "")
    if number(st.session_state.get("decision_asking_price")) <= 0:
        ask = number(st.session_state.get("asking_price"))
        if ask > 0 and ask != 35000:
            st.session_state["decision_asking_price"] = int(ask)


def _is_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("http://") or text.startswith("https://") or "www." in text


def _install_log_fields(st, ui) -> None:
    if getattr(ui, "_decision_log_fields_installed", False):
        return
    original = getattr(ui, "build_deal_log_row", None)
    if not callable(original):
        return

    def wrapped(*args, **kwargs):
        row = original(*args, **kwargs)
        row.update({
            "recommended_deal_lane": (st.session_state.get("decision_result") or {}).get("strategy", ""),
            "current_negotiated_price": st.session_state.get("decision_current_negotiated_price", 0),
            "latest_seller_counter": st.session_state.get("decision_latest_counter", 0),
            "seller_bottom_line": st.session_state.get("decision_seller_bottom_line", 0),
            "negotiation_status": st.session_state.get("decision_negotiation_status", ""),
            "negotiated_with": st.session_state.get("decision_negotiated_with", ""),
            "last_negotiation": st.session_state.get("decision_last_negotiation", ""),
            "next_follow_up": st.session_state.get("decision_next_follow_up", ""),
            "negotiation_notes": st.session_state.get("decision_negotiation_notes", ""),
            "other_negotiated_terms": st.session_state.get("decision_other_terms", ""),
            "deal_library_id": st.session_state.get("deal_library_deal_id", ""),
            "team_deal_status": st.session_state.get("deal_library_status", ""),
            "assigned_to": st.session_state.get("deal_library_assigned_to", ""),
            "team_notes": st.session_state.get("deal_library_team_notes", ""),
        })
        return row

    ui.build_deal_log_row = wrapped
    ui._decision_log_fields_installed = True


def _prepare_input(st) -> str:
    value = str(st.session_state.get("decision_property_input", "") or "").strip()
    strategy = st.session_state.get("decision_strategy", AUTO)
    source = st.session_state.get("decision_lead_source", "Zillow / On-Market")
    source_mode, lead_source, lead_type, one_load_source = source_settings(source, strategy)
    st.session_state["source_mode"] = source_mode
    st.session_state["lead_source"] = lead_source
    st.session_state["one_load_lead_type"] = lead_type
    st.session_state["one_load_lead_source"] = one_load_source
    if _is_url(value):
        st.session_state["one_load_input_method"] = "Listing URL"
        st.session_state["one_load_listing_url"] = value
        st.session_state["one_load_property_address"] = ""
    else:
        st.session_state["one_load_input_method"] = "Property address"
        st.session_state["one_load_property_address"] = value
        st.session_state["one_load_listing_url"] = ""
    ask = number(st.session_state.get("decision_asking_price"))
    negotiated = number(st.session_state.get("decision_current_negotiated_price"))
    latest = number(st.session_state.get("decision_latest_counter"))
    bottom = number(st.session_state.get("decision_seller_bottom_line"))
    if ask > 0:
        st.session_state["one_load_asking_price"] = int(ask)
        st.session_state["asking_price"] = int(ask)
    live_price = negotiated or latest or bottom or ask
    st.session_state["contract_price"] = int(live_price) if live_price > 0 else 0
    note = " | ".join(x for x in [
        str(st.session_state.get("decision_negotiation_notes", "") or "").strip(),
        str(st.session_state.get("decision_other_terms", "") or "").strip(),
    ] if x)
    if note:
        existing = str(st.session_state.get("notes", "") or "")
        if note not in existing:
            st.session_state["notes"] = "\n".join(x for x in [existing, note] if x)
    return exit_mode(strategy)


def _analyze_media(st, ui, files: list[Any]) -> None:
    files = files or []
    if not files:
        return
    photos = [f for f in files if str(getattr(f, "name", "")).lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    videos = [f for f in files if str(getattr(f, "name", "")).lower().endswith((".mp4", ".mov", ".m4v", ".avi"))]
    generated = ui.generate_boots_on_ground_notes(photos, videos[0] if videos else None)
    if str(generated or "").strip():
        st.session_state["repair_notes"] = ui.safe_condition_text(generated)
        st.session_state["repair_scope_confidence"] = "Walkthrough" if videos else "Photos only"
        analysis = ui.analyze_repairs(
            notes=st.session_state["repair_notes"],
            sqft=float(st.session_state.get("sqft", 0) or 1000),
            baths=float(st.session_state.get("baths", 0) or 1),
            uploaded_files=files,
            market=st.session_state.get("repair_market", "Central IL"),
            repair_level=st.session_state.get("repair_level", "Rental Ready"),
            contingency_pct=float(st.session_state.get("repair_contingency", 12) or 0) / 100,
            pricing_mode=st.session_state.get("repair_pricing_mode", "Investor standard"),
            repair_scope_confidence=st.session_state.get("repair_scope_confidence", "Unknown"),
            market_labor_cost=st.session_state.get("market_labor_cost", "Unknown"),
            repair_cushion_percent=ui.repair_cushion_percent_value(),
            manual_repair_adjustment=float(st.session_state.get("manual_repair_adjustment", 0) or 0),
            mold_verified=ui.mold_verified_bool(),
        )
        st.session_state["repair_analysis"] = analysis
        repair_number = int(analysis.get("recommended_repair_number", 0) or 0)
        st.session_state["recommended_repairs_from_analyzer"] = repair_number
        st.session_state["repairs"] = repair_number
        st.session_state["repair_source"] = "AI Repair Estimate"


def _run(st, ui, media_files: list[Any]) -> None:
    try:
        from ui_sections import one_load_deal_ui as one_load
    except ImportError:
        try:
            from .ui_sections import one_load_deal_ui as one_load
        except ImportError:
            from war_room_offer_engine.ui_sections import one_load_deal_ui as one_load
    chosen_exit = _prepare_input(st)
    with st.expander("Automatic engine work", expanded=False):
        normalized = one_load._run_one_load(st, ui, None, chosen_exit, True)
    price = (
        number(st.session_state.get("decision_current_negotiated_price"))
        or number(st.session_state.get("decision_latest_counter"))
        or number(st.session_state.get("decision_seller_bottom_line"))
        or number(st.session_state.get("decision_asking_price"))
        or number(st.session_state.get("asking_price"))
    )
    if price > 0:
        st.session_state["contract_price"] = int(price)
    _analyze_media(st, ui, media_files)
    assumptions = one_load._build_assumptions(st, ui)
    wholesale_deal = one_load._build_deal(st, ui, "Wholesale Only")
    engine_result = ui.analyze_deal(wholesale_deal, assumptions)
    decision = build_decision(dict(st.session_state), assumptions, engine_result, st.session_state.get("decision_strategy", AUTO))
    st.session_state["one_load_normalized"] = normalized
    st.session_state["decision_result"] = decision
    st.session_state["decision_engine_result"] = engine_result
    st.session_state["decision_last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.session_state["deal_library_loaded_without_api"] = False
    auto_save_completed_analysis(st)


def _live_decision(st, ui) -> dict[str, Any]:
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    if not normalized:
        return st.session_state.get("decision_result", {}) or {}
    try:
        from ui_sections import one_load_deal_ui as one_load
    except ImportError:
        from war_room_offer_engine.ui_sections import one_load_deal_ui as one_load
    assumptions = one_load._build_assumptions(st, ui)
    engine = st.session_state.get("decision_engine_result", {}) or {}
    decision = build_decision(dict(st.session_state), assumptions, engine, st.session_state.get("decision_strategy", AUTO))
    st.session_state["decision_result"] = decision
    return decision


def _render_decision(st, decision: dict[str, Any]) -> None:
    if not decision:
        st.info("Enter the property, then press Pull Everything & Tell Me.")
        return
    with st.container(border=True):
        label = f"{decision.get('decision')} — {decision.get('strategy')}"
        if decision.get("decision") == "BUY":
            st.success(f"# {label}")
        elif decision.get("decision") == "DO NOT BUY":
            st.error(f"# {label}")
        else:
            st.warning(f"# {label}")
        top = st.columns(5)
        top[0].metric("Starting Offer", money(decision.get("first_offer")))
        top[1].metric("Current Deal Price", money(decision.get("price")))
        top[2].metric("Absolute Maximum", money(decision.get("hard_max")))
        top[3].metric("Room Left" if number(decision.get("room_left")) >= 0 else "Over Maximum", money(abs(number(decision.get("room_left")))))
        top[4].metric("Confidence", decision.get("confidence", "Weak"))
        st.info(decision.get("next_action", ""))
        st.write("**Why:** " + str(decision.get("reason", "")))
        st.caption(str(decision.get("formula", "")))
        second = st.columns(3)
        second[0].metric(decision.get("margin_label", "Projected Margin"), money(decision.get("projected_margin")))
        second[1].metric(decision.get("exit_value_label", "Exit Value"), money(decision.get("exit_value")))
        second[2].metric("Price Source", decision.get("price_source", ""))
        if decision.get("missing"):
            st.warning("Still needed: " + ", ".join(decision["missing"]))
        if decision.get("review_flags"):
            st.warning("Must verify: " + ", ".join(decision["review_flags"]))

    with st.expander("Compare all four deal lanes", expanded=False):
        rows = []
        for row in decision.get("evaluations", []):
            rows.append({
                "Lane": row.get("strategy"), "Decision": row.get("decision"),
                "Starting Offer": money(row.get("first_offer")), "Maximum": money(row.get("hard_max")),
                "Current Price": money(row.get("price")), "Projected Margin": money(row.get("projected_margin")),
                "Reason": row.get("reason"),
            })
        st.dataframe(rows, use_container_width=True)


def _reset(st) -> None:
    for key in RESET_KEYS:
        st.session_state.pop(key, None)


def render(st, ui, original_renderer: Callable, exit_mode_value: str = "Auto") -> None:
    initialize_deal_library_state(st)
    apply_pending_restore(st)
    load_query_deal_if_requested(st)
    initialize(st)
    st.session_state.setdefault("deal_library_force_refresh", False)
    _install_log_fields(st, ui)
    st.header("Deal Decision Center")
    st.caption("Paste one address or listing link. The app pulls everything it can and gives one clear decision.")
    if st.session_state.get("deal_library_loaded_without_api"):
        st.success("Saved deal loaded from the Team Deal Library. No paid property-data credits were used.")
    first = st.columns([2.2, 1.2, 1.1])
    with first[0]:
        st.text_input("Property address or listing link", key="decision_property_input", placeholder="1115 Matson Dr, Marion, VA 24354 or Zillow link")
    with first[1]:
        st.selectbox("Deal Lane", STRATEGIES, key="decision_strategy")
    with first[2]:
        st.selectbox("Lead Source", SOURCE_OPTIONS, key="decision_lead_source")
    prices = st.columns(3)
    prices[0].number_input("Seller Asking Price", min_value=0, step=1000, key="decision_asking_price")
    prices[1].number_input("Current Negotiated Price", min_value=0, step=500, key="decision_current_negotiated_price", help="The price you currently have the deal negotiated to.")
    prices[2].number_input("Latest Seller Counter", min_value=0, step=500, key="decision_latest_counter")
    with st.expander("Negotiation Center", expanded=True):
        n1, n2, n3 = st.columns(3)
        n1.number_input("Seller Bottom-Line Price", min_value=0, step=500, key="decision_seller_bottom_line")
        n2.selectbox("Negotiation Status", NEGOTIATION_STATUSES, key="decision_negotiation_status")
        n3.text_input("Negotiated With", key="decision_negotiated_with", placeholder="Agent or seller name")
        d1, d2 = st.columns(2)
        d1.text_input("Last Negotiation", key="decision_last_negotiation", placeholder="Date/time or short note")
        d2.text_input("Next Follow-Up", key="decision_next_follow_up", placeholder="Date/time or next step")
        t1, t2 = st.columns(2)
        t1.text_area("Negotiation Notes", height=90, key="decision_negotiation_notes")
        t2.text_area("Other Important Terms", height=90, key="decision_other_terms")
    media = st.file_uploader("Optional property photos or walkthrough video", type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"], accept_multiple_files=True, key="decision_media")
    st.checkbox(
        "Refresh live paid data even if this property is already saved",
        key="deal_library_force_refresh",
        help="Leave this off for normal use. Turn it on only when you intentionally want fresh Zillow, RentCast or Apify data.",
    )
    buttons = st.columns([3, 1])
    analyze = buttons[0].button("Pull Everything & Tell Me", type="primary", use_container_width=True)
    reset = buttons[1].button("Start New Property", type="secondary", use_container_width=True)
    if reset:
        _reset(st)
        st.rerun()
    if analyze:
        if not str(st.session_state.get("decision_property_input", "")).strip():
            st.error("Enter a property address or listing link first.")
        else:
            if not st.session_state.get("deal_library_force_refresh", False):
                open_saved_before_paid_pull(st)
            with st.spinner("Pulling property facts, RentCast rents and comps, sold comps, condition, and offer numbers..."):
                _run(st, ui, media or [])
            st.session_state["deal_library_force_refresh"] = False
            st.success("Automatic analysis complete.")
    _render_decision(st, _live_decision(st, ui))
    render_deal_library_box(st)
    with st.expander("Advanced engine controls and full audit details", expanded=False):
        st.caption("Every existing detailed input, formula, comp, override, message, and audit field remains available here.")
        original_renderer(st, ui, exit_mode_value)
