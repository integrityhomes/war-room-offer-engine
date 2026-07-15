from __future__ import annotations

import sys
from types import SimpleNamespace


class FakeResponse:
    def __init__(self, status_code, payload, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


class FakeRequests:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        params = dict(params or {})
        self.calls.append((url, params))
        if url.endswith("/v1/properties"):
            return FakeResponse(
                200,
                [
                    {
                        "bedrooms": 2,
                        "bathrooms": 1,
                        "squareFootage": 900,
                        "yearBuilt": 1940,
                        "propertyType": "Single Family",
                        "propertyTaxes": {"2025": {"amount": 520}},
                    }
                ],
            )
        if url.endswith("/v1/avm/rent/long-term"):
            # Simulate a rural property where the constrained subject request
            # returns nothing but the full-address retry returns the same data
            # visible in RentCast's web interface.
            if "bedrooms" in params or "squareFootage" in params:
                return FakeResponse(200, {})
            return FakeResponse(
                200,
                {
                    "rent": 1040,
                    "comparables": [
                        {"formattedAddress": "Rent 1", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "price": 1300, "distance": 0.4},
                        {"formattedAddress": "Rent 2", "bedrooms": 2, "bathrooms": 1, "squareFootage": 850, "price": 750, "distance": 0.8},
                        {"formattedAddress": "Rent 3", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "price": 1350, "distance": 1.2},
                        {"formattedAddress": "Rent 4", "bedrooms": 2, "bathrooms": 2, "squareFootage": 900, "price": 1100, "distance": 1.5},
                    ],
                },
            )
        if url.endswith("/v1/avm/value"):
            return FakeResponse(
                200,
                {
                    "price": 35667,
                    "comparables": [
                        {"formattedAddress": "Sale 1", "price": 34000, "lastSaleDate": "2026-01-15", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "distance": 0.3},
                        {"formattedAddress": "Sale 2", "price": 37000, "lastSaleDate": "2026-02-15", "bedrooms": 2, "bathrooms": 1, "squareFootage": 875, "distance": 0.7},
                        {"formattedAddress": "Sale 3", "price": 36000, "lastSaleDate": "2026-03-15", "bedrooms": 2, "bathrooms": 1, "squareFootage": 925, "distance": 0.9},
                    ],
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")


fake_st = SimpleNamespace(session_state={})
sys.modules["streamlit"] = fake_st

import address_rentcast_bridge as bridge

fake_requests = FakeRequests()
bridge.ds.requests = fake_requests
bridge.ds.get_secret = lambda name, default="": "test-key" if name == "RENTCAST_API_KEY" else default

result = bridge.lookup_rentcast_with_full_enrichment(
    "1115 Matson Dr, Marion, VA 24354",
    beds=3,
    baths=1,
    sqft=1000,
)

assert result["found"]
assert result["rent"] == 1040
assert result["rent_comp_count"] == 4
assert result["rent_comp_average"] == 1125
assert result["rent_comp_median"] == 1200
assert result["rent_confidence"] == "Strong verified rent comps"
assert result["rentcast_lookup_retry_used"] is True
assert result["rentcast_submitted_address"] == "1115 Matson Dr, Marion, VA 24354"
assert result["rentcast_arv"] == 35667
assert result["rentcast_sold_comp_count"] == 3
assert result["auto_comp_count"] == 3
assert result["auto_recommended_arv"] == 35667
assert result["arv"] == 35667
assert result["arv_source"] == "Automatic Sold Comps"
assert result["arv_confidence"] == "Strong"
assert result["beds"] == 2
assert result["baths"] == 1
assert result["sqft"] == 900
assert result["taxes"] == 520

state = fake_st.session_state
assert state["rentcast_rent_comp_count"] == 4
assert state["rentcast_comp_count"] == 4
assert state["rent_verification_needed"] == "No"
assert state["rentcast_value_comp_count"] == 3
assert state["auto_comp_count"] == 3
assert state["auto_recommended_arv"] == 35667
assert state["arv"] == 35667
assert state["arv_source_used"] == "Automatic Sold Comps"
assert state["value_source"] == "Automatic Sold Comps"
assert state["rentcast_arv"] == 35667
assert all(comp.get("score") for comp in state["auto_sold_comps"])

constrained_rent_calls = [params for url, params in fake_requests.calls if url.endswith("/v1/avm/rent/long-term") and "bedrooms" in params]
retry_rent_calls = [params for url, params in fake_requests.calls if url.endswith("/v1/avm/rent/long-term") and "bedrooms" not in params]
assert constrained_rent_calls
assert retry_rent_calls
assert constrained_rent_calls[0]["bedrooms"] == 2
assert constrained_rent_calls[0]["squareFootage"] == 900
assert retry_rent_calls[0]["address"] == "1115 Matson Dr, Marion, VA 24354"

print("Plain-address RentCast enrichment and automatic sold-comp ARV smoke test passed.")
