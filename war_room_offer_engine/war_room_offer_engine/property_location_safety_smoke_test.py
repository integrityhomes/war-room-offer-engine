from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


guard = importlib.import_module("property_location_guard")
safety = importlib.import_module("property_location_safety")


# Street-only inputs are ambiguous and must be stopped before a paid request.
complete, message = guard.validate_property_input("404 4th St")
assert complete is False
assert "street, city, state" in message.lower()

# Full city/state or a ZIP is sufficient to identify the requested geography.
for address in [
    "404 4th St, Montgomery, AL",
    "404 4th St, Montgomery, AL 36104",
    "1263 Allison Gap Rd, Saltville, VA 24370",
    "5500 Grand Lake Dr, San Antonio, TX 78244",
    "404 4th St 36104",
]:
    assert guard.validate_property_input(address)[0] is True, address

assert guard.validate_property_input("https://www.zillow.com/homedetails/example")[0] is True

parsed = guard.parse_property_input("404 4th St, Montgomery, AL 36104")
assert parsed["city"] == "Montgomery"
assert parsed["state"] == "AL"
assert parsed["zip"] == "36104"

# The live failure resolved a Montgomery, Alabama street-only input to Idaho.
# A full Montgomery address must reject that subject before rent/ARV searches.
valid, mismatch = guard.validate_resolved_location(
    "404 4th St, Montgomery, AL 36104",
    {
        "formatted_address": "404 4th St, Saint Maries, ID 83861",
        "address": "404 4th St",
        "city": "Saint Maries",
        "state": "ID",
        "zip": "83861",
    },
)
assert valid is False
assert "different location" in mismatch.lower()
assert "id instead of al" in mismatch.lower()

valid, mismatch = guard.validate_resolved_location(
    "404 4th St, Montgomery, AL 36104",
    {
        "formatted_address": "404 4th St, Montgomery, AL 36104",
        "address": "404 4th St",
        "city": "Montgomery",
        "state": "AL",
        "zip": "36104",
    },
)
assert valid is True
assert mismatch == ""

# Incomplete input must return a safe empty result without invoking enrichment.
called = {"count": 0}
original_enrich = safety._ORIGINAL_ENRICH


def should_not_run(*args, **kwargs):
    called["count"] += 1
    raise AssertionError("paid enrichment should not run for an incomplete address")


safety._ORIGINAL_ENRICH = should_not_run
try:
    empty = safety._safe_enrich({"address": "404 4th St"}, "test-key")
finally:
    safety._ORIGINAL_ENRICH = original_enrich

assert called["count"] == 0
assert empty["location_verification_failed"] is True
assert empty["rent"] == 0
assert empty["arv"] == 0
assert empty["rent_comps"] == []
assert empty["auto_sold_comps"] == []

# Search labels describe distance expansion, not whether the municipality is rural.
assert [stage["name"] for stage in safety._NEUTRAL_SOLD_STAGES] == [
    "Local", "Expanded", "Wide area", "Extended area", "Remote area"
]
assert safety._neutral_search_mode(20.0, 0, True) == "Wide area"
assert safety._neutral_search_mode(35.0, 0, True) == "Remote area"

invalid = guard.invalid_location_result("404 4th St", "Ambiguous location")
assert invalid["verified_sold_comp_count"] == 0
assert invalid["verified_rent_comp_count"] == 0
assert invalid["arv_requires_human_verification"] is True
assert invalid["rent_requires_human_verification"] is True

print("Property location safety smoke test passed.")
