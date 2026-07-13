from __future__ import annotations

import html
import re
from typing import Any


AUTO_PULL_WIDGET_KEYS = {
    "address",
    "city",
    "state",
    "zip",
    "market",
    "property_type",
    "beds",
    "baths",
    "sqft",
    "lot_size",
    "year_built",
    "asking_price",
    "contract_price",
    "status",
    "days_on_market",
    "listing_url",
    "listing_agent_name",
    "listing_agent_phone",
    "listing_agent_email",
    "listing_brokerage",
    "sheet_arv",
    "rentcast_arv",
    "rent",
    "tax_assessed_value",
    "taxes",
    "last_sale_date",
    "last_sale_price",
    "occupancy",
    "livable",
}

QUICK_NAV_ITEMS = [
    ("🏠", "One-Load Analyzer", "one-load"),
    ("🔎", "Property Data", "property-data"),
    ("🔧", "Repairs & Walkthrough", "repairs"),
    ("📊", "Sold Comps & ARV", "comps-arv"),
    ("🏘️", "Rent Fallback", "rent-fallback"),
    ("🎯", "Buyer Demand", "buyer-demand"),
    ("📣", "Buyer Outreach / Dispo", "buyer-outreach"),
    ("🛡️", "Deal Protection", "deal-protection"),
    ("📇", "Realtor Contact & Offers", "realtor-outreach"),
    ("✅", "Final Decision", "decision"),
    ("🧪", "Greatness Test / QA", "greatness-test"),
]


def anchor_for_text(value: Any) -> str:
    text = re.sub(r"[#*_`]+", " ", str(value or "")).strip().lower()
    mappings = [
        (("one-load deal analyzer",), "one-load"),
        (("pull property data", "lead data intake"), "property-data"),
        (("repair / condition analyzer", "repairs & property condition", "repair estimate"), "repairs"),
        (("sold comps", "arv", "comparable"), "comps-arv"),
        (("rent fallback",), "rent-fallback"),
        (("buyer demand",), "buyer-demand"),
        (("buyer outreach", "dispo test", "buyer blast"), "buyer-outreach"),
        (("deal protection",), "deal-protection"),
        (("realtor contact", "first-touch realtor", "follow-up text"), "realtor-outreach"),
        (("simple deal answer", "final decision", "decision"), "decision"),
        (("greatness test", "full system qa"), "greatness-test"),
        (("war room offer engine",), "top"),
    ]
    for needles, anchor in mappings:
        if any(needle in text for needle in needles):
            return anchor
    return ""


def _repair_status_html(st) -> str:
    try:
        amount = float(st.session_state.get("repairs", 0) or 0)
    except Exception:
        amount = 0.0
    source = html.escape(str(st.session_state.get("repair_source", "Missing") or "Missing"))
    confidence = html.escape(str(st.session_state.get("repair_scope_confidence", "Unknown") or "Unknown"))
    return (
        '<div class="wr-repair-status">'
        '<div class="wr-status-title">Repair status</div>'
        f'<div><b>${amount:,.0f}</b> · {source}</div>'
        f'<div class="wr-status-small">Scope: {confidence}</div>'
        '</div>'
    )


def _quick_nav_html(st) -> str:
    cards = "".join(
        f'<a class="wr-nav-card" href="#{anchor}" target="_self"><span>{icon}</span>{html.escape(label)}</a>'
        for icon, label, anchor in QUICK_NAV_ITEMS
    )
    return f"""
<style>
.wr-nav-wrap {{ margin: 0.25rem 0 1rem 0; }}
.wr-nav-title {{ font-weight: 800; font-size: 1.15rem; margin-bottom: .45rem; }}
.wr-nav-card {{
  display: flex; gap: .55rem; align-items: center; text-decoration: none !important;
  padding: .62rem .72rem; margin: .35rem 0; border: 1px solid rgba(128,128,128,.28);
  border-radius: .65rem; background: rgba(128,128,128,.08); color: inherit !important;
  font-weight: 650;
}}
.wr-nav-card:hover {{ border-color: #ff4b4b; background: rgba(255,75,75,.10); }}
.wr-repair-status {{
  margin: .7rem 0 .9rem 0; padding: .7rem; border-radius: .65rem;
  border-left: 4px solid #ff4b4b; background: rgba(255,75,75,.08);
}}
.wr-status-title {{ font-weight: 800; margin-bottom: .2rem; }}
.wr-status-small {{ opacity: .78; font-size: .85rem; }}
</style>
<div class="wr-nav-wrap">
  <div class="wr-nav-title">Quick Tools</div>
  {_repair_status_html(st)}
  {cards}
</div>
"""


def install_runtime_guard() -> bool:
    try:
        import streamlit as st
        from streamlit.errors import StreamlitAPIException
        from streamlit.runtime.state.session_state_proxy import SessionStateProxy, get_session_state
    except Exception:
        return False

    if not getattr(SessionStateProxy, "_war_room_safe_setitem_installed", False):
        original_setitem = SessionStateProxy.__setitem__

        def safe_setitem(self, key, value):
            key_text = str(key)
            try:
                return original_setitem(self, key_text, value)
            except StreamlitAPIException:
                if key_text not in AUTO_PULL_WIDGET_KEYS:
                    raise
                state = get_session_state()
                if not hasattr(state, "reset_state_value"):
                    raise
                state.reset_state_value(key_text, value)
                state.reset_state_value("_war_room_auto_pull_reset_pending", True)
                return None

        SessionStateProxy.__setitem__ = safe_setitem
        SessionStateProxy._war_room_safe_setitem_installed = True

    if not getattr(st, "_war_room_quick_nav_installed", False):
        original_title = st.title
        original_header = st.header
        original_subheader = st.subheader
        original_markdown = st.markdown
        original_success = st.success

        def add_anchor(value: Any) -> None:
            anchor = anchor_for_text(value)
            if anchor:
                original_markdown(f'<div id="{anchor}"></div>', unsafe_allow_html=True)

        def render_sidebar_nav() -> None:
            with st.sidebar:
                original_markdown(_quick_nav_html(st), unsafe_allow_html=True)

        def title_with_nav(body, *args, **kwargs):
            render_sidebar_nav()
            add_anchor(body)
            return original_title(body, *args, **kwargs)

        def header_with_anchor(body, *args, **kwargs):
            add_anchor(body)
            return original_header(body, *args, **kwargs)

        def subheader_with_anchor(body, *args, **kwargs):
            add_anchor(body)
            return original_subheader(body, *args, **kwargs)

        def markdown_with_anchor(body, *args, **kwargs):
            text = str(body or "")
            if text.lstrip().startswith("#"):
                add_anchor(text)
            return original_markdown(body, *args, **kwargs)

        def success_with_safe_rerun(body, *args, **kwargs):
            result = original_success(body, *args, **kwargs)
            try:
                state = get_session_state()
                pending = bool(state["_war_room_auto_pull_reset_pending"])
            except Exception:
                pending = False
            if pending:
                state.reset_state_value("_war_room_auto_pull_reset_pending", False)
                st.rerun()
            return result

        st.title = title_with_nav
        st.header = header_with_anchor
        st.subheader = subheader_with_anchor
        st.markdown = markdown_with_anchor
        st.success = success_with_safe_rerun
        st._war_room_quick_nav_installed = True

    return True


install_runtime_guard()
