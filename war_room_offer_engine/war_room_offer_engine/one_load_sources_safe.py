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
    import address_rentcast_bridge  # noqa: F401 - make plain addresses use the same full RentCast enrichment as listing URLs
except ImportError:
    try:
        from . import address_rentcast_bridge  # noqa: F401
    except ImportError:
        from war_room_offer_engine import address_rentcast_bridge  # noqa: F401

try:
    import rentcast_state_bootstrap  # noqa: F401 - hydrate RentCast rent, scored sold comps and automatic ARV into workspace state
except ImportError:
    try:
        from . import rentcast_state_bootstrap  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_state_bootstrap  # noqa: F401

try:
    import rentcast_comp_normalization_fix  # noqa: F401 - remove subject comps, support date-unverified value comps and hydrate rent statistics
except ImportError:
    try:
        from . import rentcast_comp_normalization_fix  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_comp_normalization_fix  # noqa: F401

try:
    import rentcast_intelligence_preview as preview_control  # noqa: F401 - keep PR #67 off by default and expose a session-only test switch
except ImportError:
    try:
        from . import rentcast_intelligence_preview as preview_control  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_preview as preview_control  # noqa: F401

try:
    import rentcast_property_intelligence as property_intelligence  # noqa: F401 - recorded-sale ARV, rural rental comps, provenance and confidence safeguards
except ImportError:
    try:
        from . import rentcast_property_intelligence as property_intelligence  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_property_intelligence as property_intelligence  # noqa: F401

try:
    import rentcast_intelligence_quality_hardening as intelligence_quality  # noqa: F401 - keep transaction pairs intact and stop weak evidence from moving primary rent or ARV
except ImportError:
    try:
        from . import rentcast_intelligence_quality_hardening as intelligence_quality  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_quality_hardening as intelligence_quality  # noqa: F401

try:
    import rentcast_intelligence_comps_ui_fix as intelligence_comps_ui  # noqa: F401 - preserve recorded-sale confidence and adaptive search details in Comps / ARV
except ImportError:
    try:
        from . import rentcast_intelligence_comps_ui_fix as intelligence_comps_ui  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_comps_ui_fix as intelligence_comps_ui  # noqa: F401

try:
    import rentcast_intelligence_rent_ui_fix as intelligence_rent_ui  # noqa: F401 - separate total rural rental listings from verified rent support
except ImportError:
    try:
        from . import rentcast_intelligence_rent_ui_fix as intelligence_rent_ui  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_rent_ui_fix as intelligence_rent_ui  # noqa: F401

try:
    import rentcast_intelligence_rent_reconciliation as rent_reconciliation  # noqa: F401 - derive counts, confidence and metrics from selected rural evidence
except ImportError:
    try:
        from . import rentcast_intelligence_rent_reconciliation as rent_reconciliation  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_intelligence_rent_reconciliation as rent_reconciliation  # noqa: F401

intelligence_quality.install()
intelligence_comps_ui.install()
intelligence_rent_ui.install()
rent_reconciliation.install()
preview_control.install_dispatch_gate(property_intelligence)

# Install credit counting only after the preview dispatch gate is complete so the
# guard can distinguish the production path from the rural-intelligence path.
try:
    import rentcast_credit_guard as credit_guard  # noqa: F401 - estimate, count and cap paid RentCast requests
except ImportError:
    try:
        from . import rentcast_credit_guard as credit_guard  # noqa: F401
    except ImportError:
        from war_room_offer_engine import rentcast_credit_guard as credit_guard  # noqa: F401

credit_guard.install()

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


zillow_safe.base.score_zillow_row = safe_score_zillow_row
_original_safe_zillow_pull = zillow_safe.pull_zillow_listing
_original_normalize_one_load_lead = base.normalize_one_load_lead


def pull_zillow_listing_with_rentcast(listing_url: str, address: str = "", limit: int = 10):
    result = _original_safe_zillow_pull(listing_url, address=address, limit=limit)
    if not isinstance(result, dict) or not result.get("ok"):
        return result
    record = dict(result.get("record", {}) or {})
    api_key = get_secret("RENTCAST_API_KEY", "")
    enriched = enrich_property_with_rentcast(record, api_key)
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
    summary = _original_normalize_one_load_lead(payload)
    if not preview_control.preview_enabled():
        return summary
    record = payload.get("record", {}) if isinstance(payload, dict) and isinstance(payload.get("record", {}), dict) else {}
    data = summary.get("data", {}) if isinstance(summary, dict) else {}
    if record and isinstance(data, dict):
        intelligence_keys = set(property_intelligence.INTELLIGENCE_STATE_KEYS) | {
            "rent", "rent_estimate", "rent_source", "rent_confidence", "rent_verification_needed",
            "rent_comps", "rent_comp_count", "rent_comp_average", "rent_comp_median", "rent_low", "rent_high",
            "rentcast_rent_comps", "rentcast_rent_comp_count", "rentcast_comp_count",
            "arv", "arv_source", "arv_confidence", "arv_fallback_reason", "rentcast_arv",
            "rentcast_sold_comps", "rentcast_sold_comp_count", "rentcast_value_comp_count",
            "auto_sold_comps", "auto_comp_count", "auto_arv_summary", "auto_recommended_arv",
            "auto_low_arv", "auto_conservative_arv", "auto_average_arv", "auto_high_arv",
            "strong_comp_count", "good_comp_count", "weak_comp_count", "excluded_comp_count",
            "auto_comp_radius", "auto_comp_date_range", "taxes", "tax_assessed_value",
            "last_sale_date", "last_sale_price", "county", "latitude", "longitude",
            "assessor_id", "subdivision", "zoning", "hoa_fee", "hoa_frequency",
        }
        for key in intelligence_keys:
            if key in record:
                data[key] = record.get(key)
        summary["data"] = data
        summary["arv_source"] = record.get("arv_source") or summary.get("arv_source", "Missing")
        summary["arv_confidence"] = record.get("arv_confidence") or summary.get("arv_confidence", "Not enough data")
        summary["rent_confidence"] = record.get("rent_confidence") or summary.get("rent_confidence", "Weak")
        summary["status_checklist"] = base.one_load_status_checklist(summary)
    return summary


base.normalize_one_load_lead = normalize_one_load_lead
try:
    import sys
    for module_name in [
        "ui_sections.one_load_deal_ui",
        "war_room_offer_engine.ui_sections.one_load_deal_ui",
    ]:
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.normalize_one_load_lead = normalize_one_load_lead
except Exception:
    pass


def parse_seller_notes(text):
    return base.parse_seller_notes(text)


def one_load_status_checklist(summary):
    return base.one_load_status_checklist(summary)


def one_load_review_before_offer_checklist():
    return base.one_load_review_before_offer_checklist()
