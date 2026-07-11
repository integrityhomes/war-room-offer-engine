from __future__ import annotations


def render_automatic_sold_comps_section(st, ui) -> None:

    pd = ui.pd
    re = ui.re
    money = ui.money
    calculate_arv_from_comps = ui.calculate_arv_from_comps
    store_auto_arv_summary = ui.store_auto_arv_summary
    radius_to_float = ui.radius_to_float
    get_sold_comps = ui.get_sold_comps
    sold_comps_from_apify_rows = ui.sold_comps_from_apify_rows
    sold_comps_from_csv_rows = ui.sold_comps_from_csv_rows
    sold_comps_from_pasted_text = ui.sold_comps_from_pasted_text
    manual_comp_records = ui.manual_comp_records
    score_sold_comps = ui.score_sold_comps
    comp_subject = ui.comp_subject
    manual_comps_average = ui.manual_comps_average
    safe_float = ui.safe_float
    resolve_value_source = ui.resolve_value_source
    get_market_profile = ui.get_market_profile
    get_market_slow_flip_lead_search_max = ui.get_market_slow_flip_lead_search_max
    resolve_slow_flip_max_buy_price = ui.resolve_slow_flip_max_buy_price
    get_market_wholesale_buyer_percent = ui.get_market_wholesale_buyer_percent
    advanced_wholesale_buyer_model = ui.advanced_wholesale_buyer_model
    percent_label = ui.percent_label
    is_above_slow_flip_max_buy_price = ui.is_above_slow_flip_max_buy_price
    manual_wholesale_override = ui.manual_wholesale_override
    wholesale_buyer_percent_arv = ui.wholesale_buyer_percent_arv
    st.markdown("### Automatic Sold Comps")
    st.caption("Pull, paste, or upload sold comps. Manual ARV override still wins, and manual comps remain the default fallback before automatic comps.")

    if not st.session_state.get("auto_comp_address") and st.session_state.get("address"):
        st.session_state["auto_comp_address"] = st.session_state.get("address", "")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        st.text_input("Subject property address", key="auto_comp_address")
    with c2:
        st.selectbox("Search radius", ["0.5 mile", "1 mile", "2 miles", "5 miles"], key="auto_comp_radius")
    with c3:
        st.selectbox("Sold date range", ["Last 6 months", "Last 12 months", "Last 24 months"], key="auto_comp_date_range")
    with c4:
        st.selectbox("Comp source", ["Auto", "RentCast", "Apify/Zillow", "Manual pasted", "CSV upload", "Manual comps only"], key="auto_comp_source")

    upload = st.file_uploader("Upload sold comps CSV", type=["csv"], key="auto_comp_csv_upload")
    st.text_area(
        "Paste sold comps",
        height=100,
        key="auto_comp_pasted_text",
        placeholder="Example: 123 Oak St, sold $92,000, 3 bed, 1 bath, 1050 sqft, sold 2026-04-15, 0.4 miles",
    )

    fetch_col, use_col, clear_col = st.columns(3)
    with fetch_col:
        fetch_clicked = st.button("Fetch / Refresh Sold Comps", key="fetch_auto_sold_comps")
    with use_col:
        use_best_clicked = st.button("Use Best Automatic ARV", key="use_best_auto_arv")
    with clear_col:
        clear_clicked = st.button("Clear Auto Comps", key="clear_auto_sold_comps")

    if clear_clicked:
        for key in [
            "auto_sold_comps",
            "auto_arv_summary",
            "auto_comp_summary_json",
            "excluded_comp_flags_json",
        ]:
            st.session_state.pop(key, None)
        st.session_state["use_auto_arv_over_manual_comps"] = False
        store_auto_arv_summary([], calculate_arv_from_comps([]))
        st.success("Automatic sold comps cleared.")

    if fetch_clicked:
        source_choice = st.session_state.get("auto_comp_source", "Auto")
        comps: list[dict] = []
        messages: list[str] = []
        address = st.session_state.get("auto_comp_address") or st.session_state.get("address", "")
        radius = radius_to_float(st.session_state.get("auto_comp_radius", "1 mile"))

        if source_choice in ["Auto", "RentCast"]:
            result = get_sold_comps(address, radius_miles=radius, limit=25)
            comps.extend(result.get("comps", []) or [])
            if result.get("notes"):
                messages.append(result.get("notes"))

        if source_choice in ["Auto", "Apify/Zillow"]:
            apify_comps = sold_comps_from_apify_rows(st.session_state.get("apify_zillow_preview", []))
            comps.extend(apify_comps)
            if not apify_comps:
                messages.append("No sold comp rows found in the current Apify/Zillow preview.")

        if source_choice in ["Auto", "CSV upload"] and upload is not None:
            try:
                csv_rows = pd.read_csv(upload).to_dict("records")
                comps.extend(sold_comps_from_csv_rows(csv_rows))
            except Exception as exc:
                messages.append(f"CSV comp import failed: {exc}")

        pasted_text = st.session_state.get("auto_comp_pasted_text", "")
        if source_choice in ["Auto", "Manual pasted"] and pasted_text.strip():
            comps.extend(sold_comps_from_pasted_text(pasted_text))

        if source_choice in ["Auto", "Manual comps only"]:
            comps.extend(manual_comp_records())

        seen = set()
        unique_comps = []
        for comp in comps:
            address_key = re.sub(r"[^a-z0-9]+", " ", str(comp.get("comp_address", "")).lower()).strip()
            if address_key and address_key in seen:
                continue
            if address_key:
                seen.add(address_key)
            unique_comps.append(comp)

        scored = score_sold_comps(
            unique_comps,
            comp_subject(),
            st.session_state.get("auto_comp_radius", "1 mile"),
            st.session_state.get("auto_comp_date_range", "Last 12 months"),
        )
        st.session_state["auto_sold_comps"] = scored
        summary = calculate_arv_from_comps(scored)
        store_auto_arv_summary(scored, summary)
        st.session_state["use_auto_arv_over_manual_comps"] = False
        if messages:
            st.session_state["auto_comp_messages"] = messages

    scored_comps = st.session_state.get("auto_sold_comps", []) or []
    if scored_comps:
        st.write("Sold Comp Preview")
        table_rows = []
        included_keys = set()
        for idx, comp in enumerate(scored_comps):
            default_include = bool(comp.get("include_default", False))
            include = st.checkbox(
                f"Include comp {idx + 1}: {comp.get('comp_address') or 'Unknown address'}",
                value=default_include,
                key=f"auto_comp_include_{idx}",
            )
            if include:
                included_keys.add(str(idx))
            table_rows.append(
                {
                    "Address": comp.get("comp_address", ""),
                    "Sold Price": money(comp.get("sold_price", 0)),
                    "Sold Date": comp.get("sold_date", ""),
                    "Beds": comp.get("beds", 0),
                    "Baths": comp.get("baths", 0),
                    "Sqft": comp.get("square_feet", 0),
                    "Distance": comp.get("distance_miles", 0),
                    "Source": comp.get("source", ""),
                    "Score": comp.get("score", ""),
                    "Include?": "Yes" if include else "No",
                    "Why excluded / flags": "; ".join(comp.get("flags", [])),
                }
            )

        summary = calculate_arv_from_comps(scored_comps, included_keys)
        store_auto_arv_summary(scored_comps, summary)
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Recommended ARV", money(summary.get("recommended_arv", 0)))
        m2.metric("ARV Range", f"{money(summary.get('low_arv', 0))} - {money(summary.get('high_arv', 0))}")
        m3.metric("ARV Confidence", summary.get("arv_confidence", "Not enough data"))
        m4.metric("Included / Total", f"{len(included_keys)} / {len(scored_comps)}")
        st.info(summary.get("explanation", ""))

        manual_avg = manual_comps_average()
        auto_arv = safe_float(summary.get("recommended_arv", 0))
        if manual_avg > 0 and auto_arv > 0 and abs(auto_arv - manual_avg) / manual_avg > 0.15:
            st.warning("Manual comps and automatic sold comps differ by more than 15%. Review both before relying on the ARV.")

    for message in st.session_state.get("auto_comp_messages", []):
        st.caption(message)

    if use_best_clicked:
        if safe_float(st.session_state.get("auto_recommended_arv", 0)) > 0:
            st.session_state["use_auto_arv_over_manual_comps"] = True
            st.success("Automatic sold comp ARV selected. Manual ARV override still wins if entered.")
        else:
            st.warning("No automatic sold comp ARV is available yet.")



def render_comps_section(st, ui) -> None:

    pd = ui.pd
    re = ui.re
    money = ui.money
    calculate_arv_from_comps = ui.calculate_arv_from_comps
    store_auto_arv_summary = ui.store_auto_arv_summary
    radius_to_float = ui.radius_to_float
    get_sold_comps = ui.get_sold_comps
    sold_comps_from_apify_rows = ui.sold_comps_from_apify_rows
    sold_comps_from_csv_rows = ui.sold_comps_from_csv_rows
    sold_comps_from_pasted_text = ui.sold_comps_from_pasted_text
    manual_comp_records = ui.manual_comp_records
    score_sold_comps = ui.score_sold_comps
    comp_subject = ui.comp_subject
    manual_comps_average = ui.manual_comps_average
    safe_float = ui.safe_float
    resolve_value_source = ui.resolve_value_source
    get_market_profile = ui.get_market_profile
    get_market_slow_flip_lead_search_max = ui.get_market_slow_flip_lead_search_max
    resolve_slow_flip_max_buy_price = ui.resolve_slow_flip_max_buy_price
    get_market_wholesale_buyer_percent = ui.get_market_wholesale_buyer_percent
    advanced_wholesale_buyer_model = ui.advanced_wholesale_buyer_model
    percent_label = ui.percent_label
    is_above_slow_flip_max_buy_price = ui.is_above_slow_flip_max_buy_price
    manual_wholesale_override = ui.manual_wholesale_override
    wholesale_buyer_percent_arv = ui.wholesale_buyer_percent_arv
    render_automatic_sold_comps_section(st, ui)
    st.markdown("### Manual Comp Entry Fallback")
    st.caption("Use this when RentCast cannot find value/comps. Enter 1 to 5 sold or listed comps.")

    comp_rows = []
    for idx in range(1, 6):
        with st.expander(f"Comparable Property {idx}", expanded=(idx == 1)):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.text_input("Address", key=f"manual_comp_{idx}_address")
            with c2:
                st.number_input(
                    "Sold/list price",
                    min_value=0,
                    step=1000,
                    key=f"manual_comp_{idx}_price",
                )

            c3, c4, c5 = st.columns(3)
            with c3:
                st.number_input("Beds", min_value=0.0, step=0.5, key=f"manual_comp_{idx}_beds")
            with c4:
                st.number_input("Baths", min_value=0.0, step=0.5, key=f"manual_comp_{idx}_baths")
            with c5:
                st.number_input("Sqft", min_value=0, step=50, key=f"manual_comp_{idx}_sqft")

            st.text_input("Condition", key=f"manual_comp_{idx}_condition")
            st.text_area("Notes", height=80, key=f"manual_comp_{idx}_notes")

        price = safe_float(st.session_state.get(f"manual_comp_{idx}_price", 0))
        if price > 0:
            comp_rows.append(
                {
                    "address": st.session_state.get(f"manual_comp_{idx}_address", ""),
                    "sold/list price": price,
                    "beds": st.session_state.get(f"manual_comp_{idx}_beds", 0),
                    "baths": st.session_state.get(f"manual_comp_{idx}_baths", 0),
                    "sqft": st.session_state.get(f"manual_comp_{idx}_sqft", 0),
                    "condition": st.session_state.get(f"manual_comp_{idx}_condition", ""),
                    "notes": st.session_state.get(f"manual_comp_{idx}_notes", ""),
                }
            )

    comps_average = manual_comps_average()
    st.metric("Average comp value", money(comps_average))
    if comp_rows:
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

    st.number_input(
        "Manual ARV override",
        min_value=0,
        step=1000,
        key="manual_arv_override",
        help="Highest priority. Use this when you want to override RentCast, sheet ARV, or manual comps.",
    )

    resolved_arv, value_source = resolve_value_source()
    st.session_state["arv"] = int(resolved_arv) if resolved_arv > 0 else 0
    st.session_state["value_source"] = value_source

    st.markdown("### Value / Wholesale Reference")
    st.caption(f"Value Source: {value_source}")
    st.caption(f"ARV Source Used: {st.session_state.get('arv_source_used', value_source)}")
    st.caption(f"ARV Confidence: {st.session_state.get('arv_confidence', 'Not enough data')}")
    if st.session_state.get("arv_fallback_reason"):
        st.caption(st.session_state.get("arv_fallback_reason"))
    for warning in st.session_state.get("arv_fallback_warnings", []):
        st.warning(warning)

    market_profile = get_market_profile(st.session_state.get("repair_market", "Central IL"))
    slow_flip_lead_search_max = get_market_slow_flip_lead_search_max(st.session_state.get("repair_market", "Central IL"))
    slow_flip_max_buy_price, slow_flip_max_source = resolve_slow_flip_max_buy_price(st.session_state.get("repair_market", "Central IL"))
    st.session_state["slow_flip_lead_search_max"] = int(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else 0
    st.session_state["slow_flip_max_buy_price_used"] = int(slow_flip_max_buy_price) if slow_flip_max_buy_price > 0 else 0
    st.session_state["slow_flip_max_source"] = slow_flip_max_source
    market_default_buyer_percent = get_market_wholesale_buyer_percent(st.session_state.get("repair_market", "Central IL"))
    wholesale_model = advanced_wholesale_buyer_model(
        market=st.session_state.get("repair_market", "Central IL"),
        arv=float(st.session_state.get("arv", 0) or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
        notes=st.session_state.get("notes", ""),
        repair_notes=st.session_state.get("repair_notes", "") + " " + st.session_state.get("manual_repair_notes", ""),
        property_type=st.session_state.get("property_type", ""),
        days_on_market=int(st.session_state.get("days_on_market", 0) or 0),
        buyer_demand_confidence=st.session_state.get("buyer_demand_confidence", "Medium"),
        market_type=st.session_state.get("market_type", "Auto"),
        occupancy=st.session_state.get("occupancy", "Unknown"),
        livable=st.session_state.get("livable", "Unknown"),
        exit_confidence=st.session_state.get("exit_strategy_confidence", "Unknown"),
    )
    market_buyer_percent = wholesale_model["buyer_percent"]
    market_adjustments = wholesale_model["reasons"]
    final_wholesale_buyer_percent = float(wholesale_buyer_percent_arv) if manual_wholesale_override else market_buyer_percent
    wholesale_buyer_percent_source = "Manual Override" if manual_wholesale_override else "Market Default"

    p1, p2, p3 = st.columns(3)
    p1.info(f"Market Profile: {market_profile.get('buyer_profile', 'Normal investor market')}")
    p2.info(f"Market Repair Multiplier: {float(market_profile.get('repair_multiplier', 1.0)):.2f}x")
    p3.info(f"Wholesale Buyer % Source: {wholesale_buyer_percent_source}")
    if slow_flip_lead_search_max > 0:
        st.caption(f"Slow Flip Lead Search Max: {money(slow_flip_lead_search_max)}")
    if slow_flip_max_buy_price > 0:
        current_buy_price = safe_float(st.session_state.get("contract_price", 0)) or safe_float(st.session_state.get("asking_price", 0))
        above_slow_flip_max_buy_price = is_above_slow_flip_max_buy_price(current_buy_price, slow_flip_max_buy_price)
        st.caption(f"Slow Flip Max Buy Price: {money(slow_flip_max_buy_price)} ({slow_flip_max_source})")
        st.caption(f"Above Slow Flip Max Buy Price? {'Yes' if above_slow_flip_max_buy_price else 'No'}")
    st.caption(f"Market buyer % of ARV used: {percent_label(final_wholesale_buyer_percent)}")
    st.caption(f"Wholesale Buyer % Range: {wholesale_model['range']} | {wholesale_model['tier']}")
    st.caption("Wholesale buyers in this market will likely need to be around "
               f"{percent_label(final_wholesale_buyer_percent)} of ARV because {wholesale_model['reason_text']}")
    wt1, wt2, wt3 = st.columns(3)
    wt1.metric("Conservative buyer target", money(wholesale_model["conservative_buyer_target"]))
    wt2.metric("Aggressive buyer target", money(wholesale_model["aggressive_buyer_target"]))
    wt3.metric("Recommended wholesale max offer", money(wholesale_model["recommended_wholesale_max_offer"]))
    if not manual_wholesale_override and market_adjustments:
        st.caption(" ".join(market_adjustments))

    v1, v2 = st.columns(2)

    with v1:
        st.number_input(
            "ARV / estimated resale value",
            min_value=0,
            step=1000,
            key="arv",
            help="Required on every deal. Auto-filled from RentCast, sheet ARV, manual comps, or manual override.",
        )

    with v2:
        st.number_input(
            "Estimated repairs",
            min_value=0,
            step=1000,
            key="repairs",
            help="Use $0 only when repairs are truly unknown or not needed for the slow-flip decision.",
        )

    if float(st.session_state.get("arv", 0) or 0) <= 0:
        st.warning("ARV is missing. Add ARV or manual comps before making a final offer.")

