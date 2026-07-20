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


# Streamlit's legacy $900 demo/default must never be presented as verified
# RentCast data after a restart when no API provenance or comparables exist.
restarted = FakeSt(
    {
        "rent": 900,
        "rent_source": "Missing / RentCast unavailable",
        "rentcast_rent_comps": [],
        "rent_comps": [],
        "one_load_normalized": {},
    }
)
restarted_data = module._normalized_data(restarted)
assert restarted_data.get("rent", 0) == 0
assert restarted_data.get("rent_estimate", 0) == 0
assert module._rentcast_evidence_present(restarted_data, []) is False


# A genuine RentCast AVM may survive without comparables, but it remains
# AVM-only evidence and must require verification.
avm_only = FakeSt(
    {
        "rent": 1075,
        "rent_source": "RentCast AVM only",
        "rentcast_submitted_address": "1263 Allison Gap Rd",
        "rentcast_rent_comps": [],
    }
)
avm_data = module._normalized_data(avm_only)
assert avm_data["rent"] == 1075
assert module._rentcast_evidence_present(avm_data, []) is True
module._apply_rentcast_state(avm_only, avm_data, [])
assert avm_only.session_state["rent_confidence"] == "AVM only"
assert avm_only.session_state["rent_verification_needed"] == "Yes"
assert avm_only.session_state["rent_comp_count"] == 0


# One or two comparable rentals are fallback evidence, not fully verified.
one_comp = [{"address": "Nearby", "rent": 1000}]
module._apply_rentcast_state(avm_only, {**avm_data, "rent_comps": one_comp}, one_comp)
assert avm_only.session_state["rent_confidence"] == "Medium fallback comps"
assert avm_only.session_state["rent_verification_needed"] == "Yes"


# Three direct comparable rentals retain the existing verified behavior.
three_comps = [
    {"address": f"Nearby {index}", "rent": 1000 + index * 25}
    for index in range(3)
]
module._apply_rentcast_state(avm_only, {**avm_data, "rent_comps": three_comps}, three_comps)
assert avm_only.session_state["rent_confidence"] == "Strong verified rent comps"
assert avm_only.session_state["rent_verification_needed"] == "No"
assert avm_only.session_state["rent_comp_count"] == 3


# Manual or seller-stated rent must not be relabeled as RentCast merely because
# it is a positive number in session state.
manual = FakeSt(
    {
        "rent": 950,
        "rent_source": "Seller-stated rent",
        "rentcast_rent_comps": [],
        "one_load_normalized": {"data": {"rent": 950, "rent_source": "Seller-stated rent"}},
    }
)
manual_data = module._normalized_data(manual)
assert manual_data["rent"] == 950
assert module._rentcast_evidence_present(manual_data, []) is False

print("Restart default rent provenance smoke test passed.")
