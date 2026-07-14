from __future__ import annotations

import json

from deal_library import build_snapshot, normalize_property_key, restore_snapshot, stable_deal_id


STATE = {
    "address": "1115 Matson Dr, Marion, VA 24354",
    "city": "Marion",
    "state": "VA",
    "zip": "24354",
    "listing_url": "https://www.zillow.com/homedetails/example",
    "decision_strategy": "Auto — Choose Best",
    "decision_current_negotiated_price": 25000,
    "decision_result": {
        "decision": "BUY",
        "strategy": "Slow Flip — Keep",
        "confidence": "Strong",
        "first_offer": 28000,
        "hard_max": 32000,
        "evaluations": [
            {"strategy": "Slow Flip — Keep", "decision": "BUY"},
            {"strategy": "Slow Flip — Wholesale", "decision": "HUMAN REVIEW"},
        ],
    },
    "rent": 1040,
    "rent_source": "RentCast",
    "rent_confidence": "Strong verified rent comps",
    "rentcast_rent_comps": [
        {"address": "Comp 1", "rent": 1300},
        {"address": "Comp 2", "rent": 750},
        {"address": "Comp 3", "rent": 1350},
        {"address": "Comp 4", "rent": 1100},
    ],
    "rentcast_rent_comp_count": 4,
    "arv": 35667,
    "arv_confidence": "Strong",
    "auto_sold_comps": [
        {"comp_address": "Sale 1", "sold_price": 34000},
        {"comp_address": "Sale 2", "sold_price": 37000},
        {"comp_address": "Sale 3", "sold_price": 36000},
    ],
    "auto_comp_count": 3,
    "repairs": 63476,
    "repair_notes": "Walkthrough was analyzed and saved.",
    "repair_analysis": {"recommended_repair_number": 63476, "scope": ["cleanout"]},
    "deal_library_status": "Negotiating",
    "deal_library_assigned_to": "Carlos",
    "deal_library_team_notes": "Seller counter expected Friday.",
    "deal_library_updated_by": "Shawn",
}


assert normalize_property_key("1115 Matson Drive, Marion, VA 24354") == normalize_property_key(
    "1115 Matson Dr Marion VA 24354"
)
assert stable_deal_id(STATE) == stable_deal_id({"address": "1115 Matson Drive Marion VA 24354"})

snapshot = build_snapshot(STATE)
assert snapshot["deal_id"]
assert snapshot["decision"] == "BUY"
assert snapshot["deal_lane"] == "Slow Flip — Keep"
assert snapshot["current_negotiated_price"] == 25000
assert snapshot["absolute_maximum"] == 32000
assert snapshot["rent_comp_count"] == 4
assert snapshot["sold_comp_count"] == 3
assert snapshot["assigned_to"] == "Carlos"
assert snapshot["state"]["rentcast_rent_comps"][0]["rent"] == 1300
assert snapshot["state"]["repair_analysis"]["recommended_repair_number"] == 63476
json.dumps(snapshot)

restored = {}
restore_snapshot(restored, snapshot)
assert restored["address"] == STATE["address"]
assert restored["decision_result"]["decision"] == "BUY"
assert restored["rentcast_rent_comp_count"] == 4
assert restored["auto_comp_count"] == 3
assert restored["deal_library_loaded_without_api"] is True
assert restored["deal_library_status"] == "Negotiating"
assert restored["deal_library_team_notes"] == "Seller counter expected Friday."

print("Google Sheet Team Deal Library smoke test passed.")
