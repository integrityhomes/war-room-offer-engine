from __future__ import annotations

try:
    from data_sources import fetch_universal_apify_dataset
    from one_load_sources import normalize_one_load_lead
except ImportError:
    try:
        from ..data_sources import fetch_universal_apify_dataset
        from ..one_load_sources import normalize_one_load_lead
    except ImportError:
        from war_room_offer_engine.data_sources import fetch_universal_apify_dataset
        from war_room_offer_engine.one_load_sources import normalize_one_load_lead

try:
    from ui_sections.realtor_outreach_ui import render_realtor_outreach_panel
except ImportError:
    try:
        from .realtor_outreach_ui import render_realtor_outreach_panel
    except ImportError:
        from war_room_offer_engine.ui_sections.realtor_outreach_ui import render_realtor_outreach_panel


ONE_LOAD_FIELD_MAP = {
    "address": "address",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "market": "market",
    "property_type": "property_type",
    "beds": "beds",
    "baths": "baths",
    "sqft": "sqft",
    "lot_size": "lot_size",
    "year_built": "year_built",
    "asking_price": "asking_price",
    "status": "status",
    "days_on_market": "days_on_market",
    "listing_url": "listing_url",
    "listing_agent_name": "listing_agent_name",
    "listing_agent_phone": "listing_agent_phone",
    "listing_agent_email": "listing_agent_email",
    "listing_brokerage": "listing_brokerage",
    "sheet_arv": "sheet_arv",
    "rent": "rent",
    "tax_assessed_value": "tax_assessed_value",
    "taxes": "taxes",
    "last_sale_date": "last_sale_date",
    "last_sale_price": "last_sale_price",
    "occupancy": "occupancy",
}

ONE_LOAD_DEFAULTS = {
    "address": "",
    "city": "",
    "state": "",
    "zip": "",
    "market": "",
    "asking_price": 35000,
    "contract_price": 0,
    "rent": 900,
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
    "status": "Unknown",
    "occupancy": "Unknown",
    "lead_type": "Agent",
    "days_on_market": 0,
}

ONE_LOAD_DEMO_VALUES = {
    "address": {"123 Main St", "123 Main St, Decatur IL 62522"},
    "city": {"Decatur"},
    "state": {"IL"},
    "market": {"Decatur IL", "Decatur, IL"},
    "asking_price": {0, 35000},
    "contract_price": {0, 35000},
    "rent": {0, 900, 1120},
    "beds": {0, 2, 2.0, 3, 3.0},
    "baths": {0, 1, 1.0},
    "sqft": {0, 1000},
    "taxes": {0},
    "tax_assessed_value": {0},
    "days_on_market": {0},
    "lead_type": {"Agent", "Unknown"},
    "status": {"Unknown"},
    "occupancy": {"Unknown"},
    "livable": {"Unknown"},
}

ONE_LOAD_WIDGET_DEFAULTS = {
    "one_load_lead_type": "On-market listing",
    "one_load_lead_source": "Zillow",
    "one_load_input_method": "Property address",
    "one_load_property_address": "",
    "one_load_listing_url": "",
    "one_load_apify_dataset": "",
    "one_load_asking_price": 0,
    "one_load_seller_desired_price": 0,
    "one_load_mortgage_balance": 0,
    "one_load_contact_name": "",
    "one_load_contact_phone": "",
    "one_load_contact_email": "",
    "one_load_pasted_listing_text": "",
    "one_load_seller_notes": "",
    "one_load_motivation_notes": "",
    "one_load_timeline": "",
    "one_load_repairs_mentioned": "",
    "one_load_access_notes": "",
    "one_load_occupancy": "Unknown",
}


_MISSING_DEFAULT = object()


def _is_blank_or_zero(value) -> bool:
    return value in [None, "", 0, 0.0, [], {}]


def _is_demo_value(state_key: str, value) -> bool:
    if _is_blank_or_zero(value):
        return True
    default_value = ONE_LOAD_DEFAULTS.get(state_key, _MISSING_DEFAULT)
    if default_value is not _MISSING_DEFAULT and str(value).strip().lower() == str(default_value).strip().lower():
        return True
    demo_values = ONE_LOAD_DEMO_VALUES.get(state_key, set())
    return any(str(value).strip().lower() == str(demo).strip().lower() for demo in demo_values)


def initialize_one_load_defaults(st) -> None:
    legacy_key_map = {
        "one_load_apify_dataset_id": "one_load_apify_dataset",
        "one_load_listing_text": "one_load_pasted_listing_text",
    }
    for legacy_key, new_key in legacy_key_map.items():
        if new_key not in st.session_state and st.session_state.get(legacy_key) not in [None, ""]:
            st.session_state[new_key] = st.session_state.get(legacy_key)
    for key, value in ONE_LOAD_WIDGET_DEFAULTS.items():
        st.session_state.setdefault(key, value)


def _state_has_manual_value(st, key: str) -> bool:
    value = st.session_state.get(key)
    if _is_blank_or_zero(value):
        return False
    if _is_demo_value(key, value):
        return False
    return True


def _one_load_main_lead_type(lead_type: str) -> str:
    lead_type_text = str(lead_type or "").lower()
    if "off-market" in lead_type_text or "seller" in lead_type_text:
        return "Seller"
    if "agent" in lead_type_text or "mls" in lead_type_text:
        return "Agent"
    if "manual" in lead_type_text:
        return "Manual"
    return "Agent"


def _coerce_one_load_value(state_key: str, value):
    if value in [None, "", [], {}]:
        return value
    if state_key in ["asking_price", "contract_price", "rent", "sqft", "days_on_market", "sheet_arv", "taxes", "tax_assessed_value", "last_sale_price"]:
        return int(float(value or 0))
    if state_key in ["beds", "baths"]:
        return float(value or 0)
    return str(value) if not isinstance(value, str) else value


def _field_changed_after_one_load(st, state_key: str) -> bool:
    applied_values = st.session_state.get("one_load_applied_values", {}) or {}
    if state_key not in applied_values:
        return False
    current = st.session_state.get(state_key)
    return str(current) != str(applied_values.get(state_key))


def _build_one_load_analyzer_values(normalized: dict) -> dict:
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    seller = normalized.get("seller", {}) if isinstance(normalized, dict) else {}
    asking_price = data.get("asking_price", 0)
    repair_notes = seller.get("seller_repair_notes", "")
    seller_notes = "\n".join(
        part
        for part in [
            seller.get("seller_condition_notes", ""),
            seller.get("seller_motivation", ""),
            seller.get("seller_timeline", ""),
            seller.get("access_notes", ""),
        ]
        if str(part or "").strip()
    )
    values = {
        "address": data.get("address"),
        "city": data.get("city"),
        "market": data.get("market") or data.get("city"),
        "state": data.get("state"),
        "zip": data.get("zip"),
        "asking_price": asking_price,
        "contract_price": asking_price,
        "beds": data.get("beds"),
        "baths": data.get("baths"),
        "sqft": data.get("sqft"),
        "rent": data.get("rent"),
        "taxes": data.get("taxes"),
        "tax_assessed_value": data.get("tax_assessed_value"),
        "listing_url": data.get("listing_url"),
        "lead_type": _one_load_main_lead_type(normalized.get("lead_type", "")),
        "status": data.get("status"),
        "days_on_market": data.get("days_on_market"),
        "occupancy": data.get("occupancy") or seller.get("occupancy"),
        "livable": "Unknown",
        "listing_agent_name": data.get("listing_agent_name") or seller.get("seller_name"),
        "listing_agent_phone": data.get("listing_agent_phone") or seller.get("seller_phone"),
        "listing_agent_email": data.get("listing_agent_email") or seller.get("seller_email"),
        "repair_notes": repair_notes,
        "notes": seller_notes,
    }
    return {key: value for key, value in values.items() if not _is_blank_or_zero(value)}


def apply_one_load_import(st, normalized: dict, force: bool = False, overwrite_demo_values: bool = True) -> tuple[list[str], list[str], list[str]]:
    analyzer_values = _build_one_load_analyzer_values(normalized)
    imported = []
    skipped = []
    overwritten_defaults = []
    conflicts = list(normalized.get("warnings", []) or [])
    field_sources = dict(st.session_state.get("apify_field_sources", {}) or {})
    source = normalized.get("lead_source", "One-Load Deal Analyzer")
    applied_values = dict(st.session_state.get("one_load_applied_values", {}) or {})
    for state_key, value in analyzer_values.items():
        if _is_blank_or_zero(value):
            continue
        value = _coerce_one_load_value(state_key, value)
        current = st.session_state.get(state_key)
        if not force and _field_changed_after_one_load(st, state_key):
            skipped.append(state_key)
            if state_key == "beds":
                conflicts.append("Bed count conflict")
            elif state_key == "baths":
                conflicts.append("Bath count conflict")
            continue
        if not force and _state_has_manual_value(st, state_key):
            skipped.append(state_key)
            continue
        if _is_demo_value(state_key, current):
            if not overwrite_demo_values and not _is_blank_or_zero(current):
                skipped.append(state_key)
                continue
            if not _is_blank_or_zero(current):
                overwritten_defaults.append(state_key)
        st.session_state[state_key] = value
        imported.append(state_key)
        applied_values[state_key] = value
        field_sources[state_key] = source
    st.session_state["apify_field_sources"] = field_sources
    st.session_state["field_source_map_json"] = ui_json_dumps(field_sources)
    st.session_state["one_load_imported_fields"] = imported
    st.session_state["one_load_skipped_manual_fields"] = skipped
    st.session_state["one_load_overwritten_default_fields"] = overwritten_defaults
    st.session_state["one_load_conflict_flags"] = sorted(set(conflicts))
    st.session_state["one_load_applied_values"] = applied_values
    st.session_state["one_load_missing_analyzer_fields"] = [
        key
        for key in [
            "address",
            "asking_price",
            "beds",
            "baths",
            "sqft",
            "rent",
            "repair_notes",
        ]
        if key not in analyzer_values
    ]
    st.session_state["one_load_import_status"] = "Lead imported into analyzer fields. Review before final offer."
    return imported, skipped, conflicts


def ui_json_dumps(value) -> str:
    try:
        import json

        return json.dumps(value)
    except Exception:
        return "{}"


def _build_payload_from_state(st, csv_record: dict | None = None) -> dict:
    return {
        "lead_type": st.session_state.get("one_load_lead_type", ""),
        "lead_source": st.session_state.get("one_load_lead_source", ""),
        "input_method": st.session_state.get("one_load_input_method", ""),
        "property_address": st.session_state.get("one_load_property_address", ""),
        "listing_url": st.session_state.get("one_load_listing_url", ""),
        "dataset_id": st.session_state.get("one_load_apify_dataset", ""),
        "listing_text": st.session_state.get("one_load_pasted_listing_text", ""),
        "seller_notes": st.session_state.get("one_load_seller_notes", ""),
        "asking_price": st.session_state.get("one_load_asking_price", 0),
        "seller_desired_price": st.session_state.get("one_load_seller_desired_price", 0),
        "mortgage_balance": st.session_state.get("one_load_mortgage_balance", 0),
        "occupancy": st.session_state.get("one_load_occupancy", ""),
        "motivation_notes": st.session_state.get("one_load_motivation_notes", ""),
        "timeline": st.session_state.get("one_load_timeline", ""),
        "repairs_mentioned": st.session_state.get("one_load_repairs_mentioned", ""),
        "access_notes": st.session_state.get("one_load_access_notes", ""),
        "contact_name": st.session_state.get("one_load_contact_name", ""),
        "contact_phone": st.session_state.get("one_load_contact_phone", ""),
        "contact_email": st.session_state.get("one_load_contact_email", ""),
        "buyer_demand_confidence": st.session_state.get("buyer_demand_confidence", "Unknown"),
        "deal_protection_mode": st.session_state.get("deal_protection_mode", "Yes"),
        "record": csv_record or {},
    }


def _build_assumptions(st, ui):
    market_default_buyer_percent = ui.get_market_wholesale_buyer_percent(st.session_state.get("repair_market", "Central IL"))
    slow_flip_lead_search_max = ui.get_market_slow_flip_lead_search_max(st.session_state.get("repair_market", "Central IL"))
    slow_flip_max_buy_price, slow_flip_max_source = ui.resolve_slow_flip_max_buy_price(st.session_state.get("repair_market", "Central IL"))
    wholesale_model = ui.advanced_wholesale_buyer_model(
        market=st.session_state.get("repair_market", "Central IL"),
        arv=float(st.session_state.get("arv", 0) or st.session_state.get("sheet_arv", 0) or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
        notes=st.session_state.get("notes", ""),
        repair_notes=st.session_state.get("repair_notes", "") + " " + st.session_state.get("manual_repair_notes", ""),
        property_type=st.session_state.get("property_type", ""),
        days_on_market=int(st.session_state.get("days_on_market", 0) or 0),
        buyer_demand_confidence=st.session_state.get("buyer_demand_confidence", "Unknown"),
        market_type=st.session_state.get("market_type", "Auto"),
        occupancy=st.session_state.get("occupancy", "Unknown"),
        livable=st.session_state.get("livable", "Unknown"),
        exit_confidence=st.session_state.get("exit_strategy_confidence", "Unknown"),
    )
    final_buyer_percent = float(ui.wholesale_buyer_percent_arv) if ui.manual_wholesale_override else float(wholesale_model.get("buyer_percent", market_default_buyer_percent))
    return ui.Assumptions(
        min_assignment_fee=float(ui.min_assignment_fee),
        exception_assignment_fee=float(ui.exception_assignment_fee),
        slow_flip_rent_multiple=float(ui.slow_flip_rent_multiple),
        close_title_buffer=float(ui.close_title_buffer),
        target_offer_discount=float(ui.target_offer_discount),
        wholesale_buyer_percent_arv=final_buyer_percent,
        wholesale_buyer_percent_source="Manual Override" if ui.manual_wholesale_override else "Market Default",
        wholesale_buyer_percent_range=wholesale_model.get("range", ""),
        wholesale_buyer_percent_reason=wholesale_model.get("reason_text", ""),
        market_liquidity_tier=wholesale_model.get("tier", ""),
        market_wholesale_buyer_percent=float(market_default_buyer_percent),
        slow_flip_max_offer_cap=float(ui.slow_flip_max_offer_cap),
        slow_flip_first_offer_gap=float(ui.slow_flip_first_offer_gap),
        slow_flip_lead_search_max=float(slow_flip_lead_search_max),
        slow_flip_lead_search_source="Market Default",
        above_slow_flip_lead_search_range=bool(slow_flip_lead_search_max > 0 and float(st.session_state.get("asking_price", 0) or 0) > slow_flip_lead_search_max),
        inside_slow_flip_lead_search_range=bool(slow_flip_lead_search_max > 0 and float(st.session_state.get("asking_price", 0) or 0) <= slow_flip_lead_search_max),
        slow_flip_max_buy_price=float(slow_flip_max_buy_price),
        slow_flip_max_source=slow_flip_max_source,
        above_slow_flip_max_buy_price=bool(slow_flip_max_buy_price > 0 and float(st.session_state.get("asking_price", 0) or 0) > slow_flip_max_buy_price),
    )


def _build_deal(st, ui, exit_mode: str):
    resolved_arv, value_source = ui.resolve_value_source()
    st.session_state["value_source"] = value_source
    analysis_price = float(st.session_state.get("contract_price", 0) or 0) or float(st.session_state.get("asking_price", 0) or 0)
    return ui.DealInput(
        address=st.session_state.get("address", ""),
        market=st.session_state.get("market", ""),
        lead_type=st.session_state.get("lead_type", "Agent"),
        exit_mode=exit_mode,
        asking_price=analysis_price,
        rent=float(st.session_state.get("rent", 0) or 0),
        beds=float(st.session_state.get("beds", 0) or 0),
        baths=float(st.session_state.get("baths", 0) or 0),
        sqft=float(st.session_state.get("sqft", 0) or 0),
        taxes=float(st.session_state.get("taxes", 0) or 0),
        status=st.session_state.get("status", "Unknown"),
        occupancy=st.session_state.get("occupancy", "Unknown"),
        livable=st.session_state.get("livable", "Unknown"),
        days_on_market=int(st.session_state.get("days_on_market", 0) or 0),
        notes="\n".join(
            part
            for part in [
                st.session_state.get("notes", ""),
                st.session_state.get("repair_notes", ""),
                st.session_state.get("manual_repair_notes", ""),
            ]
            if str(part or "").strip()
        ),
        arv=float(resolved_arv or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
    )


def _run_one_load(st, ui, csv_record: dict | None, exit_mode: str, overwrite_demo_values: bool = True) -> dict:
    payload = _build_payload_from_state(st, csv_record=csv_record)
    method = payload.get("input_method", "")
    if method == "Apify dataset URL / ID" and payload.get("dataset_id"):
        result = fetch_universal_apify_dataset(payload["dataset_id"], source=payload.get("lead_source", "Apify Dataset"), limit=1)
        rows = result.get("rows", []) if result.get("ok") else []
        if rows:
            payload["record"] = rows[0].get("data", {})
        else:
            st.session_state["one_load_last_error"] = result.get("error", "Needs Manual Entry")
    normalized = normalize_one_load_lead(payload)
    imported, skipped, conflicts = apply_one_load_import(st, normalized, overwrite_demo_values=overwrite_demo_values)
    seller = normalized.get("seller", {})
    st.session_state["one_load_normalized"] = normalized
    st.session_state["one_load_run_success"] = normalized.get("one_load_run_success", "No")
    st.session_state["one_load_missing_fields"] = normalized.get("missing_critical_fields", [])
    st.session_state["one_load_data_sources_used"] = normalized.get("data_sources_used", [])
    st.session_state["seller_name"] = seller.get("seller_name", payload.get("contact_name", ""))
    st.session_state["seller_phone"] = seller.get("seller_phone", payload.get("contact_phone", ""))
    st.session_state["seller_email"] = seller.get("seller_email", payload.get("contact_email", ""))
    st.session_state["seller_motivation"] = seller.get("seller_motivation", payload.get("motivation_notes", ""))
    st.session_state["seller_timeline"] = seller.get("seller_timeline", payload.get("timeline", ""))
    st.session_state["seller_desired_price"] = seller.get("seller_desired_price", payload.get("seller_desired_price", 0))
    st.session_state["seller_condition_notes"] = seller.get("seller_condition_notes", "")
    st.session_state["seller_repair_notes"] = seller.get("seller_repair_notes", payload.get("repairs_mentioned", ""))
    repair_notes = " ".join(
        part
        for part in [payload.get("listing_text", ""), payload.get("seller_notes", ""), payload.get("repairs_mentioned", "")]
        if str(part or "").strip()
    )
    if repair_notes:
        if "repair_notes" not in skipped:
            st.session_state["repair_notes"] = repair_notes
        repair_analysis = ui.analyze_repairs(
            notes=repair_notes,
            sqft=float(st.session_state.get("sqft", 0) or 0),
            baths=float(st.session_state.get("baths", 0) or 0),
            uploaded_files=[],
            market=st.session_state.get("repair_market", "Central IL"),
            repair_level=st.session_state.get("repair_level", "Rental Ready"),
            pricing_mode=st.session_state.get("repair_pricing_mode", "Investor standard"),
            repair_scope_confidence=st.session_state.get("repair_scope_confidence", "Unknown"),
            market_labor_cost=st.session_state.get("market_labor_cost", "Unknown"),
            repair_cushion_percent=ui.repair_cushion_percent_value(),
            manual_repair_adjustment=float(st.session_state.get("manual_repair_adjustment", 0) or 0),
        )
        st.session_state["repair_analysis"] = repair_analysis
        st.session_state["repairs"] = int(repair_analysis.get("recommended_repair_number", 0) or st.session_state.get("repairs", 0) or 0)
    if st.session_state.get("address"):
        pulled = ui.fetch_all_sources(
            st.session_state.get("address", ""),
            beds=float(st.session_state.get("beds", 0) or 0),
            baths=float(st.session_state.get("baths", 0) or 0),
            sqft=float(st.session_state.get("sqft", 0) or 0),
            include_listing_sheet=st.session_state.get("source_mode") == "Zillow / Sheet Match",
        )
        st.session_state["last_source_results"] = pulled
        merged = ui.merge_results(pulled)
        st.session_state["last_auto_pull"] = merged
        ui.update_state_from_auto_pull(merged)
    protection = ui.build_deal_protection_payload(
        {
            "contract_status": st.session_state.get("contract_status", "Not under contract"),
            "deal_protection_mode": st.session_state.get("deal_protection_mode", "Yes"),
            "address_sharing_level": st.session_state.get("address_sharing_level", "Hide exact address"),
            "listing_source_sharing_level": st.session_state.get("listing_source_sharing_level", "Hide listing/source links"),
            "buyer_message_type": st.session_state.get("buyer_message_type", "Pre-contract demand check"),
            "address": st.session_state.get("address", ""),
            "city": st.session_state.get("city", ""),
            "state": st.session_state.get("state", ""),
            "market": st.session_state.get("market", ""),
            "beds": st.session_state.get("beds", 0),
            "baths": st.session_state.get("baths", 0),
            "arv": st.session_state.get("arv", st.session_state.get("sheet_arv", 0)),
            "repairs": st.session_state.get("repairs", 0),
            "asking_price": st.session_state.get("asking_price", 0),
            "listing_url": st.session_state.get("listing_url", ""),
            "notes": st.session_state.get("notes", ""),
            "repair_notes": st.session_state.get("repair_notes", ""),
            "mold_verified": ui.mold_verified_bool(),
        }
    )
    for key, value in protection.items():
        st.session_state[key] = value
    assumptions = _build_assumptions(st, ui)
    deal = _build_deal(st, ui, exit_mode)
    result = ui.analyze_deal(deal, assumptions)
    final_summary = ui.render_final_decision_box(
        result=result,
        deal=deal,
        value_source=st.session_state.get("value_source", "Missing"),
        uploaded_files=[],
        repair_notes=st.session_state.get("repair_notes", ""),
        assumptions=assumptions,
    )
    best = result.get("best", {}) if isinstance(result, dict) else {}
    final_decision = final_summary.get("final_decision", result.get("best_exit", "Needs Human Review"))
    team_action = final_summary.get("team_action", "")
    first_offer = best.get("offer_to_send") or best.get("target_offer_low") or 0
    internal_max = best.get("max_offer") or best.get("target_offer_high") or 0
    normalized.update(
        {
            "imported_fields": imported,
            "skipped_manual_fields": skipped,
            "conflict_flags": conflicts,
            "final_simple_answer": final_decision,
            "first_offer": first_offer,
            "internal_max": internal_max,
            "do_not_exceed": internal_max,
            "best_next_move": team_action,
            "final_decision": final_decision,
            "arv_source": st.session_state.get("arv_source_used", st.session_state.get("value_source", "Missing")),
            "arv_confidence": st.session_state.get("arv_confidence", "Not enough data"),
            "rent_confidence": "Weak" if float(st.session_state.get("rent", 0) or 0) <= 0 else st.session_state.get("rental_demand_confidence", "Unknown"),
            "repair_source": ui.resolve_repair_source(),
            "buyer_demand_confidence": st.session_state.get("buyer_demand_confidence", "Unknown"),
            "deal_protection_status": st.session_state.get("deal_protection_mode", "Yes"),
        }
    )
    st.session_state["one_load_normalized"] = normalized
    st.session_state["one_load_final_answer"] = normalized.get("final_simple_answer", "")
    st.session_state["one_load_next_action"] = normalized.get("best_next_move", "")
    return normalized


def _render_imported_fields_summary(st) -> None:
    imported = st.session_state.get("one_load_imported_fields", []) or []
    missing = st.session_state.get("one_load_missing_analyzer_fields", []) or []
    skipped = st.session_state.get("one_load_skipped_manual_fields", []) or []
    overwritten = st.session_state.get("one_load_overwritten_default_fields", []) or []
    if not imported and not missing and not skipped and not overwritten:
        return
    st.markdown("### Imported Fields Summary")
    st.write(
        {
            "Fields updated": ", ".join(imported) if imported else "None",
            "Fields missing": ", ".join(missing) if missing else "None",
            "Fields skipped due to manual override": ", ".join(skipped) if skipped else "None",
            "Fields overwritten because they were default/demo values": ", ".join(overwritten) if overwritten else "None",
        }
    )


def _render_off_market_summary(st, normalized: dict) -> None:
    seller = normalized.get("seller", {})
    missing = normalized.get("missing_critical_fields", [])
    st.markdown("### Off-Market Lead Summary")
    st.write(
        {
            "Seller name": st.session_state.get("seller_name", seller.get("seller_name", "")),
            "Seller phone": st.session_state.get("seller_phone", seller.get("seller_phone", "")),
            "Lead source": normalized.get("lead_source", ""),
            "Motivation": st.session_state.get("seller_motivation", seller.get("seller_motivation", "")),
            "Asking price / desired price": st.session_state.get("seller_desired_price", seller.get("seller_desired_price", 0)),
            "Timeline": st.session_state.get("seller_timeline", seller.get("seller_timeline", "")),
            "Occupancy": st.session_state.get("occupancy", ""),
            "Condition notes": st.session_state.get("seller_condition_notes", seller.get("seller_condition_notes", "")),
            "Repairs mentioned": st.session_state.get("seller_repair_notes", seller.get("seller_repair_notes", "")),
            "Access status": st.session_state.get("one_load_access_notes", ""),
            "Missing info": ", ".join(missing) if missing else "None",
        }
    )


def _render_one_load_summary(st, ui, normalized: dict) -> None:
    st.markdown("### One-Load Results Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Data imported?", normalized.get("one_load_run_success", "No"))
    c2.metric("Lead type", normalized.get("lead_type", ""))
    c3.metric("Lead source", normalized.get("lead_source", ""))
    c4.metric("Final answer", normalized.get("final_simple_answer", "Needs Manual Entry"))
    st.write(
        {
            "Missing critical fields": ", ".join(normalized.get("missing_critical_fields", [])) or "None",
            "ARV source used": normalized.get("arv_source", "Missing"),
            "ARV confidence": normalized.get("arv_confidence", "Not enough data"),
            "Rent confidence": normalized.get("rent_confidence", "Weak"),
            "Repair estimate source": normalized.get("repair_source", "Missing"),
            "Buyer demand confidence": normalized.get("buyer_demand_confidence", "Unknown"),
            "Deal protection status": normalized.get("deal_protection_status", "Yes"),
            "First offer": ui.money(normalized.get("first_offer", 0)),
            "Internal max": ui.money(normalized.get("internal_max", 0)),
            "Do not exceed price": ui.money(normalized.get("do_not_exceed", 0)),
            "Best next move": normalized.get("best_next_move", ""),
        }
    )
    _render_imported_fields_summary(st)
    st.markdown("### Status Checklist")
    for item in normalized.get("status_checklist", []):
        if item.get("status") == "ok":
            st.success(item.get("label", ""))
        else:
            st.warning(item.get("label", ""))
    st.markdown("### Review Before Offer")
    for item in normalized.get("review_before_offer_checklist", []):
        st.checkbox(item, value=False, key=f"review_before_offer_{item}")


def render_one_load_deal_section(st, ui, exit_mode: str = "Auto") -> None:
    initialize_one_load_defaults(st)
    st.header("One-Load Deal Analyzer")
    st.caption("One input can populate the deal engine for on-market, off-market, CSV, Apify, and manual leads.")
    st.info("One-Load settings saved. Change source/input method as needed, then run analysis.")
    with st.expander("One-Load Deal Analyzer", expanded=True):
        top_cols = st.columns(3)
        with top_cols[0]:
            st.selectbox(
                "Lead Type",
                ["On-market listing", "Off-market seller lead", "Agent / MLS lead", "Apify / Zillow dataset", "CSV / list lead", "Manual quick entry"],
                key="one_load_lead_type",
            )
            st.text_input("Property address", key="one_load_property_address")
            st.number_input("Asking price", min_value=0, step=1000, key="one_load_asking_price")
            st.text_input("Contact name", key="one_load_contact_name")
        with top_cols[1]:
            st.selectbox(
                "Lead Source",
                ["Zillow", "Redfin", "Realtor.com", "MLS", "Agent", "XLeads", "Cold text reply", "Seller call", "Facebook", "Driving for Dollars", "Direct mail", "Probate", "Tax delinquent", "Code violation", "Vacant house", "Referral", "Other"],
                key="one_load_lead_source",
            )
            st.text_input("Listing URL", key="one_load_listing_url")
            st.number_input("Seller desired price", min_value=0, step=1000, key="one_load_seller_desired_price")
            st.text_input("Contact phone", key="one_load_contact_phone")
        with top_cols[2]:
            st.selectbox(
                "Input Method",
                ["Property address", "Listing URL", "Apify dataset URL / ID", "Paste listing text", "Paste seller notes", "Upload CSV", "Manual quick entry"],
                key="one_load_input_method",
            )
            st.text_input("Apify dataset ID / URL", key="one_load_apify_dataset")
            st.number_input("Mortgage balance if known", min_value=0, step=1000, key="one_load_mortgage_balance")
            st.text_input("Contact email", key="one_load_contact_email")
        detail_cols = st.columns(2)
        with detail_cols[0]:
            st.text_area("Pasted listing text", height=120, key="one_load_pasted_listing_text")
            st.text_area("Motivation notes", height=80, key="one_load_motivation_notes")
            st.text_input("Timeline", key="one_load_timeline")
        with detail_cols[1]:
            st.text_area("Seller conversation notes", height=120, key="one_load_seller_notes")
            st.text_area("Repairs mentioned by seller", height=80, key="one_load_repairs_mentioned")
            st.text_input("Access notes", key="one_load_access_notes")
            st.selectbox("Occupancy", ["Unknown", "Vacant", "Owner occupied", "Tenant occupied", "Occupied"], key="one_load_occupancy")
        uploaded_csv = st.file_uploader("Upload CSV", type=["csv"], key="one_load_csv")
        overwrite_demo_values = st.checkbox("Overwrite default/demo values?", value=True, key="one_load_overwrite_demo_values")
        csv_record = None
        if uploaded_csv is not None:
            try:
                csv_df = ui.pd.read_csv(uploaded_csv)
                st.dataframe(csv_df.head(5), use_container_width=True)
                if not csv_df.empty:
                    csv_record = csv_df.iloc[0].to_dict()
            except Exception as exc:
                st.warning(f"Could not read CSV yet: {exc}")
        if st.button("Run Full Deal Analysis", type="primary"):
            normalized = _run_one_load(st, ui, csv_record=csv_record, exit_mode=exit_mode, overwrite_demo_values=overwrite_demo_values)
            if not overwrite_demo_values and st.session_state.get("one_load_overwritten_default_fields"):
                st.info("Default/demo analyzer fields were left unchanged.")
            st.success("Lead imported into analyzer fields. Review before final offer.")
            if normalized.get("skipped_manual_fields"):
                st.info("Manual overrides kept: " + ", ".join(normalized.get("skipped_manual_fields", [])))
            if normalized.get("conflict_flags"):
                for warning in normalized.get("conflict_flags", []):
                    st.warning(warning)
        normalized = st.session_state.get("one_load_normalized", {})
        if normalized:
            if st.button("Apply One-Load Data to Analyzer", type="secondary"):
                imported, skipped, conflicts = apply_one_load_import(st, normalized, force=True, overwrite_demo_values=overwrite_demo_values)
                normalized["imported_fields"] = imported
                normalized["skipped_manual_fields"] = skipped
                normalized["conflict_flags"] = conflicts
                st.session_state["one_load_normalized"] = normalized
                st.session_state["one_load_import_status"] = "Lead imported into analyzer fields. Review before final offer."
                st.success(st.session_state["one_load_import_status"])
                st.rerun()
            _render_off_market_summary(st, normalized)
            render_realtor_outreach_panel(st, normalized)
            _render_one_load_summary(st, ui, normalized)
