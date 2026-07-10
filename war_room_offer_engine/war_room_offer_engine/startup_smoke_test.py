from __future__ import annotations

import contextlib
import io
import importlib
import inspect
import logging
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
logging.getLogger("streamlit").setLevel(logging.ERROR)

for import_path in [str(REPO_ROOT), str(APP_DIR)]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


def import_first(*module_names: str):
    last_error: Exception | None = None
    for module_name in module_names:
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            last_error = exc
    raise last_error or ImportError("No module names provided")


rules = import_first("rules", "war_room_offer_engine.rules", "war_room_offer_engine.war_room_offer_engine.rules")
price_book = import_first(
    "repair_price_book_il",
    "war_room_offer_engine.repair_price_book_il",
    "war_room_offer_engine.war_room_offer_engine.repair_price_book_il",
)
repair_analyzer = import_first(
    "repair_analyzer",
    "war_room_offer_engine.repair_analyzer",
    "war_room_offer_engine.war_room_offer_engine.repair_analyzer",
)
data_sources = import_first(
    "data_sources",
    "war_room_offer_engine.data_sources",
    "war_room_offer_engine.war_room_offer_engine.data_sources",
)
apify_connector = import_first(
    "apify_connector",
    "war_room_offer_engine.apify_connector",
    "war_room_offer_engine.war_room_offer_engine.apify_connector",
)
sold_comps = import_first(
    "sold_comps",
    "war_room_offer_engine.sold_comps",
    "war_room_offer_engine.war_room_offer_engine.sold_comps",
)

assumption_kwargs = {
    "min_assignment_fee": 10000,
    "exception_assignment_fee": 5000,
    "slow_flip_rent_multiple": 45,
    "close_title_buffer": 1500,
    "target_offer_discount": 0.85,
    "wholesale_buyer_percent_arv": 0.70,
    "wholesale_buyer_percent_source": "Market Default",
    "wholesale_buyer_percent_range": "",
    "wholesale_buyer_percent_reason": "Smoke test default",
    "market_liquidity_tier": "Normal investor market",
    "market_wholesale_buyer_percent": 0.70,
    "slow_flip_max_offer_cap": 32000,
    "slow_flip_first_offer_gap": 4000,
    "slow_flip_lead_search_max": 85000,
    "slow_flip_lead_search_source": "Market Default",
    "above_slow_flip_lead_search_range": False,
    "inside_slow_flip_lead_search_range": True,
    "slow_flip_max_buy_price": 50000,
    "slow_flip_max_source": "Market Default",
    "above_slow_flip_max_buy_price": False,
}

accepted_assumption_fields = set(inspect.signature(rules.Assumptions).parameters)
missing_assumption_fields = sorted(set(assumption_kwargs) - accepted_assumption_fields)
check(not missing_assumption_fields, f"Assumptions accepts app kwargs: {', '.join(assumption_kwargs)}")

assumptions = rules.Assumptions(**assumption_kwargs)
test_assumptions = rules.build_default_assumptions_for_test()
check(test_assumptions.slow_flip_lead_search_max == 85000, "default test assumptions include lead search max")
check(test_assumptions.slow_flip_max_buy_price == 50000, "default test assumptions include slow flip max buy price")

for function_name in [
    "available_markets",
    "get_market_profile",
    "get_market_wholesale_buyer_percent",
    "get_market_repair_multiplier",
    "get_market_slow_flip_lead_search_max",
    "get_market_slow_flip_max_buy_price",
]:
    check(hasattr(price_book, function_name), f"market helper exists: {function_name}")

markets = price_book.available_markets()
check("Central IL" in markets, "Central IL market loads")
virginia_markets = [market for market in markets if market.endswith(" VA")]
check(virginia_markets, "Virginia markets load")
for market in virginia_markets:
    check(price_book.get_market_slow_flip_lead_search_max(market) == 85000, f"{market} lead search max is 85000")
    check(price_book.get_market_slow_flip_max_buy_price(market) == 50000, f"{market} slow flip max buy price is 50000")

for function_name in ["analyze_repairs", "repair_number_for_offer"]:
    check(hasattr(repair_analyzer, function_name), f"repair analyzer function exists: {function_name}")

repair_analysis = repair_analyzer.analyze_repairs(
    notes="roof, kitchen, bath, paint, flooring",
    sqft=1000,
    baths=1,
    uploaded_files=[],
    market="Central IL",
    repair_level="Rental Ready",
    pricing_mode="Licensed contractor",
    repair_scope_confidence="Photos only",
    market_labor_cost="Normal market",
    repair_cushion_percent=10,
    manual_repair_adjustment=500,
)
check(repair_analysis.get("recommended_repair_number", 0) > 0, "repair breakdown generates a number")
check(repair_analyzer.repair_number_for_offer(repair_analysis) > 0, "repair number for offer works")
repair_calibration = repair_analysis.get("repair_calibration", {})
check(repair_calibration.get("base_repair_estimate", 0) > 0, "repair calibration tracks base estimate")
check(repair_calibration.get("final_repair_estimate", 0) == repair_analysis.get("recommended_repair_number", 0), "repair calibration drives final repair number")
check(repair_calibration.get("repair_math_rows"), "repair calibration exposes full repair math rows")

for function_name in [
    "fetch_all_sources",
    "merge_results",
    "get_secret",
    "parse_listing_text",
    "provider_connection_status",
    "fetch_apify_zillow_dataset",
    "run_apify_zillow_actor",
    "get_sold_comps",
    "sold_comps_from_apify_rows",
]:
    check(hasattr(data_sources, function_name), f"data_sources function exists: {function_name}")

fake_zillow_record = {
    "zpid": 123456,
    "streetAddress": "123 Main St",
    "city": "Richmond",
    "state": "VA",
    "zipcode": "23220",
    "price": "$85,000",
    "bedrooms": 3,
    "bathrooms": 1,
    "livingArea": 1100,
    "daysOnZillow": 12,
    "homeStatus": "FOR_SALE",
    "detailUrl": "/homedetails/123-Main-St-Richmond-VA-23220/123456_zpid/",
    "brokerName": "Sample Brokerage",
}
normalized = apify_connector.normalize_zillow_record(fake_zillow_record)
check(normalized.get("ok"), "fake Apify/Zillow record normalizes")
check(normalized["data"]["address"].startswith("123 Main St"), "Apify/Zillow address normalization works")
check(normalized["data"]["asking_price"] == 85000, "Apify/Zillow price normalization works")
check(normalized["field_sources"].get("asking_price") == "price", "Apify/Zillow field source tracking works")
missing_price = apify_connector.normalize_zillow_record({key: value for key, value in fake_zillow_record.items() if key != "price"})
check("Missing price" in missing_price.get("errors", []), "Apify/Zillow missing price is a clear error")
deduped = apify_connector.normalize_zillow_records([fake_zillow_record, dict(fake_zillow_record)])
check(len(deduped.get("rows", [])) == 1 and len(deduped.get("duplicates", [])) == 1, "Apify/Zillow duplicate-address protection works")

fake_comp_rows = [
    {
        "address": "120 Main St",
        "soldPrice": 150000,
        "soldDate": "2026-05-01",
        "bedrooms": 3,
        "bathrooms": 1,
        "livingArea": 1000,
        "distanceMiles": 0.2,
        "homeType": "Single Family",
        "confidence": "High",
    },
    {
        "address": "124 Main St",
        "soldPrice": 152000,
        "soldDate": "2026-04-15",
        "bedrooms": 3,
        "bathrooms": 1,
        "livingArea": 1050,
        "distanceMiles": 0.3,
        "homeType": "Single Family",
        "confidence": "High",
    },
    {
        "address": "126 Main St",
        "soldPrice": 148000,
        "soldDate": "2026-03-01",
        "bedrooms": 3,
        "bathrooms": 1,
        "livingArea": 980,
        "distanceMiles": 0.4,
        "homeType": "Single Family",
        "confidence": "High",
    },
    {
        "address": "999 Far Rd",
        "soldPrice": "",
        "soldDate": "",
        "livingArea": "",
        "distanceMiles": 8,
        "homeType": "Mobile Home",
    },
]
normalized_comps = sold_comps.normalize_sold_comps(fake_comp_rows, source="Smoke Test")
check(normalized_comps[0]["sold_price"] == 150000, "fake sold comp normalizes price")
subject = {"sqft": 1000, "beds": 3, "baths": 1, "property_type": "Single Family", "functional_risks": ""}
scored_comps = sold_comps.score_sold_comps(normalized_comps, subject, "1 mile", "Last 12 months")
check(scored_comps[0]["score"] == "Strong Comp", "strong sold comp scores correctly")
check(scored_comps[-1]["score"] == "Bad Comp", "bad sold comp is excluded")
auto_summary = sold_comps.calculate_arv_from_comps(scored_comps)
check(auto_summary["recommended_arv"] > 0, "automatic sold comps calculate recommended ARV")
manual_override_fallback = sold_comps.resolve_arv_fallback(
    manual_override=95000,
    manual_comp_average=90000,
    auto_summary=auto_summary,
    rentcast_value=120000,
    zillow_value=125000,
    tax_assessed_value=80000,
)
check(manual_override_fallback["source"] == "Manual Override" and manual_override_fallback["arv"] == 95000, "manual ARV override wins fallback")
manual_comp_fallback = sold_comps.resolve_arv_fallback(
    manual_override=0,
    manual_comp_average=90000,
    auto_summary=auto_summary,
    rentcast_value=120000,
    zillow_value=125000,
    tax_assessed_value=80000,
)
check(manual_comp_fallback["source"] == "Manual Comps", "manual comps outrank automatic comps")
avm_fallback = sold_comps.resolve_arv_fallback(rentcast_value=120000)
check(avm_fallback["confidence"] == "AVM only", "AVM fallback gets human-review confidence warning")
missing_fallback = sold_comps.resolve_arv_fallback()
check(missing_fallback["source"] == "Missing" and missing_fallback["arv"] == 0, "missing ARV fallback does not crash")

deal = rules.DealInput(
    address="123 Smoke Test Ave",
    market="Southside VA",
    lead_type="Agent",
    exit_mode="Wholesale Only",
    asking_price=75000,
    rent=900,
    beds=3,
    baths=1,
    sqft=1000,
    taxes=0,
    status="Active",
    occupancy="Vacant",
    livable="Yes",
    days_on_market=10,
    notes="clean wholesale test",
    arv=160000,
    repairs=20000,
)
result = rules.analyze_deal(deal, assumptions)
check(result["best_exit"] == "Wholesale", "wholesale path ignores slow flip max buy price")
check(result["wholesale"]["estimated_fee_at_ask"] >= assumptions.exception_assignment_fee, "wholesale fee math works")

with contextlib.redirect_stderr(io.StringIO()):
    app = import_first("app", "war_room_offer_engine.app", "war_room_offer_engine.war_room_offer_engine.app")
check(hasattr(app, "build_simple_deal_answer"), "app simple deal answer function imports")
check(hasattr(app, "build_repair_breakdown"), "app repair breakdown function imports")
check(hasattr(app, "build_exit_strategy_confidence"), "app exit confidence function imports")


def set_exit_inputs(
    buyer_demand="Strong buyer demand",
    buyer_list="Strong active buyers",
    slow_flip_demand="Strong",
    rental_demand="Strong verified rents",
    exit_confidence="Strong",
    marketability="Easy to sell",
    obstacles=None,
    buyer_proof="Buyer already interested",
    market_type="Normal investor market",
):
    app.st.session_state["buyer_demand_confidence"] = buyer_demand
    app.st.session_state["wholesale_buyer_list_strength"] = buyer_list
    app.st.session_state["slow_flip_buyer_demand"] = slow_flip_demand
    app.st.session_state["rental_demand_confidence"] = rental_demand
    app.st.session_state["exit_strategy_confidence"] = exit_confidence
    app.st.session_state["property_marketability"] = marketability
    app.st.session_state["exit_obstacles"] = obstacles or []
    app.st.session_state["buyer_proof"] = buyer_proof
    app.st.session_state["market_type"] = market_type
    app.st.session_state["arv_source_used"] = "Automatic Sold Comps"
    app.st.session_state["arv_confidence"] = "Strong"
    app.st.session_state["value_source"] = "Automatic Sold Comps"


set_exit_inputs()
strong_exit = app.build_exit_strategy_confidence(result, deal, missing_info=[], risk_flags=[])
check(strong_exit["buyer_demand_score"] == "Strong", "strong buyer demand allows strong buyer demand score")
check(strong_exit["overall_exit_confidence"] == "Strong", "strong buyer demand allows strong exit confidence")

set_exit_inputs(buyer_demand="Unknown", buyer_proof="Unknown")
unknown_exit = app.build_exit_strategy_confidence(result, deal, missing_info=[], risk_flags=[])
check(unknown_exit["overall_exit_confidence"] == "Weak", "unknown buyer demand downgrades exit confidence")

slow_flip_deal = rules.DealInput(
    address="124 Smoke Test Ave",
    market="Southside VA",
    lead_type="Agent",
    exit_mode="Slow Flip Only",
    asking_price=42000,
    rent=1000,
    beds=3,
    baths=1,
    sqft=1000,
    taxes=0,
    status="Active",
    occupancy="Vacant",
    livable="Yes",
    days_on_market=10,
    notes="clean slow flip test",
    arv=110000,
    repairs=15000,
)
slow_flip_result = rules.analyze_deal(slow_flip_deal, assumptions)
set_exit_inputs(rental_demand="Weak rent comps")
weak_rent_exit = app.build_exit_strategy_confidence(slow_flip_result, slow_flip_deal, missing_info=[], risk_flags=[])
check(weak_rent_exit["slow_flip_exit_confidence"] == "Weak", "weak rent comps downgrade slow flip confidence")

set_exit_inputs(buyer_list="No buyer list yet")
no_buyer_list_exit = app.build_exit_strategy_confidence(result, deal, missing_info=[], risk_flags=[])
check(no_buyer_list_exit["wholesale_exit_confidence"] == "Weak", "no buyer list downgrades wholesale confidence")

set_exit_inputs(marketability="Very limited buyer pool")
very_limited_answer = app.build_simple_deal_answer(result, deal, missing_info=[], risk_flags=[])
check(very_limited_answer["plain_answer"] == "Needs Human Review", "very limited buyer pool triggers Human Review")

set_exit_inputs(obstacles=["Low ceilings", "No driveway / street parking only", "Weak rent comps"])
obstacle_answer = app.build_simple_deal_answer(result, deal, missing_info=[], risk_flags=[])
check(obstacle_answer["plain_answer"] == "Needs Human Review", "three exit obstacles trigger Human Review")

cleveland_deal = rules.DealInput(
    address="125 Risk Stack Ave",
    market="Cleveland OH",
    lead_type="Agent",
    exit_mode="Auto",
    asking_price=52000,
    rent=750,
    beds=2,
    baths=1,
    sqft=850,
    taxes=0,
    status="Active",
    occupancy="Vacant",
    livable="Unknown",
    days_on_market=80,
    notes="low ceilings, no driveway, termite concern, weak rent comps, high repairs",
    arv=85000,
    repairs=42000,
)
cleveland_result = rules.analyze_deal(cleveland_deal, assumptions)
set_exit_inputs(
    buyer_demand="Limited buyer demand",
    buyer_list="Weak buyer list",
    slow_flip_demand="Weak",
    rental_demand="Weak rent comps",
    exit_confidence="Weak",
    marketability="Very limited buyer pool",
    obstacles=["Low ceilings", "No driveway / street parking only", "Termite / structural concern", "Weak rent comps", "High repairs"],
    buyer_proof="No buyer proof yet",
    market_type="Unknown",
)
cleveland_answer = app.build_simple_deal_answer(cleveland_result, cleveland_deal, missing_info=[], risk_flags=[])
check(
    cleveland_answer["plain_answer"] in {"Pass Unless Seller Takes Steal Price", "Needs Human Review"},
    "Cleveland-style risk case becomes Pass Unless Steal Price or Needs Human Review",
)

app.st.session_state["value_source"] = "RentCast Estimate"
app.st.session_state["arv_source_used"] = "RentCast Estimate"
app.st.session_state["arv_confidence"] = "AVM only"
with contextlib.redirect_stderr(io.StringIO()):
    simple_answer = app.build_simple_deal_answer(result, deal, missing_info=[], risk_flags=[])
check(simple_answer.get("plain_answer") == "Needs Human Review", "simple deal answer warns on weak AVM ARV")
check(
    any("Wholesale spread depends on weak ARV support" in reason for reason in simple_answer.get("why", [])),
    "wholesale weak ARV warning appears",
)

app.st.session_state["repair_analysis"] = repair_analysis
app.st.session_state["repairs"] = int(repair_analysis.get("recommended_repair_number", 0))
app.st.session_state["manual_repair_estimate"] = 0
app.st.session_state["manual_repair_notes"] = ""
app.st.session_state["repair_notes"] = "roof, kitchen, bath, paint, flooring"
with contextlib.redirect_stderr(io.StringIO()):
    repair_breakdown = app.build_repair_breakdown()
check(repair_breakdown.get("total_estimated_repairs", 0) > 0, "repair breakdown function works")

print("Startup smoke test passed.")
