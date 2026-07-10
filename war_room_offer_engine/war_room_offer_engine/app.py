from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from rules import Assumptions, DealInput, analyze_deal, money
from ai_writer import build_ai_summary
from data_sources import fetch_all_sources, merge_results, get_secret
from repair_analyzer import analyze_repairs, repair_number_for_offer
try:
    from repair_price_book_il import available_markets, get_market_buy_box_max, get_market_profile, get_market_wholesale_buyer_percent
except ImportError:
    try:
        from .repair_price_book_il import available_markets, get_market_buy_box_max, get_market_profile, get_market_wholesale_buyer_percent
    except ImportError:
        from war_room_offer_engine.repair_price_book_il import (
            available_markets,
            get_market_buy_box_max,
            get_market_profile,
            get_market_wholesale_buyer_percent,
        )
from media_notes import generate_boots_on_ground_notes
st.set_page_config(page_title="War Room Offer Engine", page_icon="🏠", layout="wide")

FIELD_DEFAULTS = {
    "address": "",
    "market": "",
    "source_mode": "Zillow / Sheet Match",
    "lead_source": "Zillow / Apify",
    "lead_type": "Agent",
    "status": "Unknown",
    "asking_price": 35000,
    "contract_price": 0,
    "rent": 900,
    "occupancy": "Unknown",
    "livable": "Unknown",
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
    "taxes": 0,
    "days_on_market": 0,
    "arv": 0,
    "rentcast_arv": 0,
    "sheet_arv": 0,
    "manual_arv_override": 0,
    "value_source": "Missing",
    "repairs": 0,
    "manual_repair_estimate": 0,
    "manual_repair_notes": "",
    "repair_source": "Missing",
    "manual_market_buy_box_max_override": 0,
    "notes": "",
}

for key, value in FIELD_DEFAULTS.items():
    st.session_state.setdefault(key, value)
st.session_state.setdefault("last_source_results", [])
st.session_state.setdefault("last_auto_pull", {})


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def comp_price_values() -> list[float]:
    prices = []
    for idx in range(1, 6):
        price = safe_float(st.session_state.get(f"manual_comp_{idx}_price", 0))
        if price > 0:
            prices.append(price)
    return prices


def manual_comps_average() -> float:
    prices = comp_price_values()
    if not prices:
        return 0.0
    return sum(prices) / len(prices)


def resolve_value_source() -> tuple[float, str]:
    rentcast_arv = safe_float(st.session_state.get("rentcast_arv", 0))
    sheet_arv = safe_float(st.session_state.get("sheet_arv", 0))
    comps_arv = manual_comps_average()
    manual_override = safe_float(st.session_state.get("manual_arv_override", 0))

    if manual_override > 0:
        return manual_override, "Manual Override"
    if rentcast_arv > 0:
        return rentcast_arv, "RentCast"
    if sheet_arv > 0:
        return sheet_arv, "Zillow/Apify Sheet"
    if comps_arv > 0:
        return comps_arv, "Manual Comps"
    return 0.0, "Missing"


def resolve_repair_source() -> tuple[float, str]:
    manual_repair = safe_float(st.session_state.get("manual_repair_estimate", 0))
    ai_repair = safe_float(st.session_state.get("recommended_repairs_from_analyzer", 0))

    if manual_repair > 0:
        return manual_repair, "Manual Repair Estimate"
    if ai_repair > 0:
        return ai_repair, "AI Repair Estimate"
    return 0.0, "Missing"


def percent_label(value: float) -> str:
    return f"{float(value or 0) * 100:.0f}%"


def market_wholesale_percent_used(
    market: str,
    arv: float,
    repairs: float,
    notes: str,
    repair_notes: str,
) -> tuple[float, list[str]]:
    market_profile = get_market_profile(market)
    buyer_percent = float(market_profile.get("wholesale_buyer_percent", 0.70) or 0.70)
    buyer_profile = market_profile.get("buyer_profile", "")
    all_notes = f"{notes or ''} {repair_notes or ''}".lower()
    adjustments = []

    major_red_flags = [
        "foundation",
        "structural",
        "mold",
        "fire damage",
        "condemned",
        "roof leak",
        "active leak",
        "water intrusion",
        "sewer",
        "polybutylene",
        "galvanized",
        "termite",
        "flood zone",
    ]

    if arv > 0 and repairs > max(40000, arv * 0.25):
        buyer_percent -= 0.05
        adjustments.append("Heavy repairs reduce buyer percent by 5%.")
    elif any(flag in all_notes for flag in major_red_flags):
        buyer_percent -= 0.05
        adjustments.append("Major red flags reduce buyer percent by 5%.")

    if arv > 0 and arv < 75000 and buyer_profile != "Strong / liquid market":
        buyer_percent = min(buyer_percent, 0.65)
        adjustments.append("Low ARV under $75k caps buyer percent near 65% outside strong markets.")

    return max(buyer_percent, 0.50), adjustments


def resolve_market_buy_box_max(market: str) -> tuple[float, str]:
    manual_override = safe_float(st.session_state.get("manual_market_buy_box_max_override", 0))
    if manual_override > 0:
        return manual_override, "Manual Override"
    return get_market_buy_box_max(market), "Market Default"


def update_state_from_auto_pull(data: dict) -> None:
    mapping = {
        "market": "market",
        "asking_price": "asking_price",
        "rent": "rent",
        "beds": "beds",
        "baths": "baths",
        "sqft": "sqft",
        "taxes": "taxes",
        "days_on_market": "days_on_market",
        "status": "status",
        "arv": "arv",
        "rentcast_arv": "rentcast_arv",
        "sheet_arv": "sheet_arv",
        "arv_source": "value_source",
    }
    for source_key, state_key in mapping.items():
        value = data.get(source_key)
        if value not in [None, "", 0]:
            if state_key in ["asking_price", "rent", "sqft", "taxes", "days_on_market", "arv", "rentcast_arv", "sheet_arv"]:
                st.session_state[state_key] = int(float(value))
            elif state_key in ["beds", "baths"]:
                st.session_state[state_key] = float(value)
            else:
                st.session_state[state_key] = str(value)

    note_bits = []
    for label in ["agent_name", "agent_phone", "listing_url", "year_built", "property_type", "matched_sheet_address"]:
        if data.get(label):
            pretty = label.replace("_", " ").title()
            note_bits.append(f"{pretty}: {data[label]}")
    if note_bits:
        current = st.session_state.get("notes", "")
        auto_note = "Auto-pulled data: " + " | ".join(note_bits)
        st.session_state["notes"] = (current + "\n" + auto_note).strip() if current else auto_note

    resolved_arv, value_source = resolve_value_source()
    st.session_state["arv"] = int(resolved_arv) if resolved_arv > 0 else 0
    st.session_state["value_source"] = value_source


def build_missing_info(deal: DealInput, uploaded_files, repair_notes: str) -> list[str]:
    missing = []
    if not str(deal.address or "").strip():
        missing.append("Missing address")
    if deal.arv <= 0:
        missing.append("Missing ARV")
    if deal.rent <= 0:
        missing.append("Missing rent")
    if deal.repairs <= 0 and deal.exit_mode in ["Wholesale Only", "Auto"]:
        missing.append("Missing repairs")
    if deal.livable == "Unknown":
        missing.append("Missing condition")
    if deal.occupancy == "Unknown":
        missing.append("Missing occupancy")
    if not uploaded_files and not str(repair_notes or "").strip():
        missing.append("Missing photos/repair notes")
    return missing


def build_extra_risk_flags(
    deal: DealInput,
    result: dict,
    value_source: str,
    assumptions: Assumptions,
) -> list[str]:
    notes = str(deal.notes or "").lower()
    repair_notes_text = str(st.session_state.get("repair_notes", "") or "").lower()
    all_notes = f"{notes} {repair_notes_text}"
    risks = []

    if deal.arv <= 0:
        risks.append("ARV missing")
    if value_source == "Manual Comps":
        risks.append("Manual comps used")
    if value_source == "Manual Override":
        risks.append("Manual override used")
    if deal.arv > 0 and deal.repairs > max(40000, deal.arv * 0.25):
        risks.append("Repairs high")
    if "mold" in all_notes:
        risks.append("Mold mentioned in notes")
    if "roof leak" in all_notes or "leak in roof" in all_notes or ("roof" in all_notes and "leak" in all_notes):
        risks.append("Roof leak mentioned in notes")
    if deal.livable == "No":
        risks.append("Property not livable")
    market_buy_box_max = safe_float(st.session_state.get("market_buy_box_max_used", 0))
    if market_buy_box_max > 0 and deal.asking_price > market_buy_box_max:
        risks.append(f"Asking/buy price is above the market buy box max of {money(market_buy_box_max)}")

    slow = result.get("slow_flip", {})
    if slow.get("rent_formula_max_offer_before_cap", 0) > assumptions.slow_flip_max_offer_cap:
        risks.append("Slow flip max offer is above normal $32,000 cap")

    wholesale = result.get("wholesale", {})
    if deal.exit_mode in ["Wholesale Only", "Auto"] and wholesale.get("estimated_fee_at_ask", 0) < assumptions.min_assignment_fee:
        risks.append("Wholesale fee below minimum")

    return risks


def choose_final_decision(
    result: dict,
    deal: DealInput,
    missing_info: list[str],
    risk_flags: list[str],
) -> str:
    best = result["best"]
    grade = result["grade"]
    best_exit = result["best_exit"]
    max_offer = safe_float(best.get("max_offer", 0))
    asking = safe_float(deal.asking_price)
    critical_missing = {"Missing address", "Missing ARV", "Missing rent"}

    if best_exit == "Pass" or grade == "Pass":
        return "Pass"
    if best_exit == "Needs Human Review" or deal.livable == "No":
        return "Human Review"
    if critical_missing.intersection(missing_info):
        return "Human Review"
    if any(flag in risk_flags for flag in ["Mold mentioned in notes", "Property not livable"]):
        return "Human Review"
    if asking > 0 and max_offer > 0 and asking > max_offer:
        return "Renegotiate"
    if grade in ["A", "B", "C"] and best.get("offer_to_send", 0) > 0:
        return "Send Offer"
    if max_offer > 0:
        return "Renegotiate"
    return "Pass"


def choose_team_action(final_decision: str, missing_info: list[str]) -> str:
    if final_decision == "Pass":
        return "Pass for now"
    if "Missing photos/repair notes" in missing_info or "Missing condition" in missing_info or "Missing occupancy" in missing_info:
        return "Get photos / walkthrough"
    if "Missing repairs" in missing_info:
        return "Get repair estimate"
    if final_decision == "Renegotiate":
        return "Renegotiate lower"
    if final_decision == "Send Offer":
        return "Send first offer"
    return "Call agent/seller now"


def build_decision_reason(
    result: dict,
    deal: DealInput,
    value_source: str,
    risk_flags: list[str],
) -> str:
    best = result["best"]
    risks = result.get("risks", [])
    risk_summary = risk_flags[0] if risk_flags else (risks[0] if risks else "no major risk flags")
    return (
        f"Grade {result['grade']} with {result['best_exit']} as the best exit. "
        f"Value source is {value_source}; ARV is {money(deal.arv)}, rent is {money(deal.rent)}, "
        f"repairs are {money(deal.repairs)}, and buy price is {money(deal.asking_price)}. "
        f"The current first offer is {money(best.get('offer_to_send', best.get('target_offer_low', 0)))} "
        f"against an internal max of {money(best.get('max_offer', 0))}. Key concern: {risk_summary}."
    )


def render_final_decision_box(
    result: dict,
    deal: DealInput,
    value_source: str,
    uploaded_files,
    repair_notes: str,
    assumptions: Assumptions,
) -> dict:
    best = result["best"]
    missing_info = build_missing_info(deal, uploaded_files, repair_notes)
    risk_flags = list(dict.fromkeys(result.get("risks", []) + build_extra_risk_flags(deal, result, value_source, assumptions)))
    final_decision = choose_final_decision(result, deal, missing_info, risk_flags)
    team_action = choose_team_action(final_decision, missing_info)
    decision_reason = build_decision_reason(result, deal, value_source, risk_flags)

    st.subheader("Final Decision")
    with st.container(border=True):
        if final_decision == "Send Offer":
            st.success("Final Decision: Send Offer")
        elif final_decision == "Renegotiate":
            st.warning("Final Decision: Renegotiate")
        elif final_decision == "Pass":
            st.error("Final Decision: Pass")
        else:
            st.warning("Final Decision: Human Review")

        d1, d2, d3 = st.columns(3)
        d1.metric("First Offer to Send", money(best.get("offer_to_send", best.get("target_offer_low", 0))))
        d2.metric("Internal Max Offer", money(best.get("max_offer", 0)))
        d3.metric("Best Exit", result["best_exit"])

        st.write("Why this decision:")
        st.write(decision_reason)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.write("Missing Info:")
            if missing_info:
                for item in missing_info:
                    st.warning(item)
            else:
                st.success("None")
        with c2:
            st.write("Risk Flags:")
            if risk_flags:
                for item in risk_flags:
                    st.warning(item)
            else:
                st.success("None")
        with c3:
            st.write("Team Action:")
            st.info(team_action)

    return {
        "final_decision": final_decision,
        "decision_reason": decision_reason,
        "missing_info": missing_info,
        "risk_flags": risk_flags,
        "team_action": team_action,
    }


def build_deal_log_row(
    result: dict,
    deal: DealInput,
    final_summary: dict,
    value_source: str,
    asking_price: float,
    contract_price: float,
) -> dict:
    best = result["best"]
    market_profile = get_market_profile(st.session_state.get("repair_market", "Central IL"))
    result_assumptions = result.get("assumptions", {})
    market_buy_box_max, market_buy_box_source = resolve_market_buy_box_max(st.session_state.get("repair_market", "Central IL"))
    return {
        "date_time_analyzed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "address": deal.address,
        "market": deal.market,
        "source_mode": st.session_state.get("source_mode", ""),
        "lead_source": st.session_state.get("lead_source", ""),
        "lead_type": deal.lead_type,
        "deal_type": deal.exit_mode,
        "asking_price": asking_price,
        "contract_buy_price": contract_price,
        "rent": deal.rent,
        "arv": deal.arv,
        "value_source": value_source,
        "manual_comps_average": manual_comps_average(),
        "market_profile": market_profile.get("buyer_profile", ""),
        "market_buy_box_max": market_buy_box_max,
        "market_buy_box_max_source": market_buy_box_source,
        "market_repair_multiplier": market_profile.get("repair_multiplier", 1.0),
        "market_wholesale_buyer_percent_default": result_assumptions.get(
            "market_wholesale_buyer_percent",
            market_profile.get("wholesale_buyer_percent", 0.70),
        ),
        "wholesale_buyer_percent_source": result_assumptions.get("wholesale_buyer_percent_source", ""),
        "final_wholesale_buyer_percent_used": result_assumptions.get("wholesale_buyer_percent_arv", 0.70),
        "repairs": deal.repairs,
        "repair_source": st.session_state.get("repair_source", "Missing"),
        "manual_repair_notes": st.session_state.get("manual_repair_notes", ""),
        "final_decision": final_summary["final_decision"],
        "team_action": final_summary["team_action"],
        "best_exit": result["best_exit"],
        "first_offer": best.get("offer_to_send", best.get("target_offer_low", 0)),
        "internal_max": best.get("max_offer", 0),
        "estimated_fee": best.get("estimated_fee_at_ask", 0),
        "missing_info": "; ".join(final_summary["missing_info"]),
        "risk_flags": "; ".join(final_summary["risk_flags"]),
        "notes": deal.notes,
        "suggested_message": result["suggested_message"],
    }


def render_save_deal_analysis(deal_log_row: dict) -> None:
    st.subheader("Save Deal Analysis")
    deal_log_df = pd.DataFrame([deal_log_row])
    st.dataframe(deal_log_df, use_container_width=True)
    st.download_button(
        "Save / Download Deal Log Row",
        data=deal_log_df.to_csv(index=False),
        file_name="war_room_deal_log_row.csv",
        mime="text/csv",
        key="download_deal_log_row",
    )


st.title("🏠 War Room Offer Engine")
st.caption("Universal Property Analyzer — Zillow/Sheet leads, MLS leads, off-market sellers, RentCast, and manual fallback in one place.")

with st.sidebar:
    st.header("Offer Assumptions")
    min_assignment_fee = st.number_input("Minimum assignment fee", min_value=0, value=10000, step=500)
    exception_assignment_fee = st.number_input("Exception assignment fee", min_value=0, value=5000, step=500)
    slow_flip_rent_multiple = st.slider("Slow flip resale multiple x rent", 20, 70, 45, 1)
    close_title_buffer = st.number_input("Close/title/safety buffer", min_value=0, value=1500, step=250)
    target_offer_discount = st.slider("Target offer discount from max", 0.50, 1.00, 0.85, 0.01)
    manual_wholesale_override = st.checkbox(
        "Use manual wholesale buyer % override",
        value=False,
        help="When off, the app uses the selected market profile and deal risk to choose the buyer percent.",
    )
    wholesale_buyer_percent_arv = st.slider(
        "Manual wholesale buyer % of ARV",
        0.40,
        0.90,
        0.70,
        0.01,
        disabled=not manual_wholesale_override,
    )
    slow_flip_max_offer_cap = st.number_input("Normal slow flip max offer cap", min_value=0, value=32000, step=500, help="Bradley rule: 98% of slow-flip offers stay at or below this number. Use human review for exceptions.")
    slow_flip_first_offer_gap = st.number_input("Slow flip first offer below max", min_value=0, value=4000, step=500, help="Negotiation rule: do not start at max. Example: $32k max starts at $28k.")

    st.divider()
    st.header("Data Connections")
    st.caption("Green means ready. Missing connections do not stop manual analysis.")
    st.write("✅ RentCast API key" if get_secret("RENTCAST_API_KEY") else "⚠️ RentCast API key missing")
    st.write("✅ Zillow/Master Feed CSV" if get_secret("APIFY_ZILLOW_SHEET_CSV_URL") else "⚠️ Zillow/Master Feed CSV missing")
    st.write("✅ Lead sheet" if get_secret("LEADS_SHEET_CSV_URL") else "ℹ️ Lead sheet blank / optional")

assumptions = Assumptions(
    min_assignment_fee=float(min_assignment_fee),
    exception_assignment_fee=float(exception_assignment_fee),
    slow_flip_rent_multiple=float(slow_flip_rent_multiple),
    close_title_buffer=float(close_title_buffer),
    target_offer_discount=float(target_offer_discount),
    wholesale_buyer_percent_arv=float(wholesale_buyer_percent_arv),
    wholesale_buyer_percent_source="Manual Override" if manual_wholesale_override else "Market Default",
    market_wholesale_buyer_percent=float(wholesale_buyer_percent_arv),
    slow_flip_max_offer_cap=float(slow_flip_max_offer_cap),
    slow_flip_first_offer_gap=float(slow_flip_first_offer_gap),
)

st.subheader("1. Pull Property Data")

source_col1, source_col2 = st.columns([1, 1])
with source_col1:
    st.radio(
        "Source mode",
        ["Zillow / Sheet Match", "Off-Market / Manual"],
        key="source_mode",
        horizontal=True,
        help="Zillow / Sheet Match searches your published Master Feed. Off-Market / Manual skips the sheet and uses RentCast + your manual inputs.",
    )
with source_col2:
    st.selectbox(
        "Lead source",
        ["Zillow / Apify", "MLS / Agent", "Off-Market Seller", "Facebook", "Driving for Dollars", "Cold Text Reply", "Manual Entry", "Other"],
        key="lead_source",
    )

if st.session_state.get("source_mode") == "Off-Market / Manual":
    st.info("Off-market/manual mode skips the Zillow/Master Feed. Enter the seller ask manually if you have it. RentCast will still pull rent, beds, baths, sq ft, value, and facts.")
else:
    st.info("Zillow/Sheet mode uses RentCast plus your Master Feed CSV to pull asking price, Zillow link, status, and other listing data when the address matches.")

lookup_col1, lookup_col2 = st.columns([3, 1])
with lookup_col1:
    st.text_input("Property address", key="address", placeholder="123 Main St, Decatur IL 62522")
with lookup_col2:
    st.write("")
    st.write("")
    pull_data = st.button("Pull Data", type="primary", use_container_width=True)

if pull_data:
    include_listing_sheet = st.session_state.get("source_mode") == "Zillow / Sheet Match"
    spinner_text = "Pulling RentCast + Master Feed data..." if include_listing_sheet else "Pulling RentCast data only..."
    with st.spinner(spinner_text):
        results = fetch_all_sources(
            st.session_state["address"],
            beds=float(st.session_state.get("beds", 0) or 0),
            baths=float(st.session_state.get("baths", 0) or 0),
            sqft=float(st.session_state.get("sqft", 0) or 0),
            include_listing_sheet=include_listing_sheet,
            
        )
        merged = merge_results(results)
        st.session_state["last_source_results"] = results
        st.session_state["last_auto_pull"] = merged
        update_state_from_auto_pull(merged)

        good_sources = []
        for item in results:
            if isinstance(item, dict):
                if item.get("found") or item.get("ok"):
                    good_sources.append(item.get("source", "Unknown"))
            else:
                if getattr(item, "ok", False) or getattr(item, "found", False):
                    good_sources.append(getattr(item, "source", "Unknown"))

        if good_sources:
            st.success("Pulled data from: " + ", ".join(good_sources))
        else:
            st.warning("No data pulled yet. Add Streamlit secrets or verify the address. Manual analysis still works.")

        with st.expander("Data pull results"):
            for result in results:
                if isinstance(result, dict):
                    source = result.get("source", "Unknown")
                    found = result.get("found") or result.get("ok")
                    message = result.get("notes") or result.get("message") or ""
                    data = result.get("data", None)
                else:
                    source = getattr(result, "source", "Unknown")
                    found = getattr(result, "ok", False) or getattr(result, "found", False)
                    message = getattr(result, "message", "") or getattr(result, "notes", "")
                    data = getattr(result, "data", None)

                if found:
                    st.success(f"{source}: {message}")
                    if data:
                        st.write(data)
                else:
                    st.info(f"{source}: {message}") 

       
st.caption("Works for Zillow, MLS, agent leads, and off-market sellers. Slow Flip uses rent/livability; ARV and repairs are reference unless you switch to Wholesale/Auto.")

exit_mode = st.radio(
    "Deal type",
    ["Slow Flip Only", "Wholesale Only", "Auto"],
    horizontal=True,
    help="Use Slow Flip Only for your normal owner-finance/slow-flip buy box. ARV/repairs are informational unless you switch to Wholesale/Auto.",
)

col1, col2, col3 = st.columns([1, 1, 1.45])
with col1:
    st.text_input("Market / city", key="market", placeholder="Decatur IL")
    st.selectbox("Lead type", ["Agent", "Seller", "Wholesaler", "Other"], key="lead_type")
    st.selectbox("Listing/status", ["Active", "Pending", "Sold", "Off-market", "Unknown"], key="status")
    st.number_input("Days on market", min_value=0, step=1, key="days_on_market")

with col2:
    st.number_input("Asking price", min_value=0, step=1000, key="asking_price")
    st.number_input("Contract / Buy Price", min_value=0, step=1000, key="contract_price")
    st.number_input("Rent estimate", min_value=0, step=25, key="rent")
    st.selectbox("Occupancy", ["Unknown", "Vacant", "Tenant occupied", "Owner occupied"], key="occupancy")
    st.selectbox("Livable now?", ["Unknown", "Yes", "No"], key="livable")

with col3:
    st.number_input("Beds", min_value=0.0, step=0.5, key="beds")
    st.number_input("Baths", min_value=0.0, step=0.5, key="baths")
    st.number_input("Sq ft", min_value=0, step=50, key="sqft")
    st.number_input("Annual taxes", min_value=0, step=100, key="taxes")
    st.subheader("3. Repair / Condition Analyzer")
    st.caption(
        "Uses investor repair pricing by selected market across IL, VA, MI, St. Louis, IN, AL, and FL. "
        "Upload photos/videos and add boots-on-ground notes. "
        "This version prices the repair scope from the notes and uploaded media count. "
        "Full AI video frame review and audio transcription will be added next."
    )

    repair_market = st.selectbox(
        "Repair pricing market",
        available_markets(),
        index=0,
        key="repair_market",
    )
    st.number_input(
        "Manual market buy box max override",
        min_value=0,
        step=5000,
        key="manual_market_buy_box_max_override",
        help="Leave at $0 to use the market default. Every Virginia market defaults to $80,000.",
    )
    market_buy_box_max, market_buy_box_source = resolve_market_buy_box_max(st.session_state.get("repair_market", "Central IL"))
    st.session_state["market_buy_box_max_used"] = int(market_buy_box_max) if market_buy_box_max > 0 else 0
    st.session_state["market_buy_box_max_source"] = market_buy_box_source
    if market_buy_box_max > 0:
        st.info(f"Market Buy Box Max: {money(market_buy_box_max)} ({market_buy_box_source})")
    else:
        st.info("Market Buy Box Max: Not set")

    r2, r3 = st.columns(2)

    with r2:
        repair_level = st.selectbox(
            "Repair finish level",
            ["Investor Basic", "Rental Ready", "Retail Ready"],
            index=1,
            key="repair_level",
        )

    with r3:
        repair_contingency = st.number_input(
            "Repair contingency %",
            min_value=0,
            max_value=50,
            value=12,
            step=1,
            key="repair_contingency",
        )
    uploaded_repair_files = st.file_uploader(
        "Upload property photos or boots-on-ground walkthrough video",
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"],
        accept_multiple_files=True,
        key="repair_media_files",
    )
    media_files_for_notes = uploaded_repair_files or []

    photo_files_for_notes = [
        f for f in media_files_for_notes
        if str(getattr(f, "name", "")).lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    video_files_for_notes = [
        f for f in media_files_for_notes
        if str(getattr(f, "name", "")).lower().endswith((".mp4", ".mov", ".m4v", ".avi"))
    ]

    selected_video_for_notes = video_files_for_notes[0] if video_files_for_notes else None

    if st.button("Generate boots-on-ground notes from media", type="secondary"):
        if not photo_files_for_notes and selected_video_for_notes is None:
            st.warning("Upload at least one photo or video first.")
        else:
            with st.spinner("Reviewing uploaded photos/video frames and writing boots-on-ground notes..."):
                generated_notes = generate_boots_on_ground_notes(
                    photo_files_for_notes,
                    selected_video_for_notes,
                )

            st.session_state["repair_notes"] = generated_notes
            st.success("Boots-on-ground notes created. Review them below, then click Generate Repair Estimate.") 
    repair_notes = st.text_area(
        "Boots-on-ground repair notes",
        height=140,
        key="repair_notes",
        placeholder=(
            "Example: Roof looks old, kitchen needs cabinets, bathroom floor is soft, "
            "furnace missing, water heater old, windows damaged, trash out needed."
        ),
    )

    generate_repair_estimate = st.button("Generate Repair Estimate", type="secondary")

    if generate_repair_estimate:
        repair_analysis = analyze_repairs(
            notes=st.session_state.get("repair_notes", ""),
            sqft=float(st.session_state.get("sqft", 0) or 1000),
            baths=float(st.session_state.get("baths", 0) or 1),
            uploaded_files=uploaded_repair_files,
            market=st.session_state.get("repair_market", "Central IL"),
            repair_level=st.session_state.get("repair_level", "Rental Ready"),
            contingency_pct=float(st.session_state.get("repair_contingency", 12) or 0) / 100,
        )

        st.session_state["repair_analysis"] = repair_analysis
        st.session_state["recommended_repairs_from_analyzer"] = repair_number_for_offer(repair_analysis)

    if st.session_state.get("repair_analysis"):
        repair_analysis = st.session_state["repair_analysis"]
        estimate = repair_analysis.get("estimate", {})

        st.markdown("#### Repair Estimate Result")

        e1, e2, e3, e4 = st.columns(4)

        with e1:
            st.metric("Low Repairs", money(estimate.get("total_low", 0)))

        with e2:
            st.metric("Likely Repairs", money(estimate.get("total_likely", 0)))

        with e3:
            st.metric("High Repairs", money(estimate.get("total_high", 0)))

        with e4:
            st.metric("Use In Offer", money(repair_analysis.get("recommended_repair_number", 0)))

        st.info(f"Confidence: {repair_analysis.get('confidence', 'Low')}")

        if repair_analysis.get("red_flags"):
            st.error(
                "Red flags needing contractor quote: "
                + ", ".join(repair_analysis.get("red_flags", []))
            )

        line_items = estimate.get("line_items", [])

        if line_items:
            st.dataframe(
                pd.DataFrame(line_items)[
                    ["category", "label", "quantity", "unit", "low", "likely", "high", "notes"]
                ],
                use_container_width=True,
            )

        st.text_area(
            "Repair estimate summary",
            value=repair_analysis.get("summary", ""),
            height=260,
        )

        if st.button("Use likely repair number in offer", type="primary"):
            st.session_state["repairs"] = int(repair_analysis.get("recommended_repair_number", 0) or 0)
            st.session_state["repair_source"] = "AI Repair Estimate"
            st.success("Repair number copied into Estimated repairs. Scroll down and confirm it before analyzing the deal.")
    st.markdown("### Manual Repair Estimate")
    st.caption("Use this when you already know the repair number. Manual repair estimate overrides the AI repair estimate.")
    st.number_input(
        "Manual repair estimate amount",
        min_value=0,
        step=1000,
        key="manual_repair_estimate",
    )
    st.text_area(
        "Repair notes / scope",
        height=100,
        key="manual_repair_notes",
        placeholder="Example: Roof patch, kitchen refresh, LVP, paint, trash out.",
    )

    resolved_repairs, repair_source = resolve_repair_source()
    if resolved_repairs > 0:
        st.session_state["repairs"] = int(resolved_repairs)
    st.session_state["repair_source"] = repair_source
    st.info(f"Repair Source: {repair_source}")

    st.markdown("### Manual Comp Entry Fallback")
    st.caption("Use this when RentCast cannot find value/comps. Enter 1 to 5 sold or listed comps.")

    comp_rows = []
    for idx in range(1, 6):
        with st.expander(f"Comparable Property {idx}", expanded=(idx == 1)):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.text_input("Address", key=f"manual_comp_{idx}_address")
            with c2:
                st.number_input(
                    "Sold/list price",
                    min_value=0,
                    step=1000,
                    key=f"manual_comp_{idx}_price",
                )

            c3, c4, c5 = st.columns(3)
            with c3:
                st.number_input("Beds", min_value=0.0, step=0.5, key=f"manual_comp_{idx}_beds")
            with c4:
                st.number_input("Baths", min_value=0.0, step=0.5, key=f"manual_comp_{idx}_baths")
            with c5:
                st.number_input("Sqft", min_value=0, step=50, key=f"manual_comp_{idx}_sqft")

            st.text_input("Condition", key=f"manual_comp_{idx}_condition")
            st.text_area("Notes", height=80, key=f"manual_comp_{idx}_notes")

        price = safe_float(st.session_state.get(f"manual_comp_{idx}_price", 0))
        if price > 0:
            comp_rows.append(
                {
                    "address": st.session_state.get(f"manual_comp_{idx}_address", ""),
                    "sold/list price": price,
                    "beds": st.session_state.get(f"manual_comp_{idx}_beds", 0),
                    "baths": st.session_state.get(f"manual_comp_{idx}_baths", 0),
                    "sqft": st.session_state.get(f"manual_comp_{idx}_sqft", 0),
                    "condition": st.session_state.get(f"manual_comp_{idx}_condition", ""),
                    "notes": st.session_state.get(f"manual_comp_{idx}_notes", ""),
                }
            )

    comps_average = manual_comps_average()
    st.metric("Average comp value", money(comps_average))
    if comp_rows:
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

    st.number_input(
        "Manual ARV override",
        min_value=0,
        step=1000,
        key="manual_arv_override",
        help="Highest priority. Use this when you want to override RentCast, sheet ARV, or manual comps.",
    )

    resolved_arv, value_source = resolve_value_source()
    st.session_state["arv"] = int(resolved_arv) if resolved_arv > 0 else 0
    st.session_state["value_source"] = value_source

    st.markdown("### Value / Wholesale Reference")
    st.caption(f"Value Source: {value_source}")

    market_profile = get_market_profile(st.session_state.get("repair_market", "Central IL"))
    market_buy_box_max, market_buy_box_source = resolve_market_buy_box_max(st.session_state.get("repair_market", "Central IL"))
    st.session_state["market_buy_box_max_used"] = int(market_buy_box_max) if market_buy_box_max > 0 else 0
    st.session_state["market_buy_box_max_source"] = market_buy_box_source
    market_default_buyer_percent = get_market_wholesale_buyer_percent(st.session_state.get("repair_market", "Central IL"))
    market_buyer_percent, market_adjustments = market_wholesale_percent_used(
        market=st.session_state.get("repair_market", "Central IL"),
        arv=float(st.session_state.get("arv", 0) or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
        notes=st.session_state.get("notes", ""),
        repair_notes=st.session_state.get("repair_notes", "") + " " + st.session_state.get("manual_repair_notes", ""),
    )
    final_wholesale_buyer_percent = float(wholesale_buyer_percent_arv) if manual_wholesale_override else market_buyer_percent
    wholesale_buyer_percent_source = "Manual Override" if manual_wholesale_override else "Market Default"

    p1, p2, p3 = st.columns(3)
    p1.info(f"Market Profile: {market_profile.get('buyer_profile', 'Normal investor market')}")
    p2.info(f"Market Repair Multiplier: {float(market_profile.get('repair_multiplier', 1.0)):.2f}x")
    p3.info(f"Wholesale Buyer % Source: {wholesale_buyer_percent_source}")
    if market_buy_box_max > 0:
        st.caption(f"Market Buy Box Max: {money(market_buy_box_max)} ({market_buy_box_source})")
    st.caption(f"Market buyer % of ARV used: {percent_label(final_wholesale_buyer_percent)}")
    if not manual_wholesale_override and market_adjustments:
        st.caption(" ".join(market_adjustments))

    v1, v2 = st.columns(2)

    with v1:
        st.number_input(
            "ARV / estimated resale value",
            min_value=0,
            step=1000,
            key="arv",
            help="Required on every deal. Auto-filled from RentCast, sheet ARV, manual comps, or manual override.",
        )

    with v2:
        st.number_input(
            "Estimated repairs",
            min_value=0,
            step=1000,
            key="repairs",
            help="Use $0 only when repairs are truly unknown or not needed for the slow-flip decision.",
        )

    if float(st.session_state.get("arv", 0) or 0) <= 0:
        st.warning("ARV is missing. Add ARV or manual comps before making a final offer.")

st.text_area("Seller/agent notes, condition, occupancy, motivation", height=120, key="notes")
st.caption(f"Current source: {st.session_state.get('source_mode')} / {st.session_state.get('lead_source')}")

analyze = st.button("Analyze Deal", type="primary")

if analyze:
    asking_price_value = float(st.session_state.get("asking_price", 0) or 0)
    contract_price_value = float(st.session_state.get("contract_price", 0) or 0)
    analysis_price = contract_price_value if contract_price_value > 0 else asking_price_value
    resolved_arv, value_source = resolve_value_source()
    st.session_state["value_source"] = value_source

    if resolved_arv <= 0:
        st.warning("ARV is missing. Add ARV or manual comps before making a final offer.")

    market_buy_box_max, market_buy_box_source = resolve_market_buy_box_max(st.session_state.get("repair_market", "Central IL"))
    st.session_state["market_buy_box_max_used"] = int(market_buy_box_max) if market_buy_box_max > 0 else 0
    st.session_state["market_buy_box_max_source"] = market_buy_box_source
    market_default_buyer_percent = get_market_wholesale_buyer_percent(st.session_state.get("repair_market", "Central IL"))
    final_wholesale_buyer_percent, market_adjustments = market_wholesale_percent_used(
        market=st.session_state.get("repair_market", "Central IL"),
        arv=float(resolved_arv or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
        notes=st.session_state.get("notes", ""),
        repair_notes=st.session_state.get("repair_notes", "") + " " + st.session_state.get("manual_repair_notes", ""),
    )
    if manual_wholesale_override:
        final_wholesale_buyer_percent = float(wholesale_buyer_percent_arv)
    wholesale_buyer_percent_source = "Manual Override" if manual_wholesale_override else "Market Default"

    assumptions = Assumptions(
        min_assignment_fee=float(min_assignment_fee),
        exception_assignment_fee=float(exception_assignment_fee),
        slow_flip_rent_multiple=float(slow_flip_rent_multiple),
        close_title_buffer=float(close_title_buffer),
        target_offer_discount=float(target_offer_discount),
        wholesale_buyer_percent_arv=float(final_wholesale_buyer_percent),
        wholesale_buyer_percent_source=wholesale_buyer_percent_source,
        market_wholesale_buyer_percent=float(market_default_buyer_percent),
        slow_flip_max_offer_cap=float(slow_flip_max_offer_cap),
        slow_flip_first_offer_gap=float(slow_flip_first_offer_gap),
    )

    deal = DealInput(
        address=st.session_state["address"],
        market=st.session_state["market"],
        lead_type=st.session_state["lead_type"],
        exit_mode=exit_mode,
        asking_price=analysis_price,
        rent=float(st.session_state["rent"]),
        beds=float(st.session_state["beds"]),
        baths=float(st.session_state["baths"]),
        sqft=float(st.session_state["sqft"]),
        taxes=float(st.session_state["taxes"]),
        status=st.session_state["status"],
        occupancy=st.session_state["occupancy"],
        livable=st.session_state["livable"],
        days_on_market=int(st.session_state["days_on_market"]),
        notes=st.session_state["notes"],
        arv=float(resolved_arv or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
    )

    result = analyze_deal(deal, assumptions)
    best = result["best"]

    st.divider()
    final_summary = render_final_decision_box(
        result=result,
        deal=deal,
        value_source=value_source,
        uploaded_files=uploaded_repair_files,
        repair_notes=st.session_state.get("repair_notes", ""),
        assumptions=assumptions,
    )
    deal_log_row = build_deal_log_row(
        result=result,
        deal=deal,
        final_summary=final_summary,
        value_source=value_source,
        asking_price=asking_price_value,
        contract_price=contract_price_value,
    )
    render_save_deal_analysis(deal_log_row)

    st.divider()
    st.subheader("Decision")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Deal Grade", result["grade"])
    m2.metric("Best Exit", result["best_exit"])
    m3.metric("First Offer", money(best.get("offer_to_send", best.get("target_offer_low", 0))))
    m4.metric("Internal Max", money(best["max_offer"]))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Slow Flip Numbers")
        slow = result["slow_flip"]
        st.write({
            "Resale to slow flipper": money(slow["resale_to_slow_flipper"]),
            "First offer to send": money(slow.get("offer_to_send", 0)),
            "Internal max offer": money(slow["max_offer"]),
            "Rent formula max before cap": money(slow.get("rent_formula_max_offer_before_cap", 0)),
            "Normal slow flip cap": money(slow.get("normal_slow_flip_cap", 0)),
            "Estimated fee at buy price": money(slow["estimated_fee_at_ask"]),
        })
        slow_resale_value = float(slow.get("resale_to_slow_flipper", 0) or 0)
        buyer_payment_support = float(st.session_state.get("rent", 0) or 0)
        annual_taxes_value = float(st.session_state.get("taxes", 0) or 0)

        if slow_resale_value >= 50000 and (buyer_payment_support < 1200 or annual_taxes_value > 1500):
            st.warning("$50k+ slow-flip resale warning: still show the resale price, but only push it hard if buyer payment support is about $1,200/month and taxes are low enough.")
    with c2:
        st.subheader("Value / Wholesale Reference")
        wholesale = result["wholesale"]
        st.write({
        "ARV / estimated value": money(resolved_arv),
        "Value Source": value_source,
        "Market Buy Box Max": money(market_buy_box_max) if market_buy_box_max > 0 else "Not set",
        "Repairs": money(st.session_state.get("repairs", 0)),
        "Wholesale Buyer % Source": wholesale.get("buyer_percent_source", ""),
        "Market buyer % of ARV used": percent_label(wholesale.get("buyer_percent_arv", 0)),
        "Buyer target": money(wholesale["buyer_target"]),
        "Wholesale max offer": money(wholesale["max_offer"]),
        "Wholesale estimated fee at buy price": money(wholesale["estimated_fee_at_ask"])
        })

    st.subheader("Risk Notes")
    for risk in result["risks"]:
        st.warning(risk)

    st.subheader("Suggested Message")
    st.text_area("Copy/paste message", result["suggested_message"], height=180)

    with st.expander("AI Summary - optional if OpenAI key is added"):
        ai_summary = build_ai_summary(result)
        if ai_summary:
            st.write(ai_summary)
        else:
            st.info("No OpenAI key found. Add OPENAI_API_KEY in Streamlit secrets later to enable this section.")

    with st.expander("Download Analysis CSV"):
        row = {
            **deal_log_row,
            "grade": result["grade"],
            "final_decision": final_summary["final_decision"],
            "team_action": final_summary["team_action"],
            "missing_info": "; ".join(final_summary["missing_info"]),
            "risk_flags": "; ".join(final_summary["risk_flags"]),
            "decision_reason": final_summary["decision_reason"],
            "exit_mode": exit_mode,
            "internal_max_offer": best["max_offer"],
            "estimated_fee_at_ask": best["estimated_fee_at_ask"],
            "livable": st.session_state["livable"],
            "occupancy": st.session_state["occupancy"],
        }
        df = pd.DataFrame([row])
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "Download CSV",
            data=df.to_csv(index=False),
            file_name="offer_engine_analysis.csv",
            mime="text/csv",
        )
else:
    st.info("Enter or pull the property data, then click Analyze Deal.")
