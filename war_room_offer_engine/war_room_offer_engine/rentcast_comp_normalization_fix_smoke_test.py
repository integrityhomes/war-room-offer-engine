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

# Exact street identity must handle common abbreviations while protecting
# legitimate properties with a different house number, street, city or unit.
assert module._is_subject_comp(
    "1115 Matson Drive, Marion, VA 24354",
    "1115 Matson Dr, Marion, VA 24354",
)
assert not module._is_subject_comp(
    "1115 Matson Dr, Marion, VA 24354",
    "115 Matson Dr, Marion, VA 24354",
)
assert not module._is_subject_comp(
    "100 St Paul St, Marion, VA 24354",
    "100 St James Ave, Marion, VA 24354",
)
assert not module._is_subject_comp(
    "100 Dr Martin Luther King Jr Blvd, Marion, VA 24354",
    "100 Dr Smith Rd, Marion, VA 24354",
)
assert not module._is_subject_comp(
    "100 Main St, Marion, VA 24354",
    "100 Main St, Bristol, VA 24201",
)
assert module._is_subject_comp(
    "100 Valley Parkway, Marion, VA 24354",
    "100 Valley Pkwy, Marion, VA 24354",
)
assert module._is_subject_comp(
    "100 West Main Street, Marion, VA 24354",
    "100 W Main St, Marion, VA 24354",
)
assert not module._is_subject_comp(
    "100 Main St Apt 2, Marion, VA 24354",
    "100 Main St Apt 3, Marion, VA 24354",
)
assert not module._is_subject_comp(
    "100 Main St Apt 2, Marion, VA 24354",
    "100 Main St, Marion, VA 24354",
)

# Date-free records are provisional only when the source is explicitly
# RentCast. An undated record from another source must remain excluded.
non_rentcast = module._score_rentcast_stage(
    [
        {
            "comp_address": "10 Main St, Marion, VA 24354",
            "sold_price": 50000,
            "sold_date": "",
            "beds": 2,
            "baths": 1,
            "square_feet": 735,
            "distance_miles": 0.2,
            "source": "County Records",
            "confidence": "High",
        }
    ],
    {
        "sqft": 735,
        "beds": 2,
        "baths": 1,
        "property_type": "Single Family",
        "functional_risks": "",
    },
    "1 mile",
    "Last 12 months",
)[0]
assert non_rentcast["include_default"] is False
assert "missing sold date" in non_rentcast["flags"]


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

# An explicitly empty current-property result is authoritative. It must clear
# previous rows, counts and statistics instead of reviving stale session data.
fake_st.session_state["rentcast_rent_comps"] = [{"rent": 9999}]
fake_st.session_state["rent_comps"] = [{"rent": 9999}]
fake_st.session_state["rent_comp_average"] = 9999
fake_st.session_state["rent_comp_median"] = 9999
module._store_rent_stats(fake_st, {"rent_comps": []})
assert fake_st.session_state["rentcast_rent_comps"] == []
assert fake_st.session_state["rent_comps"] == []
assert fake_st.session_state["rentcast_rent_comp_count"] == 0
assert fake_st.session_state["rent_comp_count"] == 0
assert fake_st.session_state["rent_comp_average"] == 0
assert fake_st.session_state["rent_comp_median"] == 0

# The same rule applies to a new property's empty ARV result. Clear the prior
# provisional comp state rather than reapplying it through rerun fallbacks.
fake_st.session_state.update(
    {
        "auto_arv_summary": {"sale_dates_unverified": True, "recommended_arv": 44933},
        "auto_sold_comps": [{"comp_address": "old property"}],
        "auto_comp_count": 1,
        "auto_recommended_arv": 44933,
        "strong_comp_count": 2,
        "good_comp_count": 1,
        "arv": 44933,
        "arv_source_used": module._UNVERIFIED_ARV_SOURCE,
        "value_source": module._UNVERIFIED_ARV_SOURCE,
        "arv_confidence": "Weak",
    }
)
module._store_unverified_source(
    fake_st,
    {
        "auto_arv_summary": {},
        "auto_sold_comps": [],
        "rentcast_sold_comps": [],
        "arv": 0,
        "auto_recommended_arv": 0,
        "rentcast_arv": 0,
    },
)
assert fake_st.session_state["auto_arv_summary"] == {}
assert fake_st.session_state["auto_sold_comps"] == []
assert fake_st.session_state["rentcast_sold_comps"] == []
assert fake_st.session_state["auto_comp_count"] == 0
assert fake_st.session_state["auto_recommended_arv"] == 0
assert fake_st.session_state["strong_comp_count"] == 0
assert fake_st.session_state["good_comp_count"] == 0
assert fake_st.session_state["arv"] == 0
assert fake_st.session_state["arv_source_used"] == ""
assert fake_st.session_state["value_source"] == ""
assert fake_st.session_state["arv_confidence"] == "Not enough data"

# A valid current-property AVM must replace the stale provisional source label.
fake_st.session_state.update(
    {
        "arv": 44933,
        "arv_source_used": module._UNVERIFIED_ARV_SOURCE,
        "value_source": module._UNVERIFIED_ARV_SOURCE,
        "arv_confidence": "Weak",
    }
)
module._store_unverified_source(
    fake_st,
    {
        "auto_arv_summary": {},
        "auto_sold_comps": [],
        "rentcast_sold_comps": [],
        "arv": 35667,
        "rentcast_arv": 35667,
        "arv_source": "RentCast AVM only",
        "arv_confidence": "AVM only",
    },
)
assert fake_st.session_state["arv"] == 35667
assert fake_st.session_state["arv_source_used"] == "RentCast AVM only"
assert fake_st.session_state["value_source"] == "RentCast AVM only"
assert fake_st.session_state["arv_confidence"] == "AVM only"

# Start New Property clears the current identity and source snapshots. Any RentCast
# aliases left by older reset lists must be removed on the next bootstrap.
reset_st = FakeSt()
reset_st.session_state.update(
    {
        "rentcast_rent_comps": [{"rent": 9999}],
        "rent_comps": [{"rent": 9999}],
        "rent_comp_average": 9999,
        "rent_comp_median": 9999,
        "auto_sold_comps": [{"comp_address": "old property"}],
        "auto_arv_summary": {"sale_dates_unverified": True, "recommended_arv": 44933},
        "arv": 44933,
        "arv_source_used": module._UNVERIFIED_ARV_SOURCE,
        "value_source": module._UNVERIFIED_ARV_SOURCE,
    }
)
module.bootstrap_hydrate_fixed(reset_st)
for key in [
    "rentcast_rent_comps",
    "rent_comps",
    "rent_comp_average",
    "rent_comp_median",
    "auto_sold_comps",
    "auto_arv_summary",
    "arv",
    "arv_source_used",
    "value_source",
]:
    assert key not in reset_st.session_state

class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def get(self, endpoint, **kwargs):
        if str(endpoint).endswith("/rent/long-term"):
            return FakeResponse(
                {
                    "rent": 1040,
                    "comparables": [
                        {
                            "formattedAddress": f"Rental {idx}, Marion, VA 24354",
                            "rent": value,
                            "bedrooms": 2,
                            "bathrooms": 1,
                            "squareFootage": 735,
                            "distance": idx / 10,
                        }
                        for idx, value in enumerate(rents, start=1)
                    ],
                }
            )
        return FakeResponse(
            {
                "price": 35667,
                "comparables": [
                    {
                        "formattedAddress": row["comp_address"],
                        "price": row["sold_price"],
                        "saleDate": row["sold_date"],
                        "bedrooms": row["beds"],
                        "bathrooms": row["baths"],
                        "squareFootage": row["square_feet"],
                        "distance": row["distance_miles"],
                    }
                    for row in raw_comps
                ],
            }
        )


# Replay the production enrichment path, not merely the statistics helper.
# The original code produces 1052.0 for a 1052.5 average because round() uses
# half-to-even. The wrapper must store the business-facing half-up value 1053.
enriched = module.enrich_property_with_rentcast_fixed(
    subject,
    "test-key",
    session=FakeSession(),
)
assert enriched["rent_comp_average"] == 1053
assert enriched["rentcast_rent_comp_average"] == 1053
assert enriched["rent_comp_median"] == 1100
assert int(enriched["arv"]) == 44933
assert enriched["arv_source"] == module._UNVERIFIED_ARV_SOURCE
assert enriched["arv_confidence"] == "Weak"

print("RentCast subject removal, source-safe provisional ARV, address identity, state reset and production-path rent statistics smoke test passed.")
