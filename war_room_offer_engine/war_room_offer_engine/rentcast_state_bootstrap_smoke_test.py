from __future__ import annotations

from rentcast_state_bootstrap import hydrate_rentcast_state


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self, state):
        self.session_state = FakeState(state)


# Zillow/listing path: comps arrive inside one_load_normalized.data.
zillow_state = FakeSt(
    {
        "one_load_normalized": {
            "data": {
                "rent": 1040,
                "rent_comps": [
                    {"rent": 1300},
                    {"rent": 750},
                    {"rent": 1350},
                    {"rent": 1100},
                ],
                "rentcast_sold_comps": [
                    {"sold_price": 34000},
                    {"sold_price": 37000},
                    {"sold_price": 36000},
                ],
                "rentcast_arv": 35667,
                "arv_source": "RentCast sold comps",
                "arv_confidence": "Strong",
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
assert zillow_state.session_state["rentcast_arv"] == 35667


# Plain-address path: comps are hydrated directly into session state while the
# normalized lead record contains no RentCast comp lists. A Streamlit rerun must
# preserve the returned comps and verified status.
address_state = FakeSt(
    {
        "one_load_normalized": {"data": {"address": "1115 Matson Dr", "rent": 1040}},
        "rent": 1040,
        "rentcast_rent_comps": [
            {"rent": 1300},
            {"rent": 750},
            {"rent": 1350},
            {"rent": 1100},
        ],
        "rentcast_sold_comps": [
            {"sold_price": 34000},
            {"sold_price": 37000},
            {"sold_price": 36000},
        ],
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
assert address_state.session_state["rentcast_submitted_address"] == "1115 Matson Dr, Marion, VA 24354"

print("RentCast state hydration and rerun persistence smoke tests passed.")
