from __future__ import annotations

from statistics import median
from typing import Any

try:
    from rentcast_intelligence_core import (
        MAX_STORED_COMPS, RENTAL_LISTING_ENDPOINT, _canonical_property_type,
        _clean_text, _number, _optional_number, _quantile, _round_money,
    )
    from rentcast_listing_normalizers import normalize_rent_comp_intelligent
    from rentcast_property_records import _records_from_result, _request_json
    from rentcast_rural_rental_scoring import _dedupe_rent_comps, _score_rent_comp
except ImportError:
    try:
        from .rentcast_intelligence_core import (
            MAX_STORED_COMPS, RENTAL_LISTING_ENDPOINT, _canonical_property_type,
            _clean_text, _number, _optional_number, _quantile, _round_money,
        )
        from .rentcast_listing_normalizers import normalize_rent_comp_intelligent
        from .rentcast_property_records import _records_from_result, _request_json
        from .rentcast_rural_rental_scoring import _dedupe_rent_comps, _score_rent_comp
    except ImportError:
        from war_room_offer_engine.rentcast_intelligence_core import (
            MAX_STORED_COMPS, RENTAL_LISTING_ENDPOINT, _canonical_property_type,
            _clean_text, _number, _optional_number, _quantile, _round_money,
        )
        from war_room_offer_engine.rentcast_listing_normalizers import normalize_rent_comp_intelligent
        from war_room_offer_engine.rentcast_property_records import _records_from_result, _request_json
        from war_room_offer_engine.rentcast_rural_rental_scoring import _dedupe_rent_comps, _score_rent_comp


def analyze_rent_intelligence(subject: dict[str, Any], comps: list[dict[str, Any]], avm_rent: float = 0) -> dict[str, Any]:
    scored = [_score_rent_comp(comp, subject) for comp in _dedupe_rent_comps(comps)]
    initial = [row for row in scored if row.get("include_default") and _number(row.get("rent")) > 0]
    if len(initial) >= 3:
        center = median(_number(row.get("rent")) for row in initial)
        for row in scored:
            if not row.get("include_default"):
                continue
            value = _number(row.get("rent"))
            if value < center * 0.55 or value > center * 1.75:
                row["flags"] = sorted(set(list(row.get("flags", [])) + ["listed rent is a robust local outlier"]))
                row["score_points"] = max(int(row.get("score_points", 0)) - 25, 0)
                row["score"] = "Bad Comp"
                row["include_default"] = False

    ranked = sorted(
        scored,
        key=lambda row: (
            bool(row.get("include_default")), row.get("score") == "Strong Comp",
            row.get("score") == "Good Comp", int(row.get("score_points", 0) or 0),
            -(_optional_number(row.get("distance")) or 999), -int(_number(row.get("days_old")) or 9999),
        ),
        reverse=True,
    )
    usable = [row for row in ranked if row.get("include_default")][:10]
    selected_ids = {id(row) for row in usable}
    display = []
    for row in ranked[:MAX_STORED_COMPS]:
        selected = id(row) in selected_ids
        flags = list(row.get("flags", []) or [])
        if row.get("include_default") and not selected:
            flags.append("not selected because ten higher-ranked rental comps were available")
        display.append({**row, "include_default": selected, "flags": sorted(set(flags))})

    strong = sum(row.get("score") == "Strong Comp" for row in usable)
    good = sum(row.get("score") == "Good Comp" for row in usable)
    weak = sum(row.get("score") == "Weak Comp" for row in usable)
    verified = strong + good
    rents = [_number(row.get("rent")) for row in usable]
    comp_median = median(rents) if rents else 0
    weighted_rent = (
        sum(_number(row.get("rent")) * max(int(row.get("score_points", 0)), 1) for row in usable)
        / sum(max(int(row.get("score_points", 0)), 1) for row in usable)
        if usable else 0
    )
    disagreement = abs(comp_median - avm_rent) / ((comp_median + avm_rent) / 2) if comp_median > 0 and avm_rent > 0 else 0
    if verified >= 3:
        recommended = (
            0.65 * comp_median + 0.35 * avm_rent if avm_rent > 0 and disagreement <= 0.20
            else min(comp_median, avm_rent) if avm_rent > 0 and disagreement > 0.20
            else comp_median
        )
    elif comp_median > 0 and avm_rent > 0:
        recommended = min(comp_median, avm_rent)
    else:
        recommended = comp_median or avm_rent

    max_distance = max((_number(row.get("distance")) for row in usable), default=0)
    max_days = max((int(_number(row.get("days_old"))) for row in usable), default=0)
    inactive_count = sum(_clean_text(row.get("status")).lower() == "inactive" for row in usable)
    if verified >= 5 and max_distance <= 10 and max_days <= 365:
        confidence = "Strong verified rent comps"
    elif verified >= 3 and max_distance <= 25 and max_days <= 730:
        confidence = "Medium verified rent comps"
    else:
        confidence = "Weak rural fallback comps" if usable else "AVM only" if avm_rent else "Missing"

    reasons: list[str] = []
    if verified < 3:
        reasons.append("Fewer than three strong or good rental comps were available.")
    if max_distance > 25:
        reasons.append(f"Rental evidence expanded as far as {max_distance:.1f} miles.")
    if max_days > 730:
        reasons.append(f"Rental evidence includes listings up to {max_days} days old.")
    if disagreement > 0.25:
        reasons.append("RentCast AVM and rental-comp median disagree by more than 25%.")
    if usable and inactive_count == len(usable):
        reasons.append("Only historical inactive rental listings were available.")
    if _canonical_property_type(subject.get("property_type")) in {"Multi-Family", "Apartment"}:
        reasons.append("RentCast rent estimates are unit-level for multi-family properties; confirm the unit configuration.")

    requires_review = bool(reasons) and (
        verified < 3 or max_distance > 25 or max_days > 730 or disagreement > 0.25
        or inactive_count == len(usable) or _canonical_property_type(subject.get("property_type")) in {"Multi-Family", "Apartment"}
    )
    mode = "Local" if max_distance <= 5 and max_days <= 270 else "Expanded" if max_distance <= 10 and max_days <= 540 else "Rural" if max_distance <= 25 else "Deep rural"
    return {
        "rent_comps": display,
        "rent_comp_count": len(usable),
        "verified_rent_comp_count": verified,
        "rent_comp_average": _round_money(weighted_rent),
        "rent_comp_median": _round_money(comp_median),
        "recommended_rent": _round_money(recommended),
        "rent_low": _round_money(_quantile(rents, 0.25)) if rents else 0,
        "rent_high": _round_money(_quantile(rents, 0.75)) if rents else 0,
        "rent_confidence": confidence,
        "rent_requires_human_verification": requires_review,
        "rent_verification_reasons": reasons,
        "rent_search_mode": mode,
        "rent_search_radius": round(max_distance, 2),
        "rent_search_days": max_days,
        "rural_market_detected": mode in {"Rural", "Deep rural"},
        "rent_comp_quality_summary": {
            "strong": strong, "good": good, "weak": weak,
            "excluded": max(len(scored) - len(usable), 0),
            "avm_comp_disagreement_pct": round(disagreement * 100, 1),
        },
    }


def _rental_listing_search(address: str, subject: dict[str, Any], api_key: str, session: Any = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    property_type = _canonical_property_type(subject.get("property_type"))
    all_comps: list[dict[str, Any]] = []
    trail: list[dict[str, Any]] = []
    errors: list[str] = []
    for status in ("Active", "Inactive"):
        params: dict[str, Any] = {
            "address": address, "radius": 50, "status": status, "daysOld": 1095, "limit": 500,
        }
        if property_type in {"Single Family", "Condo", "Townhouse", "Manufactured", "Multi-Family", "Apartment"}:
            params["propertyType"] = property_type
        result = _request_json(RENTAL_LISTING_ENDPOINT, api_key, params, session=session)
        records = _records_from_result(result) if result.get("ok") else []
        normalized = [normalize_rent_comp_intelligent(row) for row in records]
        all_comps.extend(normalized)
        trail.append({
            "source": "RentCast rental listings", "status": status, "radius": 50, "days": 1095,
            "returned": len(records), "cache_hit": bool(result.get("cache_hit")), "ok": bool(result.get("ok")),
        })
        if not result.get("ok"):
            errors.append(_clean_text(result.get("error")))
        analysis = analyze_rent_intelligence(subject, all_comps)
        if int(analysis.get("verified_rent_comp_count", 0) or 0) >= 3:
            break
    return all_comps, trail, errors
