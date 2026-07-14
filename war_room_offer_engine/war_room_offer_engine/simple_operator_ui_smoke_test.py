from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for import_path in [str(APP_DIR.parent.parent), str(APP_DIR)]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)


module = importlib.import_module("simple_operator_ui")


class FakeSt:
    def __init__(self, state):
        self.session_state = state


marion_state = {
    "address": "1115 Matson Dr, Marion, VA 24354",
    "asking_price": 64900,
    "contract_price": 0,
    "rent": 1050,
    "rent_source": "RentCast",
    "rent_confidence": "Strong verified rent comps",
    "rentcast_rent_comp_count": 4,
    "arv": 35667,
    "arv_source_used": "RentCast Estimate",
    "arv_confidence": "AVM only",
    "rentcast_value_comp_count": 3,
    "repairs": 63476,
    "livable": "Unknown",
    "recommended_exit_strategy": "Slow Flip",
    "notes": "Needs cleanout and cosmetic work",
    "repair_notes": "Heavy cleanout, flooring and kitchen condition",
}
marion = module.build_operator_decision(
    FakeSt(marion_state),
    {
        "first_offer": 30000,
        "internal_max": 44120,
        "do_not_exceed": 44120,
        "final_simple_answer": "Human Review",
        "arv_source": "RentCast Estimate",
    },
)
assert marion["verdict"] == "BUY ONLY AT OR BELOW $44,120"
assert marion["first_offer"] == 30000
assert marion["hard_max"] == 44120
assert marion["rent_comps"] == 4
assert "slow flip" in " ".join(marion["reasons"]).lower()

missing_rent_state = dict(marion_state)
missing_rent_state["rent"] = 0
missing_rent_state["rentcast_rent_comp_count"] = 0
missing_rent = module.build_operator_decision(
    FakeSt(missing_rent_state),
    {"first_offer": 30000, "internal_max": 44120, "do_not_exceed": 44120},
)
assert missing_rent["verdict"] == "NEEDS MORE INFORMATION"

structural_state = dict(marion_state)
structural_state["notes"] = "Structural failure at foundation wall"
structural = module.build_operator_decision(
    FakeSt(structural_state),
    {"first_offer": 30000, "internal_max": 44120, "do_not_exceed": 44120},
)
assert structural["verdict"] == "REVIEW BEFORE BUYING"

bad_deal_state = dict(marion_state)
bad_deal_state["asking_price"] = 30000
bad_deal = module.build_operator_decision(
    FakeSt(bad_deal_state),
    {"first_offer": 0, "internal_max": 0, "do_not_exceed": 0, "final_simple_answer": "Pass"},
)
assert bad_deal["verdict"] == "NEEDS MORE INFORMATION" or bad_deal["verdict"] == "DO NOT BUY"

print("Simple operator decision smoke test passed.")
