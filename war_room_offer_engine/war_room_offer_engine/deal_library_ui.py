from __future__ import annotations

import json
from typing import Any

try:
    from deal_library import (
        DEAL_STATUSES,
        build_snapshot,
        get_deal,
        health,
        is_connected,
        restore_snapshot,
        save_deal,
        search_deals,
    )
    from data_sources import get_secret
except ImportError:
    try:
        from .deal_library import (
            DEAL_STATUSES,
            build_snapshot,
            get_deal,
            health,
            is_connected,
            restore_snapshot,
            save_deal,
            search_deals,
        )
        from .data_sources import get_secret
    except ImportError:
        from war_room_offer_engine.deal_library import (
            DEAL_STATUSES,
            build_snapshot,
            get_deal,
            health,
            is_connected,
            restore_snapshot,
            save_deal,
            search_deals,
        )
        from war_room_offer_engine.data_sources import get_secret


def initialize_deal_library_state(st) -> None:
    defaults = {
        "deal_library_status": "Analyzing",
        "deal_library_assigned_to": "",
        "deal_library_team_notes": "",
        "deal_library_updated_by": "",
        "deal_library_search": "",
        "deal_library_search_results": [],
        "deal_library_auto_save": True,
        "deal_library_last_error": "",
        "deal_library_last_message": "",
        "deal_library_deal_id": "",
        "deal_library_version": 0,
        "deal_library_last_saved_at": "",
        "deal_library_loaded_without_api": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def apply_pending_restore(st) -> bool:
    pending = st.session_state.pop("deal_library_pending_snapshot", None)
    if not isinstance(pending, dict):
        return False
    restore_snapshot(st.session_state, pending)
    property_input = (
        st.session_state.get("listing_url")
        or st.session_state.get("address")
        or pending.get("address", "")
    )
    st.session_state["decision_property_input"] = property_input
    st.session_state["deal_library_last_message"] = (
        "Saved deal restored. No Zillow, RentCast, or Apify credits were used."
    )
    st.session_state["deal_library_last_error"] = ""
    return True


def load_query_deal_if_requested(st) -> bool:
    try:
        deal_id = str(st.query_params.get("deal_id", "") or "").strip()
    except Exception:
        deal_id = ""
    if not deal_id or st.session_state.get("deal_library_query_loaded_id") == deal_id:
        return False
    st.session_state["deal_library_query_loaded_id"] = deal_id
    result = get_deal(deal_id)
    if result.get("ok") and isinstance(result.get("snapshot"), dict):
        st.session_state["deal_library_pending_snapshot"] = result["snapshot"]
        st.rerun()
        return True
    st.session_state["deal_library_last_error"] = result.get("error", "Saved deal could not be loaded.")
    return False


def _save_current(st, *, automatic: bool = False) -> dict[str, Any]:
    snapshot = build_snapshot(dict(st.session_state))
    result = save_deal(snapshot)
    if result.get("ok"):
        st.session_state["deal_library_deal_id"] = snapshot["deal_id"]
        st.session_state["deal_library_version"] = int(result.get("version", snapshot.get("base_version", 0)) or 0)
        st.session_state["deal_library_last_saved_at"] = result.get("saved_at", snapshot.get("saved_at", ""))
        verb = "Auto-saved" if automatic else "Saved"
        st.session_state["deal_library_last_message"] = (
            f"{verb} to the team Deal Library as version {st.session_state['deal_library_version']}."
        )
        st.session_state["deal_library_last_error"] = ""
    else:
        if result.get("conflict"):
            st.session_state["deal_library_last_error"] = (
                "A teammate saved a newer version. Open the latest saved deal before updating it. "
                f"Latest version: {result.get('current_version', 'unknown')} by "
                f"{result.get('current_updated_by') or 'another team member'}."
            )
        else:
            st.session_state["deal_library_last_error"] = result.get("error", "Deal could not be saved.")
    return result


def auto_save_completed_analysis(st) -> dict[str, Any]:
    initialize_deal_library_state(st)
    if not is_connected() or not st.session_state.get("deal_library_auto_save", True):
        return {"ok": False, "skipped": True}
    decision = st.session_state.get("decision_result", {}) or {}
    if not decision or not (st.session_state.get("address") or st.session_state.get("decision_property_input")):
        return {"ok": False, "skipped": True}
    return _save_current(st, automatic=True)


def _queue_open(st, deal_id: str) -> None:
    result = get_deal(deal_id)
    if result.get("ok") and isinstance(result.get("snapshot"), dict):
        st.session_state["deal_library_pending_snapshot"] = result["snapshot"]
        st.rerun()
    else:
        st.session_state["deal_library_last_error"] = result.get("error", "Saved deal could not be opened.")


def _share_link(deal_id: str) -> str:
    base_url = get_secret("DEAL_LIBRARY_APP_URL", "").rstrip("/")
    return f"{base_url}/?deal_id={deal_id}" if base_url and deal_id else ""


def render_deal_library_box(st) -> None:
    initialize_deal_library_state(st)
    connected = is_connected()

    st.markdown("## 💾 Team Deal Library")
    st.caption(
        "Save the complete deal once, reopen it later without repulling paid data, and keep a shared version history for the team."
    )

    with st.container(border=True):
        if connected:
            st.success("Google Sheet Deal Library connected")
        else:
            st.warning(
                "Deal Library setup is not connected yet. The app is ready, but Streamlit still needs the Google Apps Script web-app URL."
            )

        metadata = st.columns([1.2, 1.2, 1.2, 2.2])
        with metadata[0]:
            current_status = st.session_state.get("deal_library_status", "Analyzing")
            if current_status not in DEAL_STATUSES:
                st.session_state["deal_library_status"] = "Analyzing"
            st.selectbox("Team Deal Status", DEAL_STATUSES, key="deal_library_status")
        with metadata[1]:
            st.text_input("Assigned To", key="deal_library_assigned_to", placeholder="Carlos, Amiel, Chase...")
        with metadata[2]:
            st.text_input("Updated By", key="deal_library_updated_by", placeholder="Your name")
        with metadata[3]:
            st.text_area(
                "Team Notes",
                key="deal_library_team_notes",
                height=78,
                placeholder="Seller counter, next step, title issue, buyer feedback...",
            )

        controls = st.columns([1.5, 1.2, 1.2])
        save_clicked = controls[0].button(
            "Save / Update Deal for Team",
            type="primary",
            use_container_width=True,
            disabled=not connected,
        )
        controls[1].checkbox(
            "Auto-save completed analysis",
            key="deal_library_auto_save",
            help="Each completed Pull Everything & Tell Me run updates this property and writes a history version.",
        )
        test_clicked = controls[2].button(
            "Test Sheet Connection",
            use_container_width=True,
            disabled=not connected,
        )

        if save_clicked:
            with st.spinner("Saving the complete deal for the team..."):
                _save_current(st)
        if test_clicked:
            result = health()
            if result.get("ok"):
                st.session_state["deal_library_last_message"] = (
                    f"Google Sheet connection is working. {result.get('deals_count', 0)} current deal(s) and "
                    f"{result.get('history_count', 0)} history version(s)."
                )
                st.session_state["deal_library_last_error"] = ""
            else:
                st.session_state["deal_library_last_error"] = result.get("error", "Connection test failed.")

        if st.session_state.get("deal_library_last_message"):
            st.success(st.session_state["deal_library_last_message"])
        if st.session_state.get("deal_library_last_error"):
            st.error(st.session_state["deal_library_last_error"])

        deal_id = str(st.session_state.get("deal_library_deal_id", "") or "")
        version = int(st.session_state.get("deal_library_version", 0) or 0)
        if deal_id:
            st.caption(f"Saved Deal ID: {deal_id} | Version: {version or 'Not saved yet'}")
            share_link = _share_link(deal_id)
            if share_link:
                st.code(share_link)
                st.caption("Send this link to a team member. It opens the saved analysis without new data pulls.")

        snapshot = build_snapshot(dict(st.session_state))
        st.download_button(
            "Download JSON Backup",
            data=json.dumps(snapshot, indent=2),
            file_name=f"deal-{snapshot['deal_id']}.json",
            mime="application/json",
            use_container_width=False,
        )

    with st.expander("Find and open a saved team deal — no API credits", expanded=False):
        search_cols = st.columns([3, 1])
        search_cols[0].text_input(
            "Search saved deals",
            key="deal_library_search",
            placeholder="Address, city, status, or assigned team member",
        )
        find_clicked = search_cols[1].button(
            "Find Saved Deals",
            use_container_width=True,
            disabled=not connected,
        )
        if find_clicked:
            with st.spinner("Searching the team Deal Library..."):
                result = search_deals(st.session_state.get("deal_library_search", ""), limit=30)
            if result.get("ok"):
                st.session_state["deal_library_search_results"] = result.get("deals", []) or []
                st.session_state["deal_library_last_error"] = ""
            else:
                st.session_state["deal_library_last_error"] = result.get("error", "Saved deals could not be searched.")

        results = st.session_state.get("deal_library_search_results", []) or []
        if not results and find_clicked:
            st.info("No saved deals matched that search.")
        for idx, deal in enumerate(results):
            with st.container(border=True):
                columns = st.columns([2.8, 1.1, 1.1, 1.1, 1])
                columns[0].write(f"**{deal.get('address') or 'Unknown property'}**")
                columns[0].caption(
                    " | ".join(
                        part for part in [
                            str(deal.get("deal_status", "")),
                            str(deal.get("assigned_to", "")),
                            f"v{deal.get('version')}" if deal.get("version") else "",
                            str(deal.get("updated_at", "")),
                        ] if part
                    )
                )
                columns[1].metric("Decision", deal.get("decision", ""))
                columns[2].metric("Price", f"${float(deal.get('current_negotiated_price', 0) or 0):,.0f}")
                columns[3].metric("Maximum", f"${float(deal.get('absolute_maximum', 0) or 0):,.0f}")
                if columns[4].button("Open Saved Deal", key=f"open_saved_deal_{deal.get('deal_id', idx)}"):
                    _queue_open(st, str(deal.get("deal_id", "")))

        st.info(
            "Opening a saved deal restores its prior facts, comps, notes, repair analysis, negotiation and decision. "
            "Use Pull Everything & Tell Me only when you intentionally want fresh paid data."
        )
