from __future__ import annotations

from typing import Any

try:
    from deal_library import (
        PRIORITIES,
        TEAM_STATUSES,
        backup_json,
        build_record,
        configured,
        get_deal,
        list_deals,
        parse_backup,
        restore_snapshot,
        save_deal,
    )
except ImportError:
    try:
        from .deal_library import (
            PRIORITIES,
            TEAM_STATUSES,
            backup_json,
            build_record,
            configured,
            get_deal,
            list_deals,
            parse_backup,
            restore_snapshot,
            save_deal,
        )
    except ImportError:
        from war_room_offer_engine.deal_library import (
            PRIORITIES,
            TEAM_STATUSES,
            backup_json,
            build_record,
            configured,
            get_deal,
            list_deals,
            parse_backup,
            restore_snapshot,
            save_deal,
        )


def initialize(st) -> None:
    defaults = {
        "deal_library_saved_deals": [],
        "deal_library_search": "",
        "deal_library_selected_id": "",
        "deal_library_loaded_id": "",
        "deal_library_loaded_from_saved": False,
        "deal_library_loaded_label": "",
        "deal_library_last_error": "",
        "deal_library_last_saved_at": "",
        "deal_library_assigned_to": "",
        "deal_library_team_status": "New",
        "deal_library_priority": "Warm",
        "deal_library_saved_by": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _deal_label(deal: dict[str, Any]) -> str:
    address = str(deal.get("property_address") or "Unknown property")
    decision = str(deal.get("decision") or "Not decided")
    status = str(deal.get("team_status") or "New")
    price = deal.get("current_price") or 0
    try:
        price_text = f"${float(price):,.0f}" if float(price or 0) > 0 else "No price"
    except Exception:
        price_text = "No price"
    return f"{address} — {decision} — {price_text} — {status}"


def refresh_saved_deals(st, search: str = "") -> None:
    result = list_deals(search=search)
    if result.get("ok"):
        st.session_state["deal_library_saved_deals"] = result.get("deals", []) or []
        st.session_state["deal_library_last_error"] = ""
    else:
        st.session_state["deal_library_last_error"] = result.get("error", "Could not load saved deals.")


def _load_record(st, record: dict[str, Any]) -> None:
    snapshot = record.get("snapshot", {}) if isinstance(record, dict) else {}
    restored = restore_snapshot(st, snapshot)
    st.session_state["deal_library_loaded_id"] = str(record.get("deal_id") or "")
    st.session_state["deal_library_loaded_from_saved"] = True
    st.session_state["deal_library_loaded_label"] = str(record.get("property_address") or "Saved deal")
    st.session_state["deal_library_assigned_to"] = str(record.get("assigned_to") or st.session_state.get("deal_library_assigned_to", ""))
    team_status = str(record.get("team_status") or "New")
    st.session_state["deal_library_team_status"] = team_status if team_status in TEAM_STATUSES else "New"
    priority = str(record.get("priority") or "Warm")
    st.session_state["deal_library_priority"] = priority if priority in PRIORITIES else "Warm"
    st.session_state["deal_library_last_error"] = "" if restored else "The saved record contained no restorable fields."


def render_library_panel(st) -> None:
    initialize(st)
    is_configured = configured()
    with st.expander("📚 Deal Library — Save / Open Team Deals", expanded=bool(st.session_state.get("deal_library_loaded_from_saved"))):
        st.caption(
            "Open a saved analysis without rerunning RentCast, Zillow, Apify, sold comps, or media analysis. "
            "Use Refresh Live Data only when new information is needed."
        )

        workflow = st.columns([1.3, 1.2, 1, 1.2])
        workflow[0].text_input("Assigned To", key="deal_library_assigned_to", placeholder="Team member")
        workflow[1].selectbox("Team Status", TEAM_STATUSES, key="deal_library_team_status")
        workflow[2].selectbox("Priority", PRIORITIES, key="deal_library_priority")
        workflow[3].text_input("Saved By", key="deal_library_saved_by", placeholder="Your name")

        if st.session_state.get("deal_library_loaded_from_saved"):
            st.success(
                f"Saved deal loaded: {st.session_state.get('deal_library_loaded_label', 'Property')}. "
                "No paid data sources were used to reopen it."
            )
            media_names = st.session_state.get("deal_library_media_filenames", []) or []
            if media_names:
                st.caption("Prior media on record: " + ", ".join(str(name) for name in media_names))

        if not is_configured:
            st.warning(
                "Shared Google Sheet storage is not configured yet. JSON backup and restore are available below. "
                "After the Google Sheet web app is connected, Save / Update will become shared for the whole team."
            )
        else:
            search_cols = st.columns([3, 1])
            search_cols[0].text_input("Search saved deals", key="deal_library_search", placeholder="Address, city, status, decision, or assigned team member")
            refresh_clicked = search_cols[1].button("Refresh Library", use_container_width=True)
            if refresh_clicked or not st.session_state.get("deal_library_saved_deals"):
                refresh_saved_deals(st, st.session_state.get("deal_library_search", ""))

            deals = st.session_state.get("deal_library_saved_deals", []) or []
            search_text = str(st.session_state.get("deal_library_search", "") or "").lower().strip()
            if search_text:
                deals = [deal for deal in deals if search_text in " ".join(str(value).lower() for value in deal.values())]

            if deals:
                label_map = {_deal_label(deal): str(deal.get("deal_id") or "") for deal in deals}
                selected_label = st.selectbox("Saved Property", list(label_map.keys()), key="deal_library_selected_label")
                selected_id = label_map.get(selected_label, "")
                st.session_state["deal_library_selected_id"] = selected_id
                open_clicked = st.button("Open Saved Deal — No Credit Use", type="primary", use_container_width=True)
                if open_clicked and selected_id:
                    result = get_deal(selected_id)
                    if result.get("ok") and isinstance(result.get("deal"), dict):
                        _load_record(st, result["deal"])
                        st.rerun()
                    else:
                        st.error(result.get("error", "Could not open the saved deal."))
            else:
                st.info("No saved deals matched the current search.")

            error = st.session_state.get("deal_library_last_error", "")
            if error:
                st.error(error)

        st.markdown("**Portable backup**")
        backup_file = st.file_uploader("Restore a Deal Library JSON backup", type=["json"], key="deal_library_backup_upload")
        if backup_file is not None and st.button("Open JSON Backup — No Credit Use", use_container_width=True):
            result = parse_backup(backup_file.getvalue())
            if result.get("ok"):
                _load_record(st, result["record"])
                st.rerun()
            else:
                st.error(result.get("error", "Could not restore backup."))


def render_save_controls(st) -> None:
    initialize(st)
    record = build_record(st.session_state)
    address = str(record.get("property_address") or "").strip()
    decision = str(record.get("decision") or "").strip()

    st.markdown("### Save This Deal for the Team")
    st.caption(
        "Save the complete analysis, comps, negotiation position, decision, offer limits, notes, and team status. "
        "Opening it later will not consume paid data credits."
    )

    cols = st.columns([2, 1])
    save_clicked = cols[0].button(
        "Save / Update Team Deal",
        type="primary",
        use_container_width=True,
        disabled=not bool(address),
    )
    backup_name = f"war-room-deal-{record.get('deal_id') or 'backup'}.json"
    cols[1].download_button(
        "Download JSON Backup",
        data=backup_json(st.session_state),
        file_name=backup_name,
        mime="application/json",
        use_container_width=True,
    )

    if not address:
        st.info("Enter or load a property before saving.")
    elif not decision:
        st.info("The property can be saved now, but running the decision first will preserve a complete recommendation.")

    if save_clicked:
        if not configured():
            st.warning("Google Sheet storage is not connected yet. Use Download JSON Backup until setup is completed.")
        else:
            result = save_deal(record)
            if result.get("ok"):
                st.session_state["deal_library_loaded_id"] = str(record.get("deal_id") or "")
                st.session_state["deal_library_loaded_from_saved"] = True
                st.session_state["deal_library_loaded_label"] = address
                st.session_state["deal_library_last_saved_at"] = str(result.get("updated_at") or "")
                refresh_saved_deals(st)
                version = result.get("version")
                st.success(f"Deal saved for the team{f' — version {version}' if version else ''}.")
            else:
                st.error(result.get("error", "Could not save the deal."))
