from __future__ import annotations

import copy
import hashlib
import time
from typing import Any

try:
    import data_sources as ds
    import rentcast_auto_enrichment as rentcast
    from rentcast_intelligence_core import (
        CACHE_TTL_SECONDS, PROPERTY_ENDPOINT, _canonical_property_type, _clean_text,
        _is_subject_property, _latest_year_value, _number, _optional_number,
        _sale_from_record,
    )
except ImportError:
    try:
        from . import data_sources as ds
        from . import rentcast_auto_enrichment as rentcast
        from .rentcast_intelligence_core import (
            CACHE_TTL_SECONDS, PROPERTY_ENDPOINT, _canonical_property_type, _clean_text,
            _is_subject_property, _latest_year_value, _number, _optional_number,
            _sale_from_record,
        )
    except ImportError:
        from war_room_offer_engine import data_sources as ds
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine.rentcast_intelligence_core import (
            CACHE_TTL_SECONDS, PROPERTY_ENDPOINT, _canonical_property_type, _clean_text,
            _is_subject_property, _latest_year_value, _number, _optional_number,
            _sale_from_record,
        )


_RESPONSE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def normalize_property_record(record: dict[str, Any]) -> dict[str, Any]:
    taxes, tax_year = _latest_year_value(record.get("propertyTaxes"), "total")
    assessment, assessment_year = _latest_year_value(record.get("taxAssessments"), "value")
    sale_price, sale_date = _sale_from_record(record)
    owner = record.get("owner") if isinstance(record.get("owner"), dict) else {}
    owner_names = owner.get("names") if isinstance(owner.get("names"), list) else []
    features = record.get("features") if isinstance(record.get("features"), dict) else {}
    hoa = record.get("hoa") if isinstance(record.get("hoa"), dict) else {}
    occupied = record.get("ownerOccupied")
    return {
        "rentcast_property_record_id": _clean_text(record.get("id")),
        "formatted_address": _clean_text(record.get("formattedAddress")),
        "address": _clean_text(record.get("addressLine1") or record.get("streetAddress")),
        "address_line_2": _clean_text(record.get("addressLine2")),
        "city": _clean_text(record.get("city")),
        "state": _clean_text(record.get("state")),
        "zip": _clean_text(record.get("zipCode") or record.get("zip")),
        "county": _clean_text(record.get("county")),
        "state_fips": _clean_text(record.get("stateFips")),
        "county_fips": _clean_text(record.get("countyFips")),
        "latitude": _optional_number(record.get("latitude")),
        "longitude": _optional_number(record.get("longitude")),
        "property_type": _canonical_property_type(record.get("propertyType")),
        "beds": _number(record.get("bedrooms") or record.get("beds")),
        "baths": _number(record.get("bathrooms") or record.get("baths")),
        "sqft": _number(record.get("squareFootage") or record.get("sqft")),
        "lot_size": _number(record.get("lotSize")),
        "year_built": int(_number(record.get("yearBuilt"))) if _number(record.get("yearBuilt")) else 0,
        "assessor_id": _clean_text(record.get("assessorID")),
        "legal_description": _clean_text(record.get("legalDescription")),
        "subdivision": _clean_text(record.get("subdivision")),
        "zoning": _clean_text(record.get("zoning")),
        "last_sale_date": sale_date,
        "last_sale_price": sale_price,
        "taxes": taxes,
        "property_tax_year": tax_year,
        "tax_assessed_value": assessment,
        "tax_assessment_year": assessment_year,
        "hoa_fee": _number(hoa.get("fee")),
        "hoa_frequency": "monthly or assessment amount; verify frequency",
        "property_features": copy.deepcopy(features),
        "owner_name": ", ".join(_clean_text(name) for name in owner_names if _clean_text(name)),
        "owner_type": _clean_text(owner.get("type")),
        "owner_occupied": occupied if isinstance(occupied, bool) else None,
        "occupancy": "Owner occupied" if occupied is True else "Non-owner occupied" if occupied is False else "Unknown",
        "source": "RentCast public property record",
    }


def _cache_key(endpoint: str, api_key: str, params: dict[str, Any], session: Any) -> str:
    token = hashlib.sha256(str(api_key or "").encode("utf-8")).hexdigest()[:10]
    serialized = repr(sorted((str(key), str(value)) for key, value in params.items()))
    return f"{id(session)}|{token}|{endpoint}|{serialized}"


def _request_json(endpoint: str, api_key: str, params: dict[str, Any], session: Any = None) -> dict[str, Any]:
    session = session or getattr(rentcast, "requests", None) or getattr(ds, "requests", None)
    key = _cache_key(endpoint, api_key, params, session)
    cached = _RESPONSE_CACHE.get(key)
    if cached and time.time() - cached[0] <= CACHE_TTL_SECONDS:
        result = copy.deepcopy(cached[1])
        result["cache_hit"] = True
        return result
    try:
        response = session.get(
            endpoint,
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
            params=params,
            timeout=30,
        )
    except Exception as exc:
        return {"ok": False, "error": f"RentCast request error: {exc}", "submitted_params": params, "cache_hit": False}
    if response.status_code < 200 or response.status_code >= 300:
        return {
            "ok": False,
            "error": f"RentCast HTTP {response.status_code}: {str(getattr(response, 'text', ''))[:300]}",
            "submitted_params": params,
            "cache_hit": False,
        }
    try:
        payload = response.json()
    except Exception:
        return {"ok": False, "error": "RentCast returned non-JSON data.", "submitted_params": params, "cache_hit": False}
    result = {"ok": True, "payload": payload, "submitted_params": params, "cache_hit": False}
    _RESPONSE_CACHE[key] = (time.time(), copy.deepcopy(result))
    return result


def _avm_get_json(endpoint: str, api_key: str, params: dict[str, Any], session: Any = None) -> dict[str, Any]:
    adjusted = dict(params or {})
    if endpoint in {getattr(rentcast, "RENT_ENDPOINT", ""), getattr(rentcast, "VALUE_ENDPOINT", "")}:
        adjusted["compCount"] = max(int(_number(adjusted.get("compCount")) or 0), 20)
        adjusted.setdefault("maxRadius", 5)
        adjusted.setdefault("daysOld", 270)
        adjusted.setdefault("lookupSubjectAttributes", True)
    result = _request_json(endpoint, api_key, adjusted, session=session)
    payload = result.get("payload")
    if result.get("ok") and not isinstance(payload, dict):
        return {**result, "ok": False, "error": "RentCast AVM returned an invalid response object.", "payload": {}}
    return {**result, "payload": payload if isinstance(payload, dict) else {}}


def _records_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    payload = result.get("payload")
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("records", "properties", "listings", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _lookup_subject_record(address: str, api_key: str, session: Any = None) -> tuple[dict[str, Any], str, bool]:
    result = _request_json(PROPERTY_ENDPOINT, api_key, {"address": address, "limit": 5}, session=session)
    if not result.get("ok"):
        return {}, _clean_text(result.get("error")), bool(result.get("cache_hit"))
    records = _records_from_result(result)
    if not records:
        return {}, "RentCast property lookup returned no matching public record.", bool(result.get("cache_hit"))
    exact = next(
        (row for row in records if _is_subject_property(address, _clean_text(row.get("formattedAddress")))),
        records[0],
    )
    return normalize_property_record(exact), "", bool(result.get("cache_hit"))


def property_facts(address: str, api_key: str) -> tuple[dict[str, Any], str]:
    facts, error, _ = _lookup_subject_record(address, api_key, session=getattr(ds, "requests", None))
    return facts, error
