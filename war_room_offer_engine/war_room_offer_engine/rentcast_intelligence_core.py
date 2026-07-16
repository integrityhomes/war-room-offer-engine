from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

try:
    import rentcast_comp_normalization_fix as normalization
except ImportError:
    try:
        from . import rentcast_comp_normalization_fix as normalization
    except ImportError:
        from war_room_offer_engine import rentcast_comp_normalization_fix as normalization


PROPERTY_ENDPOINT = "https://api.rentcast.io/v1/properties"
RENTAL_LISTING_ENDPOINT = "https://api.rentcast.io/v1/listings/rental/long-term"
CACHE_TTL_SECONDS = 6 * 60 * 60
MAX_STORED_COMPS = 25

SOLD_SEARCH_STAGES = (
    {"name": "Local", "radius": 1.0, "days": 365, "sqft_tolerance": 0.25},
    {"name": "Expanded", "radius": 3.0, "days": 730, "sqft_tolerance": 0.35},
    {"name": "Rural", "radius": 10.0, "days": 1095, "sqft_tolerance": 0.45},
    {"name": "Deep rural", "radius": 25.0, "days": 1825, "sqft_tolerance": 0.55},
    {"name": "Remote rural", "radius": 50.0, "days": 2555, "sqft_tolerance": 0.65},
)

INTELLIGENCE_STATE_KEYS = {
    "rentcast_property_record_id", "rentcast_property_record_summary", "rentcast_property_error",
    "rentcast_value_listing_comps", "rentcast_value_listing_comp_count", "rentcast_value_listing_median",
    "verified_sold_comp_count", "arv_price_median", "arv_median_ppsf", "arv_ppsf_estimate",
    "arv_method_disagreement_pct", "arv_search_mode", "arv_search_radius", "arv_search_days",
    "arv_search_trail", "arv_requires_human_verification", "arv_verification_reasons",
    "verified_rent_comp_count", "rentcast_rent_avm", "rent_search_mode", "rent_search_radius",
    "rent_search_days", "rent_search_trail", "rent_requires_human_verification",
    "rent_verification_reasons", "rent_comp_quality_summary", "rural_market_detected",
    "rentcast_data_provenance", "rentcast_request_policy",
}


def _number(value: Any) -> float:
    if value in [None, "", [], {}] or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9.\-]", "", str(value))
    try:
        return float(text) if text else 0.0
    except Exception:
        return 0.0


def _optional_number(value: Any) -> float | None:
    if value in [None, "", [], {}] or isinstance(value, bool):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_address(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    replacements = {
        "street": "st", "avenue": "ave", "road": "rd", "drive": "dr", "lane": "ln",
        "court": "ct", "boulevard": "blvd", "place": "pl", "parkway": "pkwy",
        "highway": "hwy", "terrace": "ter", "circle": "cir", "north": "n",
        "south": "s", "east": "e", "west": "w",
    }
    return " ".join(replacements.get(token, token) for token in text.split())


def _is_subject_property(subject_address: str, comp_address: str) -> bool:
    matcher = getattr(normalization, "_is_subject_comp", None)
    if callable(matcher):
        try:
            return bool(matcher(subject_address, comp_address))
        except Exception:
            pass
    return bool(_normalize_address(subject_address) and _normalize_address(subject_address) == _normalize_address(comp_address))


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean_text(value)
    if not text:
        return None
    text = text[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    return None


def _iso_date(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _days_old(value: Any) -> int | None:
    parsed = _parse_date(value)
    return max((date.today() - parsed).days, 0) if parsed else None


def _round_money(value: Any) -> int:
    number = _number(value)
    return int(number + 0.5) if number > 0 else 0


def _quantile(values: list[float], fraction: float) -> float:
    rows = sorted(float(value) for value in values if _number(value) > 0)
    if not rows:
        return 0.0
    if len(rows) == 1:
        return rows[0]
    position = (len(rows) - 1) * max(0.0, min(float(fraction), 1.0))
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return rows[lower]
    return rows[lower] + (rows[upper] - rows[lower]) * (position - lower)


def _canonical_property_type(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    aliases = {
        "single family": "Single Family", "single family residence": "Single Family",
        "singlefamily": "Single Family", "house": "Single Family",
        "condo": "Condo", "condominium": "Condo", "townhouse": "Townhouse",
        "townhome": "Townhouse", "manufactured": "Manufactured", "mobile home": "Manufactured",
        "multi family": "Multi-Family", "multifamily": "Multi-Family", "duplex": "Multi-Family",
        "triplex": "Multi-Family", "quadplex": "Multi-Family", "apartment": "Apartment",
        "land": "Land", "vacant land": "Land",
    }
    if text in aliases:
        return aliases[text]
    for key, result in aliases.items():
        if key in text:
            return result
    return _clean_text(value)


def _same_property_type(subject_type: Any, comp_type: Any) -> bool:
    subject = _canonical_property_type(subject_type).lower()
    comp = _canonical_property_type(comp_type).lower()
    return not subject or not comp or subject == comp


def _haversine_miles(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> float | None:
    values = [_optional_number(value) for value in (lat1, lon1, lat2, lon2)]
    if any(value is None for value in values):
        return None
    a_lat, a_lon, b_lat, b_lon = [math.radians(float(value)) for value in values]
    d_lat, d_lon = b_lat - a_lat, b_lon - a_lon
    hav = math.sin(d_lat / 2) ** 2 + math.cos(a_lat) * math.cos(b_lat) * math.sin(d_lon / 2) ** 2
    return 3958.7613 * 2 * math.asin(min(1.0, math.sqrt(hav)))


def _latest_year_value(mapping: Any, value_key: str) -> tuple[float, int]:
    if not isinstance(mapping, dict):
        return 0.0, 0
    rows: list[tuple[int, float]] = []
    for key, raw in mapping.items():
        record = raw if isinstance(raw, dict) else {}
        try:
            year = int(record.get("year") or key)
        except Exception:
            continue
        value = _number(record.get(value_key))
        if value > 0:
            rows.append((year, value))
    if not rows:
        return 0.0, 0
    year, value = max(rows)
    return value, year


def _sale_from_record(record: dict[str, Any]) -> tuple[float, str]:
    price = _number(record.get("lastSalePrice") or record.get("lastSoldPrice"))
    sold_date = _iso_date(record.get("lastSaleDate") or record.get("lastSoldDate"))
    if price > 0 and sold_date:
        return price, sold_date
    events: list[tuple[date, float, str]] = []
    history = record.get("history") if isinstance(record.get("history"), dict) else {}
    for raw in history.values():
        event = raw if isinstance(raw, dict) else {}
        if "sale" not in _clean_text(event.get("event")).lower() or "listing" in _clean_text(event.get("event")).lower():
            continue
        event_date = _parse_date(event.get("date"))
        event_price = _number(event.get("price"))
        if event_date and event_price > 0:
            events.append((event_date, event_price, event_date.isoformat()))
    if events:
        _, event_price, event_date = max(events, key=lambda row: row[0])
        return price or event_price, sold_date or event_date
    return price, sold_date
