from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent.parent
for import_path in [str(REPO_ROOT), str(APP_DIR)]:
    if import_path in sys.path:
        sys.path.remove(import_path)
    sys.path.insert(0, import_path)


patch = importlib.import_module("rentcast_auto_comps_patch")


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = ""

    def json(self):
        return self._payload


def fake_get(url, headers=None, params=None, timeout=None):
    if url.endswith("/v1/properties"):
        return FakeResponse(
            200,
            [
                {
                    "bedrooms": 2,
                    "bathrooms": 1,
                    "squareFootage": 900,
                    "propertyType": "Single Family",
                    "yearBuilt": 1940,
                }
            ],
        )
    if url.endswith("/v1/avm/rent/long-term"):
        return FakeResponse(
            200,
            {
                "rent": 1050,
                "subjectProperty": {"bedrooms": 2, "bathrooms": 1, "squareFootage": 900},
                "comparables": [
                    {"formattedAddress": "Comp 1", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "price": 1300, "distance": 0.4, "correlation": 0.95},
                    {"formattedAddress": "Comp 2", "bedrooms": 2, "bathrooms": 1, "squareFootage": 850, "price": 750, "distance": 0.8, "correlation": 0.90},
                    {"formattedAddress": "Comp 3", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "price": 1350, "distance": 1.2, "correlation": 0.88},
                    {"formattedAddress": "Comp 4", "bedrooms": 2, "bathrooms": 2, "squareFootage": 900, "price": 1100, "distance": 1.5, "correlation": 0.84},
                ],
            },
        )
    if url.endswith("/v1/avm/value"):
        return FakeResponse(
            200,
            {
                "price": 35667,
                "comparables": [
                    {"formattedAddress": "Sale 1", "price": 34000, "lastSaleDate": "2026-01-15", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "distance": 0.4, "propertyType": "Single Family"},
                    {"formattedAddress": "Sale 2", "price": 37000, "lastSaleDate": "2026-02-15", "bedrooms": 2, "bathrooms": 1, "squareFootage": 875, "distance": 0.7, "propertyType": "Single Family"},
                    {"formattedAddress": "Sale 3", "price": 36000, "lastSaleDate": "2026-03-15", "bedrooms": 2, "bathrooms": 1, "squareFootage": 925, "distance": 1.1, "propertyType": "Single Family"},
                ],
            },
        )
    raise AssertionError(url)


patch.base.get_secret = lambda name, default="": "test-key" if name == "RENTCAST_API_KEY" else default
patch.base.requests.get = fake_get

result = patch.lookup_rentcast_with_comps(
    "1115 Matson Dr, Marion, VA 24354",
    beds=2,
    baths=1,
    sqft=900,
)

assert result["rent"] == 1050
assert result["rentcast_rent_comp_count"] == 4
assert result["rentcast_rent_comp_average"] == 1125
assert result["rentcast_rent_comp_median"] == 1200
assert result["rent_confidence"] == "Strong verified rent comps"
assert result["arv"] == 35667
assert result["rentcast_value_comp_count"] == 3
assert result["rentcast_submitted_address"] == "1115 Matson Dr, Marion, VA 24354"
assert result["rentcast_rent_http_status"] == 200
assert result["rentcast_value_http_status"] == 200

print("RentCast automatic comps smoke test passed.")
