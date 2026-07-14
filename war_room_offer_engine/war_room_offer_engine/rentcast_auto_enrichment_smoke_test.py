from __future__ import annotations

import importlib
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)

module = importlib.import_module("rentcast_auto_enrichment")


class FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
        self.text = "ok"

    def json(self):
        return self._payload


class FakeSession:
    def get(self, endpoint, **kwargs):
        if endpoint == module.RENT_ENDPOINT:
            return FakeResponse(
                {
                    "rent": 1050,
                    "rentRange": {"low": 750, "high": 1350},
                    "comparables": [
                        {"formattedAddress": "Comp 1", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "rent": 1300},
                        {"formattedAddress": "Comp 2", "bedrooms": 2, "bathrooms": 1, "squareFootage": 850, "rent": 750},
                        {"formattedAddress": "Comp 3", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900, "rent": 1350},
                        {"formattedAddress": "Comp 4", "bedrooms": 2, "bathrooms": 2, "squareFootage": 900, "rent": 1100},
                    ],
                }
            )
        return FakeResponse(
            {
                "price": 35667,
                "comparables": [
                    {"formattedAddress": "Sold 1", "price": 35000, "saleDate": "2026-01-01", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900},
                    {"formattedAddress": "Sold 2", "price": 37000, "saleDate": "2026-02-01", "bedrooms": 2, "bathrooms": 1, "squareFootage": 850},
                    {"formattedAddress": "Sold 3", "price": 35500, "saleDate": "2026-03-01", "bedrooms": 2, "bathrooms": 1, "squareFootage": 900},
                ],
            }
        )


data = {
    "address": "1115 Matson Dr",
    "city": "Marion",
    "state": "VA",
    "zip": "24354",
    "beds": 2,
    "baths": 1,
    "sqft": 900,
}
result = module.enrich_property_with_rentcast(data, "test-key", session=FakeSession())

assert result["rentcast_submitted_address"] == "1115 Matson Dr, Marion, VA 24354"
assert result["rent"] == 1050
assert result["rent_comp_count"] == 4
assert result["rent_comp_average"] == 1125
assert result["rent_comp_median"] == 1200
assert result["rent_confidence"] == "Strong verified rent comps"
assert result["rentcast_arv"] == 35667
assert result["rentcast_sold_comp_count"] == 3
assert result["arv_source"] == "RentCast sold comps"
assert result["arv_confidence"] == "Strong"

print("RentCast automatic rent and ARV enrichment smoke test passed.")
