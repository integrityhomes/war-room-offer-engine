from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


os.environ["RENTCAST_INTELLIGENCE_PREVIEW"] = "1"

APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)

module = importlib.import_module("rentcast_intelligence_rent_ui_fix")


subject = {
    "address": "1263 Allison Gap Rd, Saltville, VA 24370",
    "property_type": "Single Family",
    "beds": 2,
    "baths": 1,
    "sqft": 1170,
    "latitude": 36.88,
    "longitude": -81.76,
}

# A 49-mile advertised rental may be useful context, but it must not count as
# quality-verified current rent support for a binding slow-flip decision.
far = module.score_rent_comp_ui_hardened(
    {
        "id": "far-active",
        "address": "1301 Cobblestone Ct, Johnson City, TN 37601",
        "property_type": "Single Family",
        "beds": 2,
        "baths": 1,
        "sqft": 1056,
        "rent": 1700,
        "distance": 49.54,
        "status": "Active",
        "listed_date": "2026-06-01",
        "last_seen_date": "2026-07-10",
        "days_old": 45,
        "source": "RentCast Rental Listing",
        "record_type": "rental_listing",
    },
    subject,
)
assert far["score"] == "Weak Comp"
assert "too distant to count as verified rental support" in far["flags"]

# Expanded evidence between 10 and 25 miles can be Good, but never Strong.
expanded = module.score_rent_comp_ui_hardened(
    {
        "id": "expanded-active",
        "address": "225 Ruth St SW, Abingdon, VA 24210",
        "property_type": "Single Family",
        "beds": 2,
        "baths": 1,
        "sqft": 933,
        "rent": 1200,
        "distance": 16.13,
        "status": "Active",
        "listed_date": "2026-06-01",
        "last_seen_date": "2026-07-10",
        "days_old": 45,
        "source": "RentCast Rental Listing",
        "record_type": "rental_listing",
    },
    subject,
)
assert expanded["score"] in {"Good Comp", "Weak Comp"}
assert expanded["score"] != "Strong Comp"
assert "expanded rural rental evidence" in expanded["flags"]

# Inactive history remains useful context but cannot be called verified current rent.
inactive = module.score_rent_comp_ui_hardened(
    {
        "id": "inactive-near",
        "address": "100 Main St, Saltville, VA 24370",
        "property_type": "Single Family",
        "beds": 2,
        "baths": 1,
        "sqft": 1150,
        "rent": 1050,
        "distance": 2.0,
        "status": "Inactive",
        "listed_date": "2025-09-01",
        "removed_date": "2025-10-01",
        "days_old": 300,
        "source": "RentCast Rental Listing",
        "record_type": "rental_listing",
    },
    subject,
)
assert inactive["score"] == "Weak Comp"
assert "inactive listing cannot count as verified current rent" in inactive["flags"]


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self):
        self.session_state = FakeState()


fake = FakeSt()
rows = []
for index in range(25):
    rows.append(
        {
            "id": f"rent-{index}",
            "address": f"{100 + index} Rural Rd, Southwest VA",
            "property_type": "Single Family",
            "beds": 2,
            "baths": 1,
            "sqft": 1000 + index,
            "rent": 900 + index * 25,
            "distance": 7.0 + index,
            "status": "Active",
            "listed_date": "2026-06-01",
            "last_seen_date": "2026-07-10",
            "days_old": 45,
            "score": "Good Comp" if index < 2 else "Weak Comp",
            "score_points": 80 if index < 2 else 65,
            "include_default": index < 6,
            "flags": [] if index < 2 else ["weak rural fallback"],
            "source": "RentCast Rental Listing",
            "record_type": "rental_listing",
        }
    )

fake.session_state.update(
    {
        "rent": 1275,
        "rent_estimate": 1275,
        "rentcast_rent_avm": 1275,
        "rent_source": "RentCast Rural Rental Fallback",
        "rent_confidence": "Weak rural fallback comps",
        "rent_verification_needed": "Yes",
        "rent_comps": rows,
        "rent_comp_count": 6,
        "verified_rent_comp_count": 2,
        "rent_comp_average": 1088,
        "rent_comp_median": 1050,
        "rent_low": 975,
        "rent_high": 1175,
        "rent_search_mode": "Deep rural",
        "rent_search_radius": 49.54,
        "rent_search_days": 300,
        "rent_requires_human_verification": True,
        "rent_verification_reasons": [
            "Fewer than three strong/good rental listings had verified distance and listing age.",
            "Rental evidence expanded as far as 49.5 miles.",
        ],
        "rent_comp_quality_summary": {
            "strong": 0,
            "good": 2,
            "weak": 4,
            "excluded": 19,
            "avm_comp_disagreement_pct": 21.0,
        },
        "rentcast_submitted_address": "1263 Allison Gap Rd",
    }
)

model = module.build_rent_display_model(fake)
assert model["total_listing_count"] == 25
assert model["used_comp_count"] == 6
assert model["verified_comp_count"] == 2
assert model["recommended_rent"] == 1275
assert model["comp_average"] == 1088
assert model["comp_median"] == 1050
assert model["confidence"] == "Weak rural fallback comps"
assert model["requires_human_verification"] is True

module._store_intelligent_rent_state(fake, model)
assert fake.session_state["rentcast_total_listing_count"] == 25
assert fake.session_state["rent_comp_count"] == 6
assert fake.session_state["rentcast_comp_count"] == 6
assert fake.session_state["rentcast_rent_comp_count"] == 6
assert fake.session_state["verified_rent_comp_count"] == 2
assert fake.session_state["rent_verification_needed"] == "Yes"
assert fake.session_state["rent_confidence"] == "Weak rural fallback comps"
assert fake.session_state["rental_demand_confidence"] == "Weak rent comps"

# Turning preview off returns the existing production display path.
os.environ.pop("RENTCAST_INTELLIGENCE_PREVIEW", None)
assert module._rural_preview_active(fake) is False

print("Saltville rural rent count, distance, confidence and UI-state regression test passed.")
