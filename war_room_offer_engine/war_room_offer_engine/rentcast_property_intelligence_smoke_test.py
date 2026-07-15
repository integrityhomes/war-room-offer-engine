from __future__ import annotations

import importlib
import sys
from datetime import date, timedelta
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
for path in [str(APP_DIR), str(APP_DIR.parent), str(APP_DIR.parent.parent)]:
    if path not in sys.path:
        sys.path.insert(0, path)


module = importlib.import_module("rentcast_property_intelligence")
module._RESPONSE_CACHE.clear()
module._RESULT_CACHE.clear()


def iso(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat() + "T00:00:00.000Z"


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def get(self, endpoint, **kwargs):
        params = dict(kwargs.get("params", {}) or {})
        self.calls.append((str(endpoint), params))

        if str(endpoint).endswith("/avm/rent/long-term"):
            return FakeResponse(
                {
                    "rent": 1100,
                    "comparables": [
                        {
                            "id": "near-rent",
                            "formattedAddress": "200 Main St, Rural, VA 24354",
                            "price": 1125,
                            "propertyType": "Single Family",
                            "bedrooms": 3,
                            "bathrooms": 2,
                            "squareFootage": 1200,
                            "distance": 2.0,
                            "status": "Active",
                            "lastSeenDate": iso(20),
                            "daysOld": 20,
                            "correlation": 0.93,
                        }
                    ],
                }
            )

        if str(endpoint).endswith("/avm/value"):
            return FakeResponse(
                {
                    "price": 165000,
                    "comparables": [
                        {
                            "id": f"listing-{index}",
                            "formattedAddress": f"{300 + index} Listing Rd, Rural, VA 24354",
                            "price": 170000 + index * 5000,
                            "propertyType": "Single Family",
                            "bedrooms": 3,
                            "bathrooms": 2,
                            "squareFootage": 1200 + index * 20,
                            "distance": 3 + index,
                            "status": "Active",
                            "listedDate": iso(30),
                            "lastSeenDate": iso(2),
                            "daysOld": 2,
                            "correlation": 0.90 - index * 0.02,
                        }
                        for index in range(4)
                    ],
                }
            )

        if str(endpoint).endswith("/properties"):
            if "radius" not in params:
                return FakeResponse(
                    [
                        {
                            "id": "100-County-Rd-Rural-VA-24354",
                            "formattedAddress": "100 County Rd, Rural, VA 24354",
                            "addressLine1": "100 County Rd",
                            "city": "Rural",
                            "state": "VA",
                            "zipCode": "24354",
                            "county": "Smyth",
                            "latitude": 36.84,
                            "longitude": -81.52,
                            "propertyType": "Single Family",
                            "bedrooms": 3,
                            "bathrooms": 2,
                            "squareFootage": 1200,
                            "lotSize": 87120,
                            "yearBuilt": 1980,
                            "lastSaleDate": iso(2000),
                            "lastSalePrice": 70000,
                            "propertyTaxes": {"2025": {"year": 2025, "total": 900}},
                            "taxAssessments": {"2025": {"year": 2025, "value": 85000}},
                        }
                    ]
                )

            if int(params.get("radius", 0) or 0) == 10:
                return FakeResponse([])

            sales = []
            for index, (latitude, price, sqft, age) in enumerate(
                [
                    (37.00, 150000, 1150, 300),
                    (37.05, 160000, 1250, 500),
                    (37.10, 155000, 1180, 650),
                    (37.12, 170000, 1300, 800),
                ]
            ):
                sales.append(
                    {
                        "id": f"sale-{index}",
                        "formattedAddress": f"{400 + index} Farm Rd, Rural, VA 24354",
                        "city": "Rural",
                        "state": "VA",
                        "zipCode": "24354",
                        "county": "Smyth",
                        "latitude": latitude,
                        "longitude": -81.52,
                        "propertyType": "Single Family",
                        "bedrooms": 3,
                        "bathrooms": 2,
                        "squareFootage": sqft,
                        "lotSize": 90000,
                        "yearBuilt": 1982,
                        "lastSaleDate": iso(age),
                        "lastSalePrice": price,
                    }
                )
            return FakeResponse(sales)

        if str(endpoint).endswith("/listings/rental/long-term"):
            if params.get("status") == "Active":
                return FakeResponse(
                    [
                        {
                            "id": f"rent-{index}",
                            "formattedAddress": f"{500 + index} Rural Hwy, Rural, VA 24354",
                            "city": "Rural",
                            "state": "VA",
                            "zipCode": "24354",
                            "county": "Smyth",
                            "latitude": 36.96 + index * 0.02,
                            "longitude": -81.52,
                            "propertyType": "Single Family",
                            "bedrooms": 3,
                            "bathrooms": 2,
                            "squareFootage": 1150 + index * 30,
                            "price": 1050 + index * 50,
                            "status": "Active",
                            "lastSeenDate": iso(10 + index),
                            "listedDate": iso(30 + index),
                        }
                        for index in range(4)
                    ]
                )
            return FakeResponse([])

        raise AssertionError(f"Unexpected RentCast endpoint: {endpoint}")


session = FakeSession()
subject = {
    "address": "100 County Rd",
    "city": "Rural",
    "state": "VA",
    "zip": "24354",
}
result = module.enrich_property_with_intelligence(subject, "test-key", session=session)

assert result["rentcast_property_record_id"] == "100-County-Rd-Rural-VA-24354"
assert result["beds"] == 3
assert result["sqft"] == 1200
assert result["taxes"] == 900

# RentCast AVM comparables are listing evidence, not confirmed closed sales.
assert result["rentcast_value_listing_comp_count"] == 4
assert all(row.get("record_type") == "sale_listing" for row in result["rentcast_value_listing_comps"])

# Actual ARV evidence comes from the /properties public-record sold search.
assert result["arv_source"] == "RentCast Recorded Sales"
assert result["verified_sold_comp_count"] >= 3
assert result["arv_search_mode"] == "Deep rural"
assert result["arv_requires_human_verification"] is True
assert result["arv"] > 0
assert result["arv_median_ppsf"] > 0
assert result["arv_ppsf_estimate"] > 0

# Sparse rental markets expand to listing search and remain transparently scored.
assert result["verified_rent_comp_count"] >= 3
assert result["rent_search_mode"] in {"Rural", "Deep rural"}
assert result["rent"] > 0
assert result["rentcast_rent_avm"] == 1100
assert result["rural_market_detected"] is True
assert any(endpoint.endswith("/listings/rental/long-term") for endpoint, _ in session.calls)
assert any(
    endpoint.endswith("/properties") and int(params.get("radius", 0) or 0) == 50
    for endpoint, params in session.calls
)

# Paid calls are cached during Streamlit reruns for the same property and query.
before = len(session.calls)
second = module.enrich_property_with_intelligence(subject, "test-key", session=session)
assert second["arv"] == result["arv"]
assert second["rent"] == result["rent"]
assert len(session.calls) == before


# Decision guards use verified-quality counts rather than treating any three distant rows as proof.
import deal_decision_logic as decision_logic

weak_rent_state = {
    "address": "100 County Rd, Rural, VA 24354",
    "rent": 1100,
    "rentcast_rent_comp_count": 5,
    "verified_rent_comp_count": 2,
    "rent_requires_human_verification": True,
    "rent_confidence": "Weak rural fallback comps",
}
assert decision_logic.rent_verified(weak_rent_state) is False

listing_only_state = {
    "address": "100 County Rd, Rural, VA 24354",
    "arv": 165000,
    "arv_source_used": "RentCast AVM — listing-based",
    "rentcast_value_comp_count": 10,
    "verified_sold_comp_count": 0,
    "arv_requires_human_verification": True,
    "repairs": 25000,
    "repair_source": "AI Repair Estimate",
}
assert decision_logic.sold_count(listing_only_state) == 0
assert "verified ARV / recorded sold comps" in decision_logic.missing_items(
    listing_only_state, decision_logic.WHOLESALE_OFF_MARKET
)

print("RentCast recorded-sale, rural ARV, rural rent and request-cache smoke test passed.")
