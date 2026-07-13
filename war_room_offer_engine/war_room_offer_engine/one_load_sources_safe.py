from __future__ import annotations

try:
    import one_load_sources as base
    from zillow_url_import_safe import pull_zillow_listing
except ImportError:
    try:
        from . import one_load_sources as base
        from .zillow_url_import_safe import pull_zillow_listing
    except ImportError:
        from war_room_offer_engine import one_load_sources as base
        from war_room_offer_engine.zillow_url_import_safe import pull_zillow_listing


base.pull_zillow_listing = pull_zillow_listing


def normalize_one_load_lead(payload):
    return base.normalize_one_load_lead(payload)


def parse_seller_notes(text):
    return base.parse_seller_notes(text)


def one_load_status_checklist(summary):
    return base.one_load_status_checklist(summary)


def one_load_review_before_offer_checklist():
    return base.one_load_review_before_offer_checklist()
