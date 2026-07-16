from __future__ import annotations

from statistics import mean, median
from typing import Any

try:
    import address_rentcast_bridge as bridge
    import rentcast_auto_enrichment as rentcast
    import rentcast_intelligence_core as core
    import rentcast_listing_normalizers as normalizers
    import rentcast_property_enrichment as enrichment
    import rentcast_property_intelligence as intelligence
    import rentcast_property_records as records
    import rentcast_recorded_sales as sales
    import rentcast_recorded_sales_scoring as sale_scoring
    import rentcast_rural_rental_scoring as rent_scoring
    import rentcast_rural_rentals as rentals
except ImportError:
    try:
        from . import address_rentcast_bridge as bridge
        from . import rentcast_auto_enrichment as rentcast
        from . import rentcast_intelligence_core as core
        from . import rentcast_listing_normalizers as normalizers
        from . import rentcast_property_enrichment as enrichment
        from . import rentcast_property_intelligence as intelligence
        from . import rentcast_property_records as records
        from . import rentcast_recorded_sales as sales
        from . import rentcast_recorded_sales_scoring as sale_scoring
        from . import rentcast_rural_rental_scoring as rent_scoring
        from . import rentcast_rural_rentals as rentals
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge as bridge
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine import rentcast_intelligence_core as core
        from war_room_offer_engine import rentcast_listing_normalizers as normalizers
        from war_room_offer_engine import rentcast_property_enrichment as enrichment
        from war_room_offer_engine import rentcast_property_intelligence as intelligence
        from war_room_offer_engine import rentcast_property_records as records
        from war_room_offer_engine import rentcast_recorded_sales as sales
        from war_room_offer_engine import rentcast_recorded_sales_scoring as sale_scoring
        from war_room_offer_engine import rentcast_rural_rental_scoring as rent_scoring
        from war_room_offer_engine import rentcast_rural_rentals as rentals


CONDITION_REASON = (
    "Public-record sale data confirms price and date, but not renovated or ARV-level "
    "condition. Review comp photos, MLS details, or a trusted local source."
)
RENT_EVIDENCE_NOTE = (
    "Rental comps are advertised asking rents, not proof of executed lease amounts."
)

_ORIGINAL_SUMMARIZE = getattr(
    sales, "_quality_hardening_original_summarize", sales._summarize_recorded_sales
)
_ORIGINAL_INTELLIGENT_ENRICH = getattr(
    enrichment,
    "_quality_hardening_original_enrich",
    enrichment.enrich_property_with_intelligence,
)


def _sale_events(record: dict[str, Any]) -> list[tuple[Any, float, str]]:
    events: list[tuple[Any, float, str]] = []
    history = record.get("history") if isinstance(record.get("history"), dict) else {}
    for raw in history.values():
        event = raw if isinstance(raw, dict) else {}
        label = core._clean_text(event.get("event")).lower()
        if "sale" not in label or "listing" in label:
            continue
        sold_on = core._parse_date(event.get("date"))
        price = core._number(event.get("price"))
        if sold_on and price > 0:
            events.append((sold_on, price, sold_on.isoformat()))
    return sorted(events, key=lambda row: row[0], reverse=True)


def sale_from_record_paired(record: dict[str, Any]) -> tuple[float, str]:
    """Return a price and date from the same recorded transaction."""
    top_price = core._number(record.get("lastSalePrice") or record.get("lastSoldPrice"))
    top_date = core._iso_date(record.get("lastSaleDate") or record.get("lastSoldDate"))
    if top_price > 0 and top_date:
        return top_price, top_date

    events = _sale_events(record)
    if top_price > 0:
        tolerance = max(100.0, top_price * 0.005)
        match = next((row for row in events if abs(row[1] - top_price) <= tolerance), None)
        if match:
            return top_price, match[2]
    if top_date:
        match = next((row for row in events if row[2] == top_date), None)
        if match:
            return match[1], top_date
    if events:
        _, price, sold_date = events[0]
        return price, sold_date
    return 0.0, ""


def _sale_key(row: dict[str, Any]) -> str:
    return core._clean_text(row.get("assessor_id") or row.get("id")) or "|".join(
        [
            core._normalize_address(row.get("comp_address")),
            core._clean_text(row.get("sold_date")),
            str(core._round_money(row.get("sold_price"))),
        ]
    )


def _quality_sales(
    scored: list[dict[str, Any]], subject: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in scored
        if row.get("include_default")
        and row.get("score") in {"Strong Comp", "Good Comp"}
        and core._number(row.get("sold_price")) > 0
        and core._clean_text(row.get("sold_date"))
        and core._optional_number(row.get("distance_miles")) is not None
        and (
            core._number(subject.get("sqft")) <= 0
            or core._number(row.get("square_feet")) > 0
        )
    ]
    return sorted(
        rows,
        key=lambda row: (
            row.get("score") == "Strong Comp",
            int(row.get("score_points", 0) or 0),
            -int(core._number(row.get("sale_age_days")) or 999999),
            -(core._optional_number(row.get("distance_miles")) or 999),
        ),
        reverse=True,
    )[:5]


def apply_ppsf_outlier_guard_quality(
    scored: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Anchor outlier detection to quality comps so weak rows cannot move the center."""
    quality = [
        row
        for row in scored
        if row.get("include_default")
        and row.get("score") in {"Strong Comp", "Good Comp"}
        and core._number(row.get("price_per_sqft")) > 0
    ]
    if len(quality) < 3:
        return scored

    center = median(core._number(row.get("price_per_sqft")) for row in quality)
    deviations = [
        abs(core._number(row.get("price_per_sqft")) - center) for row in quality
    ]
    mad = median(deviations) if deviations else 0
    updated: list[dict[str, Any]] = []
    for raw in scored:
        row = dict(raw)
        ppsf = core._number(row.get("price_per_sqft"))
        include = bool(row.get("include_default"))
        outlier = False
        if include and ppsf > 0:
            if mad > 0:
                outlier = 0.6745 * abs(ppsf - center) / mad > 3.5
            else:
                outlier = ppsf < center * 0.55 or ppsf > center * 1.80
        if outlier:
            flags = list(row.get("flags", []) or [])
            flags.append("price per square foot is a robust quality-comp outlier")
            points = max(int(row.get("score_points", 0) or 0) - 25, 0)
            row.update(
                {
                    "flags": sorted(set(flags)),
                    "score_points": points,
                    "score": sale_scoring._score_label(points, True),
                    "include_default": False,
                }
            )
        updated.append(row)
    return updated


def _add_condition_guard(summary: dict[str, Any]) -> dict[str, Any]:
    summary = dict(summary or {})
    if core._number(summary.get("recommended_arv")) <= 0:
        return summary
    reasons = list(summary.get("verification_reasons", []) or [])
    reasons.append(CONDITION_REASON)
    raw_confidence = core._clean_text(summary.get("arv_confidence") or "Weak")
    summary["pre_condition_arv_confidence"] = raw_confidence
    summary["arv_confidence"] = "Medium" if raw_confidence == "Strong" else raw_confidence
    summary["arv_requires_human_verification"] = True
    summary["verification_reasons"] = list(dict.fromkeys(reasons))
    summary["condition_evidence"] = "Unverified"
    return summary


def summarize_recorded_sales_quality(
    scored: list[dict[str, Any]],
    subject: dict[str, Any],
    stage: dict[str, Any],
    candidate_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    display, baseline = _ORIGINAL_SUMMARIZE(scored, subject, stage, candidate_count)
    quality = _quality_sales(scored, subject)
    if len(quality) < 3:
        summary = dict(baseline or {})
        summary["verified_sold_comp_count"] = len(quality)
        summary["strong_comp_count"] = sum(
            row.get("score") == "Strong Comp" for row in quality
        )
        summary["good_comp_count"] = sum(
            row.get("score") == "Good Comp" for row in quality
        )
        summary["calculation_comp_quality"] = (
            "Weak fallback: fewer than three strong/good sales had verified date, "
            "price, distance, and required square footage."
        )
        return display, _add_condition_guard(summary)

    selected = {_sale_key(row) for row in quality}
    hardened_display: list[dict[str, Any]] = []
    for raw in display:
        row = dict(raw)
        use = _sale_key(row) in selected
        flags = list(row.get("flags", []) or [])
        if row.get("include_default") and not use:
            flags.append(
                "not used in primary ARV because stronger verified comps were available"
            )
        row.update({"include_default": use, "flags": sorted(set(flags))})
        hardened_display.append(row)

    prices = [core._number(row.get("sold_price")) for row in quality]
    ppsf = [
        core._number(row.get("price_per_sqft"))
        for row in quality
        if core._number(row.get("price_per_sqft")) > 0
    ]
    subject_sqft = core._number(subject.get("sqft"))
    price_median = median(prices)
    median_ppsf = median(ppsf) if ppsf else 0
    ppsf_arv = median_ppsf * subject_sqft if median_ppsf and subject_sqft else 0
    disagreement = (
        abs(price_median - ppsf_arv) / ((price_median + ppsf_arv) / 2)
        if price_median and ppsf_arv
        else 0
    )
    if price_median and ppsf_arv:
        recommended = (
            0.70 * ppsf_arv + 0.30 * price_median
            if disagreement <= 0.15
            else 0.80 * ppsf_arv + 0.20 * price_median
            if disagreement <= 0.25
            else min(price_median, ppsf_arv)
        )
    else:
        recommended = ppsf_arv or price_median

    adjusted = [
        core._number(row.get("price_per_sqft")) * subject_sqft
        for row in quality
        if core._number(row.get("price_per_sqft")) > 0 and subject_sqft > 0
    ] or prices
    strong = sum(row.get("score") == "Strong Comp" for row in quality)
    good = sum(row.get("score") == "Good Comp" for row in quality)
    if strong >= 2 and float(stage["radius"]) <= 3 and disagreement <= 0.15:
        confidence = "Strong"
    elif float(stage["radius"]) <= 10 and disagreement <= 0.25:
        confidence = "Medium"
    else:
        confidence = "Weak"

    reasons: list[str] = []
    if float(stage["radius"]) >= 25:
        reasons.append(
            f"The closed-sale search expanded to {float(stage['radius']):g} miles."
        )
    if int(stage["days"]) > 1095:
        reasons.append(f"The search used sales as old as {int(stage['days'])} days.")
    if disagreement > 0.25:
        reasons.append(
            "Median-price and price-per-square-foot methods disagree by more than 25%."
        )
    reasons.append(CONDITION_REASON)

    summary = dict(baseline or {})
    summary.update(
        {
            "low_arv": core._round_money(
                min(core._quantile(adjusted, 0.25) or recommended, recommended)
            ),
            "conservative_arv": core._round_money(
                core._quantile(adjusted, 0.35) or recommended
            ),
            "average_arv": core._round_money(mean(adjusted)),
            "high_arv": core._round_money(
                max(core._quantile(adjusted, 0.75) or recommended, recommended)
            ),
            "recommended_arv": core._round_money(recommended),
            "arv_confidence": "Medium" if confidence == "Strong" else confidence,
            "pre_condition_arv_confidence": confidence,
            "strong_comp_count": strong,
            "good_comp_count": good,
            "weak_comp_count": 0,
            "excluded_comp_count": max(candidate_count - len(quality), 0),
            "included_comp_count": len(quality),
            "verified_sold_comp_count": len(quality),
            "price_median": core._round_money(price_median),
            "median_price_per_sqft": round(median_ppsf, 2),
            "ppsf_arv": core._round_money(ppsf_arv),
            "method_disagreement_pct": round(disagreement * 100, 1),
            "arv_requires_human_verification": True,
            "verification_reasons": list(dict.fromkeys(reasons)),
            "condition_evidence": "Unverified",
            "calculation_comp_quality": "Strong and good recorded-sale comps only",
            "explanation": (
                f"Recommended ARV uses {len(quality)} quality public-record sales. "
                "Comp condition still requires human verification."
            ),
        }
    )
    return hardened_display, summary


def _has_rent_age(row: dict[str, Any]) -> bool:
    return bool(
        core._clean_text(row.get("listed_date"))
        or core._clean_text(row.get("last_seen_date"))
        or core._clean_text(row.get("removed_date"))
        or core._number(row.get("days_old")) > 0
    )


def _quality_rent_rows(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in scored
        if row.get("include_default")
        and row.get("score") in {"Strong Comp", "Good Comp"}
        and core._number(row.get("rent")) > 0
        and core._optional_number(row.get("distance")) is not None
        and _has_rent_age(row)
    ]


def _apply_rent_outlier_guard(
    scored: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    quality = _quality_rent_rows(scored)
    if len(quality) < 3:
        return scored
    center = median(core._number(row.get("rent")) for row in quality)
    updated: list[dict[str, Any]] = []
    for raw in scored:
        row = dict(raw)
        value = core._number(row.get("rent"))
        if (
            row.get("include_default")
            and value > 0
            and (value < center * 0.55 or value > center * 1.75)
        ):
            flags = list(row.get("flags", []) or [])
            flags.append("listed rent is a robust quality-comp outlier")
            points = max(int(row.get("score_points", 0) or 0) - 25, 0)
            row.update(
                {
                    "flags": sorted(set(flags)),
                    "score_points": points,
                    "score": sale_scoring._score_label(points, True),
                    "include_default": False,
                }
            )
        updated.append(row)
    return updated


def _rank_rent_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            bool(row.get("include_default")),
            row.get("score") == "Strong Comp",
            row.get("score") == "Good Comp",
            int(row.get("score_points", 0) or 0),
            -(core._optional_number(row.get("distance")) or 999),
            -int(core._number(row.get("days_old")) or 999999),
        ),
        reverse=True,
    )


def analyze_rent_intelligence_quality(
    subject: dict[str, Any], comps: list[dict[str, Any]], avm_rent: float = 0
) -> dict[str, Any]:
    scored = [
        rent_scoring._score_rent_comp(comp, subject)
        for comp in rent_scoring._dedupe_rent_comps(comps)
    ]
    scored = _apply_rent_outlier_guard(scored)
    ranked = _rank_rent_rows(scored)
    quality = _rank_rent_rows(_quality_rent_rows(scored))[:10]
    selected = (
        quality
        if len(quality) >= 3
        else [row for row in ranked if row.get("include_default")][:10]
    )
    selected_ids = {id(row) for row in selected}

    display: list[dict[str, Any]] = []
    for raw in ranked[: core.MAX_STORED_COMPS]:
        row = dict(raw)
        use = id(raw) in selected_ids
        flags = list(row.get("flags", []) or [])
        if row.get("include_default") and not use:
            flags.append(
                "not used in primary rent because stronger verified comps were available"
            )
        row.update({"include_default": use, "flags": sorted(set(flags))})
        display.append(row)

    verified = len(quality)
    rents = [core._number(row.get("rent")) for row in selected]
    comp_median = median(rents) if rents else 0
    weighted = (
        sum(
            core._number(row.get("rent"))
            * max(int(row.get("score_points", 0) or 0), 1)
            for row in selected
        )
        / sum(max(int(row.get("score_points", 0) or 0), 1) for row in selected)
        if selected
        else 0
    )
    disagreement = (
        abs(comp_median - avm_rent) / ((comp_median + avm_rent) / 2)
        if comp_median and avm_rent
        else 0
    )
    if verified >= 3:
        recommended = (
            0.65 * comp_median + 0.35 * avm_rent
            if avm_rent and disagreement <= 0.20
            else min(comp_median, avm_rent)
            if avm_rent
            else comp_median
        )
    elif comp_median and avm_rent:
        recommended = min(comp_median, avm_rent)
    else:
        recommended = comp_median or avm_rent

    max_distance = max(
        (core._number(row.get("distance")) for row in selected), default=0
    )
    max_days = max(
        (int(core._number(row.get("days_old"))) for row in selected), default=0
    )
    inactive = sum(
        core._clean_text(row.get("status")).lower() == "inactive" for row in selected
    )
    missing_age = any(not _has_rent_age(row) for row in selected)
    if verified >= 5 and max_distance <= 10 and max_days <= 365:
        confidence = "Strong verified rent comps"
    elif verified >= 3 and max_distance <= 25 and max_days <= 730:
        confidence = "Medium verified rent comps"
    else:
        confidence = (
            "Weak rural fallback comps"
            if selected
            else "AVM only"
            if avm_rent
            else "Missing"
        )

    reasons: list[str] = []
    if verified < 3:
        reasons.append(
            "Fewer than three strong/good rental listings had verified distance and listing age."
        )
    if max_distance > 25:
        reasons.append(f"Rental evidence expanded as far as {max_distance:.1f} miles.")
    if max_days > 730:
        reasons.append(f"Rental evidence includes listings up to {max_days} days old.")
    if missing_age:
        reasons.append("Some rental listing ages could not be verified.")
    if disagreement > 0.25:
        reasons.append(
            "RentCast AVM and rental-comp median disagree by more than 25%."
        )
    if selected and inactive == len(selected):
        reasons.append("Only historical inactive rental listings were available.")
    if core._canonical_property_type(subject.get("property_type")) in {
        "Multi-Family",
        "Apartment",
    }:
        reasons.append(
            "RentCast rent estimates are unit-level for multi-family properties; "
            "confirm the unit configuration."
        )

    strong = sum(row.get("score") == "Strong Comp" for row in selected)
    good = sum(row.get("score") == "Good Comp" for row in selected)
    weak = sum(row.get("score") == "Weak Comp" for row in selected)
    mode = (
        "Local"
        if max_distance <= 5 and max_days <= 270
        else "Expanded"
        if max_distance <= 10 and max_days <= 540
        else "Rural"
        if max_distance <= 25
        else "Deep rural"
    )
    return {
        "rent_comps": display,
        "rent_comp_count": len(selected),
        "verified_rent_comp_count": verified,
        "rent_comp_average": core._round_money(weighted),
        "rent_comp_median": core._round_money(comp_median),
        "recommended_rent": core._round_money(recommended),
        "rent_low": core._round_money(core._quantile(rents, 0.25)) if rents else 0,
        "rent_high": core._round_money(core._quantile(rents, 0.75)) if rents else 0,
        "rent_confidence": confidence,
        "rent_requires_human_verification": bool(reasons),
        "rent_verification_reasons": list(dict.fromkeys(reasons)),
        "rent_search_mode": mode,
        "rent_search_radius": round(max_distance, 2),
        "rent_search_days": max_days,
        "rural_market_detected": mode in {"Rural", "Deep rural"},
        "rent_comp_quality_summary": {
            "strong": strong,
            "good": good,
            "weak": weak,
            "excluded": max(len(scored) - len(selected), 0),
            "avm_comp_disagreement_pct": round(disagreement * 100, 1),
            "calculation_comp_quality": (
                "Strong and good rental listings only"
                if verified >= 3
                else "Weak rural fallback"
            ),
            "evidence_note": RENT_EVIDENCE_NOTE,
        },
    }


def enrich_property_with_quality(
    data: dict[str, Any], api_key: str, session: Any = None
) -> dict[str, Any]:
    kwargs = {} if session is None else {"session": session}
    result = dict(_ORIGINAL_INTELLIGENT_ENRICH(data, api_key, **kwargs) or {})
    if core._clean_text(result.get("arv_source")) == "Manual Override":
        result["arv_requires_human_verification"] = False
        result["arv_verification_reasons"] = []
        summary = result.get("auto_arv_summary")
        if isinstance(summary, dict):
            summary = dict(summary)
            summary["manual_override_active"] = True
            result["auto_arv_summary"] = summary
    return result


def install() -> bool:
    if getattr(core, "_rentcast_intelligence_quality_hardening_installed", False):
        return True

    sales._quality_hardening_original_summarize = _ORIGINAL_SUMMARIZE
    enrichment._quality_hardening_original_enrich = _ORIGINAL_INTELLIGENT_ENRICH

    core._sale_from_record = sale_from_record_paired
    records._sale_from_record = sale_from_record_paired
    normalizers._sale_from_record = sale_from_record_paired

    sale_scoring._apply_ppsf_outlier_guard = apply_ppsf_outlier_guard_quality
    sales._apply_ppsf_outlier_guard = apply_ppsf_outlier_guard_quality
    sales._summarize_recorded_sales = summarize_recorded_sales_quality

    rentals.analyze_rent_intelligence = analyze_rent_intelligence_quality
    enrichment.analyze_rent_intelligence = analyze_rent_intelligence_quality

    enrichment.enrich_property_with_intelligence = enrich_property_with_quality
    intelligence.enrich_property_with_intelligence = enrich_property_with_quality
    rentcast.enrich_property_with_rentcast = enrich_property_with_quality
    bridge.enrich_property_with_rentcast = enrich_property_with_quality

    core._rentcast_intelligence_quality_hardening_installed = True
    return True


install()
