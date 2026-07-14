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


zillow_safe.base.score_zillow_row = safe_score_zillow_row
_original_safe_zillow_pull = zillow_safe.pull_zillow_listing


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
    return base.normalize_one_load_lead(payload)


def parse_seller_notes(text):
    return base.parse_seller_notes(text)


def one_load_status_checklist(summary):
    return base.one_load_status_checklist(summary)


def one_load_review_before_offer_checklist():
    return base.one_load_review_before_offer_checklist()
