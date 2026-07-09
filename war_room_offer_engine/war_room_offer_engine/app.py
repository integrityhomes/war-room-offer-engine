from __future__ import annotations

import pandas as pd
import streamlit as st

from rules import Assumptions, DealInput, analyze_deal, money
from ai_writer import build_ai_summary
from data_sources import fetch_all_sources, merge_results, get_secret
from repair_analyzer import analyze_repairs, repair_number_for_offer
from media_notes import generate_boots_on_ground_notes
st.set_page_config(page_title="War Room Offer Engine", page_icon="🏠", layout="wide")

FIELD_DEFAULTS = {
    "address": "",
    "market": "",
    "source_mode": "Zillow / Sheet Match",
    "lead_source": "Zillow / Apify",
    "lead_type": "Agent",
    "status": "Unknown",
    "asking_price": 35000,
    "contract_price": 0,
    "rent": 900,
    "occupancy": "Unknown",
    "livable": "Unknown",
    "beds": 3.0,
    "baths": 1.0,
    "sqft": 1000,
    "taxes": 0,
    "days_on_market": 0,
    "arv": 0,
    "rentcast_arv": 0,
    "sheet_arv": 0,
    "manual_arv_override": 0,
    "value_source": "Missing",
    "repairs": 0,
    "notes": "",
}

for key, value in FIELD_DEFAULTS.items():
    st.session_state.setdefault(key, value)
st.session_state.setdefault("last_source_results", [])
st.session_state.setdefault("last_auto_pull", {})


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def comp_price_values() -> list[float]:
    prices = []
    for idx in range(1, 6):
        price = safe_float(st.session_state.get(f"manual_comp_{idx}_price", 0))
        if price > 0:
            prices.append(price)
    return prices


def manual_comps_average() -> float:
    prices = comp_price_values()
    if not prices:
        return 0.0
    return sum(prices) / len(prices)


def resolve_value_source() -> tuple[float, str]:
    rentcast_arv = safe_float(st.session_state.get("rentcast_arv", 0))
    sheet_arv = safe_float(st.session_state.get("sheet_arv", 0))
    comps_arv = manual_comps_average()
    manual_override = safe_float(st.session_state.get("manual_arv_override", 0))

    if rentcast_arv > 0:
        return rentcast_arv, "RentCast"
    if sheet_arv > 0:
        return sheet_arv, "Zillow/Apify Sheet"
    if comps_arv > 0:
        return comps_arv, "Manual Comps"
    if manual_override > 0:
        return manual_override, "Manual Override"
    return 0.0, "Missing"


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
        "rentcast_arv": "rentcast_arv",
        "sheet_arv": "sheet_arv",
        "arv_source": "value_source",
    }
    for source_key, state_key in mapping.items():
        value = data.get(source_key)
        if value not in [None, "", 0]:
            if state_key in ["asking_price", "rent", "sqft", "taxes", "days_on_market", "arv", "rentcast_arv", "sheet_arv"]:
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

    resolved_arv, value_source = resolve_value_source()
    st.session_state["arv"] = int(resolved_arv) if resolved_arv > 0 else 0
    st.session_state["value_source"] = value_source


st.title("🏠 War Room Offer Engine")
st.caption("Universal Property Analyzer — Zillow/Sheet leads, MLS leads, off-market sellers, RentCast, and manual fallback in one place.")

with st.sidebar:
    st.header("Offer Assumptions")
    min_assignment_fee = st.number_input("Minimum assignment fee", min_value=0, value=10000, step=500)
    exception_assignment_fee = st.number_input("Exception assignment fee", min_value=0, value=5000, step=500)
    slow_flip_rent_multiple = st.slider("Slow flip resale multiple x rent", 20, 70, 45, 1)
    close_title_buffer = st.number_input("Close/title/safety buffer", min_value=0, value=1500, step=250)
    target_offer_discount = st.slider("Target offer discount from max", 0.50, 1.00, 0.85, 0.01)
    wholesale_buyer_percent_arv = st.slider("Wholesale buyer % of ARV", 0.40, 0.90, 0.70, 0.01)
    slow_flip_max_offer_cap = st.number_input("Normal slow flip max offer cap", min_value=0, value=32000, step=500, help="Bradley rule: 98% of slow-flip offers stay at or below this number. Use human review for exceptions.")
    slow_flip_first_offer_gap = st.number_input("Slow flip first offer below max", min_value=0, value=4000, step=500, help="Negotiation rule: do not start at max. Example: $32k max starts at $28k.")

    st.divider()
    st.header("Data Connections")
    st.caption("Green means ready. Missing connections do not stop manual analysis.")
    st.write("✅ RentCast API key" if get_secret("RENTCAST_API_KEY") else "⚠️ RentCast API key missing")
    st.write("✅ Zillow/Master Feed CSV" if get_secret("APIFY_ZILLOW_SHEET_CSV_URL") else "⚠️ Zillow/Master Feed CSV missing")
    st.write("✅ Lead sheet" if get_secret("LEADS_SHEET_CSV_URL") else "ℹ️ Lead sheet blank / optional")

assumptions = Assumptions(
    min_assignment_fee=float(min_assignment_fee),
    exception_assignment_fee=float(exception_assignment_fee),
    slow_flip_rent_multiple=float(slow_flip_rent_multiple),
    close_title_buffer=float(close_title_buffer),
    target_offer_discount=float(target_offer_discount),
    wholesale_buyer_percent_arv=float(wholesale_buyer_percent_arv),
    slow_flip_max_offer_cap=float(slow_flip_max_offer_cap),
    slow_flip_first_offer_gap=float(slow_flip_first_offer_gap),
)

st.subheader("1. Pull Property Data")

source_col1, source_col2 = st.columns([1, 1])
with source_col1:
    st.radio(
        "Source mode",
        ["Zillow / Sheet Match", "Off-Market / Manual"],
        key="source_mode",
        horizontal=True,
        help="Zillow / Sheet Match searches your published Master Feed. Off-Market / Manual skips the sheet and uses RentCast + your manual inputs.",
    )
with source_col2:
    st.selectbox(
        "Lead source",
        ["Zillow / Apify", "MLS / Agent", "Off-Market Seller", "Facebook", "Driving for Dollars", "Cold Text Reply", "Manual Entry", "Other"],
        key="lead_source",
    )

if st.session_state.get("source_mode") == "Off-Market / Manual":
    st.info("Off-market/manual mode skips the Zillow/Master Feed. Enter the seller ask manually if you have it. RentCast will still pull rent, beds, baths, sq ft, value, and facts.")
else:
    st.info("Zillow/Sheet mode uses RentCast plus your Master Feed CSV to pull asking price, Zillow link, status, and other listing data when the address matches.")

lookup_col1, lookup_col2 = st.columns([3, 1])
with lookup_col1:
    st.text_input("Property address", key="address", placeholder="123 Main St, Decatur IL 62522")
with lookup_col2:
    st.write("")
    st.write("")
    pull_data = st.button("Pull Data", type="primary", use_container_width=True)

if pull_data:
    include_listing_sheet = st.session_state.get("source_mode") == "Zillow / Sheet Match"
    spinner_text = "Pulling RentCast + Master Feed data..." if include_listing_sheet else "Pulling RentCast data only..."
    with st.spinner(spinner_text):
        results = fetch_all_sources(
            st.session_state["address"],
            beds=float(st.session_state.get("beds", 0) or 0),
            baths=float(st.session_state.get("baths", 0) or 0),
            sqft=float(st.session_state.get("sqft", 0) or 0),
            include_listing_sheet=include_listing_sheet,
            
        )
        merged = merge_results(results)
        st.session_state["last_source_results"] = results
        st.session_state["last_auto_pull"] = merged
        update_state_from_auto_pull(merged)

        good_sources = []
        for item in results:
            if isinstance(item, dict):
                if item.get("found") or item.get("ok"):
                    good_sources.append(item.get("source", "Unknown"))
            else:
                if getattr(item, "ok", False) or getattr(item, "found", False):
                    good_sources.append(getattr(item, "source", "Unknown"))

        if good_sources:
            st.success("Pulled data from: " + ", ".join(good_sources))
        else:
            st.warning("No data pulled yet. Add Streamlit secrets or verify the address. Manual analysis still works.")

        with st.expander("Data pull results"):
            for result in results:
                if isinstance(result, dict):
                    source = result.get("source", "Unknown")
                    found = result.get("found") or result.get("ok")
                    message = result.get("notes") or result.get("message") or ""
                    data = result.get("data", None)
                else:
                    source = getattr(result, "source", "Unknown")
                    found = getattr(result, "ok", False) or getattr(result, "found", False)
                    message = getattr(result, "message", "") or getattr(result, "notes", "")
                    data = getattr(result, "data", None)

                if found:
                    st.success(f"{source}: {message}")
                    if data:
                        st.write(data)
                else:
                    st.info(f"{source}: {message}") 

       
st.caption("Works for Zillow, MLS, agent leads, and off-market sellers. Slow Flip uses rent/livability; ARV and repairs are reference unless you switch to Wholesale/Auto.")

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
    st.number_input("Contract / Buy Price", min_value=0, step=1000, key="contract_price")
    st.number_input("Rent estimate", min_value=0, step=25, key="rent")
    st.selectbox("Occupancy", ["Unknown", "Vacant", "Tenant occupied", "Owner occupied"], key="occupancy")
    st.selectbox("Livable now?", ["Unknown", "Yes", "No"], key="livable")

with col3:
    st.number_input("Beds", min_value=0.0, step=0.5, key="beds")
    st.number_input("Baths", min_value=0.0, step=0.5, key="baths")
    st.number_input("Sq ft", min_value=0, step=50, key="sqft")
    st.number_input("Annual taxes", min_value=0, step=100, key="taxes")
    st.subheader("3. Repair / Condition Analyzer")
    st.caption(
        "Uses investor repair pricing by selected market. Illinois and Virginia active. "
        "Upload photos/videos and add boots-on-ground notes. "
        "This version prices the repair scope from the notes and uploaded media count. "
        "Full AI video frame review and audio transcription will be added next."
    )

    repair_market = st.selectbox(
        "Repair pricing market",
        [
            "Central IL",
            "Downstate IL",
            "Metro East IL",
            "Northern IL Non-Chicago",
            "Southside VA",
            "Southwest VA",
            "Roanoke / Lynchburg VA",
            "Richmond / Petersburg VA",
            "Hampton Roads / Tidewater VA",
            "Shenandoah Valley VA",
            "Charlottesville / Central VA",
            "Fredericksburg / Northern Neck VA",
            "Eastern Shore VA",
            "Northern VA",
        ],
        index=0,
        key="repair_market",
    )

    r2, r3 = st.columns(2)

    with r2:
        repair_level = st.selectbox(
            "Repair finish level",
            ["Investor Basic", "Rental Ready", "Retail Ready"],
            index=1,
            key="repair_level",
        )

    with r3:
        repair_contingency = st.number_input(
            "Repair contingency %",
            min_value=0,
            max_value=50,
            value=12,
            step=1,
            key="repair_contingency",
        )
    uploaded_repair_files = st.file_uploader(
        "Upload property photos or boots-on-ground walkthrough video",
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "avi"],
        accept_multiple_files=True,
        key="repair_media_files",
    )
    media_files_for_notes = uploaded_repair_files or []

    photo_files_for_notes = [
        f for f in media_files_for_notes
        if str(getattr(f, "name", "")).lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    ]

    video_files_for_notes = [
        f for f in media_files_for_notes
        if str(getattr(f, "name", "")).lower().endswith((".mp4", ".mov", ".m4v", ".avi"))
    ]

    selected_video_for_notes = video_files_for_notes[0] if video_files_for_notes else None

    if st.button("Generate boots-on-ground notes from media", type="secondary"):
        if not photo_files_for_notes and selected_video_for_notes is None:
            st.warning("Upload at least one photo or video first.")
        else:
            with st.spinner("Reviewing uploaded photos/video frames and writing boots-on-ground notes..."):
                generated_notes = generate_boots_on_ground_notes(
                    photo_files_for_notes,
                    selected_video_for_notes,
                )

            st.session_state["repair_notes"] = generated_notes
            st.success("Boots-on-ground notes created. Review them below, then click Generate Repair Estimate.") 
    repair_notes = st.text_area(
        "Boots-on-ground repair notes",
        height=140,
        key="repair_notes",
        placeholder=(
            "Example: Roof looks old, kitchen needs cabinets, bathroom floor is soft, "
            "furnace missing, water heater old, windows damaged, trash out needed."
        ),
    )

    generate_repair_estimate = st.button("Generate Repair Estimate", type="secondary")

    if generate_repair_estimate:
        repair_analysis = analyze_repairs(
            notes=st.session_state.get("repair_notes", ""),
            sqft=float(st.session_state.get("sqft", 0) or 1000),
            baths=float(st.session_state.get("baths", 0) or 1),
            uploaded_files=uploaded_repair_files,
            market=st.session_state.get("repair_market", "Central IL"),
            repair_level=st.session_state.get("repair_level", "Rental Ready"),
            contingency_pct=float(st.session_state.get("repair_contingency", 12) or 0) / 100,
        )

        st.session_state["repair_analysis"] = repair_analysis
        st.session_state["recommended_repairs_from_analyzer"] = repair_number_for_offer(repair_analysis)

    if st.session_state.get("repair_analysis"):
        repair_analysis = st.session_state["repair_analysis"]
        estimate = repair_analysis.get("estimate", {})

        st.markdown("#### Repair Estimate Result")

        e1, e2, e3, e4 = st.columns(4)

        with e1:
            st.metric("Low Repairs", money(estimate.get("total_low", 0)))

        with e2:
            st.metric("Likely Repairs", money(estimate.get("total_likely", 0)))

        with e3:
            st.metric("High Repairs", money(estimate.get("total_high", 0)))

        with e4:
            st.metric("Use In Offer", money(repair_analysis.get("recommended_repair_number", 0)))

        st.info(f"Confidence: {repair_analysis.get('confidence', 'Low')}")

        if repair_analysis.get("red_flags"):
            st.error(
                "Red flags needing contractor quote: "
                + ", ".join(repair_analysis.get("red_flags", []))
            )

        line_items = estimate.get("line_items", [])

        if line_items:
            st.dataframe(
                pd.DataFrame(line_items)[
                    ["category", "label", "quantity", "unit", "low", "likely", "high", "notes"]
                ],
                use_container_width=True,
            )

        st.text_area(
            "Repair estimate summary",
            value=repair_analysis.get("summary", ""),
            height=260,
        )

        if st.button("Use likely repair number in offer", type="primary"):
            st.session_state["repairs"] = int(repair_analysis.get("recommended_repair_number", 0) or 0)
            st.success("Repair number copied into Estimated repairs. Scroll down and confirm it before analyzing the deal.")
    st.markdown("### Manual Comp Entry Fallback")
    st.caption("Use this when RentCast cannot find value/comps. Enter 1 to 5 sold or listed comps.")

    comp_rows = []
    for idx in range(1, 6):
        with st.expander(f"Comparable Property {idx}", expanded=(idx == 1)):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.text_input("Address", key=f"manual_comp_{idx}_address")
            with c2:
                st.number_input(
                    "Sold/list price",
                    min_value=0,
                    step=1000,
                    key=f"manual_comp_{idx}_price",
                )

            c3, c4, c5 = st.columns(3)
            with c3:
                st.number_input("Beds", min_value=0.0, step=0.5, key=f"manual_comp_{idx}_beds")
            with c4:
                st.number_input("Baths", min_value=0.0, step=0.5, key=f"manual_comp_{idx}_baths")
            with c5:
                st.number_input("Sqft", min_value=0, step=50, key=f"manual_comp_{idx}_sqft")

            st.text_input("Condition", key=f"manual_comp_{idx}_condition")
            st.text_area("Notes", height=80, key=f"manual_comp_{idx}_notes")

        price = safe_float(st.session_state.get(f"manual_comp_{idx}_price", 0))
        if price > 0:
            comp_rows.append(
                {
                    "address": st.session_state.get(f"manual_comp_{idx}_address", ""),
                    "sold/list price": price,
                    "beds": st.session_state.get(f"manual_comp_{idx}_beds", 0),
                    "baths": st.session_state.get(f"manual_comp_{idx}_baths", 0),
                    "sqft": st.session_state.get(f"manual_comp_{idx}_sqft", 0),
                    "condition": st.session_state.get(f"manual_comp_{idx}_condition", ""),
                    "notes": st.session_state.get(f"manual_comp_{idx}_notes", ""),
                }
            )

    comps_average = manual_comps_average()
    st.metric("Average comp value", money(comps_average))
    if comp_rows:
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

    st.number_input(
        "Manual ARV override",
        min_value=0,
        step=1000,
        key="manual_arv_override",
        help="Fallback only. RentCast ARV, sheet ARV, then manual comps are used first.",
    )

    resolved_arv, value_source = resolve_value_source()
    st.session_state["arv"] = int(resolved_arv) if resolved_arv > 0 else 0
    st.session_state["value_source"] = value_source

    st.markdown("### Value / Wholesale Reference")
    st.caption(f"Value Source: {value_source}")

    v1, v2 = st.columns(2)

    with v1:
        st.number_input(
            "ARV / estimated resale value",
            min_value=0,
            step=1000,
            key="arv",
            help="Required on every deal. Auto-filled from RentCast, sheet ARV, manual comps, or manual override.",
        )

    with v2:
        st.number_input(
            "Estimated repairs",
            min_value=0,
            step=1000,
            key="repairs",
            help="Use $0 only when repairs are truly unknown or not needed for the slow-flip decision.",
        )

    if float(st.session_state.get("arv", 0) or 0) <= 0:
        st.warning("ARV is missing. Add ARV or manual comps before making a final offer.")

st.text_area("Seller/agent notes, condition, occupancy, motivation", height=120, key="notes")
st.caption(f"Current source: {st.session_state.get('source_mode')} / {st.session_state.get('lead_source')}")

analyze = st.button("Analyze Deal", type="primary")

if analyze:
    asking_price_value = float(st.session_state.get("asking_price", 0) or 0)
    contract_price_value = float(st.session_state.get("contract_price", 0) or 0)
    analysis_price = contract_price_value if contract_price_value > 0 else asking_price_value
    resolved_arv, value_source = resolve_value_source()
    st.session_state["value_source"] = value_source

    if resolved_arv <= 0:
        st.warning("ARV is missing. Add ARV or manual comps before making a final offer.")

    deal = DealInput(
        address=st.session_state["address"],
        market=st.session_state["market"],
        lead_type=st.session_state["lead_type"],
        exit_mode=exit_mode,
        asking_price=analysis_price,
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
        arv=float(resolved_arv or 0),
        repairs=float(st.session_state.get("repairs", 0) or 0),
    )

    result = analyze_deal(deal, assumptions)
    best = result["best"]

    st.divider()
    st.subheader("Decision")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Deal Grade", result["grade"])
    m2.metric("Best Exit", result["best_exit"])
    m3.metric("First Offer", money(best.get("offer_to_send", best.get("target_offer_low", 0))))
    m4.metric("Internal Max", money(best["max_offer"]))

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Slow Flip Numbers")
        slow = result["slow_flip"]
        st.write({
            "Resale to slow flipper": money(slow["resale_to_slow_flipper"]),
            "First offer to send": money(slow.get("offer_to_send", 0)),
            "Internal max offer": money(slow["max_offer"]),
            "Rent formula max before cap": money(slow.get("rent_formula_max_offer_before_cap", 0)),
            "Normal slow flip cap": money(slow.get("normal_slow_flip_cap", 0)),
            "Estimated fee at buy price": money(slow["estimated_fee_at_ask"]),
        })
        slow_resale_value = float(slow.get("resale_to_slow_flipper", 0) or 0)
        buyer_payment_support = float(st.session_state.get("rent", 0) or 0)
        annual_taxes_value = float(st.session_state.get("taxes", 0) or 0)

        if slow_resale_value >= 50000 and (buyer_payment_support < 1200 or annual_taxes_value > 1500):
            st.warning("$50k+ slow-flip resale warning: still show the resale price, but only push it hard if buyer payment support is about $1,200/month and taxes are low enough.")
    with c2:
        st.subheader("Value / Wholesale Reference")
        wholesale = result["wholesale"]
        st.write({
        "ARV / estimated value": money(resolved_arv),
        "Value Source": value_source,
        "Repairs": money(st.session_state.get("repairs", 0)),
        "Buyer target": money(wholesale["buyer_target"]),
        "Wholesale max offer": money(wholesale["max_offer"]),
        "Wholesale estimated fee at buy price": money(wholesale["estimated_fee_at_ask"])
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
            "source_mode": st.session_state.get("source_mode", ""),
            "lead_source": st.session_state.get("lead_source", ""),
            "lead_type": st.session_state["lead_type"],
            "exit_mode": exit_mode,
            "grade": result["grade"],
            "best_exit": result["best_exit"],
            "asking_price": st.session_state["asking_price"],
            "rent": st.session_state["rent"],
            "arv": resolved_arv,
            "value_source": value_source,
            "manual_comps_average": manual_comps_average(),
            "repairs": st.session_state.get("repairs", 0),
            "first_offer": best.get("offer_to_send", best.get("target_offer_low", 0)),
            "internal_max_offer": best["max_offer"],
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
