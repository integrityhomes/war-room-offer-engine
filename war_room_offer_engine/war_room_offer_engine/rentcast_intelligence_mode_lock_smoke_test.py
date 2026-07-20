from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


preview = importlib.import_module("rentcast_intelligence_preview")
comps_fix = importlib.import_module("rentcast_intelligence_comps_ui_fix")
rent_fix = importlib.import_module("rentcast_intelligence_rent_ui_fix")
mode = importlib.import_module("rentcast_intelligence_mode_lock")
library = importlib.import_module("deal_library")
mode.install()


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self, state=None):
        self.session_state = FakeState(state or {})
        self.query_params = {}
        self.checkboxes = []
        self.messages = []

    def checkbox(self, label, **kwargs):
        self.checkboxes.append((label, kwargs))
        return bool(self.session_state.get(kwargs.get("key"), False))

    def info(self, message):
        self.messages.append(("info", str(message)))

    def warning(self, message):
        self.messages.append(("warning", str(message)))

    def caption(self, message):
        self.messages.append(("caption", str(message)))


# Accuracy-first default: a new team session starts with verified intelligence on.
clean = FakeSt()
mode.render_verified_intelligence_control(clean)
assert clean.session_state[preview.PREVIEW_STATE_KEY] is True
assert clean.checkboxes[-1][0] == "Use verified RentCast intelligence (recommended)"
assert clean.checkboxes[-1][1].get("disabled") is False


# A loaded recorded-sale result remains tied to verified mode even when the old
# checkbox value is false. This prevents the legacy comps screen and baseline
# decision rules from interpreting the evidence.
recorded_state = {
    preview.PREVIEW_STATE_KEY: False,
    "auto_arv_summary": {
        "comp_data_type": "RentCast public-record closed sales",
        "recommended_arv": 48000,
    },
    "auto_sold_comps": [
        {
            "record_type": "recorded_sale",
            "source": "RentCast Recorded Sale",
            "comp_address": "405 W Main St, Saltville, VA 24370",
        }
    ],
    "one_load_normalized": {
        "data": {
            "rent_search_trail": [{"source": "RentCast rental listings"}],
            "rentcast_data_provenance": {"arv": "RentCast Recorded Sales"},
        }
    },
}
loaded = FakeSt(recorded_state)
assert mode.result_uses_verified_intelligence(loaded.session_state) is True
assert mode.verified_intelligence_enabled(loaded) is True
assert comps_fix._recorded_preview_active(loaded) is True
mode.render_verified_intelligence_control(loaded)
assert loaded.session_state[preview.PREVIEW_STATE_KEY] is True
assert loaded.checkboxes[-1][1].get("disabled") is True
assert loaded.session_state[mode.MODE_KEY] == mode.MODE_VERIFIED


# The rural-rent panel also remains active from positive result evidence rather
# than depending on the current checkbox.
rent_data = {
    "verified_rent_comp_count": 6,
    "rent_search_trail": [{"source": "RentCast rental listings"}],
    "rent_comp_quality_summary": {"strong": 1, "good": 5, "excluded": 108},
    "rent_comps": [
        {
            "record_type": "rental_listing",
            "source": "RentCast Rental Listing",
            "rent": 1075,
            "include_default": True,
        }
    ],
}
loaded.session_state.update(rent_data)
assert rent_fix._rural_preview_active(loaded, rent_data) is True


# Every verified result carries a durable marker for Team Deal Library restores.
marked = preview._result_with_preview_marker({"rent": 1075})
assert marked[preview.PREVIEW_ACTIVE_KEY] is True
assert marked[mode.MODE_KEY] == mode.MODE_VERIFIED
assert preview.PREVIEW_ACTIVE_KEY in library.PERSISTED_STATE_KEYS
assert mode.MODE_KEY in library.PERSISTED_STATE_KEYS

print("Verified intelligence mode lock and evidence routing smoke test passed.")
