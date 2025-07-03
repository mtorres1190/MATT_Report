import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import os

from scripts.process_matt import color_map

# --- Set up the Streamlit page ---
st.set_page_config(page_title="Inventory Report", layout="wide")
st.title("Inventory Report")

# --- Apply custom styles for filter tags ---
st.markdown("""
    <style>
        .stMultiSelect [data-baseweb=\"tag\"] {
            background-color: #1f77b4 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- Check for uploaded MATT data ---
uploaded = 'matt_processed' in st.session_state
if not uploaded:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed']

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")

    # COE Date Range filter
    coe_range = st.date_input(
        "COE Date Range",
        value=(datetime.date(2025, 6, 1), datetime.date(2025, 8, 31)),
        key="inv_est_coe_range"
    )
    if isinstance(coe_range, tuple) and len(coe_range) == 2:
        est_coe_start = pd.to_datetime(coe_range[0])
        est_coe_end = pd.to_datetime(coe_range[1])
    else:
        st.error("Invalid date range selection.")
        st.stop()

    # Aggregation level (Hub, Community Name, Plan Name)
    agg_level = st.selectbox("Aggregation Level", ["Hub", "Community Name", "Plan Name"], index=0, key="inv_agg_level")

    # Hub filter
    all_hubs = sorted(df['Hub'].dropna().unique())
    selected_hubs = st.multiselect("Hub", options=all_hubs, key="inv_hubs")
    hubs = all_hubs if not selected_hubs else selected_hubs

    # Community filter
    community_options = sorted(df[df['Hub'].isin(hubs)]['Community Name'].dropna().unique())
    selected_communities = st.multiselect("Community Name", options=community_options, key="inv_communities")
    communities = community_options if not selected_communities else selected_communities

    # Collection filter
    collection_options = sorted(df[df['Hub'].isin(hubs) & df['Community Name'].isin(communities)]['Collection'].dropna().unique())
    selected_collections = st.multiselect("Collection", options=collection_options, key="inv_collections")
    collections = collection_options if not selected_collections else selected_collections

    # Plan filter (only used if Plan Name is selected)
    plan_options = sorted(df[df['Hub'].isin(hubs) & df['Community Name'].isin(communities) & df['Collection'].isin(collections)]['Plan Name'].dropna().unique())
    selected_plans = st.multiselect("Plan Name", options=plan_options, key="inv_plans")
    plans = plan_options if not selected_plans else selected_plans

    # Homesite status filter
    all_statuses = sorted(df['HS_TYPE_LABEL'].dropna().unique())
    selected_statuses = st.multiselect("Homesite Status", options=all_statuses, key="inv_statuses")
    if not selected_statuses:
        selected_statuses = all_statuses

# --- Apply all filters ---
filtered_df = df[
    (df['EST_COE_DATE'] >= est_coe_start) &
    (df['EST_COE_DATE'] <= est_coe_end) &
    (df['HS_TYPE_LABEL'].isin(selected_statuses)) &
    (df['Hub'].isin(hubs)) &
    (df['Community Name'].isin(communities)) &
    (df['Collection'].isin(collections))
]

if agg_level == "Plan Name":
    filtered_df = filtered_df[filtered_df['Plan Name'].isin(plans)]

# --- Create monthly summary pivot table ---
summary_df = filtered_df.copy()
summary_df['MonthYear'] = summary_df['EST_COE_DATE'].dt.to_period('M').astype(str)
summary_df['MonthYearOrder'] = pd.to_datetime(summary_df['MonthYear'], format='%Y-%m')
summary_df['Status Label'] = summary_df['HS_TYPE_LABEL']

pivot = pd.pivot_table(
    summary_df,
    values='COMMUNITY',
    index='Status Label',
    columns='MonthYear',
    aggfunc='count',
    fill_value=0,
    margins=True,
    margins_name='Grand Total'
).rename_axis("Status")

# --- Order and format month columns ---
ordered_months = summary_df[['MonthYear', 'MonthYearOrder']].drop_duplicates().sort_values('MonthYearOrder')['MonthYear'].tolist()
if 'Grand Total' in pivot.columns:
    ordered_months += ['Grand Total']
renamed_columns = {col: pd.to_datetime(col).strftime('%b-%Y') for col in pivot.columns if col != 'Grand Total'}
pivot.rename(columns=renamed_columns, inplace=True)
pivot = pivot[[renamed_columns.get(col, col) for col in ordered_months]]

# --- Apply color styling to pivot rows ---
def color_rows(row):
    color = color_map.get(row.name, '')
    return [f'background-color: {color}80'] * len(row)

styled = pivot.style.format('{:,}').apply(color_rows, axis=1)
st.dataframe(styled, use_container_width=True)

# --- Generate inventory bar chart ---
if agg_level == "Hub":
    group_col = "Hub"
elif agg_level == "Community Name":
    group_col = "Community Name"
else:
    group_col = ["Community Name", "Plan Name"]

if isinstance(group_col, list):
    chart_data = filtered_df.groupby(group_col + ['HS_TYPE_LABEL']).size().reset_index(name='Count')
    chart_data['Label'] = chart_data['Plan Name'] + " (" + chart_data['Community Name'] + ")"
    x_col = 'Label'
else:
    chart_data = filtered_df.groupby([group_col, 'HS_TYPE_LABEL']).size().reset_index(name='Count')
    x_col = group_col

fig = go.Figure()
for label in chart_data['HS_TYPE_LABEL'].unique():
    subset = chart_data[chart_data['HS_TYPE_LABEL'] == label]
    fig.add_trace(go.Bar(
        x=subset[x_col],
        y=subset['Count'],
        name=label,
        customdata=subset[[x_col, 'Count']].values,
        hovertemplate=f"<b>%{{customdata[0]}}</b><br>Homesite Status: {label}<br>Count: %{{customdata[1]:,}}<extra></extra>",
        marker_color=color_map.get(label, None)
    ))

fig.update_layout(
    title=f"Inventory by {agg_level} and Homesite Status",
    title_font=dict(size=20),
    xaxis_title=agg_level,
    yaxis_title="Number of Homesites",
    legend_title="Homesite Status",
    barmode='stack',
    xaxis={'categoryorder': 'total descending'},
    margin=dict(t=50, l=20, r=20, b=20)
)

st.plotly_chart(fig, use_container_width=True)







