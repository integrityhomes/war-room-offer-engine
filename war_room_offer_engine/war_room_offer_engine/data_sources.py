from __future__ import annotations

import os
import re
from typing import Any

import pandas as pd
import requests

try:
    from apify_connector import fetch_dataset_items, normalize_zillow_record, parse_apify_dataset_id, preview_rows, run_actor_for_items
except ImportError:
    try:
        from .apify_connector import fetch_dataset_items, normalize_zillow_record, parse_apify_dataset_id, preview_rows, run_actor_for_items
    except ImportError:
        try:
            from war_room_offer_engine.apify_connector import fetch_dataset_items, normalize_zillow_record, parse_apify_dataset_id, preview_rows, run_actor_for_items
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.apify_connector import fetch_dataset_items, normalize_zillow_record, parse_apify_dataset_id, preview_rows, run_actor_for_items

try:
    from sold_comps import normalize_sold_comps, parse_comp_text
except ImportError:
    try:
        from .sold_comps import normalize_sold_comps, parse_comp_text
    except ImportError:
        try:
            from war_room_offer_engine.sold_comps import normalize_sold_comps, parse_comp_text
        except ImportError:
            from war_room_offer_engine.war_room_offer_engine.sold_comps import normalize_sold_comps, parse_comp_text


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


def money_to_float(value: Any) -> float:
    if value is None:
        return 0.0

    text = str(value)
    text = re.sub(r"[^0-9.]", "", text)

    try:
        return float(text) if text else 0.0
    except Exception:
        return 0.0


def parse_listing_text(text: str) -> dict[str, Any]:
    text = str(text or "")
    compact = re.sub(r"\s+", " ", text).strip()

    def find_money(patterns: list[str]) -> float:
        for pattern in patterns:
            match = re.search(pattern, compact, re.IGNORECASE)
            if match:
                return money_to_float(match.group(1))
        return 0.0

    def find_number(patterns: list[str]) -> float:
        for pattern in patterns:
            match = re.search(pattern, compact, re.IGNORECASE)
            if match:
                return money_to_float(match.group(1))
        return 0.0

    parsed = {
        "address": "",
        "city": "",
        "state": "",
        "zip": "",
        "asking_price": find_money([r"(?:price|list price|asking)[:\s$]+([\d,]+)", r"\$([\d,]{4,})"]),
        "beds": find_number([r"(\d+(?:\.\d+)?)\s*(?:beds?|bedrooms?)"]),
        "baths": find_number([r"(\d+(?:\.\d+)?)\s*(?:baths?|bathrooms?)"]),
        "sqft": find_number([r"([\d,]+)\s*(?:sq\.?\s*ft|square feet|sqft)"]),
        "lot_size": "",
        "year_built": "",
        "property_type": "",
        "days_on_market": find_number([r"(\d+)\s*(?:days on market|dom)"]),
        "listing_status": "",
        "agent_name": "",
        "agent_phone": "",
        "agent_email": "",
        "listing_brokerage": "",
        "tax_assessed_value": find_money([r"(?:assessed value|tax assessed value)[:\s$]+([\d,]+)"]),
        "annual_taxes": find_money([r"(?:annual taxes|taxes)[:\s$]+([\d,]+)"]),
        "last_sale_date": "",
        "last_sale_price": find_money([r"(?:last sale price|sold for)[:\s$]+([\d,]+)"]),
        "owner_name": "",
        "rent_estimate": find_money([r"(?:rent estimate|estimated rent|rent)[:\s$]+([\d,]+)"]),
        "arv_estimate": find_money([r"(?:arv|value estimate|estimated value)[:\s$]+([\d,]+)"]),
        "comp_source": "",
    }

    address_match = re.search(
        r"(\d{1,6}\s+[A-Za-z0-9 .'-]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|Boulevard|Blvd|Place|Pl))",
        compact,
        re.IGNORECASE,
    )
    if address_match:
        parsed["address"] = address_match.group(1).strip()

    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", compact)
    if email_match:
        parsed["agent_email"] = email_match.group(0)

    phone_match = re.search(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", compact)
    if phone_match:
        parsed["agent_phone"] = phone_match.group(0)

    year_match = re.search(r"(?:year built|built)[:\s]+(18\d{2}|19\d{2}|20\d{2})", compact, re.IGNORECASE)
    if year_match:
        parsed["year_built"] = year_match.group(1)

    return parsed


def _api_not_connected(provider: str, secret_name: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "connected": bool(get_secret(secret_name, "")),
        "message": "API connected." if get_secret(secret_name, "") else "API not connected - using manual data only.",
    }


def provider_connection_status() -> list[dict[str, Any]]:
    return [
        _api_not_connected("RentCast", "RENTCAST_API_KEY"),
        _api_not_connected("Apify Zillow", "APIFY_TOKEN"),
        _api_not_connected("Regrid", "REGRID_API_KEY"),
        _api_not_connected("ATTOM", "ATTOM_API_KEY"),
    ]


def get_property_details(address: str) -> dict[str, Any]:
    if get_secret("RENTCAST_API_KEY", ""):
        return lookup_rentcast(address)
    return {"found": False, "source": "Property Details Provider", "notes": "API not connected - using manual data only."}


def get_tax_info(address: str) -> dict[str, Any]:
    if get_secret("REGRID_API_KEY", "") or get_secret("ATTOM_API_KEY", ""):
        return {"found": False, "source": "Tax Provider", "notes": "Provider interface ready. API-specific implementation pending."}
    return {"found": False, "source": "Tax Provider", "notes": "API not connected - using manual data only."}


def get_sold_comps(address: str, radius_miles: float = 1.0, limit: int = 20) -> dict[str, Any]:
    if get_secret("RENTCAST_API_KEY", ""):
        return lookup_rentcast_sold_comps(address, radius_miles=radius_miles, limit=limit)
    if get_secret("ATTOM_API_KEY", ""):
        return {"found": False, "source": "Sold Comps Provider", "notes": "Future provider interface ready. ATTOM sold comps not wired yet."}
    return {"found": False, "source": "Sold Comps Provider", "notes": "API not connected - using manual data only."}


def get_rent_comps(address: str) -> dict[str, Any]:
    if get_secret("RENTCAST_API_KEY", ""):
        return lookup_rentcast(address)
    return {"found": False, "source": "Rent Comps Provider", "notes": "API not connected - using manual data only."}


def get_listing_details(url_or_text: str) -> dict[str, Any]:
    parsed = parse_listing_text(url_or_text)
    return {
        "found": any(value not in ["", 0, 0.0] for value in parsed.values()),
        "source": "Manual Listing Text",
        "notes": "Parsed from pasted/manual listing text. Missing fields need manual entry.",
        "data": parsed,
    }


def fetch_apify_zillow_dataset(dataset_id: str, limit: int = 50) -> dict[str, Any]:
    token = get_secret("APIFY_TOKEN", "") or get_secret("APIFY_API_TOKEN", "")
    parsed_dataset_id = parse_apify_dataset_id(dataset_id)
    return fetch_dataset_items(dataset_id=parsed_dataset_id, token=token, limit=limit)


def run_apify_zillow_actor(actor_id: str, actor_input: dict[str, Any] | None = None, limit: int = 50) -> dict[str, Any]:
    token = get_secret("APIFY_TOKEN", "") or get_secret("APIFY_API_TOKEN", "")
    return run_actor_for_items(actor_id=actor_id, actor_input=actor_input or {}, token=token, limit=limit)


def apify_zillow_result_from_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_zillow_record(record)
    data = normalized.get("data", {})
    return {
        "source": "Apify Zillow",
        "found": normalized.get("ok", False),
        **data,
        "zillow_link": data.get("zillow_link", data.get("listing_url", "")),
        "arv_source": "Zillow/Apify Sheet" if data.get("arv") else "",
        "field_sources": normalized.get("field_sources", {}),
        "apify_warnings": normalized.get("warnings", []),
        "apify_errors": normalized.get("errors", []),
        "notes": "Imported from Apify/Zillow normalized record.",
    }


def sold_comps_from_apify_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for row in rows or []:
        data = row.get("data", row) if isinstance(row, dict) else {}
        if not isinstance(data, dict):
            continue
        status = str(data.get("status", "") or "").lower()
        has_sold_data = data.get("sold_price") or data.get("sold_date") or "sold" in status
        if has_sold_data:
            records.append(data)
    return normalize_sold_comps(records, source="Apify/Zillow")


def sold_comps_from_csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return normalize_sold_comps(rows, source="CSV")


def sold_comps_from_pasted_text(text: str) -> list[dict[str, Any]]:
    return parse_comp_text(text, source="Pasted text")


def lookup_rentcast_sold_comps(address: str, radius_miles: float = 1.0, limit: int = 20) -> dict[str, Any]:
    api_key = get_secret("RENTCAST_API_KEY", "")
    if not api_key:
        return {"found": False, "source": "RentCast Sold Comps", "notes": "Missing RentCast API key."}
    headers = {"X-Api-Key": api_key}
    try:
        response = requests.get(
            "https://api.rentcast.io/v1/avm/value",
            headers=headers,
            params={"address": address, "compCount": limit, "radius": radius_miles},
            timeout=25,
        )
    except Exception as exc:
        return {"found": False, "source": "RentCast Sold Comps", "notes": f"RentCast sold comps lookup error: {exc}"}

    if response.status_code < 200 or response.status_code >= 300:
        return {"found": False, "source": "RentCast Sold Comps", "notes": f"RentCast sold comps HTTP {response.status_code}: {response.text[:200]}"}
    try:
        data = response.json()
    except Exception:
        return {"found": False, "source": "RentCast Sold Comps", "notes": "RentCast sold comps returned non-JSON data."}

    candidates = []
    for key in ["comparables", "comps", "saleComps", "salesComparables"]:
        value = data.get(key)
        if isinstance(value, list):
            candidates = value
            break
    comps = normalize_sold_comps(candidates, source="RentCast")
    return {
        "found": bool(comps),
        "source": "RentCast Sold Comps",
        "comps": comps,
        "notes": f"Loaded {len(comps)} RentCast sold comp(s)." if comps else "RentCast value endpoint returned no sold comps.",
    }


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


def extract_latest_tax_amount(property_taxes: Any) -> float:
    if not property_taxes:
        return 0.0

    candidates: list[tuple[int, float]] = []

    if isinstance(property_taxes, dict):
        for year_key, tax_value in property_taxes.items():
            year = 0
            try:
                year = int(re.sub(r"[^0-9]", "", str(year_key))[:4])
            except Exception:
                year = 0

            if isinstance(tax_value, dict):
                amount = 0.0
                for key in [
                    "total",
                    "amount",
                    "tax",
                    "taxes",
                    "taxAmount",
                    "propertyTax",
                    "propertyTaxes",
                    "value",
                ]:
                    amount = money_to_float(tax_value.get(key))
                    if amount > 0:
                        break
            else:
                amount = money_to_float(tax_value)

            if amount > 0:
                candidates.append((year, amount))

    if isinstance(property_taxes, list):
        for item in property_taxes:
            if not isinstance(item, dict):
                amount = money_to_float(item)
                if amount > 0:
                    candidates.append((0, amount))
                continue

            year = 0
            for year_key in ["year", "taxYear"]:
                try:
                    year = int(item.get(year_key, 0) or 0)
                    if year:
                        break
                except Exception:
                    year = 0

            amount = 0.0
            for key in [
                "total",
                "amount",
                "tax",
                "taxes",
                "taxAmount",
                "propertyTax",
                "propertyTaxes",
                "value",
            ]:
                amount = money_to_float(item.get(key))
                if amount > 0:
                    break

            if amount > 0:
                candidates.append((year, amount))

    if not candidates:
        return 0.0

    candidates.sort(key=lambda x: x[0])
    return float(candidates[-1][1])


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

    rent = money_to_float(
        get_col(["Rent", "Rent_Estimate", "RC_Rent_Estimate", "RC_Rent_Clean"], 0)
    )

    arv = money_to_float(
        get_col(["ARV", "Estimated_Value", "Value", "RC_Value", "RentCast_Value"], 0)
    )

    taxes = money_to_float(
        get_col(["Annual_Taxes", "Taxes", "Property_Taxes", "Tax_Amount", "Annual Tax"], 0)
    )

    beds = money_to_float(get_col(["Beds", "Bedrooms", "RC_Beds"], 0))
    baths = money_to_float(get_col(["Baths", "Bathrooms", "RC_Baths"], 0))
    sqft = money_to_float(get_col(["Sqft", "Sq_Ft", "Square_Feet", "RC_Sqft"], 0))

    zillow_link = get_col(["Zillow_Link", "Listing_Url", "Listing_URL", "URL", "Link"], "")
    status = get_col(["Listing_Status", "Status"], "")
    days_on_market = money_to_float(get_col(["Days_On_Market", "DOM"], 0))
    agent_name = get_col(["Agent_Name", "Agent", "Listing_Agent"], "")
    agent_phone = get_col(["Agent_Phone", "Phone"], "")
    brokerage = get_col(["Agent_Brokerage", "Brokerage"], "")
    priority = get_col(["Acq_Priority", "Priority"], "")
    source = get_col(["Source", "Lead_Source"], label)

    matched_address = get_col(
        ["Property_Address", "Address", "Full_Address", "Opening_Message"],
        "",
    )

    return {
        "source": label,
        "found": True,
        "asking_price": asking_price,
        "rent": rent,
        "beds": beds,
        "baths": baths,
        "sqft": sqft,
        "arv": arv,
        "arv_source": "Zillow/Apify Sheet" if arv > 0 else "",
        "taxes": taxes,
        "zillow_link": zillow_link,
        "listing_url": zillow_link,
        "status": status,
        "days_on_market": days_on_market,
        "agent_name": agent_name,
        "agent_phone": agent_phone,
        "brokerage": brokerage,
        "priority": priority,
        "lead_source": source,
        "matched_address": matched_address,
        "matched_sheet_address": matched_address,
        "notes": f"Matched sheet address: {matched_address}",
    }


def lookup_rentcast(
    address: str,
    beds: float = 0,
    baths: float = 0,
    sqft: float = 0,
) -> dict:
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
        "arv_source": "",
        "taxes": 0,
        "year_built": "",
        "property_type": "",
        "notes": "",
    }

    try:
        prop_resp = requests.get(
            "https://api.rentcast.io/v1/properties",
            headers=headers,
            params={"address": address},
            timeout=20,
        )

        if prop_resp.status_code == 200:
            data = prop_resp.json()

            if isinstance(data, list) and data:
                p = data[0]
            elif isinstance(data, dict):
                p = data
            else:
                p = {}

            if p:
                result["found"] = True
                result["beds"] = p.get("bedrooms") or p.get("beds") or 0
                result["baths"] = p.get("bathrooms") or p.get("baths") or 0
                result["sqft"] = p.get("squareFootage") or p.get("sqft") or 0
                result["year_built"] = p.get("yearBuilt") or ""
                result["property_type"] = p.get("propertyType") or ""
                result["taxes"] = extract_latest_tax_amount(p.get("propertyTaxes"))

        avm_params = {"address": address}

        if beds:
            avm_params["bedrooms"] = beds
        if baths:
            avm_params["bathrooms"] = baths
        if sqft:
            avm_params["squareFootage"] = sqft

        rent_resp = requests.get(
            "https://api.rentcast.io/v1/avm/rent/long-term",
            headers=headers,
            params=avm_params,
            timeout=20,
        )

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

            subject = rent_data.get("subjectProperty") or {}
            if subject:
                result["beds"] = result["beds"] or subject.get("bedrooms") or 0
                result["baths"] = result["baths"] or subject.get("bathrooms") or 0
                result["sqft"] = result["sqft"] or subject.get("squareFootage") or 0
                result["property_type"] = result["property_type"] or subject.get("propertyType") or ""
                result["year_built"] = result["year_built"] or subject.get("yearBuilt") or ""

        value_resp = requests.get(
            "https://api.rentcast.io/v1/avm/value",
            headers=headers,
            params=avm_params,
            timeout=20,
        )

        if value_resp.status_code == 200:
            value_data = value_resp.json()
            result["found"] = True
            result["arv"] = (
                value_data.get("price")
                or value_data.get("value")
                or value_data.get("valueEstimate")
                or value_data.get("estimatedValue")
                or 0
            )
            if result["arv"]:
                result["arv_source"] = "RentCast"

            subject = value_data.get("subjectProperty") or {}
            if subject:
                result["beds"] = result["beds"] or subject.get("bedrooms") or 0
                result["baths"] = result["baths"] or subject.get("bathrooms") or 0
                result["sqft"] = result["sqft"] or subject.get("squareFootage") or 0
                result["property_type"] = result["property_type"] or subject.get("propertyType") or ""
                result["year_built"] = result["year_built"] or subject.get("yearBuilt") or ""

        note_parts = []
        if result.get("year_built"):
            note_parts.append(f"Year Built: {result['year_built']}")
        if result.get("property_type"):
            note_parts.append(f"Property Type: {result['property_type']}")
        if result.get("taxes"):
            note_parts.append(f"Annual Taxes: {result['taxes']}")
        if result.get("arv"):
            note_parts.append(f"ARV: {result['arv']}")
        if result.get("rent"):
            note_parts.append(f"Rent: {result['rent']}")

        result["notes"] = "Auto-pulled data: " + " | ".join(note_parts) if note_parts else "RentCast checked."

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
        "taxes": 0,
        "arv": 0,
        "arv_source": "Missing",
        "rentcast_arv": 0,
        "sheet_arv": 0,
        "status": "Unknown",
        "days_on_market": 0,
        "zillow_link": "",
        "listing_url": "",
        "agent_name": "",
        "agent_phone": "",
        "brokerage": "",
        "priority": "",
        "lead_source": "",
        "year_built": "",
        "property_type": "",
        "matched_sheet_address": "",
        "notes": "",
        "sources_found": [],
    }

    notes = []

    for r in results:
        if not r or not isinstance(r, dict):
            continue

        if not r.get("found"):
            if r.get("notes"):
                notes.append(r.get("notes"))
            continue

        merged["sources_found"].append(r.get("source", "Unknown"))
        source_name = str(r.get("source", ""))
        arv_value = r.get("arv")
        if arv_value not in [None, "", 0, 0.0]:
            if source_name == "RentCast":
                merged["rentcast_arv"] = arv_value
            elif source_name in ["Master Feed CSV", "Lead Sheet CSV", "Apify Zillow"]:
                merged["sheet_arv"] = arv_value

        for key in [
            "asking_price",
            "rent",
            "beds",
            "baths",
            "sqft",
            "taxes",
            "arv",
            "arv_source",
            "status",
            "days_on_market",
            "zillow_link",
            "listing_url",
            "agent_name",
            "agent_phone",
            "brokerage",
            "priority",
            "lead_source",
            "year_built",
            "property_type",
            "matched_sheet_address",
        ]:
            value = r.get(key)

            if value not in [None, "", 0, 0.0, "Unknown"]:
                merged[key] = value

        if r.get("notes"):
            notes.append(r.get("notes"))

    merged["notes"] = " | ".join(notes)

    if merged.get("rentcast_arv"):
        merged["arv"] = merged["rentcast_arv"]
        merged["arv_source"] = "RentCast"
    elif merged.get("sheet_arv"):
        merged["arv"] = merged["sheet_arv"]
        merged["arv_source"] = "Zillow/Apify Sheet"
    elif not merged.get("arv"):
        merged["arv_source"] = "Missing"

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
    results = []

    results.append(
        lookup_rentcast(
            address,
            beds=beds,
            baths=baths,
            sqft=sqft,
        )
    )

    if include_listing_sheet:
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
