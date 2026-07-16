from __future__ import annotations

from statistics import median
from typing import Any

try:
    from rentcast_intelligence_core import (
        _clean_text, _days_old, _number, _optional_number, _parse_date,
        _same_property_type,
    )
except ImportError:
    try:
        from .rentcast_intelligence_core import (
            _clean_text, _days_old, _number, _optional_number, _parse_date,
            _same_property_type,
        )
    except ImportError:
        from war_room_offer_engine.rentcast_intelligence_core import (
            _clean_text, _days_old, _number, _optional_number, _parse_date,
            _same_property_type,
        )


def _score_label(points: int, critical: bool) -> str:
    if critical or points < 45:
        return "Bad Comp"
    if points >= 88:
        return "Strong Comp"
    if points >= 72:
        return "Good Comp"
    return "Weak Comp"


def _score_recorded_sale(comp: dict[str, Any], subject: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
    flags: list[str] = []
    critical = False
    points = 82
    price = _number(comp.get("sold_price"))
    sold_date = _parse_date(comp.get("sold_date"))
    age = _days_old(comp.get("sold_date"))
    sqft = _number(comp.get("square_feet"))
    subject_sqft = _number(subject.get("sqft"))
    distance = _optional_number(comp.get("distance_miles"))

    if comp.get("record_type") != "recorded_sale" or not _clean_text(comp.get("source")).startswith("RentCast Recorded Sale"):
        flags.append("not a confirmed public-record closed sale")
        critical = True
    if price <= 0:
        flags.append("missing recorded sale price")
        critical = True
    if not sold_date:
        flags.append("missing recorded sale date")
        critical = True
    elif age is not None and age > int(stage["days"]):
        flags.append(f"older than {int(stage['days'])} day search stage")
        critical = True
    elif age is not None:
        if age <= 365:
            points += 10
        elif age <= 730:
            points += 3
        elif age <= 1095:
            points -= 4
        elif age <= 1825:
            points -= 12
        else:
            points -= 20

    if distance is None:
        flags.append("distance could not be verified")
        points -= 18
    elif distance > float(stage["radius"]):
        flags.append(f"outside {stage['radius']:g} mile search stage")
        critical = True
    elif distance <= 1:
        points += 10
    elif distance <= 3:
        points += 5
    elif distance <= 10:
        points -= 2
    elif distance <= 25:
        points -= 12
    else:
        points -= 22

    if not _same_property_type(subject.get("property_type"), comp.get("property_type")):
        flags.append("different property type")
        critical = True
    else:
        points += 5

    sqft_delta = None
    if subject_sqft > 0 and sqft > 0:
        sqft_delta = abs(sqft - subject_sqft) / subject_sqft
        if sqft_delta > float(stage["sqft_tolerance"]):
            flags.append(f"square footage differs by {sqft_delta:.0%}")
            critical = True
        elif sqft_delta <= 0.15:
            points += 8
        elif sqft_delta <= 0.25:
            points += 4
        elif sqft_delta > 0.40:
            points -= 10
    elif subject_sqft > 0:
        flags.append("missing comparable square footage")
        critical = True

    bed_delta = abs(_number(comp.get("beds")) - _number(subject.get("beds"))) if _number(comp.get("beds")) and _number(subject.get("beds")) else None
    bath_delta = abs(_number(comp.get("baths")) - _number(subject.get("baths"))) if _number(comp.get("baths")) and _number(subject.get("baths")) else None
    if bed_delta is not None:
        points += 4 if bed_delta == 0 else 0 if bed_delta <= 1 else -8 if bed_delta <= 2 else -15
        if bed_delta > 1:
            flags.append("bedroom count differs materially")
    if bath_delta is not None:
        points += 3 if bath_delta <= 0.5 else 0 if bath_delta <= 1 else -8
        if bath_delta > 1:
            flags.append("bathroom count differs materially")

    subject_lot = _number(subject.get("lot_size"))
    comp_lot = _number(comp.get("lot_size"))
    lot_delta = None
    if subject_lot >= 43560:
        if comp_lot <= 0:
            flags.append("rural acreage is missing")
            points -= 10
        else:
            lot_delta = abs(comp_lot - subject_lot) / subject_lot
            if max(subject_lot, comp_lot) / max(min(subject_lot, comp_lot), 1) > 10:
                flags.append("acreage differs too much for a rural comp")
                critical = True
            elif lot_delta > 2:
                flags.append("acreage differs materially")
                points -= 14
            elif lot_delta > 0.75:
                points -= 6
            else:
                points += 4

    subject_year = int(_number(subject.get("year_built")))
    comp_year = int(_number(comp.get("year_built")))
    if subject_year and comp_year:
        year_delta = abs(comp_year - subject_year)
        points += 4 if year_delta <= 15 else 0 if year_delta <= 30 else -5 if year_delta <= 50 else -9
        if year_delta > 50:
            flags.append("year built differs materially")

    if _clean_text(subject.get("zip")) and _clean_text(subject.get("zip")) == _clean_text(comp.get("zip")):
        points += 4
    if _clean_text(subject.get("county")) and _clean_text(subject.get("county")).lower() == _clean_text(comp.get("county")).lower():
        points += 4
    if _clean_text(subject.get("subdivision")) and _clean_text(subject.get("subdivision")).lower() == _clean_text(comp.get("subdivision")).lower():
        points += 6

    points = max(0, min(int(points), 100))
    score = _score_label(points, critical)
    return {
        **comp,
        "sale_age_days": age if age is not None else 0,
        "sqft_delta_pct": round(sqft_delta * 100, 1) if sqft_delta is not None else None,
        "lot_delta_pct": round(lot_delta * 100, 1) if lot_delta is not None else None,
        "score": score,
        "score_points": points,
        "flags": sorted(set(flags)),
        "include_default": not critical and score != "Bad Comp",
    }


def _apply_ppsf_outlier_guard(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    included = [row for row in scored if row.get("include_default") and _number(row.get("price_per_sqft")) > 0]
    if len(included) < 3:
        return scored
    center = median(_number(row.get("price_per_sqft")) for row in included)
    deviations = [abs(_number(row.get("price_per_sqft")) - center) for row in included]
    mad = median(deviations) if deviations else 0
    updated = []
    for row in scored:
        ppsf = _number(row.get("price_per_sqft"))
        flags = list(row.get("flags", []) or [])
        points = int(row.get("score_points", 0) or 0)
        include = bool(row.get("include_default"))
        outlier = False
        if include and ppsf > 0:
            if mad > 0:
                outlier = 0.6745 * abs(ppsf - center) / mad > 3.5
            else:
                outlier = ppsf < center * 0.55 or ppsf > center * 1.80
        if outlier:
            flags.append("price per square foot is a robust local outlier")
            points = max(points - 25, 0)
            include = False
        updated.append({**row, "flags": sorted(set(flags)), "score_points": points, "score": _score_label(points, not include), "include_default": include})
    return updated


def _empty_arv_summary(reason: str = "No verified public-record closed sales were found.") -> dict[str, Any]:
    return {
        "low_arv": 0, "conservative_arv": 0, "average_arv": 0, "high_arv": 0,
        "recommended_arv": 0, "arv_confidence": "Not enough data", "strong_comp_count": 0,
        "good_comp_count": 0, "weak_comp_count": 0, "excluded_comp_count": 0,
        "included_comp_count": 0, "verified_sold_comp_count": 0, "price_median": 0,
        "median_price_per_sqft": 0, "ppsf_arv": 0, "method_disagreement_pct": 0,
        "search_mode": "Unavailable", "search_radius": "0 miles", "search_days": 0,
        "date_range": "Unavailable", "rural_market_detected": False,
        "arv_requires_human_verification": True, "verification_reasons": [reason],
        "comp_data_type": "RentCast public-record closed sales", "sale_dates_unverified": False,
        "explanation": reason,
    }
