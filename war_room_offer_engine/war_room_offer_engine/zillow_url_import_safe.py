from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

import pandas as pd

try:
    import zillow_url_import as base
except ImportError:
    try:
        from . import zillow_url_import as base
    except ImportError:
        from war_room_offer_engine import zillow_url_import as base


is_zillow_url = base.is_zillow_url
extract_zpid = base.extract_zpid
extract_zip = base.extract_zip
extract_zip_code = base.extract_zip
build_zillow_actor_input = base.build_zillow_actor_input


def _first_nonblank(record: dict[str, Any], *keys: str) -> Any:
    lower = {str(key).strip().lower(): key for key in record.keys()}
    for key in keys:
        actual = lower.get(str(key).strip().lower())
        if actual is not None:
            value = record.get(actual)
            if value not in [None, "", 0, 0.0, [], {}]:
                return value
    return ""


def _money(value: Any) -> float:
    """Convert Zillow/Apify number shapes without ever raising.

    Real actor responses may contain numbers, formatted strings such as
    ``$64,900``, one-item lists, or nested objects such as
    ``{"value": 64900}``.  Scoring and importing must handle all of them.
    """
    if value in [None, "", [], {}] or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        preferred_keys = [
            "value",
            "price",
            "amount",
            "unformattedPrice",
            "listPrice",
            "listingPrice",
            "askingPrice",
            "formattedValue",
            "formatted",
            "text",
        ]
        for key in preferred_keys:
            if key in value:
                number = _money(value.get(key))
                if number > 0:
                    return number
        for nested in value.values():
            number = _money(nested)
            if number > 0:
                return number
        return 0.0
    if isinstance(value, (list, tuple, set)):
        for item in value:
            number = _money(item)
            if number > 0:
                return number
        return 0.0

    text = str(value).strip()
    if not text:
        return 0.0
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return 0.0
    cleaned = match.group(0).replace(",", "")
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return 0.0


def _stop_or_return(result: dict[str, Any]) -> dict[str, Any]:
    """Stop a Streamlit run cleanly; return normally in offline tests."""
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except Exception:
        return result

    if get_script_run_ctx() is not None:
        message = str(result.get("error") or "Zillow data could not be imported.")
        st.error("Zillow import stopped: " + message)
        st.info("No offer was calculated because the subject property data was not verified.")
        st.stop()
    return result


def _address_hint_from_url(listing_url: str) -> str:
    try:
        path = urlsplit(str(listing_url or "")).path
    except Exception:
        path = str(listing_url or "")
    match = re.search(r"/homedetails/([^/]+)/", path, re.IGNORECASE)
    if not match:
        return ""
    slug = match.group(1)
    if slug.endswith("_zpid") and slug[:-5].isdigit():
        return ""
    return slug.replace("-", " ")


def _photo_urls_from_value(value: Any, depth: int = 0) -> list[str]:
    if depth > 7 or value in [None, "", [], {}]:
        return []
    if isinstance(value, str):
        text = value.strip()
        if text.startswith(("[", "{")):
            try:
                return _photo_urls_from_value(json.loads(text), depth + 1)
            except Exception:
                pass
        parts = re.split(r"\s*\|\s*|[\r\n]+|\s*,\s*(?=https?://)", text)
        urls = []
        for part in parts:
            candidate = part.strip().strip('"\'')
            lower = candidate.lower()
            if candidate.startswith(("http://", "https://")) and (
                "zillowstatic.com" in lower
                or "photo" in lower
                or "image" in lower
                or re.search(r"\.(?:jpg|jpeg|png|webp)(?:\?|$)", lower)
            ):
                urls.append(candidate)
        return urls
    if isinstance(value, list):
        urls: list[str] = []
        for item in value[:200]:
            urls.extend(_photo_urls_from_value(item, depth + 1))
        return urls
    if isinstance(value, dict):
        urls: list[str] = []
        for key, item in value.items():
            key_text = str(key).lower()
            if any(token in key_text for token in ["photo", "image", "img", "jpeg", "webp", "url", "src", "mixedsources"]):
                urls.extend(_photo_urls_from_value(item, depth + 1))
        return urls
    return []


def extract_photo_urls(record: dict[str, Any]) -> list[str]:
    fields = [
        "photo_all", "photo_main", "photos", "photoUrls", "images", "imageUrls",
        "carouselPhotos", "responsivePhotos", "miniCardPhotos", "originalPhotos",
        "imgSrc", "media",
    ]
    seen: set[str] = set()
    result: list[str] = []
    for field in fields:
        value = _first_nonblank(record, field)
        for url in _photo_urls_from_value(value):
            if url not in seen:
                seen.add(url)
                result.append(url)
    if not result:
        for url in _photo_urls_from_value(record):
            if url not in seen:
                seen.add(url)
                result.append(url)
    return result[:100]


def _enrich_from_raw(data: dict[str, Any], raw_record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(data or {})
    aliases = {
        "zpid": ("zpid", "id", "listingId"),
        "address": ("address", "streetAddress", "unformattedAddress"),
        "city": ("city", "addressCity"),
        "state": ("state", "addressState", "stateCode"),
        "zip": ("zip", "zipcode", "postalCode"),
        "asking_price": ("price", "unformattedPrice", "listPrice", "listingPrice", "askingPrice"),
        "beds": ("beds", "bedrooms"),
        "baths": ("baths", "bathrooms"),
        "sqft": ("sqft", "int_size", "livingArea", "area"),
        "lot_size": ("lot_size", "lotSize", "lotAreaValue", "lotAreaString"),
        "year_built": ("year_built", "yearBuilt"),
        "property_type": ("property_type", "propertyType", "homeType"),
        "days_on_market": ("days_on_market", "daysOnZillow", "daysOnMarket", "timeOnZillow", "dom"),
        "status": ("status", "homeStatus", "listingStatus"),
        "listing_url": ("url", "detailUrl", "DetailURL", "hdpUrl", "listingUrl", "Zillow_Link"),
        "listing_agent_name": ("listing_agent_name", "agent_name", "agentName", "listedBy"),
        "listing_agent_phone": ("listing_agent_phone", "agent_phone", "agentPhone", "phone"),
        "listing_agent_email": ("listing_agent_email", "agent_email", "agent_emai", "agentEmail"),
        "listing_brokerage": ("listing_brokerage", "agent_brokerage", "brokerageName", "brokerName", "BrokerName"),
        "rent": ("RC_Rent_Clean", "RC_Rent_Estimate", "rent", "rentZestimate", "rentEstimate"),
        "arv": ("zestimate", "estimatedValue", "homeValue", "redfinEstimate", "realtorEstimate", "ARV"),
        "taxes": ("taxes", "annualTaxes", "propertyTaxes"),
        "tax_assessed_value": ("taxAssessedValue", "assessedValue", "taxAssessment"),
        "last_sale_price": ("last_sale_price", "soldPrice", "lastSoldPrice", "lastSalePrice"),
        "last_sale_date": ("last_sale_date", "soldDate", "lastSoldDate", "lastSaleDate"),
    }
    numeric = {
        "asking_price", "beds", "baths", "sqft", "lot_size", "year_built",
        "days_on_market", "rent", "arv", "taxes", "tax_assessed_value", "last_sale_price",
    }

    for target, keys in aliases.items():
        current = enriched.get(target)
        if current in [None, "", 0, 0.0, [], {}]:
            current = _first_nonblank(raw_record, *keys)
        if current in [None, "", 0, 0.0, [], {}]:
            continue
        enriched[target] = _money(current) if target in numeric else current

    photos = extract_photo_urls(raw_record or enriched)
    if photos:
        enriched["listing_photos"] = photos
        enriched["primary_photo"] = photos[0]
    return enriched


def _score_zillow_row(row: dict[str, Any], listing_url: str, address: str = "") -> int:
    data = row.get("data", row) if isinstance(row, dict) else {}
    if not isinstance(data, dict):
        return -100

    score = 0
    target_zpid = base.extract_zpid(listing_url)
    row_zpid = str(data.get("zpid") or base.extract_zpid(str(data.get("listing_url") or "")))
    if target_zpid and row_zpid and target_zpid == row_zpid:
        score += 100

    target_url = base.canonical_url(listing_url)
    row_url = base.canonical_url(str(data.get("listing_url") or data.get("zillow_link") or ""))
    if target_url and row_url:
        if target_url == row_url:
            score += 80
        elif target_url in row_url or row_url in target_url:
            score += 50

    target_address = base.normalize_address(address)
    row_address = base.normalize_address(str(data.get("address") or ""))
    if target_address and row_address:
        if target_address == row_address:
            score += 70
        elif target_address in row_address or row_address in target_address:
            score += 35

    target_zip = base.extract_zip(address, listing_url)
    row_zip = str(data.get("zip") or "")
    if target_zip and row_zip and target_zip == row_zip:
        score += 10

    if row.get("ok", True):
        score += 5
    if _money(data.get("asking_price")) > 0:
        score += 5
    return score


def _strict_match(rows: list[dict[str, Any]], listing_url: str, address: str = "") -> dict[str, Any] | None:
    if not rows:
        return None
    address_hint = address or _address_hint_from_url(listing_url)
    ranked = sorted(rows, key=lambda row: _score_zillow_row(row, listing_url, address_hint), reverse=True)
    best = ranked[0]
    data = best.get("data", best) if isinstance(best, dict) else {}

    target_zpid = base.extract_zpid(listing_url)
    row_zpid = str(data.get("zpid") or base.extract_zpid(str(data.get("listing_url") or "")))
    if target_zpid and row_zpid and target_zpid == row_zpid:
        return best

    target_address = base.normalize_address(address_hint)
    row_address = base.normalize_address(str(data.get("address") or ""))
    if target_address and row_address:
        if target_address == row_address:
            return best
        target_number = re.match(r"\d+", target_address)
        row_number = re.match(r"\d+", row_address)
        if target_number and row_number and target_number.group(0) == row_number.group(0):
            overlap = set(target_address.split()) & set(row_address.split())
            if len(overlap) >= 4:
                return best
    return None


def _sheet_urls() -> list[tuple[str, str]]:
    candidates = [
        ("APIFY_ZILLOW_SHEET_CSV_URL", "Apify Zillow Sheet"),
        ("LEADS_SHEET_CSV_URL", "Leads/Master Feed Sheet"),
        ("MASTER_FEED_CSV_URL", "Master Feed Sheet"),
        ("RAW_FEED_CSV_URL", "Raw Feed Sheet"),
    ]
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for secret_name, label in candidates:
        url = str(base.get_secret(secret_name, "") or "").strip()
        if url and url not in seen:
            seen.add(url)
            result.append((url, label))
    return result


def _row_matches_zillow(row: dict[str, Any], listing_url: str) -> bool:
    target_zpid = base.extract_zpid(listing_url)
    target_url = base.canonical_url(listing_url)
    row_text = json.dumps(row, default=str)
    if target_zpid and target_zpid in row_text:
        return True
    for key in ["url", "listing_url", "Zillow_Link", "zillow_link", "detailUrl", "DetailURL"]:
        value = _first_nonblank(row, key)
        if not value:
            continue
        candidate = base.canonical_url(str(value))
        if target_url and candidate and (target_url == candidate or target_url in candidate or candidate in target_url):
            return True
    return False


def _sheet_fallback(listing_url: str) -> dict[str, Any]:
    errors: list[str] = []
    for csv_url, label in _sheet_urls():
        try:
            df = pd.read_csv(csv_url)
        except Exception as exc:
            errors.append(f"{label} could not be read: {exc}")
            continue
        if df.empty:
            errors.append(f"{label} was empty.")
            continue
        for _, series in df.iterrows():
            row = {str(k): v for k, v in series.to_dict().items()}
            if not _row_matches_zillow(row, listing_url):
                continue
            normalized = base.normalize_zillow_records([row])
            rows = normalized.get("rows", []) or []
            selected = rows[0] if rows else {"ok": True, "data": {}}
            data = _enrich_from_raw(dict(selected.get("data", {}) or {}), row)
            data["listing_url"] = data.get("listing_url") or listing_url
            data["zillow_link"] = data.get("zillow_link") or data["listing_url"]
            missing = [
                field for field in ["address", "asking_price", "beds", "baths", "sqft"]
                if data.get(field) in [None, "", 0, 0.0, [], {}]
            ]
            warnings = []
            if missing:
                warnings.append("Missing from sheet fallback: " + ", ".join(missing))
            return {
                "ok": True,
                "source": label,
                "record": data,
                "selected_row": selected,
                "missing_fields": missing,
                "warnings": warnings,
                "row_count": 1,
                "configured_id": "sheet-fallback",
                "actor_input": {},
            }
    return {
        "ok": False,
        "source": "Google Sheet fallback",
        "error": "No matching Zillow ID or listing URL was found in the configured Google Sheet feeds. " + " | ".join(errors[:3]),
    }


def pull_zillow_listing(listing_url: str, address: str = "", limit: int = 10) -> dict[str, Any]:
    url = str(listing_url or "").strip()
    if not base.is_zillow_url(url):
        return _stop_or_return(
            {
                "ok": False,
                "source": "Apify Zillow Live Pull",
                "error": "Paste a complete Zillow property URL beginning with https://.",
            }
        )

    live_result = base._configured_result(url, address, max(int(limit or 10), 1))
    if live_result.get("ok"):
        rows = live_result.get("rows", []) or []
        selected = _strict_match(rows, url, address)
        if selected is not None:
            data = dict(selected.get("data", {}) or {})
            raw_items = live_result.get("raw_items", []) or []
            raw_record = base._raw_item_for_normalized_row(selected, raw_items) if raw_items else {}
            data = _enrich_from_raw(data, raw_record)
            data["listing_url"] = data.get("listing_url") or url
            data["zillow_link"] = data.get("zillow_link") or data["listing_url"]
            required = ["address", "asking_price", "beds", "baths", "sqft"]
            missing = [field for field in required if data.get(field) in [None, "", 0, 0.0, [], {}]]
            warnings = list(selected.get("warnings", []) or [])
            if missing:
                warnings.append("Missing from Zillow pull: " + ", ".join(missing))
            blocking_missing = [field for field in ["address", "asking_price"] if field in missing]
            if blocking_missing:
                return _stop_or_return(
                    {
                        "ok": False,
                        "source": live_result.get("source", "Apify Zillow Live Pull"),
                        "error": "The property matched, but required fields were missing: " + ", ".join(blocking_missing) + ".",
                        "warnings": warnings,
                    }
                )
            return {
                "ok": True,
                "source": live_result.get("source", "Apify Zillow Live Pull"),
                "record": data,
                "selected_row": selected,
                "missing_fields": missing,
                "warnings": warnings,
                "row_count": len(rows),
                "configured_id": live_result.get("configured_id", ""),
                "actor_input": live_result.get("actor_input", {}),
            }

    sheet_result = _sheet_fallback(url)
    if sheet_result.get("ok"):
        warning = str(live_result.get("error") or "Live Apify pull did not return a safe match.")
        sheet_result.setdefault("warnings", []).append("Live pull unavailable; used Google Sheet fallback. " + warning)
        return sheet_result

    live_error = str(live_result.get("error") or "Live Apify pull did not return a safe property match.")
    sheet_error = str(sheet_result.get("error") or "No sheet fallback match was found.")
    return _stop_or_return(
        {
            "ok": False,
            "source": "Zillow import",
            "error": (
                "Zillow import failed, so analysis was stopped before using default values. "
                f"Live pull: {live_error} Sheet fallback: {sheet_error}"
            ),
        }
    )
