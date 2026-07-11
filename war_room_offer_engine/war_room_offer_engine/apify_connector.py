from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

import requests


APIFY_API_BASE = "https://api.apify.com/v2"


FIELD_ALIASES: dict[str, list[str]] = {
    "address": [
        "address",
        "streetAddress",
        "street_address",
        "unformattedAddress",
        "fullAddress",
        "full_address",
        "propertyAddress",
        "property_address",
        "hdpData.homeInfo.streetAddress",
    ],
    "city": ["city", "addressCity", "hdpData.homeInfo.city"],
    "state": ["state", "stateCode", "addressState", "hdpData.homeInfo.state"],
    "zip": ["zip", "zipcode", "postalCode", "addressZipcode", "hdpData.homeInfo.zipcode"],
    "asking_price": [
        "price",
        "unformattedPrice",
        "listPrice",
        "listingPrice",
        "askingPrice",
        "zestimate",
        "hdpData.homeInfo.price",
    ],
    "rent": ["rentZestimate", "rentEstimate", "estimatedRent", "hdpData.homeInfo.rentZestimate"],
    "arv": ["zestimate", "estimatedValue", "homeValue", "hdpData.homeInfo.zestimate"],
    "tax_assessed_value": ["taxAssessedValue", "taxAssessment", "assessedValue", "hdpData.homeInfo.taxAssessedValue"],
    "taxes": ["annualTaxes", "propertyTax", "taxAnnualAmount", "hdpData.homeInfo.taxHistory.0.taxPaid"],
    "last_sale_date": ["lastSoldDate", "lastSaleDate", "dateSold.date", "hdpData.homeInfo.dateSold"],
    "last_sale_price": ["lastSoldPrice", "lastSalePrice", "dateSold.price", "hdpData.homeInfo.lastSoldPrice"],
    "beds": ["beds", "bedrooms", "bedroomsTotal", "hdpData.homeInfo.bedrooms"],
    "baths": ["baths", "bathrooms", "bathroomsTotal", "hdpData.homeInfo.bathrooms"],
    "sqft": ["sqft", "livingArea", "livingAreaValue", "area", "hdpData.homeInfo.livingArea"],
    "lot_size": ["lotSize", "lotAreaValue", "lotAreaString", "hdpData.homeInfo.lotAreaValue"],
    "year_built": ["yearBuilt", "hdpData.homeInfo.yearBuilt"],
    "property_type": ["propertyType", "homeType", "hdpData.homeInfo.homeType"],
    "days_on_market": ["daysOnZillow", "daysOnMarket", "dom", "hdpData.homeInfo.daysOnZillow"],
    "status": ["status", "homeStatus", "listingStatus", "hdpData.homeInfo.homeStatus"],
    "listing_url": ["url", "detailUrl", "hdpUrl", "zillowUrl", "listingUrl"],
    "zpid": ["zpid", "hdpData.homeInfo.zpid"],
    "latitude": ["latitude", "lat", "hdpData.homeInfo.latitude"],
    "longitude": ["longitude", "lng", "lon", "hdpData.homeInfo.longitude"],
    "listing_agent_name": ["agentName", "brokerName", "listingAgent.name", "attributionInfo.agentName"],
    "listing_agent_phone": ["agentPhone", "brokerPhone", "listingAgent.phone", "attributionInfo.agentPhoneNumber"],
    "listing_brokerage": ["brokerageName", "brokerName", "attributionInfo.brokerName"],
    "listing_agent_email": ["agentEmail", "listingAgent.email", "attributionInfo.agentEmail"],
    "source_name": ["sourceName", "source", "provider", "sellerType"],
    "source_confidence": ["sourceConfidence", "confidence", "matchConfidence"],
    "sold_price": ["soldPrice", "lastSoldPrice", "lastSalePrice", "dateSold.price", "hdpData.homeInfo.lastSoldPrice"],
    "sold_date": ["soldDate", "lastSoldDate", "lastSaleDate", "dateSold.date", "hdpData.homeInfo.dateSold"],
    "distance_miles": ["distance", "distanceMiles"],
    "condition": ["condition", "homeCondition"],
}


STANDARD_FIELDS = list(FIELD_ALIASES.keys())


def get_secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, default)
        return str(value).strip() if value is not None else default
    except Exception:
        return str(os.environ.get(name, default)).strip()


def money_to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    if not text.strip():
        return 0.0
    multiplier = 1.0
    if re.search(r"\bm\b|million", text, re.IGNORECASE):
        multiplier = 1_000_000
    elif re.search(r"\bk\b", text, re.IGNORECASE):
        multiplier = 1_000
    cleaned = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(cleaned) * multiplier if cleaned else 0.0
    except Exception:
        return 0.0


def normalize_address(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    replacements = {
        " street ": " st ",
        " avenue ": " ave ",
        " road ": " rd ",
        " drive ": " dr ",
        " court ": " ct ",
        " lane ": " ln ",
        " place ": " pl ",
        " boulevard ": " blvd ",
        " highway ": " hwy ",
        " north ": " n ",
        " south ": " s ",
        " east ": " e ",
        " west ": " w ",
    }
    value = f" {value} "
    for old, new in replacements.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def get_nested_value(record: dict[str, Any], path: str) -> Any:
    current: Any = record
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current.get(part)
    return current


def first_value(record: dict[str, Any], aliases: list[str]) -> tuple[Any, str]:
    lower_keys = {str(key).lower(): key for key in record.keys()}
    for alias in aliases:
        value = get_nested_value(record, alias) if "." in alias else None
        if value not in [None, "", [], {}]:
            return value, alias
        key = lower_keys.get(alias.lower())
        if key is not None and record.get(key) not in [None, "", [], {}]:
            return record.get(key), str(key)
    return None, ""


def build_full_address(data: dict[str, Any]) -> str:
    address = str(data.get("address", "") or "").strip()
    city = str(data.get("city", "") or "").strip()
    state = str(data.get("state", "") or "").strip()
    zip_code = str(data.get("zip", "") or "").strip()
    if "," in address and (city or state):
        return address
    parts = [address]
    city_state = " ".join(part for part in [city, state] if part)
    if zip_code:
        city_state = f"{city_state} {zip_code}".strip()
    if city_state:
        parts.append(city_state)
    return ", ".join(part for part in parts if part)


def normalize_zillow_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"ok": False, "errors": ["Bad dataset item. Expected an object record."], "data": {}, "field_sources": {}}

    data: dict[str, Any] = {}
    field_sources: dict[str, str] = {}
    warnings: list[str] = []
    errors: list[str] = []

    for field_name, aliases in FIELD_ALIASES.items():
        value, source_key = first_value(record, aliases)
        if value in [None, "", [], {}]:
            continue
        field_sources[field_name] = source_key
        if field_name in [
            "asking_price",
            "rent",
            "arv",
            "tax_assessed_value",
            "taxes",
            "last_sale_price",
            "beds",
            "baths",
            "sqft",
            "days_on_market",
            "year_built",
        ]:
            number = money_to_float(value)
            data[field_name] = number if number > 0 else value
        else:
            data[field_name] = str(value).strip()

    if not data.get("address"):
        address_bits = [
            data.get("address"),
            record.get("streetAddress"),
            record.get("street"),
            record.get("streetName"),
        ]
        data["address"] = next((str(bit).strip() for bit in address_bits if bit), "")

    full_address = build_full_address(data)
    if full_address:
        data["address"] = full_address

    if data.get("listing_url") and str(data["listing_url"]).startswith("/"):
        data["listing_url"] = "https://www.zillow.com" + str(data["listing_url"])
    data["zillow_link"] = data.get("listing_url", "")

    if not str(data.get("address", "")).strip():
        errors.append("Missing address")
    if money_to_float(data.get("asking_price", 0)) <= 0:
        errors.append("Missing price")

    known_source_keys = {source for source in field_sources.values() if source}
    weird_keys = sorted(
        str(key)
        for key in record.keys()
        if str(key) not in known_source_keys and not isinstance(record.get(key), (dict, list))
    )
    if not field_sources:
        errors.append("Weird field names. No standard Zillow/Apify fields were recognized.")
    elif len(field_sources) < 3 and weird_keys:
        warnings.append("Weird field names. Only a few standard fields were recognized.")

    normalized_address = normalize_address(str(data.get("address", "")))
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "data": data,
        "field_sources": field_sources,
        "duplicate_key": normalized_address,
        "raw_keys": sorted(str(key) for key in record.keys()),
    }


def dedupe_normalized_records(rows: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    unique = []
    duplicates = []
    for row in rows:
        key = row.get("duplicate_key") or normalize_address(row.get("data", {}).get("address", ""))
        if key and key in seen:
            duplicates.append(row)
            continue
        if key:
            seen.add(key)
        unique.append(row)
    return {"rows": unique, "duplicates": duplicates}


def normalize_zillow_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [normalize_zillow_record(record) for record in records if isinstance(record, dict)]
    deduped = dedupe_normalized_records(normalized)
    return {
        "ok": bool(deduped["rows"]),
        "rows": deduped["rows"],
        "duplicates": deduped["duplicates"],
        "errors": [] if deduped["rows"] else ["Empty results"],
    }


def fetch_dataset_items(dataset_id: str, token: str, limit: int = 50) -> dict[str, Any]:
    if not token:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Missing Apify token"}
    if not dataset_id:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Bad dataset. Dataset id is required."}

    try:
        response = requests.get(
            f"{APIFY_API_BASE}/datasets/{dataset_id}/items",
            params={"token": token, "clean": "true", "format": "json", "limit": max(int(limit or 50), 1)},
            timeout=30,
        )
    except Exception as exc:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": f"Apify request failed: {exc}"}

    if response.status_code in [401, 403]:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Missing token or token does not have access to this dataset."}
    if response.status_code == 404:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Bad dataset. Dataset was not found."}
    if response.status_code < 200 or response.status_code >= 300:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": f"Bad dataset response HTTP {response.status_code}: {response.text[:250]}"}

    try:
        items = response.json()
    except Exception:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": f"Bad dataset. Non-JSON response: {response.text[:250]}"}

    if not isinstance(items, list) or not items:
        return {"ok": False, "source": "Apify Zillow Dataset", "error": "Empty results"}

    normalized = normalize_zillow_records(items)
    normalized.update(
        {
            "source": "Apify Zillow Dataset",
            "dataset_id": dataset_id,
            "pulled_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return normalized


def run_actor_for_items(actor_id: str, actor_input: dict[str, Any], token: str, limit: int = 50) -> dict[str, Any]:
    if not token:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Missing Apify token"}
    if not actor_id:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Actor id is required."}

    try:
        response = requests.post(
            f"{APIFY_API_BASE}/acts/{actor_id}/run-sync-get-dataset-items",
            params={"token": token, "clean": "true", "format": "json", "limit": max(int(limit or 50), 1)},
            json=actor_input or {},
            timeout=120,
        )
    except Exception as exc:
        return {"ok": False, "source": "Apify Zillow Actor", "error": f"Apify actor request failed: {exc}"}

    if response.status_code in [401, 403]:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Missing token or token cannot run this actor."}
    if response.status_code < 200 or response.status_code >= 300:
        return {"ok": False, "source": "Apify Zillow Actor", "error": f"Actor run failed HTTP {response.status_code}: {response.text[:250]}"}

    try:
        items = response.json()
    except Exception:
        return {"ok": False, "source": "Apify Zillow Actor", "error": f"Actor returned non-JSON response: {response.text[:250]}"}

    if not isinstance(items, list) or not items:
        return {"ok": False, "source": "Apify Zillow Actor", "error": "Empty results"}

    normalized = normalize_zillow_records(items)
    normalized.update(
        {
            "source": "Apify Zillow Actor",
            "actor_id": actor_id,
            "pulled_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    return normalized


def preview_rows(normalized_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(normalized_rows):
        data = row.get("data", {})
        rows.append(
            {
                "row": index,
                "address": data.get("address", ""),
                "price": data.get("asking_price", 0),
                "beds": data.get("beds", ""),
                "baths": data.get("baths", ""),
                "sqft": data.get("sqft", ""),
                "status": data.get("status", ""),
                "url": data.get("listing_url", ""),
                "warnings": "; ".join(row.get("warnings", [])),
                "errors": "; ".join(row.get("errors", [])),
            }
        )
    return rows
