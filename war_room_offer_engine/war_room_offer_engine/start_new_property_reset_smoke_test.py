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


state = LockedState(
    {
        identity.ACTIVE_MEMBER_KEY: "Shawn",
        identity.MEMBER_SELECTION_KEY: "Shawn",
        identity.CUSTOM_MEMBER_KEY: "",
        preview.PREVIEW_STATE_KEY: True,
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

# This is the exact moment that previously crashed: the button is handled after
# the keyed widgets already exist. The patched reset may write only its non-widget
# pending flag during this run.
state.locked.update(
    {
        identity.ACTIVE_MEMBER_KEY,
        identity.MEMBER_SELECTION_KEY,
        identity.CUSTOM_MEMBER_KEY,
        preview.PREVIEW_STATE_KEY,
        "decision_property_input",
        "decision_strategy",
        "decision_asking_price",
    }
)
hotfix.request_reset(st)
assert state[hotfix.PENDING_RESET_KEY] is True
assert state["decision_property_input"] == "404 4th St, Montgomery, AL 36110"
assert state[identity.ACTIVE_MEMBER_KEY] == "Shawn"

# At the beginning of the next rerun no widgets are locked. The original stable
# reset now clears property evidence and keeps the browser-session teammate.
state.locked.clear()
immediate_reset = stability.reset_with_stability
assert hotfix.apply_pending_reset(st, immediate_reset) is True
assert hotfix.PENDING_RESET_KEY not in state
assert state[identity.ACTIVE_MEMBER_KEY] == "Shawn"
assert state[identity.MEMBER_SELECTION_KEY] == "Shawn"
assert state[preview.PREVIEW_STATE_KEY] is True
assert "decision_property_input" not in state
assert "decision_asking_price" not in state
assert "rentcast_rent_comps" not in state
assert "auto_sold_comps" not in state
assert "decision_result" not in state
assert "deal_library_deal_id" not in state
assert identity.DEAL_OFFER_MAKER_KEY not in state

# Runtime installation must leave the deferred functions as the final aliases used
# by the Deal Decision Center.
hotfix.install_runtime_patch()
assert decision_ui._reset is stability.reset_with_stability
assert decision_ui.render is stability.render_with_stability

second = LockedState(
    {
        identity.ACTIVE_MEMBER_KEY: "Sabrina",
        identity.MEMBER_SELECTION_KEY: "Sabrina",
        "decision_property_input": "1263 Allison Gap Rd, Saltville, VA 24370",
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
assert second[identity.ACTIVE_MEMBER_KEY] == "Sabrina"
assert second["decision_property_input"] == "1263 Allison Gap Rd, Saltville, VA 24370"

print("Start New Property deferred reset smoke test passed.")
