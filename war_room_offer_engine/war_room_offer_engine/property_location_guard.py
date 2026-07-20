from __future__ import annotations

import re
from typing import Any


STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

_STREET_ALIASES = {
    "street": "st",
    "avenue": "ave",
    "road": "rd",
    "drive": "dr",
    "lane": "ln",
    "court": "ct",
    "boulevard": "blvd",
    "place": "pl",
    "parkway": "pkwy",
    "highway": "hwy",
    "terrace": "ter",
    "circle": "cir",
    "trail": "trl",
    "way": "way",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
    "apartment": "apt",
    "suite": "ste",
    "unit": "unit",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).lower()).strip()


def _normalized_street(value: Any) -> str:
    tokens = _normalized(value).split()
    return " ".join(_STREET_ALIASES.get(token, token) for token in tokens)


def is_listing_url(value: Any) -> bool:
    text = _text(value).lower()
    return text.startswith("http://") or text.startswith("https://") or "www." in text


def parse_property_input(value: Any) -> dict[str, Any]:
    """Parse enough location information to prevent ambiguous paid lookups.

    A listing URL is accepted because the listing source can supply a full address.
    A plain address must include a street number and either:
    - city plus two-letter state; or
    - a five-digit ZIP code.
    """
    raw = _text(value)
    result: dict[str, Any] = {
        "raw": raw,
        "is_url": is_listing_url(raw),
        "street": "",
        "city": "",
        "state": "",
        "zip": "",
        "complete": False,
        "message": "",
    }
    if not raw:
        result["message"] = "Enter a property address or listing URL."
        return result
    if result["is_url"]:
        result["complete"] = True
        return result

    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", raw)
    if zip_match:
        result["zip"] = zip_match.group(1)

    state_match = None
    for match in re.finditer(r"\b([A-Za-z]{2})\b", raw):
        candidate = match.group(1).upper()
        if candidate in STATE_CODES:
            state_match = match
    if state_match:
        result["state"] = state_match.group(1).upper()

    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if parts:
        result["street"] = parts[0]
    else:
        street = raw
        if zip_match:
            street = street[: zip_match.start()].strip(" ,")
        if state_match and state_match.start() < len(street):
            street = street[: state_match.start()].strip(" ,")
        result["street"] = street

    if len(parts) >= 3:
        result["city"] = parts[-2]
    elif len(parts) == 2 and result["state"]:
        second = re.sub(
            rf"\b{re.escape(result['state'])}\b.*$",
            "",
            parts[1],
            flags=re.IGNORECASE,
        ).strip(" ,")
        result["city"] = second

    has_street_number = bool(re.search(r"^\s*\d+[A-Za-z0-9-]*\s+\S+", result["street"]))
    has_city_state = bool(_normalized(result["city"]) and result["state"])
    has_zip = bool(result["zip"])
    result["complete"] = bool(has_street_number and (has_city_state or has_zip))
    if not result["complete"]:
        result["message"] = (
            "Enter the complete property location before using paid data: street, city, state, and preferably ZIP. "
            "Example: 404 4th St, Montgomery, AL 36110."
        )
    return result


def validate_property_input(value: Any) -> tuple[bool, str]:
    parsed = parse_property_input(value)
    return bool(parsed.get("complete")), _text(parsed.get("message"))


def validate_resolved_location(
    requested: Any,
    resolved: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Verify that a returned property record is the requested property."""
    parsed = parse_property_input(requested)
    if parsed.get("is_url"):
        return True, ""
    if not parsed.get("complete"):
        return False, _text(parsed.get("message"))
    resolved = resolved if isinstance(resolved, dict) else {}

    expected_street = _normalized_street(parsed.get("street"))
    resolved_street_value = " ".join(
        part for part in [
            _text(resolved.get("address")),
            _text(resolved.get("address_line_2")),
        ] if part
    )
    resolved_street = _normalized_street(resolved_street_value)
    resolved_state = _text(resolved.get("state")).upper()
    resolved_zip = re.sub(r"\D", "", _text(resolved.get("zip")))[:5]
    resolved_city = _normalized(resolved.get("city"))
    expected_state = _text(parsed.get("state")).upper()
    expected_zip = _text(parsed.get("zip"))[:5]
    expected_city = _normalized(parsed.get("city"))

    mismatches: list[str] = []
    if expected_street and resolved_street and expected_street != resolved_street:
        mismatches.append(
            f"street {resolved_street_value or 'unavailable'} instead of {parsed.get('street')}"
        )
    elif expected_street and not resolved_street:
        mismatches.append("street address unavailable in the returned subject record")
    if expected_state and resolved_state and expected_state != resolved_state:
        mismatches.append(f"state {resolved_state} instead of {expected_state}")
    if expected_zip and resolved_zip and expected_zip != resolved_zip:
        mismatches.append(f"ZIP {resolved_zip} instead of {expected_zip}")
    if expected_city and resolved_city and expected_city != resolved_city:
        mismatches.append(f"city {resolved.get('city')} instead of {parsed.get('city')}")

    if mismatches:
        resolved_address = _text(resolved.get("formatted_address")) or ", ".join(
            part for part in [
                resolved_street_value,
                _text(resolved.get("city")),
                _text(resolved.get("state")),
                _text(resolved.get("zip")),
            ] if part
        )
        return False, (
            "RentCast resolved the request to a different property or location"
            + (f" ({resolved_address})" if resolved_address else "")
            + ": "
            + "; ".join(mismatches)
            + ". No rent, ARV, or comparable evidence was accepted."
        )

    if not resolved_state and not resolved_zip and not resolved_city:
        return False, (
            "RentCast did not return enough subject-location information to verify the property. "
            "No rent, ARV, or comparable evidence was accepted."
        )
    return True, ""


def invalid_location_result(address: Any, message: str) -> dict[str, Any]:
    """Safe empty result used when a subject address is incomplete or mismatched."""
    return {
        "source": "RentCast",
        "found": False,
        "address": _text(address),
        "rent": 0,
        "rent_estimate": 0,
        "rent_source": "Missing / location not verified",
        "rent_confidence": "Missing",
        "rent_verification_needed": "Yes",
        "rent_requires_human_verification": True,
        "rent_verification_reasons": [message],
        "rent_comps": [],
        "rent_comp_count": 0,
        "verified_rent_comp_count": 0,
        "arv": 0,
        "rentcast_arv": 0,
        "arv_source": "Missing / location not verified",
        "arv_confidence": "Not enough data",
        "arv_requires_human_verification": True,
        "arv_verification_reasons": [message],
        "rentcast_sold_comps": [],
        "rentcast_sold_comp_count": 0,
        "verified_sold_comp_count": 0,
        "auto_sold_comps": [],
        "auto_comp_count": 0,
        "auto_arv_summary": {},
        "auto_recommended_arv": 0,
        "location_verification_failed": True,
        "location_verification_error": message,
        "rentcast_property_error": message,
        "notes": message,
    }
