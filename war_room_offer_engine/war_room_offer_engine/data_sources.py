from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st


RENTCAST_BASE_URL = "https://api.rentcast.io/v1"


@dataclass
class SourceResult:
    source: str
    ok: bool
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    raw: Any = None


def get_secret(name: str, default: str = "") -> str:
    """Read from Streamlit secrets first, then environment variables."""
    try:
        value = st.secrets.get(name, default)  # type: ignore[attr-defined]
        if value is None:
            return default
        return str(value)
    except Exception:
        return os.getenv(name, default)


def normalize_address(value: str) -> str:
    if not value:
        return ""
    v = value.lower().strip()
    v = re.sub(r"[^a-z0-9 ]+", " ", v)
    v = re.sub(r"\s+", " ", v)
    replacements = {
        " street ": " st ",
        " avenue ": " ave ",
        " road ": " rd ",
        " drive ": " dr ",
        " boulevard ": " blvd ",
        " lane ": " ln ",
        " court ": " ct ",
        " place ": " pl ",
        " north ": " n ",
        " south ": " s ",
        " east ": " e ",
        " west ": " w ",
    }
    v = f" {v} "
    for old, new in replacements.items():
        v = v.replace(old, new)
    return re.sub(r"\s+", " ", v).strip()


def clean_money(value: Any) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    text = re.sub(r"[^0-9.\-]", "", text)
    try:
        return float(text)
    except Exception:
        return 0.0


def first_number(*values: Any) -> float:
    for value in values:
        num = clean_money(value)
        if num > 0:
            return num
    return 0.0


def first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def deep_get(obj: Any, *keys: str) -> Any:
    cur = obj
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def rentcast_get(endpoint: str, params: Dict[str, Any]) -> Tuple[bool, str, Any]:
    api_key = get_secret("RENTCAST_API_KEY")
    if not api_key:
        return False, "Missing RENTCAST_API_KEY in Streamlit secrets.", None

    headers = {
        "Accept": "application/json",
        "X-Api-Key": api_key,
    }
    url = f"{RENTCAST_BASE_URL}{endpoint}"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code == 401:
            return False, "RentCast auth failed. Check RENTCAST_API_KEY.", None
        if response.status_code >= 400:
            return False, f"RentCast error {response.status_code}: {response.text[:250]}", None
        return True, "OK", response.json()
    except Exception as exc:
        return False, f"RentCast request failed: {exc}", None


def extract_property_record(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, list):
        record = raw[0] if raw else {}
    elif isinstance(raw, dict) and isinstance(raw.get("properties"), list):
        record = raw["properties"][0] if raw["properties"] else {}
    elif isinstance(raw, dict):
        record = raw
    else:
        record = {}

    taxes = first_number(
        record.get("propertyTaxes"),
        record.get("taxAmount"),
        deep_get(record, "taxAssessments", "2025", "taxAmount"),
        deep_get(record, "taxAssessments", "2024", "taxAmount"),
        deep_get(record, "taxAssessments", "2023", "taxAmount"),
    )

    city = first_text(record.get("city"), deep_get(record, "address", "city"))
    state = first_text(record.get("state"), deep_get(record, "address", "state"))
    market = " ".join(x for x in [city, state] if x)

    return {
        "beds": first_number(record.get("bedrooms"), record.get("beds")),
        "baths": first_number(record.get("bathrooms"), record.get("baths")),
        "sqft": first_number(record.get("squareFootage"), record.get("livingArea"), record.get("buildingArea")),
        "taxes": taxes,
        "year_built": first_number(record.get("yearBuilt")),
        "property_type": first_text(record.get("propertyType")),
        "market": market,
        "rentcast_address": first_text(record.get("formattedAddress"), record.get("addressLine1"), record.get("address")),
    }


def lookup_rentcast(address: str, beds: float = 0, baths: float = 0, sqft: float = 0) -> SourceResult:
    if not address.strip():
        return SourceResult("RentCast", False, "Enter an address first.")

    merged: Dict[str, Any] = {}
    raw_bundle: Dict[str, Any] = {}
    messages: List[str] = []

    ok, msg, raw = rentcast_get("/properties", {"address": address, "limit": 1})
    if ok:
        raw_bundle["property_record"] = raw
        merged.update({k: v for k, v in extract_property_record(raw).items() if v not in [None, "", 0]})
        messages.append("property record")
    else:
        messages.append(msg)

    params: Dict[str, Any] = {"address": address, "compCount": 5, "lookupSubjectAttributes": "true"}
    if beds:
        params["bedrooms"] = beds
    if baths:
        params["bathrooms"] = baths
    if sqft:
        params["squareFootage"] = sqft

    ok_rent, msg_rent, raw_rent = rentcast_get("/avm/rent/long-term", params)
    if ok_rent:
        raw_bundle["rent_estimate"] = raw_rent
        merged["rent"] = first_number(
            raw_rent.get("rent") if isinstance(raw_rent, dict) else None,
            raw_rent.get("price") if isinstance(raw_rent, dict) else None,
            raw_rent.get("value") if isinstance(raw_rent, dict) else None,
        )
        merged["rent_low"] = first_number(raw_rent.get("rentRangeLow") if isinstance(raw_rent, dict) else None)
        merged["rent_high"] = first_number(raw_rent.get("rentRangeHigh") if isinstance(raw_rent, dict) else None)
        messages.append("rent estimate")
    else:
        messages.append(msg_rent)

    ok_value, msg_value, raw_value = rentcast_get("/avm/value", params)
    if ok_value:
        raw_bundle["value_estimate"] = raw_value
        merged["arv"] = first_number(
            raw_value.get("price") if isinstance(raw_value, dict) else None,
            raw_value.get("value") if isinstance(raw_value, dict) else None,
            raw_value.get("avm") if isinstance(raw_value, dict) else None,
        )
        merged["arv_low"] = first_number(raw_value.get("priceRangeLow") if isinstance(raw_value, dict) else None)
        merged["arv_high"] = first_number(raw_value.get("priceRangeHigh") if isinstance(raw_value, dict) else None)
        messages.append("value estimate")
    else:
        messages.append(msg_value)

    ok_any = bool(merged)
    return SourceResult(
        "RentCast",
        ok_any,
        "Pulled " + ", ".join(messages) if ok_any else "; ".join(messages),
        merged,
        raw_bundle,
    )


SHEET_COLUMN_MAP = {
    "asking_price": ["asking_price", "asking price", "price", "list_price", "list price", "zillow_price", "listing price"],
    "rent": ["rent", "rent_estimate", "rent estimate", "market_rent", "rentcast_rent"],
    "arv": ["arv", "value", "zestimate", "zillow estimate", "estimated_value", "avm", "rentcast_value"],
    "beds": ["beds", "bedrooms", "bed"],
    "baths": ["baths", "bathrooms", "bath"],
    "sqft": ["sqft", "sq ft", "square_feet", "square feet", "living_area", "livingarea"],
    "taxes": ["taxes", "annual_taxes", "annual taxes", "property_taxes", "tax amount"],
    "days_on_market": ["days_on_market", "days on market", "dom", "zillow days on zillow"],
    "status": ["status", "listing_status", "listing status"],
    "agent_name": ["agent", "agent_name", "listing_agent", "listing agent"],
    "agent_phone": ["agent_phone", "agent phone", "phone", "listing_agent_phone"],
    "listing_url": ["url", "link", "listing_url", "zillow_url", "zillow link"],
    "market": ["market", "city", "location"],
}


def find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    normalized = {str(c).strip().lower(): c for c in df.columns}
    for cand in candidates:
        if cand in normalized:
            return normalized[cand]
    for col_key, col in normalized.items():
        for cand in candidates:
            if cand in col_key:
                return col
    return None


def extract_sheet_fields(row: pd.Series) -> Dict[str, Any]:
    df = row.to_frame().T
    data: Dict[str, Any] = {}
    for field, candidates in SHEET_COLUMN_MAP.items():
        col = find_column(df, candidates)
        if col is None:
            continue
        value = row[col]
        if field in ["asking_price", "rent", "arv", "beds", "baths", "sqft", "taxes", "days_on_market"]:
            data[field] = first_number(value)
        else:
            data[field] = first_text(value)
    return {k: v for k, v in data.items() if v not in [None, "", 0]}


def lookup_google_sheet_csv(address: str, url_secret_name: str, label: str) -> SourceResult:
    csv_url = get_secret(url_secret_name)
    if not csv_url:
        return SourceResult(label, False, f"Missing {url_secret_name} in Streamlit secrets.")
    try:
        df = pd.read_csv(csv_url)
    except Exception as exc:
        return SourceResult(label, False, f"Could not read CSV URL: {exc}")

    if df.empty:
        return SourceResult(label, False, "Sheet is empty.")

    address_col = find_column(df, ["address", "property address", "property_address", "full_address", "full address", "street"])
    if address_col is None:
        return SourceResult(label, False, "No address column found in sheet.")

    target = normalize_address(address)
    if not target:
        return SourceResult(label, False, "Enter an address first.")

    temp = df.copy()
    temp["__norm_address"] = temp[address_col].astype(str).map(normalize_address)
    exact = temp[temp["__norm_address"] == target]
    if exact.empty:
        # Loose match: match house number + first street word.
        parts = target.split()
        loose_terms = parts[:2] if len(parts) >= 2 else parts
        if loose_terms:
            pattern = " ".join(loose_terms)
            exact = temp[temp["__norm_address"].str.contains(re.escape(pattern), na=False)]

    if exact.empty:
        return SourceResult(label, False, "No matching address found in sheet.")

    row = exact.iloc[0]
    data = extract_sheet_fields(row)
    data["matched_sheet_address"] = first_text(row.get(address_col))
    return SourceResult(label, True, "Matched sheet row.", data, row.to_dict())


def fetch_all_sources(address: str, beds: float = 0, baths: float = 0, sqft: float = 0) -> List[SourceResult]:
    results: List[SourceResult] = []
    results.append(lookup_rentcast(address, beds=beds, baths=baths, sqft=sqft))
    results.append(lookup_google_sheet_csv(address, "APIFY_ZILLOW_SHEET_CSV_URL", "Apify/Zillow Sheet"))
    results.append(lookup_google_sheet_csv(address, "LEADS_SHEET_CSV_URL", "Lead Sheet"))
    return results


def merge_results(results: List[SourceResult]) -> Dict[str, Any]:
    """Merge results. Sheet listing price wins asking price; RentCast wins rent/value/property facts."""
    merged: Dict[str, Any] = {}

    # Lead sheet first, then Apify, then RentCast for base facts.
    for source_name in ["Lead Sheet", "Apify/Zillow Sheet", "RentCast"]:
        for result in results:
            if result.source == source_name and result.ok:
                for key, value in result.data.items():
                    if value not in [None, "", 0]:
                        merged[key] = value

    # Prefer RentCast rent/arv/facts if available.
    for result in results:
        if result.source == "RentCast" and result.ok:
            for key in ["rent", "arv", "beds", "baths", "sqft", "taxes", "market", "year_built", "property_type"]:
                value = result.data.get(key)
                if value not in [None, "", 0]:
                    merged[key] = value

    # Prefer Apify/listing sheet for asking/status/DOM/agent/listing URL.
    for source_name in ["Apify/Zillow Sheet", "Lead Sheet"]:
        for result in results:
            if result.source == source_name and result.ok:
                for key in ["asking_price", "status", "days_on_market", "agent_name", "agent_phone", "listing_url", "matched_sheet_address"]:
                    value = result.data.get(key)
                    if value not in [None, "", 0]:
                        merged[key] = value

    return merged
