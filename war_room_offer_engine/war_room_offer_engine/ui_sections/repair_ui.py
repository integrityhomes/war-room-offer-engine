from __future__ import annotations

try:
    from ui_sections.comps_ui import render_comps_section
except ImportError:
    try:
        from .comps_ui import render_comps_section
    except ImportError:
        from war_room_offer_engine.ui_sections.comps_ui import render_comps_section


def render_repair_section(st, ui):
    pd = ui.pd
    money = ui.money
    available_markets = ui.available_markets
    get_market_slow_flip_lead_search_max = ui.get_market_slow_flip_lead_search_max
    resolve_slow_flip_max_buy_price = ui.resolve_slow_flip_max_buy_price
    safe_float = ui.safe_float
    analyze_repairs = ui.analyze_repairs
    repair_number_for_offer = ui.repair_number_for_offer
    repair_cushion_percent_value = ui.repair_cushion_percent_value
    mold_verified_bool = ui.mold_verified_bool
    condition_wording_used = ui.condition_wording_used
    generate_boots_on_ground_notes = ui.generate_boots_on_ground_notes
    safe_condition_text = ui.safe_condition_text
    render_repair_number_explanation = ui.render_repair_number_explanation
    resolve_repair_source = ui.resolve_repair_source

    st.markdown('<div id="repairs"></div>', unsafe_allow_html=True)
    st.header("🔧 Repairs & Property Condition")
    st.caption(
        "Use photos, walkthrough video, repair notes, or a known contractor number. "
        "This section now stays full-width so the complete repair workspace is easy to find and use."
    )

    status1, status2, status3, status4 = st.columns(4)
    status1.metric("Current repair number", money(st.session_state.get("repairs", 0)))
    status2.metric("Repair source", st.session_state.get("repair_source", "Missing"))
    status3.metric("Scope confidence", st.session_state.get("repair_scope_confidence", "Unknown"))
    status4.metric("Pricing market", st.session_state.get("repair_market", "Central IL"))

    with st.expander("Property facts used by the repair analyzer", expanded=False):
        facts1, facts2, facts3 = st.columns(3)
        with facts1:
            st.text_input("Market / city", key="market", placeholder="Decatur IL")
            st.selectbox("Lead type", ["Agent", "Seller", "Wholesaler", "Other"], key="lead_type")
            st.selectbox("Listing/status", ["Active", "Pending", "Sold", "Off-market", "Unknown"], key="status")
            st.number_input("Days on market", min_value=0, step=1, key="days_on_market")
        with facts2:
            st.number_input("Asking price", min_value=0, step=1000, key="asking_price")
            st.number_input("Contract / Buy Price", min_value=0, step=1000, key="contract_price")
            st.number_input("Rent estimate", min_value=0, step=25, key="rent")
            st.selectbox("Occupancy", ["Unknown", "Vacant", "Tenant occupied", "Owner occupied"], key="occupancy")
            st.selectbox("Livable now?", ["Unknown", "Yes", "No"], key="livable")
        with facts3:
            st.number_input("Beds", min_value=0.0, step=0.5, key="beds")
            st.number_input("Baths", min_value=0.0, step=0.5, key="baths")
            st.number_input("Sq ft", min_value=0, step=50, key="sqft")
            st.number_input("Annual taxes", min_value=0, step=100, key="taxes")

    st.subheader("3. Repair / Condition Analyzer")

    market_col, finish_col, contingency_col = st.columns(3)
    with market_col:
        st.selectbox(
            "Repair pricing market",
            available_markets(),
            index=0,
            key="repair_market",
        )
        st.number_input(
            "Manual Slow Flip Max Override",
            min_value=0,
            step=5000,
            key="manual_slow_flip_max_override",
            help="Leave at $0 to use the market default. Every Virginia market defaults to a $50,000 slow-flip max buy price.",
        )
    with finish_col:
        st.selectbox(
            "Repair finish level",
            ["Investor Basic", "Rental Ready", "Retail Ready"],
            index=1,
            key="repair_level",
        )
        st.selectbox(
            "Repair Scope Confidence",
            ["Photos only", "Walkthrough", "Contractor verified", "Unknown"],
            key="repair_scope_confidence",
        )
    with contingency_col:
        st.number_input(
            "Repair contingency %",
            min_value=0,
            max_value=50,
            value=12,
            step=1,
            key="repair_contingency",
        )
        st.selectbox(
            "Repair Cushion",
            ["0%", "5%", "10%", "15%", "20%"],
            key="repair_cushion_percent",
        )

    slow_flip_lead_search_max = get_market_slow_flip_lead_search_max(
        st.session_state.get("repair_market", "Central IL")
    )
    slow_flip_max_buy_price, slow_flip_max_source = resolve_slow_flip_max_buy_price(
        st.session_state.get("repair_market", "Central IL")
    )
    current_slow_flip_price = safe_float(st.session_state.get("contract_price", 0)) or safe_float(
        st.session_state.get("asking_price", 0)
    )
    st.session_state["slow_flip_lead_search_max"] = int(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else 0
    st.session_state["slow_flip_lead_search_source"] = "Market Default"
    st.session_state["above_slow_flip_lead_search_range"] = bool(
        slow_flip_lead_search_max > 0 and current_slow_flip_price > slow_flip_lead_search_max
    )
    st.session_state["inside_slow_flip_lead_search_range"] = bool(
        slow_flip_lead_search_max > 0 and current_slow_flip_price <= slow_flip_lead_search_max
    )
    st.session_state["slow_flip_max_buy_price_used"] = int(slow_flip_max_buy_price) if slow_flip_max_buy_price > 0 else 0
    st.session_state["slow_flip_max_source"] = slow_flip_max_source
    st.session_state["above_slow_flip_max_buy_price"] = bool(
        slow_flip_max_buy_price > 0 and current_slow_flip_price > slow_flip_max_buy_price
    )

    sf1, sf2 = st.columns(2)
    sf1.info(
        f"Slow Flip Lead Search Max: {money(slow_flip_lead_search_max)}"
        if slow_flip_lead_search_max > 0
        else "Slow Flip Lead Search Max: Not set"
    )
    sf2.info(
        f"Slow Flip Max Buy Price: {money(slow_flip_max_buy_price)} ({slow_flip_max_source})"
        if slow_flip_max_buy_price > 0
        else "Slow Flip Max Buy Price: Not set"
    )

    with st.expander("Repair pricing settings", expanded=False):
        settings1, settings2, settings3 = st.columns(3)
        with settings1:
            st.selectbox(
                "Pricing Mode",
                [
                    "Budget handyman",
                    "Investor standard",
                    "Licensed contractor",
                    "Conservative high-risk",
                ],
                key="repair_pricing_mode",
                help="Changes how the app calibrates the price-book estimate against contractor reality.",
            )
        with settings2:
            st.selectbox(
                "Market Labor Cost",
                ["Low-cost market", "Normal market", "High-cost market", "Unknown"],
                key="market_labor_cost",
            )
        with settings3:
            st.number_input(
                "Manual Repair Adjustment",
                step=500,
                key="manual_repair_adjustment",
                help="Add or subtract dollars from the calculated repair estimate.",
            )
            st.toggle("Show full repair math?", key="show_full_repair_math")

    scope_confidence = st.session_state.get("repair_scope_confidence")
    if scope_confidence in ["Photos only", "Unknown"]:
        st.warning(
            "Repair scope confidence is limited. Add a walkthrough or contractor estimate before treating the repair number as final."
        )
    elif scope_confidence == "Contractor verified":
        st.success(
            "Contractor verified scope selected. Final offer still depends on the complete deal math."
        )

    uploaded_repair_files = st.file_uploader(
        "Upload property photos or boots-on-ground walkthrough video",
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"],
        accept_multiple_files=True,
        key="repair_media_files",
    )

    st.selectbox(
        "Moisture/biological growth verified?",
        [
            "No",
            "Unknown",
            "Suspected staining only",
            "Yes - inspector verified",
            "Yes - seller disclosed",
        ],
        key="mold_verified",
        help="When not verified, the app uses moisture/discoloration wording.",
    )
    st.caption(condition_wording_used())

    media_files_for_notes = uploaded_repair_files or []
    photo_files_for_notes = [
        file
        for file in media_files_for_notes
        if str(getattr(file, "name", "")).lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]
    video_files_for_notes = [
        file
        for file in media_files_for_notes
        if str(getattr(file, "name", "")).lower().endswith((".mp4", ".mov", ".m4v", ".avi"))
    ]
    selected_video_for_notes = video_files_for_notes[0] if video_files_for_notes else None

    if st.button("Generate boots-on-ground notes from media", type="secondary"):
        if not photo_files_for_notes and selected_video_for_notes is None:
            st.warning("Upload at least one photo or video first.")
        else:
            with st.spinner("Reviewing uploaded photos/video frames and writing boots-on-ground notes..."):
                generated_notes = generate_boots_on_ground_notes(
                    photo_files_for_notes,
                    selected_video_for_notes,
                )
            st.session_state["repair_notes"] = safe_condition_text(generated_notes)
            st.success("Boots-on-ground notes created. Review them, then generate the repair estimate.")

    st.text_area(
        "Boots-on-ground repair notes",
        height=170,
        key="repair_notes",
        placeholder=(
            "Example: Roof looks old, kitchen needs cabinets, bathroom floor is soft, "
            "furnace missing, water heater old, windows damaged, trash out needed."
        ),
    )

    generate_repair_estimate = st.button("Generate Repair Estimate", type="primary")
    if generate_repair_estimate:
        repair_analysis = analyze_repairs(
            notes=st.session_state.get("repair_notes", ""),
            sqft=float(st.session_state.get("sqft", 0) or 1000),
            baths=float(st.session_state.get("baths", 0) or 1),
            uploaded_files=uploaded_repair_files,
            market=st.session_state.get("repair_market", "Central IL"),
            repair_level=st.session_state.get("repair_level", "Rental Ready"),
            contingency_pct=float(st.session_state.get("repair_contingency", 12) or 0) / 100,
            pricing_mode=st.session_state.get("repair_pricing_mode", "Investor standard"),
            repair_scope_confidence=st.session_state.get("repair_scope_confidence", "Unknown"),
            market_labor_cost=st.session_state.get("market_labor_cost", "Unknown"),
            repair_cushion_percent=repair_cushion_percent_value(),
            manual_repair_adjustment=float(st.session_state.get("manual_repair_adjustment", 0) or 0),
            mold_verified=mold_verified_bool(),
        )
        st.session_state["repair_analysis"] = repair_analysis
        st.session_state["recommended_repairs_from_analyzer"] = repair_number_for_offer(repair_analysis)

    if st.session_state.get("repair_analysis"):
        repair_analysis = st.session_state["repair_analysis"]
        estimate = repair_analysis.get("estimate", {})
        st.markdown("#### Repair Estimate Result")
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Low Repairs", money(estimate.get("total_low", 0)))
        e2.metric("Likely Repairs", money(estimate.get("total_likely", 0)))
        e3.metric("High Repairs", money(estimate.get("total_high", 0)))
        e4.metric("Use In Offer", money(repair_analysis.get("recommended_repair_number", 0)))
        st.info(f"Confidence: {repair_analysis.get('confidence', 'Low')}")

        if repair_analysis.get("red_flags"):
            st.error(
                "Red flags needing contractor quote: "
                + ", ".join(
                    safe_condition_text(flag) for flag in repair_analysis.get("red_flags", [])
                )
            )

        render_repair_number_explanation(repair_analysis.get("repair_calibration", {}))
        line_items = estimate.get("line_items", [])
        if line_items:
            st.dataframe(
                pd.DataFrame(line_items).assign(
                    label=lambda frame: frame["label"].map(safe_condition_text),
                    notes=lambda frame: frame["notes"].map(safe_condition_text),
                )[["category", "label", "quantity", "unit", "low", "likely", "high", "notes"]],
                use_container_width=True,
            )

        st.text_area(
            "Repair estimate summary",
            value=safe_condition_text(repair_analysis.get("summary", "")),
            height=260,
        )
        if st.button("Use likely repair number in offer", type="primary"):
            st.session_state["repairs"] = int(
                repair_analysis.get("recommended_repair_number", 0) or 0
            )
            st.session_state["repair_source"] = "AI Repair Estimate"
            st.success("Calibrated repair number copied into the deal analysis.")

    with st.expander("Manual repair estimate override", expanded=False):
        st.caption(
            "Use this when you already know the repair number. A manual repair estimate overrides the AI repair estimate."
        )
        st.number_input(
            "Manual repair estimate amount",
            min_value=0,
            step=1000,
            key="manual_repair_estimate",
        )
        st.text_area(
            "Repair notes / scope",
            height=120,
            key="manual_repair_notes",
            placeholder="Example: Roof patch, kitchen refresh, LVP, paint, trash out.",
        )

    resolved_repairs, repair_source = resolve_repair_source()
    if resolved_repairs > 0:
        st.session_state["repairs"] = int(resolved_repairs)
    st.session_state["repair_source"] = repair_source
    st.info(f"Repair Source: {repair_source} | Current repair number: {money(resolved_repairs)}")

    st.divider()
    st.markdown('<div id="comps-arv"></div>', unsafe_allow_html=True)
    render_comps_section(st, ui)

    return uploaded_repair_files
