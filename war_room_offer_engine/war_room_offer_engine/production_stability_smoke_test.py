from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


stability = importlib.import_module("production_stability")
preview = importlib.import_module("rentcast_intelligence_preview")
identity = importlib.import_module("team_offer_identity")
decision_ui = importlib.import_module("deal_decision_ui")


# Prototype numbers must disappear before a production property is loaded.
blank = {
    "address": "123 Main St, Decatur IL 62522",
    "asking_price": 35000,
    "contract_price": 35000,
    "rent": 900,
    "rent_source": "Missing / RentCast unavailable",
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
}
cleared = stability.sanitize_legacy_demo_defaults(blank)
assert set(cleared) == {"address", "asking_price", "contract_price", "rent", "beds", "baths", "sqft"}
assert blank["address"] == ""
assert blank["asking_price"] == 0
assert blank["rent"] == 0
assert blank["rent_confidence"] == "Missing"
assert blank["rent_verification_needed"] == "Yes"


# Real loaded evidence may legitimately equal an old fixture number and must stay.
loaded = {
    "decision_property_input": "100 Real St, Montgomery, AL 36110",
    "asking_price": 35000,
    "rent": 900,
    "beds": 3,
    "baths": 1,
    "sqft": 1000,
    "one_load_normalized": {
        "data": {
            "address": "100 Real St",
            "city": "Montgomery",
            "state": "AL",
            "zip": "36110",
            "rent": 900,
            "rent_comps": [{"address": "Nearby", "rent": 900}],
        }
    },
}
assert stability.sanitize_legacy_demo_defaults(loaded) == []
assert loaded["rent"] == 900
assert loaded["asking_price"] == 35000


# Moving to a new address clears every prior evidence family while preserving
# the teammate and the inputs already entered above the analysis button.
state = {
    identity.ACTIVE_MEMBER_KEY: "Jordan Smith",
    identity.MEMBER_SELECTION_KEY: "Jordan Smith",
    identity.CUSTOM_MEMBER_KEY: "",
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "decision_strategy": "Auto — Choose Best",
    "decision_asking_price": 37000,
    "decision_current_negotiated_price": 29900,
    "one_load_property_address": "404 4th St, Montgomery, AL 36110",
    "deal_library_force_refresh": True,
    "rentcast_credit_guard_refresh_confirmed": True,
    preview.PREVIEW_STATE_KEY: False,
    "rent": 1075,
    "rentcast_rent_comps": [{"rent": 1075}],
    "auto_sold_comps": [{"sold_price": 50000}],
    "location_verification_status": "Matched",
    "deal_library_deal_id": "old-deal",
    "one_load_normalized": {"data": {"address": "Old Property"}},
    "decision_result": {"decision": "BUY"},
    identity.DEAL_OFFER_MAKER_KEY: "Prior Teammate",
}
removed = stability.clear_property_state(state, preserve_current_inputs=True)
assert removed
assert state[identity.ACTIVE_MEMBER_KEY] == "Jordan Smith"
assert state["decision_property_input"] == "404 4th St, Montgomery, AL 36110"
assert state["decision_asking_price"] == 37000
assert state["deal_library_force_refresh"] is True
assert state[preview.PREVIEW_STATE_KEY] is True
assert "rentcast_rent_comps" not in state
assert "auto_sold_comps" not in state
assert "decision_result" not in state
assert "deal_library_deal_id" not in state
assert identity.DEAL_OFFER_MAKER_KEY not in state


# A decision is valid only for the exact property that produced its evidence.
matching = {
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "one_load_normalized": {
        "data": {
            "requested_property_address": "404 4th St, Montgomery, AL 36110",
            "rent": 1050,
            "rent_comps": [{"address": "Comp", "rent": 1050}],
        }
    },
    "decision_result": {"decision": "BUY"},
}
assert stability.analysis_matches_current_input(matching) is True
matching["decision_property_input"] = "1263 Allison Gap Rd, Saltville, VA 24370"
assert stability.analysis_matches_current_input(matching) is False


class FakeSt:
    def __init__(self, session_state):
        self.session_state = session_state


# A stale prior-property decision is hidden instead of being shown under a new address.
stale_st = FakeSt(matching)
assert stability.live_decision_with_property_match(stale_st, object()) == {}
assert matching[stability.STALE_ANALYSIS_KEY] is True


# A run is marked complete only when usable evidence exists and location did not fail.
successful = {
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "one_load_normalized": {
        "data": {
            "requested_property_address": "404 4th St, Montgomery, AL 36110",
            "location_verification_status": "Matched requested property",
            "rent_comps": [{"address": "Comp", "rent": 1050}],
        }
    },
}
assert stability.record_run_status(successful) is True
assert successful[stability.LAST_RUN_OK_KEY] is True
assert successful[stability.ANALYSIS_PROPERTY_KEY]

failed = {
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "one_load_normalized": {
        "data": {
            "location_verification_failed": True,
            "location_verification_error": "Wrong property",
        }
    },
}
assert stability.record_run_status(failed) is False
assert failed[stability.LAST_RUN_OK_KEY] is False
assert "Wrong property" in failed[stability.LAST_RUN_MESSAGE_KEY]


# Full startup must leave the stability layer as the final decision/UI contract.
importlib.import_module("one_load_sources_safe")
assert decision_ui.render is stability.render_with_stability
assert decision_ui._run is stability.run_with_stability
assert decision_ui._reset is stability.reset_with_stability
assert decision_ui._live_decision is stability.live_decision_with_property_match
assert preview.render_preview_control is stability.render_accuracy_first_control

print("Production stability foundation smoke test passed.")
