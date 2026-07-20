from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


identity = importlib.import_module("team_offer_identity")
integration = importlib.import_module("team_offer_integration")
outreach = importlib.import_module("realtor_outreach")
library = importlib.import_module("deal_library")


messages = outreach.build_first_touch_outreach(
    agent_name="Stacy Spracklen",
    address="404 4th St, Montgomery, AL 36110",
    offer_price=28000,
    asking_price=37000,
    buyer_name="Maria Lopez",
)
for key in ("text", "email_body", "follow_up_text"):
    assert "Maria Lopez" in messages[key]
    assert "Shawn" not in messages[key]
assert messages["offer_made_by"] == "Maria Lopez"

contact_package = outreach.build_realtor_contact_package(
    record={
        "address": "404 4th St, Montgomery, AL 36110",
        "agent_name": "Stacy Spracklen",
        "agent_email": "stacy@example.com",
    },
    normalized={"address": "404 4th St, Montgomery, AL 36110", "asking_price": 37000},
    offer_price=28000,
    buyer_name="Maria Lopez",
)
master = outreach.build_master_feed_fields(
    contact_package=contact_package,
    max_price=32000,
    opening_offer=28000,
)
assert contact_package["offer_made_by"] == "Maria Lopez"
assert master["Offer_Made_By"] == "Maria Lopez"
assert "Maria Lopez" in master["Opening_Message"]

# The active browser-session teammate is used automatically when callers do not
# explicitly pass a sender name.
fake_streamlit = SimpleNamespace(
    session_state={
        identity.ACTIVE_MEMBER_KEY: "Jordan Lee",
        identity.DEAL_OFFER_MAKER_KEY: "Alice Jones",
    }
)
previous_streamlit = sys.modules.get("streamlit")
sys.modules["streamlit"] = fake_streamlit
try:
    automatic = outreach.build_first_touch_outreach(
        agent_name="Stacy Spracklen",
        address="404 4th St, Montgomery, AL 36110",
        offer_price=28000,
    )
finally:
    if previous_streamlit is None:
        sys.modules.pop("streamlit", None)
    else:
        sys.modules["streamlit"] = previous_streamlit
assert "Jordan Lee" in automatic["text"]
assert "Shawn" not in automatic["text"]

# Deal snapshots preserve the original offer maker while each saved version is
# attributed to the teammate currently working the deal.
state = {
    "address": "404 4th St, Montgomery, AL 36110",
    "decision_property_input": "404 4th St, Montgomery, AL 36110",
    "decision_result": {
        "strategy": "Slow Flip — Keep",
        "decision": "BUY",
        "confidence": "Medium",
        "first_offer": 28000,
        "hard_max": 32000,
    },
    identity.ACTIVE_MEMBER_KEY: "Jordan Lee",
    identity.DEAL_OFFER_MAKER_KEY: "Alice Jones",
    "deal_library_updated_by": "Jordan Lee",
}
snapshot = library.build_snapshot(state)
assert snapshot["offer_made_by"] == "Alice Jones"
assert snapshot["updated_by"] == "Jordan Lee"
assert snapshot["session_state"][identity.DEAL_OFFER_MAKER_KEY] == "Alice Jones"

restored = {
    identity.ACTIVE_MEMBER_KEY: "Bob Smith",
    identity.MEMBER_SELECTION_KEY: "Bob Smith",
    identity.CUSTOM_MEMBER_KEY: "",
}
library.restore_snapshot(restored, snapshot)
assert restored[identity.ACTIVE_MEMBER_KEY] == "Bob Smith"
assert restored[identity.DEAL_OFFER_MAKER_KEY] == "Alice Jones"
assert restored["deal_library_updated_by"] == "Bob Smith"

# Even outside Streamlit, the safe fallback is a role, never a person's name.
generic = integration.build_first_touch_outreach_for_team(
    agent_name="Stacy Spracklen",
    address="404 4th St, Montgomery, AL 36110",
    offer_price=28000,
    buyer_name="",
)
assert "Acquisitions Team" in generic["text"]
assert "Shawn" not in generic["text"]

print("Team-specific realtor outreach and Deal Library attribution smoke test passed.")
