import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
from scripts.process_matt import compute_snapshot_unsold_inventory

st.set_page_config(page_title="Sales Report", layout="wide")
st.title("Sales Report")

st.markdown("""
    <style>
        .stMultiSelect [data-baseweb=\"tag\"] {
            background-color: #1f77b4 !important;
        }
    </style>
""", unsafe_allow_html=True)

uploaded = 'matt_processed' in st.session_state
if not uploaded:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed']
df = df.copy()

# Sidebar filters
with st.sidebar:
    st.header("Filters")

    est_coe_range = st.date_input("COE Date Range", value=(datetime.date(2025, 6, 1), datetime.date(2025, 8, 31)), key="sales_est_coe_range")
    if isinstance(est_coe_range, tuple) and len(est_coe_range) == 2:
        est_coe_start, est_coe_end = pd.to_datetime(est_coe_range[0]), pd.to_datetime(est_coe_range[1])
    else:
        st.error("Please select a valid COE date range.")
        st.stop()

    snapshot_date = st.date_input("Snapshot Date", value=datetime.date.today() - datetime.timedelta(days=1), key="sales_snapshot_date")

    all_weeks = ["Snapshot", "LW", "L2W", "L3W"]
    selected_weeks = st.multiselect(
        "Select Snapshot Week(s)",
        options=all_weeks,
        default=[],
        key="sales_selected_weeks"
    )
    selected_weeks = all_weeks if not selected_weeks else selected_weeks

    agg_level = st.selectbox("Aggregation Level", ["Hub", "Community Name"], index=0, key="sales_agg_level")

    all_hubs = sorted(df['Hub'].dropna().unique())
    selected_hubs = st.multiselect("Hub", options=all_hubs, key="sales_hubs")
    hubs = all_hubs if not selected_hubs else selected_hubs

    all_communities = sorted(df['Community Name'].dropna().unique())
    selected_communities = st.multiselect("Community Name", options=all_communities, key="sales_communities")
    communities = all_communities if not selected_communities else selected_communities

# Filter data
df = df[(df['Hub'].isin(hubs)) & (df['Community Name'].isin(communities))]

# Snapshot dates
snapshot_map = {
    "Snapshot": pd.to_datetime(snapshot_date),
    "LW": pd.to_datetime(snapshot_date) - pd.Timedelta(days=7),
    "L2W": pd.to_datetime(snapshot_date) - pd.Timedelta(days=14),
    "L3W": pd.to_datetime(snapshot_date) - pd.Timedelta(days=21)
}

# Determine grouping column
group_col = 'Hub' if agg_level == 'Hub' else 'Community Name'

# Compute unsold data
results = []
all_groups = df[(df['EST_COE_DATE'] >= est_coe_start) & (df['EST_COE_DATE'] <= est_coe_end)][group_col].dropna().unique()

for label in selected_weeks:
    snap_date = snapshot_map.get(label)
    if snap_date is None:
        continue

    agg_df = compute_snapshot_unsold_inventory(df, group_col, snap_date, est_coe_start, est_coe_end, label)
    if agg_df.empty:
        continue

    filled_df = pd.DataFrame({group_col: all_groups})
    merged = filled_df.merge(agg_df, on=group_col, how='left')
    merged['Week'] = label
    merged['Unsold'] = merged['Unsold'].fillna(0)
    merged['Avg_Age'] = merged['Avg_Age'].fillna(0)

    if group_col == 'Community Name':
        merged = merged.merge(df[['Community Name', 'Hub']].drop_duplicates(), on='Community Name', how='left')

    results.append(merged)

if not results:
    st.warning("No matching unsold inventory data available for the selected filters.")
    st.stop()

viz_df = pd.concat(results)
viz_df['label'] = viz_df[group_col]
days_between_snapshot_and_end = (est_coe_end - pd.to_datetime(snapshot_date)).days
cmax_dynamic = max(60, days_between_snapshot_and_end)

fig = go.Figure()
fig.update_layout(
    template='plotly_white',
    hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial")
)

for week in ['L3W', 'L2W', 'LW', 'Snapshot']:
    week_df = viz_df[viz_df['Week'] == week].copy()
    if week_df.empty:
        continue
    marker_colors = week_df.apply(lambda row: 'grey' if row['Unsold'] == 0 else row['Avg_Age'], axis=1)
    week_labels = {'Snapshot': 'S', 'LW': '1', 'L2W': '2', 'L3W': '3'}
    text_labels = [week_labels.get(week, '')] * len(week_df)

    if group_col == 'Community Name':
        customdata = week_df[['Avg_Age', 'Community Name', 'Hub']]
        hovertemplate = (
            "<b>%{meta}</b><br>"
            "Hub: %{customdata[2]}<br>"
            "Community: %{customdata[1]}<br>"
            "Unsold: %{x}<br>"
            "Avg Age: %{customdata[0]:.1f} days<extra></extra>"
        )
    else:
        customdata = week_df[['Avg_Age', 'Hub']]
        hovertemplate = (
            "<b>%{meta}</b><br>"
            "Hub: %{customdata[1]}<br>"
            "Unsold: %{x}<br>"
            "Avg Age: %{customdata[0]:.1f} days<extra></extra>"
        )

    fig.add_trace(go.Scatter(
        x=week_df['Unsold'],
        y=week_df['label'],
        mode='markers+text',
        marker=dict(
            size=16,
            color=marker_colors,
            colorscale=[[0.0, 'red'], [0.5, 'yellow'], [1.0, 'green']],
            cmin=0,
            cmax=cmax_dynamic,
            colorbar=dict(
                title='Avg Age (days)',
                tickvals=[0, 30, 60, days_between_snapshot_and_end],
                ticktext=['0 Days Before', '30 Days Before', '60 Days Before', f'— {days_between_snapshot_and_end} Days to COE End'],
                tickmode='array'
            ),
            showscale=True,
            line=dict(color=['black' if x == 0 else 'rgba(0,0,0,0)' for x in week_df['Unsold']], width=1)
        ),
        showlegend=False,
        customdata=customdata,
        meta=week,
        hovertemplate=hovertemplate,
        text=text_labels,
        textfont=dict(color='white', size=14, family='Arial Black'),
        textposition='middle center'
    ))

fig.update_layout(
    title=dict(
        text="<b>Weekly Unsold Inventory Snapshots</b>",
        font=dict(size=22),
        x=0.5,
        xanchor='center'
    ),
    xaxis_title=dict(text="<b>Unsold Homes</b>", font=dict(size=14)),
    xaxis=dict(
        range=[-0.75, max(viz_df['Unsold'].max(), 10) + 1],
        fixedrange=True,
        showgrid=True,
        gridcolor='lightgrey',
        gridwidth=1,
        zeroline=False
    ),
    yaxis_title=dict(text=f"<b>{group_col}</b>", font=dict(size=14)),
    yaxis=dict(
        categoryorder='array',
        categoryarray=sorted(viz_df['label'].unique(), reverse=True),
        tickfont=dict(size=18 if agg_level == 'Hub' else 14)
    ),
    height=720,
    plot_bgcolor="white",
    margin=dict(t=60, b=60, l=80, r=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)

st.plotly_chart(fig, use_container_width=True)

# Community Table
snapshot_only = viz_df[viz_df['Week'] == 'Snapshot'][[group_col, 'Unsold']]
community_snapshot = df[(df['EST_COE_DATE'] >= est_coe_start) & (df['EST_COE_DATE'] <= est_coe_end)]

sold_counts = community_snapshot[(community_snapshot['SALE_DATE'].notna()) & (community_snapshot['SALE_DATE'] >= snapshot_map['LW']) & (community_snapshot['SALE_DATE'] < snapshot_map['Snapshot'])].groupby(group_col).size().reset_index(name='Sold')

if group_col == 'Community Name':
    table_df = community_snapshot[['Hub', 'Community Name']].drop_duplicates()
    table_df = table_df.merge(snapshot_only, left_on='Community Name', right_on='Community Name', how='left')
    table_df = table_df.merge(sold_counts, on='Community Name', how='left')
else:
    table_df = community_snapshot[['Hub']].drop_duplicates()
    table_df['Community Name'] = ''
    table_df = table_df.merge(snapshot_only, left_on='Hub', right_on='Hub', how='left')
    table_df = table_df.merge(sold_counts, on='Hub', how='left')

table_df['Unsold'] = table_df['Unsold'].fillna(0).astype(int)
table_df['Sold'] = table_df['Sold'].fillna(0).astype(int)
table_df = table_df.rename(columns={'Unsold': 'Unsold (Snapshot)', 'Sold': 'LW Sold'})
table_df = table_df.sort_values(by=['Hub', 'Community Name'])
table_df = table_df.merge(viz_df[viz_df['Week'] == 'Snapshot'][[group_col, 'Avg_Age']], on=group_col, how='left')
table_df['Avg Age (days)'] = table_df['Avg_Age'].fillna(0).round(1)
table_df = table_df.drop(columns=['Avg_Age'])

if not table_df.empty:
    st.subheader("Community Detail Table")
    st.dataframe(table_df, use_container_width=True, hide_index=True)





