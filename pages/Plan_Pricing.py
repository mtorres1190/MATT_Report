import pandas as pd
import numpy as np
import os
import datetime
import streamlit as st
import plotly.graph_objects as go
from scripts.process_matt import compute_plan_pricing

# --- Page setup ---
st.set_page_config(page_title="Plan Pricing", layout="wide")
st.title("Plan Pricing Chart")

# --- Styling for multi-select tags ---
st.markdown("""
    <style>
        .stMultiSelect [data-baseweb=\"tag\"] {
            background-color: #1f77b4 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- Ensure MATT data is loaded ---
uploaded = 'matt_processed' in st.session_state
if not uploaded:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed'].copy()

# --- Sidebar Filters ---
st.sidebar.header("Filters")

# Division filter
div_selection = st.sidebar.multiselect("Division", options=df['DIV_CODE_DESC'].dropna().unique(), default=["HB Dallas-Fort Worth"], key="div_selection")

# Sale date range filter
sale_date_range = st.sidebar.date_input("Sale Date Range", value=(datetime.date(2025, 4, 1), datetime.date.today() - datetime.timedelta(days=1)), key="sale_date_range")

# Aggregation level (Hub, Community Name, Plan Name)
agg_level = st.sidebar.selectbox("Aggregation Level", ["Hub", "Community Name", "Plan Name"], index=0, key="plan_agg_level")
group_col = agg_level

# Validate and convert date range
if isinstance(sale_date_range, tuple) and len(sale_date_range) == 2:
    start_date = pd.to_datetime(sale_date_range[0])
    end_date = pd.to_datetime(sale_date_range[1])
else:
    st.error("Invalid date range selection.")
    st.stop()

# Dynamic filter options

# Date filtered base
date_mask = df['SALE_DATE'].between(start_date, end_date)

# Hub filter
hub_options = sorted(df[date_mask]['Hub'].dropna().unique())
selected_hubs = st.sidebar.multiselect("Hub", options=hub_options, key="plan_hubs")
hubs = hub_options if not selected_hubs else selected_hubs

# Community filter
community_options = sorted(df[date_mask & df['Hub'].isin(hubs)]['Community Name'].dropna().unique())
selected_communities = st.sidebar.multiselect("Community Name", options=community_options, key="plan_communities")
communities = community_options if not selected_communities else selected_communities

# Collection filter
collection_options = sorted(df[date_mask & df['Hub'].isin(hubs) & df['Community Name'].isin(communities)]['Collection'].dropna().unique())
selected_collections = st.sidebar.multiselect("Collection", options=collection_options, key="plan_collections")
collections = collection_options if not selected_collections else selected_collections

# Plan filter
plan_options = sorted(df[date_mask & df['Hub'].isin(hubs) & df['Community Name'].isin(communities) & df['Collection'].isin(collections)]['Plan Name'].dropna().unique())
selected_plans = st.sidebar.multiselect("Plan Name", options=plan_options, key="plan_plans")
plans = plan_options if not selected_plans else selected_plans

# Investor sale filter
investor_filter = st.sidebar.selectbox("Investor Sale", options=["All", "Retail", "Investor"], index=1, key="investor_filter")

# --- Filter to only sold homes within date and group selections ---
sold_df = df[
    df['SALE_DATE'].between(start_date, end_date) &
    df['Hub'].isin(hubs) &
    df['Community Name'].isin(communities) &
    df['Collection'].isin(collections) &
    df['Plan Name'].isin(plans) &
    df['DIV_CODE_DESC'].isin(div_selection)
]

# --- Compute average pricing ---
if group_col == "Plan Name":
    pricing_df = compute_plan_pricing(sold_df, start_date, end_date, group_col=["Community Name", "Plan Name"])
else:
    pricing_df = compute_plan_pricing(sold_df, start_date, end_date, group_col=group_col)

if pricing_df.empty:
    st.warning("No sold home data available for the selected filters.")
    st.stop()

# --- Create scatter plot of pricing ---
if group_col == "Plan Name":
    x_labels = pricing_df["Plan Name"] + " (" + pricing_df["Community Name"] + ")"
else:
    x_labels = pricing_df[group_col]
x_positions = list(range(len(x_labels)))

fig = go.Figure()
for price_type in ["Avg Base Price", "Avg List Price", "Avg Net Revenue"]:
    fig.add_trace(go.Scatter(
        x=x_positions,
        y=pricing_df[price_type],
        mode='markers',
        name=price_type,
        marker=dict(size=10),
        hovertext=[
            f"{group_col}: {label}<br>{price_type}: ${value:,.0f}"
            for label, value in zip(x_labels, pricing_df[price_type])
        ],
        hoverinfo="text"
    ))

fig.update_layout(
    title=dict(text="Average Pricing by " + group_col, font=dict(size=24)),
    xaxis=dict(title=dict(text=group_col, font=dict(size=18)), tickmode='array', tickvals=x_positions, ticktext=x_labels, tickangle=45, tickfont=dict(size=14)),
    yaxis=dict(title=dict(text="Price", font=dict(size=18)), tickprefix="$", tickfont=dict(size=14)),
    legend=dict(font=dict(size=14), orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    margin=dict(t=60, b=100, l=60, r=40),
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# --- Pricing table output ---
st.markdown("### Pricing Data Table")

# Format table output by aggregation level
if group_col == "Hub":
    plan_counts = sold_df.groupby("Hub").size().reset_index(name="Sold Homes")
    formatted_df = pricing_df.merge(plan_counts, on="Hub", how="left")
    formatted_df["Community Name"] = ""
    formatted_df["Collection"] = ""
    formatted_df["Plan Name"] = ""
    formatted_df = formatted_df[["Hub", "Community Name", "Collection", "Plan Name"] + [col for col in pricing_df.columns if col not in ["Hub"]] + ["Sold Homes"]]

elif group_col == "Community Name":
    plan_counts = sold_df.groupby("Community Name").size().reset_index(name="Sold Homes")
    formatted_df = (
        sold_df[["Hub", "Community Name"]]
        .drop_duplicates()
        .merge(pricing_df, on="Community Name", how="right")
        .merge(plan_counts, on="Community Name", how="left")
    )
    formatted_df["Collection"] = ""
    formatted_df["Plan Name"] = ""
    formatted_df = formatted_df[["Hub", "Community Name", "Collection", "Plan Name"] + [col for col in pricing_df.columns if col not in ["Community Name"]] + ["Sold Homes"]]

else:
    plan_counts = sold_df.groupby(["Community Name", "Plan Name"]).size().reset_index(name="Sold Homes")
    formatted_df = (
        sold_df[["Hub", "Community Name", "Collection", "Plan Name"]]
        .drop_duplicates()
        .merge(pricing_df, on=["Community Name", "Plan Name"], how="right")
        .merge(plan_counts, on=["Community Name", "Plan Name"], how="left")
    )

# Format display columns
formatted_df["Avg SqFt"] = formatted_df["Avg SqFt"].round(0).astype(int).map("{:,}".format)
formatted_df["Avg Base Price"] = formatted_df["Avg Base Price"].map("${:,.0f}".format)
formatted_df["Avg List Price"] = formatted_df["Avg List Price"].map("${:,.0f}".format)
formatted_df["Avg Net Revenue"] = formatted_df["Avg Net Revenue"].map("${:,.0f}".format)

st.dataframe(
    formatted_df[["Hub", "Community Name", "Collection", "Plan Name", "Avg SqFt", "Sold Homes", "Avg Base Price", "Avg List Price", "Avg Net Revenue"]],
    use_container_width=True,
    hide_index=True
)





