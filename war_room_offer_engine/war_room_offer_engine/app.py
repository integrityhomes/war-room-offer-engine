from __future__ import annotations

import pandas as pd
import streamlit as st

from rules import Assumptions, DealInput, analyze_deal, money
from ai_writer import build_ai_summary

st.set_page_config(page_title="War Room Offer Engine", page_icon="🏠", layout="wide")

st.title("🏠 War Room Offer Engine")
st.caption("Deal Analyzer MVP — manual first, APIs later.")

with st.sidebar:
    st.header("Offer Assumptions")
    min_assignment_fee = st.number_input("Minimum assignment fee", min_value=0, value=10000, step=500)
    discounted_assignment_fee = st.number_input("Exception assignment fee", min_value=0, value=5000, step=500)
    wholesale_buyer_percent_arv = st.slider("Wholesale buyer % of ARV", 0.40, 0.90, 0.70, 0.01)
    slow_flip_rent_multiple = st.slider("Slow flip rent multiple", 20, 70, 45, 1)
    slow_flip_repair_factor = st.slider("Slow flip repair adjustment", 0.0, 1.0, 0.50, 0.05)
    cash_close_buffer = st.number_input("Close/title/safety buffer", min_value=0, value=1500, step=250)
    target_offer_discount = st.slider("Target offer discount from max", 0.50, 1.00, 0.85, 0.01)

assumptions = Assumptions(
    min_assignment_fee=float(min_assignment_fee),
    discounted_assignment_fee=float(discounted_assignment_fee),
    wholesale_buyer_percent_arv=float(wholesale_buyer_percent_arv),
    slow_flip_rent_multiple=float(slow_flip_rent_multiple),
    slow_flip_repair_factor=float(slow_flip_repair_factor),
    cash_close_buffer=float(cash_close_buffer),
    target_offer_discount=float(target_offer_discount),
)

st.subheader("Property Inputs")

col1, col2, col3 = st.columns(3)
with col1:
    address = st.text_input("Property address", placeholder="123 Main St, Decatur IL")
    market = st.text_input("Market / city", placeholder="Decatur IL")
    lead_type = st.selectbox("Lead type", ["Agent", "Seller", "Wholesaler", "Other"])
    status = st.selectbox("Listing/status", ["Active", "Pending", "Sold", "Off-market", "Unknown"])

with col2:
    asking_price = st.number_input("Asking price", min_value=0, value=35000, step=1000)
    arv = st.number_input("ARV / estimated resale", min_value=0, value=75000, step=1000)
    repairs = st.number_input("Estimated repairs", min_value=0, value=20000, step=1000)
    rent = st.number_input("Rent estimate", min_value=0, value=900, step=25)

with col3:
    beds = st.number_input("Beds", min_value=0.0, value=3.0, step=0.5)
    baths = st.number_input("Baths", min_value=0.0, value=1.0, step=0.5)
    sqft = st.number_input("Sq ft", min_value=0, value=1000, step=50)
    taxes = st.number_input("Annual taxes", min_value=0, value=0, step=100)
    days_on_market = st.number_input("Days on market", min_value=0, value=0, step=1)

notes = st.text_area("Seller/agent notes, condition, occupancy, motivation", height=120)

analyze = st.button("Analyze Deal", type="primary")

if analyze:
    deal = DealInput(
        address=address,
        market=market,
        lead_type=lead_type,
        asking_price=float(asking_price),
        arv=float(arv),
        repairs=float(repairs),
        rent=float(rent),
        beds=float(beds),
        baths=float(baths),
        sqft=float(sqft),
        taxes=float(taxes),
        status=status,
        days_on_market=int(days_on_market),
        notes=notes,
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
        st.subheader("Wholesale Numbers")
        wholesale = result["wholesale"]
        st.write({
            "Buyer target": money(wholesale["buyer_target"]),
            "Target offer low": money(wholesale["target_offer_low"]),
            "Target offer high": money(wholesale["target_offer_high"]),
            "Max offer": money(wholesale["max_offer"]),
            "Estimated fee at asking": money(wholesale["estimated_fee_at_ask"]),
        })

    with c2:
        st.subheader("Slow Flip Numbers")
        slow = result["slow_flip"]
        st.write({
            "Resale to slow flipper": money(slow["resale_to_slow_flipper"]),
            "Repair adjustment": money(slow["repair_credit"]),
            "Target offer low": money(slow["target_offer_low"]),
            "Target offer high": money(slow["target_offer_high"]),
            "Max offer": money(slow["max_offer"]),
            "Estimated fee at asking": money(slow["estimated_fee_at_ask"]),
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
            "address": address,
            "market": market,
            "lead_type": lead_type,
            "grade": result["grade"],
            "best_exit": result["best_exit"],
            "asking_price": asking_price,
            "arv": arv,
            "repairs": repairs,
            "rent": rent,
            "target_offer_low": best["target_offer_low"],
            "target_offer_high": best["target_offer_high"],
            "max_offer": best["max_offer"],
            "estimated_fee_at_ask": best["estimated_fee_at_ask"],
            "notes": notes,
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
    st.info("Enter the property numbers, then click Analyze Deal.")
