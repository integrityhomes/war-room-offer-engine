from __future__ import annotations

import importlib
import os
import sys
from datetime import date, timedelta
from pathlib import Path


os.environ["RENTCAST_INTELLIGENCE_PREVIEW"] = "1"

APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)

module = importlib.import_module("rentcast_intelligence_comps_ui_fix")


def iso(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


subject = {
    "address": "1263 Allison Gap Rd, Saltville, VA 24370",
    "city": "Saltville",
    "state": "VA",
    "zip": "24370",
    "county": "Smyth",
    "property_type": "Single Family",
    "beds": 2,
    "baths": 1,
    "sqft": 1170,
}

stage = {
    "name": "Expanded",
    "radius": 3.0,
    "days": 730,
    "sqft_tolerance": 0.35,
}

four_bed = module.score_recorded_sale_ui_hardened(
    {
        "record_type": "recorded_sale",
        "source": "RentCast Recorded Sale",
        "comp_address": "924 W Main St, Saltville, VA 24370",
        "sold_price": 15000,
        "sold_date": iso(100),
        "property_type": "Single Family",
        "beds": 4,
        "baths": 1,
        "square_feet": 1193,
        "distance_miles": 2.7,
        "zip": "24370",
        "county": "Smyth",
        "price_per_sqft": 15000 / 1193,
    },
    subject,
    stage,
)
assert "bedroom count differs materially" in four_bed["flags"]
assert four_bed["score"] != "Strong Comp"

small_comp = module.score_recorded_sale_ui_hardened(
    {
        "record_type": "recorded_sale",
        "source": "RentCast Recorded Sale",
        "comp_address": "861 Allison Gap Rd, Saltville, VA 24370",
        "sold_price": 15600,
        "sold_date": iso(120),
        "property_type": "Single Family",
        "beds": 2,
        "baths": 1,
        "square_feet": 806,
        "distance_miles": 0.68,
        "zip": "24370",
        "county": "Smyth",
        "price_per_sqft": 15600 / 806,
    },
    subject,
    stage,
)
assert "square footage differs materially" in small_comp["flags"]
assert small_comp["score"] != "Strong Comp"


class FakeSt:
    def __init__(self):
        self.session_state = {
            **subject,
            "auto_arv_summary": {
                "search_mode": "Expanded",
                "search_radius": "3 miles",
                "search_days": 730,
                "candidate_comp_count": 6,
                "comp_data_type": "RentCast public-record closed sales",
                "search_trail": [{"radius": 10, "returned": 25}],
            },
        }


rows = []
for index, (price, sqft, score, include) in enumerate(
    [
        (15600, 806, "Good Comp", True),
        (29900, 1479, "Good Comp", True),
        (14250, 1326, "Strong Comp", True),
        (15000, 1193, "Good Comp", True),
        (15000, 840, "Good Comp", True),
        (27500, 1055, "Strong Comp", False),
    ]
):
    rows.append(
        {
            "id": f"sale-{index}",
            "assessor_id": f"parcel-{index}",
            "record_type": "recorded_sale",
            "source": "RentCast Recorded Sale",
            "comp_address": f"{index + 1} Test Rd, Saltville, VA 24370",
            "sold_price": price,
            "sold_date": iso(100 + index * 10),
            "property_type": "Single Family",
            "beds": 2,
            "baths": 1,
            "square_feet": sqft,
            "distance_miles": 0.5 + index * 0.3,
            "price_per_sqft": price / sqft,
            "sale_age_days": 100 + index * 10,
            "score": score,
            "score_points": 90 if score == "Strong Comp" else 80,
            "flags": [],
            "include_default": include,
        }
    )

fake_st = FakeSt()
display, summary = module._selection_summary(fake_st, rows, set(range(6)))
assert summary["verified_sold_comp_count"] == 5
assert summary["arv_confidence"] != "Strong"
assert summary["arv_requires_human_verification"] is True
assert summary["condition_evidence"] == "Unverified"
assert "quality public-record sales" in summary["explanation"]
assert sum(bool(row.get("include_default")) for row in display) == 5

# Removing three selected comps must weaken the result rather than silently
# keeping the prior strong-looking ARV.
_, reduced = module._selection_summary(fake_st, rows, {0, 1})
assert reduced["verified_sold_comp_count"] == 2
assert reduced["arv_requires_human_verification"] is True
assert any("fewer than three" in reason.lower() for reason in reduced["verification_reasons"])

from ui_sections import comps_ui

assert comps_ui.render_automatic_sold_comps_section is module.render_automatic_sold_comps_section
print("Recorded-sale Comps / ARV UI safety regression test passed.")
