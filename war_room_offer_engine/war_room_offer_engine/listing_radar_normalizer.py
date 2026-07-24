from __future__ import annotations

import hashlib
import re
from typing import Any

try:
    from listing_radar_schema import (
        CURRENT_HEADERS,
        clean_text,
        first_value,
        listing_key,
        normalize_phone,
        normalize_url,
        number,
        utc_now_iso,
    )
except ImportError:
    try:
        from .listing_radar_schema import (
            CURRENT_HEADERS,
            clean_text,
            first_value,
            listing_key,
            normalize_phone,
            normalize_url,
            number,
            utc_now_iso,
        )
    except ImportError:
        from war_room_offer_engine.listing_radar_schema import (
            CURRENT_HEADERS,
            clean_text,
            first_value,
            listing_key,
            normalize_phone,
            normalize_url,
            number,
            utc_now_iso,
        )


def _photo(record: dict[str, Any]) -> str:
    direct = first_value(record, "primary_photo", "photo_main", "imgSrc", "hdpData.homeInfo.imgSrc")
    if direct:
        return normalize_url(direct)
    photos = first_value(record, "photos", "photo_all", "images", "carouselPhotos")
    if isinstance(photos, list) and photos:
        first = photos[0]
        if isinstance(first, dict):
            first = first_value(first, "url", "imageUrl", "imgSrc", "mixedSources.jpeg.0.url")
        return normalize_url(first)
    if isinstance(photos, str):
        return normalize_url(re.split(r"[|\n]", photos)[0])
    return ""


def normalize_listing(
    record: dict[str, Any],
    *,
    market_id: str = "",
    run_id: str = "",
    observed_at: str = "",
    source: str = "Apify Zillow",
) -> dict[str, Any]:
    record = dict(record or {})
    observed = observed_at or utc_now_iso()
    zpid = clean_text(first_value(record, "zpid", "id", "listingId", "hdpData.homeInfo.zpid"))
    address = clean_text(
        first_value(
            record,
            "address",
            "streetAddress",
            "unformattedAddress",
            "fullAddress",
            "hdpData.homeInfo.streetAddress",
        )
    )
    city = clean_text(first_value(record, "city", "addressCity", "hdpData.homeInfo.city"))
    state = clean_text(first_value(record, "state", "addressState", "stateCode", "hdpData.homeInfo.state")).upper()
    zip_code = re.sub(
        r"\D",
        "",
        clean_text(first_value(record, "zip", "zipcode", "postalCode", "hdpData.homeInfo.zipcode")),
    )[:5]
    url = normalize_url(first_value(record, "url", "detailUrl", "hdpUrl", "listingUrl", "zillowUrl"))
    price = number(first_value(record, "price", "unformattedPrice", "listPrice", "asking_price", "hdpData.homeInfo.price"))
    agent_email = clean_text(
        first_value(record, "agent_email", "agentEmail", "listingAgent.email", "attributionInfo.agentEmail")
    ).lower()
    if agent_email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", agent_email):
        agent_email = ""
    agent_phone_raw = first_value(
        record,
        "agent_phone",
        "agentPhone",
        "listingAgent.phone",
        "attributionInfo.agentPhoneNumber",
    )

    result = {
        "listing_key": listing_key(zpid, address, zip_code, url),
        "zpid": re.sub(r"\D", "", zpid),
        "address": address,
        "city": city,
        "state": state,
        "zip": zip_code,
        "market_id": clean_text(market_id),
        "asking_price": round(price, 2) if price > 0 else 0,
        "original_price": round(price, 2) if price > 0 else 0,
        "price_change": 0,
        "price_change_percent": 0,
        "beds": number(first_value(record, "beds", "bedrooms", "hdpData.homeInfo.bedrooms")),
        "baths": number(first_value(record, "baths", "bathrooms", "hdpData.homeInfo.bathrooms")),
        "sqft": number(first_value(record, "sqft", "livingArea", "int_size", "hdpData.homeInfo.livingArea")),
        "lot_size": clean_text(first_value(record, "lot_size", "lotSize", "lotAreaString", "lotAreaValue")),
        "year_built": int(number(first_value(record, "year_built", "yearBuilt", "hdpData.homeInfo.yearBuilt")) or 0),
        "property_type": clean_text(first_value(record, "property_type", "propertyType", "homeType")),
        "days_on_market": int(number(first_value(record, "days_on_market", "daysOnZillow", "daysOnMarket")) or 0),
        "listing_status": clean_text(first_value(record, "listing_status", "status", "homeStatus")) or "Active",
        "listing_url": url,
        "primary_photo": _photo(record),
        "agent_name": clean_text(first_value(record, "agent_name", "agentName", "listingAgent.name", "attributionInfo.agentName")),
        "agent_email": agent_email,
        "agent_phone": normalize_phone(agent_phone_raw),
        "agent_brokerage": clean_text(first_value(record, "agent_brokerage", "brokerageName", "brokerName", "attributionInfo.brokerName")),
        "contact_source": "Zillow" if agent_email or normalize_phone(agent_phone_raw) else "Missing",
        "contact_verified_at": "",
        "first_seen": observed,
        "last_seen": observed,
        "last_run_id": clean_text(run_id),
        "feed_status": "NEW",
        "data_quality": "",
        "source": clean_text(source) or "Apify Zillow",
    }
    missing = []
    if not result["listing_key"]:
        missing.append("listing identity")
    if not address:
        missing.append("address")
    if not zip_code:
        missing.append("ZIP")
    if price <= 0:
        missing.append("asking price")
    result["data_quality"] = "Complete" if not missing else "Missing: " + ", ".join(missing)
    return {header: result.get(header, "") for header in CURRENT_HEADERS}


def _event_id(key: str, event_type: str, field: str, observed: str) -> str:
    raw = f"{key}|{event_type}|{field}|{observed}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def merge_listing(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    existing = dict(existing or {})
    incoming = dict(incoming or {})
    key = clean_text(incoming.get("listing_key") or existing.get("listing_key"))
    observed = clean_text(incoming.get("last_seen") or utc_now_iso())
    run_id = clean_text(incoming.get("last_run_id"))
    market_id = clean_text(incoming.get("market_id") or existing.get("market_id"))
    source = clean_text(incoming.get("source") or existing.get("source") or "Apify Zillow")
    events: list[dict[str, Any]] = []

    def event(event_type: str, field: str = "", old: Any = "", new: Any = "") -> None:
        events.append(
            {
                "event_id": _event_id(key, event_type, field, observed),
                "listing_key": key,
                "event_type": event_type,
                "field_name": field,
                "old_value": old,
                "new_value": new,
                "market_id": market_id,
                "run_id": run_id,
                "observed_at": observed,
                "source": source,
            }
        )

    if not existing:
        result = {header: incoming.get(header, "") for header in CURRENT_HEADERS}
        result["first_seen"] = incoming.get("first_seen") or observed
        result["last_seen"] = observed
        result["feed_status"] = "NEW"
        event("NEW_LISTING")
        return result, events

    result = dict(existing)
    result.update({"listing_key": key, "last_seen": observed, "last_run_id": run_id, "market_id": market_id, "source": source})
    result["first_seen"] = existing.get("first_seen") or incoming.get("first_seen") or observed
    result["feed_status"] = "UNCHANGED"

    old_price = number(existing.get("asking_price"))
    new_price = number(incoming.get("asking_price"))
    if new_price > 0 and new_price != old_price:
        result["asking_price"] = new_price
        result["original_price"] = number(existing.get("original_price")) or old_price or new_price
        result["price_change"] = new_price - old_price if old_price else 0
        result["price_change_percent"] = round(((new_price - old_price) / old_price) * 100, 2) if old_price else 0
        result["feed_status"] = "PRICE_DROP" if old_price and new_price < old_price else "PRICE_INCREASE"
        event(result["feed_status"], "asking_price", old_price, new_price)

    tracked = {"listing_status", "listing_url", "agent_name", "agent_phone", "agent_email", "agent_brokerage"}
    protected = {"listing_key", "first_seen", "last_seen", "asking_price", "original_price", "price_change", "price_change_percent", "feed_status"}
    for field in CURRENT_HEADERS:
        if field in protected:
            continue
        new_value = incoming.get(field)
        old_value = existing.get(field)
        if new_value in [None, "", [], {}] or new_value == old_value:
            continue
        result[field] = new_value
        if field in tracked:
            event("FIELD_CHANGED", field, old_value, new_value)
            if result["feed_status"] == "UNCHANGED":
                result["feed_status"] = "UPDATED"

    return {header: result.get(header, "") for header in CURRENT_HEADERS}, events
