from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from types import SimpleNamespace

try:
    from ui_sections.buyer_demand_ui import render_buyer_demand_section
    from ui_sections.buyer_outreach_ui import render_buyer_outreach_section
    from ui_sections.deal_protection_ui import render_deal_protection_section
    from ui_sections.decision_ui import render_decision_section
    from ui_sections.lead_intake_ui import render_lead_intake_section
    from ui_sections.repair_ui import render_repair_section
except ImportError:
    try:
        from .ui_sections.buyer_demand_ui import render_buyer_demand_section
        from .ui_sections.buyer_outreach_ui import render_buyer_outreach_section
        from .ui_sections.deal_protection_ui import render_deal_protection_section
        from .ui_sections.decision_ui import render_decision_section
        from .ui_sections.lead_intake_ui import render_lead_intake_section
        from .ui_sections.repair_ui import render_repair_section
    except ImportError:
        from war_room_offer_engine.ui_sections.buyer_demand_ui import render_buyer_demand_section
        from war_room_offer_engine.ui_sections.buyer_outreach_ui import render_buyer_outreach_section
        from war_room_offer_engine.ui_sections.deal_protection_ui import render_deal_protection_section
        from war_room_offer_engine.ui_sections.decision_ui import render_decision_section
        from war_room_offer_engine.ui_sections.lead_intake_ui import render_lead_intake_section
        from war_room_offer_engine.ui_sections.repair_ui import render_repair_section

# Developer validation before merge:
# python -m py_compile war_room_offer_engine/war_room_offer_engine/app.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/rules.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/repair_analyzer.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/repair_price_book_il.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/data_sources.py
# python -m py_compile war_room_offer_engine/war_room_offer_engine/apify_connector.py
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
    build_deal_protection_payload = _rules_module.build_deal_protection_payload
    default_address_sharing_level = _rules_module.default_address_sharing_level
    default_listing_source_sharing_level = _rules_module.default_listing_source_sharing_level
    money = _rules_module.money
except ImportError:
    try:
        from .rules import Assumptions, DealInput, analyze_deal, build_deal_protection_payload, default_address_sharing_level, default_listing_source_sharing_level, money
    except ImportError:
        try:
            from war_room_offer_engine.rules import Assumptions, DealInput, analyze_deal, build_deal_protection_payload, default_address_sharing_level, default_listing_source_sharing_level, money
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.rules import Assumptions, DealInput, analyze_deal, build_deal_protection_payload, default_address_sharing_level, default_listing_source_sharing_level, money

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
        fetch_apify_zillow_dataset,
        run_apify_zillow_actor,
        get_sold_comps,
        sold_comps_from_apify_rows,
        sold_comps_from_csv_rows,
        sold_comps_from_pasted_text,
    )
except ImportError:
    try:
        from .data_sources import (
            fetch_all_sources,
            merge_results,
            get_secret,
            parse_listing_text,
            provider_connection_status,
            fetch_apify_zillow_dataset,
            run_apify_zillow_actor,
            get_sold_comps,
            sold_comps_from_apify_rows,
            sold_comps_from_csv_rows,
            sold_comps_from_pasted_text,
        )
    except ImportError:
        try:
            from war_room_offer_engine.data_sources import (
                fetch_all_sources,
                merge_results,
                get_secret,
                parse_listing_text,
                provider_connection_status,
                fetch_apify_zillow_dataset,
                run_apify_zillow_actor,
                get_sold_comps,
                sold_comps_from_apify_rows,
                sold_comps_from_csv_rows,
                sold_comps_from_pasted_text,
            )
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.data_sources import (
                fetch_all_sources,
                merge_results,
                get_secret,
                parse_listing_text,
                provider_connection_status,
                fetch_apify_zillow_dataset,
                run_apify_zillow_actor,
                get_sold_comps,
                sold_comps_from_apify_rows,
                sold_comps_from_csv_rows,
                sold_comps_from_pasted_text,
            )

try:
    from sold_comps import (
        calculate_arv_from_comps,
        comp_summary_json,
        normalize_sold_comps,
        radius_to_float,
        resolve_arv_fallback,
        score_sold_comps,
    )
except ImportError:
    try:
        from .sold_comps import (
            calculate_arv_from_comps,
            comp_summary_json,
            normalize_sold_comps,
            radius_to_float,
            resolve_arv_fallback,
            score_sold_comps,
        )
    except ImportError:
        try:
            from war_room_offer_engine.sold_comps import (
                calculate_arv_from_comps,
                comp_summary_json,
                normalize_sold_comps,
                radius_to_float,
                resolve_arv_fallback,
                score_sold_comps,
            )
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.sold_comps import (
                calculate_arv_from_comps,
                comp_summary_json,
                normalize_sold_comps,
                radius_to_float,
                resolve_arv_fallback,
                score_sold_comps,
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
    "arv_source_used": "Missing",
    "arv_confidence": "Not enough data",
    "arv_fallback_reason": "",
    "arv_fallback_warnings": [],
    "auto_comp_address": "",
    "auto_comp_radius": "1 mile",
    "auto_comp_date_range": "Last 12 months",
    "auto_comp_source": "Auto",
    "auto_comp_pasted_text": "",
    "auto_comp_count": 0,
    "strong_comp_count": 0,
    "good_comp_count": 0,
    "weak_comp_count": 0,
    "excluded_comp_count": 0,
    "auto_low_arv": 0,
    "auto_conservative_arv": 0,
    "auto_average_arv": 0,
    "auto_high_arv": 0,
    "auto_recommended_arv": 0,
    "auto_comp_summary_json": "[]",
    "excluded_comp_flags_json": "[]",
    "use_auto_arv_over_manual_comps": False,
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
    "apify_dataset_id": "",
    "apify_actor_id": "",
    "apify_actor_input_json": "{}",
    "apify_preview_limit": 25,
    "apify_selected_row": 0,
    "apify_import_status": "",
    "apify_imported_at": "",
    "apify_source": "",
    "apify_zpid": "",
    "apify_duplicate_count": 0,
    "apify_field_sources": {},
    "apify_imported_fields": [],
    "apify_skipped_manual_fields": [],
    "apify_last_error": "",
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
    "buyer_demand_confidence": "Unknown",
    "wholesale_buyer_list_strength": "No buyer list yet",
    "slow_flip_buyer_demand": "Unknown",
    "rental_demand_confidence": "Unknown",
    "exit_strategy_confidence": "Unknown",
    "property_marketability": "Normal",
    "exit_obstacles": [],
    "buyer_proof": "Unknown",
    "buyer_demand_score": "Weak",
    "wholesale_exit_confidence": "Weak",
    "slow_flip_exit_confidence": "Weak",
    "overall_exit_confidence": "Weak",
    "exit_risk_warnings": [],
    "recommended_exit_strategy": "",
    "backup_exit_strategy": "",
    "buyer_outreach_needed": "Yes",
    "exit_verification_items": [],
    "buyer_outreach_status": "Not sent",
    "buyers_contacted_count": 0,
    "buyer_response_level": "Not sent yet",
    "best_buyer_feedback": "",
    "buyer_target_price_confirmed": "Pending",
    "confirmed_buyer_target_price": 0,
    "buyer_concerns": [],
    "contract_status": "Not under contract",
    "deal_protection_mode": "Yes",
    "address_sharing_level": "Hide exact address",
    "listing_source_sharing_level": "Hide listing/source links",
    "buyer_message_type": "Pre-contract demand check",
    "buyer_access_notes": "",
    "buyer_deadline": "",
    "pre_contract_teaser_message": "",
    "under_contract_buyer_blast": "",
    "protected_buyer_message": "",
    "exact_address_shared": "No",
    "protected_fields_hidden": [],
    "buyer_message_allowed": "Teaser Only",
    "deal_protection_warning": "",
    "buyer_blast_text": "",
    "buyer_blast_email": "",
    "slow_flip_buyer_message": "",
    "internal_team_message": "",
    "dispo_test_summary": "",
    "dispo_test_recommendation": "Get buyer commitment first",
    "dispo_exit_confidence_after_outreach": "Weak",
    "notes": "",
}

for key, value in FIELD_DEFAULTS.items():
    st.session_state.setdefault(key, value)
st.session_state.setdefault("last_source_results", [])
st.session_state.setdefault("last_auto_pull", {})
st.session_state.setdefault("apify_zillow_preview", [])
st.session_state.setdefault("apify_zillow_duplicates", [])


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


def manual_comp_records() -> list[dict]:
    records = []
    for idx in range(1, 6):
        price = safe_float(st.session_state.get(f"manual_comp_{idx}_price", 0))
        if price <= 0:
            continue
        records.append(
            {
                "comp_address": st.session_state.get(f"manual_comp_{idx}_address", ""),
                "sold_price": price,
                "sold_date": "",
                "beds": st.session_state.get(f"manual_comp_{idx}_beds", 0),
                "baths": st.session_state.get(f"manual_comp_{idx}_baths", 0),
                "square_feet": st.session_state.get(f"manual_comp_{idx}_sqft", 0),
                "condition": st.session_state.get(f"manual_comp_{idx}_condition", ""),
                "notes": st.session_state.get(f"manual_comp_{idx}_notes", ""),
                "source": "Manual Comps",
                "confidence": "Manual",
            }
        )
    return normalize_sold_comps(records, source="Manual Comps")


def comp_subject() -> dict:
    return {
        "address": st.session_state.get("address", ""),
        "beds": st.session_state.get("beds", 0),
        "baths": st.session_state.get("baths", 0),
        "sqft": st.session_state.get("sqft", 0),
        "property_type": st.session_state.get("property_type", ""),
        "functional_risks": " ".join(
            str(st.session_state.get(key, ""))
            for key in ["notes", "repair_notes", "manual_repair_notes"]
        ),
    }


def store_auto_arv_summary(scored_comps: list[dict], summary: dict) -> None:
    excluded_flags = []
    for comp in scored_comps:
        if not comp.get("include_default", False) or comp.get("score") == "Bad Comp":
            excluded_flags.extend(comp.get("flags", []))
    st.session_state["auto_comp_count"] = len(scored_comps)
    st.session_state["strong_comp_count"] = int(summary.get("strong_comp_count", 0) or 0)
    st.session_state["good_comp_count"] = int(summary.get("good_comp_count", 0) or 0)
    st.session_state["weak_comp_count"] = int(summary.get("weak_comp_count", 0) or 0)
    st.session_state["excluded_comp_count"] = int(summary.get("excluded_comp_count", 0) or 0)
    st.session_state["auto_low_arv"] = int(summary.get("low_arv", 0) or 0)
    st.session_state["auto_conservative_arv"] = int(summary.get("conservative_arv", 0) or 0)
    st.session_state["auto_average_arv"] = int(summary.get("average_arv", 0) or 0)
    st.session_state["auto_high_arv"] = int(summary.get("high_arv", 0) or 0)
    st.session_state["auto_recommended_arv"] = int(summary.get("recommended_arv", 0) or 0)
    st.session_state["auto_arv_summary"] = summary
    st.session_state["auto_comp_summary_json"] = comp_summary_json(scored_comps)
    st.session_state["excluded_comp_flags_json"] = json.dumps(sorted(set(excluded_flags)))


def resolve_value_source() -> tuple[float, str]:
    rentcast_arv = safe_float(st.session_state.get("rentcast_arv", 0))
    sheet_arv = safe_float(st.session_state.get("sheet_arv", 0))
    comps_arv = manual_comps_average()
    manual_override = safe_float(st.session_state.get("manual_arv_override", 0))
    tax_assessed_value = safe_float(st.session_state.get("tax_assessed_value", 0))
    auto_summary = st.session_state.get("auto_arv_summary", {}) or {}

    if st.session_state.get("use_auto_arv_over_manual_comps") and manual_override <= 0:
        preferred_auto = dict(auto_summary)
        fallback = resolve_arv_fallback(
            manual_override=0,
            manual_comp_average=0,
            auto_summary=preferred_auto,
            rentcast_value=rentcast_arv,
            zillow_value=sheet_arv,
            tax_assessed_value=tax_assessed_value,
        )
        if fallback.get("source") == "Automatic Sold Comps":
            fallback["warnings"] = list(fallback.get("warnings", [])) + ["Automatic sold comps manually selected over manual comp average."]
        elif comps_arv > 0:
            fallback = resolve_arv_fallback(
                manual_override=0,
                manual_comp_average=comps_arv,
                auto_summary={},
                rentcast_value=0,
                zillow_value=0,
                tax_assessed_value=0,
            )
    else:
        fallback = resolve_arv_fallback(
            manual_override=manual_override,
            manual_comp_average=comps_arv,
            auto_summary=auto_summary,
            rentcast_value=rentcast_arv,
            zillow_value=sheet_arv,
            tax_assessed_value=tax_assessed_value,
        )

    st.session_state["arv_source_used"] = fallback.get("source", "Missing")
    st.session_state["arv_confidence"] = fallback.get("confidence", "Not enough data")
    st.session_state["arv_fallback_reason"] = fallback.get("reason", "")
    st.session_state["arv_fallback_warnings"] = fallback.get("warnings", [])
    return safe_float(fallback.get("arv", 0)), fallback.get("source", "Missing")


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
    buyer_demand_text = str(buyer_demand_confidence or "").lower()
    exit_confidence_text = str(exit_confidence or "").lower()
    if "strong" in buyer_demand_text:
        buyer_percent += 0.03
        reasons.append("Strong buyer demand adds 3%.")
    elif "limited" in buyer_demand_text or "weak" in buyer_demand_text or "unknown" in buyer_demand_text:
        buyer_percent -= 0.03
        reasons.append("Weak buyer demand subtracts 3%.")
    if any(word in all_notes for word in ["functional obsolescence", "low ceiling", "low ceilings", "no driveway", "bad layout"]):
        buyer_percent -= 0.07
        reasons.append("Functional obsolescence subtracts 7%.")
    if market_type == "Unknown":
        buyer_percent -= 0.05
        reasons.append("Unknown market subtracts 5%.")
    if "weak" in exit_confidence_text or "unknown" in exit_confidence_text:
        buyer_percent -= 0.03
        reasons.append("Weak data/exit confidence subtracts 3%.")
    elif "strong" in exit_confidence_text:
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


EXIT_OBSTACLE_OPTIONS = [
    "Low ceilings",
    "Low doorways",
    "No driveway / street parking only",
    "Termite / structural concern",
    "Rural / thin buyer pool",
    "Weak rent comps",
    "Weird layout",
    "High repairs",
    "Low ARV",
    "Tenant occupied",
    "Title/ownership issue",
    "Flood/moisture concern",
    "Unknown market",
    "Other",
]


BUYER_CONCERN_OPTIONS = [
    "Price too high",
    "Repairs too high",
    "Market too rural",
    "ARV too low",
    "Rent too low",
    "No driveway / parking issue",
    "Low ceilings / layout issue",
    "Structural concern",
    "Title concern",
    "Too small",
    "Unknown area",
    "Other",
]


def build_dispo_test_summary(result: dict, deal: DealInput) -> dict:
    best = result.get("best", {})
    app_buyer_target = safe_float(result.get("wholesale", {}).get("buyer_target", 0)) or safe_float(best.get("buyer_target", 0))
    confirmed_target = safe_float(st.session_state.get("confirmed_buyer_target_price", 0))
    outreach_status = st.session_state.get("buyer_outreach_status", "Not sent")
    buyers_contacted = int(safe_float(st.session_state.get("buyers_contacted_count", 0)))
    response_level = st.session_state.get("buyer_response_level", "Not sent yet")
    target_confirmed = st.session_state.get("buyer_target_price_confirmed", "Pending")
    concerns = list(st.session_state.get("buyer_concerns", []) or [])
    buyer_proof = st.session_state.get("buyer_proof", "Unknown")
    market_type = st.session_state.get("market_type", "Auto")
    warnings: list[str] = []

    exit_confidence_after = st.session_state.get("overall_exit_confidence", "Weak")
    recommendation = "Get buyer commitment first"

    if outreach_status in ["Not sent", "Not applicable"] and buyer_proof in ["No buyer proof yet", "Unknown"]:
        warnings.append("Do not rely on wholesale exit until buyer demand is confirmed.")
    if outreach_status == "Not sent" and market_type in ["Unknown", "Rural / thin buyer market"]:
        warnings.append("No buyer outreach has been done in a new/unproven market. Require Human Review.")
    if response_level == "No interest" or outreach_status == "No buyer interest":
        exit_confidence_after = "Weak"
        recommendation = "Pass" if deal.asking_price > safe_float(best.get("max_offer", 0)) else "Renegotiate"
        warnings.append("Buyer response shows no interest. Downgrade the deal before locking it up.")
    elif response_level == "Weak interest":
        exit_confidence_after = "Weak"
        recommendation = "Lower offer"
        warnings.append("Buyer response is weak. Lower the offer or get a real buyer commitment first.")
    elif response_level in ["Strong interest", "Some interest"] and outreach_status in ["Buyers responded", "Buyer interest confirmed"]:
        if target_confirmed == "Yes" and confirmed_target > 0:
            if app_buyer_target > 0 and confirmed_target < app_buyer_target:
                exit_confidence_after = "Medium"
                recommendation = "Lower offer"
                warnings.append(
                    f"Confirmed buyer target {money(confirmed_target)} is below the app buyer target {money(app_buyer_target)}."
                )
            else:
                exit_confidence_after = "Strong" if response_level == "Strong interest" else "Medium"
                recommendation = "Proceed with offer"
        else:
            exit_confidence_after = "Medium"
            recommendation = "Get buyer commitment first"

    concern_warning_terms = [
        "Repairs too high",
        "Market too rural",
        "Low ceilings / layout issue",
        "No driveway / parking issue",
        "Structural concern",
    ]
    matched_concerns = [concern for concern in concerns if concern in concern_warning_terms]
    if matched_concerns:
        warnings.append("Exit Risk warning from buyer concerns: " + ", ".join(matched_concerns) + ".")
        if recommendation == "Proceed with offer":
            recommendation = "Lower offer"

    if target_confirmed == "No":
        warnings.append("Buyer target price is not confirmed yet.")
        if recommendation == "Proceed with offer":
            recommendation = "Get buyer commitment first"

    summary = (
        f"Outreach status: {outreach_status}. Buyer response: {response_level}. "
        f"Buyers contacted: {buyers_contacted}. Confirmed buyer target: {money(confirmed_target)}. "
        f"Recommendation: {recommendation}."
    )

    return {
        "outreach_status": outreach_status,
        "buyers_contacted_count": buyers_contacted,
        "buyer_response_level": response_level,
        "best_buyer_feedback": safe_condition_text(st.session_state.get("best_buyer_feedback", "")),
        "buyer_target_price_confirmed": target_confirmed,
        "confirmed_buyer_target_price": confirmed_target,
        "buyer_concerns": concerns,
        "app_buyer_target": app_buyer_target,
        "warnings": list(dict.fromkeys(safe_condition_text(warning) for warning in warnings)),
        "exit_confidence_after_outreach": exit_confidence_after,
        "recommendation": recommendation,
        "summary": safe_condition_text(summary),
    }


def generate_buyer_blast_messages(deal: DealInput, result: dict, dispo_summary: dict | None = None) -> dict:
    dispo_summary = dispo_summary or build_dispo_test_summary(result, deal)
    city_market = deal.market or st.session_state.get("city", "") or "this market"
    arv_text = money(deal.arv) if deal.arv else "unverified"
    repairs_text = money(deal.repairs) if deal.repairs else "needs verification"
    buyer_target = safe_float(dispo_summary.get("confirmed_buyer_target_price", 0)) or safe_float(result.get("wholesale", {}).get("buyer_target", 0))
    notes = safe_condition_text(
        " ".join(
            part
            for part in [
                st.session_state.get("notes", ""),
                st.session_state.get("repair_notes", ""),
                st.session_state.get("manual_repair_notes", ""),
                "; ".join(st.session_state.get("exit_obstacles", []) or []),
                "; ".join(st.session_state.get("buyer_concerns", []) or []),
            ]
            if str(part or "").strip()
        )
    )
    short_notes = notes[:260] if notes else "Buyer feedback requested before finalizing offer."
    property_line = f"{city_market}. {deal.beds:g} bed, {deal.baths:g} bath, {int(deal.sqft or 0):,} sqft"
    protected_message = st.session_state.get("protected_buyer_message", "")
    teaser_only = st.session_state.get("buyer_message_allowed", "Teaser Only") != "Full Blast Allowed"

    text = safe_condition_text(
        f"Investor special in {property_line}. Estimated ARV around {arv_text}, repairs around {repairs_text}. "
        f"Asking for buyer feedback before finalizing offer. Notes: {short_notes}. "
        "Reply with your highest comfortable buy price."
    )
    email = safe_condition_text(
        f"Subject: Buyer feedback needed - {deal.address or city_market}\n\n"
        f"Team, can you review this one before we finalize an offer?\n\n"
        f"Address/market: {deal.address or city_market}\n"
        f"Specs: {deal.beds:g} bed / {deal.baths:g} bath / {int(deal.sqft or 0):,} sqft\n"
        f"ARV: {arv_text}\nRepairs: {repairs_text}\n"
        f"Current ask/buy price: {money(deal.asking_price)}\n"
        f"Notes: {short_notes}\n\n"
        "Please reply with whether you would buy this, your highest comfortable price, and any deal-killer concerns."
    )
    slow_flip = safe_condition_text(
        f"Owner-finance buyer check in {city_market}: {deal.beds:g}/{deal.baths:g}, rent support around {money(deal.rent)}, "
        f"ARV around {arv_text}, repair scope {repairs_text}. Any buyer appetite here, and what payment/price range feels realistic?"
    )
    internal = safe_condition_text(
        f"Dispo test: {deal.address or city_market}. Best exit: {result.get('best_exit', 'Needs Human Review')}. "
        f"App buyer target: {money(result.get('wholesale', {}).get('buyer_target', 0))}. "
        f"Confirmed buyer target: {money(buyer_target)}. Dispo recommendation: {dispo_summary.get('recommendation', '')}."
    )
    if teaser_only and protected_message:
        text = protected_message
        email = protected_message
        slow_flip = protected_message
    return {
        "buyer_blast_text": text,
        "buyer_blast_email": email,
        "slow_flip_buyer_message": slow_flip,
        "internal_team_message": internal,
    }


def store_dispo_summary(dispo_summary: dict, messages: dict) -> None:
    st.session_state["dispo_test_summary"] = dispo_summary.get("summary", "")
    st.session_state["dispo_test_recommendation"] = dispo_summary.get("recommendation", "")
    st.session_state["dispo_exit_confidence_after_outreach"] = dispo_summary.get("exit_confidence_after_outreach", "Weak")
    for key, value in messages.items():
        st.session_state[key] = value


def build_exit_strategy_confidence(
    result: dict,
    deal: DealInput,
    missing_info: list[str] | None = None,
    risk_flags: list[str] | None = None,
) -> dict:
    missing_info = missing_info or []
    risk_flags = risk_flags or []
    exit_mode = deal.exit_mode
    best_exit = result.get("best_exit", "Needs Human Review")
    wholesale_percent = safe_float(result.get("wholesale", {}).get("buyer_percent_arv", 0))
    functional_risks = result.get("slow_flip", {}).get("functional_risks", [])

    buyer_demand = st.session_state.get("buyer_demand_confidence", "Unknown")
    buyer_list = st.session_state.get("wholesale_buyer_list_strength", "No buyer list yet")
    slow_flip_demand = st.session_state.get("slow_flip_buyer_demand", "Unknown")
    rental_demand = st.session_state.get("rental_demand_confidence", "Unknown")
    exit_confidence_input = st.session_state.get("exit_strategy_confidence", "Unknown")
    marketability = st.session_state.get("property_marketability", "Normal")
    obstacles = list(st.session_state.get("exit_obstacles", []) or [])
    buyer_proof = st.session_state.get("buyer_proof", "Unknown")
    market_type = st.session_state.get("market_type", "Auto")
    outreach_status = st.session_state.get("buyer_outreach_status", "Not sent")
    response_level = st.session_state.get("buyer_response_level", "Not sent yet")
    target_confirmed = st.session_state.get("buyer_target_price_confirmed", "Pending")
    confirmed_target = safe_float(st.session_state.get("confirmed_buyer_target_price", 0))
    buyer_concerns = list(st.session_state.get("buyer_concerns", []) or [])

    warnings: list[str] = []
    verification_items: list[str] = []
    outreach: list[str] = []

    buyer_demand_score = "Medium"
    if buyer_demand == "Strong buyer demand" and buyer_proof in [
        "Buyer already interested",
        "Buyer list confirms demand",
        "Similar deals sold recently",
    ]:
        buyer_demand_score = "Strong"
    if buyer_demand in ["Limited buyer demand", "Unknown"] or buyer_proof in ["No buyer proof yet", "Unknown"]:
        buyer_demand_score = "Weak"
        warnings.append("Buyer demand is limited or unverified. Do not treat this as a clean buy.")
        verification_items.append("buyer demand")

    if marketability == "Very limited buyer pool":
        buyer_demand_score = "Weak"
        warnings.append("Property marketability is very limited. Require Human Review or a steal-price offer.")
        verification_items.append("buyer pool")
    elif marketability == "Limited buyer pool":
        warnings.append("Property has a limited buyer pool. Confirm demand before offer.")
        verification_items.append("marketability")

    if len(obstacles) >= 3:
        buyer_demand_score = "Weak"
        warnings.append("Three or more exit obstacles selected. Require Human Review.")
        verification_items.append("exit obstacles")

    if buyer_proof == "No buyer proof yet" and market_type in ["Unknown", "Rural / thin buyer market"]:
        warnings.append("No buyer proof in a new/unproven market. Require Human Review.")
        verification_items.append("buyer proof")
    if outreach_status == "Not sent" and market_type in ["Unknown", "Rural / thin buyer market"]:
        warnings.append("No buyer outreach has been done in a new/unproven market. Require Human Review.")
        verification_items.append("buyer outreach")

    wholesale_applicable = exit_mode in ["Wholesale Only", "Auto"]
    if not wholesale_applicable:
        wholesale_exit_confidence = "Not applicable"
    elif buyer_list in ["Weak buyer list", "No buyer list yet", "Not applicable"] or buyer_demand_score == "Weak":
        wholesale_exit_confidence = "Weak"
        warnings.append("Wholesale Exit Risk: buyer list strength is weak, missing, or not confirmed.")
        verification_items.append("wholesale buyers")
    elif buyer_list == "Some buyers":
        wholesale_exit_confidence = "Medium"
    else:
        wholesale_exit_confidence = "Strong"

    if wholesale_applicable and wholesale_percent < 0.55:
        wholesale_exit_confidence = "Weak"
        warnings.append("Wholesale Exit Risk: buyer percent of ARV is below 55%. Require Human Review.")
        verification_items.append("wholesale buyer percent")
    if wholesale_applicable and response_level == "No interest":
        wholesale_exit_confidence = "Weak"
        warnings.append("Wholesale Exit Risk: buyer outreach came back with no interest.")
    if wholesale_applicable and response_level == "Strong interest" and outreach_status in ["Buyers responded", "Buyer interest confirmed"]:
        if target_confirmed == "Yes" and confirmed_target > 0:
            app_target = safe_float(result.get("wholesale", {}).get("buyer_target", 0))
            wholesale_exit_confidence = "Strong" if not app_target or confirmed_target >= app_target else "Medium"
            buyer_demand_score = "Strong"
        elif buyer_list in ["Strong active buyers", "Some buyers"]:
            wholesale_exit_confidence = "Medium"

    slow_flip_applicable = exit_mode in ["Slow Flip Only", "Auto"]
    weak_rental = rental_demand in ["Weak rent comps", "Conflicting data", "Unknown"]
    if not slow_flip_applicable:
        slow_flip_exit_confidence = "Not applicable"
    elif slow_flip_demand in ["Weak", "Unknown", "Not applicable"] or weak_rental:
        slow_flip_exit_confidence = "Weak"
        warnings.append("Slow Flip Exit Risk: owner-finance buyer demand or rent support is weak/unverified.")
        verification_items.append("slow flip buyer demand")
        if weak_rental:
            verification_items.append("rent comps")
    elif slow_flip_demand == "Normal" or rental_demand == "Some rent comps":
        slow_flip_exit_confidence = "Medium"
    else:
        slow_flip_exit_confidence = "Strong"

    if weak_rental and slow_flip_applicable:
        warnings.append("Weak or conflicting rent comps should prevent a Grade A slow-flip decision.")

    concern_warning_terms = [
        "Repairs too high",
        "Market too rural",
        "Low ceilings / layout issue",
        "No driveway / parking issue",
        "Structural concern",
    ]
    matched_buyer_concerns = [concern for concern in buyer_concerns if concern in concern_warning_terms]
    if matched_buyer_concerns:
        warnings.append("Exit Risk warning from buyer concerns: " + ", ".join(matched_buyer_concerns) + ".")
        verification_items.append("buyer concern")

    if functional_risks and buyer_demand_score == "Weak":
        warnings.append("Functional risks plus weak buyer demand: Pass Unless Seller Takes Steal Price.")
        verification_items.append("functional risk buyer appetite")

    if "High repairs" in obstacles or (deal.arv > 0 and deal.repairs > max(50000, deal.arv * 0.30)):
        verification_items.append("repair level buyer appetite")
    if "Low ARV" in obstacles or (deal.arv > 0 and deal.arv < 75000):
        verification_items.append("low ARV buyer appetite")
    if "No driveway / street parking only" in obstacles:
        verification_items.append("parking/access concerns")

    if exit_confidence_input in ["Weak", "Unknown"]:
        warnings.append("Exit strategy confidence is weak or unknown.")
        verification_items.append("exit strategy")

    applicable_confidences = [
        confidence
        for confidence in [wholesale_exit_confidence, slow_flip_exit_confidence]
        if confidence != "Not applicable"
    ]
    if not applicable_confidences:
        overall_exit_confidence = "Weak"
    elif any(confidence == "Weak" for confidence in applicable_confidences) or buyer_demand_score == "Weak":
        overall_exit_confidence = "Weak"
    elif all(confidence == "Strong" for confidence in applicable_confidences) and buyer_demand_score == "Strong":
        overall_exit_confidence = "Strong"
    else:
        overall_exit_confidence = "Medium"

    if best_exit == "Wholesale":
        selected_exit_confidence = wholesale_exit_confidence
        backup_exit = "Slow Flip" if slow_flip_exit_confidence in ["Strong", "Medium"] else "Pass"
    elif best_exit == "Slow Flip":
        selected_exit_confidence = slow_flip_exit_confidence
        backup_exit = "Wholesale" if wholesale_exit_confidence in ["Strong", "Medium"] else "Pass"
    else:
        selected_exit_confidence = overall_exit_confidence
        backup_exit = "Pass"

    recommended_exit = best_exit if best_exit in ["Wholesale", "Slow Flip"] else "Human Review"
    if selected_exit_confidence == "Weak" and best_exit in ["Wholesale", "Slow Flip"]:
        recommended_exit = f"{best_exit} after verification"

    buyer_outreach_needed = "Yes" if overall_exit_confidence != "Strong" or wholesale_exit_confidence == "Weak" or buyer_proof in ["No buyer proof yet", "Unknown"] else "No"
    if buyer_outreach_needed == "Yes":
        outreach.extend(
            [
                "Send to top buyers before final offer",
                "Confirm buyer appetite for this city",
                "Confirm buyer appetite for repair level",
            ]
        )
    if deal.beds <= 2 or (deal.arv > 0 and deal.arv < 75000):
        outreach.append("Confirm buyer appetite for 2-bed / low ARV property")
    if slow_flip_applicable:
        outreach.append("Confirm slow flip buyer demand")
    if weak_rental:
        outreach.append("Verify rent comps")
    if "No driveway / street parking only" in obstacles:
        outreach.append("Verify parking/access concerns")

    if "Missing ARV" in missing_info:
        verification_items.append("ARV")
    if "Missing repairs" in missing_info:
        verification_items.append("repairs")
    if "Missing rent" in missing_info:
        verification_items.append("rents")
    if risk_flags:
        verification_items.append("risk flags")

    return {
        "buyer_demand_score": buyer_demand_score,
        "wholesale_exit_confidence": wholesale_exit_confidence,
        "slow_flip_exit_confidence": slow_flip_exit_confidence,
        "overall_exit_confidence": overall_exit_confidence,
        "exit_risk_warnings": list(dict.fromkeys(safe_condition_text(warning) for warning in warnings)),
        "recommended_exit_strategy": recommended_exit,
        "backup_exit_strategy": backup_exit,
        "buyer_outreach_needed": buyer_outreach_needed,
        "exit_verification_items": list(dict.fromkeys(verification_items)),
        "buyer_outreach_checklist": list(dict.fromkeys(outreach)),
        "selected_exit_confidence": selected_exit_confidence,
        "exit_obstacles": obstacles,
    }


def store_exit_confidence_summary(summary: dict) -> None:
    for key in [
        "buyer_demand_score",
        "wholesale_exit_confidence",
        "slow_flip_exit_confidence",
        "overall_exit_confidence",
        "exit_risk_warnings",
        "recommended_exit_strategy",
        "backup_exit_strategy",
        "buyer_outreach_needed",
        "exit_verification_items",
    ]:
        st.session_state[key] = summary.get(key, [] if key in ["exit_risk_warnings", "exit_verification_items"] else "")


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


def can_import_over_state_field(state_key: str) -> bool:
    current_value = st.session_state.get(state_key)
    default_value = FIELD_DEFAULTS.get(state_key)
    return current_value in [None, "", 0, 0.0, "Unknown", default_value]


def apply_apify_zillow_import(row: dict) -> tuple[list[str], list[str]]:
    data = row.get("data", {}) if isinstance(row, dict) else {}
    field_sources = row.get("field_sources", {}) if isinstance(row, dict) else {}
    mapping = {
        "address": "address",
        "city": "city",
        "state": "state",
        "zip": "zip",
        "asking_price": "asking_price",
        "rent": "rent",
        "arv": "sheet_arv",
        "beds": "beds",
        "baths": "baths",
        "sqft": "sqft",
        "lot_size": "lot_size",
        "year_built": "year_built",
        "property_type": "property_type",
        "days_on_market": "days_on_market",
        "status": "status",
        "listing_url": "listing_url",
        "listing_agent_name": "listing_agent_name",
        "listing_agent_phone": "listing_agent_phone",
        "listing_agent_email": "listing_agent_email",
        "listing_brokerage": "listing_brokerage",
    }
    imported = []
    skipped = []

    for source_key, state_key in mapping.items():
        value = data.get(source_key)
        if value in [None, "", 0, 0.0]:
            continue
        if not can_import_over_state_field(state_key):
            skipped.append(state_key)
            continue
        if state_key in ["asking_price", "rent", "sqft", "days_on_market", "sheet_arv", "year_built"]:
            st.session_state[state_key] = int(float(value))
        elif state_key in ["beds", "baths"]:
            st.session_state[state_key] = float(value)
        else:
            st.session_state[state_key] = str(value)
        imported.append(state_key)

    if data.get("zpid"):
        st.session_state["apify_zpid"] = str(data.get("zpid"))

    st.session_state["apify_source"] = row.get("source", "Apify Zillow")
    st.session_state["apify_import_status"] = "Imported"
    st.session_state["apify_imported_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["apify_field_sources"] = field_sources
    st.session_state["apify_imported_fields"] = imported
    st.session_state["apify_skipped_manual_fields"] = skipped
    st.session_state["data_intake_source"] = "Zillow / Apify"
    st.session_state["lead_source"] = "Zillow / Apify"

    resolved_arv, value_source = resolve_value_source()
    st.session_state["arv"] = int(resolved_arv) if resolved_arv > 0 else 0
    st.session_state["value_source"] = value_source
    return imported, skipped


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
    if value_source == "Automatic Sold Comps" and st.session_state.get("arv_confidence") == "Weak":
        risks.append("Weak automatic sold comps used")
    if value_source in ["Zillow/Apify AVM", "RentCast Estimate"]:
        risks.append("AVM used only as fallback")
    if value_source == "Tax Assessment Reference":
        risks.append("Tax assessment used only as reference")
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
    if any("Functional risks plus weak buyer demand" in str(flag) for flag in risk_flags):
        return "Pass"
    if any(
        phrase in str(flag)
        for flag in risk_flags
        for phrase in [
            "Do not treat this as a clean buy",
            "Do not rely on wholesale exit",
            "No buyer outreach",
            "Buyer response shows no interest",
            "Confirmed buyer target",
            "Three or more exit obstacles",
            "very limited",
            "Require Human Review",
            "Wholesale Exit Risk",
            "Slow Flip Exit Risk",
        ]
    ):
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
        f"Buyer demand score is {st.session_state.get('buyer_demand_score', 'Weak')} and overall exit confidence is {st.session_state.get('overall_exit_confidence', 'Weak')}. "
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
    arv_confidence = st.session_state.get("arv_confidence", "Not enough data")
    arv_source_used = st.session_state.get("arv_source_used", st.session_state.get("value_source", "Missing"))
    weak_arv_source = arv_confidence in ["Weak", "AVM only", "Reference only", "Not enough data"] or arv_source_used in [
        "Zillow/Apify AVM",
        "Tax Assessment Reference",
        "Missing",
    ]
    exit_summary = build_exit_strategy_confidence(result, deal, missing_info, risk_flags)
    dispo_summary = build_dispo_test_summary(result, deal)
    weak_exit = exit_summary.get("overall_exit_confidence") == "Weak"
    limited_marketability = st.session_state.get("property_marketability") == "Very limited buyer pool"
    too_many_obstacles = len(st.session_state.get("exit_obstacles", []) or []) >= 3

    if critical_missing or weak_arv_source or weak_exit or best_exit == "Needs Human Review" or functional_risks or wholesale_percent < 0.55:
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

    if plain_answer == "Buy" and weak_arv_source:
        plain_answer = "Needs Human Review"
    if high_repairs and weak_arv_source:
        plain_answer = "Pass Unless Seller Takes Steal Price"
    if dispo_summary.get("buyer_response_level") == "No interest":
        plain_answer = "Renegotiate Hard" if asking <= hard_max or not hard_max else "Do Not Buy"
    if dispo_summary.get("recommendation") == "Pass":
        plain_answer = "Do Not Buy"
    if functional_risks and exit_summary.get("buyer_demand_score") == "Weak":
        plain_answer = "Pass Unless Seller Takes Steal Price"
    if limited_marketability and plain_answer in ["Buy", "Wholesale Only", "Slow Flip Only", "Renegotiate Hard"]:
        plain_answer = "Needs Human Review"
    if too_many_obstacles and plain_answer in ["Buy", "Wholesale Only", "Slow Flip Only", "Renegotiate Hard"]:
        plain_answer = "Needs Human Review"

    why = []
    if asking > hard_max > 0:
        why.append(f"Current price is above the hard max of {money(hard_max)}.")
    else:
        why.append(f"Current price is inside the modeled range for {best_exit}.")
    why.append(f"ARV/value source is {arv_source_used} at {money(deal.arv)} with {arv_confidence} confidence.")
    why.append(f"Rent is {money(deal.rent)} and repairs are {money(deal.repairs)}.")
    if weak_arv_source:
        why.append("ARV confidence is not strong enough for a clean Buy decision.")
    if best_exit == "Wholesale" and weak_arv_source:
        why.append("Wholesale spread depends on weak ARV support, so verify comps before sending a firm number.")
    if weak_exit:
        why.append("Do not treat this as a clean buy. Exit confidence is weak or unverified.")
    if exit_summary.get("exit_risk_warnings"):
        why.extend(exit_summary.get("exit_risk_warnings", [])[:3])
    if dispo_summary.get("warnings"):
        why.extend(dispo_summary.get("warnings", [])[:3])
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
    elif exit_summary.get("buyer_outreach_needed") == "Yes":
        next_move = "Confirm buyer demand first"
    elif dispo_summary.get("recommendation") in ["Lower offer", "Renegotiate"]:
        next_move = "Lower offer"
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
    if critical_missing or functional_risks or weak_exit:
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
        "buyer_demand_score": exit_summary.get("buyer_demand_score", "Weak"),
        "wholesale_exit_confidence": exit_summary.get("wholesale_exit_confidence", "Weak"),
        "slow_flip_exit_confidence": exit_summary.get("slow_flip_exit_confidence", "Weak"),
        "overall_exit_confidence": exit_summary.get("overall_exit_confidence", "Weak"),
        "exit_risk_warnings": exit_summary.get("exit_risk_warnings", []),
        "recommended_exit_strategy": exit_summary.get("recommended_exit_strategy", ""),
        "buyer_outreach_status": dispo_summary.get("outreach_status", "Not sent"),
        "buyer_feedback_summary": dispo_summary.get("best_buyer_feedback", ""),
        "confirmed_buyer_price": dispo_summary.get("confirmed_buyer_target_price", 0),
        "buyer_proof_level": st.session_state.get("buyer_proof", "Unknown"),
        "dispo_test_recommendation": dispo_summary.get("recommendation", "Get buyer commitment first"),
        "contract_status": st.session_state.get("contract_status", "Not under contract"),
        "deal_protection_status": st.session_state.get("deal_protection_mode", "Yes"),
        "buyer_message_allowed": st.session_state.get("buyer_message_allowed", "Teaser Only"),
        "protected_fields_hidden": st.session_state.get("protected_fields_hidden", []),
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
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Buyer Demand Score", simple_answer.get("buyer_demand_score", "Weak"))
        e2.metric("Wholesale Exit Confidence", simple_answer.get("wholesale_exit_confidence", "Weak"))
        e3.metric("Slow Flip Exit Confidence", simple_answer.get("slow_flip_exit_confidence", "Weak"))
        e4.metric("Overall Exit Confidence", simple_answer.get("overall_exit_confidence", "Weak"))
        if simple_answer.get("exit_risk_warnings"):
            st.write("Exit Risk Warnings:")
            for warning in simple_answer.get("exit_risk_warnings", []):
                st.warning(safe_condition_text(warning))
        st.info(f"Recommended Exit Strategy: {simple_answer.get('recommended_exit_strategy', '')}")
        b1, b2, b3 = st.columns(3)
        b1.metric("Buyer Outreach Status", simple_answer.get("buyer_outreach_status", "Not sent"))
        b2.metric("Confirmed Buyer Price", money(simple_answer.get("confirmed_buyer_price", 0)))
        b3.metric("Buyer Proof Level", simple_answer.get("buyer_proof_level", "Unknown"))
        p1, p2, p3 = st.columns(3)
        p1.metric("Contract Status", simple_answer.get("contract_status", "Not under contract"))
        p2.metric("Deal Protection Status", simple_answer.get("deal_protection_status", "Yes"))
        p3.metric("Buyer Message Allowed?", simple_answer.get("buyer_message_allowed", "Teaser Only"))
        hidden_fields = simple_answer.get("protected_fields_hidden", [])
        st.caption("Protected Fields Hidden: " + (", ".join(hidden_fields) if hidden_fields else "None"))
        if simple_answer.get("buyer_feedback_summary"):
            st.write("Buyer Feedback Summary:")
            st.write(safe_condition_text(simple_answer.get("buyer_feedback_summary", "")))
        st.info(f"Dispo Test Recommendation: {simple_answer.get('dispo_test_recommendation', 'Get buyer commitment first')}")
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


def render_exit_strategy_recommendation(exit_summary: dict, result: dict) -> None:
    st.subheader("Exit Strategy Recommendation")
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Best exit", result.get("best_exit", "Needs Human Review"))
        c2.metric("Backup exit", exit_summary.get("backup_exit_strategy", "Pass"))
        c3.metric("Exit confidence", exit_summary.get("overall_exit_confidence", "Weak"))
        c4.metric("Buyer outreach needed?", exit_summary.get("buyer_outreach_needed", "Yes"))

        st.write("What must be verified before offer:")
        verification_items = exit_summary.get("exit_verification_items", [])
        if verification_items:
            for item in verification_items:
                st.warning(str(item).title())
        else:
            st.success("No extra exit verification flagged.")

        checklist = exit_summary.get("buyer_outreach_checklist", [])
        if checklist:
            st.write("Buyer outreach checklist:")
            for item in checklist:
                st.write(f"- {item}")


def render_buyer_blast_messages(messages: dict) -> None:
    st.subheader("Buyer Blast Message Generator")
    with st.container(border=True):
        if st.session_state.get("buyer_message_allowed", "Teaser Only") != "Full Blast Allowed":
            st.warning(st.session_state.get("deal_protection_warning") or "Deal is not under contract. Use teaser only. Do not share exact address, seller/source details, parcel ID, or listing link.")
        st.text_area("Wholesale buyer text message", value=messages.get("buyer_blast_text", ""), height=120)
        st.text_area("Wholesale buyer email", value=messages.get("buyer_blast_email", ""), height=220)
        st.text_area("Slow flip / owner-finance buyer message", value=messages.get("slow_flip_buyer_message", ""), height=120)
        st.text_area("Internal team message", value=messages.get("internal_team_message", ""), height=120)


def render_dispo_test_summary(dispo_summary: dict) -> None:
    st.subheader("Dispo Test Summary")
    with st.container(border=True):
        d1, d2, d3 = st.columns(3)
        d1.metric("Outreach status", dispo_summary.get("outreach_status", "Not sent"))
        d2.metric("Buyer response level", dispo_summary.get("buyer_response_level", "Not sent yet"))
        d3.metric("Confirmed buyer target price", money(dispo_summary.get("confirmed_buyer_target_price", 0)))
        d4, d5 = st.columns(2)
        d4.metric("Exit confidence after outreach", dispo_summary.get("exit_confidence_after_outreach", "Weak"))
        d5.metric("Recommended action", dispo_summary.get("recommendation", "Get buyer commitment first"))
        concerns = dispo_summary.get("buyer_concerns", [])
        if concerns:
            st.caption("Buyer concerns: " + ", ".join(concerns))
        feedback = dispo_summary.get("best_buyer_feedback", "")
        if feedback:
            st.write("Best buyer feedback:")
            st.write(feedback)
        for warning in dispo_summary.get("warnings", []):
            st.warning(safe_condition_text(warning))
        st.write(dispo_summary.get("summary", ""))


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
    exit_summary = build_exit_strategy_confidence(result, deal, missing_info, risk_flags)
    store_exit_confidence_summary(exit_summary)
    dispo_summary = build_dispo_test_summary(result, deal)
    buyer_messages = generate_buyer_blast_messages(deal, result, dispo_summary)
    store_dispo_summary(dispo_summary, buyer_messages)
    risk_flags = list(dict.fromkeys(risk_flags + exit_summary.get("exit_risk_warnings", []) + dispo_summary.get("warnings", [])))
    final_decision = choose_final_decision(result, deal, missing_info, risk_flags)
    team_action = choose_team_action(final_decision, missing_info)
    decision_reason = build_decision_reason(result, deal, value_source, risk_flags)
    simple_answer = build_simple_deal_answer(result, deal, missing_info, risk_flags)

    render_simple_deal_answer(simple_answer)
    render_exit_strategy_recommendation(exit_summary, result)
    render_buyer_blast_messages(buyer_messages)
    render_dispo_test_summary(dispo_summary)
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

        a1, a2, a3 = st.columns(3)
        a1.metric("ARV Source Used", st.session_state.get("arv_source_used", value_source))
        a2.metric("ARV Confidence", st.session_state.get("arv_confidence", "Not enough data"))
        a3.metric("Recommended ARV", money(deal.arv))

        x1, x2, x3 = st.columns(3)
        x1.metric("Buyer Demand Score", exit_summary.get("buyer_demand_score", "Weak"))
        x2.metric("Recommended Exit Strategy", exit_summary.get("recommended_exit_strategy", "Human Review"))
        x3.metric("Overall Exit Confidence", exit_summary.get("overall_exit_confidence", "Weak"))

        o1, o2, o3 = st.columns(3)
        o1.metric("Buyer Outreach Status", dispo_summary.get("outreach_status", "Not sent"))
        o2.metric("Buyer Response", dispo_summary.get("buyer_response_level", "Not sent yet"))
        o3.metric("Dispo Test Recommendation", dispo_summary.get("recommendation", "Get buyer commitment first"))

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
        "exit_summary": exit_summary,
        "dispo_summary": dispo_summary,
        "buyer_messages": buyer_messages,
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
    exit_summary = final_summary.get("exit_summary", {})
    dispo_summary = final_summary.get("dispo_summary", {})
    buyer_messages = final_summary.get("buyer_messages", {})
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
        "arv_source_used": st.session_state.get("arv_source_used", value_source),
        "arv_confidence": st.session_state.get("arv_confidence", "Not enough data"),
        "arv_fallback_reason": st.session_state.get("arv_fallback_reason", ""),
        "arv_fallback_warnings": "; ".join(st.session_state.get("arv_fallback_warnings", [])),
        "manual_comps_average": manual_comps_average(),
        "automatic_comp_count": st.session_state.get("auto_comp_count", 0),
        "strong_comp_count": st.session_state.get("strong_comp_count", 0),
        "good_comp_count": st.session_state.get("good_comp_count", 0),
        "weak_comp_count": st.session_state.get("weak_comp_count", 0),
        "excluded_comp_count": st.session_state.get("excluded_comp_count", 0),
        "auto_low_arv": st.session_state.get("auto_low_arv", 0),
        "auto_conservative_arv": st.session_state.get("auto_conservative_arv", 0),
        "auto_average_arv": st.session_state.get("auto_average_arv", 0),
        "auto_high_arv": st.session_state.get("auto_high_arv", 0),
        "auto_recommended_arv": st.session_state.get("auto_recommended_arv", 0),
        "auto_comp_source": st.session_state.get("auto_comp_source", ""),
        "auto_comp_radius": st.session_state.get("auto_comp_radius", ""),
        "auto_comp_date_range": st.session_state.get("auto_comp_date_range", ""),
        "auto_comp_summary_json": st.session_state.get("auto_comp_summary_json", "[]"),
        "excluded_comp_flags_json": st.session_state.get("excluded_comp_flags_json", "[]"),
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
        "buyer_demand_confidence": st.session_state.get("buyer_demand_confidence", ""),
        "wholesale_buyer_list_strength": st.session_state.get("wholesale_buyer_list_strength", ""),
        "slow_flip_buyer_demand": st.session_state.get("slow_flip_buyer_demand", ""),
        "rental_demand_confidence": st.session_state.get("rental_demand_confidence", ""),
        "exit_strategy_confidence": st.session_state.get("exit_strategy_confidence", ""),
        "property_marketability": st.session_state.get("property_marketability", ""),
        "exit_obstacles": "; ".join(st.session_state.get("exit_obstacles", []) or []),
        "buyer_proof": st.session_state.get("buyer_proof", ""),
        "buyer_demand_score": exit_summary.get("buyer_demand_score", st.session_state.get("buyer_demand_score", "")),
        "wholesale_exit_confidence": exit_summary.get("wholesale_exit_confidence", st.session_state.get("wholesale_exit_confidence", "")),
        "slow_flip_exit_confidence": exit_summary.get("slow_flip_exit_confidence", st.session_state.get("slow_flip_exit_confidence", "")),
        "overall_exit_confidence": exit_summary.get("overall_exit_confidence", st.session_state.get("overall_exit_confidence", "")),
        "exit_risk_warnings": "; ".join(exit_summary.get("exit_risk_warnings", st.session_state.get("exit_risk_warnings", []))),
        "recommended_exit_strategy": exit_summary.get("recommended_exit_strategy", st.session_state.get("recommended_exit_strategy", "")),
        "backup_exit_strategy": exit_summary.get("backup_exit_strategy", st.session_state.get("backup_exit_strategy", "")),
        "buyer_outreach_needed": exit_summary.get("buyer_outreach_needed", st.session_state.get("buyer_outreach_needed", "")),
        "exit_verification_items": "; ".join(exit_summary.get("exit_verification_items", st.session_state.get("exit_verification_items", []))),
        "buyer_outreach_status": st.session_state.get("buyer_outreach_status", ""),
        "buyers_contacted_count": st.session_state.get("buyers_contacted_count", 0),
        "buyer_response_level": st.session_state.get("buyer_response_level", ""),
        "best_buyer_feedback": st.session_state.get("best_buyer_feedback", ""),
        "buyer_target_price_confirmed": st.session_state.get("buyer_target_price_confirmed", ""),
        "confirmed_buyer_target_price": st.session_state.get("confirmed_buyer_target_price", 0),
        "buyer_concerns": "; ".join(st.session_state.get("buyer_concerns", []) or []),
        "contract_status": st.session_state.get("contract_status", "Not under contract"),
        "deal_protection_mode": st.session_state.get("deal_protection_mode", "Yes"),
        "address_sharing_level": st.session_state.get("address_sharing_level", "Hide exact address"),
        "listing_source_sharing_level": st.session_state.get("listing_source_sharing_level", "Hide listing/source links"),
        "buyer_message_type": st.session_state.get("buyer_message_type", "Pre-contract demand check"),
        "pre_contract_teaser_message": st.session_state.get("pre_contract_teaser_message", ""),
        "under_contract_buyer_blast": st.session_state.get("under_contract_buyer_blast", ""),
        "protected_buyer_message": st.session_state.get("protected_buyer_message", ""),
        "exact_address_shared": st.session_state.get("exact_address_shared", "No"),
        "protected_fields_hidden": "; ".join(st.session_state.get("protected_fields_hidden", []) or []),
        "buyer_message_allowed": st.session_state.get("buyer_message_allowed", "Teaser Only"),
        "buyer_blast_text": buyer_messages.get("buyer_blast_text", st.session_state.get("buyer_blast_text", "")),
        "buyer_blast_email": buyer_messages.get("buyer_blast_email", st.session_state.get("buyer_blast_email", "")),
        "dispo_test_summary": dispo_summary.get("summary", st.session_state.get("dispo_test_summary", "")),
        "dispo_test_recommendation": dispo_summary.get("recommendation", st.session_state.get("dispo_test_recommendation", "")),
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
        "apify_source": st.session_state.get("apify_source", ""),
        "apify_import_status": st.session_state.get("apify_import_status", ""),
        "apify_imported_at": st.session_state.get("apify_imported_at", ""),
        "apify_zpid": st.session_state.get("apify_zpid", ""),
        "apify_dataset_id": st.session_state.get("apify_dataset_id", ""),
        "apify_actor_id": st.session_state.get("apify_actor_id", ""),
        "apify_duplicate_count": st.session_state.get("apify_duplicate_count", 0),
        "apify_imported_fields": "; ".join(st.session_state.get("apify_imported_fields", [])),
        "apify_skipped_manual_fields": "; ".join(st.session_state.get("apify_skipped_manual_fields", [])),
        "apify_field_sources_json": json.dumps(st.session_state.get("apify_field_sources", {})),
        "apify_last_error": st.session_state.get("apify_last_error", ""),
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


ui_context = SimpleNamespace(
    pd=pd,
    json=json,
    re=re,
    Assumptions=Assumptions,
    DealInput=DealInput,
    analyze_deal=analyze_deal,
    money=money,
    build_ai_summary=build_ai_summary,
    build_deal_protection_payload=build_deal_protection_payload,
    default_address_sharing_level=default_address_sharing_level,
    default_listing_source_sharing_level=default_listing_source_sharing_level,
    fetch_all_sources=fetch_all_sources,
    merge_results=merge_results,
    get_secret=get_secret,
    parse_listing_text=parse_listing_text,
    provider_connection_status=provider_connection_status,
    fetch_apify_zillow_dataset=fetch_apify_zillow_dataset,
    run_apify_zillow_actor=run_apify_zillow_actor,
    get_sold_comps=get_sold_comps,
    sold_comps_from_apify_rows=sold_comps_from_apify_rows,
    sold_comps_from_csv_rows=sold_comps_from_csv_rows,
    sold_comps_from_pasted_text=sold_comps_from_pasted_text,
    calculate_arv_from_comps=calculate_arv_from_comps,
    radius_to_float=radius_to_float,
    score_sold_comps=score_sold_comps,
    analyze_repairs=analyze_repairs,
    repair_number_for_offer=repair_number_for_offer,
    available_markets=available_markets,
    get_market_profile=get_market_profile,
    get_market_slow_flip_lead_search_max=get_market_slow_flip_lead_search_max,
    get_market_slow_flip_max_buy_price=get_market_slow_flip_max_buy_price,
    get_market_wholesale_buyer_percent=get_market_wholesale_buyer_percent,
    generate_boots_on_ground_notes=generate_boots_on_ground_notes,
    safe_float=safe_float,
    safe_condition_text=safe_condition_text,
    condition_wording_used=condition_wording_used,
    mold_verified_bool=mold_verified_bool,
    comp_subject=comp_subject,
    manual_comp_records=manual_comp_records,
    manual_comps_average=manual_comps_average,
    store_auto_arv_summary=store_auto_arv_summary,
    resolve_value_source=resolve_value_source,
    resolve_repair_source=resolve_repair_source,
    percent_label=percent_label,
    advanced_wholesale_buyer_model=advanced_wholesale_buyer_model,
    resolve_slow_flip_max_buy_price=resolve_slow_flip_max_buy_price,
    is_above_slow_flip_max_buy_price=is_above_slow_flip_max_buy_price,
    update_state_from_auto_pull=update_state_from_auto_pull,
    apply_apify_zillow_import=apply_apify_zillow_import,
    repair_cushion_percent_value=repair_cushion_percent_value,
    render_repair_number_explanation=render_repair_number_explanation,
    build_repair_breakdown=build_repair_breakdown,
    render_repair_estimate_breakdown=render_repair_estimate_breakdown,
    render_final_decision_box=render_final_decision_box,
    build_deal_log_row=build_deal_log_row,
    render_save_deal_analysis=render_save_deal_analysis,
    build_dispo_test_summary=build_dispo_test_summary,
    min_assignment_fee=min_assignment_fee,
    exception_assignment_fee=exception_assignment_fee,
    slow_flip_rent_multiple=slow_flip_rent_multiple,
    close_title_buffer=close_title_buffer,
    target_offer_discount=target_offer_discount,
    manual_wholesale_override=manual_wholesale_override,
    wholesale_buyer_percent_arv=wholesale_buyer_percent_arv,
    slow_flip_max_offer_cap=slow_flip_max_offer_cap,
    slow_flip_first_offer_gap=slow_flip_first_offer_gap,
)

render_lead_intake_section(st, ui_context)

st.caption("Works for Zillow, MLS, agent leads, and off-market sellers. Slow Flip uses rent/livability; ARV and repairs are reference unless you switch to Wholesale/Auto.")

exit_mode = st.radio(
    "Deal type",
    ["Slow Flip Only", "Wholesale Only", "Auto"],
    horizontal=True,
    help="Use Slow Flip Only for your normal owner-finance/slow-flip buy box. ARV/repairs are informational unless you switch to Wholesale/Auto.",
)

render_deal_protection_section(st, ui_context)
render_buyer_demand_section(st, EXIT_OBSTACLE_OPTIONS)
render_buyer_outreach_section(st, BUYER_CONCERN_OPTIONS)
uploaded_repair_files = render_repair_section(st, ui_context)
render_decision_section(st, ui_context, exit_mode, uploaded_repair_files)
