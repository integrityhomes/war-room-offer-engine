from __future__ import annotations

import deal_library_preflight as preflight


class RerunSignal(Exception):
    pass


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self, property_input: str):
        self.session_state = FakeState(
            {
                "decision_property_input": property_input,
                "deal_library_force_refresh": False,
            }
        )

    def rerun(self):
        raise RerunSignal()


snapshot = {
    "deal_id": "saved-123",
    "address": "1115 Matson Dr, Marion, VA 24354",
    "session_state": {"address": "1115 Matson Dr, Marion, VA 24354", "rent": 1040},
}

preflight.is_connected = lambda: True
preflight.stable_deal_id = lambda state: "saved-123"
preflight.get_deal = lambda deal_id: {"ok": True, "snapshot": snapshot}

st = FakeSt("1115 Matson Dr, Marion, VA 24354")
try:
    preflight.open_saved_before_paid_pull(st)
    raise AssertionError("Expected Streamlit rerun after a saved deal was found.")
except RerunSignal:
    pass

assert st.session_state["deal_library_pending_snapshot"]["deal_id"] == "saved-123"
assert "No property-data credits" in st.session_state["deal_library_last_message"]

forced = FakeSt("1115 Matson Dr, Marion, VA 24354")
forced.session_state["deal_library_force_refresh"] = True
assert preflight.open_saved_before_paid_pull(forced) is False
assert "deal_library_pending_snapshot" not in forced.session_state

# URL/search fallback: direct ID does not match because the saved ID was based on
# the normalized property address. The sheet search finds the one matching deal.
responses = {"wrong-direct": {"ok": False}, "saved-456": {"ok": True, "snapshot": snapshot}}
preflight.stable_deal_id = lambda state: "wrong-direct"
preflight.get_deal = lambda deal_id: responses.get(deal_id, {"ok": False})
preflight.search_deals = lambda query, limit=10: {
    "ok": True,
    "deals": [
        {
            "deal_id": "saved-456",
            "address": "1115 Matson Dr, Marion, VA 24354",
            "listing_url": "https://www.zillow.com/homedetails/example",
        }
    ],
}

url_st = FakeSt("https://www.zillow.com/homedetails/example")
try:
    preflight.open_saved_before_paid_pull(url_st)
    raise AssertionError("Expected Streamlit rerun after URL fallback found a saved deal.")
except RerunSignal:
    pass
assert url_st.session_state["deal_library_pending_snapshot"]["deal_id"] == "saved-123"

print("Deal Library paid-data preflight smoke test passed.")
