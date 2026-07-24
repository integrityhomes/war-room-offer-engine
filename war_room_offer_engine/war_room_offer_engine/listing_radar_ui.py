from __future__ import annotations

from typing import Any
from urllib.parse import quote

try:
    import listing_radar_client as client
    import listing_radar_integration as integration
    import team_offer_identity as identity
    from team_offer_integration import build_first_touch_outreach_for_team
except ImportError:
    try:
        from . import listing_radar_client as client
        from . import listing_radar_integration as integration
        from . import team_offer_identity as identity
        from .team_offer_integration import build_first_touch_outreach_for_team
    except ImportError:
        from war_room_offer_engine import listing_radar_client as client
        from war_room_offer_engine import listing_radar_integration as integration
        from war_room_offer_engine import team_offer_identity as identity
        from war_room_offer_engine.team_offer_integration import build_first_touch_outreach_for_team


def _money(value: Any) -> str:
    try:
        amount = float(value or 0)
    except Exception:
        amount = 0
    return f"${amount:,.0f}" if amount else "Missing"


def _text(value: Any, fallback: str = "Missing") -> str:
    text = str(value or "").strip()
    return text or fallback


def _invalidate(st) -> None:
    st.session_state.pop("listing_radar_last_result", None)
    st.session_state.pop("listing_radar_health", None)


def _queue_for_analysis(st, listing: dict[str, Any]) -> None:
    if integration.queue_for_one_load(st, listing):
        st.rerun()


def _update_workflow(st, listing: dict[str, Any], changes: dict[str, Any], success: str) -> None:
    teammate = identity.active_team_member(st.session_state)
    if not teammate:
        st.session_state[integration.HANDOFF_ERROR_KEY] = "Select the current team member before changing Listing Radar workflow."
        st.rerun()
    listing_key = str(listing.get("listing_key") or "").strip()
    result = client.update_queue(
        listing_key,
        {**changes, "updated_by": teammate},
    )
    if result.get("ok"):
        st.session_state[integration.HANDOFF_MESSAGE_KEY] = success
        st.session_state[integration.HANDOFF_ERROR_KEY] = ""
        _invalidate(st)
    else:
        st.session_state[integration.HANDOFF_ERROR_KEY] = result.get("error", "Listing Radar workflow update failed.")
    st.rerun()


def _load(st) -> dict[str, Any]:
    result = client.list_listings(
        query=st.session_state.get("listing_radar_query", ""),
        market_id=st.session_state.get("listing_radar_market", ""),
        feed_status=st.session_state.get("listing_radar_feed_status", ""),
        workflow_status=st.session_state.get("listing_radar_workflow_status", ""),
        limit=st.session_state.get("listing_radar_limit", 100),
    )
    st.session_state["listing_radar_last_result"] = result
    return result


def _market_options(st) -> list[tuple[str, str]]:
    cached = st.session_state.get("listing_radar_market_result")
    if not isinstance(cached, dict):
        cached = client.list_markets()
        st.session_state["listing_radar_market_result"] = cached
    markets = cached.get("markets", []) if cached.get("ok") else []
    options = [("", "All markets")]
    for market in markets:
        market_id = str(market.get("market_id") or "")
        name = str(market.get("market_name") or market_id)
        if market_id:
            options.append((market_id, name))
    return options


def _outreach(listing: dict[str, Any], teammate: str) -> dict[str, str]:
    return build_first_touch_outreach_for_team(
        agent_name=str(listing.get("agent_name") or ""),
        address=str(listing.get("address") or "the property"),
        asking_price=listing.get("asking_price", 0),
        buyer_name=teammate,
    )


def _render_listing_card(st, listing: dict[str, Any], index: int) -> None:
    teammate = identity.active_team_member(st.session_state)
    listing_key = str(listing.get("listing_key") or index)
    with st.container(border=True):
        top = st.columns([1.2, 3.2, 1.4, 1.2])
        photo = str(listing.get("primary_photo") or "").strip()
        if photo:
            top[0].image(photo, use_container_width=True)
        else:
            top[0].caption("No listing photo")

        address = _text(listing.get("address"), "Unknown address")
        city_state = " ".join(
            part for part in [str(listing.get("city") or ""), str(listing.get("state") or "")] if part
        )
        top[1].markdown(f"### {address}")
        top[1].caption(
            " | ".join(
                part
                for part in [
                    city_state,
                    str(listing.get("zip") or ""),
                    str(listing.get("market_id") or ""),
                    str(listing.get("feed_status") or ""),
                ]
                if part
            )
        )
        top[1].write(
            f"{_text(listing.get('beds'), '—')} bed | {_text(listing.get('baths'), '—')} bath | "
            f"{_text(listing.get('sqft'), '—')} sqft | DOM {_text(listing.get('days_on_market'), '—')}"
        )
        top[2].metric("Asking Price", _money(listing.get("asking_price")))
        price_change = float(listing.get("price_change") or 0)
        if price_change:
            top[2].caption(f"Change: {_money(price_change)}")
        top[3].metric("Workflow", _text(listing.get("workflow_status"), "New"))
        top[3].caption(f"Assigned: {_text(listing.get('assigned_to'), 'Unassigned')}")

        contact = st.columns([1.5, 1.15, 1.15, 1.15, 1.25, 1.7])
        agent = _text(listing.get("agent_name"), "Agent not found")
        brokerage = _text(listing.get("agent_brokerage"), "Brokerage missing")
        contact[0].write(f"**{agent}**")
        contact[0].caption(brokerage)

        url = str(listing.get("listing_url") or "").strip()
        if url:
            contact[1].link_button("Open Listing", url, use_container_width=True)
        else:
            contact[1].button("Open Listing", disabled=True, key=f"radar_no_url_{index}", use_container_width=True)

        phone = str(listing.get("agent_phone") or "").strip()
        if phone:
            contact[2].link_button("Call Agent", f"tel:{phone}", use_container_width=True)
        else:
            contact[2].button("Phone Missing", disabled=True, key=f"radar_no_phone_{index}", use_container_width=True)

        email = str(listing.get("agent_email") or "").strip()
        outreach = _outreach(listing, teammate) if teammate else {}
        if email:
            subject = quote(outreach.get("email_subject") or f"Question about {address}")
            body = quote(outreach.get("email_body") or "")
            contact[3].link_button("Email Agent", f"mailto:{email}?subject={subject}&body={body}", use_container_width=True)
        else:
            contact[3].button("Email Missing", disabled=True, key=f"radar_no_email_{index}", use_container_width=True)

        finder_url = integration.agent_contact_finder_url(listing)
        if finder_url:
            contact[4].link_button("Find Agent Contact", finder_url, use_container_width=True)
        else:
            contact[4].button(
                "Find Agent Contact",
                disabled=True,
                key=f"radar_no_finder_{index}",
                help="Add AGENT_CONTACT_FINDER_URL to Streamlit secrets to connect the existing Agent Contact Finder.",
                use_container_width=True,
            )

        if contact[5].button(
            "Analyze in Deal Engine",
            key=f"listing_radar_analyze_{listing_key}",
            type="primary",
            disabled=not bool(teammate),
            help=None if teammate else "Select the current team member above first.",
            use_container_width=True,
        ):
            _queue_for_analysis(st, listing)

        with st.expander("Team workflow", expanded=False):
            workflow = st.columns([1, 1, 1, 2.2])
            if workflow[0].button(
                "Assign to Me",
                key=f"radar_assign_{listing_key}",
                disabled=not bool(teammate),
                use_container_width=True,
            ):
                _update_workflow(
                    st,
                    listing,
                    {"assigned_to": teammate, "workflow_status": "Assigned"},
                    f"{address} assigned to {teammate}.",
                )
            if workflow[1].button(
                "Mark Contacted",
                key=f"radar_contacted_{listing_key}",
                disabled=not bool(teammate),
                use_container_width=True,
            ):
                _update_workflow(
                    st,
                    listing,
                    {"assigned_to": teammate, "workflow_status": "Contacted"},
                    f"{address} marked contacted.",
                )
            if workflow[2].button(
                "Dismiss",
                key=f"radar_dismiss_{listing_key}",
                disabled=not bool(teammate),
                use_container_width=True,
            ):
                _update_workflow(
                    st,
                    listing,
                    {"assigned_to": teammate, "workflow_status": "Dismissed"},
                    f"{address} dismissed from the active queue.",
                )

            note_key = f"listing_radar_note_{listing_key}"
            st.session_state.setdefault(note_key, str(listing.get("team_notes") or ""))
            workflow[3].text_input("Team note", key=note_key, placeholder="Agent response, next step, repair concern...")
            if st.button(
                "Save Team Note",
                key=f"radar_save_note_{listing_key}",
                disabled=not bool(teammate),
            ):
                _update_workflow(
                    st,
                    listing,
                    {
                        "assigned_to": str(listing.get("assigned_to") or teammate),
                        "workflow_status": str(listing.get("workflow_status") or "Assigned"),
                        "team_notes": st.session_state.get(note_key, ""),
                    },
                    f"Team note saved for {address}.",
                )


def render(st) -> None:
    st.header("📡 Listing Radar")
    st.caption(
        "New and changed on-market listings flow here first. No RentCast or full deal-analysis credits are used until a teammate opens a property in the Deal Engine."
    )
    identity.render_team_member_selector(st)

    message = st.session_state.pop(integration.HANDOFF_MESSAGE_KEY, "")
    error = st.session_state.pop(integration.HANDOFF_ERROR_KEY, "")
    if message:
        st.success(message)
    if error:
        st.error(error)

    if not client.is_connected():
        st.warning(
            "Listing Radar V2 is in foundation mode and is not connected to its mirror Google Sheet yet. "
            "The existing Illinois feed remains unchanged."
        )
        st.info(
            "Required later: LISTING_RADAR_WEBHOOK_URL and LISTING_RADAR_TOKEN in Streamlit secrets. "
            "Do not reuse the Deal Library or War Room Apify token."
        )
        return

    health = st.session_state.get("listing_radar_health")
    if not isinstance(health, dict):
        health = client.health()
        st.session_state["listing_radar_health"] = health
    if health.get("ok"):
        st.success(
            f"Listing Radar connected | {health.get('current_count', 0)} current listings | "
            f"Last successful run: {health.get('last_successful_run', 'Not available')}"
        )
    else:
        st.error(health.get("error", "Listing Radar connection check failed."))

    market_options = _market_options(st)
    market_ids = [item[0] for item in market_options]
    market_labels = {item[0]: item[1] for item in market_options}
    filters = st.columns([2.2, 1.7, 1.4, 1.4, 1])
    filters[0].text_input("Search address, city, ZIP, agent or brokerage", key="listing_radar_query")
    filters[1].selectbox(
        "Market",
        market_ids,
        format_func=lambda value: market_labels.get(value, value),
        key="listing_radar_market",
    )
    filters[2].selectbox(
        "Listing change",
        ["", "NEW", "PRICE_DROP", "PRICE_INCREASE", "UPDATED", "UNCHANGED"],
        format_func=lambda value: value.replace("_", " ").title() if value else "All changes",
        key="listing_radar_feed_status",
    )
    filters[3].selectbox(
        "Team status",
        ["", "New", "Assigned", "Contacted", "Follow Up", "Analyze", "Pursue", "Dismissed"],
        format_func=lambda value: value or "All team statuses",
        key="listing_radar_workflow_status",
    )
    refresh = filters[4].button("Refresh", type="primary", use_container_width=True)

    result = st.session_state.get("listing_radar_last_result")
    if refresh or not isinstance(result, dict):
        with st.spinner("Loading current listings..."):
            result = _load(st)

    if not result.get("ok"):
        st.error(result.get("error", "Listings could not be loaded."))
        return

    listings = result.get("listings", []) or []
    st.caption(f"Showing {len(listings)} listing(s).")
    if not listings:
        st.info("No listings match the current filters.")
        return
    for index, listing in enumerate(listings):
        _render_listing_card(st, dict(listing or {}), index)
