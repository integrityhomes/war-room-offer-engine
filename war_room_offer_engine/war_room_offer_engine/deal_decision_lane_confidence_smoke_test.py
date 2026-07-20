from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


logic = importlib.import_module("deal_decision_logic")


assumptions = {
    "min_assignment_fee": 10000,
    "exception_assignment_fee": 5000,
    "slow_flip_rent_multiple": 45,
    "close_title_buffer": 1500,
    "slow_flip_max_offer_cap": 32000,
    "slow_flip_first_offer_gap": 4000,
}


medium_rural = {
    "address": "1263 Allison Gap Rd, Saltville, VA 24370",
    "decision_property_input": "1263 Allison Gap Rd, Saltville, VA 24370",
    "decision_strategy": logic.AUTO,
    "decision_lead_source": "Zillow / On-Market",
    "source_mode": "Zillow / Sheet Match",
    "decision_asking_price": 34900,
    "decision_current_negotiated_price": 30000,
    "rent": 1075,
    "verified_rent_comp_count": 6,
    "rentcast_rent_comp_count": 114,
    "rentcast_rent_comps": [{} for _ in range(25)],
    "rent_confidence": "Medium verified rent comps",
    "rent_verification_needed": "No",
    "rent_requires_human_verification": False,
    "rent_search_mode": "Rural",
    "rent_search_radius": 20.1,
    # Strong ARV evidence must not inflate a Slow Flip — Keep confidence rating.
    "arv": 95000,
    "verified_sold_comp_count": 5,
    "auto_comp_count": 25,
    "arv_confidence": "Strong",
    "arv_requires_human_verification": False,
}

result = logic.build_decision(medium_rural, assumptions, {}, logic.AUTO)
assert result["strategy"] == logic.SLOW_KEEP
assert result["decision"] == "BUY"
assert result["confidence"] == "Medium"
assert result["first_offer"] == 28000
assert result["hard_max"] == 32000
assert result["price"] == 30000
assert "local rental support" in result["next_action"].lower()
assert logic.rent_comp_count(medium_rural) == 6
assert logic.sold_count(medium_rural) == 5


# A genuinely local, recent, strong five-comp set may still earn Strong.
strong_local = dict(medium_rural)
strong_local.update(
    {
        "rent_confidence": "Strong verified rent comps",
        "rent_search_mode": "Local",
        "rent_search_radius": 3,
        "verified_rent_comp_count": 5,
    }
)
strong_result = logic.build_decision(strong_local, assumptions, {}, logic.AUTO)
assert strong_result["decision"] == "BUY"
assert strong_result["confidence"] == "Strong"


# A human-verification flag always blocks a clean BUY regardless of row counts.
needs_review = dict(medium_rural)
needs_review["rent_requires_human_verification"] = True
needs_review["rent_verification_needed"] = "Yes"
review_result = logic.build_decision(needs_review, assumptions, {}, logic.AUTO)
assert review_result["decision"] == "HUMAN REVIEW"
assert review_result["confidence"] == "Weak"
assert "verified rental comps" in review_result["missing"]


# Listing-based value rows cannot masquerade as verified closed sales.
listing_only = {
    "address": "100 Main St",
    "decision_property_input": "100 Main St",
    "decision_current_negotiated_price": 20000,
    "arv": 90000,
    "arv_source_used": "RentCast AVM — listing-based",
    "arv_confidence": "AVM only",
    "verified_sold_comp_count": 0,
    "auto_comp_count": 25,
    "rentcast_value_comp_count": 25,
    "repairs": 10000,
    "repair_source": "AI Repair Estimate",
}
assert logic.sold_count(listing_only) == 0
assert "verified ARV / recorded sold comps" in logic.missing_items(
    listing_only, logic.WHOLESALE_OFF_MARKET
)

print("Lane-specific deal confidence and verified-evidence smoke test passed.")
