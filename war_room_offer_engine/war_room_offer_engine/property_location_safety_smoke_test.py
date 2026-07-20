from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


guard = importlib.import_module("property_location_guard")
safety = importlib.import_module("property_location_safety")
decision_guard = importlib.import_module("property_location_decision_guard")
decision_logic = importlib.import_module("deal_decision_logic")
decision_guard.install()


# Street-only inputs are ambiguous and must be stopped before a paid request.
complete, message = guard.validate_property_input("404 4th St")
assert complete is False
assert "street, city, state" in message.lower()

# Full city/state or a ZIP is sufficient to identify the requested geography.
for address in [
    "404 4th St, Montgomery, AL",
    "404 4th St, Montgomery, AL 36110",
    "1263 Allison Gap Rd, Saltville, VA 24370",
    "5500 Grand Lake Dr, San Antonio, TX 78244",
    "404 4th St 36110",
]:
    assert guard.validate_property_input(address)[0] is True, address

assert guard.validate_property_input("https://www.zillow.com/homedetails/example")[0] is True

parsed = guard.parse_property_input("404 4th St, Montgomery, AL 36110")
assert parsed["street"] == "404 4th St"
assert parsed["city"] == "Montgomery"
assert parsed["state"] == "AL"
assert parsed["zip"] == "36110"
assert guard.parse_property_input("404 4th Street 36110")["street"] == "404 4th Street"

# The live failure resolved a Montgomery, Alabama street-only input to Idaho.
# A full Montgomery address must reject that subject before rent/ARV searches.
valid, mismatch = guard.validate_resolved_location(
    "404 4th St, Montgomery, AL 36110",
    {
        "formatted_address": "404 4th St, Saint Maries, ID 83861",
        "address": "404 4th St",
        "city": "Saint Maries",
        "state": "ID",
        "zip": "83861",
    },
)
assert valid is False
assert "different property or location" in mismatch.lower()
assert "id instead of al" in mismatch.lower()

# Even the same city/state/ZIP is not enough when RentCast returns a different house.
valid, mismatch = guard.validate_resolved_location(
    "404 4th St, Montgomery, AL 36110",
    {
        "formatted_address": "406 4th St, Montgomery, AL 36110",
        "address": "406 4th Street",
        "city": "Montgomery",
        "state": "AL",
        "zip": "36110",
    },
)
assert valid is False
assert "406 4th street instead of 404 4th st" in mismatch.lower()

# Common street suffix variations should still match the same property.
valid, mismatch = guard.validate_resolved_location(
    "404 4th Street, Montgomery, AL 36110",
    {
        "formatted_address": "404 4th St, Montgomery, AL 36110",
        "address": "404 4th St",
        "city": "Montgomery",
        "state": "AL",
        "zip": "36110",
    },
)
assert valid is True
assert mismatch == ""

# Incomplete input must return a safe empty result without invoking enrichment.
called = {"count": 0}
original_enrich = safety._ORIGINAL_ENRICH


def should_not_run(*args, **kwargs):
    called["count"] += 1
    raise AssertionError("paid enrichment should not run for an incomplete address")


safety._ORIGINAL_ENRICH = should_not_run
try:
    empty = safety._safe_enrich({"address": "404 4th St"}, "test-key")
finally:
    safety._ORIGINAL_ENRICH = original_enrich

assert called["count"] == 0
assert empty["location_verification_failed"] is True
assert empty["rent"] == 0
assert empty["arv"] == 0
assert empty["rent_comps"] == []
assert empty["auto_sold_comps"] == []

# Search labels describe distance expansion, not whether the municipality is rural.
assert [stage["name"] for stage in safety._NEUTRAL_SOLD_STAGES] == [
    "Local", "Expanded", "Wide area", "Extended area", "Remote area"
]
assert safety._neutral_search_mode(20.0, 0, True) == "Wide area"
assert safety._neutral_search_mode(35.0, 0, True) == "Remote area"

invalid = guard.invalid_location_result("404 4th St", "Ambiguous location")
assert invalid["verified_sold_comp_count"] == 0
assert invalid["verified_rent_comp_count"] == 0
assert invalid["arv_requires_human_verification"] is True
assert invalid["rent_requires_human_verification"] is True

# Even strong-looking rent numbers cannot produce a clean BUY when the address is
# incomplete or the subject record failed exact-location verification.
assumptions = {
    "min_assignment_fee": 10000,
    "exception_assignment_fee": 5000,
    "slow_flip_rent_multiple": 45,
    "close_title_buffer": 1500,
    "slow_flip_max_offer_cap": 32000,
    "slow_flip_first_offer_gap": 4000,
    "slow_flip_max_buy_price": 50000,
}
engine = {"wholesale": {"buyer_target": 0, "max_offer": 0, "first_offer": 0, "offer_to_send": 0}}
base_state = {
    "decision_strategy": decision_logic.SLOW_KEEP,
    "decision_current_negotiated_price": 29900,
    "rent": 1400,
    "verified_rent_comp_count": 10,
    "rent_confidence": "Strong verified rent comps",
    "rent_verification_needed": "No",
    "rent_search_mode": "Local",
    "rent_search_radius": 5,
}

incomplete_decision = decision_logic.build_decision(
    {**base_state, "decision_property_input": "404 4th St"},
    assumptions,
    engine,
    decision_logic.SLOW_KEEP,
)
assert incomplete_decision["decision"] == "HUMAN REVIEW"
assert "complete property location" in incomplete_decision["missing"]

mismatch_decision = decision_logic.build_decision(
    {
        **base_state,
        "decision_property_input": "404 4th St, Montgomery, AL 36110",
        "location_verification_failed": True,
    },
    assumptions,
    engine,
    decision_logic.SLOW_KEEP,
)
assert mismatch_decision["decision"] == "HUMAN REVIEW"
assert "verified property location" in mismatch_decision["missing"]

matching_decision = decision_logic.build_decision(
    {
        **base_state,
        "decision_property_input": "404 4th St, Montgomery, AL 36110",
        "location_verification_failed": False,
    },
    assumptions,
    engine,
    decision_logic.SLOW_KEEP,
)
assert matching_decision["decision"] == "BUY"

print("Property location safety smoke test passed.")
