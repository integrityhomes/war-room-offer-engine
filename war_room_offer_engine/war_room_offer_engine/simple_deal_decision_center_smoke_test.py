from __future__ import annotations

from dataclasses import dataclass

from simple_deal_decision_center import (
    LANE_SLOW_KEEP,
    LANE_WHOLESALE_MLS,
    build_lane_evaluations,
    select_recommended_lane,
)


@dataclass
class Assumptions:
    slow_flip_rent_multiple: float = 45
    min_assignment_fee: float = 10000
    exception_assignment_fee: float = 5000
    close_title_buffer: float = 1500
    slow_flip_max_offer_cap: float = 32000
    slow_flip_max_buy_price: float = 50000
    slow_flip_first_offer_gap: float = 4000


result = {
    "wholesale": {
        "buyer_target": 0,
        "max_offer": 0,
        "offer_to_send": 0,
    }
}

marion_state = {
    "asking_price": 64900,
    "current_negotiated_price": 30000,
    "latest_counter": 0,
    "seller_bottom_line": 0,
    "rent": 1050,
    "rent_confidence": "Strong verified rent comps",
    "rent_comp_count": 4,
    "rent_verification_needed": "No",
    "arv": 35667,
    "arv_confidence": "AVM only",
    "repairs": 63476,
    "repair_source": "AI Repair Estimate",
    "livable": "Yes",
    "notes": "Property sold as-is for slow flip.",
    "repair_notes": "Heavy cleanout and cosmetic condition.",
    "manual_repair_notes": "",
    "negotiation_notes": "",
}

rows = build_lane_evaluations(marion_state, result, Assumptions())
keep = next(row for row in rows if row["lane"] == LANE_SLOW_KEEP)
wholesale = next(row for row in rows if row["lane"] == LANE_WHOLESALE_MLS)

assert keep["decision"] == "BUY"
assert keep["absolute_max"] == 32000
assert keep["starting_offer"] == 28000
assert keep["expected_spread"] == 15750
# The $63,476 retail-style repair estimate must not reduce the Slow Flip Keep max.
assert keep["absolute_max"] > 0
# Wholesale still uses the repair/value math and is not a buy in this fixture.
assert wholesale["decision"] in ["DO NOT BUY", "HUMAN REVIEW"]

recommended = select_recommended_lane(rows, "Auto — choose best", "Zillow / on-market listing")
assert recommended["lane"] == LANE_SLOW_KEEP
assert recommended["decision"] == "BUY"

above_max = dict(marion_state)
above_max["current_negotiated_price"] = 33000
rows_above = build_lane_evaluations(above_max, result, Assumptions())
keep_above = next(row for row in rows_above if row["lane"] == LANE_SLOW_KEEP)
assert keep_above["decision"] == "DO NOT BUY"
assert keep_above["absolute_max"] == 32000

missing_rent = dict(marion_state)
missing_rent["rent"] = 0
missing_rent["rent_comp_count"] = 0
missing_rent["rent_verification_needed"] = "Yes"
rows_missing = build_lane_evaluations(missing_rent, result, Assumptions())
keep_missing = next(row for row in rows_missing if row["lane"] == LANE_SLOW_KEEP)
assert keep_missing["decision"] == "HUMAN REVIEW"

print("Simple Deal Decision Center smoke test passed.")
