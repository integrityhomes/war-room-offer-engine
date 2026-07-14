from __future__ import annotations

from deal_decision_logic import (
    AUTO,
    SLOW_KEEP,
    SLOW_WHOLESALE,
    build_decision,
    evaluate,
    rent_comp_count,
    rent_verified,
    sold_count,
)


ASSUMPTIONS = {
    "min_assignment_fee": 10000,
    "exception_assignment_fee": 5000,
    "slow_flip_rent_multiple": 45,
    "close_title_buffer": 1500,
    "slow_flip_max_offer_cap": 32000,
    "slow_flip_first_offer_gap": 4000,
    "slow_flip_max_buy_price": 50000,
}

ENGINE = {
    "wholesale": {
        "buyer_target": 0,
        "max_offer": 0,
        "first_offer": 0,
        "offer_to_send": 0,
    }
}

STATE = {
    "address": "1115 Matson Dr, Marion, VA 24354",
    "decision_lead_source": "Zillow / On-Market",
    "decision_asking_price": 64900,
    "decision_current_negotiated_price": 30000,
    "rent": 1050,
    "rentcast_rent_comp_count": 4,
    "rent_confidence": "Strong verified rent comps",
    "rent_verification_needed": "No",
    "arv": 35667,
    "arv_confidence": "Strong",
    "rentcast_value_comp_count": 3,
    "repairs": 63476,
    "repair_source": "AI Repair Estimate",
    "slow_flip_max_buy_price_used": 50000,
    "livable": "Unknown",
    "notes": "As-is slow flip. Final offer contingent on walkthrough.",
}

keep = evaluate(STATE, ASSUMPTIONS, ENGINE, SLOW_KEEP)
assert keep["decision"] == "BUY"
assert keep["hard_max"] == 32000
assert keep["first_offer"] == 28000
assert keep["projected_margin"] == 15750
assert "no assignment fee deducted" in keep["formula"].lower()

slow_wholesale = evaluate(STATE, ASSUMPTIONS, ENGINE, SLOW_WHOLESALE)
assert slow_wholesale["decision"] == "BUY"
assert "assignment target" in slow_wholesale["formula"].lower()

auto = build_decision(STATE, ASSUMPTIONS, ENGINE, AUTO)
assert auto["strategy"] == SLOW_KEEP
assert auto["decision"] == "BUY"

above_max = dict(STATE, decision_current_negotiated_price=33000)
assert build_decision(above_max, ASSUMPTIONS, ENGINE, AUTO)["decision"] == "DO NOT BUY"

missing_rent = dict(STATE, rent=0, rentcast_rent_comp_count=0, rent_verification_needed="Yes")
assert build_decision(missing_rent, ASSUMPTIONS, ENGINE, AUTO)["decision"] == "HUMAN REVIEW"

# Regression: merged RentCast enrichment originally used `rentcast_comp_count`
# and nested `one_load_normalized.data.rent_comps`, while the decision screen
# checked only `rentcast_rent_comp_count`. Actual returned comps must win over a
# stale verification flag in the same Streamlit run.
live_rentcast_state = dict(STATE)
live_rentcast_state.pop("rentcast_rent_comp_count")
live_rentcast_state.pop("rentcast_value_comp_count")
live_rentcast_state.update(
    {
        "rent": 1040,
        "rent_confidence": "Weak",
        "rent_verification_needed": "Yes",
        "rentcast_comp_count": 4,
        "one_load_normalized": {
            "data": {
                "rent": 1040,
                "rent_confidence": "Strong verified rent comps",
                "rent_comp_count": 4,
                "rent_comps": [{"rent": 1300}, {"rent": 750}, {"rent": 1350}, {"rent": 1100}],
                "rentcast_sold_comp_count": 3,
                "rentcast_sold_comps": [{"sold_price": 34000}, {"sold_price": 37000}, {"sold_price": 36000}],
            }
        },
    }
)
assert rent_comp_count(live_rentcast_state) == 4
assert rent_verified(live_rentcast_state)
assert sold_count(live_rentcast_state) == 3
assert build_decision(live_rentcast_state, ASSUMPTIONS, ENGINE, AUTO)["decision"] == "BUY"

print("Deal Decision Center Marion and RentCast state smoke tests passed.")
