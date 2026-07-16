from __future__ import annotations

from typing import Any

try:
    from rentcast_intelligence_core import (
        _canonical_property_type, _clean_text, _days_old, _haversine_miles,
        _iso_date, _number, _optional_number, _sale_from_record,
    )
except ImportError:
    try:
        from .rentcast_intelligence_core import (
            _canonical_property_type, _clean_text, _days_old, _haversine_miles,
            _iso_date, _number, _optional_number, _sale_from_record,
        )
    except ImportError:
        from war_room_offer_engine.rentcast_intelligence_core import (
            _canonical_property_type, _clean_text, _days_old, _haversine_miles,
            _iso_date, _number, _optional_number, _sale_from_record,
        )


def normalize_rent_comp_intelligent(item: dict[str, Any]) -> dict[str, Any]:
    listed_date = _iso_date(item.get("listedDate"))
    last_seen = _iso_date(item.get("lastSeenDate"))
    days_old = int(_number(item.get("daysOld"))) if _number(item.get("daysOld")) else _days_old(last_seen or listed_date)
    return {
        "id": _clean_text(item.get("id")),
        "address": _clean_text(item.get("formattedAddress") or item.get("address") or item.get("streetAddress")),
        "city": _clean_text(item.get("city")),
        "state": _clean_text(item.get("state")),
        "zip": _clean_text(item.get("zipCode") or item.get("zip")),
        "county": _clean_text(item.get("county")),
        "latitude": _optional_number(item.get("latitude")),
        "longitude": _optional_number(item.get("longitude")),
        "property_type": _canonical_property_type(item.get("propertyType") or item.get("homeType")),
        "beds": _number(item.get("bedrooms") or item.get("beds")),
        "baths": _number(item.get("bathrooms") or item.get("baths")),
        "sqft": _number(item.get("squareFootage") or item.get("sqft") or item.get("livingArea")),
        "lot_size": _number(item.get("lotSize")),
        "year_built": int(_number(item.get("yearBuilt"))) if _number(item.get("yearBuilt")) else 0,
        "rent": _number(item.get("rent") or item.get("price") or item.get("listedRent")),
        "distance": _number(item.get("distance") or item.get("distanceMiles")),
        "status": _clean_text(item.get("status")),
        "listing_type": _clean_text(item.get("listingType")),
        "listed_date": listed_date,
        "removed_date": _iso_date(item.get("removedDate")),
        "last_seen_date": last_seen,
        "days_on_market": int(_number(item.get("daysOnMarket"))) if _number(item.get("daysOnMarket")) else 0,
        "days_old": days_old if days_old is not None else 0,
        "correlation": _number(item.get("correlation")),
        "source": "RentCast Rental Listing",
        "record_type": "rental_listing",
    }


def normalize_value_listing(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean_text(item.get("id")),
        "comp_address": _clean_text(item.get("formattedAddress") or item.get("address") or item.get("streetAddress")),
        "listing_price": _number(item.get("price") or item.get("listedPrice")),
        "sold_price": _number(item.get("price") or item.get("listedPrice")),
        "sold_date": "",
        "beds": _number(item.get("bedrooms") or item.get("beds")),
        "baths": _number(item.get("bathrooms") or item.get("baths")),
        "square_feet": _number(item.get("squareFootage") or item.get("sqft") or item.get("livingArea")),
        "lot_size": _number(item.get("lotSize")),
        "year_built": int(_number(item.get("yearBuilt"))) if _number(item.get("yearBuilt")) else 0,
        "distance_miles": _number(item.get("distance") or item.get("distanceMiles")),
        "property_type": _canonical_property_type(item.get("propertyType") or item.get("homeType")),
        "status": _clean_text(item.get("status")),
        "listing_type": _clean_text(item.get("listingType")),
        "listed_date": _iso_date(item.get("listedDate")),
        "removed_date": _iso_date(item.get("removedDate")),
        "last_seen_date": _iso_date(item.get("lastSeenDate")),
        "days_on_market": int(_number(item.get("daysOnMarket"))) if _number(item.get("daysOnMarket")) else 0,
        "days_old": int(_number(item.get("daysOld"))) if _number(item.get("daysOld")) else 0,
        "correlation": _number(item.get("correlation")),
        "latitude": _optional_number(item.get("latitude")),
        "longitude": _optional_number(item.get("longitude")),
        "zip": _clean_text(item.get("zipCode") or item.get("zip")),
        "county": _clean_text(item.get("county")),
        "source": "RentCast Value Listing",
        "confidence": "Listing evidence only",
        "record_type": "sale_listing",
        "notes": "Comparable listing price; not a confirmed closed-sale price.",
        "listing_url": _clean_text(item.get("listingUrl") or item.get("url")),
    }


def _subject_from_data(data: dict[str, Any], full_address: str = "") -> dict[str, Any]:
    return {
        "address": full_address or _clean_text(data.get("formatted_address") or data.get("address")),
        "city": _clean_text(data.get("city")),
        "state": _clean_text(data.get("state")),
        "zip": _clean_text(data.get("zip") or data.get("zipCode")),
        "county": _clean_text(data.get("county")),
        "latitude": _optional_number(data.get("latitude")),
        "longitude": _optional_number(data.get("longitude")),
        "property_type": _canonical_property_type(data.get("property_type") or data.get("propertyType")),
        "beds": _number(data.get("beds") or data.get("bedrooms")),
        "baths": _number(data.get("baths") or data.get("bathrooms")),
        "sqft": _number(data.get("sqft") or data.get("squareFootage")),
        "lot_size": _number(data.get("lot_size") or data.get("lotSize")),
        "year_built": int(_number(data.get("year_built") or data.get("yearBuilt"))) if _number(data.get("year_built") or data.get("yearBuilt")) else 0,
        "subdivision": _clean_text(data.get("subdivision")),
    }


def normalize_recorded_sale(item: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    if item.get("record_type") == "recorded_sale" or item.get("source") == "RentCast Recorded Sale":
        row = dict(item)
        if not row.get("distance_miles"):
            row["distance_miles"] = _haversine_miles(
                subject.get("latitude"), subject.get("longitude"), row.get("latitude"), row.get("longitude")
            )
        return row
    price, sold_date = _sale_from_record(item)
    distance = _haversine_miles(
        subject.get("latitude"), subject.get("longitude"), item.get("latitude"), item.get("longitude")
    )
    sqft = _number(item.get("squareFootage") or item.get("sqft") or item.get("square_feet"))
    return {
        "id": _clean_text(item.get("id")),
        "assessor_id": _clean_text(item.get("assessorID") or item.get("assessor_id")),
        "comp_address": _clean_text(item.get("formattedAddress") or item.get("comp_address") or item.get("address")),
        "city": _clean_text(item.get("city")),
        "state": _clean_text(item.get("state")),
        "zip": _clean_text(item.get("zipCode") or item.get("zip")),
        "county": _clean_text(item.get("county")),
        "latitude": _optional_number(item.get("latitude")),
        "longitude": _optional_number(item.get("longitude")),
        "sold_price": price or _number(item.get("sold_price")),
        "sold_date": sold_date or _iso_date(item.get("sold_date")),
        "beds": _number(item.get("bedrooms") or item.get("beds")),
        "baths": _number(item.get("bathrooms") or item.get("baths")),
        "square_feet": sqft,
        "lot_size": _number(item.get("lotSize") or item.get("lot_size")),
        "year_built": int(_number(item.get("yearBuilt") or item.get("year_built"))) if _number(item.get("yearBuilt") or item.get("year_built")) else 0,
        "property_type": _canonical_property_type(item.get("propertyType") or item.get("property_type")),
        "subdivision": _clean_text(item.get("subdivision")),
        "distance_miles": distance if distance is not None else _optional_number(item.get("distance_miles")),
        "price_per_sqft": price / sqft if price > 0 and sqft > 0 else 0,
        "source": "RentCast Recorded Sale",
        "confidence": "Public-record sale",
        "record_type": "recorded_sale",
        "notes": "Public-record sale date and price from RentCast property data.",
        "listing_url": "",
    }
