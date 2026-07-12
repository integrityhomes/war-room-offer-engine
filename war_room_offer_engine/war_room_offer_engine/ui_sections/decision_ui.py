from __future__ import annotations

try:
    from ui_sections.rent_fallback_ui import render_rent_fallback_section
except ImportError:
    try:
        from .rent_fallback_ui import render_rent_fallback_section
    except ImportError:
        from war_room_offer_engine.ui_sections.rent_fallback_ui import render_rent_fallback_section


def render_decision_section(st, ui, exit_mode, uploaded_repair_files) -> None:

    pd = ui.pd
    money = ui.money
    build_ai_summary = ui.build_ai_summary
    Assumptions = ui.Assumptions
    DealInput = ui.DealInput
    analyze_deal = ui.analyze_deal
    resolve_value_source = ui.resolve_value_source
    get_market_slow_flip_lead_search_max = ui.get_market_slow_flip_lead_search_max
    resolve_slow_flip_max_buy_price = ui.resolve_slow_flip_max_buy_price
    get_market_wholesale_buyer_percent = ui.get_market_wholesale_buyer_percent
    advanced_wholesale_buyer_model = ui.advanced_wholesale_buyer_model
    render_final_decision_box = ui.render_final_decision_box
    build_repair_breakdown = ui.build_repair_breakdown
    render_repair_estimate_breakdown = ui.render_repair_estimate_breakdown
    build_deal_log_row = ui.build_deal_log_row
    render_save_deal_analysis = ui.render_save_deal_analysis
    percent_label = ui.percent_label
    safe_condition_text = ui.safe_condition_text
    min_assignment_fee = ui.min_assignment_fee
    exception_assignment_fee = ui.exception_assignment_fee
    slow_flip_rent_multiple = ui.slow_flip_rent_multiple
    close_title_buffer = ui.close_title_buffer
    target_offer_discount = ui.target_offer_discount
    slow_flip_max_offer_cap = ui.slow_flip_max_offer_cap
    slow_flip_first_offer_gap = ui.slow_flip_first_offer_gap
    manual_wholesale_override = ui.manual_wholesale_override
    wholesale_buyer_percent_arv = ui.wholesale_buyer_percent_arv
    st.text_area("Seller/agent notes, condition, occupancy, motivation", height=120, key="notes")
    st.caption(f"Current source: {st.session_state.get('source_mode')} / {st.session_state.get('lead_source')}")
    render_rent_fallback_section(st, ui)

    analyze = st.button("Analyze Deal", type="primary")

    if analyze:
        asking_price_value = float(st.session_state.get("asking_price", 0) or 0)
        contract_price_value = float(st.session_state.get("contract_price", 0) or 0)
        analysis_price = contract_price_value if contract_price_value > 0 else asking_price_value
        resolved_arv, value_source = resolve_value_source()
        st.session_state["value_source"] = value_source

        if resolved_arv <= 0:
            st.warning("ARV is missing. Add ARV or manual comps before making a final offer.")

        slow_flip_lead_search_max = get_market_slow_flip_lead_search_max(st.session_state.get("repair_market", "Central IL"))
        slow_flip_max_buy_price, slow_flip_max_source = resolve_slow_flip_max_buy_price(st.session_state.get("repair_market", "Central IL"))
        st.session_state["slow_flip_lead_search_max"] = int(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else 0
        st.session_state["slow_flip_max_buy_price_used"] = int(slow_flip_max_buy_price) if slow_flip_max_buy_price > 0 else 0
        st.session_state["slow_flip_max_source"] = slow_flip_max_source
        market_default_buyer_percent = get_market_wholesale_buyer_percent(st.session_state.get("repair_market", "Central IL"))
        wholesale_model = advanced_wholesale_buyer_model(
            market=st.session_state.get("repair_market", "Central IL"),
            arv=float(resolved_arv or 0),
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
        final_wholesale_buyer_percent = wholesale_model["buyer_percent"]
        if manual_wholesale_override:
            final_wholesale_buyer_percent = float(wholesale_buyer_percent_arv)
        wholesale_buyer_percent_source = "Manual Override" if manual_wholesale_override else "Market Default"

        assumptions = Assumptions(
            min_assignment_fee=float(min_assignment_fee),
            exception_assignment_fee=float(exception_assignment_fee),
            slow_flip_rent_multiple=float(slow_flip_rent_multiple),
            close_title_buffer=float(close_title_buffer),
            target_offer_discount=float(target_offer_discount),
            wholesale_buyer_percent_arv=float(final_wholesale_buyer_percent),
            wholesale_buyer_percent_source=wholesale_buyer_percent_source,
            wholesale_buyer_percent_range=wholesale_model.get("range", ""),
            wholesale_buyer_percent_reason=wholesale_model.get("reason_text", ""),
            market_liquidity_tier=wholesale_model.get("tier", ""),
            market_wholesale_buyer_percent=float(market_default_buyer_percent),
            slow_flip_max_offer_cap=float(slow_flip_max_offer_cap),
            slow_flip_first_offer_gap=float(slow_flip_first_offer_gap),
            slow_flip_lead_search_max=float(slow_flip_lead_search_max),
            slow_flip_lead_search_source="Market Default",
            above_slow_flip_lead_search_range=bool(slow_flip_lead_search_max > 0 and analysis_price > slow_flip_lead_search_max),
            inside_slow_flip_lead_search_range=bool(slow_flip_lead_search_max > 0 and analysis_price <= slow_flip_lead_search_max),
            slow_flip_max_buy_price=float(slow_flip_max_buy_price),
            slow_flip_max_source=slow_flip_max_source,
            above_slow_flip_max_buy_price=bool(slow_flip_max_buy_price > 0 and analysis_price > slow_flip_max_buy_price),
        )

        analysis_notes = "\n".join(
            part
            for part in [
                st.session_state.get("notes", ""),
                st.session_state.get("repair_notes", ""),
                st.session_state.get("manual_repair_notes", ""),
            ]
            if str(part or "").strip()
        )

        deal = DealInput(
            address=st.session_state["address"],
            market=st.session_state["market"],
            lead_type=st.session_state["lead_type"],
            exit_mode=exit_mode,
            asking_price=analysis_price,
            rent=float(st.session_state["rent"]),
            beds=float(st.session_state["beds"]),
            baths=float(st.session_state["baths"]),
            sqft=float(st.session_state["sqft"]),
            taxes=float(st.session_state["taxes"]),
            status=st.session_state["status"],
            occupancy=st.session_state["occupancy"],
            livable=st.session_state["livable"],
            days_on_market=int(st.session_state["days_on_market"]),
            notes=analysis_notes,
            arv=float(resolved_arv or 0),
            repairs=float(st.session_state.get("repairs", 0) or 0),
        )

        result = analyze_deal(deal, assumptions)
        best = result["best"]

        st.divider()
        final_summary = render_final_decision_box(
            result=result,
            deal=deal,
            value_source=value_source,
            uploaded_files=uploaded_repair_files,
            repair_notes=st.session_state.get("repair_notes", ""),
            assumptions=assumptions,
        )
        repair_breakdown = build_repair_breakdown()
        render_repair_estimate_breakdown(repair_breakdown)
        deal_log_row = build_deal_log_row(
            result=result,
            deal=deal,
            final_summary=final_summary,
            value_source=value_source,
            asking_price=asking_price_value,
            contract_price=contract_price_value,
        )
        deal_log_row.update(
            {
                "universal_listing_source": st.session_state.get("universal_listing_source", ""),
                "universal_listing_url": st.session_state.get("universal_listing_url", ""),
                "universal_import_method": st.session_state.get("universal_import_method", ""),
                "imported_listing_source": st.session_state.get("imported_listing_source", ""),
                "imported_listing_price": st.session_state.get("imported_listing_price", 0),
                "imported_beds": st.session_state.get("imported_beds", 0),
                "imported_baths": st.session_state.get("imported_baths", 0),
                "imported_sqft": st.session_state.get("imported_sqft", 0),
                "imported_dom": st.session_state.get("imported_dom", 0),
                "imported_agent_name": st.session_state.get("imported_agent_name", ""),
                "imported_agent_phone": st.session_state.get("imported_agent_phone", ""),
                "imported_agent_email": st.session_state.get("imported_agent_email", ""),
                "imported_brokerage": st.session_state.get("imported_brokerage", ""),
                "imported_listing_status": st.session_state.get("imported_listing_status", ""),
                "imported_source_confidence": st.session_state.get("imported_source_confidence", ""),
                "imported_missing_fields": "; ".join(st.session_state.get("universal_import_missing_fields", []) or []),
                "imported_conflict_flags": "; ".join(st.session_state.get("universal_import_conflict_flags", []) or []),
                "field_source_map_json": st.session_state.get("field_source_map_json", ""),
                "one_load_lead_type": st.session_state.get("one_load_lead_type", ""),
                "one_load_lead_source": st.session_state.get("one_load_lead_source", ""),
                "one_load_input_method": st.session_state.get("one_load_input_method", ""),
                "one_load_input_value": st.session_state.get("one_load_listing_url") or st.session_state.get("one_load_property_address") or st.session_state.get("one_load_apify_dataset", ""),
                "seller_name": st.session_state.get("seller_name", ""),
                "seller_phone": st.session_state.get("seller_phone", ""),
                "seller_email": st.session_state.get("seller_email", ""),
                "seller_motivation": st.session_state.get("seller_motivation", ""),
                "seller_timeline": st.session_state.get("seller_timeline", ""),
                "seller_desired_price": st.session_state.get("seller_desired_price", 0),
                "seller_condition_notes": st.session_state.get("seller_condition_notes", ""),
                "seller_repair_notes": st.session_state.get("seller_repair_notes", ""),
                "one_load_run_success": st.session_state.get("one_load_run_success", "No"),
                "one_load_missing_fields": "; ".join(st.session_state.get("one_load_missing_fields", []) or []),
                "one_load_data_sources_used": "; ".join(st.session_state.get("one_load_data_sources_used", []) or []),
                "one_load_arv_source": st.session_state.get("arv_source_used", st.session_state.get("value_source", "")),
                "one_load_arv_confidence": st.session_state.get("arv_confidence", ""),
                "one_load_rent_confidence": st.session_state.get("rental_demand_confidence", ""),
                "one_load_repair_source": st.session_state.get("repair_source", ""),
                "one_load_buyer_demand_confidence": st.session_state.get("buyer_demand_confidence", ""),
                "one_load_deal_protection_status": st.session_state.get("deal_protection_mode", ""),
                "one_load_final_answer": st.session_state.get("one_load_final_answer", ""),
                "one_load_next_action": st.session_state.get("one_load_next_action", ""),
            }
        )
        render_save_deal_analysis(deal_log_row)

        st.divider()
        st.subheader("Decision")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Deal Grade", result["grade"])
        m2.metric("Best Exit", result["best_exit"])
        m3.metric("First Offer", money(best.get("offer_to_send", best.get("target_offer_low", 0))))
        m4.metric("Internal Max", money(best["max_offer"]))

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Slow Flip Numbers")
            slow = result["slow_flip"]
            st.write({
                "Resale to slow flipper": money(slow["resale_to_slow_flipper"]),
                "First offer to send": money(slow.get("offer_to_send", 0)),
                "Internal max offer": money(slow["max_offer"]),
                "Rent formula max before cap": money(slow.get("rent_formula_max_offer_before_cap", 0)),
                "Normal slow flip cap": money(slow.get("normal_slow_flip_cap", 0)),
                "Slow Flip Lead Search Max": money(slow_flip_lead_search_max) if slow_flip_lead_search_max > 0 else "Not set",
                "Slow Flip Max Buy Price": money(slow.get("slow_flip_max_buy_price", 0)) if slow.get("slow_flip_max_buy_price", 0) > 0 else "Not set",
                "Slow Flip Max Source": slow.get("slow_flip_max_source", ""),
                "Above Slow Flip Max Buy Price?": "Yes" if slow.get("above_slow_flip_max_buy_price") else "No",
                "Estimated fee at buy price": money(slow["estimated_fee_at_ask"]),
            })
            slow_resale_value = float(slow.get("resale_to_slow_flipper", 0) or 0)
            buyer_payment_support = float(st.session_state.get("rent", 0) or 0)
            annual_taxes_value = float(st.session_state.get("taxes", 0) or 0)

            if slow_resale_value >= 50000 and (buyer_payment_support < 1200 or annual_taxes_value > 1500):
                st.warning("$50k+ slow-flip resale warning: still show the resale price, but only push it hard if buyer payment support is about $1,200/month and taxes are low enough.")
        with c2:
            st.subheader("Value / Wholesale Reference")
            wholesale = result["wholesale"]
            st.write({
            "ARV / estimated value": money(resolved_arv),
            "Value Source": value_source,
            "Repairs": money(st.session_state.get("repairs", 0)),
            "Wholesale Buyer % Source": wholesale.get("buyer_percent_source", ""),
            "Market buyer % of ARV used": percent_label(wholesale.get("buyer_percent_arv", 0)),
            "Buyer % Range": wholesale.get("buyer_percent_range", ""),
            "Market Liquidity Tier": wholesale.get("market_liquidity_tier", ""),
            "Buyer % Reason": wholesale.get("buyer_percent_reason", ""),
            "Conservative buyer target": money(wholesale.get("conservative_buyer_target", 0)),
            "Aggressive buyer target": money(wholesale.get("aggressive_buyer_target", 0)),
            "Buyer target": money(wholesale["buyer_target"]),
            "Wholesale max offer": money(wholesale["max_offer"]),
            "Wholesale estimated fee at buy price": money(wholesale["estimated_fee_at_ask"])
            })

        st.subheader("Risk Notes")
        for risk in result["risks"]:
            st.warning(safe_condition_text(risk))

        st.subheader("Suggested Message")
        st.text_area("Copy/paste message", result["suggested_message"], height=180)

        with st.expander("AI Summary - optional if OpenAI key is added"):
            ai_summary = build_ai_summary(result)
            if ai_summary:
                st.write(ai_summary)
            else:
                st.info("No OpenAI key found. Add OPENAI_API_KEY in Streamlit secrets later to enable this section.")

        with st.expander("Download Analysis CSV"):
            row = {
                **deal_log_row,
                "grade": result["grade"],
                "final_decision": final_summary["final_decision"],
                "team_action": final_summary["team_action"],
                "missing_info": "; ".join(final_summary["missing_info"]),
                "risk_flags": "; ".join(final_summary["risk_flags"]),
                "decision_reason": final_summary["decision_reason"],
                "exit_mode": exit_mode,
                "internal_max_offer": best["max_offer"],
                "estimated_fee_at_ask": best["estimated_fee_at_ask"],
                "livable": st.session_state["livable"],
                "occupancy": st.session_state["occupancy"],
            }
            df = pd.DataFrame([row])
            st.dataframe(df, use_container_width=True)
            st.download_button(
                "Download CSV",
                data=df.to_csv(index=False),
                file_name="offer_engine_analysis.csv",
                mime="text/csv",
            )
    else:
        st.info("Enter or pull the property data, then click Analyze Deal.")
