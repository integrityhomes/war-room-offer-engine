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


# Regression: a restart can restore the historical $900 default together with
# empty or generic quality keys. None of those keys is positive RentCast value
# provenance, so the default must not enter the RentCast display model.
placeholder = FakeSt(
    {
        "rent": 900,
        "rent_source": "Missing / RentCast unavailable",
        "rent_confidence": "Weak",
        "rent_verification_needed": "Yes",
        "verified_rent_comp_count": 0,
        "rent_search_mode": "",
        "rent_search_trail": [],
        "rent_requires_human_verification": True,
        "rent_comp_quality_summary": {
            "strong": 0,
            "good": 0,
            "weak": 0,
            "excluded": 0,
        },
    }
)
placeholder_data = module._normalized_data(placeholder)
assert placeholder_data.get("rent", 0) == 0
assert module._data_has_rentcast_evidence(placeholder, placeholder_data, []) is False


# A stale label created by an earlier buggy render is also insufficient without
# an address, explicit AVM field, search trail, or comparable rows.
stale_label = FakeSt(
    {
        "rent": 900,
        "rent_source": "RentCast AVM only",
        "rentcast_submitted_address": "",
        "rentcast_rent_avm": 0,
        "rent_search_trail": [],
        "rent_comps": [],
    }
)
stale_data = module._normalized_data(stale_label)
assert stale_data.get("rent", 0) == 0
assert module._data_has_rentcast_evidence(stale_label, stale_data, []) is False


# A failed lookup may retain its submitted address and error, but that context
# must not attach the default $900 to RentCast.
failed_lookup = FakeSt(
    {
        "rent": 900,
        "rent_source": "Missing / RentCast unavailable",
        "rentcast_submitted_address": "1263 Allison Gap Rd",
        "rentcast_rent_error": "RentCast HTTP 402: request limit reached",
        "rent_comps": [],
    }
)
failed_data = module._normalized_data(failed_lookup)
assert failed_data.get("rent", 0) == 0
assert module._data_has_rentcast_evidence(failed_lookup, failed_data, []) is False
assert module._rentcast_context_present(failed_data) is True


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


# A real RentCast AVM-only result may be shown, but it must have positive
# provenance and remain weak when no comparable rentals were returned.
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


# The explicit RentCast AVM field is sufficient provenance even when the source
# label is absent.
explicit_avm = FakeSt(
    {
        "rent": 1075,
        "rentcast_rent_avm": 1075,
        "rent_source": "",
    }
)
explicit_data = module._normalized_data(explicit_avm)
assert explicit_data["rent"] == 1075
assert module._data_has_rentcast_evidence(explicit_avm, explicit_data, []) is True


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

print("Rent fallback provenance, restart, and AVM-only smoke test passed.")
