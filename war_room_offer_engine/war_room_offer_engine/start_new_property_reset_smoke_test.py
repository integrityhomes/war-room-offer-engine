from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


# Load the same startup chain used by the app, then inspect the final Stability v1
# functions before the deferred runtime hotfix is installed by Streamlit's title.
importlib.import_module("one_load_sources_safe")
stability = importlib.import_module("production_stability")
hotfix = importlib.import_module("start_new_property_reset_hotfix")
identity = importlib.import_module("team_offer_identity")
preview = importlib.import_module("rentcast_intelligence_preview")
decision_ui = importlib.import_module("deal_decision_ui")


class LockedState(dict):
    """Model Streamlit keys that cannot be rewritten after widget creation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked: set[str] = set()

    def __setitem__(self, key, value):
        if str(key) in self.locked:
            raise RuntimeError(f"widget key is locked: {key}")
        return super().__setitem__(key, value)


class FakeSt:
    def __init__(self, state):
        self.session_state = state


hotfix.install_runtime_patch()
assert stability.clear_property_state is hotfix.clear_property_state_without_rewriting_preferences
assert decision_ui._reset is stability.reset_with_stability
assert decision_ui.render is stability.render_with_stability

state = LockedState(
    {
        identity.ACTIVE_MEMBER_KEY: "Shawn",
        identity.MEMBER_SELECTION_KEY: "Shawn",
        identity.CUSTOM_MEMBER_KEY: "",
        preview.PREVIEW_STATE_KEY: True,
        "war_room_active_section": "One-Load Deal",
        "deal_library_auto_save": True,
        "decision_property_input": "404 4th St, Montgomery, AL 36110",
        "decision_strategy": "Auto — Choose Best",
        "decision_asking_price": 37000,
        "rent": 1075,
        "rentcast_rent_comps": [{"rent": 1075}],
        "auto_sold_comps": [{"sold_price": 50000}],
        "one_load_normalized": {"data": {"address": "404 4th St"}},
        "decision_result": {"decision": "BUY"},
        "deal_library_deal_id": "old-deal",
        identity.DEAL_OFFER_MAKER_KEY: "Shawn",
    }
)
st = FakeSt(state)

# This is the exact button-click moment: every visible keyed widget is locked. The
# patched reset may write only its non-widget pending flag during this run.
state.locked.update(
    {
        identity.ACTIVE_MEMBER_KEY,
        identity.MEMBER_SELECTION_KEY,
        identity.CUSTOM_MEMBER_KEY,
        preview.PREVIEW_STATE_KEY,
        "war_room_active_section",
        "deal_library_auto_save",
        "decision_property_input",
        "decision_strategy",
        "decision_asking_price",
    }
)
hotfix.request_reset(st)
assert state[hotfix.PENDING_RESET_KEY] is True
assert state["decision_property_input"] == "404 4th St, Montgomery, AL 36110"
assert state[identity.ACTIVE_MEMBER_KEY] == "Shawn"

# On the next rerun the workspace selector and other global controls may already
# be instantiated before the Deal Decision Center. Keep those preference keys
# locked and prove the real reset does not rewrite them.
state.locked = {
    identity.ACTIVE_MEMBER_KEY,
    identity.MEMBER_SELECTION_KEY,
    identity.CUSTOM_MEMBER_KEY,
    preview.PREVIEW_STATE_KEY,
    "war_room_active_section",
    "deal_library_auto_save",
}
assert hotfix.apply_pending_reset(
    st,
    hotfix.reset_property_without_rewriting_preferences,
) is True
assert hotfix.PENDING_RESET_KEY not in state
assert state[identity.ACTIVE_MEMBER_KEY] == "Shawn"
assert state[identity.MEMBER_SELECTION_KEY] == "Shawn"
assert state[preview.PREVIEW_STATE_KEY] is True
assert state["war_room_active_section"] == "One-Load Deal"
assert state["deal_library_auto_save"] is True
assert "decision_property_input" not in state
assert "decision_asking_price" not in state
assert "rentcast_rent_comps" not in state
assert "auto_sold_comps" not in state
assert "decision_result" not in state
assert "deal_library_deal_id" not in state
assert identity.DEAL_OFFER_MAKER_KEY not in state

# Automatic cross-property cleanup runs after the current input widgets exist.
# It must preserve those input values by skipping them, never by reassigning them.
cross_property = LockedState(
    {
        identity.ACTIVE_MEMBER_KEY: "Sabrina",
        identity.MEMBER_SELECTION_KEY: "Sabrina",
        preview.PREVIEW_STATE_KEY: True,
        "war_room_active_section": "One-Load Deal",
        "decision_property_input": "1263 Allison Gap Rd, Saltville, VA 24370",
        "decision_strategy": "Slow Flip — Keep",
        "decision_asking_price": 32000,
        "rent": 1050,
        "rentcast_rent_comps": [{"rent": 1050}],
        "decision_result": {"decision": "BUY"},
        "deal_library_deal_id": "prior-property",
    }
)
cross_property.locked.update(
    {
        identity.ACTIVE_MEMBER_KEY,
        identity.MEMBER_SELECTION_KEY,
        preview.PREVIEW_STATE_KEY,
        "war_room_active_section",
        "decision_property_input",
        "decision_strategy",
        "decision_asking_price",
    }
)
removed = hotfix.clear_property_state_without_rewriting_preferences(
    cross_property,
    preserve_current_inputs=True,
)
assert removed
assert cross_property[identity.ACTIVE_MEMBER_KEY] == "Sabrina"
assert cross_property["decision_property_input"] == "1263 Allison Gap Rd, Saltville, VA 24370"
assert cross_property["decision_strategy"] == "Slow Flip — Keep"
assert cross_property["decision_asking_price"] == 32000
assert "rentcast_rent_comps" not in cross_property
assert "decision_result" not in cross_property
assert "deal_library_deal_id" not in cross_property

# The public reset alias still schedules rather than mutating visible widget keys.
second = LockedState(
    {
        identity.ACTIVE_MEMBER_KEY: "Carlos",
        identity.MEMBER_SELECTION_KEY: "Carlos",
        "decision_property_input": "101 Test St, Decatur, IL 62521",
    }
)
second.locked.update(
    {
        identity.ACTIVE_MEMBER_KEY,
        identity.MEMBER_SELECTION_KEY,
        "decision_property_input",
    }
)
stability.reset_with_stability(FakeSt(second))
assert second[hotfix.PENDING_RESET_KEY] is True
assert second[identity.ACTIVE_MEMBER_KEY] == "Carlos"
assert second["decision_property_input"] == "101 Test St, Decatur, IL 62521"

print("Start New Property preserved-widget reset smoke test passed.")
