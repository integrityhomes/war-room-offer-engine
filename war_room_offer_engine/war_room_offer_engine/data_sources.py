from __future__ import annotations

import os
import re
import pandas as pd
import requests


def get_secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st
        value = st.secrets.get(name, default)
        return str(value).strip() if value is not None else default
    except Exception:
        return str(os.environ.get(name, default)).strip()


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
        " north ": " n ",
        " south ": " s ",
        " east ": " e ",
        " west ": " w ",
        " decatur illinois ": " decatur il ",
    }

    value = f" {value} "
    for old, new in replacements.items():
        value = value.replace(old, new)

    return re.sub(r"\s+", " ", value).strip()


def money_to_float(value) -> float:
    if value is None:
        return 0.0
    text = str(value)
    text = re.sub(r"[^0-9.]", "", text)
    try:
        return float(text) if text else 0.0
    except Exception:
        return 0.0


def first_existing_column(df: pd.DataFrame, possible_names: list[str]) -> str | None:
    lower_map = {str(c).strip().lower(): c for c in df.columns}
    for name in possible_names:
        found = lower_map.get(name.lower())
        if found is not None:
            return found
    return None


def read_csv_url(url: str) -> pd.DataFrame:
    if not url or not str(url).strip():
        return pd.DataFrame()

    try:
        return pd.read_csv(str(url).strip())
    except Exception:
        return pd.DataFrame()


def lookup_google_sheet_csv(address: str, secret_name: str, label: str) -> dict:
    url = get_secret(secret_name, "")
    df = read_csv_url(url)

    if df.empty:
        return {"source": label, "found": False, "notes": f"No CSV loaded for {secret_name}."}

    address_col = first_existing_column(
        df,
        [
            "Property_Address",
            "Address",
            "Full_Address",
            "Street_Address",
            "Property Address",
            "Opening_Message",
            "Follow_Up_Message",
        ],
    )

    if not address_col:
        return {"source": label, "found": False, "notes": "No usable address/message column found."}

    target = normalize_address(address)

    df["_norm_address"] = df[address_col].astype(str).map(normalize_address)

    matches = df[df["_norm_address"].str.contains(target, na=False, regex=False)]

    if matches.empty:
        street_only = " ".join(target.split()[:4])
        matches = df[df["_norm_address"].str.contains(street_only, na=False, regex=False)]

    if matches.empty:
        return {"source": label, "found": False, "notes": "No sheet match found."}

    row = matches.iloc[0].to_dict()

    def get_col(possible_names: list[str], default=""):
        col = first_existing_column(df, possible_names)
        return row.get(col, default) if col else default

    asking_price = money_to_float(
        get_col(["Asking_Price", "Price", "Max_Price", "List_Price", "asking price"], 0)
    )

    zillow_link = get_col(["Zillow_Link", "Listing_Url", "Listing_URL", "URL", "Link"], "")
    status = get_col(["Listing_Status", "Status"], "")
    days_on_market = money_to_float(get_col(["Days_On_Market", "DOM"], 0))
    agent_name = get_col(["Agent_Name", "Agent", "Listing_Agent"], "")
    agent_phone = get_col(["Agent_Phone", "Phone"], "")
    brokerage = get_col(["Agent_Brokerage", "Brokerage"], "")
    priority = get_col(["Acq_Priority", "Priority"], "")
    source = get_col(["Source", "Lead_Source"], label)

    return {
        "source": label,
        "found": True,
        "asking_price": asking_price,
        "zillow_link": zillow_link,
        "status": status,
        "days_on_market": days_on_market,
        "agent_name": agent_name,
        "agent_phone": agent_phone,
        "brokerage": brokerage,
        "priority": priority,
        "lead_source": source,
        "matched_address": get_col(["Property_Address", "Address", "Full_Address", "Opening_Message"], ""),
        "notes": f"Matched sheet address: {get_col(['Property_Address', 'Address', 'Full_Address', 'Opening_Message'], '')}",
    }


def lookup_rentcast(address: str) -> dict:
    api_key = get_secret("RENTCAST_API_KEY", "")
    if not api_key:
        return {"source": "RentCast", "found": False, "notes": "Missing RentCast API key."}

    headers = {"X-Api-Key": api_key}

    result = {
        "source": "RentCast",
        "found": False,
        "rent": 0,
        "beds": 0,
        "baths": 0,
        "sqft": 0,
        "arv": 0,
        "year_built": "",
        "property_type": "",
        "notes": "",
    }

    try:
        prop_url = "https://api.rentcast.io/v1/properties"
        prop_resp = requests.get(prop_url, headers=headers, params={"address": address}, timeout=20)

        if prop_resp.status_code == 200:
            data = prop_resp.json()
            if isinstance(data, list) and data:
                p = data[0]
            elif isinstance(data, dict):
                p = data
            else:
                p = {}

            result["found"] = True
            result["beds"] = p.get("bedrooms") or p.get("beds") or 0
            result["baths"] = p.get("bathrooms") or p.get("baths") or 0
            result["sqft"] = p.get("squareFootage") or p.get("sqft") or 0
            result["year_built"] = p.get("yearBuilt") or ""
            result["property_type"] = p.get("propertyType") or ""
            result["arv"] = p.get("price") or p.get("value") or 0

        rent_url = "https://api.rentcast.io/v1/avm/rent/long-term"
        rent_resp = requests.get(rent_url, headers=headers, params={"address": address}, timeout=20)

        if rent_resp.status_code == 200:
            rent_data = rent_resp.json()
            result["found"] = True
            result["rent"] = (
                rent_data.get("rent")
                or rent_data.get("rentEstimate")
                or rent_data.get("price")
                or rent_data.get("value")
                or 0
            )

        result["notes"] = f"Auto-pulled data: Year Built: {result.get('year_built')} | Property Type: {result.get('property_type')}"
        return result

    except Exception as e:
        result["notes"] = f"RentCast lookup error: {e}"
        return result


def merge_results(results: list[dict]) -> dict:
    merged = {
        "address": "",
        "market": "",
        "asking_price": 0,
        "rent": 0,
        "beds": 0,
        "baths": 0,
        "sqft": 0,
        "arv": 0,
        "status": "Unknown",
        "days_on_market": 0,
        "zillow_link": "",
        "agent_name": "",
        "agent_phone": "",
        "brokerage": "",
        "priority": "",
        "lead_source": "",
        "notes": "",
        "sources_found": [],
    }

    notes = []

    for r in results:
        if not r or not r.get("found"):
            if r and r.get("notes"):
                notes.append(r.get("notes"))
            continue

        merged["sources_found"].append(r.get("source", "Unknown"))

        for key in [
            "asking_price",
            "rent",
            "beds",
            "baths",
            "sqft",
            "arv",
            "status",
            "days_on_market",
            "zillow_link",
            "agent_name",
            "agent_phone",
            "brokerage",
            "priority",
            "lead_source",
        ]:
            value = r.get(key)
            if value not in [None, "", 0, 0.0, "Unknown"]:
                merged[key] = value

        if r.get("notes"):
            notes.append(r.get("notes"))

    merged["notes"] = " | ".join(notes)
    return merged


def fetch_all_sources(
    address: str,
    beds: float = 0,
    baths: float = 0,
    sqft: float = 0,
    source_mode: str = "Zillow / Sheet Match",
    lead_source: str = "Zillow / Apify",
    include_listing_sheet: bool = True,
    include_lead_sheet: bool = False,
    **kwargs,
) -> list[dict]:
    """
    Pulls property data from RentCast and optional Google Sheet feeds.

    This function is intentionally flexible so app.py will not crash
    if older/newer versions send extra arguments like beds, baths, sqft,
    source_mode, lead_source, include_listing_sheet, or include_lead_sheet.
    """

    results = []

    # Always try RentCast first
    results.append(lookup_rentcast(address))

    # Zillow / Master Feed lookup
    if include_listing_sheet:
        results.append(
            lookup_google_sheet_csv(
                address,
                "APIFY_ZILLOW_SHEET_CSV_URL",
                "Master Feed CSV",
            )
        )

    # Optional lead sheet lookup. Safe to leave off for now.
    if include_lead_sheet:
        results.append(
            lookup_google_sheet_csv(
                address,
                "LEADS_SHEET_CSV_URL",
                "Lead Sheet CSV",
            )
        )

    return results

    results.append(lookup_rentcast(address))

    if source_mode == "Zillow / Sheet Match" and include_listing_sheet:
        results.append(
            lookup_google_sheet_csv(
                address,
                "APIFY_ZILLOW_SHEET_CSV_URL",
                "Master Feed CSV",
            )
        )

    if include_lead_sheet:
        results.append(
            lookup_google_sheet_csv(
                address,
                "LEADS_SHEET_CSV_URL",
                "Lead Sheet CSV",
            )
        )

    return results
