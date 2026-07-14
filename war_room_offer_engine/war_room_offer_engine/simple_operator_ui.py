from __future__ import annotations

from typing import Any, Callable


SEVERE_CONDITION_TERMS = [
    "foundation failure",
    "foundation collapse",
    "structural failure",
    "structural collapse",
    "roof collapse",
    "fire damage",
    "condemned",
    "unsafe electrical",
    "no working plumbing",
    "no plumbing",
    "no electricity",
    "septic failure",
    "major water intrusion",
    "active flooding",
]

RESET_KEYS = [
    "one_load_normalized",
    "one_load_final_answer",
    "one_load_next_action",
    "one_load_property_address",
    "one_load_listing_url",
    "one_load_asking_price",
    "simple_deal_input",
    "simple_asking_price",
    "address",
    "city",
    "state",
    "zip",
    "market",
    "asking_price",
    "contract_price",
    "rent",
    "rent_source",
    "rent_confidence",
    "arv",
    "rentcast_arv",
    "sheet_arv",
    "value_source",
    "arv_source_used",
    "arv_confidence",
    "repairs",
    "repair_analysis",
    "recommended_repairs_from_analyzer",
    "repair_source",
    "repair_notes",
    "last_source_results",
    "last_auto_pull",
    "rentcast_rent_comps",
    "rentcast_rent_comp_count",
    "rentcast_rent_comp_average",
    "rentcast_rent_comp_median",
    "rentcast_value_comps",
    "rentcast_value_comp_count",
    "auto_sold_comps",
    "auto_arv_summary",
    "auto_recommended_arv",
    "strong_comp_count",
    "good_comp_count",
    "weak_comp_count",
    "excluded_comp_count",
    "one_load_quick_media",
]


def _money(value: Any) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except Exception:
        return "$0"


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _looks_like_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    return text.startswith("http://") or text.startswith("https://") or "www." in text


def _source_from_input(value: str) -> str:
    text = str(value or "").lower()
    if "zillow" in text:
        return "Zillow"
    if "redfin" in text:
        return "Redfin"
    if "realtor" in text:
        return "Realtor.com"
    return "Other"


def _condition_text(st) -> str:
    return " ".join(
        str(st.session_state.get(key, "") or "")
        for key in ["notes", "repair_notes", "manual_repair_notes", "seller_condition_notes"]
    ).lower()


def _has_severe_condition_risk(st) -> bool:
    notes = _condition_text(st)
    return any(term in notes for term in SEVERE_CONDITION_TERMS)


def _best_exit(st, normalized: dict[str, Any]) -> str:
    candidates = [
        st.session_state.get("recommended_exit_strategy"),
        st.session_state.get("one_load_recommended_exit"),
        normalized.get("recommended_exit_strategy"),
    ]
    for candidate in candidates:
        text = str(candidate or "").strip()
        if text and text not in ["Human Review", "Needs Human Review"]:
            return text
    final_answer = str(normalized.get("final_simple_answer", "") or "")
    if "slow flip" in final_answer.lower():
        return "Slow Flip"
    if "wholesale" in final_answer.lower():
        return "Wholesale"
    return "Auto — best modeled exit"


def _actual_missing(st, normalized: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    if not str(st.session_state.get("address", "") or "").strip():
        missing.append("property address")
    if _number(st.session_state.get("rent", 0)) <= 0:
        missing.append("rent")
    if _number(st.session_state.get("arv", 0)) <= 0:
        missing.append("value / ARV")
    if _number(normalized.get("internal_max", 0)) <= 0:
        missing.append("usable maximum offer")
    return missing


def build_operator_decision(st, normalized: dict[str, Any]) -> dict[str, Any]:
    first_offer = _number(normalized.get("first_offer", 0))
    hard_max = _number(normalized.get("do_not_exceed", normalized.get("internal_max", 0)))
    asking = _number(st.session_state.get("contract_price", 0)) or _number(st.session_state.get("asking_price", 0))
    rent = _number(st.session_state.get("rent", 0))
    arv = _number(st.session_state.get("arv", 0))
    rent_comps = int(_number(st.session_state.get("rentcast_rent_comp_count", 0)))
    sold_comps = int(_number(st.session_state.get("rentcast_value_comp_count", 0)))
    auto_comp_count = int(_number(st.session_state.get("auto_comp_count", 0)))
    sold_comps = max(sold_comps, auto_comp_count)
    rent_confidence = str(st.session_state.get("rent_confidence", "") or normalized.get("rent_confidence", "Weak"))
    arv_confidence = str(st.session_state.get("arv_confidence", "Not enough data") or "Not enough data")
    arv_source = str(st.session_state.get("arv_source_used", normalized.get("arv_source", "Missing")) or "Missing")
    final_engine_answer = str(normalized.get("final_simple_answer", normalized.get("final_decision", "")) or "")
    exit_strategy = _best_exit(st, normalized)
    missing = _actual_missing(st, normalized)
    severe_condition = _has_severe_condition_risk(st)
    livable = str(st.session_state.get("livable", "Unknown") or "Unknown")

    if missing:
        verdict = "NEEDS MORE INFORMATION"
        verdict_type = "warning"
        action = "Let the app finish the missing automatic pulls, then rerun the decision."
    elif severe_condition or livable == "No":
        verdict = "REVIEW BEFORE BUYING"
        verdict_type = "warning"
        action = "Verify the major safety or livability issue before committing."
    elif hard_max <= 0 or final_engine_answer in ["Pass", "Do Not Buy"]:
        verdict = "DO NOT BUY"
        verdict_type = "error"
        action = "Pass unless new verified information materially changes the numbers."
    elif asking > hard_max > 0:
        verdict = f"BUY ONLY AT OR BELOW {_money(hard_max)}"
        verdict_type = "warning"
        action = f"Start at {_money(first_offer)} and never exceed {_money(hard_max)}."
    else:
        verdict = "BUY"
        verdict_type = "success"
        action = f"Send the starting offer of {_money(first_offer)}. Do not exceed {_money(hard_max)}."

    confidence_points = 0
    if rent > 0:
        confidence_points += 1
    if rent_comps >= 3 or "strong" in rent_confidence.lower():
        confidence_points += 2
    elif rent_comps > 0 or "medium" in rent_confidence.lower():
        confidence_points += 1
    if sold_comps >= 3 or arv_confidence.lower() == "strong":
        confidence_points += 2
    elif sold_comps > 0 or arv_confidence.lower() in ["medium", "avm only"]:
        confidence_points += 1
    if not severe_condition and livable != "No":
        confidence_points += 1
    if not missing:
        confidence_points += 1

    confidence = "Strong" if confidence_points >= 6 else "Medium" if confidence_points >= 3 else "Weak"
    if verdict in ["NEEDS MORE INFORMATION", "REVIEW BEFORE BUYING"]:
        confidence = "Weak"

    reasons: list[str] = []
    if asking > 0:
        reasons.append(f"Current price is {_money(asking)}; the app's do-not-exceed price is {_money(hard_max)}.")
    else:
        reasons.append(f"The app calculated a starting offer of {_money(first_offer)} and a do-not-exceed price of {_money(hard_max)}.")
    reasons.append(
        f"Rent support is {_money(rent)}/month from {rent_comps} automatic RentCast comparable rental(s) "
        f"with {rent_confidence or 'unknown'} confidence."
    )
    reasons.append(
        f"Value is {_money(arv)} from {arv_source} with {arv_confidence} confidence and {sold_comps} automatic sold comp(s)."
    )
    if severe_condition or livable == "No":
        reasons.append("A major safety or livability concern requires verification before buying.")
    elif _number(st.session_state.get("repairs", 0)) > 0:
        reasons.append(
            f"The condition analyzer estimated {_money(st.session_state.get('repairs', 0))}; for a slow flip this is a warning, not an automatic dollar-for-dollar rehab deduction."
        )
    if missing:
        reasons.append("Still missing: " + ", ".join(missing) + ".")

    return {
        "verdict": verdict,
        "verdict_type": verdict_type,
        "action": action,
        "confidence": confidence,
        "first_offer": first_offer,
        "hard_max": hard_max,
        "asking": asking,
        "rent": rent,
        "arv": arv,
        "rent_comps": rent_comps,
        "sold_comps": sold_comps,
        "rent_confidence": rent_confidence or "Weak",
        "arv_confidence": arv_confidence,
        "arv_source": arv_source,
        "exit_strategy": exit_strategy,
        "engine_answer": final_engine_answer,
        "reasons": reasons[:5],
        "missing": missing,
    }


def render_operator_decision(st, normalized: dict[str, Any]) -> None:
    decision = build_operator_decision(st, normalized)
    st.markdown("## Deal Decision")
    with st.container(border=True):
        if decision["verdict_type"] == "success":
            st.success(f"# {decision['verdict']}")
        elif decision["verdict_type"] == "error":
            st.error(f"# {decision['verdict']}")
        else:
            st.warning(f"# {decision['verdict']}")

        top = st.columns(4)
        top[0].metric("Starting Offer", _money(decision["first_offer"]))
        top[1].metric("Do Not Exceed", _money(decision["hard_max"]))
        top[2].metric("Best Exit", decision["exit_strategy"])
        top[3].metric("Decision Confidence", decision["confidence"])

        st.info(decision["action"])
        st.markdown("**Why the app made this decision**")
        for reason in decision["reasons"]:
            st.write(f"• {reason}")

        with st.expander("Automatic data collected", expanded=False):
            data_cols = st.columns(4)
            data_cols[0].metric("Rent", _money(decision["rent"]))
            data_cols[1].metric("Rental Comps", decision["rent_comps"])
            data_cols[2].metric("Value / ARV", _money(decision["arv"]))
            data_cols[3].metric("Sold Comps", decision["sold_comps"])
            st.write(
                {
                    "Rent confidence": decision["rent_confidence"],
                    "ARV source": decision["arv_source"],
                    "ARV confidence": decision["arv_confidence"],
                    "Detailed engine answer": decision["engine_answer"],
                }
            )


def _prepare_quick_input(st, quick_input: str, asking_price: float, lead_kind: str) -> None:
    is_url = _looks_like_url(quick_input)
    source = _source_from_input(quick_input)
    if is_url:
        st.session_state["one_load_input_method"] = "Listing URL"
        st.session_state["one_load_listing_url"] = quick_input.strip()
        st.session_state["one_load_property_address"] = ""
        st.session_state["one_load_lead_type"] = "On-market listing"
        st.session_state["one_load_lead_source"] = source
        st.session_state["source_mode"] = "Zillow / Sheet Match" if source == "Zillow" else "Off-Market / Manual"
        st.session_state["lead_source"] = "Zillow / Apify" if source == "Zillow" else source
    else:
        st.session_state["one_load_input_method"] = "Property address"
        st.session_state["one_load_property_address"] = quick_input.strip()
        st.session_state["one_load_listing_url"] = ""
        if lead_kind == "Off-market seller":
            st.session_state["one_load_lead_type"] = "Off-market seller lead"
            st.session_state["one_load_lead_source"] = "Seller call"
            st.session_state["source_mode"] = "Off-Market / Manual"
            st.session_state["lead_source"] = "Off-Market Seller"
        else:
            st.session_state["one_load_lead_type"] = "On-market listing"
            st.session_state["one_load_lead_source"] = "Zillow"
            st.session_state["source_mode"] = "Zillow / Sheet Match"
            st.session_state["lead_source"] = "Zillow / Apify"
    if asking_price > 0:
        st.session_state["one_load_asking_price"] = int(asking_price)
        st.session_state["asking_price"] = int(asking_price)


def _analyze_uploaded_media(st, ui, files: list[Any]) -> bool:
    files = files or []
    if not files:
        return False
    photos = [file for file in files if str(getattr(file, "name", "")).lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    videos = [file for file in files if str(getattr(file, "name", "")).lower().endswith((".mp4", ".mov", ".m4v", ".avi"))]
    try:
        generated_notes = ui.generate_boots_on_ground_notes(photos, videos[0] if videos else None)
    except Exception as exc:
        st.warning(f"Property media was uploaded, but automatic condition notes could not be generated: {exc}")
        return False
    if not str(generated_notes or "").strip():
        return False
    st.session_state["repair_notes"] = ui.safe_condition_text(generated_notes)
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
    st.session_state["recommended_repairs_from_analyzer"] = int(analysis.get("recommended_repair_number", 0) or 0)
    st.session_state["repairs"] = int(analysis.get("recommended_repair_number", 0) or 0)
    st.session_state["repair_source"] = "AI Repair Estimate"
    return True


def _clear_property(st) -> None:
    for key in RESET_KEYS:
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
    st.header("Analyze a Property")
    st.caption("Paste one Zillow link or property address. The app pulls everything connected, runs the deal engine, and gives one clear buying decision.")

    input_col, ask_col = st.columns([3, 1])
    with input_col:
        st.text_input(
            "Property address or listing link",
            key="simple_deal_input",
            placeholder="1115 Matson Dr, Marion, VA 24354 or paste the Zillow link",
        )
    with ask_col:
        st.number_input("Asking price if not listed", min_value=0, step=1000, key="simple_asking_price")

    option_col, media_col = st.columns([1, 2])
    with option_col:
        st.selectbox("Lead type", ["Auto / listing", "Off-market seller"], key="simple_lead_kind")
    with media_col:
        media_files = st.file_uploader(
            "Optional photos or walkthrough video",
            type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"],
            accept_multiple_files=True,
            key="one_load_quick_media",
        )

    analyze_col, reset_col = st.columns([3, 1])
    with analyze_col:
        analyze_clicked = st.button("Analyze Property Automatically", type="primary", use_container_width=True)
    with reset_col:
        reset_clicked = st.button("Start New Property", type="secondary", use_container_width=True)

    if reset_clicked:
        _clear_property(st)
        st.rerun()

    if analyze_clicked:
        quick_input = str(st.session_state.get("simple_deal_input", "") or "").strip()
        if not quick_input:
            st.error("Enter a property address or listing link first.")
        else:
            _prepare_quick_input(
                st,
                quick_input,
                _number(st.session_state.get("simple_asking_price", 0)),
                st.session_state.get("simple_lead_kind", "Auto / listing"),
            )
            with st.spinner("Pulling property facts, RentCast rents and comps, value data, and running the offer engine..."):
                with st.expander("Automatic engine work", expanded=False):
                    normalized = one_load._run_one_load(
                        st,
                        ui,
                        csv_record=None,
                        exit_mode=exit_mode,
                        overwrite_demo_values=True,
                    )
                    if _analyze_uploaded_media(st, ui, media_files or []):
                        normalized = one_load._run_one_load(
                            st,
                            ui,
                            csv_record=None,
                            exit_mode=exit_mode,
                            overwrite_demo_values=True,
                        )
            st.session_state["one_load_normalized"] = normalized
            st.success("Automatic analysis complete.")

    normalized = st.session_state.get("one_load_normalized", {}) or {}
    if normalized:
        render_operator_decision(st, normalized)
    else:
        st.info("Enter the property above and press Analyze Property Automatically.")

    with st.expander("Advanced engine controls and full audit details", expanded=False):
        st.caption("Nothing was removed. Open this only when you need to inspect or override the detailed engine inputs.")
        original_renderer(st, ui, exit_mode)
