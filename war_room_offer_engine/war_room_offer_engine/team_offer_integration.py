from __future__ import annotations

import sys
from typing import Any, Callable

try:
    import deal_decision_ui as decision_ui
    import deal_library as library
    import deal_library_ui as library_ui
    import realtor_outreach as outreach
    import team_offer_identity as identity
except ImportError:
    try:
        from . import deal_decision_ui as decision_ui
        from . import deal_library as library
        from . import deal_library_ui as library_ui
        from . import realtor_outreach as outreach
        from . import team_offer_identity as identity
    except ImportError:
        from war_room_offer_engine import deal_decision_ui as decision_ui
        from war_room_offer_engine import deal_library as library
        from war_room_offer_engine import deal_library_ui as library_ui
        from war_room_offer_engine import realtor_outreach as outreach
        from war_room_offer_engine import team_offer_identity as identity


_ORIGINAL_DECISION_RENDER = getattr(
    decision_ui,
    "_team_identity_original_render",
    decision_ui.render,
)
_ORIGINAL_INSTALL_LOG_FIELDS = getattr(
    decision_ui,
    "_team_identity_original_install_log_fields",
    decision_ui._install_log_fields,
)
_ORIGINAL_SAVE_CURRENT = getattr(
    library_ui,
    "_team_identity_original_save_current",
    library_ui._save_current,
)
_ORIGINAL_BUILD_SNAPSHOT = getattr(
    library,
    "_team_identity_original_build_snapshot",
    library.build_snapshot,
)
_ORIGINAL_RESTORE_SNAPSHOT = getattr(
    library,
    "_team_identity_original_restore_snapshot",
    library.restore_snapshot,
)
_ORIGINAL_LIBRARY_RENDER = getattr(
    library_ui,
    "_team_identity_original_render_deal_library_box",
    library_ui.render_deal_library_box,
)


def _generic_sender() -> str:
    return "Acquisitions Team"


def _sender_name(explicit_name: Any = "") -> str:
    return identity.outreach_sender_name(explicit_name) or _generic_sender()


def build_first_touch_outreach_for_team(
    *,
    agent_name: str,
    address: str,
    offer_price: Any = 0,
    asking_price: Any = 0,
    closing_days: int = 14,
    buyer_name: str = "",
) -> dict[str, str]:
    """Generate offer messages with the selected teammate, never a hard-coded name."""
    first_name = outreach._first_name(agent_name)
    offer = outreach.money(offer_price)
    asking = outreach.money(asking_price)
    sender = _sender_name(buyer_name)
    close_text = f"close in about {int(closing_days or 14)} days"
    walkthrough = "This offer is contingent on a walkthrough and confirmation of the property condition."

    if offer:
        text = (
            f"Hi {first_name}, this is {sender}. I’m reaching out about {address}. "
            f"We can offer {offer}, purchase as-is, and {close_text}. "
            f"{walkthrough} Is the seller open to reviewing that? Please text me back when you can."
        )
        subject = f"Offer for {address} — {offer}"
        email_body = (
            f"Hi {first_name},\n\n"
            f"I’m reaching out regarding {address}. Based on the information currently available, "
            f"we can offer {offer}, purchase the property as-is, and {close_text}. "
            "This offer is contingent on a walkthrough, confirmation of the property condition, "
            "and confirmation of title, access, and the property information provided.\n\n"
            "Please let me know whether the seller is open to reviewing this or if there is a price range "
            "that would receive serious consideration.\n\n"
            f"Thank you,\n{sender}"
        )
    else:
        price_reference = f" The current asking price appears to be {asking}." if asking else ""
        text = (
            f"Hi {first_name}, this is {sender}. I’m looking at {address}.{price_reference} "
            "Is it still available, and does the seller have any flexibility for an as-is purchase with a clean closing? "
            "Any offer would be contingent on a walkthrough and confirmation of the property condition."
        )
        subject = f"Question about {address}"
        email_body = (
            f"Hi {first_name},\n\n"
            f"I’m reviewing {address}.{price_reference} Is the property still available, and does the seller have any "
            "flexibility for an as-is purchase with a straightforward closing? Any offer would be contingent on a "
            "walkthrough and confirmation of the property condition. Please share any known repairs, occupancy details, "
            "and the seller’s timing.\n\n"
            f"Thank you,\n{sender}"
        )

    follow_up = (
        f"Hi {first_name}, this is {sender}, following up on {address}. Were you able to confirm whether the seller would consider "
        + (f"the {offer} as-is offer" if offer else "an as-is offer below asking")
        + "? The offer would remain contingent on a walkthrough and confirmation of the property condition."
    )
    return {
        "text": text,
        "email_subject": subject,
        "email_body": email_body,
        "follow_up_text": follow_up,
        "offer_made_by": sender,
    }


def build_realtor_contact_package_for_team(
    *,
    record: dict[str, Any],
    normalized: dict[str, Any],
    offer_price: Any = 0,
    asking_price: Any = 0,
    buyer_name: str = "",
) -> dict[str, Any]:
    sender = _sender_name(buyer_name)
    contact = outreach.extract_realtor_contact(record, normalized)
    phone_info = outreach.classify_phone(contact.get("phone_e164") or contact.get("phone", ""))
    messages = build_first_touch_outreach_for_team(
        agent_name=contact.get("name", ""),
        address=str(normalized.get("address") or record.get("address") or "the property"),
        offer_price=offer_price,
        asking_price=asking_price or normalized.get("asking_price", 0),
        buyer_name=sender,
    )
    return {
        "contact": contact,
        "phone_info": phone_info,
        "preferred_contact_method": outreach.preferred_contact_method(contact, phone_info),
        "outreach": messages,
        "offer_made_by": sender,
    }


def build_master_feed_fields_for_team(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = dict(outreach._team_identity_original_build_master_feed_fields(*args, **kwargs) or {})
    contact_package = kwargs.get("contact_package")
    if contact_package is None and args:
        contact_package = args[0]
    contact_package = contact_package if isinstance(contact_package, dict) else {}
    result["Offer_Made_By"] = (
        identity.clean_name(contact_package.get("offer_made_by"))
        or identity.outreach_sender_name()
        or _generic_sender()
    )
    return result


def build_snapshot_with_offer_identity(state: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(_ORIGINAL_BUILD_SNAPSHOT(state) or {})
    active = identity.active_team_member(state)
    offer_maker = identity.offer_maker_for_deal(state) or active
    if offer_maker:
        snapshot["offer_made_by"] = offer_maker
    if active:
        snapshot["updated_by"] = active
    return snapshot


def restore_snapshot_preserving_operator(state: Any, snapshot: dict[str, Any]) -> None:
    active_values = {
        identity.ACTIVE_MEMBER_KEY: state.get(identity.ACTIVE_MEMBER_KEY, ""),
        identity.MEMBER_SELECTION_KEY: state.get(identity.MEMBER_SELECTION_KEY, identity.UNSELECTED_LABEL),
        identity.CUSTOM_MEMBER_KEY: state.get(identity.CUSTOM_MEMBER_KEY, ""),
    }
    _ORIGINAL_RESTORE_SNAPSHOT(state, snapshot)
    for key, value in active_values.items():
        state[key] = value

    saved_offer_maker = identity.clean_name(
        snapshot.get("offer_made_by")
        or state.get(identity.DEAL_OFFER_MAKER_KEY, "")
        or state.get("decision_offer_made_by", "")
    )
    if saved_offer_maker:
        state[identity.DEAL_OFFER_MAKER_KEY] = saved_offer_maker
        state["decision_offer_made_by"] = saved_offer_maker

    active = identity.active_team_member(state)
    if active:
        state["deal_library_updated_by"] = active


def save_current_with_operator(st: Any, *, automatic: bool = False) -> dict[str, Any]:
    identity.initialize_state(st.session_state)
    if not identity.active_team_member(st.session_state):
        st.session_state["deal_library_last_error"] = (
            "Select the current team member before saving. The Deal Library will not attribute this version to another person."
        )
        return {"ok": False, "skipped": True, "missing_team_member": True}
    identity.apply_active_member_to_deal(st.session_state, overwrite_offer_maker=False)
    return _ORIGINAL_SAVE_CURRENT(st, automatic=automatic)


def install_log_fields_with_identity(st: Any, ui: Any) -> None:
    _ORIGINAL_INSTALL_LOG_FIELDS(st, ui)
    if getattr(ui, "_team_offer_identity_log_fields_installed", False):
        return
    original = getattr(ui, "build_deal_log_row", None)
    if not callable(original):
        return

    def wrapped(*args: Any, **kwargs: Any):
        row = original(*args, **kwargs)
        row.update(
            {
                "offer_made_by": identity.offer_maker_for_deal(st.session_state),
                "updated_by": identity.active_team_member(st.session_state),
                "assigned_to": st.session_state.get("deal_library_assigned_to", ""),
            }
        )
        return row

    ui.build_deal_log_row = wrapped
    ui._team_offer_identity_log_fields_installed = True


def render_deal_library_with_identity(st: Any) -> None:
    active = identity.active_team_member(st.session_state)
    if active:
        st.session_state["deal_library_updated_by"] = active

    original_text_input = st.text_input

    def text_input_with_identity(label: str, *args: Any, **kwargs: Any):
        if str(label) == "Updated By":
            name = identity.active_team_member(st.session_state)
            if name:
                st.session_state["deal_library_updated_by"] = name
            kwargs["disabled"] = True
            kwargs.setdefault("help", "Automatically uses the current team member selected above.")
        return original_text_input(label, *args, **kwargs)

    st.text_input = text_input_with_identity
    try:
        if active:
            offer_maker = identity.offer_maker_for_deal(st.session_state) or active
            st.caption(f"Current teammate: {active} | Offer made by: {offer_maker}")
        else:
            st.warning("Select the current team member above before saving this deal for the team.")
        return _ORIGINAL_LIBRARY_RENDER(st)
    finally:
        st.text_input = original_text_input


def render_decision_with_team_identity(
    st: Any,
    ui: Any,
    original_renderer: Callable,
    exit_mode_value: str = "Auto",
) -> Any:
    identity.initialize_state(st.session_state)
    original_header = st.header

    def header_with_identity(body: Any, *args: Any, **kwargs: Any):
        result = original_header(body, *args, **kwargs)
        if str(body or "").strip() == "Deal Decision Center":
            identity.render_team_member_selector(st)
        return result

    st.header = header_with_identity
    delta_generator = None
    original_button = None
    try:
        try:
            from streamlit.delta_generator import DeltaGenerator

            delta_generator = DeltaGenerator
            original_button = DeltaGenerator.button

            def button_with_identity(self: Any, label: str, *args: Any, **kwargs: Any):
                label_text = str(label or "")
                if label_text == "Pull Everything & Tell Me" and not identity.active_team_member(st.session_state):
                    kwargs["disabled"] = True
                    kwargs.setdefault("help", "Select your team member name above before calculating an offer.")
                clicked = original_button(self, label, *args, **kwargs)
                if clicked and label_text == "Pull Everything & Tell Me":
                    identity.apply_active_member_to_deal(
                        st.session_state,
                        overwrite_offer_maker=True,
                    )
                elif clicked and label_text == "Start New Property":
                    st.session_state.pop(identity.DEAL_OFFER_MAKER_KEY, None)
                    st.session_state.pop("decision_offer_made_by", None)
                return clicked

            DeltaGenerator.button = button_with_identity
        except Exception:
            delta_generator = None
            original_button = None

        return _ORIGINAL_DECISION_RENDER(st, ui, original_renderer, exit_mode_value)
    finally:
        st.header = original_header
        if delta_generator is not None and original_button is not None:
            delta_generator.button = original_button


def _patch_loaded_aliases() -> None:
    for module_name in (
        "deal_decision_ui",
        "war_room_offer_engine.deal_decision_ui",
        "war_room_offer_engine.war_room_offer_engine.deal_decision_ui",
    ):
        loaded = sys.modules.get(module_name)
        if loaded is not None:
            loaded.render = render_decision_with_team_identity
            loaded._install_log_fields = install_log_fields_with_identity
            loaded.render_deal_library_box = render_deal_library_with_identity


def install() -> bool:
    if getattr(decision_ui, "_team_offer_identity_installed", False):
        _patch_loaded_aliases()
        return True

    outreach._team_identity_original_build_first_touch_outreach = outreach.build_first_touch_outreach
    outreach._team_identity_original_build_realtor_contact_package = outreach.build_realtor_contact_package
    outreach._team_identity_original_build_master_feed_fields = outreach.build_master_feed_fields
    outreach.build_first_touch_outreach = build_first_touch_outreach_for_team
    outreach.build_realtor_contact_package = build_realtor_contact_package_for_team
    outreach.build_master_feed_fields = build_master_feed_fields_for_team

    for key in (identity.DEAL_OFFER_MAKER_KEY, "decision_offer_made_by"):
        if key not in library.PERSISTED_STATE_KEYS:
            library.PERSISTED_STATE_KEYS.append(key)

    library._team_identity_original_build_snapshot = _ORIGINAL_BUILD_SNAPSHOT
    library._team_identity_original_restore_snapshot = _ORIGINAL_RESTORE_SNAPSHOT
    library.build_snapshot = build_snapshot_with_offer_identity
    library.restore_snapshot = restore_snapshot_preserving_operator

    library_ui._team_identity_original_save_current = _ORIGINAL_SAVE_CURRENT
    library_ui._team_identity_original_render_deal_library_box = _ORIGINAL_LIBRARY_RENDER
    library_ui._save_current = save_current_with_operator
    library_ui.build_snapshot = build_snapshot_with_offer_identity
    library_ui.restore_snapshot = restore_snapshot_preserving_operator
    library_ui.render_deal_library_box = render_deal_library_with_identity

    decision_ui._team_identity_original_render = _ORIGINAL_DECISION_RENDER
    decision_ui._team_identity_original_install_log_fields = _ORIGINAL_INSTALL_LOG_FIELDS
    decision_ui.render = render_decision_with_team_identity
    decision_ui._install_log_fields = install_log_fields_with_identity
    decision_ui.render_deal_library_box = render_deal_library_with_identity

    _patch_loaded_aliases()
    decision_ui._team_offer_identity_installed = True
    return True


install()
