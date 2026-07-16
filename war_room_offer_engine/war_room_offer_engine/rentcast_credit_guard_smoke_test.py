from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path


os.environ["RENTCAST_INTELLIGENCE_PREVIEW"] = "1"

APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)

module = importlib.import_module("rentcast_credit_guard")
records = importlib.import_module("rentcast_property_records")
records._RESPONSE_CACHE.clear()


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def get(self, endpoint, **kwargs):
        params = dict(kwargs.get("params", {}) or {})
        self.calls.append((str(endpoint), params))
        return FakeResponse({"endpoint": str(endpoint), "params": params})


class FakeSt:
    def __init__(self, state=None):
        self.session_state = dict(state or {})


# Request estimates distinguish the standard engine, rural preview, addresses,
# and listing URLs. Saved/cache reuse is displayed separately as zero new calls.
address_state = {"decision_property_input": "1263 Allison Gap Rd, Saltville, VA 24370"}
url_state = {"decision_property_input": "https://www.zillow.com/homedetails/example"}
assert module.estimate_request_range(address_state, preview_on=False) == (3, 5)
assert module.estimate_request_range(url_state, preview_on=False) == (2, 4)
assert module.estimate_request_range(address_state, preview_on=True) == (5, 9)
assert module.estimate_request_range(url_state, preview_on=True) == (4, 8)

# The preview path counts only successful uncached calls. A cache hit remains
# available after the hard cap, while a new query is blocked before HTTP.
session = FakeSession()
module._RUN_CONTEXT.update(
    {
        "active": True,
        "limit": 2,
        "successful_requests": 0,
        "cache_hits": 0,
        "blocked_requests": 0,
        "request_log": [],
    }
)

first = module.request_json_budgeted(
    "https://api.rentcast.io/v1/properties", "test-key", {"address": "A"}, session=session
)
assert first["ok"] is True
assert module._RUN_CONTEXT["successful_requests"] == 1
assert len(session.calls) == 1

cached = module.request_json_budgeted(
    "https://api.rentcast.io/v1/properties", "test-key", {"address": "A"}, session=session
)
assert cached["ok"] is True
assert cached["cache_hit"] is True
assert module._RUN_CONTEXT["successful_requests"] == 1
assert module._RUN_CONTEXT["cache_hits"] == 1
assert len(session.calls) == 1

second = module.request_json_budgeted(
    "https://api.rentcast.io/v1/avm/rent/long-term", "test-key", {"address": "A"}, session=session
)
assert second["ok"] is True
assert module._RUN_CONTEXT["successful_requests"] == 2
assert len(session.calls) == 2

blocked = module.request_json_budgeted(
    "https://api.rentcast.io/v1/avm/value", "test-key", {"address": "A"}, session=session
)
assert blocked["ok"] is False
assert blocked["request_budget_blocked"] is True
assert module._RUN_CONTEXT["blocked_requests"] == 1
assert len(session.calls) == 2
module._RUN_CONTEXT["active"] = False

# Forced refresh requires an explicit second confirmation.
force_state = {
    "decision_property_input": "1263 Allison Gap Rd, Saltville, VA 24370",
    "deal_library_force_refresh": True,
    module.CONFIRM_KEY: False,
}
force_st = FakeSt(force_state)
disabled, reason = module._button_should_be_disabled(force_st)
assert disabled is True
assert "Confirm" in reason
force_st.session_state[module.CONFIRM_KEY] = True
disabled, _ = module._button_should_be_disabled(force_st)
assert disabled is False

# A same-session result younger than six hours blocks accidental duplicate pulls.
now = time.time()
recent_state = {
    "decision_property_input": "1263 Allison Gap Rd, Saltville, VA 24370",
    module.LAST_PROPERTY_KEY: "1263 Allison Gap Rd, Saltville, VA 24370",
    module.LAST_PULL_EPOCH_KEY: now - 120,
    "one_load_normalized": {"data": {"rent": 1000}},
    "deal_library_force_refresh": False,
}
assert module.duplicate_analysis_is_fresh(recent_state, now=now) is True
recent_st = FakeSt(recent_state)
disabled, reason = module._button_should_be_disabled(recent_st)
assert disabled is True
assert "already loaded" in reason

changed = dict(recent_state, decision_property_input="1115 Matson Dr, Marion, VA 24354")
assert module.duplicate_analysis_is_fresh(changed, now=now) is False

print("RentCast request estimate, successful-call count, cache reuse, hard cap, refresh confirmation and duplicate-pull guard tests passed.")
