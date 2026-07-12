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
    "parse_universal_listing_text",
    "universal_listing_from_record",
    "fetch_universal_apify_dataset",
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
check(
    apify_connector.parse_apify_dataset_id("https://api.apify.com/v2/datasets/abc123/items?clean=true") == "abc123",
    "Apify/Zillow dataset URL parses to dataset id",
)
missing_token_result = apify_connector.fetch_dataset_items("abc123", token="", limit=1)
check(
    not missing_token_result.get("ok") and "Missing Apify token" in missing_token_result.get("error", ""),
    "Apify/Zillow missing token fails safely",
)
universal_missing_token = data_sources.fetch_universal_apify_dataset("abc123", limit=1)
check(not universal_missing_token.get("ok"), "universal listing missing API token does not crash")

zillow_universal = data_sources.universal_listing_from_record(fake_zillow_record, source="Zillow")
check(zillow_universal["data"]["address"].startswith("123 Main St"), "Zillow-style fake record parses")
check(zillow_universal["data"]["asking_price"] == 85000, "Zillow-style fake record imports price")

redfin_text = """
Redfin listing: 456 Oak Ave, Lebanon, VA 24266
$72,500 2 beds 1 bath 920 sqft 18 days on market
Listed by Jane Agent, Blue Ridge Realty, jane@example.com, 276-555-1212
Redfin Estimate: $82,000
"""
redfin_universal = data_sources.parse_universal_listing_text("Redfin", "https://www.redfin.com/VA/Lebanon/456-Oak-Ave", redfin_text)
check(redfin_universal["data"]["address"].startswith("456 Oak Ave"), "Redfin-style fake pasted text parses")
check(redfin_universal["source"] == "Redfin", "Redfin-style source is detected")

realtor_text = """
Realtor.com listing 789 Pine Road, Cleveland, OH 44105
List price $59,900, 3 bedrooms, 1.5 bathrooms, 1,140 square feet, DOM 33
Brokerage: Test Realty Group
Realtor estimate: $74,000
"""
realtor_universal = data_sources.parse_universal_listing_text("Realtor.com", "https://www.realtor.com/realestateandhomes-detail/789-Pine-Road", realtor_text)
check(realtor_universal["data"]["address"].startswith("789 Pine Road"), "Realtor-style fake pasted text parses")
check(realtor_universal["data"]["baths"] == 1.5, "Realtor-style fake pasted text parses baths")

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
check(scored_comps[-1]["score"] == "Bad Comp", "bad comp is excluded")
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
lead_intake_ui = import_first(
    "ui_sections.lead_intake_ui",
    "war_room_offer_engine.ui_sections.lead_intake_ui",
    "war_room_offer_engine.war_room_offer_engine.ui_sections.lead_intake_ui",
)
check(hasattr(app, "build_simple_deal_answer"), "app simple deal answer function imports")
check(hasattr(app, "build_repair_breakdown"), "app repair breakdown function imports")
check(hasattr(app, "build_exit_strategy_confidence"), "app exit confidence function imports")
check(hasattr(app, "build_dispo_test_summary"), "app dispo test summary function imports")
check(hasattr(app, "generate_buyer_blast_messages"), "app buyer blast generator imports")
check(hasattr(app, "apply_apify_zillow_import"), "app Apify/Zillow import function imports")

app.st.session_state["asking_price"] = 99000
app.st.session_state["rent"] = app.FIELD_DEFAULTS["rent"]
app.st.session_state["address"] = ""
app.st.session_state["sheet_arv"] = 0
imported_fields, skipped_fields = app.apply_apify_zillow_import(normalized)
check("asking_price" in skipped_fields, "manual override wins during Apify/Zillow import")
check("address" in imported_fields and "rent" not in skipped_fields, "Apify/Zillow import fills blank/default lead fields")
check(app.st.session_state["apify_field_sources"].get("asking_price") == "price", "Apify/Zillow import stores field source map")

app.st.session_state["beds"] = 2
app.st.session_state["address"] = ""
manual_override_payload = data_sources.universal_listing_from_record(
    {
        "address": "222 Manual Override Rd",
        "price": "$55,000",
        "bedrooms": 3,
        "bathrooms": 1,
        "livingArea": 900,
    },
    source="MLS / Manual",
)
universal_imported, universal_skipped, universal_conflicts = lead_intake_ui._apply_universal_listing_import(app.st, manual_override_payload)
check(app.st.session_state["beds"] == 2 and "beds" in universal_skipped, "universal listing manual override wins")
check("Bed count conflict" in universal_conflicts, "universal listing flags bed count conflict")


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


def set_dispo_inputs(
    outreach_status="Not sent",
    buyers_contacted=0,
    response_level="Not sent yet",
    feedback="",
    target_confirmed="Pending",
    confirmed_price=0,
    concerns=None,
):
    app.st.session_state["buyer_outreach_status"] = outreach_status
    app.st.session_state["buyers_contacted_count"] = buyers_contacted
    app.st.session_state["buyer_response_level"] = response_level
    app.st.session_state["best_buyer_feedback"] = feedback
    app.st.session_state["buyer_target_price_confirmed"] = target_confirmed
    app.st.session_state["confirmed_buyer_target_price"] = confirmed_price
    app.st.session_state["buyer_concerns"] = concerns or []


set_exit_inputs()
set_dispo_inputs()
strong_exit = app.build_exit_strategy_confidence(result, deal, missing_info=[], risk_flags=[])
check(strong_exit["buyer_demand_score"] == "Strong", "strong buyer demand allows strong buyer demand score")
check(strong_exit["overall_exit_confidence"] == "Strong", "strong buyer demand allows strong exit confidence")

set_exit_inputs()
set_dispo_inputs(
    outreach_status="Buyer interest confirmed",
    buyers_contacted=8,
    response_level="Strong interest",
    feedback="Buyer wants it near the modeled number.",
    target_confirmed="Yes",
    confirmed_price=int(result["wholesale"]["buyer_target"] + 1000),
)
strong_response_exit = app.build_exit_strategy_confidence(result, deal, missing_info=[], risk_flags=[])
strong_response_dispo = app.build_dispo_test_summary(result, deal)
check(strong_response_exit["wholesale_exit_confidence"] == "Strong", "strong buyer response increases exit confidence")
check(strong_response_dispo["recommendation"] == "Proceed with offer", "strong buyer response supports proceed recommendation")

set_exit_inputs()
set_dispo_inputs(outreach_status="No buyer interest", buyers_contacted=6, response_level="No interest")
no_interest_answer = app.build_simple_deal_answer(result, deal, missing_info=[], risk_flags=[])
check(no_interest_answer["plain_answer"] in {"Do Not Buy", "Renegotiate Hard", "Needs Human Review"}, "no buyer interest downgrades decision")

set_exit_inputs()
set_dispo_inputs(
    outreach_status="Buyers responded",
    buyers_contacted=5,
    response_level="Some interest",
    target_confirmed="Yes",
    confirmed_price=int(result["wholesale"]["buyer_target"] - 15000),
)
low_target_dispo = app.build_dispo_test_summary(result, deal)
check(any("below the app buyer target" in warning for warning in low_target_dispo["warnings"]), "confirmed buyer target below app target creates warning")

messages = app.generate_buyer_blast_messages(deal, result, low_target_dispo)
check(messages["buyer_blast_text"] and messages["buyer_blast_email"], "buyer blast message generates")

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
set_dispo_inputs(outreach_status="Not sent", buyers_contacted=0, response_level="Not sent yet")
cleveland_answer = app.build_simple_deal_answer(cleveland_result, cleveland_deal, missing_info=[], risk_flags=[])
check(
    cleveland_answer["plain_answer"] in {"Pass Unless Seller Takes Steal Price", "Needs Human Review"},
    "Cleveland-style risk case becomes Pass Unless Steal Price or Needs Human Review",
)
check(
    cleveland_answer["dispo_test_recommendation"] in {"Get buyer commitment first", "Lower offer", "Pass"},
    "Cleveland-style deal with no buyer proof stays guarded by dispo recommendation",
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

protection_context = {
    "contract_status": "Not under contract",
    "deal_protection_mode": "Yes",
    "address_sharing_level": "Hide exact address",
    "listing_source_sharing_level": "Hide listing/source links",
    "buyer_message_type": "Pre-contract demand check",
    "address": "123 Secret St, Lebanon VA",
    "city": "Lebanon",
    "state": "VA",
    "market": "Lebanon VA",
    "beds": 2,
    "baths": 1,
    "arv": 65000,
    "repairs": 25000,
    "asking_price": 30000,
    "listing_url": "https://www.zillow.com/homedetails/123-secret-st",
    "notes": "street parking only and functional issues noted",
    "repair_notes": "possible mold in bathroom",
    "mold_verified": False,
}
protected = rules.build_deal_protection_payload(protection_context)
check(protected["exact_address_shared"] == "No", "not under contract hides exact address")
check("123 Secret St" not in protected["protected_buyer_message"], "protected teaser generates without exact address")
check(protected["buyer_message_allowed"] == "Teaser Only", "not under contract allows teaser only")

offer_sent_context = dict(protection_context)
offer_sent_context.update(
    {
        "contract_status": "Offer sent",
        "listing_source_sharing_level": "Hide listing/source links",
        "listing_agent_phone": "555-111-2222",
        "listing_agent_email": "agent@example.com",
    }
)
offer_sent = rules.build_deal_protection_payload(offer_sent_context)
check("zillow.com" not in offer_sent["protected_buyer_message"].lower(), "offer sent hides listing URL")
check("555-111-2222" not in offer_sent["protected_buyer_message"], "offer sent hides agent phone")
check("agent@example.com" not in offer_sent["protected_buyer_message"], "offer sent hides agent email")

under_contract_context = dict(protection_context)
under_contract_context.update(
    {
        "contract_status": "Under contract",
        "address_sharing_level": "Full address allowed",
        "listing_source_sharing_level": "Full links allowed",
        "buyer_message_type": "Under-contract buyer blast",
        "mold_verified": True,
    }
)
under_contract = rules.build_deal_protection_payload(under_contract_context)
check(under_contract["buyer_message_allowed"] == "Full Blast Allowed", "under contract allows full buyer blast")
check("123 Secret St" in under_contract["under_contract_buyer_blast"], "under contract blast includes full address")
check("zillow.com" in under_contract["under_contract_buyer_blast"].lower(), "under contract blast allows listing URL")

check("mold" not in protected["protected_buyer_message"].lower(), "buyer blast does not use the word mold unless Mold Verified is Yes")
mold_verified_context = dict(protection_context)
mold_verified_context["mold_verified"] = True
mold_allowed = rules.build_deal_protection_payload(mold_verified_context)
check("mold" in mold_allowed["protected_buyer_message"].lower(), "buyer blast may use mold when Mold Verified is Yes")

app.st.session_state["contract_status"] = "Not under contract"
app.st.session_state["deal_protection_mode"] = "Yes"
app.st.session_state["buyer_message_allowed"] = "Teaser Only"
app.st.session_state["protected_fields_hidden"] = protected["protected_fields_hidden"]
cleveland_protected_context = dict(protection_context)
cleveland_protected_context.update(
    {
        "market": "Cleveland OH",
        "city": "Cleveland",
        "address": "125 Risk Stack Ave, Cleveland OH",
        "notes": cleveland_deal.notes,
        "repair_notes": "high repairs",
    }
)
cleveland_protected = rules.build_deal_protection_payload(cleveland_protected_context)
app.st.session_state["protected_buyer_message"] = cleveland_protected["protected_buyer_message"]
cleveland_messages = app.generate_buyer_blast_messages(cleveland_deal, cleveland_result)
check(cleveland_messages["buyer_blast_text"] == cleveland_protected["protected_buyer_message"], "Cleveland-style risky deal generates teaser only when not under contract")

print("Startup smoke test passed.")
