import streamlit as st
import pandas as pd
import datetime
import plotly.express as px

from scripts.process_matt import compute_pace_vs_margin

# --- Page setup ---
st.set_page_config(page_title="Pace vs. Margin", layout="wide")
st.title("Pace vs. Margin")

# --- Custom CSS for multi-select tags ---
st.markdown("""
    <style>
        .stMultiSelect [data-baseweb=\"tag\"] {
            background-color: #1f77b4 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- Check for uploaded data ---
uploaded = 'matt_processed' in st.session_state
if not uploaded:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

matt_df = st.session_state['matt_processed']

# ======================================================================================
# Sidebar filters — CASCADING, DATA-AWARE OPTIONS (no empty options shown)
# ======================================================================================
with st.sidebar:
    st.header("Filters")

    # Target Sell-by Date
    target_date_input = st.date_input("Target Sell-by Date", value=datetime.date(2025, 11, 30))
    st.session_state["target_date"] = target_date_input
    target_date = target_date_input

    # COE Date Range filter
    coe_range_input = st.date_input(
        "COE Date Range",
        value=(datetime.date(2025, 8, 1), datetime.date(2025, 12, 31)),
        key="pace_margin_est_coe_range"
    )
    if isinstance(coe_range_input, tuple) and len(coe_range_input) == 2:
        est_coe_start, est_coe_end = pd.to_datetime(coe_range_input[0]), pd.to_datetime(coe_range_input[1])
    else:
        st.error("Please select a date range for COE Date.")
        st.stop()

    # ---- 1) Filter by Date first
    df_date = matt_df[(matt_df['EST_COE_DATE'] >= est_coe_start) & (matt_df['EST_COE_DATE'] <= est_coe_end)].copy()

    # ---- 2) Hub options (dependent on date)
    hub_options = sorted(df_date['Hub'].dropna().unique())
    selected_hubs = st.multiselect("Hub", options=hub_options, key="pace_margin_hubs")
    hubs = selected_hubs if selected_hubs else hub_options

    df_hub = df_date[df_date['Hub'].isin(hubs)]

    # ---- 3) Community options (dependent on date + hub)
    community_options = sorted(df_hub['Community Name'].dropna().unique())
    selected_communities = st.multiselect("Community Name", options=community_options, key="pace_margin_communities")
    communities = selected_communities if selected_communities else community_options

# ======================================================================================
# Apply all filters to the working dataframe
# ======================================================================================
filtered_df = df_hub[df_hub['Community Name'].isin(communities)].copy()

# Stop early if no data matches
if filtered_df.empty:
    st.info("No rows match the current filter set.")
    st.stop()

# ======================================================================================
# Calculate sales pace and break-even
# ======================================================================================
summary, slope = compute_pace_vs_margin(filtered_df, target_date, est_coe_start, est_coe_end)

# Remove communities with no valid COE within window (defensive)
est_coe_col = 'EST_COE_DATE'
filtered_df[est_coe_col] = pd.to_datetime(filtered_df[est_coe_col], errors='coerce')
mask = (filtered_df[est_coe_col] >= est_coe_start) & (filtered_df[est_coe_col] <= est_coe_end)
valid_communities = filtered_df.loc[mask, 'Community Name'].dropna().unique()
summary = summary[summary.index.isin(valid_communities)]

# Stop if summary is empty after filtering
if summary.empty:
    st.info("No communities have valid COE dates in the selected range.")
    st.stop()

# ======================================================================================
# Generate scatter plot: Pace vs. Margin with Equilibrium line
# ======================================================================================
summary_plot = summary.reset_index()
summary_plot.rename(columns={'3Wk Avg Sales Pace': 'Sales Pace'}, inplace=True)
summary_plot['Break-even Pace'] = summary_plot['Unsold'] * slope

category_order = ['Margin', 'Target', 'Pace', 'Behind', 'Equilibrium']

fig = px.scatter(
    summary_plot,
    x='Unsold',
    y='Sales Pace',
    color='Category',
    category_orders={'Category': category_order},
    color_discrete_map={
        'Margin': 'green',
        'Target': 'gray',
        'Pace': 'orange',
        'Behind': 'red',
        'Equilibrium': 'blue'
    },
    hover_name='Community Name',
    hover_data={
        'Unsold': True,
        'Sales Pace': ':.2f',
        'Needed Pace': False,
        'Delta': False,
    },
    custom_data=['Needed Pace', 'Delta'],
    height=700,
    title="Pace vs. Margin",
)
fig.update_layout(title_font=dict(size=20))
fig.update_traces(
    marker=dict(size=12),
    hovertemplate='<b>%{hovertext}</b><br>' +
                  'Unsold Homes: %{x}<br>' +
                  'Sales Pace: %{y:.2f}<br>' +
                  'Sales Pace Needed: %{customdata[0]:.2f}<br>' +
                  'Delta: %{customdata[1]:.2f}<extra></extra>'
)
fig.add_scatter(
    x=[0, summary_plot['Unsold'].max() + 5],
    y=[0, (summary_plot['Unsold'].max() + 5) * slope],
    mode='lines',
    line=dict(color='blue', dash='solid'),
    name='Equilibrium'
)
fig.update_layout(
    xaxis_tickfont=dict(size=16),
    yaxis_tickfont=dict(size=16),
    xaxis_title='Unsold Homes',
    yaxis_title='Avg. Gross Sales Pace (L3W)',
    plot_bgcolor='white',
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5, font=dict(size=18)),
    legend_title_text=None,
    margin=dict(l=40, r=40, t=80, b=60),
    font=dict(size=16),
    xaxis=dict(showgrid=True, gridcolor='lightgray', zeroline=False, linecolor='black', linewidth=1, title_font=dict(size=18)),
    yaxis=dict(showgrid=True, gridcolor='lightgray', zeroline=False, linecolor='black', linewidth=1, title_font=dict(size=18))
)
st.plotly_chart(fig, use_container_width=True)

# --- Equilibrium line explanation ---
st.markdown("""
<div style='font-size: 18px; margin-top: -10px; color: #333;'>
    <strong>Equilibrium Line:</strong> Communities along the Equilibrium Line are selling exactly fast enough to sell all remaining homes by the Target Sell-by Date.
</div>
<div style='width: 50%; margin: 20px auto;'>
    <hr style='border: none; height: 1px; background-color: #ccc;'>
</div>
""", unsafe_allow_html=True)

# ======================================================================================
# Category distribution pie charts
# ======================================================================================
st.markdown("### Distribution of Communities by Category")
category_order = ['Margin', 'Target', 'Pace', 'Behind']
category_counts = summary_plot['Category'].value_counts().reset_index()
category_counts.columns = ['Category', 'Count']
category_counts['Category'] = pd.Categorical(category_counts['Category'], categories=category_order, ordered=True)
category_counts = category_counts.sort_values('Category')

col1, col2 = st.columns(2)

# Pie chart: Community count by category
with col1:
    fig_pie = px.pie(
        category_counts,
        names='Category',
        values='Count',
        title="Community Count by Category",
        color='Category',
        category_orders={'Category': category_order},
        color_discrete_map={
            'Margin': 'green',
            'Target': 'gray',
            'Pace': 'orange',
            'Behind': 'red'
        },
        hole=0.4
    )
    fig_pie.update_traces(textinfo='percent+label', hovertemplate='%{label}: %{value} (%{percent})<extra></extra>')
    fig_pie.update_layout(title_font=dict(size=20))
    st.plotly_chart(fig_pie, use_container_width=True)

# Pie chart: Unsold homes by category
with col2:
    total_unsold_by_category = summary_plot.groupby('Category')['Unsold'].sum().reset_index()
    total_unsold_by_category['Category'] = pd.Categorical(total_unsold_by_category['Category'], categories=category_order, ordered=True)
    total_unsold_by_category = total_unsold_by_category.sort_values('Category')

    fig_unsold_pie = px.pie(
        total_unsold_by_category,
        names='Category',
        values='Unsold',
        title="Unsold Homes by Category",
        color='Category',
        category_orders={'Category': category_order},
        color_discrete_map={
            'Margin': 'green',
            'Target': 'gray',
            'Pace': 'orange',
            'Behind': 'red'
        },
        hole=0.4
    )
    fig_unsold_pie.update_traces(textinfo='percent+label', hovertemplate='%{label}: %{value} homes (%{percent})<extra></extra>')
    fig_unsold_pie.update_layout(title_font=dict(size=20))
    st.plotly_chart(fig_unsold_pie, use_container_width=True)

# ======================================================================================
# Styled DataFrame output for each category
# ======================================================================================
st.markdown("---")
summary_display = summary.copy()
summary_display = summary_display.merge(
    filtered_df[['Community Name', 'Hub']].drop_duplicates(),
    on='Community Name',
    how='left'
)
summary_display['Unsold'] = summary_display['Unsold'].round(0).astype(int)

for col in ['3Wk Avg Sales Pace', 'Needed Pace', 'Delta']:
    summary_display[col] = summary_display[col].map("{:.2f}".format)

color_map = {
    'Margin': '#d4edda',
    'Target': '#e2e3e5',
    'Pace': '#fff3cd',
    'Behind': '#f8d7da'
}

for category in ['Margin', 'Target', 'Pace', 'Behind']:
    group = summary_display[summary_display['Category'] == category].copy()
    if not group.empty:
        st.markdown(f"### {category} Communities")

        columns_order = ['Hub', 'Community Name', 'Unsold', '3Wk Avg Sales Pace', 'Needed Pace', 'Delta']
        group.columns = [col.strip() for col in group.columns]
        group = group[[col for col in columns_order if col in group.columns]]

        if 'Community Name' in group.columns:
            group = group.sort_values(by='Community Name')

        def highlight_row(row):
            return [f'background-color: {color_map.get(category, "white") }'] * len(row)

        styled = group.style.set_table_styles([
            {'selector': 'th', 'props': [('font-size', '15px'), ('text-align', 'center'), ('background-color', '#f0f2f6'), ('min-width', '120px')]},
            {'selector': 'td', 'props': [('font-size', '14px'), ('padding', '8px 12px'), ('min-width', '120px')]},
            {'selector': 'tr:hover', 'props': [('background-color', '#eef6ff')]}
        ]).apply(highlight_row, axis=1).hide(axis='index')

        st.dataframe(styled, use_container_width=True, hide_index=True)













