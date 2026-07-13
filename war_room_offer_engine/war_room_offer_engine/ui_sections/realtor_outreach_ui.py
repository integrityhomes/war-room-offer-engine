from __future__ import annotations

from typing import Any

try:
    import one_load_sources_safe  # noqa: F401 - installs hardened Zillow pull into One-Load
except ImportError:
    try:
        from .. import one_load_sources_safe  # noqa: F401
    except ImportError:
        from war_room_offer_engine import one_load_sources_safe  # noqa: F401

try:
    from realtor_outreach import build_master_feed_fields, build_realtor_contact_package
except ImportError:
    try:
        from ..realtor_outreach import build_master_feed_fields, build_realtor_contact_package
    except ImportError:
        from war_room_offer_engine.realtor_outreach import build_master_feed_fields, build_realtor_contact_package


_TEXT_WIDGET_SOURCES = {
    "one_load_property_address": "address",
    "one_load_contact_name": "listing_agent_name",
    "one_load_contact_phone": "listing_agent_phone",
    "one_load_contact_email": "listing_agent_email",
}
_NUMBER_WIDGET_SOURCES = {
    "one_load_asking_price": "asking_price",
}


def _blank(value: Any) -> bool:
    return value in [None, "", 0, 0.0, [], {}]


def _looks_like_company(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return any(
        term in f" {text}"
        for term in [" llc", " inc", " corp", " properties", " realty", " brokerage", " real estate", " holdings"]
    )


def _source_value(st, source_key: str) -> Any:
    value = st.session_state.get(source_key)
    if not _blank(value):
        return value
    normalized = st.session_state.get("one_load_normalized", {}) or {}
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    return data.get(source_key) if isinstance(data, dict) else ""


def _install_one_load_widget_autofill() -> None:
    """Fill the visible One-Load widgets on the rerun after a successful import.

    The wrappers only touch the five One-Load fields that should mirror imported
    Zillow data. They run before each widget is instantiated, which avoids the
    Streamlit restriction against changing a widget after it has been rendered.
    """
    try:
        import streamlit as st
    except Exception:
        return

    if getattr(st, "_one_load_visible_autofill_installed", False):
        return

    original_text_input = st.text_input
    original_number_input = st.number_input

    def text_input_with_autofill(label, *args, **kwargs):
        key = kwargs.get("key")
        source_key = _TEXT_WIDGET_SOURCES.get(str(key or ""))
        if source_key and _blank(st.session_state.get(key)):
            value = _source_value(st, source_key)
            if source_key == "listing_agent_name" and _looks_like_company(value):
                value = ""
            if not _blank(value):
                st.session_state[key] = str(value)
        return original_text_input(label, *args, **kwargs)

    def number_input_with_autofill(label, *args, **kwargs):
        key = kwargs.get("key")
        source_key = _NUMBER_WIDGET_SOURCES.get(str(key or ""))
        if source_key and _blank(st.session_state.get(key)):
            value = _source_value(st, source_key)
            if not _blank(value):
                try:
                    st.session_state[key] = int(float(value))
                except (TypeError, ValueError):
                    pass
        return original_number_input(label, *args, **kwargs)

    st.text_input = text_input_with_autofill
    st.number_input = number_input_with_autofill
    st._one_load_visible_autofill_installed = True


_install_one_load_widget_autofill()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    parts = []
    for separator in ["\n", " | ", "|"]:
        if separator in text:
            parts = [piece.strip() for piece in text.split(separator)]
            break
    if not parts:
        parts = [text]
    return [piece for piece in parts if piece.startswith(("http://", "https://"))]


def _dedupe_urls(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        for url in _as_list(value):
            if url not in seen:
                seen.add(url)
                result.append(url)
    return result


def _acquisition_priority(normalized: dict[str, Any]) -> str:
    decision = str(normalized.get("final_decision") or normalized.get("final_simple_answer") or "").lower()
    if "buy" in decision or "great" in decision:
        return "High"
    if "renegotiate" in decision or "review" in decision:
        return "Medium"
    return "Low"


def _counter_step(normalized: dict[str, Any]) -> float:
    opening = float(normalized.get("first_offer", 0) or 0)
    maximum = float(normalized.get("internal_max", 0) or 0)
    if opening <= 0 or maximum <= opening:
        return 0
    return max(round((maximum - opening) / 3 / 100) * 100, 500)


def build_visible_outreach_package(normalized: dict[str, Any]) -> dict[str, Any]:
    normalized = normalized or {}
    data = dict(normalized.get("data", {}) or {})
    first_offer = float(normalized.get("first_offer", 0) or 0)
    internal_max = float(normalized.get("internal_max", 0) or 0)
    counter_step = _counter_step(normalized)
    next_counter = min(first_offer + counter_step, internal_max) if first_offer and internal_max else 0

    contact_package = build_realtor_contact_package(
        record=data,
        normalized=data,
        offer_price=first_offer,
        asking_price=data.get("asking_price", 0),
    )
    master_fields = build_master_feed_fields(
        contact_package=contact_package,
        max_price=internal_max,
        opening_offer=first_offer,
        next_counter_offer=next_counter,
        counter_offer_step=counter_step,
        deal_type=str(normalized.get("final_decision") or normalized.get("final_simple_answer") or "Review"),
        acquisition_priority=_acquisition_priority(normalized),
        zillow_link=str(data.get("listing_url") or data.get("zillow_link") or normalized.get("input_value") or ""),
    )
    photos = _dedupe_urls(
        [
            normalized.get("listing_photos"),
            normalized.get("primary_photo"),
            normalized.get("photo_all"),
            normalized.get("photo_main"),
            normalized.get("imgSrc"),
            data.get("listing_photos"),
            data.get("primary_photo"),
            data.get("photo_all"),
            data.get("photo_main"),
            data.get("photos"),
            data.get("images"),
            data.get("imgSrc"),
        ]
    )
    return {
        "contact_package": contact_package,
        "master_feed_fields": master_fields,
        "photos": photos,
    }


def _request_visible_autofill_rerun(st, normalized: dict[str, Any]) -> None:
    data = normalized.get("data", {}) if isinstance(normalized, dict) else {}
    if not isinstance(data, dict):
        return
    token = str(data.get("zpid") or data.get("listing_url") or data.get("address") or "").strip()
    if not token or st.session_state.get("_one_load_visible_autofill_token") == token:
        return

    source_values = {
        "one_load_property_address": data.get("address"),
        "one_load_asking_price": data.get("asking_price"),
        "one_load_contact_name": data.get("listing_agent_name"),
        "one_load_contact_phone": data.get("listing_agent_phone"),
        "one_load_contact_email": data.get("listing_agent_email"),
    }
    needs_rerun = any(_blank(st.session_state.get(key)) and not _blank(value) for key, value in source_values.items())
    if needs_rerun:
        st.session_state["_one_load_visible_autofill_token"] = token
        st.rerun()


def render_realtor_outreach_panel(st, normalized: dict[str, Any]) -> None:
    _request_visible_autofill_rerun(st, normalized)

    package = build_visible_outreach_package(normalized)
    contact_package = package["contact_package"]
    contact = contact_package.get("contact", {}) or {}
    phone_info = contact_package.get("phone_info", {}) or {}
    outreach = contact_package.get("outreach", {}) or {}
    master_fields = package["master_feed_fields"]
    photos = package["photos"]

    st.markdown("### Zillow Photos")
    if photos:
        shown = photos[:12]
        columns = st.columns(3)
        for index, photo_url in enumerate(shown):
            with columns[index % 3]:
                st.image(photo_url, use_container_width=True)
        if len(photos) > len(shown):
            st.caption(f"Showing {len(shown)} of {len(photos)} available Zillow photos.")
    else:
        st.info("No Zillow photos were returned by the current Zillow scraper for this listing.")

    st.markdown("### Realtor Contact Card")
    agent_name = contact.get("name") or "Agent name not provided by Zillow"
    brokerage = contact.get("brokerage") or contact.get("raw_name") or "Not found"
    phone = contact.get("phone") or "Not found"
    email = contact.get("email") or "Not found"
    textable = "Yes" if phone_info.get("textable") is True else "No" if phone_info.get("textable") is False else "Unknown"

    st.markdown(f"**Agent / individual contact:** {agent_name}")
    st.markdown(f"**Listing office / brokerage:** {brokerage}")
    st.markdown(f"**Phone:** {phone}")
    st.markdown(f"**Email:** {email}")
    st.markdown(f"**Phone type:** {phone_info.get('phone_type') or 'Unknown'}")
    st.markdown(f"**Textable:** {textable}")
    st.markdown(f"**Preferred contact method:** {contact_package.get('preferred_contact_method') or 'Needs lookup'}")
    st.markdown(f"**Phone lookup source:** {phone_info.get('source') or 'Not checked'}")
    if phone_info.get("warning"):
        st.warning(phone_info.get("warning"))

    st.markdown("### First-Touch Realtor Text")
    st.text_area(
        "Copy-ready text",
        value=outreach.get("text", ""),
        height=160,
        key="one_load_realtor_first_touch_text",
    )
    st.markdown("### First-Touch Realtor Email")
    st.text_input(
        "Email subject",
        value=outreach.get("email_subject", ""),
        key="one_load_realtor_email_subject",
    )
    st.text_area(
        "Email body",
        value=outreach.get("email_body", ""),
        height=300,
        key="one_load_realtor_email_body",
    )
    st.markdown("### Follow-Up Text")
    st.text_area(
        "Copy-ready follow-up",
        value=outreach.get("follow_up_text", ""),
        height=130,
        key="one_load_realtor_follow_up_text",
    )

    st.markdown("### MASTER_FEED Output Preview")
    st.write(master_fields)
