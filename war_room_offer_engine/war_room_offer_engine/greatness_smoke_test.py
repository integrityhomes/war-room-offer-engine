from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
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


greatness_test_ui = import_first(
    "ui_sections.greatness_test_ui",
    "war_room_offer_engine.ui_sections.greatness_test_ui",
    "war_room_offer_engine.war_room_offer_engine.ui_sections.greatness_test_ui",
)

weak_arv = greatness_test_ui.build_greatness_report(
    {
        "final_decision": "Buy",
        "arv_confidence": "AVM only",
        "rent_confidence": "Strong verified rent comps",
        "buyer_demand_confidence": "Strong buyer demand",
        "recommended_exit_strategy": "Wholesale",
        "buyer_message_allowed": "Full Blast Allowed",
        "contract_status": "Under contract",
        "asking_price": 50000,
        "risk_flags": ["Weak ARV"],
        "missing_info": ["Verify ARV"],
        "team_action": "Human Review",
    }
)
check(any(item["label"] == "Weak ARV blocks clean Buy" and item["status"] == "Fail" for item in weak_arv["checks"]), "weak ARV blocks clean buy")

weak_rent = greatness_test_ui.build_greatness_report(
    {
        "final_decision": "Buy",
        "arv_confidence": "Strong",
        "rent_confidence": "Weak / seller stated only",
        "recommended_exit_strategy": "Slow Flip",
        "deal_type": "Slow Flip Only",
        "buyer_demand_confidence": "Strong buyer demand",
        "rent_verification_needed": "Yes",
        "slow_flip_rent_risk": "RentCast could not verify rent.",
        "buyer_message_allowed": "Full Blast Allowed",
        "contract_status": "Under contract",
        "asking_price": 25000,
        "team_action": "Human Review",
    }
)
check(any(item["label"] == "Rent Fallback blocks clean Slow Flip" and item["status"] == "Fail" for item in weak_rent["checks"]), "weak rent blocks clean slow flip")

unknown_buyer = greatness_test_ui.build_greatness_report(
    {
        "final_decision": "Buy",
        "arv_confidence": "Strong",
        "rent_confidence": "Strong verified rent comps",
        "buyer_demand_confidence": "Unknown",
        "recommended_exit_strategy": "Wholesale",
        "buyer_message_allowed": "Full Blast Allowed",
        "contract_status": "Under contract",
        "asking_price": 70000,
        "risk_flags": ["Unknown buyer demand"],
        "team_action": "Get buyer commitment first",
    }
)
check(any(item["label"] == "Buyer demand blocks clean Wholesale" and item["status"] == "Fail" for item in unknown_buyer["checks"]), "unknown buyer demand blocks clean wholesale")

protection_leak = greatness_test_ui.build_greatness_report(
    {
        "contract_status": "Not under contract",
        "buyer_message_allowed": "Full Blast Allowed",
        "protected_buyer_message": "Full address 123 Secret St and https://www.zillow.com/homedetails/test",
        "address": "123 Secret St",
        "listing_url": "https://www.zillow.com/homedetails/test",
        "protected_fields_hidden": [],
        "arv_confidence": "Strong",
        "rent_confidence": "Strong verified rent comps",
        "buyer_demand_confidence": "Strong buyer demand",
    }
)
check(any(item["label"] == "Deal Protection pre-contract safety" and item["status"] == "Fail" for item in protection_leak["checks"]), "pre-contract protection leakage is caught")

clean_rollup = greatness_test_ui.build_confidence_rollup(
    {
        "arv_confidence": "Strong",
        "rent_confidence": "Strong verified rent comps",
        "buyer_demand_confidence": "Strong buyer demand",
        "repair_scope_confidence": "Contractor bid",
        "buyer_message_allowed": "Teaser Only",
    }
)
check(clean_rollup["overall"] == "Ready for Manager Review", "clean support can pass confidence rollup")

print("Greatness smoke test passed.")
