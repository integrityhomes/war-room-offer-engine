from __future__ import annotations


def render_buyer_outreach_section(st, buyer_concern_options) -> None:
    st.subheader("Buyer Outreach / Dispo Test")
    with st.container(border=True):
        bo1, bo2, bo3 = st.columns(3)
        with bo1:
            st.selectbox(
                "Outreach status",
                ["Not sent", "Sent to buyers", "Buyers responded", "Buyer interest confirmed", "No buyer interest", "Not applicable"],
                key="buyer_outreach_status",
            )
            st.number_input("Number of buyers contacted", min_value=0, step=1, key="buyers_contacted_count")
        with bo2:
            st.selectbox(
                "Buyer response level",
                ["Strong interest", "Some interest", "Weak interest", "No interest", "Not sent yet"],
                key="buyer_response_level",
            )
            st.selectbox(
                "Buyer target price confirmed?",
                ["Yes", "No", "Pending", "Not applicable"],
                key="buyer_target_price_confirmed",
            )
        with bo3:
            st.number_input("Confirmed buyer target price", min_value=0, step=1000, key="confirmed_buyer_target_price")
        st.text_area("Best buyer feedback", height=90, key="best_buyer_feedback")
        st.multiselect("Buyer concerns", buyer_concern_options, key="buyer_concerns")
