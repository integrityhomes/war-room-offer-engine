from __future__ import annotations

from typing import Any, Callable

try:
    import simple_operator_ui as base
    from strategy_decision import (
        NEGOTIATION_STATUSES,
        STRATEGIES,
        exit_mode_for_strategy,
        is_slow_flip,
        is_wholesale,
        money,
        negotiation_position,
        number,
        source_mode_for_strategy,
    )
except ImportError:
    try:
        from . import simple_operator_ui as base
        from .strategy_decision import (
            NEGOTIATION_STATUSES,
            STRATEGIES,
            exit_mode_for_strategy,
            is_slow_flip,
            is_wholesale,
            money,
            negotiation_position,
            number,
            source_mode_for_strategy,
        )
    except ImportError:
        from war_room_offer_engine import simple_operator_ui as base
        from war_room_offer_engine.strategy_decision import (
            NEGOTIATION_STATUSES,
            STRATEGIES,
            exit_mode_for_strategy,
            is_slow_flip,
            is_wholesale,
            money,
            negotiation_position,
            number,
            source_mode_for_strategy,
        )


EXTRA_RESET_KEYS = [
    "simple_deal_strategy",
    "simple_negotiated_price",
    "simple_negotiation_status",
    "simple_negotiation_notes",
    "simple_closing_timeline",
    "simple_other_terms",
    "simple_last_strategy",
]


def _state(st) -> dict[str, Any]:
    return dict(st.session_state)


def _actual_missing(st, normalized: dict[str, Any], strategy: str, position: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(st.session_state.get("address", "") or "").strip():
        missing.append("property address")
    if number(st.session_state.get("arv", 0)) <= 0:
        missing.append("value / ARV")
    if is_slow_flip(strategy):
        if number(st.session_state.get("rent", 0)) <= 0:
            missing.append("verified rent")
        if int(number(st.session_state.get("rentcast_rent_comp_count", 0))) < 1 and "strong" not in str(st.session_state.get("rent_confidence", "")).lower():
            missing.append("rental comps")
    if is_wholesale(strategy):
        repair_source = str(st.session_state.get("repair_source", "Missing") or "Missing")
        repair_notes = str(st.session_state.get("repair_notes", "") or "").strip()
        if number(st.session_state.get("repairs", 0)) <= 0 and repair_source == "Missing" and not repair_notes:
            missing.append("repair scope")
    if number(position.get("hard_max", 0)) <= 0:
        missing.append("usable maximum offer")
    return list(dict.fromkeys(missing))


def build_strategy_operator_decision(st, normalized: dict[str, Any]) -> dict[str, Any]:
    strategy = str(st.session_state.get("simple_deal_strategy", "Auto — Best Exit") or "Auto — Best Exit")
    position = negotiation_position(_state(st), normalized, strategy)
    hard_max = number(position.get("hard_max", 0))
    first_offer = number(position.get("first_offer", 0))
    asking = number(position.get("asking_price", 0))
    negotiated = number(position.get("negotiated_price", 0))
    price_tested = number(position.get("price_tested", 0))
    rent = number(st.session_state.get("rent", 0))
    arv = number(st.session_state.get("arv", 0))
    repairs = number(st.session_state.get("repairs", 0))
    rent_comps = int(number(st.session_state.get("rentcast_rent_comp_count", 0)))
    sold_comps = max(
        int(number(st.session_state.get("rentcast_value_comp_count", 0))),
        int(number(st.session_state.get("auto_comp_count", 0))),
    )
    rent_confidence = str(st.session_state.get("rent_confidence", normalized.get("rent_confidence", "Weak")) or "Weak")
    arv_confidence = str(st.session_state.get("arv_confidence", "Not enough data") or "Not enough data")
    arv_source = str(st.session_state.get("arv_source_used", normalized.get("arv_source", "Missing")) or "Missing")
    severe_condition = base._has_severe_condition_risk(st)
    livable = str(st.session_state.get("livable", "Unknown") or "Unknown")
    missing = _actual_missing(st, normalized, strategy, position)

    if missing:
        verdict = "NEEDS MORE INFORMATION"
        verdict_type = "warning"
    elif severe_condition or livable == "No":
        verdict = "REVIEW BEFORE BUYING"
        verdict_type = "warning"
    elif hard_max <= 0:
        verdict = "DO NOT BUY"
        verdict_type = "error"
    elif price_tested > hard_max > 0:
        verdict = f"BUY ONLY AT OR BELOW {money(hard_max)}"
        verdict_type = "warning"
    else:
        verdict = "BUY"
        verdict_type = "success"

    confidence_points = 0
    if arv > 0:
        confidence_points += 1
    if sold_comps >= 3 or arv_confidence.lower() == "strong":
        confidence_points += 2
    elif sold_comps > 0 or arv_confidence.lower() in ["medium", "avm only"]:
        confidence_points += 1
    if is_slow_flip(strategy):
        if rent > 0:
            confidence_points += 1
        if rent_comps >= 3 or "strong" in rent_confidence.lower():
            confidence_points += 2
        elif rent_comps > 0:
            confidence_points += 1
    if is_wholesale(strategy) and (repairs > 0 or str(st.session_state.get("repair_source", "")) != "Missing"):
        confidence_points += 1
    if not severe_condition and livable != "No":
        confidence_points += 1
    if not missing:
        confidence_points += 1
    confidence = "Strong" if confidence_points >= 6 else "Medium" if confidence_points >= 3 else "Weak"
    if verdict in ["NEEDS MORE INFORMATION", "REVIEW BEFORE BUYING"]:
        confidence = "Weak"

    reasons: list[str] = []
    if negotiated > 0:
        reasons.append(
            f"You have the deal negotiated to {money(negotiated)}; the do-not-exceed price for {strategy} is {money(hard_max)}."
        )
    elif asking > 0:
        reasons.append(f"The asking price is {money(asking)}; the do-not-exceed price for {strategy} is {money(hard_max)}.")
    else:
        reasons.append(f"The strategy produced a starting offer of {money(first_offer)} and a maximum of {money(hard_max)}.")

    if is_slow_flip(strategy):
        reasons.append(
            f"Rent support is {money(rent)}/month using {rent_comps} RentCast rental comp(s) with {rent_confidence} confidence."
        )
        reasons.append(position.get("formula", ""))
        if repairs > 0:
            reasons.append(
                f"The condition analyzer shows {money(repairs)} in retail-style work. For this slow-flip strategy it is treated as a warning, not automatically deducted dollar-for-dollar."
            )
    else:
        reasons.append(
            f"Wholesale underwriting uses {money(arv)} value, {money(repairs)} repairs, buyer percentage, assignment fee, and closing buffer."
        )
        reasons.append(position.get("formula", ""))

    reasons.append(f"Value / ARV is {money(arv)} from {arv_source} with {arv_confidence} confidence and {sold_comps} sold comp(s).")
    if severe_condition or livable == "No":
        reasons.append("A major safety or livability concern must be verified before buying.")
    if missing:
        reasons.append("Still missing: " + ", ".join(missing) + ".")

    return {
        "strategy": strategy,
        "verdict": verdict,
        "verdict_type": verdict_type,
        "confidence": confidence,
        "asking": asking,
        "negotiated": negotiated,
        "first_offer": first_offer,
        "hard_max": hard_max,
        "room_left": number(position.get("room_left", 0)),
        "seller_drop_needed": number(position.get("seller_drop_needed", 0)),
        "position": position.get("position", ""),
        "next_action": position.get("next_action", ""),
        "projected_margin": number(position.get("projected_margin", 0)),
        "margin_label": position.get("margin_label", "Projected margin"),
        "rent": rent,
        "rent_comps": rent_comps,
        "rent_confidence": rent_confidence,
        "arv": arv,
        "sold_comps": sold_comps,
        "arv_source": arv_source,
        "arv_confidence": arv_confidence,
        "repairs": repairs,
        "repair_source": st.session_state.get("repair_source", "Missing"),
        "missing": missing,
        "reasons": [reason for reason in reasons if str(reason or "").strip()][:6],
    }


def render_strategy_decision(st, normalized: dict[str, Any]) -> None:
    decision = build_strategy_operator_decision(st, normalized)
    st.markdown("## Deal Decision")
    with st.container(border=True):
        if decision["verdict_type"] == "success":
            st.success(f"# {decision['verdict']}")
        elif decision["verdict_type"] == "error":
            st.error(f"# {decision['verdict']}")
        else:
            st.warning(f"# {decision['verdict']}")

        top = st.columns(5)
        top[0].metric("Strategy", decision["strategy"])
        top[1].metric("Starting Offer", money(decision["first_offer"]))
        top[2].metric("Negotiated Price", money(decision["negotiated"]) if decision["negotiated"] else "Not entered")
        top[3].metric("Do Not Exceed", money(decision["hard_max"]))
        top[4].metric("Confidence", decision["confidence"])

        st.info(decision["next_action"])

        negotiation = st.columns(4)
        negotiation[0].metric("Seller Asking", money(decision["asking"]))
        negotiation[1].metric("Negotiation Position", decision["position"])
        negotiation[2].metric(
            "Room Left" if decision["room_left"] >= 0 else "Over Maximum",
            money(abs(decision["room_left"])),
        )
        negotiation[3].metric(decision["margin_label"], money(decision["projected_margin"]))

        st.markdown("**Why the app made this decision**")
        for reason in decision["reasons"]:
            st.write(f"• {reason}")

        with st.expander("Automatic data collected", expanded=False):
            data = st.columns(5)
            data[0].metric("Rent", money(decision["rent"]))
            data[1].metric("Rental Comps", decision["rent_comps"])
            data[2].metric("Value / ARV", money(decision["arv"]))
            data[3].metric("Sold Comps", decision["sold_comps"])
            data[4].metric("Condition Estimate", money(decision["repairs"]))
            st.write(
                {
                    "Rent confidence": decision["rent_confidence"],
                    "ARV source": decision["arv_source"],
                    "ARV confidence": decision["arv_confidence"],
                    "Condition source": decision["repair_source"],
                    "Negotiation status": st.session_state.get("simple_negotiation_status", "Not contacted"),
                    "Negotiation notes": st.session_state.get("simple_negotiation_notes", ""),
                    "Closing timeline / terms": st.session_state.get("simple_closing_timeline", ""),
                    "Other terms": st.session_state.get("simple_other_terms", ""),
                }
            )


def _prepare_strategy_input(st, quick_input: str, strategy: str, asking: float, negotiated: float) -> str:
    source_mode, lead_source, lead_type = source_mode_for_strategy(strategy)
    st.session_state["source_mode"] = source_mode
    st.session_state["lead_source"] = lead_source
    st.session_state["one_load_lead_type"] = lead_type
    st.session_state["simple_last_strategy"] = strategy

    is_url = base._looks_like_url(quick_input)
    if is_url:
        source = base._source_from_input(quick_input)
        st.session_state["one_load_input_method"] = "Listing URL"
        st.session_state["one_load_listing_url"] = quick_input.strip()
        st.session_state["one_load_property_address"] = ""
        if source != "Other":
            st.session_state["one_load_lead_source"] = source
    else:
        st.session_state["one_load_input_method"] = "Property address"
        st.session_state["one_load_property_address"] = quick_input.strip()
        st.session_state["one_load_listing_url"] = ""
        if strategy == "Wholesale — Off-Market":
            st.session_state["one_load_lead_source"] = "Seller call"
        elif strategy == "Wholesale — MLS":
            st.session_state["one_load_lead_source"] = "MLS"
        else:
            st.session_state["one_load_lead_source"] = "Zillow"

    st.session_state["one_load_asking_price"] = int(asking) if asking > 0 else 0
    st.session_state["asking_price"] = int(asking) if asking > 0 else 0
    st.session_state["contract_price"] = int(negotiated) if negotiated > 0 else 0
    notes = str(st.session_state.get("simple_negotiation_notes", "") or "").strip()
    terms = str(st.session_state.get("simple_other_terms", "") or "").strip()
    if notes or terms:
        current_notes = str(st.session_state.get("notes", "") or "").strip()
        added = " | ".join(part for part in [notes, terms] if part)
        if added and added not in current_notes:
            st.session_state["notes"] = "\n".join(part for part in [current_notes, added] if part)
    return exit_mode_for_strategy(strategy)


def _preload_property_and_media(st, ui, one_load, media_files: list[Any]) -> None:
    payload = one_load._build_payload_from_state(st, csv_record=None)
    normalized = one_load.normalize_one_load_lead(payload)
    one_load.apply_one_load_import(st, normalized, overwrite_demo_values=True)
    if media_files:
        base._analyze_uploaded_media(st, ui, media_files)


def _clear_all(st) -> None:
    base._clear_property(st)
    for key in EXTRA_RESET_KEYS:
        st.session_state.pop(key, None)


def render_simple_operator_section(
    st,
    ui,
    original_renderer: Callable,
    exit_mode: str = "Auto",
) -> None:
    try:
        from ui_sections import one_load_deal_ui as one_load
    except ImportError:
        try:
            from .ui_sections import one_load_deal_ui as one_load
        except ImportError:
            from war_room_offer_engine.ui_sections import one_load_deal_ui as one_load

    one_load.initialize_one_load_defaults(st)
    st.header("Analyze and Negotiate a Property")
    st.caption(
        "Enter one address or listing link, select the strategy, add the current negotiated price, and press one button."
    )

    first = st.columns([2.4, 1.3, 1])
    with first[0]:
        st.text_input(
            "Property address or listing link",
            key="simple_deal_input",
            placeholder="1115 Matson Dr, Marion, VA 24354 or paste the Zillow link",
        )
    with first[1]:
        st.selectbox("Deal Strategy", STRATEGIES, key="simple_deal_strategy")
    with first[2]:
        st.selectbox("Negotiation Status", NEGOTIATION_STATUSES, key="simple_negotiation_status")

    prices = st.columns(3)
    with prices[0]:
        st.number_input("Seller Asking Price", min_value=0, step=1000, key="simple_asking_price")
    with prices[1]:
        st.number_input(
            "Current Negotiated Price",
            min_value=0,
            step=500,
            key="simple_negotiated_price",
            help="Enter the current seller counter or the price you have negotiated the deal to.",
        )
    with prices[2]:
        st.text_input("Closing Timeline / Important Term", key="simple_closing_timeline", placeholder="Example: close in 14 days")

    details = st.columns([1.5, 1.5, 2])
    with details[0]:
        st.text_area("Negotiation Notes", height=90, key="simple_negotiation_notes", placeholder="Seller countered, roof issue, agent feedback...")
    with details[1]:
        st.text_area("Other Terms", height=90, key="simple_other_terms", placeholder="Seller pays taxes, access after contract, title issue...")
    with details[2]:
        media_files = st.file_uploader(
            "Optional photos or walkthrough video",
            type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"],
            accept_multiple_files=True,
            key="one_load_quick_media",
        )

    buttons = st.columns([3, 1])
    with buttons[0]:
        analyze_clicked = st.button("Analyze Property Automatically", type="primary", use_container_width=True)
    with buttons[1]:
        reset_clicked = st.button("Start New Property", type="secondary", use_container_width=True)

    if reset_clicked:
        _clear_all(st)
        st.rerun()

    if analyze_clicked:
        quick_input = str(st.session_state.get("simple_deal_input", "") or "").strip()
        if not quick_input:
            st.error("Enter a property address or listing link first.")
        else:
            strategy = str(st.session_state.get("simple_deal_strategy", "Auto — Best Exit"))
            chosen_exit_mode = _prepare_strategy_input(
                st,
                quick_input,
                strategy,
                number(st.session_state.get("simple_asking_price", 0)),
                number(st.session_state.get("simple_negotiated_price", 0)),
            )
            with st.spinner("Pulling property facts, RentCast rents and comps, value data, condition, and offer numbers..."):
                _preload_property_and_media(st, ui, one_load, media_files or [])
                with st.expander("Automatic engine work", expanded=False):
                    normalized = one_load._run_one_load(
                        st,
                        ui,
                        csv_record=None,
                        exit_mode=chosen_exit_mode,
                        overwrite_demo_values=True,
                    )
            st.session_state["one_load_normalized"] = normalized
            st.success("Automatic analysis and negotiation check complete.")

    normalized = st.session_state.get("one_load_normalized", {}) or {}
    if normalized:
        render_strategy_decision(st, normalized)
    else:
        st.info("Enter the property and press Analyze Property Automatically.")

    with st.expander("Advanced engine controls and full audit details", expanded=False):
        st.caption("All existing inputs, formulas, overrides, comps, messages, and audit details remain here.")
        original_renderer(st, ui, exit_mode)
