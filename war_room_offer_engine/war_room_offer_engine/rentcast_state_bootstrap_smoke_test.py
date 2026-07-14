from __future__ import annotations

from rentcast_state_bootstrap import hydrate_rentcast_state


class FakeState(dict):
    pass


class FakeSt:
    def __init__(self):
        self.session_state = FakeState(
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


st = FakeSt()
hydrate_rentcast_state(st)

assert st.session_state["rent"] == 1040
assert st.session_state["rent_verification_needed"] == "No"
assert st.session_state["rent_confidence"] == "Strong verified rent comps"
assert st.session_state["rentcast_comp_count"] == 4
assert st.session_state["rentcast_rent_comp_count"] == 4
assert st.session_state["rent_comp_count"] == 4
assert st.session_state["rentcast_sold_comp_count"] == 3
assert st.session_state["rentcast_value_comp_count"] == 3
assert st.session_state["auto_comp_count"] == 3
assert st.session_state["rentcast_arv"] == 35667

print("RentCast state alias hydration smoke test passed.")
