from __future__ import annotations

import re
from statistics import median
from typing import Any

import requests

try:
    from sold_comps import calculate_arv_from_comps, score_sold_comps
except ImportError:
    try:
        from .sold_comps import calculate_arv_from_comps, score_sold_comps
    except ImportError:
        from war_room_offer_engine.sold_comps import calculate_arv_from_comps, score_sold_comps


RENT_ENDPOINT = "https://api.rentcast.io/v1/avm/rent/long-term"
VALUE_ENDPOINT = "https://api.rentcast.io/v1/avm/value"


AUTO_COMP_SEARCH_STAGES = [
    ("1 mile", "Last 12 months"),
    ("2 miles", "Last 24 months"),
    ("5 miles", "Last 24 months"),
]


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


def _normalize_address(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    replacements = {
        " street ": " st ",
        " avenue ": " ave ",
        " road ": " rd ",
        " drive ": " dr ",
        " lane ": " ln ",
        " court ": " ct ",
        " boulevard ": " blvd ",
        " place ": " pl ",
    }
    text = f" {text} "
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text).strip()


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
        "sold_price": _number(
            item.get("price")
            or item.get("soldPrice")
            or item.get("lastSalePrice")
            or item.get("lastSoldPrice")
        ),
        "sold_date": (
            item.get("saleDate")
            or item.get("soldDate")
            or item.get("lastSaleDate")
            or item.get("lastSoldDate")
            or ""
        ),
        "beds": _number(item.get("bedrooms") or item.get("beds")),
        "baths": _number(item.get("bathrooms") or item.get("baths")),
        "square_feet": _number(item.get("squareFootage") or item.get("sqft") or item.get("livingArea")),
        "distance_miles": _number(item.get("distance") or item.get("distanceMiles")),
        "property_type": item.get("propertyType") or item.get("homeType") or "",
        "listing_url": item.get("listingUrl") or item.get("url") or "",
        "notes": item.get("notes") or item.get("description") or "",
        "source": "RentCast",
        "confidence": "High",
    }


def _comp_subject(data: dict[str, Any], full_address: str) -> dict[str, Any]:
    return {
        "address": full_address,
        "beds": _number(data.get("beds") or data.get("bedrooms")),
        "baths": _number(data.get("baths") or data.get("bathrooms")),
        "sqft": _number(data.get("sqft") or data.get("squareFootage")),
        "property_type": data.get("property_type") or data.get("propertyType") or "",
        "functional_risks": " ".join(
            str(data.get(key, "") or "")
            for key in ["notes", "repair_notes", "manual_repair_notes"]
        ),
    }


def build_sold_comp_intelligence(
    data: dict[str, Any],
    sold_comps: list[dict[str, Any]],
    full_address: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    subject_address = full_address or build_full_address(data)
    subject_key = _normalize_address(subject_address)
    filtered: list[dict[str, Any]] = []
    removed_subject_count = 0

    for comp in sold_comps or []:
        if not isinstance(comp, dict) or _number(comp.get("sold_price")) <= 0:
            continue
        comp_key = _normalize_address(comp.get("comp_address"))
        if subject_key and comp_key and comp_key == subject_key:
            removed_subject_count += 1
            continue
        filtered.append(comp)

    subject = _comp_subject(data, subject_address)
    candidates: list[tuple[list[dict[str, Any]], dict[str, Any], str, str, tuple[int, ...]]] = []

    for stage_index, (radius, date_range) in enumerate(AUTO_COMP_SEARCH_STAGES):
        scored = score_sold_comps(filtered, subject, radius, date_range)
        summary = calculate_arv_from_comps(scored)
        quality_count = int(summary.get("strong_comp_count", 0) or 0) + int(summary.get("good_comp_count", 0) or 0)
        included_count = sum(
            1
            for comp in scored
            if comp.get("include_default", False)
            and comp.get("score") != "Bad Comp"
            and _number(comp.get("sold_price")) > 0
        )
        rank = (
            1 if quality_count >= 3 and _number(summary.get("recommended_arv")) > 0 else 0,
            quality_count,
            int(summary.get("strong_comp_count", 0) or 0),
            included_count,
            1 if _number(summary.get("recommended_arv")) > 0 else 0,
            -stage_index,
        )
        candidates.append((scored, summary, radius, date_range, rank))
        if rank[0] == 1:
            break

    if candidates:
        scored, summary, radius, date_range, _ = max(candidates, key=lambda item: item[4])
    else:
        scored, summary, radius, date_range = [], calculate_arv_from_comps([]), "1 mile", "Last 12 months"

    summary = dict(summary)
    summary.update(
        {
            "search_radius": radius,
            "date_range": date_range,
            "subject_comp_removed_count": removed_subject_count,
            "candidate_comp_count": len(filtered),
            "included_comp_count": sum(
                1
                for comp in scored
                if comp.get("include_default", False)
                and comp.get("score") != "Bad Comp"
                and _number(comp.get("sold_price")) > 0
            ),
        }
    )
    return scored, summary


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
        scored_comps, auto_summary = build_sold_comp_intelligence(enriched, sold_comps, full_address)
        auto_arv = _number(auto_summary.get("recommended_arv"))

        enriched["rentcast_arv"] = value
        enriched["rentcast_sold_comps"] = sold_comps
        enriched["rentcast_sold_comp_count"] = len(sold_comps)
        enriched["auto_sold_comps"] = scored_comps
        enriched["auto_comp_count"] = len(scored_comps)
        enriched["auto_arv_summary"] = auto_summary
        enriched["auto_recommended_arv"] = auto_arv
        enriched["auto_low_arv"] = _number(auto_summary.get("low_arv"))
        enriched["auto_conservative_arv"] = _number(auto_summary.get("conservative_arv"))
        enriched["auto_average_arv"] = _number(auto_summary.get("average_arv"))
        enriched["auto_high_arv"] = _number(auto_summary.get("high_arv"))
        enriched["strong_comp_count"] = int(auto_summary.get("strong_comp_count", 0) or 0)
        enriched["good_comp_count"] = int(auto_summary.get("good_comp_count", 0) or 0)
        enriched["weak_comp_count"] = int(auto_summary.get("weak_comp_count", 0) or 0)
        enriched["excluded_comp_count"] = int(auto_summary.get("excluded_comp_count", 0) or 0)
        enriched["auto_comp_radius"] = auto_summary.get("search_radius", "1 mile")
        enriched["auto_comp_date_range"] = auto_summary.get("date_range", "Last 12 months")

        if auto_arv > 0 and (
            int(auto_summary.get("strong_comp_count", 0) or 0)
            + int(auto_summary.get("good_comp_count", 0) or 0)
        ) > 0:
            enriched["arv"] = auto_arv
            enriched["arv_source"] = "Automatic Sold Comps"
            enriched["arv_confidence"] = auto_summary.get("arv_confidence", "Weak")
        elif value > 0:
            enriched["arv"] = value
            enriched["arv_source"] = "RentCast AVM only"
            enriched["arv_confidence"] = "AVM only"
        else:
            enriched["arv_source"] = enriched.get("arv_source", "Missing")
            enriched["arv_confidence"] = "Not enough data"

    enriched["rentcast_status"] = "Complete" if enriched.get("rent") or enriched.get("rentcast_arv") or enriched.get("auto_recommended_arv") else "No usable data"
    return enriched
