from __future__ import annotations

from statistics import mean, median
from typing import Any

try:
    import data_sources as base
    from sold_comps import calculate_arv_from_comps, normalize_sold_comps, score_sold_comps
except ImportError:
    try:
        from . import data_sources as base
        from .sold_comps import calculate_arv_from_comps, normalize_sold_comps, score_sold_comps
    except ImportError:
        from war_room_offer_engine import data_sources as base
        from war_room_offer_engine.sold_comps import calculate_arv_from_comps, normalize_sold_comps, score_sold_comps


_ORIGINAL_MERGE_RESULTS = base.merge_results


def _number(value: Any) -> float:
    return base.money_to_float(value)


def _first(record: dict[str, Any], *keys: str) -> Any:
    if not isinstance(record, dict):
        return ""
    lower = {str(key).lower(): key for key in record.keys()}
    for name in keys:
        key = lower.get(name.lower())
        if key is not None and record.get(key) not in [None, "", [], {}]:
            return record.get(key)
    return ""


def _full_comp_address(record: dict[str, Any]) -> str:
    direct = _first(record, "formattedAddress", "fullAddress", "address", "propertyAddress")
    if direct:
        return str(direct).strip()
    street = _first(record, "addressLine1", "streetAddress", "address1")
    city = _first(record, "city")
    state = _first(record, "state")
    zip_code = _first(record, "zipCode", "zipcode", "postalCode", "zip")
    locality = ", ".join(part for part in [str(city or "").strip(), str(state or "").strip()] if part)
    if zip_code:
        locality = f"{locality} {zip_code}".strip()
    return ", ".join(part for part in [str(street or "").strip(), locality] if part)


def _extract_comparable_rows(payload: dict[str, Any], aliases: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    for key in aliases:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_rent_comp(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "address": _full_comp_address(record),
        "beds": _number(_first(record, "bedrooms", "beds")),
        "baths": _number(_first(record, "bathrooms", "baths")),
        "sqft": _number(_first(record, "squareFootage", "sqft", "livingArea", "area")),
        "rent": _number(_first(record, "price", "rent", "rentPrice", "listedRent", "monthlyRent", "amount")),
        "distance_miles": _number(_first(record, "distance", "distanceMiles", "distance_miles")),
        "correlation": _number(_first(record, "correlation", "score", "similarity")),
        "property_type": str(_first(record, "propertyType", "homeType", "type") or ""),
        "listed_date": str(_first(record, "listedDate", "listingDate", "createdDate", "date") or ""),
        "source": "RentCast",
    }


def _safe_secret_number(name: str, default: float) -> float:
    try:
        value = float(base.get_secret(name, str(default)) or default)
        return value
    except Exception:
        return default


def _request_params(address: str, beds: float, baths: float, sqft: float) -> dict[str, Any]:
    params: dict[str, Any] = {
        "address": str(address or "").strip(),
        "compCount": int(max(5, min(_safe_secret_number("RENTCAST_COMP_COUNT", 15), 25))),
        "maxRadius": max(0.5, _safe_secret_number("RENTCAST_MAX_RADIUS", 10)),
        "lookupSubjectAttributes": "true",
    }
    days_old = int(max(1, _safe_secret_number("RENTCAST_DAYS_OLD", 365)))
    params["daysOld"] = days_old
    if beds:
        params["bedrooms"] = beds
    if baths:
        params["bathrooms"] = baths
    if sqft:
        params["squareFootage"] = sqft
    return params


def lookup_rentcast_with_comps(
    address: str,
    beds: float = 0,
    baths: float = 0,
    sqft: float = 0,
) -> dict[str, Any]:
    api_key = base.get_secret("RENTCAST_API_KEY", "")
    submitted_address = str(address or "").strip()
    result: dict[str, Any] = {
        "source": "RentCast",
        "found": False,
        "rent": 0,
        "rent_source": "Missing / RentCast unavailable",
        "rent_confidence": "Weak",
        "beds": 0,
        "baths": 0,
        "sqft": 0,
        "arv": 0,
        "arv_source": "",
        "taxes": 0,
        "year_built": "",
        "property_type": "",
        "rentcast_submitted_address": submitted_address,
        "rentcast_rent_comps": [],
        "rentcast_rent_comp_count": 0,
        "rentcast_rent_comp_average": 0,
        "rentcast_rent_comp_median": 0,
        "rentcast_rent_http_status": 0,
        "rentcast_rent_error": "",
        "rentcast_value_comps": [],
        "rentcast_value_comp_count": 0,
        "rentcast_value_http_status": 0,
        "rentcast_value_error": "",
        "notes": "",
    }
    if not api_key:
        result["rentcast_rent_error"] = "Missing RentCast API key."
        result["rentcast_value_error"] = "Missing RentCast API key."
        result["notes"] = "Missing RentCast API key."
        return result

    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    params = _request_params(submitted_address, beds, baths, sqft)

    try:
        prop_resp = base.requests.get(
            "https://api.rentcast.io/v1/properties",
            headers=headers,
            params={"address": submitted_address},
            timeout=25,
        )
        if prop_resp.status_code == 200:
            prop_data = prop_resp.json()
            if isinstance(prop_data, list) and prop_data:
                prop = prop_data[0]
            elif isinstance(prop_data, dict):
                prop = prop_data
            else:
                prop = {}
            if prop:
                result["found"] = True
                result["beds"] = _number(_first(prop, "bedrooms", "beds"))
                result["baths"] = _number(_first(prop, "bathrooms", "baths"))
                result["sqft"] = _number(_first(prop, "squareFootage", "sqft"))
                result["year_built"] = _first(prop, "yearBuilt") or ""
                result["property_type"] = _first(prop, "propertyType") or ""
                result["taxes"] = base.extract_latest_tax_amount(prop.get("propertyTaxes"))
    except Exception as exc:
        result["property_lookup_error"] = str(exc)

    try:
        rent_resp = base.requests.get(
            "https://api.rentcast.io/v1/avm/rent/long-term",
            headers=headers,
            params=params,
            timeout=30,
        )
        result["rentcast_rent_http_status"] = int(rent_resp.status_code)
        if rent_resp.status_code == 200:
            rent_data = rent_resp.json()
            result["found"] = True
            result["rent"] = _number(_first(rent_data, "rent", "rentEstimate", "price", "value"))
            raw_rent_comps = _extract_comparable_rows(
                rent_data,
                ("comparables", "comps", "rentalComps", "rentComparables", "rentalComparables"),
            )
            rent_comps = [_normalize_rent_comp(item) for item in raw_rent_comps]
            rent_comps = [item for item in rent_comps if item.get("rent", 0) > 0]
            rents = [float(item["rent"]) for item in rent_comps]
            result["rentcast_rent_comps"] = rent_comps
            result["rentcast_rent_comp_count"] = len(rent_comps)
            result["rentcast_rent_comp_average"] = round(mean(rents), 0) if rents else 0
            result["rentcast_rent_comp_median"] = round(median(rents), 0) if rents else 0
            if result["rent"]:
                result["rent_source"] = "RentCast"
                if len(rent_comps) >= 3:
                    result["rent_confidence"] = "Strong verified rent comps"
                elif rent_comps:
                    result["rent_confidence"] = "Medium fallback comps"
                else:
                    result["rent_confidence"] = "Medium fallback comps"
            subject = rent_data.get("subjectProperty") or {}
            if subject:
                result["beds"] = result["beds"] or _number(_first(subject, "bedrooms", "beds"))
                result["baths"] = result["baths"] or _number(_first(subject, "bathrooms", "baths"))
                result["sqft"] = result["sqft"] or _number(_first(subject, "squareFootage", "sqft"))
                result["property_type"] = result["property_type"] or _first(subject, "propertyType") or ""
                result["year_built"] = result["year_built"] or _first(subject, "yearBuilt") or ""
        else:
            result["rentcast_rent_error"] = f"HTTP {rent_resp.status_code}: {rent_resp.text[:300]}"
    except Exception as exc:
        result["rentcast_rent_error"] = str(exc)

    try:
        value_params = dict(params)
        value_params.pop("daysOld", None)
        value_resp = base.requests.get(
            "https://api.rentcast.io/v1/avm/value",
            headers=headers,
            params=value_params,
            timeout=30,
        )
        result["rentcast_value_http_status"] = int(value_resp.status_code)
        if value_resp.status_code == 200:
            value_data = value_resp.json()
            result["found"] = True
            result["arv"] = _number(_first(value_data, "price", "value", "valueEstimate", "estimatedValue"))
            if result["arv"]:
                result["arv_source"] = "RentCast"
            raw_value_comps = _extract_comparable_rows(
                value_data,
                ("comparables", "comps", "saleComps", "salesComparables", "valueComparables"),
            )
            value_comps = normalize_sold_comps(raw_value_comps, source="RentCast")
            result["rentcast_value_comps"] = value_comps
            result["rentcast_value_comp_count"] = len(value_comps)
            subject = value_data.get("subjectProperty") or {}
            if subject:
                result["beds"] = result["beds"] or _number(_first(subject, "bedrooms", "beds"))
                result["baths"] = result["baths"] or _number(_first(subject, "bathrooms", "baths"))
                result["sqft"] = result["sqft"] or _number(_first(subject, "squareFootage", "sqft"))
                result["property_type"] = result["property_type"] or _first(subject, "propertyType") or ""
                result["year_built"] = result["year_built"] or _first(subject, "yearBuilt") or ""
        else:
            result["rentcast_value_error"] = f"HTTP {value_resp.status_code}: {value_resp.text[:300]}"
    except Exception as exc:
        result["rentcast_value_error"] = str(exc)

    note_parts = [f"Submitted address: {submitted_address}"]
    if result.get("rent"):
        note_parts.append(f"Rent: {result['rent']:.0f}")
    note_parts.append(f"Rental comps: {result.get('rentcast_rent_comp_count', 0)}")
    if result.get("arv"):
        note_parts.append(f"Value estimate: {result['arv']:.0f}")
    note_parts.append(f"Sold comps: {result.get('rentcast_value_comp_count', 0)}")
    if result.get("rentcast_rent_error"):
        note_parts.append(f"Rent error: {result['rentcast_rent_error']}")
    if result.get("rentcast_value_error"):
        note_parts.append(f"Value error: {result['rentcast_value_error']}")
    result["notes"] = "RentCast auto-pull | " + " | ".join(note_parts)
    return result


def _store_comp_state(merged: dict[str, Any]) -> None:
    try:
        import streamlit as st
    except Exception:
        return

    for key in [
        "rentcast_submitted_address",
        "rentcast_rent_comps",
        "rentcast_rent_comp_count",
        "rentcast_rent_comp_average",
        "rentcast_rent_comp_median",
        "rentcast_rent_http_status",
        "rentcast_rent_error",
        "rentcast_value_comps",
        "rentcast_value_comp_count",
        "rentcast_value_http_status",
        "rentcast_value_error",
    ]:
        st.session_state[key] = merged.get(key, [] if key.endswith("_comps") else 0 if "count" in key or "status" in key or "average" in key or "median" in key else "")

    rent_comps = merged.get("rentcast_rent_comps", []) or []
    if merged.get("rent", 0) and len(rent_comps) >= 3:
        st.session_state["rent_verification_needed"] = "No"
        st.session_state["rental_demand_confidence"] = "Strong rent comps"

    value_comps = merged.get("rentcast_value_comps", []) or []
    if value_comps:
        subject = {
            "address": merged.get("rentcast_submitted_address", ""),
            "beds": merged.get("beds", 0),
            "baths": merged.get("baths", 0),
            "sqft": merged.get("sqft", 0),
            "property_type": merged.get("property_type", ""),
            "functional_risks": "",
        }
        radius = _safe_secret_number("RENTCAST_MAX_RADIUS", 10)
        scored = score_sold_comps(value_comps, subject, f"{radius:g} miles", "Last 24 months")
        summary = calculate_arv_from_comps(scored)
        st.session_state["auto_sold_comps"] = scored
        st.session_state["auto_arv_summary"] = summary
        st.session_state["auto_comp_count"] = len(scored)
        st.session_state["strong_comp_count"] = int(summary.get("strong_comp_count", 0) or 0)
        st.session_state["good_comp_count"] = int(summary.get("good_comp_count", 0) or 0)
        st.session_state["weak_comp_count"] = int(summary.get("weak_comp_count", 0) or 0)
        st.session_state["excluded_comp_count"] = int(summary.get("excluded_comp_count", 0) or 0)
        st.session_state["auto_low_arv"] = int(summary.get("low_arv", 0) or 0)
        st.session_state["auto_conservative_arv"] = int(summary.get("conservative_arv", 0) or 0)
        st.session_state["auto_average_arv"] = int(summary.get("average_arv", 0) or 0)
        st.session_state["auto_high_arv"] = int(summary.get("high_arv", 0) or 0)
        st.session_state["auto_recommended_arv"] = int(summary.get("recommended_arv", 0) or 0)


def merge_results_with_auto_comps(results: list[dict]) -> dict[str, Any]:
    merged = _ORIGINAL_MERGE_RESULTS(results)
    rentcast = next(
        (
            item
            for item in results or []
            if isinstance(item, dict) and str(item.get("source", "")).lower() == "rentcast"
        ),
        {},
    )
    for key in [
        "rentcast_submitted_address",
        "rentcast_rent_comps",
        "rentcast_rent_comp_count",
        "rentcast_rent_comp_average",
        "rentcast_rent_comp_median",
        "rentcast_rent_http_status",
        "rentcast_rent_error",
        "rentcast_value_comps",
        "rentcast_value_comp_count",
        "rentcast_value_http_status",
        "rentcast_value_error",
    ]:
        merged[key] = rentcast.get(key, [] if key.endswith("_comps") else 0 if "count" in key or "status" in key or "average" in key or "median" in key else "")
    _store_comp_state(merged)
    return merged


base.lookup_rentcast = lookup_rentcast_with_comps
base.merge_results = merge_results_with_auto_comps
