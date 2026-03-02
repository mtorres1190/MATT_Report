import streamlit as st
import pandas as pd
import datetime
import plotly.express as px

# ======================================================================================
# INLINE ORIGINAL compute_pace_vs_margin (unchanged logic)
# ======================================================================================
def compute_pace_vs_margin(
    df: pd.DataFrame,
    target_date: datetime.date,
    coe_start: datetime.date,
    coe_end: datetime.date
):

    today = datetime.date.today()

    df = df.copy()
    df['EST_COE_DATE'] = pd.to_datetime(df['EST_COE_DATE'], errors='coerce')
    df['SALE_DATE'] = pd.to_datetime(df['SALE_DATE'], errors='coerce')

    # --------------------------------------------------
    # Unsold homes in selected COE window
    # --------------------------------------------------
    unsold_df = df[
        (df['HS_TYPE'] == 'S') &
        (df['EST_COE_DATE'] >= pd.Timestamp(coe_start)) &
        (df['EST_COE_DATE'] <= pd.Timestamp(coe_end))
    ]

    # --------------------------------------------------
    # Sold homes in last 3 weeks
    # --------------------------------------------------
    three_weeks_ago = pd.Timestamp(today - datetime.timedelta(days=21))
    sold_df = df[
        (df['HS_TYPE'].isin(['B', 'Z'])) &
        (df['SALE_DATE'] >= three_weeks_ago)
    ]

    # --------------------------------------------------
    # Pace + Unsold Counts
    # --------------------------------------------------
    pace = sold_df.groupby('Community Name').size() / 3
    unsold_counts = unsold_df.groupby('Community Name').size()

    # --------------------------------------------------
    # Weeks remaining to target
    # --------------------------------------------------
    weeks_left = (target_date - today).days / 7
    weeks_left = max(weeks_left, 0)

    slope = 1 / weeks_left if weeks_left > 0 else 0

    summary = pd.DataFrame({
        'Unsold': unsold_counts,
        '3Wk Avg Sales Pace': pace
    }).fillna(0)

    summary['Needed Pace'] = (
        summary['Unsold'] / weeks_left
        if weeks_left > 0 else 0
    )

    summary['Delta'] = (
        summary['3Wk Avg Sales Pace'] - summary['Needed Pace']
    )

    def classify(delta):
        if delta > 1:
            return 'Margin'
        elif 0 < delta <= 1:
            return 'Target'
        elif -2 < delta <= 0:
            return 'Pace'
        else:
            return 'Behind'

    summary['Category'] = summary['Delta'].apply(classify)

    return summary, slope


# ======================================================================================
# PAGE SETUP
# ======================================================================================

st.set_page_config(page_title="Pace vs. Margin", layout="wide")
st.title("Pace vs. Margin")

st.markdown("""
<style>

/* Multiselect styling */
.stMultiSelect [data-baseweb="tag"] {
    background-color: #1f77b4 !important;
}

/* ----------------------------------------------------------
   Allow sidebar popovers to overflow naturally
   ---------------------------------------------------------- */

section[data-testid="stSidebar"] {
    overflow-y: auto !important;
    overflow-x: visible !important;
}

section[data-testid="stSidebar"] > div {
    overflow-y: auto !important;
    overflow-x: visible !important;
}

/* Ensure date popovers render above everything */
div[data-baseweb="popover"] {
    z-index: 9999 !important;
}

</style>
""", unsafe_allow_html=True)

if 'matt_processed' not in st.session_state:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

matt_df = st.session_state['matt_processed']


# ======================================================================================
# SIDEBAR FILTERS (Target Date INCLUDED here)
# ======================================================================================

with st.sidebar:
    st.header("Filters")

    # --------------------------------------------------
    # Target Sell-by Date
    # --------------------------------------------------
    target_date_input = st.date_input(
        "Target Sell-by Date",
        value=datetime.date(2026, 3, 31),
        key="pace_margin_target_date"
    )
    target_date = target_date_input

    # --------------------------------------------------
    # COE Date Range
    # --------------------------------------------------
    coe_range_input = st.date_input(
        "COE Date Range",
        value=(datetime.date(2025, 1, 31), datetime.date(2026, 4, 15)),
        key="pace_margin_est_coe_range"
    )

    if isinstance(coe_range_input, tuple) and len(coe_range_input) == 2:
        est_coe_start = pd.to_datetime(coe_range_input[0])
        est_coe_end = pd.to_datetime(coe_range_input[1])
    else:
        st.error("Please select a valid COE Date range.")
        st.stop()

    # --------------------------------------------------
    # 1) Filter by COE date
    # --------------------------------------------------
    df_date = matt_df[
        (matt_df['EST_COE_DATE'] >= est_coe_start) &
        (matt_df['EST_COE_DATE'] <= est_coe_end)
    ].copy()

    # --------------------------------------------------
    # 2) Hub filter
    # --------------------------------------------------
    hub_options = sorted(df_date['Hub'].dropna().unique())
    selected_hubs = st.multiselect(
        "Hub",
        options=hub_options,
        key="pace_margin_hubs"
    )

    hubs = selected_hubs if selected_hubs else hub_options
    df_hub = df_date[df_date['Hub'].isin(hubs)].copy()

    # --------------------------------------------------
    # 3) Community filter
    # --------------------------------------------------
    community_options = sorted(df_hub['Community Name'].dropna().unique())
    selected_communities = st.multiselect(
        "Community Name",
        options=community_options,
        key="pace_margin_communities"
    )

    communities = selected_communities if selected_communities else community_options


# ======================================================================================
# APPLY ALL FILTERS (OUTSIDE SIDEBAR)
# ======================================================================================

filtered_df = df_hub[
    df_hub['Community Name'].isin(communities)
].copy()

if filtered_df.empty:
    st.info("No rows match the current filter set.")
    st.stop()


# ======================================================================================
# CALCULATE SUMMARY
# ======================================================================================

summary, slope = compute_pace_vs_margin(
    filtered_df,
    target_date,
    est_coe_start,
    est_coe_end
)

if summary.empty:
    st.info("No communities have valid COE dates in the selected range.")
    st.stop()

# ======================================================================================
# Scatter Plot (UNCHANGED)
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

# ------------------------------------------------------------------
# 🔥 KEY FIX: Let axes auto-scale FIRST (based only on data)
# ------------------------------------------------------------------

# Compute axis bounds from data ONLY
x_max_data = summary_plot['Unsold'].max()
y_max_data = summary_plot['Sales Pace'].max()

# Preserve Plotly’s natural buffer by NOT setting explicit ranges
# Instead, limit equilibrium line to data-driven bounds

# Determine equilibrium line end within visible area
x_line_max = x_max_data
y_line_max = x_line_max * slope

# If equilibrium line would exceed current data y max,
# trim it so it stays inside natural axis scaling
if y_line_max > y_max_data:
    x_line_max = y_max_data / slope
    y_line_max = y_max_data

fig.add_scatter(
    x=[0, x_line_max],
    y=[0, y_line_max],
    mode='lines',
    line=dict(color='blue', dash='solid'),
    name='Equilibrium'
)

# ------------------------------------------------------------------
# Layout (unchanged — preserves your padding aesthetic)
# ------------------------------------------------------------------

fig.update_layout(
    xaxis_tickfont=dict(size=16),
    yaxis_tickfont=dict(size=16),
    xaxis_title='Unsold Homes',
    yaxis_title='Avg. Gross Sales Pace (L3W)',
    plot_bgcolor='white',
    legend=dict(
        orientation='h',
        yanchor='bottom',
        y=1.02,
        xanchor='center',
        x=0.5,
        font=dict(size=18)
    ),
    legend_title_text=None,
    margin=dict(l=40, r=40, t=80, b=60),
    font=dict(size=16),
    xaxis=dict(
        showgrid=True,
        gridcolor='lightgray',
        zeroline=False,
        linecolor='black',
        linewidth=1,
        title_font=dict(size=18)
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor='lightgray',
        zeroline=False,
        linecolor='black',
        linewidth=1,
        title_font=dict(size=18)
    )
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
    fig_pie.update_traces(
        textinfo='percent+label',
        hovertemplate='%{label}: %{value} (%{percent})<extra></extra>'
    )
    fig_pie.update_layout(title_font=dict(size=20))
    st.plotly_chart(fig_pie, use_container_width=True)

# Pie chart: Unsold homes by category
with col2:
    total_unsold_by_category = summary_plot.groupby('Category')['Unsold'].sum().reset_index()
    total_unsold_by_category['Category'] = pd.Categorical(
        total_unsold_by_category['Category'],
        categories=category_order,
        ordered=True
    )
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
    fig_unsold_pie.update_traces(
        textinfo='percent+label',
        hovertemplate='%{label}: %{value} homes (%{percent})<extra></extra>'
    )
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

        columns_order = [
            'Hub',
            'Community Name',
            'Unsold',
            '3Wk Avg Sales Pace',
            'Needed Pace',
            'Delta'
        ]

        group.columns = [col.strip() for col in group.columns]
        group = group[[col for col in columns_order if col in group.columns]]

        if 'Community Name' in group.columns:
            group = group.sort_values(by='Community Name')

        def highlight_row(row):
            return [f'background-color: {color_map.get(category, "white")}'] * len(row)

        styled = group.style.set_table_styles([
            {
                'selector': 'th',
                'props': [
                    ('font-size', '15px'),
                    ('text-align', 'center'),
                    ('background-color', '#f0f2f6'),
                    ('min-width', '120px')
                ]
            },
            {
                'selector': 'td',
                'props': [
                    ('font-size', '14px'),
                    ('padding', '8px 12px'),
                    ('min-width', '120px')
                ]
            },
            {
                'selector': 'tr:hover',
                'props': [('background-color', '#eef6ff')]
            }
        ]).apply(highlight_row, axis=1).hide(axis='index')

        st.dataframe(styled, use_container_width=True, hide_index=True)













