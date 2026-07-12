from __future__ import annotations

import json

try:
    from ui_sections.one_load_deal_ui import render_one_load_deal_section
except ImportError:
    try:
        from .one_load_deal_ui import render_one_load_deal_section
    except ImportError:
        from war_room_offer_engine.ui_sections.one_load_deal_ui import render_one_load_deal_section

try:
    from data_sources import (
        fetch_universal_apify_dataset,
        parse_universal_listing_text,
        run_universal_apify_actor,
        universal_listing_from_record,
    )
except ImportError:
    try:
        from ..data_sources import (
            fetch_universal_apify_dataset,
            parse_universal_listing_text,
            run_universal_apify_actor,
            universal_listing_from_record,
        )
    except ImportError:
        from war_room_offer_engine.data_sources import (
            fetch_universal_apify_dataset,
            parse_universal_listing_text,
            run_universal_apify_actor,
            universal_listing_from_record,
        )


UNIVERSAL_FIELD_MAP = {
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
}

UNIVERSAL_DEFAULT_VALUES = {
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
    "asking_price": 35000,
    "rent": 900,
    "status": "Unknown",
    "lead_source": "Manual",
}


def _has_manual_value(st, state_key: str) -> bool:
    value = st.session_state.get(state_key)
    if value in [None, "", 0, 0.0, [], {}]:
        return False
    default_value = UNIVERSAL_DEFAULT_VALUES.get(state_key)
    if default_value is not None and str(value) == str(default_value):
        return False
    return True


def _apply_universal_listing_import(st, payload: dict) -> tuple[list[str], list[str], list[str]]:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    source = payload.get("source", "Universal Listing Import")
    imported: list[str] = []
    skipped: list[str] = []
    conflicts: list[str] = list(payload.get("conflict_flags", []))
    field_sources = dict(st.session_state.get("apify_field_sources", {}) or {})
    for import_key, state_key in UNIVERSAL_FIELD_MAP.items():
        value = data.get(import_key)
        if value in [None, "", 0, 0.0, [], {}]:
            continue
        current = st.session_state.get(state_key)
        if _has_manual_value(st, state_key) and str(current) != str(value):
            skipped.append(state_key)
            if state_key == "beds":
                conflicts.append("Bed count conflict")
            elif state_key == "baths":
                conflicts.append("Bath count conflict")
            continue
        st.session_state[state_key] = value
        imported.append(state_key)
        field_sources[state_key] = source
    st.session_state["apify_field_sources"] = field_sources
    st.session_state["field_source_map_json"] = json.dumps(field_sources)
    st.session_state["universal_import_status"] = "Imported" if imported else "Needs manual entry."
    st.session_state["universal_imported_fields"] = imported
    st.session_state["universal_skipped_manual_fields"] = skipped
    st.session_state["universal_import_conflict_flags"] = sorted(set(conflicts))
    st.session_state["universal_import_missing_fields"] = payload.get("missing_fields", [])
    st.session_state["imported_listing_source"] = source
    st.session_state["imported_source_confidence"] = payload.get("source_confidence", "Weak")
    st.session_state["imported_manual_review_needed"] = payload.get("manual_review_needed", "Yes")
    st.session_state["imported_listing_price"] = data.get("asking_price", 0)
    st.session_state["imported_beds"] = data.get("beds", 0)
    st.session_state["imported_baths"] = data.get("baths", 0)
    st.session_state["imported_sqft"] = data.get("sqft", 0)
    st.session_state["imported_dom"] = data.get("days_on_market", 0)
    st.session_state["imported_agent_name"] = data.get("listing_agent_name", "")
    st.session_state["imported_agent_phone"] = data.get("listing_agent_phone", "")
    st.session_state["imported_agent_email"] = data.get("listing_agent_email", "")
    st.session_state["imported_brokerage"] = data.get("listing_brokerage", "")
    st.session_state["imported_listing_status"] = data.get("status", "")
    return imported, skipped, conflicts


def _store_universal_payload(st, payload: dict) -> None:
    st.session_state["universal_listing_payload"] = payload
    st.session_state["universal_listing_preview"] = [payload] if payload else []
    st.session_state["universal_last_error"] = "; ".join(payload.get("errors", [])) if payload else "Needs manual entry."


def _render_universal_listing_summary(st) -> None:
    payload = st.session_state.get("universal_listing_payload", {}) or {}
    data = payload.get("data", {})
    if not payload:
        return
    st.markdown("#### Imported Listing Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Source", payload.get("source", ""))
    c2.metric("Price", f"${float(data.get('asking_price', 0) or 0):,.0f}")
    c3.metric("Beds/Baths", f"{data.get('beds', '')}/{data.get('baths', '')}")
    c4.metric("Sqft", f"{float(data.get('sqft', 0) or 0):,.0f}" if data.get("sqft") else "Needs manual entry.")
    st.write(
        {
            "Address": data.get("address", "Needs manual entry."),
            "DOM": data.get("days_on_market", "Needs manual entry."),
            "Agent": data.get("listing_agent_name", "Needs manual entry."),
            "Listing URL": data.get("listing_url", "Needs manual entry."),
            "Missing fields": ", ".join(payload.get("missing_fields", [])) or "None",
            "Data confidence": payload.get("source_confidence", "Weak"),
            "Manual review needed?": payload.get("manual_review_needed", "Yes"),
        }
    )
    for warning in st.session_state.get("universal_import_conflict_flags", payload.get("conflict_flags", [])):
        st.warning(warning)


def render_lead_intake_section(st, ui) -> None:

    render_one_load_deal_section(st, ui, "Auto")

    pd = ui.pd
    json = ui.json
    provider_connection_status = ui.provider_connection_status
    fetch_apify_zillow_dataset = ui.fetch_apify_zillow_dataset
    run_apify_zillow_actor = ui.run_apify_zillow_actor
    apply_apify_zillow_import = ui.apply_apify_zillow_import
    parse_listing_text = ui.parse_listing_text
    fetch_all_sources = ui.fetch_all_sources
    merge_results = ui.merge_results
    update_state_from_auto_pull = ui.update_state_from_auto_pull
    st.subheader("1. Pull Property Data")

    source_col1, source_col2 = st.columns([1, 1])
    with source_col1:
        st.radio(
            "Source mode",
            ["Zillow / Sheet Match", "Off-Market / Manual"],
            key="source_mode",
            horizontal=True,
            help="Zillow / Sheet Match searches your published Master Feed. Off-Market / Manual skips the sheet and uses RentCast + your manual inputs.",
        )
    with source_col2:
        st.selectbox(
            "Lead source",
            ["Zillow / Apify", "MLS / Agent", "Off-Market Seller", "Facebook", "Driving for Dollars", "Cold Text Reply", "Manual Entry", "Other"],
            key="lead_source",
        )

    with st.expander("Lead Data Intake", expanded=False):
        st.caption("Manual/pasted/vendor intake only. This does not scrape Zillow, Redfin, Realtor.com, or other listing sites.")
        intake_cols = st.columns(3)
        with intake_cols[0]:
            st.selectbox(
                "Manual source selector",
                [
                    "Zillow manual/pasted",
                    "Redfin manual/pasted",
                    "Realtor manual/pasted",
                    "XLeads",
                    "PropStream",
                    "DealMachine",
                    "RentCast",
                    "County records",
                    "MLS/manual",
                    "Other",
                ],
                key="data_intake_source",
            )
            st.text_input("Manual Listing URL", key="listing_url")
        with intake_cols[1]:
            lead_intake_csv = st.file_uploader("Upload lead CSV", type=["csv"], key="lead_intake_csv")
            st.text_input("County tax/GIS manual link", key="county_tax_gis_link")
        with intake_cols[2]:
            for provider in provider_connection_status():
                st.write(("Connected: " if provider["connected"] else "API not connected - ") + provider["provider"])

        st.markdown("### Universal Listing Import")
        st.caption("Import one on-market listing from approved APIs, Apify, uploaded CSV, pasted text, or manual entry. No direct scraping.")
        u1, u2, u3 = st.columns(3)
        with u1:
            st.selectbox(
                "Listing Source",
                ["Zillow", "Redfin", "Realtor.com", "MLS / Manual", "XLeads", "Apify Dataset", "Agent Sent Listing", "County / Tax Record", "Other"],
                key="universal_listing_source",
            )
            st.text_input("Listing URL", key="universal_listing_url")
        with u2:
            st.selectbox(
                "Import Method",
                ["Parse pasted text only", "Pull from Apify dataset", "Run Apify actor from listing URL", "Manual only"],
                key="universal_import_method",
            )
            st.text_input("Apify Actor ID / Dataset ID", key="universal_apify_id")
        with u3:
            parse_universal = st.button("Parse Listing Text", type="secondary")
            pull_universal = st.button("Pull From Apify Dataset", type="secondary")
            run_universal = st.button("Run Apify Actor + Import", type="secondary")
            clear_universal = st.button("Clear Imported Lead", type="secondary")
        st.text_area("Paste Listing Text", height=160, key="universal_listing_text")

        if clear_universal:
            for key in [
                "universal_listing_payload",
                "universal_listing_preview",
                "universal_import_status",
                "universal_imported_fields",
                "universal_skipped_manual_fields",
                "universal_import_conflict_flags",
                "universal_import_missing_fields",
                "universal_last_error",
            ]:
                st.session_state.pop(key, None)
            st.success("Imported listing cleared. Existing manual field values were left unchanged.")

        if parse_universal:
            payload = parse_universal_listing_text(
                st.session_state.get("universal_listing_source", ""),
                st.session_state.get("universal_listing_url", ""),
                st.session_state.get("universal_listing_text", ""),
            )
            _store_universal_payload(st, payload)
            imported, skipped, _ = _apply_universal_listing_import(st, payload)
            st.success("Imported fields: " + (", ".join(imported) if imported else "Needs manual entry."))
            if skipped:
                st.info("Manual overrides kept: " + ", ".join(skipped))

        if pull_universal:
            result = fetch_universal_apify_dataset(
                st.session_state.get("universal_apify_id", ""),
                source=st.session_state.get("universal_listing_source", "Apify Dataset"),
                limit=1,
            )
            rows = result.get("rows", []) if result.get("ok") else []
            if rows:
                _store_universal_payload(st, rows[0])
                imported, skipped, _ = _apply_universal_listing_import(st, rows[0])
                st.success("Imported fields: " + (", ".join(imported) if imported else "Needs manual entry."))
                if skipped:
                    st.info("Manual overrides kept: " + ", ".join(skipped))
            else:
                st.warning(result.get("error") or "; ".join(result.get("errors", [])) or "Needs manual entry.")

        if run_universal:
            result = run_universal_apify_actor(
                st.session_state.get("universal_apify_id", ""),
                st.session_state.get("universal_listing_url", ""),
                source=st.session_state.get("universal_listing_source", "Apify Dataset"),
                limit=1,
            )
            rows = result.get("rows", []) if result.get("ok") else []
            if rows:
                _store_universal_payload(st, rows[0])
                imported, skipped, _ = _apply_universal_listing_import(st, rows[0])
                st.success("Imported fields: " + (", ".join(imported) if imported else "Needs manual entry."))
                if skipped:
                    st.info("Manual overrides kept: " + ", ".join(skipped))
            else:
                st.warning(result.get("error") or "; ".join(result.get("errors", [])) or "Needs manual entry.")

        _render_universal_listing_summary(st)

        st.markdown("### Apify / Zillow Import")
        st.caption("Preview Apify Zillow data before import. Imported fields fill blank/default fields only; manual edits stay protected.")
        apify_cols = st.columns([1.2, 1.2, 0.7])
        with apify_cols[0]:
            st.text_input("Apify Dataset ID", key="apify_dataset_id")
            preview_dataset = st.button("Preview Apify Dataset", type="secondary")
        with apify_cols[1]:
            st.text_input("Apify Actor ID", key="apify_actor_id")
            st.text_area("Apify Actor Input JSON", height=80, key="apify_actor_input_json")
            preview_actor = st.button("Run Actor + Preview", type="secondary")
        with apify_cols[2]:
            st.number_input("Preview limit", min_value=1, max_value=200, step=5, key="apify_preview_limit")

        if preview_dataset:
            result = fetch_apify_zillow_dataset(
                dataset_id=st.session_state.get("apify_dataset_id", ""),
                limit=int(st.session_state.get("apify_preview_limit", 25) or 25),
            )
            st.session_state["apify_last_error"] = result.get("error", "")
            rows = result.get("rows", []) if result.get("ok") else []
            for row in rows:
                row["source"] = result.get("source", "Apify Zillow Dataset")
            st.session_state["apify_zillow_preview"] = rows
            st.session_state["apify_zillow_duplicates"] = result.get("duplicates", [])
            st.session_state["apify_duplicate_count"] = len(result.get("duplicates", []))
            if result.get("ok"):
                st.success(f"Loaded {len(rows)} unique Apify/Zillow rows.")
            else:
                st.error(result.get("error", "Could not load Apify/Zillow dataset."))

        if preview_actor:
            try:
                actor_input = json.loads(st.session_state.get("apify_actor_input_json", "{}") or "{}")
            except Exception as exc:
                actor_input = {}
                st.session_state["apify_last_error"] = f"Actor input JSON is invalid: {exc}"
                st.error(st.session_state["apify_last_error"])
            else:
                result = run_apify_zillow_actor(
                    actor_id=st.session_state.get("apify_actor_id", ""),
                    actor_input=actor_input,
                    limit=int(st.session_state.get("apify_preview_limit", 25) or 25),
                )
                st.session_state["apify_last_error"] = result.get("error", "")
                rows = result.get("rows", []) if result.get("ok") else []
                for row in rows:
                    row["source"] = result.get("source", "Apify Zillow Actor")
                st.session_state["apify_zillow_preview"] = rows
                st.session_state["apify_zillow_duplicates"] = result.get("duplicates", [])
                st.session_state["apify_duplicate_count"] = len(result.get("duplicates", []))
                if result.get("ok"):
                    st.success(f"Loaded {len(rows)} unique Apify/Zillow rows.")
                else:
                    st.error(result.get("error", "Could not run Apify actor."))

        apify_preview_rows = st.session_state.get("apify_zillow_preview", [])
        if st.session_state.get("apify_last_error"):
            st.warning(st.session_state["apify_last_error"])
        if st.session_state.get("apify_duplicate_count", 0):
            st.info(f"Duplicate-address protection removed {st.session_state['apify_duplicate_count']} duplicate row(s).")
        if apify_preview_rows:
            preview_table = []
            for idx, row in enumerate(apify_preview_rows):
                data = row.get("data", {})
                preview_table.append(
                    {
                        "row": idx,
                        "address": data.get("address", ""),
                        "price": data.get("asking_price", 0),
                        "beds": data.get("beds", ""),
                        "baths": data.get("baths", ""),
                        "sqft": data.get("sqft", ""),
                        "status": data.get("status", ""),
                        "url": data.get("listing_url", ""),
                        "warnings": "; ".join(row.get("warnings", [])),
                        "errors": "; ".join(row.get("errors", [])),
                    }
                )
            st.dataframe(pd.DataFrame(preview_table), use_container_width=True)
            st.number_input(
                "Apify/Zillow row to import",
                min_value=0,
                max_value=max(len(apify_preview_rows) - 1, 0),
                step=1,
                key="apify_selected_row",
            )
            if st.button("Import selected Apify/Zillow lead", type="secondary"):
                selected_row = apify_preview_rows[int(st.session_state.get("apify_selected_row", 0) or 0)]
                if selected_row.get("errors"):
                    st.error("Cannot import row: " + "; ".join(selected_row.get("errors", [])))
                else:
                    imported, skipped = apply_apify_zillow_import(selected_row)
                    st.success("Imported fields: " + (", ".join(imported) if imported else "none"))
                    if skipped:
                        st.info("Kept manual fields unchanged: " + ", ".join(skipped))

        st.text_area("Paste Listing Text", height=130, key="listing_text")
        if lead_intake_csv is not None:
            try:
                lead_df = pd.read_csv(lead_intake_csv)
                st.dataframe(lead_df.head(5), use_container_width=True)
                if st.button("Use first CSV row", type="secondary"):
                    first_row = lead_df.iloc[0].to_dict()
                    csv_map = {
                        "address": ["property address", "address", "property_address"],
                        "asking_price": ["asking/list price", "asking price", "price", "list_price"],
                        "beds": ["beds", "bedrooms"],
                        "baths": ["baths", "bathrooms"],
                        "sqft": ["square footage", "sqft", "sq_ft"],
                        "taxes": ["annual taxes", "taxes"],
                        "days_on_market": ["days on market", "dom"],
                        "listing_url": ["listing url", "url", "listing_url"],
                    }
                    lower_row = {str(k).strip().lower(): v for k, v in first_row.items()}
                    filled = []
                    for state_key, names in csv_map.items():
                        for name in names:
                            if name in lower_row and lower_row[name] not in [None, "", 0, 0.0]:
                                st.session_state[state_key] = lower_row[name]
                                filled.append(state_key)
                                break
                    st.success("Filled from CSV: " + ", ".join(filled) if filled else "Needs manual entry.")
            except Exception as e:
                st.warning(f"Could not read CSV yet: {e}")

        if st.button("Parse pasted listing text", type="secondary"):
            parsed = parse_listing_text(st.session_state.get("listing_text", ""))
            field_map = {
                "address": "address",
                "city": "city",
                "state": "state",
                "zip": "zip",
                "asking_price": "asking_price",
                "beds": "beds",
                "baths": "baths",
                "sqft": "sqft",
                "lot_size": "lot_size",
                "year_built": "year_built",
                "property_type": "property_type",
                "days_on_market": "days_on_market",
                "listing_status": "status",
                "agent_name": "listing_agent_name",
                "agent_phone": "listing_agent_phone",
                "agent_email": "listing_agent_email",
                "listing_brokerage": "listing_brokerage",
                "tax_assessed_value": "tax_assessed_value",
                "annual_taxes": "taxes",
                "last_sale_date": "last_sale_date",
                "last_sale_price": "last_sale_price",
                "owner_name": "owner_name",
                "rent_estimate": "rent",
                "arv_estimate": "manual_arv_override",
                "comp_source": "comp_source",
            }
            updated = []
            for parsed_key, state_key in field_map.items():
                value = parsed.get(parsed_key)
                if value not in [None, "", 0, 0.0]:
                    st.session_state[state_key] = value
                    updated.append(state_key)
            if updated:
                st.success("Parsed and filled: " + ", ".join(updated))
            else:
                st.info("Needs manual entry.")

        lead_detail_cols = st.columns(4)
        with lead_detail_cols[0]:
            st.text_input("City", key="city")
            st.text_input("State", key="state")
            st.text_input("Zip", key="zip")
        with lead_detail_cols[1]:
            st.text_input("Lot size", key="lot_size")
            st.text_input("Year built", key="year_built")
            st.text_input("Property type", key="property_type")
        with lead_detail_cols[2]:
            st.text_input("Listing agent name", key="listing_agent_name")
            st.text_input("Listing agent phone", key="listing_agent_phone")
            st.text_input("Listing agent email", key="listing_agent_email")
        with lead_detail_cols[3]:
            st.text_input("Listing brokerage", key="listing_brokerage")
            st.number_input("Tax assessed value", min_value=0, step=1000, key="tax_assessed_value")
            st.text_input("Comp source", key="comp_source")

        sale_cols = st.columns(3)
        with sale_cols[0]:
            st.text_input("Last sale date", key="last_sale_date")
        with sale_cols[1]:
            st.number_input("Last sale price", min_value=0, step=1000, key="last_sale_price")
        with sale_cols[2]:
            st.text_input("Owner name if available from approved source", key="owner_name")

    if st.session_state.get("source_mode") == "Off-Market / Manual":
        st.info("Off-market/manual mode skips the Zillow/Master Feed. Enter the seller ask manually if you have it. RentCast will still pull rent, beds, baths, sq ft, value, and facts.")
    else:
        st.info("Zillow/Sheet mode uses RentCast plus your Master Feed CSV to pull asking price, Zillow link, status, and other listing data when the address matches.")

    lookup_col1, lookup_col2 = st.columns([3, 1])
    with lookup_col1:
        st.text_input("Property address", key="address", placeholder="123 Main St, Decatur IL 62522")
    with lookup_col2:
        st.write("")
        st.write("")
        pull_data = st.button("Pull Data", type="primary", use_container_width=True)

    if pull_data:
        include_listing_sheet = st.session_state.get("source_mode") == "Zillow / Sheet Match"
        spinner_text = "Pulling RentCast + Master Feed data..." if include_listing_sheet else "Pulling RentCast data only..."
        with st.spinner(spinner_text):
            results = fetch_all_sources(
                st.session_state["address"],
                beds=float(st.session_state.get("beds", 0) or 0),
                baths=float(st.session_state.get("baths", 0) or 0),
                sqft=float(st.session_state.get("sqft", 0) or 0),
                include_listing_sheet=include_listing_sheet,
            
            )
            merged = merge_results(results)
            st.session_state["last_source_results"] = results
            st.session_state["last_auto_pull"] = merged
            update_state_from_auto_pull(merged)

            good_sources = []
            for item in results:
                if isinstance(item, dict):
                    if item.get("found") or item.get("ok"):
                        good_sources.append(item.get("source", "Unknown"))
                else:
                    if getattr(item, "ok", False) or getattr(item, "found", False):
                        good_sources.append(getattr(item, "source", "Unknown"))

            if good_sources:
                st.success("Pulled data from: " + ", ".join(good_sources))
            else:
                st.warning("No data pulled yet. Add Streamlit secrets or verify the address. Manual analysis still works.")

            with st.expander("Data pull results"):
                for result in results:
                    if isinstance(result, dict):
                        source = result.get("source", "Unknown")
                        found = result.get("found") or result.get("ok")
                        message = result.get("notes") or result.get("message") or ""
                        data = result.get("data", None)
                    else:
                        source = getattr(result, "source", "Unknown")
                        found = getattr(result, "ok", False) or getattr(result, "found", False)
                        message = getattr(result, "message", "") or getattr(result, "notes", "")
                        data = getattr(result, "data", None)

                    if found:
                        st.success(f"{source}: {message}")
                        if data:
                            st.write(data)
                    else:
                        st.info(f"{source}: {message}") 

       
