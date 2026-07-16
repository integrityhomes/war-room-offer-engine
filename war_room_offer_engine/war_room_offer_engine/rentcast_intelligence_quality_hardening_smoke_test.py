from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


module = importlib.import_module("rentcast_intelligence_quality_hardening")
core = importlib.import_module("rentcast_intelligence_core")


# A partial top-level transaction must never borrow an unrelated date from history.
mismatched = {
    "lastSalePrice": 300000,
    "history": {
        "2019-05-10": {
            "event": "Sale",
            "date": "2019-05-10T00:00:00.000Z",
            "price": 150000,
        }
    },
}
assert module.sale_from_record_paired(mismatched) == (150000.0, "2019-05-10")
assert core._sale_from_record(mismatched) == (150000.0, "2019-05-10")

matched = {
    "lastSalePrice": 300000,
    "history": {
        "2024-06-15": {
            "event": "Sale",
            "date": "2024-06-15T00:00:00.000Z",
            "price": 300000,
        },
        "2019-05-10": {
            "event": "Sale",
            "date": "2019-05-10T00:00:00.000Z",
            "price": 150000,
        },
    },
}
assert module.sale_from_record_paired(matched) == (300000.0, "2024-06-15")


# Weak high-price rows must not move the primary ARV away from quality comps.
subject = {
    "address": "1263 Allison Gap Rd, Saltville, VA 24370",
    "property_type": "Single Family",
    "beds": 2,
    "baths": 1,
    "sqft": 1100,
}
stage = {
    "name": "Expanded",
    "radius": 3.0,
    "days": 730,
    "sqft_tolerance": 0.35,
}
sales_rows = [
    {
        "id": "quality-1",
        "comp_address": "100 Quality Rd, Saltville, VA 24370",
        "sold_price": 100000,
        "sold_date": "2026-01-15",
        "square_feet": 1000,
        "price_per_sqft": 100,
        "distance_miles": 1.0,
        "sale_age_days": 180,
        "score": "Strong Comp",
        "score_points": 96,
        "flags": [],
        "include_default": True,
    },
    {
        "id": "quality-2",
        "comp_address": "101 Quality Rd, Saltville, VA 24370",
        "sold_price": 110000,
        "sold_date": "2026-02-15",
        "square_feet": 1100,
        "price_per_sqft": 100,
        "distance_miles": 1.5,
        "sale_age_days": 150,
        "score": "Strong Comp",
        "score_points": 94,
        "flags": [],
        "include_default": True,
    },
    {
        "id": "quality-3",
        "comp_address": "102 Quality Rd, Saltville, VA 24370",
        "sold_price": 120000,
        "sold_date": "2026-03-15",
        "square_feet": 1200,
        "price_per_sqft": 100,
        "distance_miles": 2.0,
        "sale_age_days": 120,
        "score": "Good Comp",
        "score_points": 80,
        "flags": [],
        "include_default": True,
    },
]
for index in range(7):
    sales_rows.append(
        {
            "id": f"weak-{index}",
            "comp_address": f"{200 + index} Weak Rd, Saltville, VA 24370",
            "sold_price": 300000 + index * 1000,
            "sold_date": "2024-01-01",
            "square_feet": 1000,
            "price_per_sqft": 300 + index,
            "distance_miles": 2.5,
            "sale_age_days": 700,
            "score": "Weak Comp",
            "score_points": 55,
            "flags": ["weak similarity"],
            "include_default": True,
        }
    )

guarded_sales = module.apply_ppsf_outlier_guard_quality(sales_rows)
display, arv_summary = module.summarize_recorded_sales_quality(
    guarded_sales, subject, stage, len(guarded_sales)
)
assert arv_summary["verified_sold_comp_count"] == 3
assert arv_summary["recommended_arv"] == 110000
assert arv_summary["price_median"] == 110000
assert arv_summary["ppsf_arv"] == 110000
assert arv_summary["pre_condition_arv_confidence"] == "Strong"
assert arv_summary["arv_confidence"] == "Medium"
assert arv_summary["arv_requires_human_verification"] is True
assert module.CONDITION_REASON in arv_summary["verification_reasons"]
assert all(
    row.get("score") in {"Strong Comp", "Good Comp"}
    for row in display
    if row.get("include_default")
)


# Weak distant asking rents must not dominate three quality rental listings.
rent_rows = []
for index, rent in enumerate([1000, 1050, 1100]):
    rent_rows.append(
        {
            "id": f"quality-rent-{index}",
            "address": f"{300 + index} Rental Rd, Saltville, VA 24370",
            "property_type": "Single Family",
            "beds": 2,
            "baths": 1,
            "sqft": 1050 + index * 25,
            "rent": rent,
            "distance": 1.0 + index,
            "status": "Active",
            "listed_date": "2026-05-01",
            "last_seen_date": "2026-06-15",
            "days_old": 30,
            "correlation": 0.92,
        }
    )
for index in range(7):
    rent_rows.append(
        {
            "id": f"weak-rent-{index}",
            "address": f"{400 + index} Distant Rd, Abingdon, VA 24210",
            "property_type": "Single Family",
            "beds": 2,
            "baths": 1,
            "sqft": 1500,
            "rent": 2000,
            "distance": 30,
            "status": "Inactive",
            "listed_date": "2024-01-01",
            "last_seen_date": "2024-02-01",
            "days_old": 600,
            "correlation": 0.70,
        }
    )

rent_summary = module.analyze_rent_intelligence_quality(
    subject, rent_rows, avm_rent=1050
)
assert rent_summary["verified_rent_comp_count"] == 3
assert rent_summary["rent_comp_count"] == 3
assert rent_summary["rent_comp_median"] == 1050
assert rent_summary["recommended_rent"] == 1050
assert rent_summary["rent_requires_human_verification"] is False
assert (
    rent_summary["rent_comp_quality_summary"]["calculation_comp_quality"]
    == "Strong and good rental listings only"
)
assert (
    rent_summary["rent_comp_quality_summary"]["evidence_note"]
    == module.RENT_EVIDENCE_NOTE
)
assert all(
    row.get("score") in {"Strong Comp", "Good Comp"}
    for row in rent_summary["rent_comps"]
    if row.get("include_default")
)

print(
    "RentCast sale-pairing, quality-comp ARV, condition guard, and rural rent "
    "hardening smoke test passed."
)
