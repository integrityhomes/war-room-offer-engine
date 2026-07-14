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
    import one_load_sources as base
    import zillow_url_import_safe as zillow_safe
    from zillow_score_patch import safe_score_zillow_row
except ImportError:
    try:
        from . import one_load_sources as base
        from . import zillow_url_import_safe as zillow_safe
        from .zillow_score_patch import safe_score_zillow_row
    except ImportError:
        from war_room_offer_engine import one_load_sources as base
        from war_room_offer_engine import zillow_url_import_safe as zillow_safe
        from war_room_offer_engine.zillow_score_patch import safe_score_zillow_row


# Streamlit can load the same source module through different import paths.
# Bind the safe scorer to the exact module object used by the active importer,
# so formatted Zillow prices such as "$64,900" never reach float() directly.
zillow_safe.base.score_zillow_row = safe_score_zillow_row
base.pull_zillow_listing = zillow_safe.pull_zillow_listing


def normalize_one_load_lead(payload):
    return base.normalize_one_load_lead(payload)


def parse_seller_notes(text):
    return base.parse_seller_notes(text)


def one_load_status_checklist(summary):
    return base.one_load_status_checklist(summary)


def one_load_review_before_offer_checklist():
    return base.one_load_review_before_offer_checklist()
