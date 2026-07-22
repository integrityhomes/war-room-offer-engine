from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


scope = importlib.import_module("property_state_scope")
hotfix = importlib.import_module("start_new_property_reset_hotfix")
stability = importlib.import_module("production_stability")
identity = importlib.import_module("team_offer_identity")
preview = importlib.import_module("rentcast_intelligence_preview")


# Every production FIELD_DEFAULTS key must be deliberately classified. This makes
# a future property field fail CI until it is added to the property registry or is
# explicitly declared as a browser-session preference.
app_tree = ast.parse((APP_DIR / "app.py").read_text(encoding="utf-8"))
field_defaults: dict[str, object] = {}
for node in app_tree.body:
    if not isinstance(node, ast.Assign):
        continue
    if any(isinstance(target, ast.Name) and target.id == "FIELD_DEFAULTS" for target in node.targets):
        field_defaults = ast.literal_eval(node.value)
        break

assert field_defaults, "FIELD_DEFAULTS could not be read from the production app"
unclassified = scope.unclassified_keys(field_defaults.keys())
assert unclassified == [], f"Production fields missing reset classification: {unclassified}"


# Offer assumptions are global business rules, not property evidence. A reset must
# never remove them even though similarly named property fields are cleared.
global_assumptions = {
    "min_assignment_fee": 10000,
    "exception_assignment_fee": 5000,
    "close_title_buffer": 1500,
    "slow_flip_rent_multiple": 45,
    "slow_flip_max_offer_cap": 32000,
    "slow_flip_first_offer_gap": 4000,
    "wholesale_buyer_percent_arv": 0.70,
    "target_offer_discount": 0.90,
}
for key in global_assumptions:
    assert not scope.is_property_state_key(key), f"Global assumption incorrectly scoped to one property: {key}"


hotfix.install_runtime_patch()
assert stability._SESSION_PREFERENCE_KEYS is scope.SESSION_PREFERENCE_KEYS
assert stability._CURRENT_INPUT_KEYS is scope.CURRENT_INPUT_KEYS
assert stability._PROPERTY_PREFIXES is scope.PROPERTY_PREFIXES
assert stability._PROPERTY_EXACT_KEYS is scope.PROPERTY_EXACT_KEYS
assert stability._is_property_state_key is scope.is_property_state_key
assert stability.clear_property_state is hotfix.clear_property_state_without_rewriting_preferences


session_preferences = {
    identity.ACTIVE_MEMBER_KEY: "Sabrina",
    identity.MEMBER_SELECTION_KEY: "Sabrina",
    identity.CUSTOM_MEMBER_KEY: "",
    preview.PREVIEW_STATE_KEY: True,
    "war_room_active_section": "One-Load Deal",
    "deal_library_auto_save": True,
    "deal_library_search": "Montgomery",
    "deal_library_search_results": [{"deal_id": "saved-1"}],
    "show_full_repair_math": True,
}

current_property_inputs = {
    "decision_property_input": "1263 Allison Gap Rd, Saltville, VA 24370",
    "decision_strategy": "Slow Flip — Keep",
    "decision_lead_source": "MLS / Agent",
    "decision_asking_price": 32000,
    "decision_current_negotiated_price": 29000,
    "decision_latest_counter": 30000,
    "decision_seller_bottom_line": 29500,
    "decision_negotiation_status": "Counter received",
    "decision_negotiated_with": "Listing agent",
    "decision_last_negotiation": "Today",
    "decision_next_follow_up": "Tomorrow",
    "decision_negotiation_notes": "Property B negotiation",
    "decision_other_terms": "Property B terms",
    "one_load_input_method": "Property address",
    "one_load_property_address": "1263 Allison Gap Rd, Saltville, VA 24370",
    "one_load_lead_type": "On-market listing",
    "one_load_lead_source": "Zillow",
    "one_load_asking_price": 32000,
    "one_load_seller_desired_price": 30000,
    "deal_library_force_refresh": False,
    "rentcast_credit_guard_refresh_confirmed": False,
}

# Deliberately extreme Property A values make any leak into Property B obvious.
prior_property_state = {
    "address": "404 4th St",
    "city": "Montgomery",
    "state": "AL",
    "zip": "36110",
    "market": "Montgomery, AL",
    "rent": 9999,
    "arv": 999999,
    "manual_arv_override": 888888,
    "value_source": "Property A manual override",
    "strong_comp_count": 9,
    "good_comp_count": 8,
    "weak_comp_count": 7,
    "excluded_comp_count": 6,
    "excluded_comp_flags_json": '[{"property":"A"}]',
    "use_auto_arv_over_manual_comps": True,
    "comp_source": "Property A comps",
    "auto_sold_comps": [{"address": "Property A comp", "sold_price": 999999}],
    "manual_repair_estimate": 77777,
    "manual_repair_adjustment": 66666,
    "manual_repair_notes": "Property A repairs",
    "repair_source": "Property A walkthrough",
    "manual_slow_flip_max_override": 55555,
    "manual_rent_confidence": "Strong",
    "manual_rent_comp_count": 12,
    "manual_rent_comp_average": 9999,
    "mold_verified": "Yes - inspector verified",
    "data_intake_source": "Property A source",
    "market_labor_cost": "Property A labor",
    "property_marketability": "Property A only",
    "wholesale_buyer_list_strength": "Property A buyers",
    "slow_flip_buyer_demand": "Property A demand",
    "rental_demand_confidence": "Property A rental demand",
    "slow_flip_rent_risk": "Property A risk",
    "exit_strategy_confidence": "Strong",
    "wholesale_exit_confidence": "Strong",
    "slow_flip_exit_confidence": "Strong",
    "overall_exit_confidence": "Strong",
    "recommended_exit_strategy": "Property A exit",
    "backup_exit_strategy": "Property A backup",
    "buyers_contacted_count": 25,
    "best_buyer_feedback": "Property A buyer feedback",
    "confirmed_buyer_target_price": 123456,
    "pre_contract_teaser_message": "Property A teaser",
    "under_contract_buyer_blast": "Property A blast",
    "protected_buyer_message": "Property A protected message",
    "exact_address_shared": "Yes",
    "protected_fields_hidden": ["Property A field"],
    "slow_flip_buyer_message": "Property A slow-flip message",
    "internal_team_message": "Property A internal note",
    "zillow_runtime_binding": {"property": "A"},
    "recorded_sale_candidates": [{"property": "A"}],
    "sold_comp_search_radius": 5,
    "subject_property_identity": "Property A",
    "geocode_result": {"property": "A"},
    "rentcast_request_audit": [{"property": "A"}],
    "one_load_normalized": {"data": {"address": "Property A"}},
    "decision_result": {"decision": "BUY", "property": "A"},
    "deal_library_deal_id": "property-a-deal",
    "deal_offer_made_by": "Prior Teammate",
}

cross_property = {
    **session_preferences,
    **global_assumptions,
    **current_property_inputs,
    **prior_property_state,
}
removed = scope.clear_property_state(cross_property, preserve_current_inputs=True)
assert removed, "Cross-property cleanup removed no prior property state"

for key, value in session_preferences.items():
    assert cross_property.get(key) == value, f"Session preference changed during cleanup: {key}"
for key, value in global_assumptions.items():
    assert cross_property.get(key) == value, f"Global assumption changed during cleanup: {key}"
for key, value in current_property_inputs.items():
    assert cross_property.get(key) == value, f"Current Property B input changed during cleanup: {key}"
for key in prior_property_state:
    assert key not in cross_property, f"Property A state leaked into Property B: {key}"


# Start New Property clears the visible current-property inputs too, while keeping
# browser identity, workspace preferences, and global business assumptions.
new_property = {
    **session_preferences,
    **global_assumptions,
    **current_property_inputs,
    **prior_property_state,
}
scope.clear_property_state(new_property, preserve_current_inputs=False)
for key, value in session_preferences.items():
    assert new_property.get(key) == value, f"Session preference lost on Start New Property: {key}"
for key, value in global_assumptions.items():
    assert new_property.get(key) == value, f"Global assumption lost on Start New Property: {key}"
for key in current_property_inputs:
    assert key not in new_property, f"Current property input did not clear: {key}"
for key in prior_property_state:
    assert key not in new_property, f"Prior property state did not clear: {key}"


print(
    f"Property reset isolation passed: {len(field_defaults)} production defaults classified; "
    f"{len(prior_property_state)} prior-property fields cleared."
)
