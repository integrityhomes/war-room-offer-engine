from __future__ import annotations

from typing import Any

try:
    from rentcast_intelligence_core import (
        _clean_text, _haversine_miles, _is_subject_property, _normalize_address,
        _number, _optional_number, _same_property_type,
    )
    from rentcast_recorded_sales_scoring import _score_label
except ImportError:
    try:
        from .rentcast_intelligence_core import (
            _clean_text, _haversine_miles, _is_subject_property, _normalize_address,
            _number, _optional_number, _same_property_type,
        )
        from .rentcast_recorded_sales_scoring import _score_label
    except ImportError:
        from war_room_offer_engine.rentcast_intelligence_core import (
            _clean_text, _haversine_miles, _is_subject_property, _normalize_address,
            _number, _optional_number, _same_property_type,
        )
        from war_room_offer_engine.rentcast_recorded_sales_scoring import _score_label


def _score_rent_comp(comp: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    row = dict(comp)
    flags: list[str] = []
    critical = False
    points = 78
    if _is_subject_property(subject.get("address", ""), row.get("address", "")):
        flags.append("subject property removed from rental comps")
        critical = True
    rent_value = _number(row.get("rent"))
    if rent_value <= 0:
        flags.append("missing listed rent")
        critical = True
    if not _same_property_type(subject.get("property_type"), row.get("property_type")):
        flags.append("different property type")
        critical = True
    else:
        points += 5

    distance = _optional_number(row.get("distance"))
    if distance is None or distance == 0:
        calculated = _haversine_miles(
            subject.get("latitude"), subject.get("longitude"), row.get("latitude"), row.get("longitude")
        )
        if calculated is not None:
            distance = calculated
            row["distance"] = calculated
    if distance is None:
        flags.append("rental comp distance could not be verified")
        points -= 15
    elif distance > 50:
        flags.append("rental comp is more than 50 miles away")
        critical = True
    elif distance <= 5:
        points += 10
    elif distance <= 10:
        points += 4
    elif distance <= 25:
        points -= 8
    else:
        points -= 18

    subject_sqft = _number(subject.get("sqft"))
    comp_sqft = _number(row.get("sqft"))
    sqft_delta = None
    if subject_sqft > 0 and comp_sqft > 0:
        sqft_delta = abs(comp_sqft - subject_sqft) / subject_sqft
        if sqft_delta > 0.65:
            flags.append("rental comp square footage differs by more than 65%")
            critical = True
        elif sqft_delta <= 0.15:
            points += 8
        elif sqft_delta <= 0.30:
            points += 3
        elif sqft_delta > 0.45:
            points -= 10
    elif subject_sqft > 0:
        flags.append("rental comp square footage is missing")
        points -= 12

    subject_beds, comp_beds = _number(subject.get("beds")), _number(row.get("beds"))
    subject_baths, comp_baths = _number(subject.get("baths")), _number(row.get("baths"))
    if subject_beds and comp_beds:
        delta = abs(subject_beds - comp_beds)
        points += 4 if delta == 0 else 0 if delta <= 1 else -10
        if delta > 1:
            flags.append("rental bedroom count differs materially")
    if subject_baths and comp_baths:
        delta = abs(subject_baths - comp_baths)
        points += 3 if delta <= 0.5 else 0 if delta <= 1 else -8
        if delta > 1:
            flags.append("rental bathroom count differs materially")

    status = _clean_text(row.get("status")).lower()
    if status == "active":
        points += 5
    elif status == "inactive":
        flags.append("historical inactive rental listing")
        points -= 8

    days = int(_number(row.get("days_old"))) if _number(row.get("days_old")) else None
    if days is not None:
        if days <= 90:
            points += 6
        elif days <= 270:
            points += 2
        elif days <= 540:
            points -= 4
        elif days <= 1095:
            points -= 12
        else:
            flags.append("rental listing is older than three years")
            critical = True

    correlation = _number(row.get("correlation"))
    if correlation >= 0.90:
        points += 8
    elif correlation >= 0.80:
        points += 4
    elif correlation and correlation < 0.60:
        flags.append("low RentCast similarity correlation")
        points -= 10

    points = max(0, min(int(points), 100))
    score = _score_label(points, critical)
    return {
        **row, "score": score, "score_points": points, "flags": sorted(set(flags)),
        "sqft_delta_pct": round(sqft_delta * 100, 1) if sqft_delta is not None else None,
        "include_default": not critical and score != "Bad Comp",
    }


def _dedupe_rent_comps(comps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows = []
    for comp in comps:
        identity = _clean_text(comp.get("id")) or _normalize_address(comp.get("address"))
        if not identity or identity in seen:
            continue
        seen.add(identity)
        rows.append(comp)
    return rows
