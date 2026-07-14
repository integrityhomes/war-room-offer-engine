from __future__ import annotations

from statistics import median
from typing import Any

import requests


RENT_ENDPOINT = "https://api.rentcast.io/v1/avm/rent/long-term"
VALUE_ENDPOINT = "https://api.rentcast.io/v1/avm/value"


def _number(value: Any) -> float:
    if value in [None, "", [], {}] or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ["value", "rent", "price", "amount", "low", "high"]:
            if key in value:
                number = _number(value.get(key))
                if number:
                    return number
        return 0.0
    text = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    try:
        return float(text) if text else 0.0
    except Exception:
        return 0.0


def build_full_address(data: dict[str, Any]) -> str:
    street = str(data.get("address") or data.get("streetAddress") or "").strip()
    city = str(data.get("city") or "").strip()
    state = str(data.get("state") or "").strip()
    zipcode = str(data.get("zip") or data.get("zipcode") or "").strip()
    if not street:
        return ""
    if city and state:
        return f"{street}, {city}, {state} {zipcode}".strip()
    return street


def _first_list(payload: dict[str, Any], keys: list[str]) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def normalize_rent_comp(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": item.get("formattedAddress") or item.get("address") or item.get("streetAddress") or "",
        "beds": _number(item.get("bedrooms") or item.get("beds")),
        "baths": _number(item.get("bathrooms") or item.get("baths")),
        "sqft": _number(item.get("squareFootage") or item.get("sqft") or item.get("livingArea")),
        "rent": _number(item.get("rent") or item.get("price") or item.get("listedRent")),
        "distance": _number(item.get("distance") or item.get("distanceMiles")),
        "source": "RentCast comparable",
    }


def normalize_sold_comp(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "comp_address": item.get("formattedAddress") or item.get("address") or item.get("streetAddress") or "",
        "sold_price": _number(item.get("price") or item.get("soldPrice") or item.get("lastSalePrice")),
        "sold_date": item.get("saleDate") or item.get("soldDate") or item.get("lastSaleDate") or "",
        "beds": _number(item.get("bedrooms") or item.get("beds")),
        "baths": _number(item.get("bathrooms") or item.get("baths")),
        "square_feet": _number(item.get("squareFootage") or item.get("sqft") or item.get("livingArea")),
        "distance_miles": _number(item.get("distance") or item.get("distanceMiles")),
        "source": "RentCast",
    }


def _get_json(endpoint: str, api_key: str, params: dict[str, Any], session=requests) -> dict[str, Any]:
    try:
        response = session.get(endpoint, headers={"X-Api-Key": api_key, "Accept": "application/json"}, params=params, timeout=30)
    except Exception as exc:
        return {"ok": False, "error": f"RentCast request error: {exc}", "submitted_params": params}
    if response.status_code < 200 or response.status_code >= 300:
        return {"ok": False, "error": f"RentCast HTTP {response.status_code}: {response.text[:300]}", "submitted_params": params}
    try:
        payload = response.json()
    except Exception:
        return {"ok": False, "error": "RentCast returned non-JSON data.", "submitted_params": params}
    return {"ok": True, "payload": payload if isinstance(payload, dict) else {}, "submitted_params": params}


def enrich_property_with_rentcast(data: dict[str, Any], api_key: str, session=requests) -> dict[str, Any]:
    enriched = dict(data or {})
    full_address = build_full_address(enriched)
    if not api_key or not full_address:
        enriched["rentcast_status"] = "Missing API key or full address"
        return enriched

    common = {
        "address": full_address,
        "bedrooms": int(_number(enriched.get("beds"))) or None,
        "bathrooms": _number(enriched.get("baths")) or None,
        "squareFootage": int(_number(enriched.get("sqft"))) or None,
        "compCount": 10,
    }
    common = {key: value for key, value in common.items() if value not in [None, "", 0, 0.0]}

    rent_result = _get_json(RENT_ENDPOINT, api_key, common, session=session)
    enriched["rentcast_submitted_address"] = full_address
    enriched["rentcast_rent_error"] = rent_result.get("error", "")
    if rent_result.get("ok"):
        payload = rent_result.get("payload", {})
        rent = _number(payload.get("rent") or payload.get("rentEstimate") or payload.get("estimate"))
        rent_range = payload.get("rentRange") if isinstance(payload.get("rentRange"), dict) else {}
        raw_comps = _first_list(payload, ["comparables", "comps", "rentalComps", "rentComparables"])
        comps = [normalize_rent_comp(item) for item in raw_comps]
        comps = [item for item in comps if item.get("rent", 0) > 0]
        if rent > 0:
            enriched["rent"] = rent
            enriched["rent_estimate"] = rent
        enriched["rent_low"] = _number(rent_range.get("low") or payload.get("rentLow"))
        enriched["rent_high"] = _number(rent_range.get("high") or payload.get("rentHigh"))
        enriched["rent_comps"] = comps
        enriched["rent_comp_count"] = len(comps)
        enriched["rent_source"] = "RentCast"
        enriched["rent_confidence"] = "Strong verified rent comps" if len(comps) >= 3 else "Medium fallback comps" if rent > 0 else "Missing"
        if comps:
            enriched["rent_comp_average"] = round(sum(item["rent"] for item in comps) / len(comps), 0)
            enriched["rent_comp_median"] = round(median(item["rent"] for item in comps), 0)

    value_result = _get_json(VALUE_ENDPOINT, api_key, common, session=session)
    enriched["rentcast_value_error"] = value_result.get("error", "")
    if value_result.get("ok"):
        payload = value_result.get("payload", {})
        value = _number(payload.get("price") or payload.get("value") or payload.get("priceEstimate") or payload.get("estimate"))
        raw_comps = _first_list(payload, ["comparables", "comps", "saleComps", "salesComparables"])
        sold_comps = [normalize_sold_comp(item) for item in raw_comps]
        sold_comps = [item for item in sold_comps if item.get("sold_price", 0) > 0]
        enriched["rentcast_arv"] = value
        enriched["rentcast_sold_comps"] = sold_comps
        enriched["rentcast_sold_comp_count"] = len(sold_comps)
        if value > 0 and not _number(enriched.get("arv")):
            enriched["arv"] = value
        enriched["arv_source"] = "RentCast sold comps" if len(sold_comps) >= 3 else "RentCast AVM only" if value > 0 else enriched.get("arv_source", "Missing")
        enriched["arv_confidence"] = "Strong" if len(sold_comps) >= 3 else "AVM only" if value > 0 else "Not enough data"

    enriched["rentcast_status"] = "Complete" if enriched.get("rent") or enriched.get("rentcast_arv") else "No usable data"
    return enriched
