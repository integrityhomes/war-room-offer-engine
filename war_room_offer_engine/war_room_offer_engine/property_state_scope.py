from __future__ import annotations

from typing import Any, Iterable


# Browser-session and workspace preferences survive both Start New Property and
# automatic cleanup when a teammate types a different property. These keys are
# preserved by omission: reset code must never rewrite them after widgets exist.
SESSION_PREFERENCE_KEYS = {
    "team_operator_name",
    "team_operator_selection",
    "team_operator_custom_name",
    "war_room_active_section",
    "deal_library_auto_save",
    "deal_library_search",
    "deal_library_search_results",
    "rentcast_intelligence_preview_enabled",
    "show_full_repair_math",
}


# Inputs already visible in the Deal Decision Center are preserved only during
# automatic cross-property cleanup. Start New Property clears them.
CURRENT_INPUT_KEYS = {
    "decision_property_input",
    "decision_strategy",
    "decision_lead_source",
    "decision_asking_price",
    "decision_current_negotiated_price",
    "decision_latest_counter",
    "decision_seller_bottom_line",
    "decision_negotiation_status",
    "decision_negotiated_with",
    "decision_last_negotiation",
    "decision_next_follow_up",
    "decision_negotiation_notes",
    "decision_other_terms",
    "decision_media",
    "one_load_input_method",
    "one_load_property_address",
    "one_load_listing_url",
    "one_load_lead_type",
    "one_load_lead_source",
    "one_load_asking_price",
    "one_load_seller_desired_price",
    "one_load_contact_name",
    "one_load_contact_phone",
    "one_load_contact_email",
    "one_load_seller_notes",
    "one_load_repairs_mentioned",
    "one_load_motivation_notes",
    "one_load_timeline",
    "one_load_access_notes",
    "one_load_occupancy",
    "deal_library_force_refresh",
    "rentcast_credit_guard_refresh_confirmed",
}


# Property-scoped families. Prefixes are intentionally limited so global offer
# assumptions such as slow_flip_rent_multiple, wholesale_buyer_percent_arv,
# min_assignment_fee, and close_title_buffer are never removed.
PROPERTY_PREFIXES = (
    "rentcast_",
    "rent_",
    "arv_",
    "auto_",
    "location_",
    "requested_property_",
    "resolved_property_",
    "one_load_",
    "decision_",
    "seller_",
    "listing_",
    "owner_",
    "apify_",
    "buyer_",
    "buyers_",
    "dispo_",
    "deal_library_",
    "deal_protection_",
    "contract_",
    "pre_contract_",
    "under_contract_",
    "address_sharing_",
    "listing_source_sharing_",
    "repair_",
    "manual_",
    "comp_",
    "strong_comp_",
    "good_comp_",
    "weak_comp_",
    "excluded_comp_",
    "value_",
    "data_intake_",
    "market_",
    "mold_",
    "property_",
    "exit_",
    "wholesale_exit_",
    "slow_flip_exit_",
    "overall_exit_",
    "recommended_exit_",
    "backup_exit_",
    "confirmed_buyer_",
    "exact_address_",
    "protected_",
    "internal_team_",
    "zillow_",
    "recorded_",
    "sold_",
    "subject_",
    "geo_",
    "geocode_",
    "rental_",
    "county_",
    "field_source_",
)


PROPERTY_EXACT_KEYS = {
    "address",
    "city",
    "state",
    "zip",
    "market",
    "county",
    "latitude",
    "longitude",
    "beds",
    "baths",
    "sqft",
    "lot_size",
    "year_built",
    "property_type",
    "taxes",
    "tax_assessed_value",
    "last_sale_date",
    "last_sale_price",
    "assessor_id",
    "subdivision",
    "zoning",
    "hoa_fee",
    "hoa_frequency",
    "status",
    "days_on_market",
    "occupancy",
    "livable",
    "lead_source",
    "lead_type",
    "source_mode",
    "asking_price",
    "contract_price",
    "rent",
    "rent_estimate",
    "arv",
    "sheet_arv",
    "repairs",
    "notes",
    "last_source_results",
    "last_auto_pull",
    "field_source_map_json",
    "deal_offer_made_by",
    "decision_offer_made_by",
    "stability_analysis_property_key",
    "stability_last_run_ok",
    "stability_last_run_message",
    "stability_analysis_is_stale",
    # Property-scoped controls/results whose names do not fit a safe prefix.
    "use_auto_arv_over_manual_comps",
    "best_buyer_feedback",
    "wholesale_buyer_list_strength",
    "slow_flip_buyer_demand",
    "slow_flip_buyer_message",
    "slow_flip_rent_risk",
}


def is_property_state_key(key: Any) -> bool:
    text = str(key or "")
    return text in PROPERTY_EXACT_KEYS or text.startswith(PROPERTY_PREFIXES)


def preserved_keys(*, preserve_current_inputs: bool) -> set[str]:
    result = set(SESSION_PREFERENCE_KEYS)
    if preserve_current_inputs:
        result.update(CURRENT_INPUT_KEYS)
    return result


def clear_property_state(state: Any, *, preserve_current_inputs: bool) -> list[str]:
    """Delete one property's state without assigning any preserved widget key."""
    if not hasattr(state, "get") or not hasattr(state, "keys"):
        return []

    preserve = preserved_keys(preserve_current_inputs=preserve_current_inputs)
    removed: list[str] = []
    for key in list(state.keys()):
        text = str(key)
        if text in preserve:
            continue
        if is_property_state_key(text):
            state.pop(key, None)
            removed.append(text)
    return removed


def unclassified_keys(keys: Iterable[Any]) -> list[str]:
    """Return keys that are neither property-scoped nor declared preferences."""
    result: list[str] = []
    for key in keys:
        text = str(key)
        if text in SESSION_PREFERENCE_KEYS or is_property_state_key(text):
            continue
        result.append(text)
    return result
