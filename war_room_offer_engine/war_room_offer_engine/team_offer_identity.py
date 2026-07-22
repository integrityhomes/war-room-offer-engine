from __future__ import annotations

import json
import os
import re
from typing import Any


ACTIVE_MEMBER_KEY = "team_operator_name"
MEMBER_SELECTION_KEY = "team_operator_selection"
CUSTOM_MEMBER_KEY = "team_operator_custom_name"
DEAL_OFFER_MAKER_KEY = "deal_offer_made_by"

UNSELECTED_LABEL = "— Select your name —"
CUSTOM_LABEL = "Other / enter a name"

_SECRET_NAMES = (
    "TEAM_MEMBER_NAMES",
    "OFFER_TEAM_MEMBERS",
    "ACQUISITIONS_TEAM_MEMBERS",
)


def clean_name(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if text in {UNSELECTED_LABEL, CUSTOM_LABEL}:
        return ""
    return text[:80]


def parse_team_members(raw: Any) -> list[str]:
    """Parse a team roster from a TOML list, JSON list, or delimited string."""
    if isinstance(raw, dict):
        raw = raw.get("names") or raw.get("members") or []
    if isinstance(raw, (list, tuple, set)):
        values = list(raw)
    else:
        text = str(raw or "").strip()
        if not text:
            values = []
        else:
            parsed: Any = None
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                values = parsed
            else:
                values = re.split(r"[,;\n\r|]+", text.strip("[]"))

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        name = clean_name(str(value or "").strip(" \"'"))
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        result.append(name)
    return result


def _secret_value() -> Any:
    try:
        import streamlit as st

        for name in _SECRET_NAMES:
            if name in st.secrets:
                return st.secrets.get(name)
    except Exception:
        pass
    for name in _SECRET_NAMES:
        value = os.environ.get(name)
        if value:
            return value
    return ""


def configured_team_members() -> list[str]:
    return parse_team_members(_secret_value())


def initialize_state(state: Any) -> None:
    state.setdefault(ACTIVE_MEMBER_KEY, "")
    state.setdefault(MEMBER_SELECTION_KEY, UNSELECTED_LABEL)
    state.setdefault(CUSTOM_MEMBER_KEY, "")
    state.setdefault(DEAL_OFFER_MAKER_KEY, "")


def active_team_member(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    return clean_name(state.get(ACTIVE_MEMBER_KEY, ""))


def offer_maker_for_deal(state: Any) -> str:
    if not hasattr(state, "get"):
        return ""
    return clean_name(state.get(DEAL_OFFER_MAKER_KEY, ""))


def _safe_widget_state_write(state: Any, key: str, value: Any) -> bool:
    """Write a widget-backed value only when Streamlit still permits it.

    Streamlit forbids changing ``session_state[key]`` after a widget using the
    same key has been instantiated during the current rerun. The Deal Library
    save button is rendered after the Assigned To and Updated By widgets, so a
    save-time audit stamp must never crash the whole application. The snapshot
    builder independently records the active teammate as ``updated_by``.
    """
    try:
        state[key] = value
        return True
    except Exception as exc:
        message = str(exc).lower()
        widget_locked = (
            "cannot be modified after the widget" in message
            or "cannot be modified after the widget with key" in message
            or "streamlitapiexception" in type(exc).__name__.lower()
        )
        if widget_locked:
            return False
        raise


def apply_active_member_to_deal(
    state: Any,
    *,
    overwrite_offer_maker: bool = False,
) -> bool:
    """Stamp the current teammate onto the deal and save audit.

    The active operator is session-specific and is intentionally not restored from
    another teammate's saved deal. ``updated_by`` always reflects the current
    teammate in saved snapshots. ``deal_offer_made_by`` is filled when blank and
    is overwritten only when a teammate explicitly starts a new analysis/offer.
    """
    if not hasattr(state, "get"):
        return False
    initialize_state(state)
    name = active_team_member(state)
    if not name:
        return False

    current_offer_maker = offer_maker_for_deal(state)
    if overwrite_offer_maker or not current_offer_maker:
        state[DEAL_OFFER_MAKER_KEY] = name
        state["decision_offer_made_by"] = name
        current_offer_maker = name
    else:
        state["decision_offer_made_by"] = current_offer_maker

    _safe_widget_state_write(state, "deal_library_updated_by", name)
    if not clean_name(state.get("deal_library_assigned_to", "")):
        _safe_widget_state_write(state, "deal_library_assigned_to", name)

    normalized = state.get("one_load_normalized")
    if isinstance(normalized, dict):
        data = normalized.get("data")
        if isinstance(data, dict):
            data["offer_made_by"] = current_offer_maker
            data["updated_by"] = name
    return True


def outreach_sender_name(explicit_name: Any = "") -> str:
    explicit = clean_name(explicit_name)
    if explicit:
        return explicit
    try:
        import streamlit as st

        state = st.session_state
        return active_team_member(state) or offer_maker_for_deal(state)
    except Exception:
        return ""


def render_team_member_selector(st: Any) -> str:
    """Render one identity selector that follows a teammate across properties."""
    state = st.session_state
    initialize_state(state)
    roster = configured_team_members()
    active = active_team_member(state)

    options = [UNSELECTED_LABEL, *roster, CUSTOM_LABEL]
    if active:
        roster_match = next((name for name in roster if name.casefold() == active.casefold()), "")
        desired = roster_match or CUSTOM_LABEL
        if desired == CUSTOM_LABEL and not clean_name(state.get(CUSTOM_MEMBER_KEY, "")):
            state[CUSTOM_MEMBER_KEY] = active
    else:
        desired = UNSELECTED_LABEL

    current_selection = state.get(MEMBER_SELECTION_KEY)
    if current_selection not in options:
        state[MEMBER_SELECTION_KEY] = desired
    elif active and current_selection == UNSELECTED_LABEL:
        state[MEMBER_SELECTION_KEY] = desired

    with st.container(border=True):
        st.markdown("#### Team Member & Offer Identity")
        left, right = st.columns([1.2, 1.8])
        with left:
            selected = st.selectbox(
                "Who is working this offer?",
                options,
                key=MEMBER_SELECTION_KEY,
                help=(
                    "This name is used in realtor texts and emails, Deal Library history, "
                    "and offer audit fields. It stays selected for this browser session."
                ),
            )
        with right:
            if selected == CUSTOM_LABEL:
                st.text_input(
                    "Enter team member name",
                    key=CUSTOM_MEMBER_KEY,
                    placeholder="Type your name",
                )
            elif roster:
                st.caption(
                    "The shared roster comes from the TEAM_MEMBER_NAMES Streamlit secret. "
                    "Choose Other when a teammate is not listed."
                )
            else:
                st.caption(
                    "Choose Other and type your name. For a shared nine-person dropdown, add "
                    "TEAM_MEMBER_NAMES to Streamlit secrets."
                )

        name = (
            clean_name(state.get(CUSTOM_MEMBER_KEY, ""))
            if selected == CUSTOM_LABEL
            else clean_name(selected)
        )
        state[ACTIVE_MEMBER_KEY] = name
        if name:
            apply_active_member_to_deal(state, overwrite_offer_maker=False)
            prior = offer_maker_for_deal(state)
            if prior and prior.casefold() != name.casefold():
                st.success(f"Current teammate: {name}. Existing offer on this saved deal: {prior}.")
            else:
                st.success(f"Offers, messages, and team saves will use: {name}")
        else:
            st.warning(
                "Select your name before calculating or sending an offer. The app will not default to another teammate."
            )
    return name
