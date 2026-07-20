from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


safe = importlib.import_module("one_load_sources_safe")


calls: list[tuple[str, float, float, float]] = []
captured: dict = {}


def fake_lookup(address: str, beds: float = 0, baths: float = 0, sqft: float = 0):
    calls.append((address, beds, baths, sqft))
    return {
        "source": "RentCast",
        "found": True,
        "address": "404 4th St",
        "city": "Montgomery",
        "state": "AL",
        "zip": "36110",
        "requested_property_address": address,
        "resolved_property_address": "404 4th St, Montgomery, AL 36110",
        "location_verification_status": "Matched requested street/city/state/ZIP",
        "location_verification_failed": False,
        "rentcast_submitted_address": address,
        "rent": 975,
        "rent_estimate": 975,
        "rent_source": "RentCast Rental Comps",
        "rent_confidence": "Strong verified rent comps",
        "rent_verification_needed": "No",
        "rent_comps": [
            {"address": "Rent 1", "rent": 950},
            {"address": "Rent 2", "rent": 975},
            {"address": "Rent 3", "rent": 1000},
        ],
        "rent_comp_count": 3,
        "verified_rent_comp_count": 3,
        "arv": 62000,
        "arv_source": "RentCast Recorded Sales",
        "arv_confidence": "Medium",
        "auto_sold_comps": [
            {"comp_address": "Sale 1", "sold_price": 60000},
            {"comp_address": "Sale 2", "sold_price": 62000},
            {"comp_address": "Sale 3", "sold_price": 64000},
        ],
        "auto_arv_summary": {
            "recommended_arv": 62000,
            "comp_data_type": "RentCast public-record closed sales",
        },
    }


def fake_original(payload):
    captured["payload"] = payload
    return {
        "data": {
            "address": payload.get("property_address", ""),
            "asking_price": payload.get("asking_price", 0),
        },
        "data_sources_used": ["Zillow"],
        "errors": [],
        "arv_source": "Missing",
        "arv_confidence": "Not enough data",
        "rent_confidence": "Weak",
    }


safe.ds.lookup_rentcast = fake_lookup
safe._original_normalize_one_load_lead = fake_original
safe.preview_control.preview_enabled = lambda *args, **kwargs: True

payload = {
    "input_method": "Property address",
    "property_address": "404 4th St, Montgomery, AL 36110",
    "listing_url": "",
    "record": {},
    "asking_price": 29900,
}
summary = safe.normalize_one_load_lead(payload)

assert calls == [("404 4th St, Montgomery, AL 36110", 0, 0, 0)]
assert captured["payload"]["record"]["rent"] == 975
assert summary["rentcast_pull_attempted"] is True
assert summary["rentcast_pull_status"] == "Complete"
assert "RentCast verified intelligence" in summary["data_sources_used"]
assert summary["data"]["rent"] == 975
assert summary["data"]["rent_comp_count"] == 3
assert summary["data"]["verified_rent_comp_count"] == 3
assert summary["data"]["arv"] == 62000
assert summary["data"]["requested_property_address"] == "404 4th St, Montgomery, AL 36110"
assert summary["data"]["resolved_property_address"] == "404 4th St, Montgomery, AL 36110"

# Listing URLs already have their own enrichment path and must not trigger a
# second address lookup from this wrapper.
calls.clear()
safe.normalize_one_load_lead(
    {
        "input_method": "Listing URL",
        "property_address": "",
        "listing_url": "https://www.zillow.com/homedetails/example",
        "record": {"rent": 1200},
    }
)
assert calls == []

# An incomplete street-only value is blocked before any paid data call.
calls.clear()
safe.normalize_one_load_lead(
    {
        "input_method": "Property address",
        "property_address": "404 4th St",
        "listing_url": "",
        "record": {},
    }
)
assert calls == []

print("One-Load plain-address RentCast pull smoke test passed.")
