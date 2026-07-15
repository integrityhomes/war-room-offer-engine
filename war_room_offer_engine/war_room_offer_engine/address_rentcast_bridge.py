from __future__ import annotations

from typing import Any

try:
    import data_sources as ds
    from rentcast_auto_enrichment import enrich_property_with_rentcast
except ImportError:
    try:
        from . import data_sources as ds
        from .rentcast_auto_enrichment import enrich_property_with_rentcast
    except ImportError:
        from war_room_offer_engine import data_sources as ds
        from war_room_offer_engine.rentcast_auto_enrichment import enrich_property_with_rentcast


_ORIGINAL_LOOKUP_RENTCAST = ds.lookup_rentcast


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _usable_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _property_facts(address: str, api_key: str) -> tuple[dict[str, Any], str]:
    if not api_key or not str(address or "").strip():
        return {}, ""
    try:
        response = ds.requests.get(
            "https://api.rentcast.io/v1/properties",
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
            params={"address": str(address).strip()},
            timeout=25,
        )
    except Exception as exc:
        return {}, f"RentCast property lookup error: {exc}"
    if response.status_code < 200 or response.status_code >= 300:
        return {}, f"RentCast property HTTP {response.status_code}: {response.text[:300]}"
    try:
        payload = response.json()
    except Exception:
        return {}, "RentCast property lookup returned non-JSON data."
    if isinstance(payload, list) and payload:
        record = payload[0]
    elif isinstance(payload, dict):
        record = payload
    else:
        record = {}
    if not isinstance(record, dict):
        return {}, ""
    return {
        "beds": _number(record.get("bedrooms") or record.get("beds")),
        "baths": _number(record.get("bathrooms") or record.get("baths")),
        "sqft": _number(record.get("squareFootage") or record.get("sqft")),
        "year_built": record.get("yearBuilt") or "",
        "property_type": record.get("propertyType") or "",
        "taxes": ds.extract_latest_tax_amount(record.get("propertyTaxes")),
    }, ""


def _enrichment_score(data: dict[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        _usable_count(data.get("rent_comps")),
        1 if _number(data.get("rent") or data.get("rent_estimate")) > 0 else 0,
        _usable_count(data.get("auto_sold_comps") or data.get("rentcast_sold_comps")),
        1 if _number(data.get("auto_recommended_arv")) > 0 else 0,
        1 if _number(data.get("rentcast_arv") or data.get("arv")) > 0 else 0,
    )


def _run_enrichment(address: str, api_key: str, facts: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    subject = {
        "address": str(address or "").strip(),
        "beds": facts.get("beds", 0),
        "baths": facts.get("baths", 0),
        "sqft": facts.get("sqft", 0),
        "property_type": facts.get("property_type", ""),
    }
    first = enrich_property_with_rentcast(subject, api_key, session=ds.requests)
    first_rent_comps = _usable_count(first.get("rent_comps"))
    first_rent = _number(first.get("rent") or first.get("rent_estimate"))

    # RentCast can return no rental result when incorrect/demo bedrooms or square
    # footage are supplied. Retry the exact full address without attribute filters.
    if first_rent > 0 and first_rent_comps > 0:
        return first, False

    retry = enrich_property_with_rentcast(
        {"address": str(address or "").strip()},
        api_key,
        session=ds.requests,
    )
    return (retry, True) if _enrichment_score(retry) > _enrichment_score(first) else (first, False)


def _hydrate_auto_arv_state(st, result: dict[str, Any]) -> None:
    scored = result.get("auto_sold_comps", []) or []
    summary = result.get("auto_arv_summary", {}) or {}
    auto_arv = _number(result.get("auto_recommended_arv") or summary.get("recommended_arv"))

    if not scored and result.get("rentcast_sold_comps"):
        scored = result.get("rentcast_sold_comps", []) or []

    st.session_state["auto_sold_comps"] = scored
    st.session_state["auto_comp_count"] = len(scored)
    st.session_state["auto_comp_source"] = "RentCast"
    st.session_state["auto_arv_summary"] = summary
    st.session_state["auto_recommended_arv"] = int(auto_arv) if auto_arv > 0 else 0
    st.session_state["auto_low_arv"] = int(_number(summary.get("low_arv")))
    st.session_state["auto_conservative_arv"] = int(_number(summary.get("conservative_arv")))
    st.session_state["auto_average_arv"] = int(_number(summary.get("average_arv")))
    st.session_state["auto_high_arv"] = int(_number(summary.get("high_arv")))
    st.session_state["strong_comp_count"] = int(summary.get("strong_comp_count", 0) or 0)
    st.session_state["good_comp_count"] = int(summary.get("good_comp_count", 0) or 0)
    st.session_state["weak_comp_count"] = int(summary.get("weak_comp_count", 0) or 0)
    st.session_state["excluded_comp_count"] = int(summary.get("excluded_comp_count", 0) or 0)
    st.session_state["auto_comp_radius"] = result.get("auto_comp_radius") or summary.get("search_radius") or "1 mile"
    st.session_state["auto_comp_date_range"] = result.get("auto_comp_date_range") or summary.get("date_range") or "Last 12 months"

    if scored:
        st.session_state["auto_comp_messages"] = [
            f"Automatically scored {len(scored)} RentCast sold comparable(s)."
        ]
    if auto_arv > 0:
        st.session_state["arv"] = int(auto_arv)
        st.session_state["arv_source_used"] = "Automatic Sold Comps"
        st.session_state["value_source"] = "Automatic Sold Comps"
        st.session_state["arv_confidence"] = summary.get("arv_confidence", "Weak")


def _hydrate_state(result: dict[str, Any]) -> None:
    try:
        import streamlit as st
    except Exception:
        return

    comps = result.get("rent_comps", []) or []
    sold = result.get("rentcast_sold_comps", []) or []
    rent_count = len(comps)
    sold_count = len(sold)

    st.session_state["rentcast_rent_comps"] = comps
    st.session_state["rent_comps"] = comps
    st.session_state["rentcast_comp_count"] = rent_count
    st.session_state["rentcast_rent_comp_count"] = rent_count
    st.session_state["rent_comp_count"] = rent_count
    st.session_state["rentcast_submitted_address"] = result.get("rentcast_submitted_address", "")
    st.session_state["rentcast_rent_error"] = result.get("rentcast_rent_error", "")
    st.session_state["rentcast_lookup_retry_used"] = result.get("rentcast_lookup_retry_used", False)

    if result.get("rent"):
        st.session_state["rent"] = int(_number(result.get("rent")))
        st.session_state["rent_source"] = "RentCast"
    if rent_count >= 3:
        st.session_state["rent_verification_needed"] = "No"
        st.session_state["rent_confidence"] = "Strong verified rent comps"
        st.session_state["rental_demand_confidence"] = "Strong rent comps"
    elif result.get("rent"):
        st.session_state["rent_verification_needed"] = "Yes"
        st.session_state["rent_confidence"] = "Medium fallback comps"

    st.session_state["rentcast_sold_comps"] = sold
    st.session_state["rentcast_sold_comp_count"] = sold_count
    st.session_state["rentcast_value_comp_count"] = sold_count
    st.session_state["rentcast_value_error"] = result.get("rentcast_value_error", "")
    if result.get("rentcast_arv"):
        st.session_state["rentcast_arv"] = int(_number(result.get("rentcast_arv")))

    _hydrate_auto_arv_state(st, result)

    if not st.session_state.get("auto_recommended_arv") and result.get("rentcast_arv"):
        st.session_state["arv"] = int(_number(result.get("rentcast_arv")))
        st.session_state["arv_source_used"] = result.get("arv_source", "RentCast AVM")
        st.session_state["value_source"] = result.get("arv_source", "RentCast AVM")
        st.session_state["arv_confidence"] = result.get("arv_confidence", "AVM only")


def lookup_rentcast_with_full_enrichment(
    address: str,
    beds: float = 0,
    baths: float = 0,
    sqft: float = 0,
) -> dict[str, Any]:
    submitted_address = str(address or "").strip()
    api_key = ds.get_secret("RENTCAST_API_KEY", "")
    if not api_key:
        return {
            "source": "RentCast",
            "found": False,
            "rent": 0,
            "rent_source": "Missing / RentCast unavailable",
            "rent_confidence": "Weak",
            "rent_comps": [],
            "rent_comp_count": 0,
            "rentcast_sold_comps": [],
            "rentcast_sold_comp_count": 0,
            "auto_sold_comps": [],
            "auto_arv_summary": {},
            "auto_recommended_arv": 0,
            "rentcast_submitted_address": submitted_address,
            "rentcast_rent_error": "Missing RentCast API key.",
            "notes": "Missing RentCast API key.",
        }

    facts, property_error = _property_facts(submitted_address, api_key)
    # Prefer RentCast's subject facts. Fall back to user/app values only when the
    # property endpoint did not return a field.
    facts["beds"] = facts.get("beds") or _number(beds)
    facts["baths"] = facts.get("baths") or _number(baths)
    facts["sqft"] = facts.get("sqft") or _number(sqft)

    enriched, retry_used = _run_enrichment(submitted_address, api_key, facts)
    rent_comps = enriched.get("rent_comps", []) or []
    sold_comps = enriched.get("rentcast_sold_comps", []) or []
    scored_comps = enriched.get("auto_sold_comps", []) or []
    auto_summary = enriched.get("auto_arv_summary", {}) or {}
    rent = _number(enriched.get("rent") or enriched.get("rent_estimate"))
    rentcast_avm = _number(enriched.get("rentcast_arv"))
    resolved_arv = _number(enriched.get("arv") or enriched.get("auto_recommended_arv") or rentcast_avm)

    result = {
        "source": "RentCast",
        "found": bool(rent or resolved_arv or rent_comps or sold_comps or any(facts.values())),
        "rent": rent,
        "rent_source": "RentCast" if rent else "Missing / RentCast unavailable",
        "rent_confidence": "Strong verified rent comps" if len(rent_comps) >= 3 else "Medium fallback comps" if rent else "Weak",
        "rent_comps": rent_comps,
        "rent_comp_count": len(rent_comps),
        "rent_comp_average": enriched.get("rent_comp_average", 0),
        "rent_comp_median": enriched.get("rent_comp_median", 0),
        "rent_low": enriched.get("rent_low", 0),
        "rent_high": enriched.get("rent_high", 0),
        "rentcast_submitted_address": enriched.get("rentcast_submitted_address") or submitted_address,
        "rentcast_rent_error": enriched.get("rentcast_rent_error", ""),
        "rentcast_lookup_retry_used": retry_used,
        "rentcast_arv": rentcast_avm,
        "arv": resolved_arv,
        "arv_source": enriched.get("arv_source", "Automatic Sold Comps" if _number(enriched.get("auto_recommended_arv")) else "RentCast AVM only" if rentcast_avm else ""),
        "arv_confidence": enriched.get("arv_confidence", auto_summary.get("arv_confidence", "AVM only" if rentcast_avm else "Not enough data")),
        "rentcast_sold_comps": sold_comps,
        "rentcast_sold_comp_count": len(sold_comps),
        "auto_sold_comps": scored_comps,
        "auto_comp_count": len(scored_comps),
        "auto_arv_summary": auto_summary,
        "auto_recommended_arv": enriched.get("auto_recommended_arv", 0),
        "auto_low_arv": enriched.get("auto_low_arv", 0),
        "auto_conservative_arv": enriched.get("auto_conservative_arv", 0),
        "auto_average_arv": enriched.get("auto_average_arv", 0),
        "auto_high_arv": enriched.get("auto_high_arv", 0),
        "strong_comp_count": enriched.get("strong_comp_count", 0),
        "good_comp_count": enriched.get("good_comp_count", 0),
        "weak_comp_count": enriched.get("weak_comp_count", 0),
        "excluded_comp_count": enriched.get("excluded_comp_count", 0),
        "auto_comp_radius": enriched.get("auto_comp_radius", auto_summary.get("search_radius", "1 mile")),
        "auto_comp_date_range": enriched.get("auto_comp_date_range", auto_summary.get("date_range", "Last 12 months")),
        "rentcast_value_error": enriched.get("rentcast_value_error", ""),
        "beds": facts.get("beds", 0),
        "baths": facts.get("baths", 0),
        "sqft": facts.get("sqft", 0),
        "taxes": facts.get("taxes", 0),
        "year_built": facts.get("year_built", ""),
        "property_type": facts.get("property_type", ""),
    }

    note_parts = [f"Address submitted: {result['rentcast_submitted_address']}"]
    if retry_used:
        note_parts.append("Address-only retry used")
    note_parts.append(f"Rent: {int(rent) if rent else 0}")
    note_parts.append(f"Rental comps: {len(rent_comps)}")
    note_parts.append(f"RentCast AVM: {int(rentcast_avm) if rentcast_avm else 0}")
    note_parts.append(f"Sold comps returned: {len(sold_comps)}")
    note_parts.append(f"Sold comps scored: {len(scored_comps)}")
    note_parts.append(f"Automatic ARV: {int(_number(result.get('auto_recommended_arv'))) if result.get('auto_recommended_arv') else 0}")
    for error in [property_error, result.get("rentcast_rent_error"), result.get("rentcast_value_error")]:
        if error:
            note_parts.append(str(error))
    result["notes"] = "RentCast full address lookup | " + " | ".join(note_parts)

    _hydrate_state(result)
    return result


# fetch_all_sources resolves this global at call time, so this also upgrades the
# existing Pull Data and Deal Decision address workflows without replacing them.
ds.lookup_rentcast = lookup_rentcast_with_full_enrichment
