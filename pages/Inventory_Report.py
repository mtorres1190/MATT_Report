import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime

from scripts.process_matt import color_map

# ======================================================================================
# PAGE SETUP
# ======================================================================================

st.set_page_config(page_title="Inventory Report", layout="wide")
st.title("Inventory Report")

st.markdown("""
<style>

/* Multiselect styling */
.stMultiSelect [data-baseweb="tag"] {
    background-color: #1f77b4 !important;
}

/* Allow sidebar popovers to overflow naturally */
section[data-testid="stSidebar"] {
    overflow-y: auto !important;
    overflow-x: visible !important;
}

section[data-testid="stSidebar"] > div {
    overflow-y: auto !important;
    overflow-x: visible !important;
}

div[data-baseweb="popover"] {
    z-index: 9999 !important;
}

</style>
""", unsafe_allow_html=True)

# ======================================================================================
# DATA VALIDATION
# ======================================================================================

if 'matt_processed' not in st.session_state:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed'].copy()

# Safeguard HS_TYPE_LABEL
if 'HS_TYPE_LABEL' not in df.columns and 'HS_TYPE' in df.columns:
    status_map = {
        'B': 'Backlog',
        'S': 'Unsold',
        'Z': 'Closed',
        'M': 'Model'
    }
    df['HS_TYPE_LABEL'] = df['HS_TYPE'].map(status_map).fillna(df['HS_TYPE'])

# Safeguard Age + Age_Bucket
if 'Age_Bucket' not in df.columns and 'EST_DELIVERABLE_DATE' in df.columns:
    today = pd.Timestamp.today().normalize()
    df['Age'] = (pd.to_datetime(df['EST_DELIVERABLE_DATE'], errors='coerce') - today).dt.days

    def categorize_age(days):
        if pd.isna(days):
            return None
        if days < 0:
            return 'Black'
        elif 0 <= days <= 30:
            return 'Red'
        elif 31 <= days <= 60:
            return 'Yellow'
        else:
            return 'Green'

    df['Age_Bucket'] = df['Age'].apply(categorize_age)

# ======================================================================================
# SIDEBAR FILTERS
# ======================================================================================

with st.sidebar:
    st.header("Filters")

    # COE Range
    coe_range = st.date_input(
        "COE Date Range",
        value=(datetime.date(2026, 1, 1), datetime.date(2026, 6, 30)),
        key="inv_est_coe_range"
    )

    if not isinstance(coe_range, tuple) or len(coe_range) != 2:
        st.error("Invalid date range selection.")
        st.stop()

    est_coe_start = pd.to_datetime(coe_range[0])
    est_coe_end = pd.to_datetime(coe_range[1])

    # Aggregation Level
    agg_level = st.selectbox(
        "Aggregation Level",
        ["Hub", "Community Name", "Plan Name"],
        index=0,
        key="inv_agg_level"
    )

    # Date Filter
    df_date = df.loc[
        df['EST_COE_DATE'].notna() &
        (df['EST_COE_DATE'] >= est_coe_start) &
        (df['EST_COE_DATE'] <= est_coe_end)
    ].copy()

    # Homesite Status
    status_options = sorted(df_date['HS_TYPE_LABEL'].dropna().unique())
    selected_statuses = st.multiselect("Homesite Status", options=status_options)
    statuses = selected_statuses if selected_statuses else status_options
    df_status = df_date[df_date['HS_TYPE_LABEL'].isin(statuses)].copy()

    # 🔥 NEW: Inventory Age Filter
    if 'Age_Bucket' in df_status.columns:
        age_options = ["Green", "Yellow", "Red", "Black"]
        available_age_options = sorted(
            df_status['Age_Bucket'].dropna().unique(),
            key=lambda x: age_options.index(x) if x in age_options else 999
        )
        selected_age = st.multiselect(
            "Inventory Age",
            options=available_age_options,
            default=[]
        )
        ages = selected_age if selected_age else available_age_options
        df_age = df_status[df_status['Age_Bucket'].isin(ages)].copy()
    else:
        df_age = df_status.copy()

    # Hub
    hub_options = sorted(df_age['Hub'].dropna().unique())
    selected_hubs = st.multiselect("Hub", options=hub_options)
    hubs = selected_hubs if selected_hubs else hub_options
    df_hub = df_age[df_age['Hub'].isin(hubs)]

    # Community
    community_options = sorted(df_hub['Community Name'].dropna().unique())
    selected_communities = st.multiselect("Community Name", options=community_options)
    communities = selected_communities if selected_communities else community_options
    df_comm = df_hub[df_hub['Community Name'].isin(communities)]

    # Collection
    if 'Collection' in df_comm.columns:
        collection_options = sorted(df_comm['Collection'].dropna().unique())
        selected_collections = st.multiselect("Collection", options=collection_options)
        collections = selected_collections if selected_collections else collection_options
        df_coll = df_comm[df_comm['Collection'].isin(collections)]
    else:
        df_coll = df_comm.copy()

    # Plan
    plan_options = sorted(df_coll['Plan Name'].dropna().unique())
    selected_plans = st.multiselect("Plan Name", options=plan_options)
    plans = selected_plans if selected_plans else plan_options

# ======================================================================================
# APPLY FINAL FILTERS
# ======================================================================================

filtered_df = df_coll.copy()
if agg_level == "Plan Name":
    filtered_df = filtered_df[filtered_df['Plan Name'].isin(plans)]

if filtered_df.empty:
    st.info("No rows match the current filter set.")
    st.stop()

# ======================================================================================
# MONTHLY SUMMARY PIVOT
# ======================================================================================

summary_df = filtered_df.copy()
summary_df['MonthYear'] = summary_df['EST_COE_DATE'].dt.to_period('M').astype(str)
summary_df['Status Label'] = summary_df['HS_TYPE_LABEL']

pivot = pd.pivot_table(
    summary_df,
    values='Plan Name',
    index='Status Label',
    columns='MonthYear',
    aggfunc='count',
    fill_value=0,
    margins=True,
    margins_name='Grand Total'
).rename_axis("Status")

# ------------------------------------------------------------------
# Custom Row Order for Monthly Summary
# ------------------------------------------------------------------

desired_order = [
    "Unsold",
    "Backlog",
    "Closed",
    "Model",
    "Grand Total"
]

# Keep only rows that actually exist in the pivot
existing_rows = [row for row in desired_order if row in pivot.index]

# Reorder pivot rows
pivot = pivot.reindex(existing_rows)

def color_rows(row):
    color = color_map.get(row.name, '')
    return [f'background-color: {color}40'] * len(row)

styled = pivot.style.format('{:,}').apply(color_rows, axis=1)

st.dataframe(styled, use_container_width=True)

# ======================================================================================
# INVENTORY STATUS CHART (Sorted)
# ======================================================================================

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
    total_counts = filtered_df.groupby(group_col).size().reset_index(name='Total')
    total_counts['Label'] = total_counts['Plan Name'] + " (" + total_counts['Community Name'] + ")"
else:
    chart_data = filtered_df.groupby([group_col, 'HS_TYPE_LABEL']).size().reset_index(name='Count')
    x_col = group_col
    total_counts = filtered_df.groupby(group_col).size().reset_index(name='Total')

total_counts = total_counts.sort_values('Total', ascending=False)
sorted_categories = total_counts[x_col].tolist()

fig = go.Figure()

for label in chart_data['HS_TYPE_LABEL'].unique():
    subset = chart_data[chart_data['HS_TYPE_LABEL'] == label]
    fig.add_trace(go.Bar(
        x=subset[x_col],
        y=subset['Count'],
        name=label,
        marker_color=color_map.get(label, None)
    ))

fig.update_layout(
    title=f"Inventory Status by {agg_level}",
    title_font=dict(size=20),
    xaxis=dict(title=agg_level, categoryorder='array', categoryarray=sorted_categories),
    yaxis_title="Number of Homesites",
    barmode='stack'
)

st.plotly_chart(fig, use_container_width=True)

# ======================================================================================
# INVENTORY AGE CHART
# ======================================================================================

unsold_df = filtered_df[filtered_df['HS_TYPE_LABEL'] == 'Unsold'].copy()

if not unsold_df.empty:

    if isinstance(group_col, list):
        age_data = unsold_df.groupby(group_col + ['Age_Bucket']).size().reset_index(name='Count')
        age_data['Label'] = age_data['Plan Name'] + " (" + age_data['Community Name'] + ")"
        x_col = 'Label'
    else:
        age_data = unsold_df.groupby([group_col, 'Age_Bucket']).size().reset_index(name='Count')
        x_col = group_col

    bucket_order = ["Green", "Yellow", "Red", "Black"]
    age_data['Age_Bucket'] = pd.Categorical(age_data['Age_Bucket'], categories=bucket_order, ordered=True)

    fig2 = go.Figure()

    for bucket in bucket_order:
        subset = age_data[age_data['Age_Bucket'] == bucket]
        if not subset.empty:
            fig2.add_trace(go.Bar(
                x=subset[x_col],
                y=subset['Count'],
                name=bucket,
                marker_color=color_map.get(bucket, None)
            ))

    fig2.update_layout(
        title=f"Inventory Age by {agg_level}",
        title_font=dict(size=20),
        xaxis=dict(title=agg_level, categoryorder='array', categoryarray=sorted_categories),
        yaxis_title="Number of Homesites",
        barmode='stack'
    )

    st.plotly_chart(fig2, use_container_width=True)
