import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
from scripts.process_matt import compute_snapshot_unsold_inventory

# --- Streamlit page config ---
st.set_page_config(page_title="Sales Report", layout="wide")
st.title("Sales Report")

# --- Custom style for selected filters ---
st.markdown("""
<style>
.stMultiSelect [data-baseweb=\"tag\"] {
    background-color: #1f77b4 !important;
}
</style>
""", unsafe_allow_html=True)

# --- Check for uploaded data ---
if 'matt_processed' not in st.session_state:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed'].copy()

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")
    est_coe_range = st.date_input("COE Date Range", (datetime.date(2025, 6, 1), datetime.date(2025, 8, 31)), key="sales_est_coe_range")
    if not (isinstance(est_coe_range, tuple) and len(est_coe_range) == 2):
        st.error("Please select a valid COE date range.")
        st.stop()
    est_coe_start, est_coe_end = pd.to_datetime(est_coe_range[0]), pd.to_datetime(est_coe_range[1])

    snapshot_date = st.date_input("Snapshot Date", datetime.date.today() - datetime.timedelta(days=1), key="sales_snapshot_date")
    all_weeks = ["Snapshot", "LW", "L2W", "L3W"]
    selected_weeks = st.multiselect("Select Snapshot Week(s)", options=all_weeks, default=[], key="sales_selected_weeks") or all_weeks
    agg_level = st.selectbox("Aggregation Level", ["Hub", "Community Name"], index=0, key="sales_agg_level")

    hubs = st.multiselect("Hub", sorted(df['Hub'].dropna().unique()), key="sales_hubs") or sorted(df['Hub'].dropna().unique())
    communities = st.multiselect("Community Name", sorted(df['Community Name'].dropna().unique()), key="sales_communities") or sorted(df['Community Name'].dropna().unique())

# --- Filter data by hub/community ---
df = df[df['Hub'].isin(hubs) & df['Community Name'].isin(communities)]
snapshot_map = {w: pd.to_datetime(snapshot_date) - pd.Timedelta(days=i*7) for i, w in enumerate(['Snapshot', 'LW', 'L2W', 'L3W'])}
group_col = 'Hub' if agg_level == 'Hub' else 'Community Name'

# --- Build snapshot datasets ---
results = []
all_groups = df[(df['EST_COE_DATE'] >= est_coe_start) & (df['EST_COE_DATE'] <= est_coe_end)][group_col].dropna().unique()
for label in selected_weeks:
    snap_date = snapshot_map.get(label)
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
days_to_end = (est_coe_end - pd.to_datetime(snapshot_date)).days
cmax = max(60, days_to_end)

# --- Create scatter chart ---
fig = go.Figure()
fig.update_layout(template='plotly_white', hoverlabel=dict(bgcolor="white", font_size=12))
for week in ['L3W', 'L2W', 'LW', 'Snapshot']:
    week_df = viz_df[viz_df['Week'] == week].copy()
    if week_df.empty:
        continue
    marker_colors = week_df.apply(lambda row: 'grey' if row['Unsold'] == 0 else row['Avg_Age'], axis=1)
    text_labels = [{'Snapshot': 'S', 'LW': '1', 'L2W': '2', 'L3W': '3'}.get(week, '')] * len(week_df)
    if group_col == 'Community Name':
        customdata = week_df[['Avg_Age', 'Community Name', 'Hub']]
        hovertemplate = "<b>%{meta}</b><br>Hub: %{customdata[2]}<br>Community: %{customdata[1]}<br>Unsold: %{x}<br>Avg Age: %{customdata[0]:.1f} days<extra></extra>"
    else:
        customdata = week_df[['Avg_Age', 'Hub']]
        hovertemplate = "<b>%{meta}</b><br>Hub: %{customdata[1]}<br>Unsold: %{x}<br>Avg Age: %{customdata[0]:.1f} days<extra></extra>"

    fig.add_trace(go.Scatter(
        x=week_df['Unsold'], y=week_df['label'], mode='markers+text',
        marker=dict(size=16, color=marker_colors, colorscale=[[0, 'red'], [0.5, 'yellow'], [1, 'green']],
                    cmin=0, cmax=cmax, colorbar=dict(title='Avg Age (days)',
                    tickvals=[0, 30, 60, days_to_end], ticktext=['0', '30', '60', f'{days_to_end}'], tickmode='array'),
                    showscale=True,
                    line=dict(color=['black' if x == 0 else 'rgba(0,0,0,0)' for x in week_df['Unsold']], width=1)),
        customdata=customdata, meta=week, hovertemplate=hovertemplate,
        text=text_labels, textfont=dict(color='white', size=14, family='Arial Black'), textposition='middle center', showlegend=False
    ))

fig.update_layout(
    title=dict(text="<b>Weekly Unsold Inventory Snapshots</b>", font=dict(size=22), x=0.5),
    xaxis=dict(title="<b>Unsold Homes</b>", range=[-0.75, max(viz_df['Unsold'].max(), 10) + 1], fixedrange=True,
               showgrid=True, gridcolor='lightgrey', gridwidth=1, zeroline=False),
    yaxis=dict(title=f"<b>{group_col}</b>", categoryorder='array',
               categoryarray=sorted(viz_df['label'].unique(), reverse=True),
               tickfont=dict(size=18 if agg_level == 'Hub' else 14)),
    height=720, plot_bgcolor="white",
    margin=dict(t=60, b=60, l=80, r=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
)
st.plotly_chart(fig, use_container_width=True)

# --- Community Detail Table ---
snapshot_only = viz_df[viz_df['Week'] == 'Snapshot'][[group_col, 'Unsold']]
community_snapshot = df[(df['EST_COE_DATE'] >= est_coe_start) & (df['EST_COE_DATE'] <= est_coe_end)]
sold_counts = community_snapshot[(community_snapshot['SALE_DATE'].notna()) &
                                  (community_snapshot['SALE_DATE'] >= snapshot_map['LW']) &
                                  (community_snapshot['SALE_DATE'] < snapshot_map['Snapshot'])].groupby(group_col).size().reset_index(name='Sold')

if group_col == 'Community Name':
    table_df = community_snapshot[['Hub', 'Community Name']].drop_duplicates()
    table_df = table_df.merge(snapshot_only, on='Community Name', how='left')
    table_df = table_df.merge(sold_counts, on='Community Name', how='left')
else:
    table_df = community_snapshot[['Hub']].drop_duplicates()
    table_df['Community Name'] = ''
    table_df = table_df.merge(snapshot_only, on='Hub', how='left')
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






