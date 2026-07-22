from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


identity = importlib.import_module("team_offer_identity")


assert identity.parse_team_members(["Alice", "Bob", "Alice", "  Carla  "]) == [
    "Alice",
    "Bob",
    "Carla",
]
assert identity.parse_team_members('["Dana", "Eli"]') == ["Dana", "Eli"]
assert identity.parse_team_members("Fran; Gabe\nHarper | Ivan") == [
    "Fran",
    "Gabe",
    "Harper",
    "Ivan",
]

state = {
    identity.ACTIVE_MEMBER_KEY: "Jordan Lee",
    "one_load_normalized": {"data": {}},
}
assert identity.apply_active_member_to_deal(state, overwrite_offer_maker=True) is True
assert state[identity.DEAL_OFFER_MAKER_KEY] == "Jordan Lee"
assert state["decision_offer_made_by"] == "Jordan Lee"
assert state["deal_library_updated_by"] == "Jordan Lee"
assert state["deal_library_assigned_to"] == "Jordan Lee"
assert state["one_load_normalized"]["data"]["offer_made_by"] == "Jordan Lee"

# Opening a saved offer from Alice while Bob is the current operator preserves
# Alice as the original offer maker but attributes the new save to Bob.
state[identity.ACTIVE_MEMBER_KEY] = "Bob Smith"
state[identity.DEAL_OFFER_MAKER_KEY] = "Alice Jones"
state["deal_library_assigned_to"] = "Acquisitions Queue"
assert identity.apply_active_member_to_deal(state, overwrite_offer_maker=False) is True
assert state[identity.DEAL_OFFER_MAKER_KEY] == "Alice Jones"
assert state["deal_library_updated_by"] == "Bob Smith"
assert state["deal_library_assigned_to"] == "Acquisitions Queue"

assert identity.apply_active_member_to_deal(state, overwrite_offer_maker=True) is True
assert state[identity.DEAL_OFFER_MAKER_KEY] == "Bob Smith"


class LockedWidgetState(dict):
    """Model Streamlit refusing writes after keyed widgets are instantiated."""

    locked_keys = {"deal_library_updated_by", "deal_library_assigned_to"}

    def __setitem__(self, key, value):
        if key in self.locked_keys:
            raise RuntimeError(
                f"st.session_state.{key} cannot be modified after the widget with key {key} is instantiated."
            )
        return super().__setitem__(key, value)


# Clicking Save / Update happens after Updated By and Assigned To widgets exist.
# Audit attribution must still reach the snapshot data without crashing the app.
locked = LockedWidgetState(
    {
        identity.ACTIVE_MEMBER_KEY: "Taylor Reed",
        identity.DEAL_OFFER_MAKER_KEY: "Original Buyer",
        "deal_library_updated_by": "Taylor Reed",
        "deal_library_assigned_to": "",
        "one_load_normalized": {"data": {}},
    }
)
assert identity.apply_active_member_to_deal(locked, overwrite_offer_maker=False) is True
assert locked[identity.DEAL_OFFER_MAKER_KEY] == "Original Buyer"
assert locked["decision_offer_made_by"] == "Original Buyer"
assert locked["one_load_normalized"]["data"]["updated_by"] == "Taylor Reed"
assert locked["one_load_normalized"]["data"]["offer_made_by"] == "Original Buyer"

missing = {}
identity.initialize_state(missing)
assert identity.apply_active_member_to_deal(missing) is False
assert identity.active_team_member(missing) == ""

print("Team member roster and offer attribution smoke test passed.")
