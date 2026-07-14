from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from deal_vault_google_sheets import DealVaultSheets, config_from_secrets
    from deal_vault_snapshot import build_snapshot, restore_snapshot, summary_from_state
except ImportError:
    try:
        from .deal_vault_google_sheets import DealVaultSheets, config_from_secrets
        from .deal_vault_snapshot import build_snapshot, restore_snapshot, summary_from_state
    except ImportError:
        from war_room_offer_engine.deal_vault_google_sheets import DealVaultSheets, config_from_secrets
        from war_room_offer_engine.deal_vault_snapshot import build_snapshot, restore_snapshot, summary_from_state


STAGES = [
    "New", "Analyzing", "Offer Ready", "Offer Sent", "Negotiating",
    "Verbal Agreement", "Contract Sent", "Under Contract", "Closed",
    "Dead / Passed",
]
PRIORITIES = ["Urgent", "High", "Normal", "Low"]


def _secret(st, key: str, default: Any = "") -> Any:
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def _team_members(st) -> list[str]:
    raw = _secret(st, "DEAL_VAULT_TEAM_MEMBERS", [])
    if isinstance(raw, (list, tuple)):
        values = [str(item).strip() for item in raw]
    else:
        values = [item.strip() for item in str(raw or "").split(",")]
    return [item for item in values if item]


def initialize(st) -> None:
    defaults = {
        "deal_vault_auto_save": True,
        "deal_vault_use_saved_first": True,
        "deal_vault_force_live_refresh": False,
        "deal_vault_stage": "New",
        "deal_vault_priority": "Normal",
        "deal_vault_assigned_to": "Unassigned",
        "deal_vault_saved_by": str(_secret(st, "DEAL_VAULT_DEFAULT_USER", "") or ""),
        "deal_vault_drive_folder_url": "",
        "deal_vault_search": "",
        "deal_vault_selected_id": "",
        "deal_vault_records": [],
        "deal_vault_records_loaded": False,
        "deal_vault_last_status": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def apply_pending_snapshot(st) -> bool:
    pending = st.session_state.pop("deal_vault_pending_snapshot", None)
    if not isinstance(pending, dict):
        return False
    record = st.session_state.pop("deal_vault_pending_record", {}) or {}
    restored = restore_snapshot(st.session_state, pending)
    if isinstance(record, dict):
        st.session_state["deal_vault_loaded_record"] = record
        st.session_state["deal_vault_selected_id"] = record.get("deal_id", "")
        st.session_state["deal_vault_stage"] = record.get("stage") or "New"
        st.session_state["deal_vault_priority"] = record.get("priority") or "Normal"
        st.session_state["deal_vault_assigned_to"] = record.get("assigned_to") or "Unassigned"
        st.session_state["deal_vault_saved_by"] = record.get("last_saved_by") or st.session_state.get("deal_vault_saved_by", "")
        st.session_state["deal_vault_drive_folder_url"] = record.get("drive_folder_url") or ""
    st.session_state["deal_vault_last_status"] = (
        f"Loaded saved deal with {restored} restored fields. No RentCast, Apify, or OpenAI credits were used."
    )
    return True


def _config(st) -> dict[str, Any]:
    try:
        return config_from_secrets(st.secrets)
    except Exception:
        return {"configured": False, "sheet_id": "", "client_email": "", "service_account": {}}


def _client(st) -> DealVaultSheets:
    return DealVaultSheets.from_secrets(st.secrets)


def refresh_records(st, *, quiet: bool = False) -> list[dict[str, Any]]:
    try:
        records = _client(st).list_deals()
        st.session_state["deal_vault_records"] = records
        st.session_state["deal_vault_records_loaded"] = True
        if not quiet:
            st.session_state["deal_vault_last_status"] = f"Deal Vault refreshed: {len(records)} saved deal(s)."
        return records
    except Exception as exc:
        st.session_state["deal_vault_last_status"] = f"Deal Vault could not be refreshed: {exc}"
        return st.session_state.get("deal_vault_records", []) or []


def _record_label(record: dict[str, Any]) -> str:
    address = str(record.get("address") or record.get("listing_url") or record.get("deal_id") or "Saved deal")
    decision = str(record.get("decision") or "No decision")
    stage = str(record.get("stage") or "New")
    price = record.get("negotiated_price") or record.get("asking_price") or 0
    try:
        price_text = f"${float(price):,.0f}"
    except Exception:
        price_text = str(price or "")
    return f"{address} — {decision} — {stage} — {price_text}"


def _filtered_records(st) -> list[dict[str, Any]]:
    records = st.session_state.get("deal_vault_records", []) or []
    query = str(st.session_state.get("deal_vault_search", "") or "").strip().lower()
    if not query:
        return records
    return [
        record for record in records
        if query in " ".join(
            str(record.get(key, ""))
            for key in ["address", "city", "state", "zip", "decision", "deal_lane", "stage", "assigned_to"]
        ).lower()
    ]


def _age_label(saved_at: str) -> str:
    try:
        saved = datetime.fromisoformat(str(saved_at).replace("Z", "+00:00"))
        if saved.tzinfo is None:
            saved = saved.replace(tzinfo=timezone.utc)
        age_days = max((datetime.now(timezone.utc) - saved).days, 0)
    except Exception:
        return "Age unknown"
    if age_days <= 7:
        return f"Fresh — {age_days} day(s) old"
    if age_days <= 30:
        return f"Review soon — {age_days} days old"
    return f"Stale — {age_days} days old; refresh live data before relying on listing status"


def queue_record_load(st, record: dict[str, Any]) -> bool:
    try:
        snapshot = _client(st).load_snapshot(record)
    except Exception as exc:
        st.session_state["deal_vault_last_status"] = f"Saved deal could not be opened: {exc}"
        return False
    st.session_state["deal_vault_pending_snapshot"] = snapshot
    st.session_state["deal_vault_pending_record"] = record
    st.session_state["war_room_active_section"] = "🏠 One-Load"
    return True


def find_saved_before_pull(st, property_input: str) -> dict[str, Any] | None:
    config = _config(st)
    if not config.get("configured") or not st.session_state.get("deal_vault_use_saved_first", True):
        return None
    if st.session_state.get("deal_vault_force_live_refresh", False):
        return None
    records = st.session_state.get("deal_vault_records", []) or []
    if not st.session_state.get("deal_vault_records_loaded"):
        records = refresh_records(st, quiet=True)
    try:
        return _client(st).find(property_input, records=records)
    except Exception as exc:
        st.session_state["deal_vault_last_status"] = f"Deal Vault lookup skipped: {exc}"
        return None


def save_current(st, media_files: list[Any] | None = None, *, automatic: bool = False) -> dict[str, Any] | None:
    config = _config(st)
    if not config.get("configured"):
        st.session_state["deal_vault_last_status"] = "Deal Vault is not connected to Google Sheets yet."
        return None
    summary = summary_from_state(st.session_state)
    if not summary.get("deal_id"):
        st.session_state["deal_vault_last_status"] = "Enter or load a property before saving it."
        return None
    snapshot = build_snapshot(st.session_state, media_files=media_files)
    try:
        result = _client(st).save_deal(
            summary,
            snapshot,
            assigned_to=str(st.session_state.get("deal_vault_assigned_to", "Unassigned")),
            stage=str(st.session_state.get("deal_vault_stage", "New")),
            priority=str(st.session_state.get("deal_vault_priority", "Normal")),
            drive_folder_url=str(st.session_state.get("deal_vault_drive_folder_url", "")),
            saved_by=str(st.session_state.get("deal_vault_saved_by", "")),
        )
        st.session_state["deal_vault_last_saved_deal_id"] = result.get("deal_id", "")
        st.session_state["deal_vault_last_status"] = (
            f"{result.get('action', 'Saved')} in Team Deal Vault at {result.get('saved_at', '')}."
            + (" Snapshot was safely trimmed to fit Google Sheets." if result.get("snapshot_trimmed") else "")
        )
        refresh_records(st, quiet=True)
        return result
    except Exception as exc:
        label = "Automatic save" if automatic else "Save"
        st.session_state["deal_vault_last_status"] = f"{label} failed: {exc}"
        return None


def render_box(st, media_files: list[Any] | None = None) -> None:
    initialize(st)
    config = _config(st)
    with st.expander("💾 Team Deal Vault — save, reopen, and avoid duplicate API pulls", expanded=False):
        if not config.get("configured"):
            st.warning("Deal Vault is built but still needs a Google Sheet connection.")
            st.write(
                "Create one Google Sheet, share it with the service-account email, then add "
                "`DEAL_VAULT_SHEET_ID` and `[gcp_service_account]` to Streamlit secrets."
            )
            if config.get("client_email"):
                st.code(config["client_email"])
            st.caption("The app will automatically create the Deal Vault and Deal History tabs after connection.")
            return

        loaded = st.session_state.get("deal_vault_loaded_record", {}) or {}
        if loaded:
            st.success(
                f"Loaded from Team Deal Vault — {_age_label(str(loaded.get('last_saved_utc', '')))}. "
                "No property-data credits were used to reopen it."
            )

        top = st.columns(3)
        top[0].checkbox("Use saved deal first", key="deal_vault_use_saved_first", help="Loads a saved snapshot before calling paid data sources.")
        top[1].checkbox("Auto-save completed analysis", key="deal_vault_auto_save")
        top[2].checkbox("Refresh live data", key="deal_vault_force_live_refresh", help="Ignore a saved snapshot and run fresh property-data calls.")

        team = _team_members(st)
        meta = st.columns(4)
        if team:
            options = ["Unassigned"] + [name for name in team if name != "Unassigned"]
            current = str(st.session_state.get("deal_vault_assigned_to", "Unassigned"))
            if current not in options:
                options.append(current)
            meta[0].selectbox("Assigned To", options, key="deal_vault_assigned_to")
        else:
            meta[0].text_input("Assigned To", key="deal_vault_assigned_to")
        meta[1].selectbox("Deal Stage", STAGES, key="deal_vault_stage")
        meta[2].selectbox("Priority", PRIORITIES, key="deal_vault_priority")
        meta[3].text_input("Saved By", key="deal_vault_saved_by")
        st.text_input("Google Drive property folder link (optional)", key="deal_vault_drive_folder_url")

        search_cols = st.columns([2, 1])
        search_cols[0].text_input("Search saved deals", key="deal_vault_search", placeholder="Address, city, status, team member...")
        if search_cols[1].button("Refresh Deal List", use_container_width=True):
            refresh_records(st)

        if not st.session_state.get("deal_vault_records_loaded"):
            refresh_records(st, quiet=True)
        matches = _filtered_records(st)
        if matches:
            option_ids = [str(record.get("deal_id")) for record in matches]
            labels = {str(record.get("deal_id")): _record_label(record) for record in matches}
            current = str(st.session_state.get("deal_vault_selected_id", ""))
            index = option_ids.index(current) if current in option_ids else 0
            selected = st.selectbox(
                "Saved Deals",
                option_ids,
                index=index,
                format_func=lambda item: labels.get(item, item),
                key="deal_vault_selected_id",
            )
            selected_record = next(record for record in matches if str(record.get("deal_id")) == selected)
            info = st.columns(3)
            info[0].metric("Saved Decision", selected_record.get("decision") or "Not set")
            info[1].metric("Assigned To", selected_record.get("assigned_to") or "Unassigned")
            info[2].metric("Data Age", _age_label(str(selected_record.get("last_saved_utc", ""))))
            if st.button("Open Saved Deal — No API Pull", type="primary", use_container_width=True):
                if queue_record_load(st, selected_record):
                    st.rerun()
        else:
            st.info("No saved deals match this search yet.")

        save_cols = st.columns([2, 1])
        if save_cols[0].button("Save / Update Current Deal", type="primary", use_container_width=True):
            save_current(st, media_files=media_files)
        if save_cols[1].button("Clear Vault Status", use_container_width=True):
            st.session_state["deal_vault_last_status"] = ""

        status = str(st.session_state.get("deal_vault_last_status", "") or "")
        if status:
            st.info(status)
