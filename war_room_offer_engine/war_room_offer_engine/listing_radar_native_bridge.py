from __future__ import annotations

try:
    import listing_radar_integration as integration
except ImportError:
    try:
        from . import listing_radar_integration as integration
    except ImportError:
        from war_room_offer_engine import listing_radar_integration as integration


_PRESERVED_RADAR_KEYS = set(integration._FILTER_KEYS)
_CURRENT_HANDOFF_KEYS = {
    integration.ANALYSIS_RECORD_KEY,
    integration.SELECTED_KEY,
    integration.MARKET_KEY,
    integration.HANDOFF_MESSAGE_KEY,
    integration.HANDOFF_ERROR_KEY,
}


def _patch_stability_contract() -> bool:
    try:
        import production_stability as stability
    except ImportError:
        try:
            from . import production_stability as stability
        except ImportError:
            from war_room_offer_engine import production_stability as stability

    preferences = getattr(stability, "_SESSION_PREFERENCE_KEYS", None)
    current_inputs = getattr(stability, "_CURRENT_INPUT_KEYS", None)
    if not isinstance(preferences, set) or not isinstance(current_inputs, set):
        return False

    # Search/filter state follows the teammate across properties. The selected
    # listing record survives only automatic cross-property cleanup long enough
    # for One-Load to consume it; Start New Property still removes it.
    preferences.update(_PRESERVED_RADAR_KEYS)
    current_inputs.update(_CURRENT_HANDOFF_KEYS)
    return True


def install() -> bool:
    integration.install()
    _patch_stability_contract()
    return True
