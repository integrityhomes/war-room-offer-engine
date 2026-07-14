from __future__ import annotations

from datetime import datetime
from typing import Any


LANE_AUTO = "Auto — choose best"
LANE_SLOW_KEEP = "Slow Flip — Keep"
LANE_SLOW_WHOLESALE = "Slow Flip — Wholesale"
LANE_WHOLESALE_MLS = "Wholesale — MLS"
LANE_WHOLESALE_OFF_MARKET = "Wholesale — Off-Market"
LANES = [
    LANE_AUTO,
    LANE_SLOW_KEEP,
    LANE_SLOW_WHOLESALE,
    LANE_WHOLESALE_MLS,
    LANE_WHOLESALE_OFF_MARKET,
]

SOURCE_OPTIONS = [
    "Zillow / on-market listing",
    "MLS / Agent",
    "XLeads / cold text",
    "Off-market seller",
    "Facebook / referral",
    "Other",
]

NEGOTIATION_STATUSES = [
    "Not contacted",
    "Offer ready",
    "Offer sent",
    "Counter received",
    "Negotiating",
    "Verbal agreement",
    "Contract sent",
    "Under contract",
    "Rejected",
    "Dead lead",
]

MAJOR_REVIEW_TERMS = [
    "foundation",
    "structural",
    "condemned",
    "fire damage",
    "tear down",
    "teardown",
    "no plumbing",
    "no water",
    "unsafe electrical",
    "septic failure",
    "sewer failure",
]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in [None, ""]:
            return default
        return float(value)
    except Exception:
        return default


def money(value: Any) -> str:
    return f"${safe_float(value):,.0f}"


def initialize_decision_center_state(st) -> None:
    defaults = {
        "decision_center_lane": LANE_AUTO,
        "decision_center_source": "Zillow / on-market listing",
        "decision_center_address": "",
        "decision_center_listing_url": "",
        "decision_center_asking_price": 0,
        "decision_center_current_negotiated_price": 0,
        "decision_center_latest_counter": 0,
        "decision_center_seller_bottom_line": 0,
        "decision_center_negotiated_with": "",
        "decision_center_negotiation_status": "Not contacted",
        "decision_center_last_negotiation": "",
        "decision_center_next_follow_up": "",
        "decision_center_negotiation_notes": "",
        "decision_center_last_run_at": "",
        "decision_center_result": {},
        "decision_center_normalized": {},
        "decision_center_show_advanced": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

    # Bring a previously imported deal into the simple screen without overwriting
    # negotiation work the user has already entered.
    if not st.session_state.get("decision_center_address") and st.session_state.get("address"):
        st.session_state["decision_center_address"] = st.session_state.get("address", "")
    if not st.session_state.get("decision_center_listing_url") and st.session_state.get("listing_url"):
        st.session_state["decision_center_listing_url"] = st.session_state.get("listing_url", "")
    if safe_float(st.session_state.get("decision_center_asking_price")) <= 0:
        asking = safe_float(st.session_state.get("asking_price"))
        if asking > 0 and asking != 35000:
            st.session_state["decision_center_asking_price"] = int(asking)


def source_is_on_market(source: str) -> bool:
    text = str(source or "").lower()
    return "zillow" in text or "mls" in text or "agent" in text or "on-market" in text


def source_to_one_load(source: str) -> tuple[str, str, str]:
    if source == "Zillow / on-market listing":
        return "On-market listing", "Zillow", "Zillow / Sheet Match"
    if source == "MLS / Agent":
        return "Agent / MLS lead", "MLS", "Zillow / Sheet Match"
    if source == "XLeads / cold text":
        return "Off-market seller lead", "XLeads", "Off-Market / Manual"
    if source == "Off-market seller":
        return "Off-market seller lead", "Seller call", "Off-Market / Manual"
    if source == "Facebook / referral":
        return "Off-market seller lead", "Facebook", "Off-Market / Manual"
    return "Manual quick entry", "Other", "Off-Market / Manual"


def lane_exit_mode(lane: str) -> str:
    if lane in [LANE_SLOW_KEEP, LANE_SLOW_WHOLESALE]:
        return "Slow Flip Only"
    if lane in [LANE_WHOLESALE_MLS, LANE_WHOLESALE_OFF_MARKET]:
        return "Wholesale Only"
    return "Auto"


def current_deal_price(state: dict[str, Any]) -> tuple[float, str]:
    choices = [
        (safe_float(state.get("current_negotiated_price")), "Current negotiated price"),
        (safe_float(state.get("latest_counter")), "Latest counteroffer"),
        (safe_float(state.get("seller_bottom_line")), "Seller bottom line"),
        (safe_float(state.get("asking_price")), "Asking price"),
    ]
    for value, label in choices:
        if value > 0:
            return value, label
    return 0.0, "Missing price"


def _has_major_review_flag(notes: str) -> list[str]:
    text = str(notes or "").lower()
    return [term for term in MAJOR_REVIEW_TERMS if term in text]


def _verified_rent_confidence(state: dict[str, Any]) -> bool:
    confidence = str(state.get("rent_confidence", "") or "").lower()
    comp_count = int(safe_float(state.get("rent_comp_count", 0)))
    verification = str(state.get("rent_verification_needed", "Yes"))
    return (
        safe_float(state.get("rent")) > 0
        and verification != "Yes"
        and ("strong" in confidence or "medium" in confidence or comp_count >= 2)
    )


def _wholesale_data_ready(state: dict[str, Any]) -> tuple[bool, list[str]]:
    missing = []
    if safe_float(state.get("arv")) <= 0:
        missing.append("ARV")
    if str(state.get("arv_confidence", "")).lower() in ["", "not enough data", "weak"]:
        missing.append("verified ARV/comps")
    repair_source = str(state.get("repair_source", "Missing") or "Missing")
    if safe_float(state.get("repairs")) <= 0 and repair_source == "Missing":
        missing.append("repair scope")
    return not missing, missing


def _decision(
    price: float,
    maximum: float,
    expected_spread: float,
    required_spread: float,
    missing: list[str],
    review_flags: list[str],
) -> tuple[str, str]:
    if price <= 0:
        return "HUMAN REVIEW", "A current price is required before the app can make a buy decision."
    if maximum <= 0:
        if missing:
            return "HUMAN REVIEW", "The app cannot calculate a safe maximum until missing information is collected."
        return "DO NOT BUY", "The available numbers do not support a positive maximum purchase price."
    if price > maximum:
        return "DO NOT BUY", f"The current price is {money(price - maximum)} above the absolute maximum. Renegotiate or pass."
    if missing or review_flags:
        reasons = []
        if missing:
            reasons.append("missing " + ", ".join(missing))
        if review_flags:
            reasons.append("review " + ", ".join(review_flags))
        return "HUMAN REVIEW", "Price is within range, but the app still needs you to " + " and ".join(reasons) + "."
    if expected_spread < required_spread:
        return "HUMAN REVIEW", f"The projected spread is only {money(expected_spread)}; normal target is {money(required_spread)}."
    return "BUY", "The current price is within the calculated maximum and the required spread is supported."


def build_lane_evaluations(state: dict[str, Any], result: dict[str, Any], assumptions: Any) -> list[dict[str, Any]]:
    price, price_source = current_deal_price(state)
    asking = safe_float(state.get("asking_price"))
    rent = safe_float(state.get("rent"))
    resale = rent * safe_float(getattr(assumptions, "slow_flip_rent_multiple", 45), 45)
    assignment_target = safe_float(getattr(assumptions, "min_assignment_fee", 10000), 10000)
    exception_fee = safe_float(getattr(assumptions, "exception_assignment_fee", 5000), 5000)
    close_buffer = safe_float(getattr(assumptions, "close_title_buffer", 1500), 1500)
    normal_cap = safe_float(getattr(assumptions, "slow_flip_max_offer_cap", 32000), 32000)
    market_cap = safe_float(getattr(assumptions, "slow_flip_max_buy_price", 0))
    first_offer_gap = safe_float(getattr(assumptions, "slow_flip_first_offer_gap", 4000), 4000)
    rent_formula_max = max(resale - assignment_target - close_buffer, 0)
    cap_candidates = [value for value in [rent_formula_max, normal_cap, market_cap] if value > 0]
    slow_max = min(cap_candidates) if cap_candidates else 0
    slow_start = max(slow_max - first_offer_gap, 0)
    if asking > 0:
        slow_start = min(slow_start, asking)

    notes = " ".join(
        str(state.get(key, "") or "")
        for key in ["notes", "repair_notes", "manual_repair_notes", "negotiation_notes"]
    )
    review_flags = _has_major_review_flag(notes)
    livable = str(state.get("livable", "Unknown") or "Unknown")
    rent_missing = []
    if rent <= 0:
        rent_missing.append("rent")
    if not _verified_rent_confidence(state):
        rent_missing.append("verified rental comps")
    if livable == "Unknown":
        rent_missing.append("livability")
    elif livable == "No":
        review_flags = list(dict.fromkeys(review_flags + ["livability/safety"]))

    keep_spread = max(resale - price - close_buffer, 0) if price > 0 else 0
    keep_decision, keep_reason = _decision(
        price,
        slow_max,
        keep_spread,
        assignment_target,
        list(dict.fromkeys(rent_missing)),
        review_flags,
    )

    slow_wholesale_fee = max(resale - price - close_buffer, 0) if price > 0 else 0
    slow_wholesale_decision, slow_wholesale_reason = _decision(
        price,
        slow_max,
        slow_wholesale_fee,
        assignment_target,
        list(dict.fromkeys(rent_missing)),
        review_flags,
    )
    if slow_wholesale_decision == "HUMAN REVIEW" and not rent_missing and not review_flags and slow_wholesale_fee >= exception_fee:
        slow_wholesale_reason = (
            f"Projected assignment is {money(slow_wholesale_fee)}, below the normal {money(assignment_target)} minimum. "
            "Proceed only with a pre-committed buyer."
        )

    wholesale = result.get("wholesale", {}) if isinstance(result, dict) else {}
    wholesale_max = safe_float(wholesale.get("max_offer"))
    wholesale_start = safe_float(wholesale.get("offer_to_send") or wholesale.get("first_offer"))
    if asking > 0 and wholesale_start > 0:
        wholesale_start = min(wholesale_start, asking)
    buyer_target = safe_float(wholesale.get("buyer_target"))
    wholesale_fee = max(buyer_target - price - close_buffer, 0) if price > 0 else 0
    wholesale_ready, wholesale_missing = _wholesale_data_ready(state)
    if not wholesale_ready:
        wholesale_missing = list(dict.fromkeys(wholesale_missing))
    wholesale_decision, wholesale_reason = _decision(
        price,
        wholesale_max,
        wholesale_fee,
        assignment_target,
        wholesale_missing,
        review_flags,
    )
    if wholesale_decision == "HUMAN REVIEW" and wholesale_ready and not review_flags and wholesale_fee >= exception_fee:
        wholesale_reason = (
            f"Projected assignment is {money(wholesale_fee)}, below the normal {money(assignment_target)} minimum. "
            "Proceed only with a pre-committed buyer."
        )

    common = {
        "current_price": price,
        "price_source": price_source,
    }
    return [
        {
            **common,
            "lane": LANE_SLOW_KEEP,
            "decision": keep_decision,
            "starting_offer": slow_start,
            "absolute_max": slow_max,
            "expected_spread": keep_spread,
            "spread_label": "Gross equity spread",
            "exit_value": resale,
            "exit_value_label": "Estimated owner-finance resale",
            "reason": keep_reason,
            "missing": list(dict.fromkeys(rent_missing)),
            "review_flags": review_flags,
        },
        {
            **common,
            "lane": LANE_SLOW_WHOLESALE,
            "decision": slow_wholesale_decision,
            "starting_offer": slow_start,
            "absolute_max": slow_max,
            "expected_spread": slow_wholesale_fee,
            "spread_label": "Projected assignment",
            "exit_value": resale,
            "exit_value_label": "Slow-flipper resale target",
            "reason": slow_wholesale_reason,
            "missing": list(dict.fromkeys(rent_missing)),
            "review_flags": review_flags,
        },
        {
            **common,
            "lane": LANE_WHOLESALE_MLS,
            "decision": wholesale_decision,
            "starting_offer": wholesale_start,
            "absolute_max": wholesale_max,
            "expected_spread": wholesale_fee,
            "spread_label": "Projected assignment",
            "exit_value": buyer_target,
            "exit_value_label": "Wholesale buyer target",
            "reason": wholesale_reason,
            "missing": wholesale_missing,
            "review_flags": review_flags,
        },
        {
            **common,
            "lane": LANE_WHOLESALE_OFF_MARKET,
            "decision": wholesale_decision,
            "starting_offer": wholesale_start,
            "absolute_max": wholesale_max,
            "expected_spread": wholesale_fee,
            "spread_label": "Projected assignment",
            "exit_value": buyer_target,
            "exit_value_label": "Wholesale buyer target",
            "reason": wholesale_reason,
            "missing": wholesale_missing,
            "review_flags": review_flags,
        },
    ]


def select_recommended_lane(evaluations: list[dict[str, Any]], selected_lane: str, source: str) -> dict[str, Any]:
    if selected_lane != LANE_AUTO:
        return next((row for row in evaluations if row.get("lane") == selected_lane), evaluations[0] if evaluations else {})

    wholesale_lane = LANE_WHOLESALE_MLS if source_is_on_market(source) else LANE_WHOLESALE_OFF_MARKET
    applicable = [
        row
        for row in evaluations
        if row.get("lane") in [LANE_SLOW_KEEP, LANE_SLOW_WHOLESALE, wholesale_lane]
    ]
    rank = {"BUY": 3, "HUMAN REVIEW": 2, "DO NOT BUY": 1}
    applicable.sort(
        key=lambda row: (
            rank.get(row.get("decision", "HUMAN REVIEW"), 0),
            safe_float(row.get("expected_spread")),
            safe_float(row.get("absolute_max")) - safe_float(row.get("current_price")),
        ),
        reverse=True,
    )
    return applicable[0] if applicable else {}


def _state_for_decision(st) -> dict[str, Any]:
    return {
        "asking_price": safe_float(st.session_state.get("decision_center_asking_price")) or safe_float(st.session_state.get("asking_price")),
        "current_negotiated_price": st.session_state.get("decision_center_current_negotiated_price", 0),
        "latest_counter": st.session_state.get("decision_center_latest_counter", 0),
        "seller_bottom_line": st.session_state.get("decision_center_seller_bottom_line", 0),
        "rent": st.session_state.get("rent", 0),
        "rent_confidence": st.session_state.get("rent_confidence", "Weak"),
        "rent_comp_count": st.session_state.get("rentcast_rent_comp_count", 0),
        "rent_verification_needed": st.session_state.get("rent_verification_needed", "Yes"),
        "arv": st.session_state.get("arv", 0),
        "arv_confidence": st.session_state.get("arv_confidence", "Not enough data"),
        "repairs": st.session_state.get("repairs", 0),
        "repair_source": st.session_state.get("repair_source", "Missing"),
        "livable": st.session_state.get("livable", "Unknown"),
        "notes": st.session_state.get("notes", ""),
        "repair_notes": st.session_state.get("repair_notes", ""),
        "manual_repair_notes": st.session_state.get("manual_repair_notes", ""),
        "negotiation_notes": st.session_state.get("decision_center_negotiation_notes", ""),
    }


def _sync_simple_inputs_to_one_load(st) -> None:
    source = st.session_state.get("decision_center_source", SOURCE_OPTIONS[0])
    lead_type, lead_source, source_mode = source_to_one_load(source)
    address = str(st.session_state.get("decision_center_address", "") or "").strip()
    listing_url = str(st.session_state.get("decision_center_listing_url", "") or "").strip()
    asking = int(safe_float(st.session_state.get("decision_center_asking_price", 0)))

    st.session_state["one_load_lead_type"] = lead_type
    st.session_state["one_load_lead_source"] = lead_source
    st.session_state["source_mode"] = source_mode
    st.session_state["one_load_property_address"] = address
    st.session_state["one_load_listing_url"] = listing_url
    st.session_state["one_load_input_method"] = "Listing URL" if listing_url else "Property address"
    st.session_state["one_load_asking_price"] = asking
    if address:
        st.session_state["address"] = address
    if listing_url:
        st.session_state["listing_url"] = listing_url
    if asking > 0:
        st.session_state["asking_price"] = asking


def _run_automatic_analysis(st, ui, one_load_module) -> None:
    _sync_simple_inputs_to_one_load(st)
    lane = st.session_state.get("decision_center_lane", LANE_AUTO)
    exit_mode = lane_exit_mode(lane)
    normalized = one_load_module._run_one_load(
        st,
        ui,
        csv_record=None,
        exit_mode=exit_mode,
        overwrite_demo_values=True,
    )

    negotiated = safe_float(st.session_state.get("decision_center_current_negotiated_price", 0))
    latest_counter = safe_float(st.session_state.get("decision_center_latest_counter", 0))
    seller_bottom = safe_float(st.session_state.get("decision_center_seller_bottom_line", 0))
    analysis_price = negotiated or latest_counter or seller_bottom or safe_float(st.session_state.get("asking_price", 0))
    if analysis_price > 0:
        st.session_state["contract_price"] = int(analysis_price)

    assumptions = one_load_module._build_assumptions(st, ui)
    deal = one_load_module._build_deal(st, ui, exit_mode)
    deal.rent_source = str(st.session_state.get("rent_source", "Missing / RentCast unavailable"))
    deal.rent_confidence = str(st.session_state.get("rent_confidence", "Weak"))
    deal.rent_verification_needed = str(st.session_state.get("rent_verification_needed", "Yes"))
    result = ui.analyze_deal(deal, assumptions)

    st.session_state["decision_center_result"] = result
    st.session_state["decision_center_normalized"] = normalized
    st.session_state["decision_center_last_run_at"] = datetime.now().strftime("%Y-%m-%d %I:%M %p")


def _render_decision_banner(st, row: dict[str, Any]) -> None:
    decision = row.get("decision", "HUMAN REVIEW")
    if decision == "BUY":
        st.success(f"# ✅ BUY\n### Best lane: {row.get('lane', '')}")
    elif decision == "DO NOT BUY":
        st.error(f"# ⛔ DO NOT BUY\n### At the current price — {row.get('lane', '')}")
    else:
        st.warning(f"# ⚠️ HUMAN REVIEW\n### Best current lane: {row.get('lane', '')}")


def _next_action(row: dict[str, Any]) -> str:
    decision = row.get("decision")
    price = safe_float(row.get("current_price"))
    maximum = safe_float(row.get("absolute_max"))
    start = safe_float(row.get("starting_offer"))
    if decision == "BUY":
        if price <= 0:
            return "Enter the current negotiated price."
        if price < maximum:
            return f"Keep negotiating. Do not exceed {money(maximum)}."
        return f"At the maximum. Do not increase beyond {money(maximum)}."
    if decision == "DO NOT BUY":
        if maximum > 0:
            return f"Renegotiate to {money(maximum)} or less. A fresh starting offer would be {money(start)}."
        return "Pass unless missing information materially changes the numbers."
    missing = row.get("missing", []) or []
    flags = row.get("review_flags", []) or []
    if missing:
        return "Verify " + ", ".join(missing) + " before committing."
    if flags:
        return "Get human review for " + ", ".join(flags) + "."
    return "Review the detailed assumptions before committing."


def _render_lane_table(st, evaluations: list[dict[str, Any]], source: str) -> None:
    wholesale_lane = LANE_WHOLESALE_MLS if source_is_on_market(source) else LANE_WHOLESALE_OFF_MARKET
    rows = [row for row in evaluations if row.get("lane") in [LANE_SLOW_KEEP, LANE_SLOW_WHOLESALE, wholesale_lane]]
    st.markdown("### All Applicable Exit Lanes")
    st.dataframe(
        [
            {
                "Lane": row.get("lane"),
                "Decision": row.get("decision"),
                "Starting Offer": money(row.get("starting_offer")),
                "Absolute Max": money(row.get("absolute_max")),
                row.get("spread_label", "Spread"): money(row.get("expected_spread")),
                row.get("exit_value_label", "Exit Value"): money(row.get("exit_value")),
            }
            for row in rows
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_simple_decision_center(st, ui, one_load_module, original_renderer, exit_mode: str = "Auto") -> None:
    initialize_decision_center_state(st)

    st.header("🏠 Deal Decision Center")
    st.caption(
        "Enter the deal once. The app pulls every connected source, compares the applicable exit lanes, "
        "and tells you BUY, DO NOT BUY, or HUMAN REVIEW."
    )

    top = st.columns([1.1, 1.1, 1.8])
    with top[0]:
        st.selectbox("Deal lane", LANES, key="decision_center_lane")
    with top[1]:
        st.selectbox("Lead source", SOURCE_OPTIONS, key="decision_center_source")
    with top[2]:
        st.text_input("Property address", key="decision_center_address", placeholder="1115 Matson Dr, Marion, VA 24354")

    second = st.columns([2, 1, 1])
    with second[0]:
        st.text_input("Zillow / MLS listing link", key="decision_center_listing_url")
    with second[1]:
        st.number_input("Asking price", min_value=0, step=1000, key="decision_center_asking_price")
    with second[2]:
        st.number_input(
            "Current negotiated price",
            min_value=0,
            step=500,
            key="decision_center_current_negotiated_price",
            help="This is the price the BUY / DO NOT BUY decision is judging.",
        )

    run_cols = st.columns([2, 1])
    with run_cols[0]:
        run_clicked = st.button("🚀 Pull Everything & Tell Me", type="primary", use_container_width=True)
    with run_cols[1]:
        last_run = st.session_state.get("decision_center_last_run_at", "")
        st.caption(f"Last full analysis: {last_run or 'Not run yet'}")

    if run_clicked:
        has_address = bool(str(st.session_state.get("decision_center_address", "") or "").strip())
        has_url = bool(str(st.session_state.get("decision_center_listing_url", "") or "").strip())
        if not has_address and not has_url:
            st.error("Enter the property address or listing link first.")
        else:
            with st.spinner("Pulling property facts, rent, rental comps, value, sold comps, taxes, contacts, and deal math..."):
                _run_automatic_analysis(st, ui, one_load_module)
            st.rerun()

    result = st.session_state.get("decision_center_result", {}) or {}
    if result:
        assumptions = one_load_module._build_assumptions(st, ui)
        evaluations = build_lane_evaluations(_state_for_decision(st), result, assumptions)
        recommended = select_recommended_lane(
            evaluations,
            st.session_state.get("decision_center_lane", LANE_AUTO),
            st.session_state.get("decision_center_source", SOURCE_OPTIONS[0]),
        )
        _render_decision_banner(st, recommended)

        metrics = st.columns(5)
        metrics[0].metric("Starting offer", money(recommended.get("starting_offer", 0)))
        metrics[1].metric("Current deal price", money(recommended.get("current_price", 0)))
        metrics[2].metric("Absolute maximum", money(recommended.get("absolute_max", 0)))
        room = safe_float(recommended.get("absolute_max")) - safe_float(recommended.get("current_price"))
        metrics[3].metric("Room left", money(max(room, 0)), delta=(f"{money(abs(room))} over max" if room < 0 else None), delta_color="inverse")
        metrics[4].metric(recommended.get("spread_label", "Expected spread"), money(recommended.get("expected_spread", 0)))

        st.info(f"**Why:** {recommended.get('reason', '')}")
        st.markdown(f"### Next action: {_next_action(recommended)}")

        support = st.columns(5)
        support[0].metric("Supported rent", money(st.session_state.get("rent", 0)))
        support[1].metric("Rental comps", int(safe_float(st.session_state.get("rentcast_rent_comp_count", 0))))
        support[2].metric("ARV / value", money(st.session_state.get("arv", 0)))
        support[3].metric("Sold comps", int(safe_float(st.session_state.get("rentcast_value_comp_count", st.session_state.get("auto_comp_count", 0)))))
        support[4].metric("Repairs reference", money(st.session_state.get("repairs", 0)))
        st.caption(
            "Slow Flip lanes use repairs as condition/livability information, not a dollar-for-dollar rehab deduction. "
            "Wholesale lanes continue using repair costs in buyer and offer math."
        )

        _render_lane_table(st, evaluations, st.session_state.get("decision_center_source", SOURCE_OPTIONS[0]))
    else:
        st.info("Enter the address or listing link, then click **Pull Everything & Tell Me**.")

    st.divider()
    st.markdown("## 🤝 Negotiation Center")
    st.caption("Update these fields as the seller or agent moves. The decision above recalculates against the latest price automatically.")
    n1, n2, n3, n4 = st.columns(4)
    with n1:
        st.number_input("Latest counteroffer", min_value=0, step=500, key="decision_center_latest_counter")
        st.selectbox("Negotiation status", NEGOTIATION_STATUSES, key="decision_center_negotiation_status")
    with n2:
        st.number_input("Seller's bottom line", min_value=0, step=500, key="decision_center_seller_bottom_line")
        st.text_input("Negotiated with", key="decision_center_negotiated_with", placeholder="Agent or seller name")
    with n3:
        st.text_input("Last negotiation", key="decision_center_last_negotiation", placeholder="Date / time")
        st.text_input("Next follow-up", key="decision_center_next_follow_up", placeholder="Date / time")
    with n4:
        st.text_area("Negotiation notes", height=105, key="decision_center_negotiation_notes")

    if result:
        assumptions = one_load_module._build_assumptions(st, ui)
        evaluations = build_lane_evaluations(_state_for_decision(st), result, assumptions)
        recommended = select_recommended_lane(
            evaluations,
            st.session_state.get("decision_center_lane", LANE_AUTO),
            st.session_state.get("decision_center_source", SOURCE_OPTIONS[0]),
        )
        price = safe_float(recommended.get("current_price"))
        maximum = safe_float(recommended.get("absolute_max"))
        if price > 0 and maximum > 0:
            if price < maximum:
                st.success(f"Still within buy range. You have {money(maximum - price)} left before the absolute maximum.")
            elif price == maximum:
                st.warning(f"At the absolute maximum of {money(maximum)}. Do not increase.")
            else:
                st.error(f"Current price is {money(price - maximum)} above the maximum. Renegotiate or pass.")

    with st.expander("What was pulled automatically?", expanded=False):
        st.write(
            {
                "Address submitted": st.session_state.get("rentcast_submitted_address", st.session_state.get("address", "")),
                "Property facts": "Pulled" if st.session_state.get("beds") and st.session_state.get("sqft") else "Missing",
                "RentCast rent": money(st.session_state.get("rent", 0)),
                "RentCast rental comps": int(safe_float(st.session_state.get("rentcast_rent_comp_count", 0))),
                "Rent confidence": st.session_state.get("rent_confidence", "Unknown"),
                "ARV/value source": st.session_state.get("arv_source_used", st.session_state.get("value_source", "Missing")),
                "ARV confidence": st.session_state.get("arv_confidence", "Not enough data"),
                "Sold comps": int(safe_float(st.session_state.get("rentcast_value_comp_count", st.session_state.get("auto_comp_count", 0)))),
                "Repair source": st.session_state.get("repair_source", "Missing"),
                "Agent": st.session_state.get("listing_agent_name", ""),
                "Brokerage": st.session_state.get("listing_brokerage", ""),
                "Taxes": money(st.session_state.get("taxes", 0)),
            }
        )

    st.toggle("Show advanced One-Load inputs and detailed tools", key="decision_center_show_advanced")
    if st.session_state.get("decision_center_show_advanced"):
        st.divider()
        original_renderer(st, ui, exit_mode)
