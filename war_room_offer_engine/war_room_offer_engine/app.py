from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Developer validation before merge:
# python -m py_compile war_room_offer_engine/war_room_offer_engine/app.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/rules.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/repair_analyzer.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/repair_price_book_il.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/data_sources.py
# python war_room_offer_engine/war_room_offer_engine/startup_smoke_test.py

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for import_path in [str(REPO_ROOT), str(APP_DIR)]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)

try:
    _rules_spec = importlib.util.spec_from_file_location("war_room_offer_engine_local_rules", APP_DIR / "rules.py")
    if _rules_spec is None or _rules_spec.loader is None:
        raise ImportError("Could not load local rules.py")
    _rules_module = importlib.util.module_from_spec(_rules_spec)
    sys.modules[_rules_spec.name] = _rules_module
    _rules_spec.loader.exec_module(_rules_module)
    Assumptions = _rules_module.Assumptions
    DealInput = _rules_module.DealInput
    analyze_deal = _rules_module.analyze_deal
    money = _rules_module.money
except ImportError:
    try:
        from .rules import Assumptions, DealInput, analyze_deal, money
    except ImportError:
        try:
            from war_room_offer_engine.rules import Assumptions, DealInput, analyze_deal, money
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.rules import Assumptions, DealInput, analyze_deal, money

try:
    from ai_writer import build_ai_summary
except ImportError:
    try:
        from .ai_writer import build_ai_summary
    except ImportError:
        try:
            from war_room_offer_engine.ai_writer import build_ai_summary
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.ai_writer import build_ai_summary

try:
    from data_sources import (
        fetch_all_sources,
        merge_results,
        get_secret,
        parse_listing_text,
        provider_connection_status,
    )
except ImportError:
    try:
        from .data_sources import (
            fetch_all_sources,
            merge_results,
            get_secret,
            parse_listing_text,
            provider_connection_status,
        )
    except ImportError:
        try:
            from war_room_offer_engine.data_sources import (
                fetch_all_sources,
                merge_results,
                get_secret,
                parse_listing_text,
                provider_connection_status,
            )
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.data_sources import (
                fetch_all_sources,
                merge_results,
                get_secret,
                parse_listing_text,
                provider_connection_status,
            )

try:
    from repair_analyzer import analyze_repairs, repair_number_for_offer
except ImportError:
    try:
        from .repair_analyzer import analyze_repairs, repair_number_for_offer
    except ImportError:
        try:
            from war_room_offer_engine.repair_analyzer import analyze_repairs, repair_number_for_offer
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.repair_analyzer import analyze_repairs, repair_number_for_offer

try:
    from repair_price_book_il import (
        available_markets,
        get_market_profile,
        get_market_slow_flip_lead_search_max,
        get_market_slow_flip_max_buy_price,
        get_market_wholesale_buyer_percent,
    )
except ImportError:
    try:
        from .repair_price_book_il import (
            available_markets,
            get_market_profile,
            get_market_slow_flip_lead_search_max,
            get_market_slow_flip_max_buy_price,
            get_market_wholesale_buyer_percent,
        )
    except ImportError:
        try:
            from war_room_offer_engine.repair_price_book_il import (
                available_markets,
                get_market_profile,
                get_market_slow_flip_lead_search_max,
                get_market_slow_flip_max_buy_price,
                get_market_wholesale_buyer_percent,
            )
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.repair_price_book_il import (
                available_markets,
                get_market_profile,
                get_market_slow_flip_lead_search_max,
                get_market_slow_flip_max_buy_price,
                get_market_wholesale_buyer_percent,
            )

try:
    from media_notes import generate_boots_on_ground_notes
except ImportError:
    try:
        from .media_notes import generate_boots_on_ground_notes
    except ImportError:
        try:
            from war_room_offer_engine.media_notes import generate_boots_on_ground_notes
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.media_notes import generate_boots_on_ground_notes
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
    "repair_pricing_mode": "Investor standard",
    "repair_scope_confidence": "Unknown",
    "market_labor_cost": "Unknown",
    "repair_cushion_percent": "10%",
    "manual_repair_adjustment": 0,
    "show_full_repair_math": False,
    "manual_slow_flip_max_override": 0,
    "mold_verified": "Unknown",
    "listing_url": "",
    "listing_text": "",
    "data_intake_source": "Zillow manual/pasted",
    "city": "",
    "state": "",
    "zip": "",
    "lot_size": "",
    "year_built": "",
    "property_type": "",
    "listing_agent_name": "",
    "listing_agent_phone": "",
    "listing_agent_email": "",
    "listing_brokerage": "",
    "tax_assessed_value": 0,
    "last_sale_date": "",
    "last_sale_price": 0,
    "owner_name": "",
    "comp_source": "",
    "county_tax_gis_link": "",
    "market_type": "Auto",
    "buyer_demand_confidence": "Medium",
    "exit_confidence": "Medium",
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


def mold_word_allowed() -> bool:
    return st.session_state.get("mold_verified") in [
        "Yes - inspector verified",
        "Yes - seller disclosed",
    ]


def mold_verified_bool() -> bool:
    return mold_word_allowed()


def safe_condition_text(text: str) -> str:
    if mold_word_allowed():
        return str(text or "")
    replacements = {
        "black mold": "suspected biological growth",
        "mold remediation": "moisture/biological growth verification allowance",
        "visible mold": "visible discoloration",
        "mold": "moisture staining/discoloration",
    }
    clean = str(text or "")
    for old, new in replacements.items():
        clean = re.sub(old, new, clean, flags=re.IGNORECASE)
    return clean


def condition_wording_used() -> str:
    if mold_word_allowed():
        return "Verified mold wording allowed"
    return "Moisture staining/discoloration observed. Further verification needed."


def format_percent_range(low: float, high: float) -> str:
    return f"{low * 100:.0f}% to {high * 100:.0f}%"


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


def advanced_wholesale_buyer_model(
    market: str,
    arv: float,
    repairs: float,
    notes: str,
    repair_notes: str,
    property_type: str = "",
    days_on_market: int = 0,
    buyer_demand_confidence: str = "Medium",
    market_type: str = "Auto",
    occupancy: str = "Unknown",
    livable: str = "Unknown",
    exit_confidence: str = "Medium",
) -> dict:
    market_profile = get_market_profile(market)
    buyer_profile = market_profile.get("buyer_profile", "")
    all_notes = f"{notes or ''} {repair_notes or ''} {property_type or ''}".lower()
    reasons = []

    if "strong" in buyer_profile.lower() or "very liquid" in str(market_type).lower():
        tier, low, high = "Tier A - Very liquid investor market", 0.72, 0.78
    elif "rural" in buyer_profile.lower() or "thin" in buyer_profile.lower() or "rural" in str(market_type).lower():
        tier, low, high = "Tier C - Thin / rural / slower market", 0.60, 0.67
    elif "unknown" in str(market_type).lower() or any(word in all_notes for word in ["mobile home", "manufactured home", "low ceiling", "no driveway"]):
        tier, low, high = "Tier D - Very risky / unknown / unusual property", 0.50, 0.60
    else:
        tier, low, high = "Tier B - Normal investor market", 0.68, 0.72

    buyer_percent = float(market_profile.get("wholesale_buyer_percent", (low + high) / 2) or (low + high) / 2)
    buyer_percent = min(max(buyer_percent, low), high)
    reasons.append(f"Base tier: {tier}.")

    major_red_flags = [
        "foundation",
        "structural",
        "mold",
        "moisture",
        "discoloration",
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
        "low ceiling",
        "no driveway",
    ]

    if arv > 0 and repairs > max(40000, arv * 0.25):
        buyer_percent -= 0.06
        reasons.append("Heavy repairs subtract 6%.")
    elif any(flag in all_notes for flag in major_red_flags):
        buyer_percent -= 0.05
        reasons.append("Functional or condition red flags subtract 5%.")

    if arv > 0 and arv < 75000:
        buyer_percent -= 0.04
        reasons.append("Very low ARV under $75k subtracts 4%.")
    if "rural" in all_notes or "rural" in buyer_profile.lower():
        buyer_percent -= 0.04
        reasons.append("Rural or thinner buyer pool subtracts 4%.")
    if safe_float(st.session_state.get("rent", 0)) >= 1200:
        buyer_percent += 0.02
        reasons.append("Strong rental demand adds 2%.")
    if buyer_demand_confidence == "Strong":
        buyer_percent += 0.03
        reasons.append("Strong buyer demand adds 3%.")
    elif buyer_demand_confidence == "Weak":
        buyer_percent -= 0.03
        reasons.append("Weak buyer demand subtracts 3%.")
    if any(word in all_notes for word in ["functional obsolescence", "low ceiling", "low ceilings", "no driveway", "bad layout"]):
        buyer_percent -= 0.07
        reasons.append("Functional obsolescence subtracts 7%.")
    if market_type == "Unknown":
        buyer_percent -= 0.05
        reasons.append("Unknown market subtracts 5%.")
    if exit_confidence == "Weak":
        buyer_percent -= 0.03
        reasons.append("Weak data/exit confidence subtracts 3%.")
    elif exit_confidence == "Strong":
        buyer_percent += 0.02
        reasons.append("Strong exit confidence adds 2%.")
    if st.session_state.get("repair_level") == "Investor Basic" and repairs > 0 and repairs < max(20000, arv * 0.12 if arv else 20000):
        buyer_percent += 0.03
        reasons.append("Turnkey/light cosmetic scope adds 3%.")
    if days_on_market >= 90:
        buyer_percent -= 0.04
        reasons.append("High DOM subtracts 4%.")
    elif days_on_market >= 45:
        buyer_percent -= 0.02
        reasons.append("Moderate DOM subtracts 2%.")
    if occupancy in ["Tenant occupied", "Owner occupied"] or livable == "No":
        buyer_percent -= 0.04
        reasons.append("Occupancy or livability risk subtracts 4%.")

    buyer_percent = max(min(buyer_percent, 0.78), 0.50)
    conservative_percent = max(buyer_percent - 0.03, 0.50)
    aggressive_percent = min(buyer_percent + 0.03, 0.78)
    conservative_target = max((arv * conservative_percent) - repairs, 0) if arv else 0
    aggressive_target = max((arv * aggressive_percent) - repairs, 0) if arv else 0
    recommended_max_offer = max((arv * buyer_percent) - repairs - safe_float(st.session_state.get("min_assignment_fee_snapshot", 10000)) - safe_float(st.session_state.get("close_title_buffer_snapshot", 1500)), 0) if arv else 0

    return {
        "buyer_percent": buyer_percent,
        "range": format_percent_range(conservative_percent, aggressive_percent),
        "tier": tier,
        "reasons": reasons,
        "reason_text": " ".join(reasons),
        "conservative_buyer_target": conservative_target,
        "aggressive_buyer_target": aggressive_target,
        "recommended_wholesale_max_offer": recommended_max_offer,
    }


def market_wholesale_percent_used(
    market: str,
    arv: float,
    repairs: float,
    notes: str,
    repair_notes: str,
) -> tuple[float, list[str]]:
    model = advanced_wholesale_buyer_model(market, arv, repairs, notes, repair_notes)
    return model["buyer_percent"], model["reasons"]


def resolve_slow_flip_max_buy_price(market: str) -> tuple[float, str]:
    manual_override = safe_float(st.session_state.get("manual_slow_flip_max_override", 0))
    if manual_override > 0:
        return manual_override, "Manual Override"
    return get_market_slow_flip_max_buy_price(market), "Market Default"


def is_above_slow_flip_max_buy_price(buy_price: float, slow_flip_max_buy_price: float) -> bool:
    return slow_flip_max_buy_price > 0 and safe_float(buy_price) > slow_flip_max_buy_price


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
        "listing_url": "listing_url",
        "agent_name": "listing_agent_name",
        "agent_phone": "listing_agent_phone",
        "brokerage": "listing_brokerage",
        "year_built": "year_built",
        "property_type": "property_type",
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
    if "mold" in all_notes or "discoloration" in all_notes or "moisture staining" in all_notes:
        risks.append("Verified mold mentioned in notes" if mold_word_allowed() and "mold" in all_notes else "Moisture staining/discoloration needs verification")
    if "roof leak" in all_notes or "leak in roof" in all_notes or ("roof" in all_notes and "leak" in all_notes):
        risks.append("Roof leak mentioned in notes")
    if deal.livable == "No":
        risks.append("Property not livable")
    slow_flip = result.get("slow_flip", {})
    if (
        deal.exit_mode in ["Slow Flip Only", "Auto"]
        and result.get("best_exit") != "Wholesale"
        and slow_flip.get("above_slow_flip_max_buy_price")
    ):
        risks.append("Above Slow Flip Max Buy Price")

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
    if any(flag in risk_flags for flag in ["Verified mold mentioned in notes", "Moisture staining/discoloration needs verification", "Property not livable"]):
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


def build_simple_deal_answer(result: dict, deal: DealInput, missing_info: list[str], risk_flags: list[str]) -> dict:
    best = result["best"]
    best_exit = result["best_exit"]
    grade = result["grade"]
    asking = safe_float(deal.asking_price)
    first_offer = safe_float(best.get("offer_to_send", best.get("target_offer_low", 0)))
    comfortable_max = safe_float(best.get("target_offer_high", best.get("max_offer", 0))) or safe_float(best.get("max_offer", 0))
    hard_max = safe_float(best.get("max_offer", 0))
    do_not_exceed = hard_max

    critical_missing = {"Missing ARV", "Missing rent", "Missing repairs"}.intersection(missing_info)
    high_repairs = deal.arv > 0 and deal.repairs > max(50000, deal.arv * 0.30)
    functional_risks = result.get("slow_flip", {}).get("functional_risks", [])
    wholesale_percent = safe_float(result.get("wholesale", {}).get("buyer_percent_arv", 0))

    if critical_missing or best_exit == "Needs Human Review" or functional_risks or wholesale_percent < 0.55:
        plain_answer = "Needs Human Review"
    elif best_exit == "Wholesale":
        plain_answer = "Wholesale Only"
    elif best_exit == "Slow Flip":
        plain_answer = "Slow Flip Only"
    elif high_repairs:
        plain_answer = "Pass Unless Seller Takes Steal Price"
    elif grade == "Pass" or best_exit == "Pass":
        plain_answer = "Do Not Buy"
    elif asking > hard_max > 0:
        plain_answer = "Renegotiate Hard"
    elif grade in ["A", "B"]:
        plain_answer = "Buy"
    else:
        plain_answer = "Renegotiate Hard"

    why = []
    if asking > hard_max > 0:
        why.append(f"Current price is above the hard max of {money(hard_max)}.")
    else:
        why.append(f"Current price is inside the modeled range for {best_exit}.")
    why.append(f"ARV/value source is {st.session_state.get('value_source', 'Missing')} at {money(deal.arv)}.")
    why.append(f"Rent is {money(deal.rent)} and repairs are {money(deal.repairs)}.")
    if high_repairs:
        why.append("Repairs are high compared to the ARV, so the deal needs a larger discount.")
    if functional_risks:
        why.append("Functional risks limit the buyer pool: " + ", ".join(functional_risks) + ".")
    if risk_flags:
        why.append("Main risk flag: " + safe_condition_text(risk_flags[0]) + ".")
    if critical_missing:
        why.append("Missing info must be verified first: " + ", ".join(sorted(critical_missing)) + ".")

    if "Missing repairs" in missing_info:
        next_move = "Verify repairs first"
    elif "Missing rent" in missing_info:
        next_move = "Verify rent first"
    elif any("termite" in str(flag).lower() or "structural" in str(flag).lower() or "moisture" in str(flag).lower() for flag in risk_flags):
        next_move = "Get contractor/termite inspection"
    elif plain_answer in ["Do Not Buy", "Pass Unless Seller Takes Steal Price"]:
        next_move = "Pass"
    elif plain_answer in ["Renegotiate Hard", "Needs Human Review"]:
        next_move = "Lower offer"
    elif plain_answer == "Wholesale Only" and result.get("wholesale", {}).get("buyer_percent_arv", 0) < 0.62:
        next_move = "Build buyer list first"
    else:
        next_move = "Make offer"

    confidence_score = 0
    if deal.arv > 0:
        confidence_score += 1
    if deal.rent > 0:
        confidence_score += 1
    if deal.repairs > 0:
        confidence_score += 1
    if not risk_flags:
        confidence_score += 1
    confidence = "Strong" if confidence_score >= 4 else "Medium" if confidence_score >= 2 else "Weak"
    if critical_missing or functional_risks:
        confidence = "Weak"

    one_sentence = (
        f"{plain_answer}: pursue only around {money(first_offer)} to {money(comfortable_max)} "
        f"and do not exceed {money(do_not_exceed)} unless the missing items and risks check out."
    )

    return {
        "plain_answer": plain_answer,
        "why": [safe_condition_text(item) for item in why],
        "best_next_move": next_move,
        "safe_offer_range": {
            "first_offer": first_offer,
            "comfortable_max": comfortable_max,
            "hard_max": hard_max,
            "do_not_exceed": do_not_exceed,
        },
        "confidence": confidence,
        "one_sentence_summary": safe_condition_text(one_sentence),
    }


def render_simple_deal_answer(simple_answer: dict) -> None:
    st.subheader("Simple Deal Answer")
    with st.container(border=True):
        answer = simple_answer["plain_answer"]
        if answer in ["Buy", "Wholesale Only", "Slow Flip Only"]:
            st.success(f"Plain Answer: {answer}")
        elif answer in ["Do Not Buy", "Pass Unless Seller Takes Steal Price"]:
            st.error(f"Plain Answer: {answer}")
        else:
            st.warning(f"Plain Answer: {answer}")

        st.write("Why:")
        for item in simple_answer["why"]:
            st.write(f"- {item}")

        offer_range = simple_answer["safe_offer_range"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("First offer", money(offer_range["first_offer"]))
        c2.metric("Comfortable max", money(offer_range["comfortable_max"]))
        c3.metric("Hard max", money(offer_range["hard_max"]))
        c4.metric("Do not exceed", money(offer_range["do_not_exceed"]))
        n1, n2 = st.columns(2)
        n1.info(f"Best Next Move: {simple_answer['best_next_move']}")
        n2.info(f"Confidence: {simple_answer['confidence']}")
        st.write(simple_answer["one_sentence_summary"])


def repair_source_label() -> str:
    manual = safe_float(st.session_state.get("manual_repair_estimate", 0))
    ai = safe_float(st.session_state.get("recommended_repairs_from_analyzer", 0))
    if manual > 0:
        return "Manual Repair Estimate"
    if ai > 0:
        return "AI Repair Estimate"
    return "Missing"


def repair_cushion_percent_value() -> float:
    raw_value = st.session_state.get("repair_cushion_percent", "0%")
    return safe_float(str(raw_value).replace("%", ""), 0)


def repair_calibration_from_analysis() -> dict:
    analysis = st.session_state.get("repair_analysis") or {}
    return analysis.get("repair_calibration", {}) or {}


def build_repair_breakdown() -> dict:
    analysis = st.session_state.get("repair_analysis") or {}
    estimate = analysis.get("estimate", {})
    calibration = repair_calibration_from_analysis()
    line_items = []
    for item in estimate.get("line_items", []) or []:
        line_items.append(
            {
                "Category": safe_condition_text(item.get("category", "")),
                "Issue": safe_condition_text(item.get("label", "")),
                "Quantity/Severity": item.get("quantity", ""),
                "Unit price or allowance": money(item.get("base_estimate", item.get("likely", 0))),
                "Market multiplier": item.get("market_multiplier", estimate.get("market_multiplier", "")),
                "Market Adjustment": money(item.get("market_adjustment", 0)),
                "Risk Adjustment": money(item.get("risk_adjustment", 0)),
                "Final Estimate": money(item.get("final_estimate", item.get("likely", 0))),
                "Notes": safe_condition_text(item.get("notes", "")),
            }
        )

    triggers = []
    notes = f"{st.session_state.get('repair_notes', '')} {st.session_state.get('manual_repair_notes', '')}".lower()
    trigger_terms = [
        "termite", "structural", "flooring", "kitchen", "bath", "roof", "electrical",
        "plumbing", "hvac", "full cosmetic", "paint", "drywall", "moisture", "water damage",
        "discoloration", "mold", "crawlspace", "septic", "well", "flood",
    ]
    for term in trigger_terms:
        if term in notes:
            triggers.append(safe_condition_text(term))

    total_repairs = safe_float(st.session_state.get("repairs", 0))
    if not total_repairs:
        total_repairs = safe_float(analysis.get("recommended_repair_number", 0))

    confidence = str(analysis.get("confidence", "Low - not enough repair information"))
    if confidence.startswith("High"):
        confidence_label = "High"
    elif confidence.startswith("Medium"):
        confidence_label = "Medium"
    else:
        confidence_label = "Low"

    explanation = "Repair estimate is based on manual input." if safe_float(st.session_state.get("manual_repair_estimate", 0)) > 0 else calibration.get("repair_number_explanation", "Repair estimate is based on price-book items detected from notes/media.")
    if triggers:
        explanation += " Repairs are driven by: " + ", ".join(sorted(set(triggers))) + "."
    if total_repairs > 50000:
        explanation += " High repair estimate warning: this number is driven by the major items listed in the breakdown."

    return {
        "total_estimated_repairs": total_repairs,
        "repair_confidence": confidence_label,
        "repair_source": repair_source_label(),
        "line_items": line_items,
        "note_triggers": sorted(set(triggers)),
        "market_multiplier": analysis.get("market_repair_multiplier", ""),
        "risk_allowance": estimate.get("contingency_pct", 0),
        "repair_explanation": safe_condition_text(explanation),
        "repair_calibration": calibration,
    }


def render_repair_number_explanation(calibration: dict) -> None:
    if not calibration:
        return

    st.subheader("Repair Number Explanation")
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Base repair estimate", money(calibration.get("base_repair_estimate", 0)))
        c2.metric("Pricing mode adjustment", money(calibration.get("repair_pricing_adjustment", 0)))
        c3.metric("Market labor adjustment", money(calibration.get("market_labor_adjustment", 0)))

        c4, c5, c6 = st.columns(3)
        c4.metric("Repair cushion", money(calibration.get("repair_risk_cushion", 0)))
        c5.metric("Manual adjustment", money(calibration.get("manual_repair_adjustment", 0)))
        c6.metric("Final repair estimate", money(calibration.get("final_repair_estimate", 0)))

        st.write(safe_condition_text(calibration.get("repair_number_explanation", "")))
        for warning in calibration.get("caution_warnings", []):
            st.warning(safe_condition_text(warning))

        if st.session_state.get("show_full_repair_math", False):
            rows = calibration.get("repair_math_rows", [])
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.info("No repair math rows yet. Generate a repair estimate from notes/media first.")


def render_repair_estimate_breakdown(breakdown: dict) -> None:
    st.subheader("Repair Estimate Breakdown")
    with st.container(border=True):
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Total estimated repairs", money(breakdown.get("total_estimated_repairs", 0)))
        r2.metric("Repair confidence", breakdown.get("repair_confidence", "Low"))
        r3.metric("Repair source", breakdown.get("repair_source", "Missing"))
        r4.metric("Market multiplier", breakdown.get("market_multiplier", ""))
        if safe_float(breakdown.get("total_estimated_repairs", 0)) > 50000:
            st.warning("High repair estimate warning: this number is driven by the following major items.")
        st.write(breakdown.get("repair_explanation", ""))
        if breakdown.get("note_triggers"):
            st.caption("Note triggers: " + ", ".join(breakdown["note_triggers"]))
        if breakdown.get("line_items"):
            st.dataframe(pd.DataFrame(breakdown["line_items"]), use_container_width=True)
        else:
            st.info("No price-book line items yet. Enter repair notes, upload media, or add a manual repair estimate.")
    render_repair_number_explanation(breakdown.get("repair_calibration", {}))


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
    simple_answer = build_simple_deal_answer(result, deal, missing_info, risk_flags)

    render_simple_deal_answer(simple_answer)
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

        slow = result.get("slow_flip", {})
        s1, s2, s3 = st.columns(3)
        s1.metric(
            "Slow Flip Lead Search Max",
            money(st.session_state.get("slow_flip_lead_search_max", 0))
            if st.session_state.get("slow_flip_lead_search_max", 0)
            else "Not set",
        )
        s2.metric(
            "Slow Flip Max Buy Price",
            money(slow.get("slow_flip_max_buy_price", 0))
            if slow.get("slow_flip_max_buy_price", 0)
            else "Not set",
        )
        s3.metric("Above Slow Flip Max Buy Price?", "Yes" if slow.get("above_slow_flip_max_buy_price") else "No")

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
                    st.warning(safe_condition_text(item))
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
        "simple_answer": simple_answer,
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
    simple_answer = final_summary.get("simple_answer", {})
    offer_range = simple_answer.get("safe_offer_range", {})
    repair_breakdown = build_repair_breakdown()
    wholesale = result.get("wholesale", {})
    slow_flip_lead_search_max = get_market_slow_flip_lead_search_max(st.session_state.get("repair_market", "Central IL"))
    slow_flip_max_buy_price, slow_flip_max_source = resolve_slow_flip_max_buy_price(st.session_state.get("repair_market", "Central IL"))
    above_slow_flip_max_buy_price = (
        deal.exit_mode in ["Slow Flip Only", "Auto"]
        and is_above_slow_flip_max_buy_price(deal.asking_price, slow_flip_max_buy_price)
    )
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
        "slow_flip_lead_search_max": slow_flip_lead_search_max,
        "slow_flip_max_buy_price": slow_flip_max_buy_price,
        "above_slow_flip_max_buy_price": "Yes" if above_slow_flip_max_buy_price else "No",
        "slow_flip_max_source": slow_flip_max_source,
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
        "repair_pricing_mode": st.session_state.get("repair_pricing_mode", "Investor standard"),
        "repair_scope_confidence": st.session_state.get("repair_scope_confidence", "Unknown"),
        "market_labor_cost": st.session_state.get("market_labor_cost", "Unknown"),
        "manual_repair_adjustment": st.session_state.get("manual_repair_adjustment", 0),
        "repair_cushion_percent": repair_cushion_percent_value(),
        "base_repair_estimate": repair_breakdown.get("repair_calibration", {}).get("base_repair_estimate", 0),
        "repair_pricing_adjustment": repair_breakdown.get("repair_calibration", {}).get("repair_pricing_adjustment", 0),
        "repair_risk_cushion": repair_breakdown.get("repair_calibration", {}).get("repair_risk_cushion", 0),
        "final_repair_estimate": repair_breakdown.get("repair_calibration", {}).get("final_repair_estimate", deal.repairs),
        "repair_number_explanation": repair_breakdown.get("repair_calibration", {}).get("repair_number_explanation", ""),
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
        "simple_deal_answer": simple_answer.get("plain_answer", ""),
        "plain_english_why": " | ".join(simple_answer.get("why", [])),
        "best_next_move": simple_answer.get("best_next_move", ""),
        "safe_offer_range": f"{money(offer_range.get('first_offer', 0))} to {money(offer_range.get('comfortable_max', 0))}",
        "hard_do_not_exceed_price": offer_range.get("do_not_exceed", 0),
        "decision_confidence": simple_answer.get("confidence", ""),
        "repair_breakdown_json": json.dumps(repair_breakdown.get("line_items", [])),
        "repair_explanation": repair_breakdown.get("repair_explanation", ""),
        "repair_confidence": repair_breakdown.get("repair_confidence", ""),
        "condition_wording_used": condition_wording_used(),
        "mold_verified": st.session_state.get("mold_verified", "Unknown"),
        "wholesale_buyer_percent_range": wholesale.get("buyer_percent_range", ""),
        "wholesale_buyer_percent_reason": wholesale.get("buyer_percent_reason", ""),
        "market_liquidity_tier": wholesale.get("market_liquidity_tier", ""),
        "data_intake_source": st.session_state.get("data_intake_source", ""),
        "listing_url": st.session_state.get("listing_url", ""),
        "listing_agent_name": st.session_state.get("listing_agent_name", ""),
        "listing_agent_phone": st.session_state.get("listing_agent_phone", ""),
        "listing_agent_email": st.session_state.get("listing_agent_email", ""),
        "annual_taxes": st.session_state.get("taxes", 0),
        "tax_assessed_value": st.session_state.get("tax_assessed_value", 0),
        "days_on_market": st.session_state.get("days_on_market", 0),
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
    st.selectbox("Market type", ["Auto", "Very liquid investor market", "Normal investor market", "Rural / thin buyer market", "Unknown"], key="market_type")
    st.selectbox("Buyer demand confidence", ["Strong", "Medium", "Weak"], key="buyer_demand_confidence")
    st.selectbox("Exit confidence", ["Strong", "Medium", "Weak"], key="exit_confidence")
    slow_flip_max_offer_cap = st.number_input("Normal slow flip max offer cap", min_value=0, value=32000, step=500, help="Bradley rule: 98% of slow-flip offers stay at or below this number. Use human review for exceptions.")
    slow_flip_first_offer_gap = st.number_input("Slow flip first offer below max", min_value=0, value=4000, step=500, help="Negotiation rule: do not start at max. Example: $32k max starts at $28k.")
    st.session_state["min_assignment_fee_snapshot"] = min_assignment_fee
    st.session_state["close_title_buffer_snapshot"] = close_title_buffer

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
    wholesale_buyer_percent_range="",
    wholesale_buyer_percent_reason="",
    market_liquidity_tier="",
    market_wholesale_buyer_percent=float(wholesale_buyer_percent_arv),
    slow_flip_max_offer_cap=float(slow_flip_max_offer_cap),
    slow_flip_first_offer_gap=float(slow_flip_first_offer_gap),
    slow_flip_lead_search_max=float(st.session_state.get("slow_flip_lead_search_max", 0) or 0),
    slow_flip_lead_search_source=st.session_state.get("slow_flip_lead_search_source", "Market Default"),
    above_slow_flip_lead_search_range=bool(st.session_state.get("above_slow_flip_lead_search_range", False)),
    inside_slow_flip_lead_search_range=bool(st.session_state.get("inside_slow_flip_lead_search_range", False)),
    slow_flip_max_buy_price=float(st.session_state.get("slow_flip_max_buy_price_used", 0) or 0),
    slow_flip_max_source=st.session_state.get("slow_flip_max_source", "Market Default"),
    above_slow_flip_max_buy_price=bool(st.session_state.get("above_slow_flip_max_buy_price", False)),
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

with st.expander("Lead Data Intake", expanded=False):
    st.caption("Manual/pasted/vendor intake only. This does not scrape Zillow, Redfin, Realtor.com, or other listing sites.")
    intake_cols = st.columns(3)
    with intake_cols[0]:
        st.selectbox(
            "Manual source selector",
            [
                "Zillow manual/pasted",
                "Redfin manual/pasted",
                "Realtor manual/pasted",
                "XLeads",
                "PropStream",
                "DealMachine",
                "RentCast",
                "County records",
                "MLS/manual",
                "Other",
            ],
            key="data_intake_source",
        )
        st.text_input("Manual Listing URL", key="listing_url")
    with intake_cols[1]:
        lead_intake_csv = st.file_uploader("Upload lead CSV", type=["csv"], key="lead_intake_csv")
        st.text_input("County tax/GIS manual link", key="county_tax_gis_link")
    with intake_cols[2]:
        for provider in provider_connection_status():
            st.write(("Connected: " if provider["connected"] else "API not connected - ") + provider["provider"])

    st.text_area("Paste Listing Text", height=130, key="listing_text")
    if lead_intake_csv is not None:
        try:
            lead_df = pd.read_csv(lead_intake_csv)
            st.dataframe(lead_df.head(5), use_container_width=True)
            if st.button("Use first CSV row", type="secondary"):
                first_row = lead_df.iloc[0].to_dict()
                csv_map = {
                    "address": ["property address", "address", "property_address"],
                    "asking_price": ["asking/list price", "asking price", "price", "list_price"],
                    "beds": ["beds", "bedrooms"],
                    "baths": ["baths", "bathrooms"],
                    "sqft": ["square footage", "sqft", "sq_ft"],
                    "taxes": ["annual taxes", "taxes"],
                    "days_on_market": ["days on market", "dom"],
                    "listing_url": ["listing url", "url", "listing_url"],
                }
                lower_row = {str(k).strip().lower(): v for k, v in first_row.items()}
                filled = []
                for state_key, names in csv_map.items():
                    for name in names:
                        if name in lower_row and lower_row[name] not in [None, "", 0, 0.0]:
                            st.session_state[state_key] = lower_row[name]
                            filled.append(state_key)
                            break
                st.success("Filled from CSV: " + ", ".join(filled) if filled else "Needs manual entry.")
        except Exception as e:
            st.warning(f"Could not read CSV yet: {e}")

    if st.button("Parse pasted listing text", type="secondary"):
        parsed = parse_listing_text(st.session_state.get("listing_text", ""))
        field_map = {
            "address": "address",
            "city": "city",
            "state": "state",
            "zip": "zip",
            "asking_price": "asking_price",
            "beds": "beds",
            "baths": "baths",
            "sqft": "sqft",
            "lot_size": "lot_size",
            "year_built": "year_built",
            "property_type": "property_type",
            "days_on_market": "days_on_market",
            "listing_status": "status",
            "agent_name": "listing_agent_name",
            "agent_phone": "listing_agent_phone",
            "agent_email": "listing_agent_email",
            "listing_brokerage": "listing_brokerage",
            "tax_assessed_value": "tax_assessed_value",
            "annual_taxes": "taxes",
            "last_sale_date": "last_sale_date",
            "last_sale_price": "last_sale_price",
            "owner_name": "owner_name",
            "rent_estimate": "rent",
            "arv_estimate": "manual_arv_override",
            "comp_source": "comp_source",
        }
        updated = []
        for parsed_key, state_key in field_map.items():
            value = parsed.get(parsed_key)
            if value not in [None, "", 0, 0.0]:
                st.session_state[state_key] = value
                updated.append(state_key)
        if updated:
            st.success("Parsed and filled: " + ", ".join(updated))
        else:
            st.info("Needs manual entry.")

    lead_detail_cols = st.columns(4)
    with lead_detail_cols[0]:
        st.text_input("City", key="city")
        st.text_input("State", key="state")
        st.text_input("Zip", key="zip")
    with lead_detail_cols[1]:
        st.text_input("Lot size", key="lot_size")
        st.text_input("Year built", key="year_built")
        st.text_input("Property type", key="property_type")
    with lead_detail_cols[2]:
        st.text_input("Listing agent name", key="listing_agent_name")
        st.text_input("Listing agent phone", key="listing_agent_phone")
        st.text_input("Listing agent email", key="listing_agent_email")
    with lead_detail_cols[3]:
        st.text_input("Listing brokerage", key="listing_brokerage")
        st.number_input("Tax assessed value", min_value=0, step=1000, key="tax_assessed_value")
        st.text_input("Comp source", key="comp_source")

    sale_cols = st.columns(3)
    with sale_cols[0]:
        st.text_input("Last sale date", key="last_sale_date")
    with sale_cols[1]:
        st.number_input("Last sale price", min_value=0, step=1000, key="last_sale_price")
    with sale_cols[2]:
        st.text_input("Owner name if available from approved source", key="owner_name")

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
        "Manual Slow Flip Max Override",
        min_value=0,
        step=5000,
        key="manual_slow_flip_max_override",
        help="Leave at $0 to use the market default. Every Virginia market defaults to a $50,000 slow-flip max buy price.",
    )
    slow_flip_lead_search_max = get_market_slow_flip_lead_search_max(st.session_state.get("repair_market", "Central IL"))
    slow_flip_max_buy_price, slow_flip_max_source = resolve_slow_flip_max_buy_price(st.session_state.get("repair_market", "Central IL"))
    current_slow_flip_price = safe_float(st.session_state.get("contract_price", 0)) or safe_float(st.session_state.get("asking_price", 0))
    st.session_state["slow_flip_lead_search_max"] = int(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else 0
    st.session_state["slow_flip_lead_search_source"] = "Market Default"
    st.session_state["above_slow_flip_lead_search_range"] = bool(slow_flip_lead_search_max > 0 and current_slow_flip_price > slow_flip_lead_search_max)
    st.session_state["inside_slow_flip_lead_search_range"] = bool(slow_flip_lead_search_max > 0 and current_slow_flip_price <= slow_flip_lead_search_max)
    st.session_state["slow_flip_max_buy_price_used"] = int(slow_flip_max_buy_price) if slow_flip_max_buy_price > 0 else 0
    st.session_state["slow_flip_max_source"] = slow_flip_max_source
    st.session_state["above_slow_flip_max_buy_price"] = bool(
        slow_flip_max_buy_price > 0 and current_slow_flip_price > slow_flip_max_buy_price
    )
    if slow_flip_lead_search_max > 0:
        st.info(f"Slow Flip Lead Search Max: {money(slow_flip_lead_search_max)}")
    if slow_flip_max_buy_price > 0:
        st.info(f"Slow Flip Max Buy Price: {money(slow_flip_max_buy_price)} ({slow_flip_max_source})")
    else:
        st.info("Slow Flip Max Buy Price: Not set")

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
    st.markdown("### Repair Pricing Settings")
    pset1, pset2 = st.columns(2)
    with pset1:
        st.selectbox(
            "Pricing Mode",
            [
                "Budget handyman",
                "Investor standard",
                "Licensed contractor",
                "Conservative high-risk",
            ],
            key="repair_pricing_mode",
            help="Changes how the app calibrates the price-book estimate against contractor reality.",
        )
        st.selectbox(
            "Market Labor Cost",
            [
                "Low-cost market",
                "Normal market",
                "High-cost market",
                "Unknown",
            ],
            key="market_labor_cost",
        )
        st.number_input(
            "Manual Repair Adjustment",
            step=500,
            key="manual_repair_adjustment",
            help="Add or subtract dollars from the calculated repair estimate. Manual repair estimate below still overrides everything.",
        )
    with pset2:
        st.selectbox(
            "Repair Scope Confidence",
            [
                "Photos only",
                "Walkthrough",
                "Contractor verified",
                "Unknown",
            ],
            key="repair_scope_confidence",
        )
        st.selectbox(
            "Repair Cushion",
            [
                "0%",
                "5%",
                "10%",
                "15%",
                "20%",
            ],
            key="repair_cushion_percent",
        )
        st.toggle("Show full repair math?", key="show_full_repair_math")

    if st.session_state.get("repair_scope_confidence") in ["Photos only", "Unknown"]:
        st.warning("Repair scope confidence is limited. Add a walkthrough or contractor estimate before treating the repair number as final.")
    elif st.session_state.get("repair_scope_confidence") == "Contractor verified":
        st.success("Contractor verified scope selected. The app will reduce uncertainty warnings, but final offer still depends on the full deal math.")

    uploaded_repair_files = st.file_uploader(
        "Upload property photos or boots-on-ground walkthrough video",
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"],
        accept_multiple_files=True,
        key="repair_media_files",
    )
    st.selectbox(
        "Moisture/biological growth verified?",
        [
            "No",
            "Unknown",
            "Suspected staining only",
            "Yes - inspector verified",
            "Yes - seller disclosed",
        ],
        key="mold_verified",
        help="If not verified, the app uses moisture/discoloration wording.",
    )
    st.caption(condition_wording_used())
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

            st.session_state["repair_notes"] = safe_condition_text(generated_notes)
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
            pricing_mode=st.session_state.get("repair_pricing_mode", "Investor standard"),
            repair_scope_confidence=st.session_state.get("repair_scope_confidence", "Unknown"),
            market_labor_cost=st.session_state.get("market_labor_cost", "Unknown"),
            repair_cushion_percent=repair_cushion_percent_value(),
            manual_repair_adjustment=float(st.session_state.get("manual_repair_adjustment", 0) or 0),
            mold_verified=mold_verified_bool(),
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
                + ", ".join(safe_condition_text(flag) for flag in repair_analysis.get("red_flags", []))
            )

        render_repair_number_explanation(repair_analysis.get("repair_calibration", {}))

        line_items = estimate.get("line_items", [])

        if line_items:
            st.dataframe(
                pd.DataFrame(line_items).assign(
                    label=lambda df: df["label"].map(safe_condition_text),
                    notes=lambda df: df["notes"].map(safe_condition_text),
                )[["category", "label", "quantity", "unit", "low", "likely", "high", "notes"]],
                use_container_width=True,
            )

        st.text_area(
            "Repair estimate summary",
            value=safe_condition_text(repair_analysis.get("summary", "")),
            height=260,
        )

        if st.button("Use likely repair number in offer", type="primary"):
            st.session_state["repairs"] = int(repair_analysis.get("recommended_repair_number", 0) or 0)
            st.session_state["repair_source"] = "AI Repair Estimate"
            st.success("Calibrated repair number copied into Estimated repairs. Scroll down and confirm it before analyzing the deal.")
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
    slow_flip_lead_search_max = get_market_slow_flip_lead_search_max(st.session_state.get("repair_market", "Central IL"))
    slow_flip_max_buy_price, slow_flip_max_source = resolve_slow_flip_max_buy_price(st.session_state.get("repair_market", "Central IL"))
    st.session_state["slow_flip_lead_search_max"] = int(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else 0
    st.session_state["slow_flip_max_buy_price_used"] = int(slow_flip_max_buy_price) if slow_flip_max_buy_price > 0 else 0
    st.session_state["slow_flip_max_source"] = slow_flip_max_source
    market_default_buyer_percent = get_market_wholesale_buyer_percent(st.session_state.get("repair_market", "Central IL"))
    wholesale_model = advanced_wholesale_buyer_model(
        market=st.session_state.get("repair_market", "Central IL"),
        arv=float(st.session_state.get("arv", 0) or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
        notes=st.session_state.get("notes", ""),
        repair_notes=st.session_state.get("repair_notes", "") + " " + st.session_state.get("manual_repair_notes", ""),
        property_type=st.session_state.get("property_type", ""),
        days_on_market=int(st.session_state.get("days_on_market", 0) or 0),
        buyer_demand_confidence=st.session_state.get("buyer_demand_confidence", "Medium"),
        market_type=st.session_state.get("market_type", "Auto"),
        occupancy=st.session_state.get("occupancy", "Unknown"),
        livable=st.session_state.get("livable", "Unknown"),
        exit_confidence=st.session_state.get("exit_confidence", "Medium"),
    )
    market_buyer_percent = wholesale_model["buyer_percent"]
    market_adjustments = wholesale_model["reasons"]
    final_wholesale_buyer_percent = float(wholesale_buyer_percent_arv) if manual_wholesale_override else market_buyer_percent
    wholesale_buyer_percent_source = "Manual Override" if manual_wholesale_override else "Market Default"

    p1, p2, p3 = st.columns(3)
    p1.info(f"Market Profile: {market_profile.get('buyer_profile', 'Normal investor market')}")
    p2.info(f"Market Repair Multiplier: {float(market_profile.get('repair_multiplier', 1.0)):.2f}x")
    p3.info(f"Wholesale Buyer % Source: {wholesale_buyer_percent_source}")
    if slow_flip_lead_search_max > 0:
        st.caption(f"Slow Flip Lead Search Max: {money(slow_flip_lead_search_max)}")
    if slow_flip_max_buy_price > 0:
        current_buy_price = safe_float(st.session_state.get("contract_price", 0)) or safe_float(st.session_state.get("asking_price", 0))
        above_slow_flip_max_buy_price = is_above_slow_flip_max_buy_price(current_buy_price, slow_flip_max_buy_price)
        st.caption(f"Slow Flip Max Buy Price: {money(slow_flip_max_buy_price)} ({slow_flip_max_source})")
        st.caption(f"Above Slow Flip Max Buy Price? {'Yes' if above_slow_flip_max_buy_price else 'No'}")
    st.caption(f"Market buyer % of ARV used: {percent_label(final_wholesale_buyer_percent)}")
    st.caption(f"Wholesale Buyer % Range: {wholesale_model['range']} | {wholesale_model['tier']}")
    st.caption("Wholesale buyers in this market will likely need to be around "
               f"{percent_label(final_wholesale_buyer_percent)} of ARV because {wholesale_model['reason_text']}")
    wt1, wt2, wt3 = st.columns(3)
    wt1.metric("Conservative buyer target", money(wholesale_model["conservative_buyer_target"]))
    wt2.metric("Aggressive buyer target", money(wholesale_model["aggressive_buyer_target"]))
    wt3.metric("Recommended wholesale max offer", money(wholesale_model["recommended_wholesale_max_offer"]))
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

    slow_flip_lead_search_max = get_market_slow_flip_lead_search_max(st.session_state.get("repair_market", "Central IL"))
    slow_flip_max_buy_price, slow_flip_max_source = resolve_slow_flip_max_buy_price(st.session_state.get("repair_market", "Central IL"))
    st.session_state["slow_flip_lead_search_max"] = int(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else 0
    st.session_state["slow_flip_max_buy_price_used"] = int(slow_flip_max_buy_price) if slow_flip_max_buy_price > 0 else 0
    st.session_state["slow_flip_max_source"] = slow_flip_max_source
    market_default_buyer_percent = get_market_wholesale_buyer_percent(st.session_state.get("repair_market", "Central IL"))
    wholesale_model = advanced_wholesale_buyer_model(
        market=st.session_state.get("repair_market", "Central IL"),
        arv=float(resolved_arv or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
        notes=st.session_state.get("notes", ""),
        repair_notes=st.session_state.get("repair_notes", "") + " " + st.session_state.get("manual_repair_notes", ""),
        property_type=st.session_state.get("property_type", ""),
        days_on_market=int(st.session_state.get("days_on_market", 0) or 0),
        buyer_demand_confidence=st.session_state.get("buyer_demand_confidence", "Medium"),
        market_type=st.session_state.get("market_type", "Auto"),
        occupancy=st.session_state.get("occupancy", "Unknown"),
        livable=st.session_state.get("livable", "Unknown"),
        exit_confidence=st.session_state.get("exit_confidence", "Medium"),
    )
    final_wholesale_buyer_percent = wholesale_model["buyer_percent"]
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
        wholesale_buyer_percent_range=wholesale_model.get("range", ""),
        wholesale_buyer_percent_reason=wholesale_model.get("reason_text", ""),
        market_liquidity_tier=wholesale_model.get("tier", ""),
        market_wholesale_buyer_percent=float(market_default_buyer_percent),
        slow_flip_max_offer_cap=float(slow_flip_max_offer_cap),
        slow_flip_first_offer_gap=float(slow_flip_first_offer_gap),
        slow_flip_lead_search_max=float(slow_flip_lead_search_max),
        slow_flip_lead_search_source="Market Default",
        above_slow_flip_lead_search_range=bool(slow_flip_lead_search_max > 0 and analysis_price > slow_flip_lead_search_max),
        inside_slow_flip_lead_search_range=bool(slow_flip_lead_search_max > 0 and analysis_price <= slow_flip_lead_search_max),
        slow_flip_max_buy_price=float(slow_flip_max_buy_price),
        slow_flip_max_source=slow_flip_max_source,
        above_slow_flip_max_buy_price=bool(slow_flip_max_buy_price > 0 and analysis_price > slow_flip_max_buy_price),
    )

    analysis_notes = "\n".join(
        part
        for part in [
            st.session_state.get("notes", ""),
            st.session_state.get("repair_notes", ""),
            st.session_state.get("manual_repair_notes", ""),
        ]
        if str(part or "").strip()
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
        notes=analysis_notes,
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
    repair_breakdown = build_repair_breakdown()
    render_repair_estimate_breakdown(repair_breakdown)
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
            "Slow Flip Lead Search Max": money(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else "Not set",
            "Slow Flip Max Buy Price": money(slow.get("slow_flip_max_buy_price", 0)) if slow.get("slow_flip_max_buy_price", 0) > 0 else "Not set",
            "Slow Flip Max Source": slow.get("slow_flip_max_source", ""),
            "Above Slow Flip Max Buy Price?": "Yes" if slow.get("above_slow_flip_max_buy_price") else "No",
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
        "Repairs": money(st.session_state.get("repairs", 0)),
        "Wholesale Buyer % Source": wholesale.get("buyer_percent_source", ""),
        "Market buyer % of ARV used": percent_label(wholesale.get("buyer_percent_arv", 0)),
        "Buyer % Range": wholesale.get("buyer_percent_range", ""),
        "Market Liquidity Tier": wholesale.get("market_liquidity_tier", ""),
        "Buyer % Reason": wholesale.get("buyer_percent_reason", ""),
        "Conservative buyer target": money(wholesale.get("conservative_buyer_target", 0)),
        "Aggressive buyer target": money(wholesale.get("aggressive_buyer_target", 0)),
        "Buyer target": money(wholesale["buyer_target"]),
        "Wholesale max offer": money(wholesale["max_offer"]),
        "Wholesale estimated fee at buy price": money(wholesale["estimated_fee_at_ask"])
        })

    st.subheader("Risk Notes")
    for risk in result["risks"]:
        st.warning(safe_condition_text(risk))

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
