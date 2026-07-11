from __future__ import annotations


def render_buyer_demand_section(st, exit_obstacle_options) -> None:
    st.subheader("Buyer Demand / Exit Confidence")
    with st.container(border=True):
        bd1, bd2, bd3, bd4 = st.columns(4)
        with bd1:
            st.selectbox(
                "Buyer demand confidence",
                ["Strong buyer demand", "Normal buyer demand", "Limited buyer demand", "Unknown"],
                key="buyer_demand_confidence",
            )
            st.selectbox(
                "Wholesale buyer list strength",
                ["Strong active buyers", "Some buyers", "Weak buyer list", "No buyer list yet", "Not applicable"],
                key="wholesale_buyer_list_strength",
            )
        with bd2:
            st.selectbox(
                "Slow flip / owner-finance buyer demand",
                ["Strong", "Normal", "Weak", "Unknown", "Not applicable"],
                key="slow_flip_buyer_demand",
            )
            st.selectbox(
                "Rental demand confidence",
                ["Strong verified rents", "Some rent comps", "Weak rent comps", "Conflicting data", "Unknown"],
                key="rental_demand_confidence",
            )
        with bd3:
            st.selectbox(
                "Exit strategy confidence",
                ["Strong", "Moderate", "Weak", "Unknown"],
                key="exit_strategy_confidence",
            )
            st.selectbox(
                "Property marketability",
                ["Easy to sell", "Normal", "Limited buyer pool", "Very limited buyer pool"],
                key="property_marketability",
            )
        with bd4:
            st.selectbox(
                "Buyer proof",
                ["Buyer already interested", "Buyer list confirms demand", "Similar deals sold recently", "No buyer proof yet", "Unknown"],
                key="buyer_proof",
            )
        st.multiselect("Exit obstacles", exit_obstacle_options, key="exit_obstacles")
