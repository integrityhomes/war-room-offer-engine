from __future__ import annotations

from statistics import mean, median
from typing import Any

try:
    from rentcast_intelligence_core import (
        MAX_STORED_COMPS, PROPERTY_ENDPOINT, SOLD_SEARCH_STAGES,
        _canonical_property_type, _clean_text, _is_subject_property,
        _normalize_address, _number, _optional_number, _quantile, _round_money,
    )
    from rentcast_listing_normalizers import _subject_from_data, normalize_recorded_sale
    from rentcast_property_records import _records_from_result, _request_json
    from rentcast_recorded_sales_scoring import (
        _apply_ppsf_outlier_guard, _empty_arv_summary, _score_recorded_sale,
    )
except ImportError:
    try:
        from .rentcast_intelligence_core import (
            MAX_STORED_COMPS, PROPERTY_ENDPOINT, SOLD_SEARCH_STAGES,
            _canonical_property_type, _clean_text, _is_subject_property,
            _normalize_address, _number, _optional_number, _quantile, _round_money,
        )
        from .rentcast_listing_normalizers import _subject_from_data, normalize_recorded_sale
        from .rentcast_property_records import _records_from_result, _request_json
        from .rentcast_recorded_sales_scoring import (
            _apply_ppsf_outlier_guard, _empty_arv_summary, _score_recorded_sale,
        )
    except ImportError:
        from war_room_offer_engine.rentcast_intelligence_core import (
            MAX_STORED_COMPS, PROPERTY_ENDPOINT, SOLD_SEARCH_STAGES,
            _canonical_property_type, _clean_text, _is_subject_property,
            _normalize_address, _number, _optional_number, _quantile, _round_money,
        )
        from war_room_offer_engine.rentcast_listing_normalizers import _subject_from_data, normalize_recorded_sale
        from war_room_offer_engine.rentcast_property_records import _records_from_result, _request_json
        from war_room_offer_engine.rentcast_recorded_sales_scoring import (
            _apply_ppsf_outlier_guard, _empty_arv_summary, _score_recorded_sale,
        )


def _summarize_recorded_sales(scored: list[dict[str, Any]], subject: dict[str, Any], stage: dict[str, Any], candidate_count: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranked = sorted(
        scored,
        key=lambda row: (
            bool(row.get("include_default")),
            row.get("score") == "Strong Comp",
            row.get("score") == "Good Comp",
            int(row.get("score_points", 0) or 0),
            -_number(row.get("sale_age_days")),
            -(_optional_number(row.get("distance_miles")) or 999),
        ),
        reverse=True,
    )
    usable = [row for row in ranked if row.get("include_default") and row.get("score") != "Bad Comp"][:5]
    selected_ids = {id(row) for row in usable}
    display_rows: list[dict[str, Any]] = []
    for row in ranked[:MAX_STORED_COMPS]:
        selected = id(row) in selected_ids
        flags = list(row.get("flags", []) or [])
        if row.get("include_default") and not selected:
            flags.append("not selected because five higher-ranked comps were available")
        display_rows.append({**row, "include_default": selected, "flags": sorted(set(flags))})

    if not usable:
        summary = _empty_arv_summary("No closed sales passed the selected similarity, distance and recency safeguards.")
        summary.update({
            "search_mode": stage["name"], "search_radius": f"{stage['radius']:g} miles",
            "search_days": int(stage["days"]), "date_range": f"Last {int(stage['days'])} days",
            "candidate_comp_count": candidate_count, "excluded_comp_count": len(scored),
            "rural_market_detected": stage["name"] in {"Rural", "Deep rural", "Remote rural"},
        })
        return display_rows, summary

    prices = [_number(row.get("sold_price")) for row in usable]
    ppsf_values = [_number(row.get("price_per_sqft")) for row in usable if _number(row.get("price_per_sqft")) > 0]
    subject_sqft = _number(subject.get("sqft"))
    price_median = median(prices) if prices else 0
    median_ppsf = median(ppsf_values) if ppsf_values else 0
    ppsf_arv = median_ppsf * subject_sqft if median_ppsf > 0 and subject_sqft > 0 else 0
    disagreement = (
        abs(price_median - ppsf_arv) / ((price_median + ppsf_arv) / 2)
        if price_median > 0 and ppsf_arv > 0 else 0
    )
    if ppsf_arv > 0 and price_median > 0:
        recommended = 0.70 * ppsf_arv + 0.30 * price_median if disagreement <= 0.15 else (
            0.80 * ppsf_arv + 0.20 * price_median if disagreement <= 0.25 else min(ppsf_arv, price_median)
        )
    else:
        recommended = ppsf_arv or price_median

    adjusted_values = [
        _number(row.get("price_per_sqft")) * subject_sqft
        for row in usable if _number(row.get("price_per_sqft")) > 0 and subject_sqft > 0
    ] or prices
    strong = sum(row.get("score") == "Strong Comp" for row in usable)
    good = sum(row.get("score") == "Good Comp" for row in usable)
    weak = sum(row.get("score") == "Weak Comp" for row in usable)
    verified = strong + good
    rural = stage["name"] in {"Rural", "Deep rural", "Remote rural"}
    if strong >= 2 and verified >= 3 and stage["radius"] <= 3 and disagreement <= 0.15:
        confidence = "Strong"
    elif verified >= 3 and stage["radius"] <= 10 and disagreement <= 0.25:
        confidence = "Medium"
    else:
        confidence = "Weak"

    reasons: list[str] = []
    if verified < 3:
        reasons.append("Fewer than three strong or good recorded-sale comps were available.")
    if stage["radius"] >= 25:
        reasons.append(f"The closed-sale search expanded to {stage['radius']:g} miles.")
    if stage["days"] > 1095:
        reasons.append(f"The search used sales as old as {int(stage['days'])} days.")
    if disagreement > 0.25:
        reasons.append("Median-price and price-per-square-foot ARV methods disagree by more than 25%.")
    requires_review = confidence == "Weak" or stage["radius"] >= 25 or disagreement > 0.25
    if requires_review and not reasons:
        reasons.append("The recorded-sale evidence needs human confirmation before a binding offer.")

    low = _quantile(adjusted_values, 0.25)
    high = _quantile(adjusted_values, 0.75)
    conservative = _quantile(adjusted_values, 0.35)
    explanation = (
        f"Recommended ARV uses {len(usable)} public-record closed sale(s), blending the median sale price "
        f"with median price per square foot. Search mode: {stage['name']}."
    )
    return display_rows, {
        "low_arv": _round_money(min(low or recommended, recommended)),
        "conservative_arv": _round_money(conservative or recommended),
        "average_arv": _round_money(mean(adjusted_values) if adjusted_values else recommended),
        "high_arv": _round_money(max(high or recommended, recommended)),
        "recommended_arv": _round_money(recommended),
        "arv_confidence": confidence,
        "strong_comp_count": strong,
        "good_comp_count": good,
        "weak_comp_count": weak,
        "excluded_comp_count": max(candidate_count - len(usable), 0),
        "included_comp_count": len(usable),
        "verified_sold_comp_count": verified,
        "price_median": _round_money(price_median),
        "median_price_per_sqft": round(median_ppsf, 2),
        "ppsf_arv": _round_money(ppsf_arv),
        "method_disagreement_pct": round(disagreement * 100, 1),
        "search_mode": stage["name"],
        "search_radius": f"{stage['radius']:g} miles",
        "search_days": int(stage["days"]),
        "date_range": f"Last {int(stage['days'])} days",
        "rural_market_detected": rural,
        "arv_requires_human_verification": requires_review,
        "verification_reasons": reasons,
        "candidate_comp_count": candidate_count,
        "comp_data_type": "RentCast public-record closed sales",
        "sale_dates_unverified": False,
        "explanation": explanation,
    }


def build_recorded_sold_intelligence(
    data: dict[str, Any], sold_comps: list[dict[str, Any]], full_address: str = ""
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    subject = _subject_from_data(data, full_address)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    removed_subject = 0
    for raw in sold_comps or []:
        if not isinstance(raw, dict):
            continue
        comp = normalize_recorded_sale(raw, subject)
        if _is_subject_property(subject.get("address", ""), comp.get("comp_address", "")):
            removed_subject += 1
            continue
        identity = _clean_text(comp.get("assessor_id") or comp.get("id")) or "|".join([
            _normalize_address(comp.get("comp_address")), _clean_text(comp.get("sold_date")), str(_round_money(comp.get("sold_price")))
        ])
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(comp)

    if not normalized:
        summary = _empty_arv_summary()
        summary["subject_comp_removed_count"] = removed_subject
        return [], summary

    candidates: list[tuple[list[dict[str, Any]], dict[str, Any], tuple[int, int, int, int, int]]] = []
    for index, stage in enumerate(SOLD_SEARCH_STAGES):
        scored = [_score_recorded_sale(comp, subject, stage) for comp in normalized]
        scored = _apply_ppsf_outlier_guard(scored)
        display, summary = _summarize_recorded_sales(scored, subject, stage, len(normalized))
        summary["subject_comp_removed_count"] = removed_subject
        rank = (
            1 if int(summary.get("verified_sold_comp_count", 0) or 0) >= 3 else 0,
            int(summary.get("strong_comp_count", 0) or 0),
            int(summary.get("good_comp_count", 0) or 0),
            int(summary.get("included_comp_count", 0) or 0),
            -index,
        )
        candidates.append((display, summary, rank))
        if rank[0] == 1:
            break
    display, summary, _ = max(candidates, key=lambda row: row[2])
    return display, summary


def _sold_search(address: str, subject: dict[str, Any], api_key: str, session: Any = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    property_type = _canonical_property_type(subject.get("property_type"))
    trail: list[dict[str, Any]] = []
    errors: list[str] = []
    all_records: list[dict[str, Any]] = []
    for radius, days in ((10, 1095), (50, 2555)):
        params: dict[str, Any] = {
            "address": address, "radius": radius, "saleDateRange": days, "limit": 500,
        }
        if property_type in {"Single Family", "Condo", "Townhouse", "Manufactured", "Multi-Family", "Apartment", "Land"}:
            params["propertyType"] = property_type
        result = _request_json(PROPERTY_ENDPOINT, api_key, params, session=session)
        records = _records_from_result(result) if result.get("ok") else []
        trail.append({
            "source": "RentCast /properties", "radius": radius, "days": days,
            "returned": len(records), "cache_hit": bool(result.get("cache_hit")), "ok": bool(result.get("ok")),
        })
        if not result.get("ok"):
            errors.append(_clean_text(result.get("error")))
        all_records.extend(records)
        scored, summary = build_recorded_sold_intelligence(subject, all_records, address)
        if int(summary.get("verified_sold_comp_count", 0) or 0) >= 3 or radius == 50:
            return all_records, trail, errors
    return all_records, trail, errors
