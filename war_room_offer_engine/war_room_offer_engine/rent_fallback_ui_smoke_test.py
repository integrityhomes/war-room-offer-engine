from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


module = importlib.import_module("ui_sections.rent_fallback_ui")


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self, state=None):
        self.session_state = FakeState(state or {})


# Regression: the application's historical $900 demo/default value must not be
# presented as a RentCast verification after a Streamlit redeploy.
placeholder = FakeSt(
    {
        "rent": 900,
        "rent_source": "Missing / RentCast unavailable",
        "rent_confidence": "Weak",
        "rent_verification_needed": "Yes",
    }
)
placeholder_data = module._normalized_data(placeholder)
assert placeholder_data.get("rent", 0) == 0
assert module._data_has_rentcast_evidence(placeholder, placeholder_data, []) is False


# A Zillow/listing rent may remain in the normalized record, but it must not be
# mislabeled as RentCast without RentCast provenance.
listing = FakeSt(
    {
        "rent": 1200,
        "rent_source": "Zillow rental estimate",
        "one_load_normalized": {"data": {"rent": 1200, "rent_source": "Zillow rental estimate"}},
    }
)
listing_data = module._normalized_data(listing)
assert listing_data["rent"] == 1200
assert module._data_has_rentcast_evidence(listing, listing_data, []) is False


# A real RentCast AVM-only result may be shown, but it must remain weak and
# require verification when no comparable rentals were returned.
avm_only = FakeSt(
    {
        "rent": 900,
        "rent_source": "RentCast",
        "rentcast_submitted_address": "1263 Allison Gap Rd",
    }
)
avm_data = module._normalized_data(avm_only)
assert module._data_has_rentcast_evidence(avm_only, avm_data, []) is True
module._apply_rentcast_state(avm_only, avm_data, [])
assert avm_only.session_state["rent_source"] == "RentCast AVM only"
assert avm_only.session_state["rent_confidence"] == "Weak / AVM only"
assert avm_only.session_state["rent_verification_needed"] == "Yes"


# Three genuine comparable rows may still earn the existing strong label.
comps = [
    {"address": "1 Main St", "rent": 900},
    {"address": "2 Main St", "rent": 950},
    {"address": "3 Main St", "rent": 1000},
]
verified = FakeSt(
    {
        "rent": 950,
        "rent_source": "RentCast Rental Comps",
        "rentcast_submitted_address": "100 Main St",
        "rentcast_rent_comps": comps,
    }
)
verified_data = module._normalized_data(verified)
module._apply_rentcast_state(verified, verified_data, comps)
assert verified.session_state["rent_source"] == "RentCast Rental Comps"
assert verified.session_state["rent_confidence"] == "Strong verified rent comps"
assert verified.session_state["rent_verification_needed"] == "No"

print("Rent fallback placeholder and AVM-only verification smoke test passed.")
