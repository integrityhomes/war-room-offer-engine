from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for import_path in [str(APP_DIR.parent.parent), str(APP_DIR)]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)


strategy = importlib.import_module("strategy_decision")
operator = importlib.import_module("simple_operator_ui_v2")


class FakeSt:
    def __init__(self, state):
        self.session_state = state


base_state = {
    "address": "1115 Matson Dr, Marion, VA 24354",
    "asking_price": 64900,
    "contract_price": 30000,
    "simple_asking_price": 64900,
    "simple_negotiated_price": 30000,
    "rent": 1050,
    "rent_source": "RentCast",
    "rent_confidence": "Strong verified rent comps",
    "rentcast_rent_comp_count": 4,
    "arv": 35667,
    "arv_source_used": "RentCast Estimate",
    "arv_confidence": "AVM only",
    "rentcast_value_comp_count": 3,
    "auto_comp_count": 3,
    "repairs": 63476,
    "repair_source": "AI Repair Estimate",
    "livable": "Unknown",
    "notes": "Needs cleanout and cosmetic work",
    "repair_notes": "Heavy cleanout and cosmetic condition",
    "slow_flip_rent_multiple_snapshot": 45,
    "min_assignment_fee_snapshot": 10000,
    "close_title_buffer_snapshot": 1500,
    "slow_flip_max_offer_cap_snapshot": 32000,
    "slow_flip_first_offer_gap_snapshot": 4000,
    "slow_flip_max_buy_price_used": 50000,
}

keep_terms = strategy.negotiation_position(
    {**base_state, "simple_deal_strategy": "Slow Flip — Keep"},
    {"first_offer": 0, "internal_max": 0},
    "Slow Flip — Keep",
)
assert keep_terms["hard_max"] == 32000
assert keep_terms["first_offer"] == 28000
assert keep_terms["position"] == "Inside buy box"
assert keep_terms["projected_margin"] == 15750

wholesale_slow_terms = strategy.negotiation_position(
    {**base_state, "simple_deal_strategy": "Slow Flip — Wholesale"},
    {"first_offer": 0, "internal_max": 0},
    "Slow Flip — Wholesale",
)
assert wholesale_slow_terms["hard_max"] == 32000
assert wholesale_slow_terms["first_offer"] == 28000
assert wholesale_slow_terms["projected_margin"] == 15750

keep_decision = operator.build_strategy_operator_decision(
    FakeSt({**base_state, "simple_deal_strategy": "Slow Flip — Keep"}),
    {"first_offer": 0, "internal_max": 0, "arv_source": "RentCast Estimate"},
)
assert keep_decision["verdict"] == "BUY"
assert keep_decision["hard_max"] == 32000
assert keep_decision["negotiated"] == 30000

high_price_decision = operator.build_strategy_operator_decision(
    FakeSt({**base_state, "simple_deal_strategy": "Slow Flip — Keep", "simple_negotiated_price": 35000, "contract_price": 35000}),
    {"first_offer": 0, "internal_max": 0},
)
assert high_price_decision["verdict"] == "BUY ONLY AT OR BELOW $32,000"
assert high_price_decision["seller_drop_needed"] == 3000

wholesale_state = {
    **base_state,
    "simple_deal_strategy": "Wholesale — MLS",
    "repairs": 5000,
    "simple_negotiated_price": 20000,
    "contract_price": 20000,
}
wholesale_decision = operator.build_strategy_operator_decision(
    FakeSt(wholesale_state),
    {"first_offer": 18000, "internal_max": 25000, "do_not_exceed": 25000, "arv_source": "Automatic Sold Comps"},
)
assert wholesale_decision["verdict"] == "BUY"
assert wholesale_decision["hard_max"] == 25000
assert wholesale_decision["projected_margin"] == 15000

print("Strategy and negotiated-price smoke test passed.")
