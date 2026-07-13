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
    photos = _as_list(normalized.get("listing_photos") or data.get("listing_photos") or data.get("photo_all"))
    if not photos and data.get("primary_photo"):
        photos = _as_list(data.get("primary_photo"))
    return {
        "contact_package": contact_package,
        "master_feed_fields": master_fields,
        "photos": photos,
    }


def render_realtor_outreach_panel(st, normalized: dict[str, Any]) -> None:
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
        st.info("No Zillow photos were returned for this listing.")

    st.markdown("### Realtor Contact Card")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Agent", contact.get("name") or "Not found")
    c2.metric("Phone", contact.get("phone") or "Not found")
    c3.metric("Phone type", phone_info.get("phone_type") or "Unknown")
    c4.metric("Preferred contact", contact_package.get("preferred_contact_method") or "Needs lookup")
    st.write(
        {
            "Email": contact.get("email") or "Not found",
            "Brokerage": contact.get("brokerage") or "Not found",
            "Textable": "Yes" if phone_info.get("textable") is True else "No" if phone_info.get("textable") is False else "Unknown",
            "Phone lookup source": phone_info.get("source") or "Not checked",
        }
    )
    if phone_info.get("warning"):
        st.warning(phone_info.get("warning"))

    st.markdown("### First-Touch Realtor Text")
    st.text_area(
        "Copy-ready text",
        value=outreach.get("text", ""),
        height=130,
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
        height=260,
        key="one_load_realtor_email_body",
    )
    st.markdown("### Follow-Up Text")
    st.text_area(
        "Copy-ready follow-up",
        value=outreach.get("follow_up_text", ""),
        height=100,
        key="one_load_realtor_follow_up_text",
    )

    st.markdown("### MASTER_FEED Output Preview")
    st.write(master_fields)
