from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


stability = importlib.import_module("app_stability_guard")
identity = importlib.import_module("team_offer_identity")


# Fresh production sessions must not begin with realistic-looking prototype data.
blank = {
    "asking_price": 35000,
    "rent": 900,
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
    "decision_asking_price": 0,
}
changed = stability.sanitize_demo_defaults(blank)
assert set(changed) == {"asking_price", "rent", "beds", "baths", "sqft"}
for key in changed:
    assert blank[key] == 0

# Once a real property exists, an actual 3/1/1,000-square-foot property or $900
# rent must not be erased merely because it matches a former demo value.
real = {
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "asking_price": 35000,
    "rent": 900,
    "beds": 3,
    "baths": 1,
    "sqft": 1000,
}
assert stability.sanitize_demo_defaults(real) == []
assert real["rent"] == 900


# A real offer calculation requires operator identity, a complete location, and
# at least one actual seller/negotiated price.
ready = {
    identity.ACTIVE_MEMBER_KEY: "Alice Johnson",
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "decision_asking_price": 37000,
}
status = stability.readiness(ready)
assert status["ready"] is True
assert status["operator"] == "Alice Johnson"
assert status["property_complete"] is True
assert status["price"] == 37000

no_operator = dict(ready)
no_operator[identity.ACTIVE_MEMBER_KEY] = ""
assert stability.readiness(no_operator)["ready"] is False
assert any("team member" in item for item in stability.readiness(no_operator)["missing"])

street_only = dict(ready)
street_only["decision_property_input"] = "404 4th St"
assert stability.readiness(street_only)["ready"] is False
assert any("complete property location" in item.lower() for item in stability.readiness(street_only)["missing"])

no_price = dict(ready)
no_price["decision_asking_price"] = 0
assert stability.readiness(no_price)["ready"] is False
assert any("price" in item.lower() for item in stability.readiness(no_price)["missing"])


# The highest-risk cross-property failure is old evidence surviving when a team
# member types a new property. The stability guard must clear all old facts,
# decision math, negotiation, and Deal Library identity while keeping the active
# teammate, verified-intelligence choice, and the newly typed address.
old_key = stability.canonical_property("1263 Allison Gap Rd, Saltville, VA 24370")
state = {
    identity.ACTIVE_MEMBER_KEY: "Bob Smith",
    identity.MEMBER_SELECTION_KEY: "Bob Smith",
    "rentcast_intelligence_mode": "verified",
    "war_room_active_section": "🏠 One-Load",
    stability.ANALYSIS_PROPERTY_KEY: old_key,
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "decision_asking_price": 37000,
    "decision_current_negotiated_price": 29000,
    "decision_result": {"decision": "BUY", "strategy": "Slow Flip — Keep"},
    "one_load_normalized": {"data": {"address": "1263 Allison Gap Rd"}},
    "rent": 1075,
    "rentcast_rent_comps": [{"address": "Old rent comp", "rent": 1100}],
    "arv": 47850,
    "auto_sold_comps": [{"address": "Old sale comp", "sold_price": 50000}],
    "repairs": 15000,
    "deal_library_deal_id": "old-deal",
    "deal_library_version": 4,
    "deal_offer_made_by": "Bob Smith",
}
assert stability.reconcile_property_state(state) is True
assert state["decision_property_input"] == "404 4th St, Montgomery, AL 36110"
assert state[identity.ACTIVE_MEMBER_KEY] == "Bob Smith"
assert state["rentcast_intelligence_mode"] == "verified"
assert state["war_room_active_section"] == "🏠 One-Load"
assert state["decision_asking_price"] == 0
assert state["decision_current_negotiated_price"] == 0
assert state["rent"] == 0
assert state["arv"] == 0
assert state["repairs"] == 0
assert "decision_result" not in state
assert "one_load_normalized" not in state
assert "rentcast_rent_comps" not in state
assert "auto_sold_comps" not in state
assert "deal_library_deal_id" not in state
assert "deal_offer_made_by" not in state
assert "prior property" in state[stability.NOTICE_KEY].lower()


# A forced refresh starts with clean evidence but intentionally preserves the
# current price, negotiation, Deal Library record, and teammate attribution.
refresh = {
    identity.ACTIVE_MEMBER_KEY: "Carla Jones",
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "decision_asking_price": 37000,
    "decision_current_negotiated_price": 29000,
    "deal_library_deal_id": "montgomery-deal",
    "deal_library_version": 2,
    "rent": 900,
    "arv": 100000,
    "decision_result": {"decision": "BUY"},
    "rentcast_rent_comps": [{"rent": 900}],
}
stability.clear_evidence_for_forced_refresh(refresh)
assert refresh["decision_asking_price"] == 37000
assert refresh["decision_current_negotiated_price"] == 29000
assert refresh["deal_library_deal_id"] == "montgomery-deal"
assert refresh[identity.ACTIVE_MEMBER_KEY] == "Carla Jones"
assert refresh["rent"] == 0
assert refresh["arv"] == 0
assert "decision_result" not in refresh
assert "rentcast_rent_comps" not in refresh


# Restoring another teammate's saved deal marks the correct analysis property but
# does not own or replace the current browser-session operator.
restored = {identity.ACTIVE_MEMBER_KEY: "Dana Lee"}
stability.mark_restored_snapshot(
    restored,
    {
        "address": "5500 Grand Lake Dr, San Antonio, TX 78244",
        "updated_at": "2026-07-20T12:00:00Z",
    },
)
assert restored[identity.ACTIVE_MEMBER_KEY] == "Dana Lee"
assert restored[stability.ANALYSIS_PROPERTY_KEY] == stability.canonical_property(
    "5500 Grand Lake Dr, San Antonio, TX 78244"
)
assert restored[stability.RUN_STATUS_KEY] == "Loaded from Team Deal Library"


# A fatal location mismatch can never retain a clean BUY even if some upstream
# component accidentally produced one.
fatal = {
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "decision_asking_price": 37000,
    stability.ANALYSIS_PROPERTY_KEY: stability.canonical_property("404 4th St, Montgomery, AL 36110"),
    "location_verification_failed": True,
    "location_verification_error": "RentCast resolved a different state.",
    "decision_result": {
        "decision": "BUY",
        "strategy": "Wholesale — MLS",
        "confidence": "Strong",
        "review_flags": [],
    },
}
assert stability.enforce_fatal_decision_guard(fatal) is True
assert fatal["decision_result"]["decision"] == "HUMAN REVIEW"
assert fatal["decision_result"]["confidence"] == "Weak"
assert any("different state" in flag.lower() for flag in fatal["decision_result"]["review_flags"])


# Global/team controls must never be included in the property reset contract.
for preserved_key in (
    identity.ACTIVE_MEMBER_KEY,
    identity.MEMBER_SELECTION_KEY,
    identity.CUSTOM_MEMBER_KEY,
    "rentcast_intelligence_mode",
    "war_room_active_section",
    "deal_library_auto_save",
    "decision_strategy",
):
    assert preserved_key not in stability.ALL_PROPERTY_KEYS

print("App stability guard smoke test passed.")
