from __future__ import annotations

try:
    import hide_floating_quick_tools  # noqa: F401 - keep sidebar navigation, remove right-side floating panel
except ImportError:
    try:
        from . import hide_floating_quick_tools  # noqa: F401
    except ImportError:
        from war_room_offer_engine import hide_floating_quick_tools  # noqa: F401

try:
    import single_section_workspace  # noqa: F401 - show one selected War Room section at a time
except ImportError:
    try:
        from . import single_section_workspace  # noqa: F401
    except ImportError:
        from war_room_offer_engine import single_section_workspace  # noqa: F401

try:
    import rentcast_state_bootstrap  # noqa: F401 - hydrate RentCast rent and sold comps into workspace state
except ImportError:
    try:
        from . import rentcast_state_bootstrap  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_state_bootstrap  # noqa: F401

try:
    import one_load_sources as base
    import zillow_url_import_safe as zillow_safe
    from data_sources import get_secret
    from rentcast_auto_enrichment import enrich_property_with_rentcast
    from zillow_score_patch import safe_score_zillow_row
except ImportError:
    try:
        from . import one_load_sources as base
        from . import zillow_url_import_safe as zillow_safe
        from .data_sources import get_secret
        from .rentcast_auto_enrichment import enrich_property_with_rentcast
        from .zillow_score_patch import safe_score_zillow_row
    except ImportError:
        from war_room_offer_engine import one_load_sources as base
        from war_room_offer_engine import zillow_url_import_safe as zillow_safe
        from war_room_offer_engine.data_sources import get_secret
        from war_room_offer_engine.rentcast_auto_enrichment import enrich_property_with_rentcast
        from war_room_offer_engine.zillow_score_patch import safe_score_zillow_row


RENTCAST_EXTRA_KEYS = [
    "rent",
    "rent_estimate",
    "rent_low",
    "rent_high",
    "rent_comps",
    "rent_comp_count",
    "rent_comp_average",
    "rent_comp_median",
    "rent_source",
    "rent_confidence",
    "rentcast_submitted_address",
    "rentcast_rent_error",
    "rentcast_arv",
    "rentcast_sold_comps",
    "rentcast_sold_comp_count",
    "rentcast_value_error",
    "rentcast_status",
    "arv",
    "arv_source",
    "arv_confidence",
]


zillow_safe.base.score_zillow_row = safe_score_zillow_row
_original_safe_zillow_pull = zillow_safe.pull_zillow_listing
_last_enriched_record: dict = {}


def _number(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _sync_rentcast_state(record: dict) -> None:
    try:
        import streamlit as st
    except Exception:
        return

    rent_comps = [item for item in (record.get("rent_comps", []) or []) if isinstance(item, dict)]
    rent_count = max(len(rent_comps), int(_number(record.get("rent_comp_count"))))
    rent = int(_number(record.get("rent") or record.get("rent_estimate")))
    rent_confidence = str(record.get("rent_confidence") or "")

    st.session_state["rentcast_rent_comps"] = rent_comps
    st.session_state["rentcast_rent_comp_count"] = rent_count
    st.session_state["rentcast_comp_count"] = rent_count
    st.session_state["rent_comp_count"] = rent_count
    st.session_state["rentcast_submitted_address"] = record.get("rentcast_submitted_address", "")
    st.session_state["rentcast_rent_error"] = record.get("rentcast_rent_error", "")

    if rent > 0:
        st.session_state["rent"] = rent
        st.session_state["rent_source"] = "RentCast"
        st.session_state["rent_confidence"] = (
            "Strong verified rent comps"
            if rent_count >= 3
            else rent_confidence or "Medium fallback comps"
        )
        st.session_state["rent_verification_needed"] = "No" if rent_count >= 3 else "Yes"

    sold_comps = [item for item in (record.get("rentcast_sold_comps", []) or []) if isinstance(item, dict)]
    sold_count = max(len(sold_comps), int(_number(record.get("rentcast_sold_comp_count"))))
    st.session_state["rentcast_sold_comps"] = sold_comps
    st.session_state["rentcast_sold_comp_count"] = sold_count
    st.session_state["rentcast_value_comp_count"] = sold_count
    if sold_comps:
        st.session_state["auto_sold_comps"] = sold_comps
        st.session_state["auto_comp_source"] = "RentCast"
    if _number(record.get("rentcast_arv")) > 0:
        st.session_state["rentcast_arv"] = int(_number(record.get("rentcast_arv")))
        st.session_state["arv_source_used"] = record.get("arv_source", "RentCast")
        st.session_state["arv_confidence"] = record.get("arv_confidence", "AVM only")


def pull_zillow_listing_with_rentcast(listing_url: str, address: str = "", limit: int = 10):
    global _last_enriched_record
    result = _original_safe_zillow_pull(listing_url, address=address, limit=limit)
    if not isinstance(result, dict) or not result.get("ok"):
        _last_enriched_record = {}
        return result
    record = dict(result.get("record", {}) or {})
    api_key = get_secret("RENTCAST_API_KEY", "")
    enriched = enrich_property_with_rentcast(record, api_key)
    _last_enriched_record = dict(enriched)
    _sync_rentcast_state(enriched)
    result = dict(result)
    result["record"] = enriched
    result.setdefault("warnings", [])
    if enriched.get("rentcast_rent_error"):
        result["warnings"].append(enriched["rentcast_rent_error"])
    if enriched.get("rentcast_value_error"):
        result["warnings"].append(enriched["rentcast_value_error"])
    return result


zillow_safe.pull_zillow_listing = pull_zillow_listing_with_rentcast
base.pull_zillow_listing = pull_zillow_listing_with_rentcast


def normalize_one_load_lead(payload):
    global _last_enriched_record
    _last_enriched_record = {}
    summary = base.normalize_one_load_lead(payload)
    source_record = payload.get("record", {}) if isinstance(payload, dict) else {}
    if not isinstance(source_record, dict) or not source_record:
        source_record = _last_enriched_record
    if not isinstance(summary, dict) or not isinstance(source_record, dict):
        return summary

    data = summary.setdefault("data", {})
    if not isinstance(data, dict):
        data = {}
        summary["data"] = data
    for key in RENTCAST_EXTRA_KEYS:
        value = source_record.get(key)
        if value not in [None, "", [], {}]:
            data[key] = value
    _sync_rentcast_state(data)

    rent_count = max(
        len(data.get("rent_comps", []) or []),
        int(_number(data.get("rent_comp_count"))),
    )
    if rent_count >= 3:
        summary["rent_confidence"] = "Strong verified rent comps"
        missing = list(summary.get("missing_critical_fields", []) or [])
        summary["missing_critical_fields"] = [item for item in missing if str(item).lower() != "rent"]
    return summary


def parse_seller_notes(text):
    return base.parse_seller_notes(text)


def one_load_status_checklist(summary):
    return base.one_load_status_checklist(summary)


def one_load_review_before_offer_checklist():
    return base.one_load_review_before_offer_checklist()
