from __future__ import annotations


def render_deal_protection_section(st, ui) -> dict:
    build_deal_protection_payload = ui.build_deal_protection_payload
    default_address_sharing_level = ui.default_address_sharing_level
    default_listing_source_sharing_level = ui.default_listing_source_sharing_level

    st.subheader("Deal Protection Mode")
    status_options = ["Not under contract", "Offer sent", "Verbal agreement", "Under contract", "Closed / owned"]
    protect_options = ["Yes", "No"]
    address_options = ["Hide exact address", "City only", "County only", "Full address allowed"]
    listing_options = ["Hide listing/source links", "Internal only", "Full links allowed"]
    message_options = ["Pre-contract demand check", "Under-contract buyer blast", "Internal team only"]

    previous_status = st.session_state.get("_last_contract_status_for_defaults")
    current_status = st.session_state.get("contract_status", "Not under contract")
    if previous_status != current_status:
        previous_address_default = default_address_sharing_level(previous_status or "Not under contract")
        previous_listing_default = default_listing_source_sharing_level(previous_status or "Not under contract")
        if st.session_state.get("address_sharing_level") == previous_address_default:
            st.session_state["address_sharing_level"] = default_address_sharing_level(current_status)
        if st.session_state.get("listing_source_sharing_level") == previous_listing_default:
            st.session_state["listing_source_sharing_level"] = default_listing_source_sharing_level(current_status)
        st.session_state["_last_contract_status_for_defaults"] = current_status

    c1, c2, c3 = st.columns(3)
    with c1:
        st.selectbox("Contract Status", status_options, key="contract_status")
        st.selectbox("Protect deal details before contract?", protect_options, key="deal_protection_mode")
    with c2:
        st.selectbox("Address sharing level", address_options, key="address_sharing_level")
        st.selectbox("Listing/source sharing level", listing_options, key="listing_source_sharing_level")
    with c3:
        st.selectbox("Buyer message type", message_options, key="buyer_message_type")
        st.text_input("Buyer response deadline", key="buyer_deadline")

    st.text_area(
        "Access / photos note for buyer package",
        height=80,
        key="buyer_access_notes",
        placeholder="Example: Photos available after contract. Avoid sharing house number/street-sign photos before contract.",
    )

    context = {
        "contract_status": st.session_state.get("contract_status"),
        "deal_protection_mode": st.session_state.get("deal_protection_mode"),
        "address_sharing_level": st.session_state.get("address_sharing_level"),
        "listing_source_sharing_level": st.session_state.get("listing_source_sharing_level"),
        "buyer_message_type": st.session_state.get("buyer_message_type"),
        "address": st.session_state.get("address", ""),
        "city": st.session_state.get("city", ""),
        "county": st.session_state.get("county", ""),
        "state": st.session_state.get("state", ""),
        "market": st.session_state.get("market", ""),
        "beds": st.session_state.get("beds", 0),
        "baths": st.session_state.get("baths", 0),
        "arv": st.session_state.get("arv", 0),
        "repairs": st.session_state.get("repairs", 0),
        "asking_price": st.session_state.get("contract_price", 0) or st.session_state.get("asking_price", 0),
        "listing_url": st.session_state.get("listing_url", ""),
        "notes": st.session_state.get("notes", ""),
        "repair_notes": st.session_state.get("repair_notes", "") + " " + st.session_state.get("manual_repair_notes", ""),
        "access_notes": st.session_state.get("buyer_access_notes", ""),
        "buyer_deadline": st.session_state.get("buyer_deadline", ""),
        "mold_verified": st.session_state.get("mold_verified") in ["Yes - inspector verified", "Yes - seller disclosed"],
    }
    payload = build_deal_protection_payload(context)
    for key, value in payload.items():
        st.session_state[key if key != "warning" else "deal_protection_warning"] = value

    st.markdown("### Protected Buyer Message")
    with st.container(border=True):
        st.write(f"Message type: {payload['buyer_message_type']}")
        st.write("Protected fields hidden: " + (", ".join(payload["protected_fields_hidden"]) if payload["protected_fields_hidden"] else "None"))
        if payload.get("warning"):
            st.warning(payload["warning"])
        st.text_area("Safe buyer message", value=payload["protected_buyer_message"], height=150)
    return payload
