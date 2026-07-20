from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


rent_ui = importlib.import_module("rentcast_intelligence_rent_ui_fix")
module = importlib.import_module("rentcast_intelligence_rent_reconciliation")
module.install()


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self, state=None):
        self.session_state = FakeState(state or {})


def row(index: int, rent: int, distance: float, score: str, include: bool, *, days_old: int = 0):
    return {
        "id": f"rent-{index}",
        "address": f"{100 + index} Rural Rd, Saltville, VA 24370",
        "beds": 2,
        "baths": 1,
        "sqft": 1000,
        "rent": rent,
        "distance": distance,
        "status": "Active",
        "days_old": days_old,
        "score": score,
        "score_points": 92 if score == "Strong Comp" else 80 if score == "Good Comp" else 60,
        "include_default": include,
        "source": "RentCast Rental Listing",
    }


# Reproduce the live Saltville screen: 25 displayed rows, only six engine-selected,
# stale legacy state claiming all 25 were used, and an underlying 114-row candidate set.
selected = [
    row(0, 900, 7.29, "Strong Comp", True),
    row(1, 1200, 16.13, "Good Comp", True),
    row(2, 1600, 19.19, "Good Comp", True),
    row(3, 1200, 19.22, "Good Comp", True),
    row(4, 950, 20.04, "Good Comp", True),
    row(5, 950, 20.05, "Good Comp", True),
]
rows = selected + [row(index, 1400, 30 + index, "Weak Comp", False) for index in range(6, 25)]
state = {
    "rent": 1075,
    "rent_estimate": 1075,
    "rentcast_rent_avm": 0,
    "rent_comps": rows,
    "rent_comp_count": 25,
    "verified_rent_comp_count": 6,
    "rent_comp_average": 1394,
    "rent_comp_median": 1425,
    "rent_low": 950,
    "rent_high": 1200,
    "rent_confidence": "Strong verified rent comps",
    "rent_requires_human_verification": False,
    "rent_verification_reasons": [],
    "rent_search_mode": "Rural",
    "rent_search_radius": 20.1,
    "rent_search_days": 0,
    "rent_comp_quality_summary": {
        "strong": 1,
        "good": 5,
        "weak": 0,
        "excluded": 108,
    },
}
fake = FakeSt(state)
model = module.build_rent_display_model_reconciled(fake, dict(state))

assert model["total_listing_count"] == 114
assert model["used_comp_count"] == 6
assert model["verified_comp_count"] == 6
assert model["comp_median"] == 1075
assert model["comp_average"] < 1200
assert model["recommended_rent"] == 1075
assert model["search_radius"] == 20.05
assert model["search_mode"] == "Rural"
assert model["requires_human_verification"] is True
assert model["confidence"] == "Weak rural fallback comps"
assert any("no verifiable listing age" in reason for reason in model["verification_reasons"])
assert model["quality_summary"]["excluded"] == 108

rent_ui._store_intelligent_rent_state(fake, model)
assert fake.session_state["rent_comp_count"] == 6
assert fake.session_state["rentcast_rent_comp_count"] == 6
assert fake.session_state["rent_verification_needed"] == "Yes"
assert fake.session_state["rental_demand_confidence"] == "Weak rent comps"


# A true local, recent, five-comp set may retain Strong confidence.
local_rows = [
    row(index, 1000 + index * 25, 2 + index, "Strong Comp" if index < 2 else "Good Comp", True, days_old=30 + index)
    for index in range(5)
]
local_state = {
    "rent": 1050,
    "rentcast_rent_avm": 1040,
    "rent_comps": local_rows,
    "rent_comp_quality_summary": {"strong": 2, "good": 3, "weak": 0, "excluded": 0},
    "rent_verification_reasons": [],
    "rent_requires_human_verification": False,
}
local = module.build_rent_display_model_reconciled(FakeSt(local_state), dict(local_state))
assert local["total_listing_count"] == 5
assert local["used_comp_count"] == 5
assert local["verified_comp_count"] == 5
assert local["confidence"] == "Strong verified rent comps"
assert local["requires_human_verification"] is False
assert local["search_mode"] == "Expanded"

print("Rural rent evidence reconciliation smoke test passed.")
