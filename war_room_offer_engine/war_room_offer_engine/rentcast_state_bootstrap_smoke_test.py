from __future__ import annotations

from rentcast_state_bootstrap import hydrate_rentcast_state


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self, state):
        self.session_state = FakeState(state)


SOLD_COMPS = [
    {
        "comp_address": "Sale 1",
        "sold_price": 34000,
        "sold_date": "2026-01-15",
        "beds": 2,
        "baths": 1,
        "square_feet": 900,
        "distance_miles": 0.3,
        "confidence": "High",
    },
    {
        "comp_address": "Sale 2",
        "sold_price": 37000,
        "sold_date": "2026-02-15",
        "beds": 2,
        "baths": 1,
        "square_feet": 875,
        "distance_miles": 0.7,
        "confidence": "High",
    },
    {
        "comp_address": "Sale 3",
        "sold_price": 36000,
        "sold_date": "2026-03-15",
        "beds": 2,
        "baths": 1,
        "square_feet": 925,
        "distance_miles": 0.9,
        "confidence": "High",
    },
]


# Zillow/listing path: comps arrive inside one_load_normalized.data. Even an
# older record without auto_arv_summary must be scored during hydration.
zillow_state = FakeSt(
    {
        "one_load_normalized": {
            "data": {
                "address": "1115 Matson Dr",
                "city": "Marion",
                "state": "VA",
                "zip": "24354",
                "beds": 2,
                "baths": 1,
                "sqft": 900,
                "rent": 1040,
                "rent_comps": [
                    {"rent": 1300},
                    {"rent": 750},
                    {"rent": 1350},
                    {"rent": 1100},
                ],
                "rentcast_sold_comps": SOLD_COMPS,
                "rentcast_arv": 35667,
                "arv_source": "RentCast AVM only",
                "arv_confidence": "AVM only",
            }
        }
    }
)
hydrate_rentcast_state(zillow_state)

assert zillow_state.session_state["rent"] == 1040
assert zillow_state.session_state["rent_verification_needed"] == "No"
assert zillow_state.session_state["rent_confidence"] == "Strong verified rent comps"
assert zillow_state.session_state["rentcast_comp_count"] == 4
assert zillow_state.session_state["rentcast_rent_comp_count"] == 4
assert zillow_state.session_state["rent_comp_count"] == 4
assert zillow_state.session_state["rentcast_sold_comp_count"] == 3
assert zillow_state.session_state["rentcast_value_comp_count"] == 3
assert zillow_state.session_state["auto_comp_count"] == 3
assert zillow_state.session_state["auto_recommended_arv"] == 35667
assert zillow_state.session_state["arv"] == 35667
assert zillow_state.session_state["arv_source_used"] == "Automatic Sold Comps"
assert zillow_state.session_state["arv_confidence"] == "Strong"
assert zillow_state.session_state["rentcast_arv"] == 35667
assert all(comp.get("score") for comp in zillow_state.session_state["auto_sold_comps"])


# Plain-address path: comps are hydrated directly into session state while the
# normalized lead record contains no RentCast comp lists. A Streamlit rerun must
# preserve and score the returned comps without another API call or button click.
address_state = FakeSt(
    {
        "one_load_normalized": {
            "data": {
                "address": "1115 Matson Dr",
                "city": "Marion",
                "state": "VA",
                "zip": "24354",
                "beds": 2,
                "baths": 1,
                "sqft": 900,
                "rent": 1040,
            }
        },
        "rent": 1040,
        "rentcast_rent_comps": [
            {"rent": 1300},
            {"rent": 750},
            {"rent": 1350},
            {"rent": 1100},
        ],
        "rentcast_sold_comps": SOLD_COMPS,
        "rentcast_arv": 35667,
        "rentcast_submitted_address": "1115 Matson Dr, Marion, VA 24354",
        "rent_verification_needed": "No",
    }
)
hydrate_rentcast_state(address_state)

assert len(address_state.session_state["rentcast_rent_comps"]) == 4
assert address_state.session_state["rentcast_rent_comp_count"] == 4
assert address_state.session_state["rent_verification_needed"] == "No"
assert address_state.session_state["rent_confidence"] == "Strong verified rent comps"
assert address_state.session_state["rentcast_value_comp_count"] == 3
assert address_state.session_state["auto_comp_count"] == 3
assert address_state.session_state["auto_recommended_arv"] == 35667
assert address_state.session_state["arv"] == 35667
assert address_state.session_state["arv_source_used"] == "Automatic Sold Comps"
assert address_state.session_state["rentcast_submitted_address"] == "1115 Matson Dr, Marion, VA 24354"

print("RentCast state hydration, automatic ARV and rerun persistence smoke tests passed.")
