from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


stability = importlib.import_module("app_stability")
stability_runtime = importlib.import_module("app_stability_runtime")
identity = importlib.import_module("team_offer_identity")
preview = importlib.import_module("rentcast_intelligence_preview")
one_load = importlib.import_module("ui_sections.one_load_deal_ui")


class FakeState(dict):
    pass


# Stability installation removes demo defaults at their source while retaining
# the historical demo-value detector for backward-compatible imports.
stability.install_base()
stability_runtime.install()
assert one_load.ONE_LOAD_DEFAULTS["asking_price"] == 0
assert one_load.ONE_LOAD_DEFAULTS["rent"] == 0
assert one_load.ONE_LOAD_DEFAULTS["beds"] == 0.0
assert one_load.ONE_LOAD_DEFAULTS["baths"] == 0.0
assert one_load.ONE_LOAD_DEFAULTS["sqft"] == 0
assert 900 in one_load.ONE_LOAD_DEMO_VALUES["rent"]


# A fresh session must never display the old fake property numbers.
fresh = FakeState(
    {
        "asking_price": 35000,
        "contract_price": 0,
        "rent": 900,
        "beds": 3.0,
        "baths": 1.0,
        "sqft": 1000,
        "rent_source": "Missing / RentCast unavailable",
        "rent_confidence": "Weak",
    }
)
stability.clean_demo_defaults(fresh)
assert fresh["asking_price"] == 0
assert fresh["rent"] == 0
assert fresh["beds"] == 0
assert fresh["baths"] == 0
assert fresh["sqft"] == 0
assert fresh["rent_source"] == "Missing / not analyzed"
assert fresh["rent_confidence"] == "Missing"


# A legitimate $900 result tied to a real analyzed property must remain intact.
real_900 = FakeState(
    {
        "decision_property_input": "10 Main St, Marion, VA 24354",
        "rent": 900,
        "rent_source": "RentCast verified rental intelligence",
        "one_load_normalized": {
            "data": {
                "address": "10 Main St, Marion, VA 24354",
                "rent": 900,
                "rent_source": "RentCast verified rental intelligence",
            }
        },
    }
)
stability.clean_demo_defaults(real_900)
assert real_900["rent"] == 900


# Non-empty normalized evidence must beat an empty/stale session alias.
normalized_wins = FakeState(
    {
        "verified_rent_comp_count": 0,
        "one_load_normalized": {"data": {"verified_rent_comp_count": 6}},
    }
)
assert stability._state_value(normalized_wins, "verified_rent_comp_count", 0) == 6


# Changing properties clears every old evidence family but preserves the active
# teammate, selected verified-data mode, global assumptions, and chosen lane.
state = FakeState(
    {
        identity.ACTIVE_MEMBER_KEY: "Alice",
        identity.MEMBER_SELECTION_KEY: "Alice",
        preview.PREVIEW_STATE_KEY: True,
        "deal_library_auto_save": True,
        "repair_market": "Alabama",
        "decision_strategy": "Slow Flip — Keep",
        "decision_lead_source": "Off-Market Seller",
        "decision_property_input": "1 Old St, Marion, VA 24354",
        stability.CURRENT_INPUT_KEY: stability.property_key("1 Old St, Marion, VA 24354"),
        "decision_asking_price": 42000,
        "decision_current_negotiated_price": 30000,
        "rent": 1100,
        "rentcast_rent_comps": [{"rent": 1100}],
        "arv": 95000,
        "auto_sold_comps": [{"sold_price": 95000}],
        "decision_result": {"decision": "BUY"},
        "deal_library_deal_id": "old-deal",
        "rentcast_credit_guard_last_run_stats": {"successful_requests": 4},
        identity.DEAL_OFFER_MAKER_KEY: "Alice",
    }
)
stability.clear_property_state(
    state,
    input_value="2 New St, Montgomery, AL 36110",
    preserve_strategy=True,
)
assert state[identity.ACTIVE_MEMBER_KEY] == "Alice"
assert state[preview.PREVIEW_STATE_KEY] is True
assert state["deal_library_auto_save"] is True
assert state["repair_market"] == "Alabama"
assert state["decision_strategy"] == "Slow Flip — Keep"
assert state["decision_lead_source"] == "Off-Market Seller"
assert state["decision_property_input"] == "2 New St, Montgomery, AL 36110"
assert state["decision_asking_price"] == 0
assert state["decision_current_negotiated_price"] == 0
assert "rentcast_rent_comps" not in state
assert "auto_sold_comps" not in state
assert "decision_result" not in state
assert "deal_library_deal_id" not in state
assert "rentcast_credit_guard_last_run_stats" not in state
assert identity.DEAL_OFFER_MAKER_KEY not in state


# A result is usable only for the property it was analyzed against.
bound = FakeState(
    {
        "decision_property_input": "404 4th St, Montgomery, AL 36110",
        stability.ANALYSIS_PROPERTY_KEY: stability.property_key("404 4th St, Montgomery, AL 36110"),
        "one_load_normalized": {"data": {"address": "404 4th St, Montgomery, AL 36110"}},
    }
)
assert stability.analysis_matches_input(bound) is True
bound["decision_property_input"] = "1263 Allison Gap Rd, Saltville, VA 24370"
assert stability.analysis_matches_input(bound) is False


# Stamping creates an auditable run ID and binds the analysis to the exact input.
completed = FakeState(
    {
        "decision_property_input": "404 4th St, Montgomery, AL 36110",
        "rent": 1050,
        "arv": 65000,
        "verified_rent_comp_count": 4,
        "verified_sold_comp_count": 3,
        "location_verification_status": "Matched requested city/state/ZIP",
    }
)
normalized = {
    "data": {
        "address": "404 4th St, Montgomery, AL 36110",
        "rent": 1050,
        "arv": 65000,
        "verified_rent_comp_count": 4,
        "verified_sold_comp_count": 3,
    }
}
status = stability.stamp_analysis(completed, normalized)
assert status == stability.STATUS_COMPLETE
assert completed[stability.ANALYSIS_RUN_ID_KEY]
assert completed[stability.ANALYSIS_PROPERTY_KEY] == stability.property_key(
    "404 4th St, Montgomery, AL 36110"
)
assert normalized["analysis_run_id"] == completed[stability.ANALYSIS_RUN_ID_KEY]


# A cross-state or wrong-house resolution can never be marked complete.
blocked = FakeState(
    {
        "decision_property_input": "404 4th St, Montgomery, AL 36110",
        "location_verification_failed": True,
        "location_verification_error": "Resolved to a different property",
        "rent": 1400,
        "arv": 212727,
    }
)
blocked_status, blocked_errors, _ = stability.classify_analysis(blocked, {"data": {}})
assert blocked_status == stability.STATUS_BLOCKED
assert any("different property" in error.lower() for error in blocked_errors)


# The new workflow keeps the daily screen simple and moves optional controls,
# refresh controls, Team Deal Library, and full audit tools behind expanders.
source = inspect.getsource(stability.render_stable_operator_workflow)
assert "More deal details — optional" in source
assert "Paid data refresh and cost controls" in source
assert "Advanced engine controls and full audit details" in source
assert "Data Quality & Offer Readiness" not in source  # rendered by a dedicated helper
assert inspect.getsource(stability.render_compact_library).count("expanded=False") >= 1
assert "Use verified RentCast intelligence (recommended)" in inspect.getsource(
    stability.render_compact_verified_control
)

print("Stability-first operator workflow smoke test passed.")
