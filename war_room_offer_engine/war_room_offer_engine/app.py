from __future__ import annotations

import pandas as pd
import streamlit as st

from rules import Assumptions, DealInput, analyze_deal, money
from ai_writer import build_ai_summary
from data_sources import fetch_all_sources, merge_results, get_secret

st.set_page_config(page_title="War Room Offer Engine", page_icon="🏠", layout="wide")

FIELD_DEFAULTS = {
    "address": "",
    "market": "",
    "lead_type": "Agent",
    "status": "Unknown",
    "asking_price": 35000,
    "rent": 900,
    "occupancy": "Unknown",
    "livable": "Unknown",
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
    "taxes": 0,
    "days_on_market": 0,
    "arv": 0,
    "repairs": 0,
    "notes": "",
}

for key, value in FIELD_DEFAULTS.items():
    st.session_state.setdefault(key, value)
st.session_state.setdefault("last_source_results", [])
st.session_state.setdefault("last_auto_pull", {})


def update_state_from_auto_pull(data: dict) -> None:
    mapping = {
        "market": "market",
        "asking_price": "asking_price",
        "rent": "rent",
        "beds": "beds",
        "baths": "baths",
        "sqft": "sqft",
        "taxes": "taxes",
        "days_on_market": "days_on_market",
        "status": "status",
        "arv": "arv",
    }
    for source_key, state_key in mapping.items():
        value = data.get(source_key)
        if value not in [None, "", 0]:
            if state_key in ["asking_price", "rent", "sqft", "taxes", "days_on_market", "arv"]:
                st.session_state[state_key] = int(float(value))
            elif state_key in ["beds", "baths"]:
                st.session_state[state_key] = float(value)
            else:
                st.session_state[state_key] = str(value)

    note_bits = []
    for label in ["agent_name", "agent_phone", "listing_url", "year_built", "property_type", "matched_sheet_address"]:
        if data.get(label):
            pretty = label.replace("_", " ").title()
            note_bits.append(f"{pretty}: {data[label]}")
    if note_bits:
        current = st.session_state.get("notes", "")
        auto_note = "Auto-pulled data: " + " | ".join(note_bits)
        st.session_state["notes"] = (current + "\n" + auto_note).strip() if current else auto_note


st.title("🏠 War Room Offer Engine")
st.caption("Deal Analyzer MVP — pulls data automatically when keys/sheet links are added, manual fallback always works.")

with st.sidebar:
    st.header("Offer Assumptions")
    min_assignment_fee = st.number_input("Minimum assignment fee", min_value=0, value=10000, step=500)
    exception_assignment_fee = st.number_input("Exception assignment fee", min_value=0, value=5000, step=500)
    slow_flip_rent_multiple = st.slider("Slow flip resale multiple x rent", 20, 70, 45, 1)
    close_title_buffer = st.number_input("Close/title/safety buffer", min_value=0, value=1500, step=250)
    target_offer_discount = st.slider("Target offer discount from max", 0.50, 1.00, 0.85, 0.01)
    wholesale_buyer_percent_arv = st.slider("Wholesale buyer % of ARV", 0.40, 0.90, 0.70, 0.01)

    st.divider()
    st.header("Data Connections")
    st.caption("Green means ready. Missing connections do not stop manual analysis.")
    st.write("✅ RentCast API key" if get_secret("RENTCAST_API_KEY") else "⚠️ RentCast API key missing")
    st.write("✅ Apify/Zillow sheet" if get_secret("APIFY_ZILLOW_SHEET_CSV_URL") else "⚠️ Apify/Zillow sheet URL missing")
    st.write("✅ Lead sheet" if get_secret("LEADS_SHEET_CSV_URL") else "⚠️ Lead sheet URL missing")

assumptions = Assumptions(
    min_assignment_fee=float(min_assignment_fee),
    exception_assignment_fee=float(exception_assignment_fee),
    slow_flip_rent_multiple=float(slow_flip_rent_multiple),
    close_title_buffer=float(close_title_buffer),
    target_offer_discount=float(target_offer_discount),
    wholesale_buyer_percent_arv=float(wholesale_buyer_percent_arv),
)

st.subheader("1. Pull Property Data")
lookup_col1, lookup_col2 = st.columns([3, 1])
with lookup_col1:
    st.text_input("Property address", key="address", placeholder="123 Main St, Decatur IL 62522")
with lookup_col2:
    st.write("")
    st.write("")
    pull_data = st.button("Pull Data", type="primary", use_container_width=True)

if pull_data:
    with st.spinner("Pulling RentCast + Google Sheet data..."):
        results = fetch_all_sources(
            st.session_state["address"],
            beds=float(st.session_state.get("beds", 0) or 0),
            baths=float(st.session_state.get("baths", 0) or 0),
            sqft=float(st.session_state.get("sqft", 0) or 0),
        )
        merged = merge_results(results)
        st.session_state["last_source_results"] = results
        st.session_state["last_auto_pull"] = merged
        update_state_from_auto_pull(merged)

    good = [r.source for r in results if r.ok]
    if good:
        st.success("Pulled data from: " + ", ".join(good))
    else:
        st.warning("No data pulled yet. Add Streamlit secrets or verify the address. Manual analysis still works.")

if st.session_state.get("last_source_results"):
    with st.expander("Data pull results"):
        for result in st.session_state["last_source_results"]:
            if result.ok:
                st.success(f"{result.source}: {result.message}")
                st.write(result.data)
            else:
                st.warning(f"{result.source}: {result.message}")

st.subheader("2. Property Inputs")
st.caption("Slow Flip does not depend on ARV/repairs, but the app still pulls value/facts so you can make a smarter decision.")

exit_mode = st.radio(
    "Deal type",
    ["Slow Flip Only", "Wholesale Only", "Auto"],
    horizontal=True,
    help="Use Slow Flip Only for your normal owner-finance/slow-flip buy box. ARV/repairs are informational unless you switch to Wholesale/Auto.",
)

col1, col2, col3 = st.columns(3)
with col1:
    st.text_input("Market / city", key="market", placeholder="Decatur IL")
    st.selectbox("Lead type", ["Agent", "Seller", "Wholesaler", "Other"], key="lead_type")
    st.selectbox("Listing/status", ["Active", "Pending", "Sold", "Off-market", "Unknown"], key="status")
    st.number_input("Days on market", min_value=0, step=1, key="days_on_market")

with col2:
    st.number_input("Asking price", min_value=0, step=1000, key="asking_price")
    st.number_input("Rent estimate", min_value=0, step=25, key="rent")
    st.selectbox("Occupancy", ["Unknown", "Vacant", "Tenant occupied", "Owner occupied"], key="occupancy")
    st.selectbox("Livable now?", ["Unknown", "Yes", "No"], key="livable")

with col3:
    st.number_input("Beds", min_value=0.0, step=0.5, key="beds")
    st.number_input("Baths", min_value=0.0, step=0.5, key="baths")
    st.number_input("Sq ft", min_value=0, step=50, key="sqft")
    st.number_input("Annual taxes", min_value=0, step=100, key="taxes")

show_wholesale_info = exit_mode in ["Wholesale Only", "Auto"] or st.session_state.get("arv", 0) > 0
if show_wholesale_info:
    st.markdown("### Value / Wholesale Info")
    w1, w2 = st.columns(2)
    with w1:
        st.number_input("ARV / estimated resale", min_value=0, step=1000, key="arv")
    with w2:
        st.number_input("Estimated repairs", min_value=0, step=1000, key="repairs")
else:
    st.info("Slow Flip mode uses rent × multiple. ARV and repairs are not required, but value data will show here after RentCast pulls it.")

st.text_area("Seller/agent notes, condition, occupancy, motivation", height=120, key="notes")

analyze = st.button("Analyze Deal", type="primary")

if analyze:
    deal = DealInput(
        address=st.session_state["address"],
        market=st.session_state["market"],
        lead_type=st.session_state["lead_type"],
        exit_mode=exit_mode,
        asking_price=float(st.session_state["asking_price"]),
        rent=float(st.session_state["rent"]),
        beds=float(st.session_state["beds"]),
        baths=float(st.session_state["baths"]),
        sqft=float(st.session_state["sqft"]),
        taxes=float(st.session_state["taxes"]),
        status=st.session_state["status"],
        occupancy=st.session_state["occupancy"],
        livable=st.session_state["livable"],
        days_on_market=int(st.session_state["days_on_market"]),
        notes=st.session_state["notes"],
        arv=float(st.session_state.get("arv", 0) or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
    )

    result = analyze_deal(deal, assumptions)
    best = result["best"]

    st.divider()
    st.subheader("Decision")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Deal Grade", result["grade"])
    m2.metric("Best Exit", result["best_exit"])
    m3.metric("Target Offer", f"{money(best['target_offer_low'])} - {money(best['target_offer_high'])}")
    m4.metric("Max Offer", money(best["max_offer"]))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Slow Flip Numbers")
        slow = result["slow_flip"]
        st.write({
            "Resale to slow flipper": money(slow["resale_to_slow_flipper"]),
            "Target offer low": money(slow["target_offer_low"]),
            "Target offer high": money(slow["target_offer_high"]),
            "Max offer": money(slow["max_offer"]),
            "Estimated fee at asking": money(slow["estimated_fee_at_ask"]),
        })

    with c2:
        st.subheader("Value / Wholesale Reference")
        wholesale = result["wholesale"]
        st.write({
            "ARV / estimated value": money(st.session_state.get("arv", 0)),
            "Repairs": money(st.session_state.get("repairs", 0)),
            "Buyer target": money(wholesale["buyer_target"]),
            "Wholesale max offer": money(wholesale["max_offer"]),
            "Wholesale estimated fee at asking": money(wholesale["estimated_fee_at_ask"]),
        })

    st.subheader("Risk Notes")
    for risk in result["risks"]:
        st.warning(risk)

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
            "address": st.session_state["address"],
            "market": st.session_state["market"],
            "lead_type": st.session_state["lead_type"],
            "exit_mode": exit_mode,
            "grade": result["grade"],
            "best_exit": result["best_exit"],
            "asking_price": st.session_state["asking_price"],
            "rent": st.session_state["rent"],
            "arv": st.session_state.get("arv", 0),
            "repairs": st.session_state.get("repairs", 0),
            "target_offer_low": best["target_offer_low"],
            "target_offer_high": best["target_offer_high"],
            "max_offer": best["max_offer"],
            "estimated_fee_at_ask": best["estimated_fee_at_ask"],
            "livable": st.session_state["livable"],
            "occupancy": st.session_state["occupancy"],
            "notes": st.session_state["notes"],
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
