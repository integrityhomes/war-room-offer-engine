from __future__ import annotations

import copy
from statistics import median
from typing import Any

try:
    import data_sources as ds
    import rentcast_auto_enrichment as rentcast
    import rentcast_comp_normalization_fix as normalization  # noqa: F401 - install baseline safety patch first
    from rentcast_intelligence_core import (
        CACHE_TTL_SECONDS, _canonical_property_type, _normalize_address,
        _number, _round_money,
    )
    from rentcast_listing_normalizers import _subject_from_data
    from rentcast_property_records import _lookup_subject_record
    from rentcast_recorded_sales import build_recorded_sold_intelligence, _sold_search
    from rentcast_rural_rentals import analyze_rent_intelligence, _rental_listing_search
except ImportError:
    try:
        from . import data_sources as ds
        from . import rentcast_auto_enrichment as rentcast
        from . import rentcast_comp_normalization_fix as normalization  # noqa: F401
        from .rentcast_intelligence_core import (
            CACHE_TTL_SECONDS, _canonical_property_type, _normalize_address,
            _number, _round_money,
        )
        from .rentcast_listing_normalizers import _subject_from_data
        from .rentcast_property_records import _lookup_subject_record
        from .rentcast_recorded_sales import build_recorded_sold_intelligence, _sold_search
        from .rentcast_rural_rentals import analyze_rent_intelligence, _rental_listing_search
    except ImportError:
        from war_room_offer_engine import data_sources as ds
        from war_room_offer_engine import rentcast_auto_enrichment as rentcast
        from war_room_offer_engine import rentcast_comp_normalization_fix as normalization  # noqa: F401
        from war_room_offer_engine.rentcast_intelligence_core import (
            CACHE_TTL_SECONDS, _canonical_property_type, _normalize_address,
            _number, _round_money,
        )
        from war_room_offer_engine.rentcast_listing_normalizers import _subject_from_data
        from war_room_offer_engine.rentcast_property_records import _lookup_subject_record
        from war_room_offer_engine.rentcast_recorded_sales import build_recorded_sold_intelligence, _sold_search
        from war_room_offer_engine.rentcast_rural_rentals import analyze_rent_intelligence, _rental_listing_search


_RESULT_CACHE: dict[str, dict[str, Any]] = {}
_ORIGINAL_ENRICH = getattr(
    rentcast, "_rentcast_property_intelligence_original_enrich", rentcast.enrich_property_with_rentcast
)


def _hydrate_if_available(result: dict[str, Any]) -> None:
    try:
        import streamlit as st
        try:
            from rentcast_property_intelligence import hydrate_intelligence_state
        except ImportError:
            try:
                from .rentcast_property_intelligence import hydrate_intelligence_state
            except ImportError:
                from war_room_offer_engine.rentcast_property_intelligence import hydrate_intelligence_state
        hydrate_intelligence_state(st, result)
    except Exception:
        pass


def _merge_subject_facts(enriched: dict[str, Any], facts: dict[str, Any]) -> None:
    for key in (
        "address", "city", "state", "zip", "county", "latitude", "longitude", "property_type",
        "beds", "baths", "sqft", "lot_size", "year_built", "assessor_id", "subdivision", "zoning",
        "last_sale_date", "last_sale_price", "taxes", "property_tax_year", "tax_assessed_value",
        "tax_assessment_year", "hoa_fee", "hoa_frequency", "property_features", "owner_name",
        "owner_type", "owner_occupied", "occupancy",
    ):
        value = facts.get(key)
        if value not in [None, "", 0, 0.0, [], {}]:
            enriched[key] = copy.deepcopy(value)
    if facts:
        enriched["rentcast_property_record_id"] = facts.get("rentcast_property_record_id", "")
        enriched["rentcast_property_record_summary"] = copy.deepcopy(facts)


def _copy_arv_summary(enriched: dict[str, Any], scored: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    enriched.update({
        "rentcast_sold_comps": scored,
        "rentcast_sold_comp_count": int(summary.get("included_comp_count", 0) or 0),
        "rentcast_value_comp_count": int(summary.get("included_comp_count", 0) or 0),
        "auto_sold_comps": scored,
        "auto_comp_count": len(scored),
        "auto_arv_summary": summary,
        "auto_recommended_arv": _number(summary.get("recommended_arv")),
        "auto_low_arv": _number(summary.get("low_arv")),
        "auto_conservative_arv": _number(summary.get("conservative_arv")),
        "auto_average_arv": _number(summary.get("average_arv")),
        "auto_high_arv": _number(summary.get("high_arv")),
        "strong_comp_count": int(summary.get("strong_comp_count", 0) or 0),
        "good_comp_count": int(summary.get("good_comp_count", 0) or 0),
        "weak_comp_count": int(summary.get("weak_comp_count", 0) or 0),
        "excluded_comp_count": int(summary.get("excluded_comp_count", 0) or 0),
        "verified_sold_comp_count": int(summary.get("verified_sold_comp_count", 0) or 0),
        "auto_comp_radius": summary.get("search_radius", "0 miles"),
        "auto_comp_date_range": summary.get("date_range", "Unavailable"),
        "arv_price_median": _number(summary.get("price_median")),
        "arv_median_ppsf": _number(summary.get("median_price_per_sqft")),
        "arv_ppsf_estimate": _number(summary.get("ppsf_arv")),
        "arv_method_disagreement_pct": _number(summary.get("method_disagreement_pct")),
        "arv_search_mode": summary.get("search_mode", "Unavailable"),
        "arv_search_radius": summary.get("search_radius", "0 miles"),
        "arv_search_days": int(summary.get("search_days", 0) or 0),
        "arv_requires_human_verification": bool(summary.get("arv_requires_human_verification", True)),
        "arv_verification_reasons": list(summary.get("verification_reasons", []) or []),
    })


def enrich_property_with_intelligence(data: dict[str, Any], api_key: str, session: Any = None) -> dict[str, Any]:
    session = session or getattr(rentcast, "requests", None) or getattr(ds, "requests", None)
    enriched = _ORIGINAL_ENRICH(data, api_key, **({} if session is None else {"session": session}))
    enriched = dict(enriched or {})
    full_address = rentcast.build_full_address(enriched) or rentcast.build_full_address(data or {})
    if not api_key or not full_address:
        return enriched

    facts, property_error, property_cache_hit = _lookup_subject_record(full_address, api_key, session=session)
    _merge_subject_facts(enriched, facts)
    enriched["rentcast_property_error"] = property_error
    subject = _subject_from_data({**dict(data or {}), **enriched, **facts}, facts.get("formatted_address") or full_address)

    value_listing_comps = [
        dict(row) for row in (enriched.get("rentcast_sold_comps") or []) if isinstance(row, dict)
    ]
    enriched["rentcast_value_listing_comps"] = value_listing_comps
    enriched["rentcast_value_listing_comp_count"] = len(value_listing_comps)
    listing_prices = [_number(row.get("listing_price") or row.get("sold_price")) for row in value_listing_comps]
    enriched["rentcast_value_listing_median"] = _round_money(median(listing_prices)) if listing_prices else 0

    recorded_raw, sold_trail, sold_errors = _sold_search(full_address, subject, api_key, session=session)
    recorded_scored, recorded_summary = build_recorded_sold_intelligence(subject, recorded_raw, full_address)
    recorded_summary["search_trail"] = sold_trail
    if sold_errors:
        recorded_summary.setdefault("verification_reasons", []).extend(error for error in sold_errors if error)
    _copy_arv_summary(enriched, recorded_scored, recorded_summary)
    enriched["arv_search_trail"] = sold_trail

    manual_arv = _number(enriched.get("manual_arv_override") or enriched.get("manual_arv"))
    recorded_arv = _number(recorded_summary.get("recommended_arv"))
    avm_value = _number(enriched.get("rentcast_arv"))
    if manual_arv > 0:
        enriched.update({"arv": manual_arv, "arv_source": "Manual Override", "arv_confidence": "Manual"})
    elif recorded_arv > 0:
        enriched.update({
            "arv": recorded_arv,
            "arv_source": "RentCast Recorded Sales",
            "arv_confidence": recorded_summary.get("arv_confidence", "Weak"),
            "arv_fallback_reason": recorded_summary.get("explanation", ""),
        })
    elif avm_value > 0:
        enriched.update({
            "arv": avm_value,
            "arv_source": "RentCast AVM — listing-based",
            "arv_confidence": "AVM only",
            "arv_requires_human_verification": True,
            "arv_verification_reasons": list(dict.fromkeys(
                list(enriched.get("arv_verification_reasons", []) or [])
                + ["No verified public-record closed sales supported the AVM."]
            )),
            "arv_fallback_reason": "RentCast AVM is based on comparable sale listings, not confirmed closed-sale prices.",
        })
    else:
        enriched.update({
            "arv": 0, "arv_source": "Missing", "arv_confidence": "Not enough data",
            "arv_requires_human_verification": True,
        })

    avm_rent = _number(enriched.get("rent") or enriched.get("rent_estimate"))
    initial_rent_comps = [dict(row) for row in (enriched.get("rent_comps") or []) if isinstance(row, dict)]
    rent_analysis = analyze_rent_intelligence(subject, initial_rent_comps, avm_rent)
    rent_trail: list[dict[str, Any]] = [{
        "source": "RentCast rent AVM comparables", "radius": 5, "days": 270,
        "returned": len(initial_rent_comps), "ok": bool(avm_rent or initial_rent_comps),
    }]
    rental_errors: list[str] = []
    if int(rent_analysis.get("verified_rent_comp_count", 0) or 0) < 3 and _canonical_property_type(subject.get("property_type")) != "Land":
        fallback_comps, fallback_trail, rental_errors = _rental_listing_search(
            full_address, subject, api_key, session=session
        )
        rent_trail.extend(fallback_trail)
        rent_analysis = analyze_rent_intelligence(subject, initial_rent_comps + fallback_comps, avm_rent)
    if rental_errors:
        rent_analysis["rent_verification_reasons"] = list(dict.fromkeys(
            list(rent_analysis.get("rent_verification_reasons", []) or [])
            + [error for error in rental_errors if error]
        ))
        rent_analysis["rent_requires_human_verification"] = True

    recommended_rent = _number(rent_analysis.get("recommended_rent"))
    enriched.update({
        "rentcast_rent_avm": avm_rent,
        "rent": recommended_rent or avm_rent,
        "rent_estimate": recommended_rent or avm_rent,
        "rent_comps": rent_analysis.get("rent_comps", []),
        "rent_comp_count": int(rent_analysis.get("rent_comp_count", 0) or 0),
        "verified_rent_comp_count": int(rent_analysis.get("verified_rent_comp_count", 0) or 0),
        "rent_comp_average": _number(rent_analysis.get("rent_comp_average")),
        "rent_comp_median": _number(rent_analysis.get("rent_comp_median")),
        "rent_low": _number(rent_analysis.get("rent_low")) or _number(enriched.get("rent_low")),
        "rent_high": _number(rent_analysis.get("rent_high")) or _number(enriched.get("rent_high")),
        "rent_confidence": rent_analysis.get("rent_confidence", "Missing"),
        "rent_requires_human_verification": bool(rent_analysis.get("rent_requires_human_verification", True)),
        "rent_verification_reasons": list(rent_analysis.get("rent_verification_reasons", []) or []),
        "rent_search_mode": rent_analysis.get("rent_search_mode", "Unavailable"),
        "rent_search_radius": _number(rent_analysis.get("rent_search_radius")),
        "rent_search_days": int(rent_analysis.get("rent_search_days", 0) or 0),
        "rent_search_trail": rent_trail,
        "rent_comp_quality_summary": rent_analysis.get("rent_comp_quality_summary", {}),
        "rent_source": "RentCast Rental Comps" if int(rent_analysis.get("verified_rent_comp_count", 0) or 0) >= 3 else "RentCast Rural Rental Fallback" if rent_analysis.get("rent_comps") else "RentCast AVM only" if avm_rent else "Missing",
        "rent_verification_needed": "Yes" if rent_analysis.get("rent_requires_human_verification", True) else "No",
    })

    enriched["rural_market_detected"] = bool(
        recorded_summary.get("rural_market_detected") or rent_analysis.get("rural_market_detected")
    )
    enriched["rentcast_data_provenance"] = {
        "subject_facts": "RentCast public property record" if facts else "Input/listing facts",
        "arv": enriched.get("arv_source", "Missing"),
        "value_comparable_context": "RentCast sale listings; not treated as closed sales",
        "rent": enriched.get("rent_source", "Missing"),
    }
    enriched["rentcast_request_policy"] = {
        "cache_ttl_hours": CACHE_TTL_SECONDS // 3600,
        "subject_record_cache_hit": property_cache_hit,
        "sold_search": "10 miles / 3 years, expanding to 50 miles / 7 years only when needed",
        "rental_search": "5-mile AVM comps, then active and inactive listings within 50 miles only when needed",
    }
    enriched["rentcast_status"] = "Complete" if enriched.get("rent") or enriched.get("arv") else "No usable data"
    _RESULT_CACHE[_normalize_address(full_address)] = copy.deepcopy(enriched)
    _hydrate_if_available(enriched)
    return enriched
