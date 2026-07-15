from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


module = importlib.import_module("rentcast_comp_normalization_fix")

subject = {
    "address": "1115 Matson Dr",
    "city": "Marion",
    "state": "VA",
    "zip": "24354",
    "beds": 2,
    "baths": 1,
    "sqft": 735,
    "property_type": "Single Family",
}

raw_comps = [
    {"comp_address": "1115 Matson Dr, Marion, VA 24354", "sold_price": 30000, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 735, "distance_miles": 0.0043, "source": "RentCast", "confidence": "High"},
    {"comp_address": "804 Spruce St, Marion, VA 24354", "sold_price": 55000, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 728, "distance_miles": 0.5583, "source": "RentCast", "confidence": "High"},
    {"comp_address": "708 Spruce St, Marion, VA 24354", "sold_price": 44900, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 859, "distance_miles": 0.6219, "source": "RentCast", "confidence": "High"},
    {"comp_address": "115 Matson Dr, Marion, VA 24354", "sold_price": 29000, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 0, "distance_miles": 0.0047, "source": "RentCast", "confidence": "High"},
    {"comp_address": "228 Henderson St, Marion, VA 24354", "sold_price": 34900, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 602, "distance_miles": 0.6189, "source": "RentCast", "confidence": "High"},
    {"comp_address": "225 W Coyner Ave, Marion, VA 24354", "sold_price": 135000, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 801, "distance_miles": 1.8790, "source": "RentCast", "confidence": "High"},
    {"comp_address": "196 Severt St, Marion, VA 24354", "sold_price": 94500, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 981, "distance_miles": 0.6360, "source": "RentCast", "confidence": "High"},
    {"comp_address": "255 W Coyner Ave, Marion, VA 24354", "sold_price": 135000, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 801, "distance_miles": 1.9215, "source": "RentCast", "confidence": "High"},
    {"comp_address": "140 Race Blvd, Marion, VA 24354", "sold_price": 124900, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 844, "distance_miles": 1.9164, "source": "RentCast", "confidence": "High"},
    {"comp_address": "206 Sprinkle Ave, Marion, VA 24354", "sold_price": 195000, "sold_date": "", "beds": 2, "baths": 1, "square_feet": 906, "distance_miles": 1.7497, "source": "RentCast", "confidence": "High"},
]

scored, summary = module.build_sold_comp_intelligence_fixed(subject, raw_comps)

assert summary["subject_comp_removed_count"] == 1
assert all("1115 matson" not in str(row.get("comp_address", "")).lower() for row in scored)
assert summary["included_comp_count"] == 3
assert int(summary["recommended_arv"]) == 44933
assert summary["arv_confidence"] == "Weak"
assert summary["sale_dates_unverified"] is True
assert summary["search_radius"] == "1 mile"

included_addresses = {
    row["comp_address"]
    for row in scored
    if row.get("include_default") and row.get("score") != "Bad Comp"
}
assert included_addresses == {
    "804 Spruce St, Marion, VA 24354",
    "708 Spruce St, Marion, VA 24354",
    "228 Henderson St, Marion, VA 24354",
}


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self):
        self.session_state = FakeState()


fake_st = FakeSt()
rents = [1300, 750, 1350, 1100, 1175, 1500, 1100, 750, 750, 750]
module._store_rent_stats(fake_st, {"rent_comps": [{"rent": value} for value in rents]})

assert fake_st.session_state["rent_comp_average"] == 1053
assert fake_st.session_state["rentcast_rent_comp_average"] == 1053
assert fake_st.session_state["rent_comp_median"] == 1100
assert fake_st.session_state["rentcast_rent_comp_median"] == 1100

print("RentCast subject removal, date-unverified ARV and rent-stat hydration smoke test passed.")
