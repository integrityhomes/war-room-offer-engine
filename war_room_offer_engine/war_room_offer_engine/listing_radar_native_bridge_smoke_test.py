from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for path in [str(REPO_ROOT), str(APP_DIR.parent), str(APP_DIR)]:
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)

bridge = importlib.import_module("listing_radar_native_bridge")
integration = importlib.import_module("listing_radar_integration")
identity = importlib.import_module("team_offer_identity")
stability = importlib.import_module("production_stability")
library = importlib.import_module("deal_library")
one_load = importlib.import_module("ui_sections.one_load_deal_ui")

assert bridge.install() is True
assert integration.SELECTED_KEY in library.PERSISTED_STATE_KEYS
assert integration.MARKET_KEY in library.PERSISTED_STATE_KEYS
assert integration.ANALYSIS_RECORD_KEY in stability._CURRENT_INPUT_KEYS
assert integration.SELECTED_KEY in stability._CURRENT_INPUT_KEYS
for key in integration._FILTER_KEYS:
    assert key in stability._SESSION_PREFERENCE_KEYS


class FakeSt:
    def __init__(self):
        self.session_state = {}

    def rerun(self):
        raise AssertionError("This regression calls the handoff functions directly and should not rerun.")


st = FakeSt()
st.session_state.update(
    {
        identity.ACTIVE_MEMBER_KEY: "Shawn",
        identity.MEMBER_SELECTION_KEY: "Shawn",
        identity.CUSTOM_MEMBER_KEY: "",
        "war_room_active_section": "📡 Listing Radar",
        "listing_radar_query": "Decatur",
        "listing_radar_market": "IL_CENTRAL_TARGET_ZIPS",
        "address": "999 Old Property St",
        "decision_result": {"decision": "BUY"},
        "rent": 999,
    }
)

listing = {
    "listing_key": "zpid:12345678",
    "zpid": "12345678",
    "address": "101 Main St",
    "city": "Decatur",
    "state": "IL",
    "zip": "62521",
    "market_id": "IL_CENTRAL_TARGET_ZIPS",
    "asking_price": 55000,
    "beds": 3,
    "baths": 1,
    "sqft": 1050,
    "lot_size": "6098.4",
    "year_built": 1950,
    "property_type": "Single Family",
    "listing_status": "Active",
    "days_on_market": 4,
    "listing_url": "https://www.zillow.com/homedetails/12345678_zpid/",
    "agent_name": "Test Agent",
    "agent_phone": "2175550101",
    "agent_email": "agent@example.com",
    "agent_brokerage": "Test Brokerage",
    "primary_photo": "https://photos.zillowstatic.com/test.jpg",
}

original_connected = integration.client.is_connected
original_update = integration.client.update_queue
updates = []
integration.client.is_connected = lambda: True
integration.client.update_queue = lambda key, changes: updates.append((key, dict(changes))) or {"ok": True}

assert integration.queue_for_one_load(st, listing) is True
assert integration.PENDING_HANDOFF_KEY in st.session_state
assert st.session_state["war_room_active_section"] == "🏠 One-Load"
assert updates[-1][0] == "zpid:12345678"
assert updates[-1][1]["assigned_to"] == "Shawn"
assert updates[-1][1]["workflow_status"] == "Analyze"

assert integration.apply_pending_handoff(st) is True
assert st.session_state["decision_property_input"] == listing["listing_url"]
assert st.session_state["decision_asking_price"] == 55000
assert st.session_state["one_load_input_method"] == "Listing URL"
assert st.session_state["one_load_contact_name"] == "Test Agent"
assert st.session_state["deal_library_assigned_to"] == "Shawn"
assert st.session_state[integration.SELECTED_KEY] == "zpid:12345678"
assert st.session_state[integration.ANALYSIS_RECORD_KEY]["address"] == "101 Main St"
assert st.session_state.get("address") != "999 Old Property St"
assert not st.session_state.get("decision_result")
assert st.session_state[identity.ACTIVE_MEMBER_KEY] == "Shawn"
assert st.session_state["listing_radar_query"] == "Decatur"
assert st.session_state["listing_radar_market"] == "IL_CENTRAL_TARGET_ZIPS"

captured = {}
original_one_load_run = one_load._run_one_load
original_decision_run = integration._ORIGINAL_DECISION_RUN
original_mark_completed = integration.mark_analysis_completed


def fake_one_load_run(st_arg, ui_arg, csv_record, exit_mode, overwrite_demo_values=True):
    captured["record"] = dict(csv_record or {})
    captured["exit_mode"] = exit_mode
    return {"ok": True}


def fake_decision_run(st_arg, ui_arg, media_files):
    result = one_load._run_one_load(st_arg, ui_arg, None, "Auto", True)
    st_arg.session_state["deal_library_deal_id"] = "deal-123"
    return result

completed = []
one_load._run_one_load = fake_one_load_run
integration._ORIGINAL_DECISION_RUN = fake_decision_run
integration.mark_analysis_completed = lambda st_arg: completed.append(st_arg.session_state.get("deal_library_deal_id")) or {"ok": True}
try:
    result = integration.run_with_listing_radar(st, object(), [])
finally:
    one_load._run_one_load = original_one_load_run
    integration._ORIGINAL_DECISION_RUN = original_decision_run
    integration.mark_analysis_completed = original_mark_completed

assert result == {"ok": True}
assert captured["record"]["zpid"] == "12345678"
assert captured["record"]["listing_agent_email"] == "agent@example.com"
assert completed == ["deal-123"]

integration.get_secret = lambda name, default="": "https://agent-finder.example.app" if name == "AGENT_CONTACT_FINDER_URL" else default
finder = integration.agent_contact_finder_url(listing)
assert finder.startswith("https://agent-finder.example.app?")
assert "agent_name=Test+Agent" in finder
assert "zip=62521" in finder

# Start New Property keeps the teammate and Listing Radar filters, but removes the
# selected source listing and the cached listing facts.
stability.clear_property_state(st.session_state, preserve_current_inputs=False)
assert st.session_state[identity.ACTIVE_MEMBER_KEY] == "Shawn"
assert st.session_state["listing_radar_query"] == "Decatur"
assert st.session_state["listing_radar_market"] == "IL_CENTRAL_TARGET_ZIPS"
assert integration.SELECTED_KEY not in st.session_state
assert integration.ANALYSIS_RECORD_KEY not in st.session_state
assert not st.session_state.get("decision_property_input")

integration.client.is_connected = original_connected
integration.client.update_queue = original_update

print("Listing Radar native War Room integration smoke test passed.")
