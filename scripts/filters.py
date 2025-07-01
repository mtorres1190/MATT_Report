import streamlit as st
import datetime

def apply_core_filters(df):
    st.sidebar.header("Filters")

    # Division
    st.session_state.setdefault("div_selection", ["HB Dallas-Fort Worth"])
    st.sidebar.multiselect(
        "Division",
        options=df['DIV_CODE_DESC'].dropna().unique(),
        default=st.session_state["div_selection"],
        key="div_selection"
    )

    # Sale Date Range
    st.session_state.setdefault("sale_date_range", (
        datetime.date(2024, 9, 1),
        datetime.date.today() - datetime.timedelta(days=1)
    ))
    st.sidebar.date_input(
        "Sale Date Range",
        value=st.session_state["sale_date_range"],
        key="sale_date_range"
    )

    # Investor Sale
    st.session_state.setdefault("investor_filter", "Retail")
    st.sidebar.selectbox(
        "Investor Sale",
        options=["All", "Retail", "Investor"],
        index=["All", "Retail", "Investor"].index(st.session_state["investor_filter"]),
        key="investor_filter"
    )

    # Realtor/Direct
    st.session_state.setdefault("cobroke_filter", "All")
    st.sidebar.selectbox(
        "Realtor/Direct",
        options=["All", "Realtor", "Direct"],
        index=["All", "Realtor", "Direct"].index(st.session_state["cobroke_filter"]),
        key="cobroke_filter"
    )

    # Return parsed values if needed by the page
    div_selection = st.session_state["div_selection"]
    investor_filter = st.session_state["investor_filter"]
    cobroke_filter = st.session_state["cobroke_filter"]
    start_date, end_date = st.session_state["sale_date_range"]

    return div_selection, investor_filter, cobroke_filter, start_date, end_date