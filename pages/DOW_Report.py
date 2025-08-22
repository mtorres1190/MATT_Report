import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import math

# --- Page setup ---
st.set_page_config(page_title="DOW Report", layout="wide")
st.title("Day of Week (DOW) Sales Report")

# --- Custom CSS ---
st.markdown("""
    <style>
        .stMultiSelect [data-baseweb=\"tag\"] { background-color: #1f77b4 !important; }
        .chart-title { font-size: 20px !important; font-weight: bold !important; }
        .week-start-label { font-size: 20px !important; font-weight: bold !important; }
    </style>
""", unsafe_allow_html=True)

# --- Check if processed MATT data is available ---
if 'matt_processed' not in st.session_state:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed']

# ======================================================================================
# Sidebar filters — CASCADING, DATA-AWARE OPTIONS
# ======================================================================================
with st.sidebar:
    st.header("Filters")

    # Sale Date Range filter (applies ONLY to DOW charts)
    most_recent_sunday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday() + 1)
    sale_date_range = st.date_input("Sale Date Range", value=(datetime.date(2024, 9, 1), most_recent_sunday))
    if isinstance(sale_date_range, tuple) and len(sale_date_range) == 2:
        start_date, end_date = pd.to_datetime(sale_date_range[0]), pd.to_datetime(sale_date_range[1])
    else:
        st.error("Invalid date range selection.")
        st.stop()

    # ---- 1) Build base set WITHOUT date filtering (for non-DOW charts)
    df_base = df.copy()

    # ---- 2) Division filter (data-aware)
    div_options = sorted(df_base['DIV_CODE_DESC'].dropna().astype(str).unique())
    div_selection = st.multiselect("Division", options=div_options, default=[])
    div_selected = div_selection if div_selection else div_options
    df_div = df_base.loc[df_base['DIV_CODE_DESC'].isin(div_selected)].copy()

    # ---- 3) Hub filter (division)
    hub_options = sorted(df_div['Hub'].dropna().astype(str).unique())
    selected_hubs = st.multiselect("Hub", options=hub_options, default=[])
    hubs = selected_hubs if selected_hubs else hub_options
    df_hub = df_div.loc[df_div['Hub'].isin(hubs)].copy()

    # ---- 4) Community filter (division + hub)
    community_options = sorted(df_hub['Community Name'].dropna().astype(str).unique())
    selected_communities = st.multiselect("Community Name", options=community_options, default=[])
    communities = selected_communities if selected_communities else community_options
    df_comm = df_hub.loc[df_hub['Community Name'].isin(communities)].copy()

        # ---- 5) Investor filter (division + hub + community)
    investor_options = sorted(df_comm['Investor Sale'].dropna().astype(str).unique()) if 'Investor Sale' in df_comm.columns else []
    investor_options = [opt for opt in investor_options if not df_comm.loc[df_comm['Investor Sale'] == opt].empty]

    # Default to "Retail" if available, otherwise fallback to "All"
    default_index = 0  # fallback to "All"
    if "Retail" in investor_options:
        default_index = (["All"] + investor_options).index("Retail")

    investor_filter = st.selectbox("Investor Sale", ["All"] + investor_options, index=default_index)
    df_inv = df_comm.copy()
    if investor_filter != "All":
        df_inv = df_inv.loc[df_inv['Investor Sale'] == investor_filter].copy()

    # ---- 6) Realtor/Direct filter (division + hub + community + investor)
    rd_options = sorted(df_inv['Realtor/Direct'].dropna().astype(str).unique()) if 'Realtor/Direct' in df_inv.columns else []
    rd_options = [opt for opt in rd_options if not df_inv.loc[df_inv['Realtor/Direct'] == opt].empty]
    cobroke_filter = st.selectbox("Realtor/Direct", ["All"] + rd_options, index=0)
    df_final = df_inv.copy()
    if cobroke_filter != "All":
        df_final = df_final.loc[df_final['Realtor/Direct'] == cobroke_filter].copy()

# ======================================================================================
# Create date-filtered copy for DOW charts only
# ======================================================================================
df_dow = df_final.loc[(df_final['SALE_DATE'] >= start_date) & (df_final['SALE_DATE'] <= end_date)].copy()

# ======================================================================================
# DOW Charts (use df_dow)
# ======================================================================================
if not df_dow.empty and 'Weekday_Group' in df_dow.columns:
    dow_summary = (
        df_dow.groupby('DOW_Sale')
        .agg(Sales=('DOW_Sale', 'count'))
        .reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
        .fillna(0)
    )
    dow_summary['Sales %'] = 100 * dow_summary['Sales'] / dow_summary['Sales'].sum()
    sales_counts = list(dow_summary['Sales']) + [int(dow_summary['Sales'].sum())]
    fig_waterfall = go.Figure(go.Waterfall(
        measure=["relative"] * len(dow_summary) + ["total"],
        x=list(dow_summary.index) + ["Grand Total"],
        y=list(dow_summary['Sales %']) + [100],
        text=[f"{round(val)}%" for val in dow_summary['Sales %']] + ["100%"],
        textposition="inside",
        textfont=dict(color="white", size=14),
        customdata=sales_counts,
        hovertemplate="<b>%{x}</b><br>Share: %{y:.0f}%<br>Sales: %{customdata:,}<extra></extra>",
        connector={"line": {"color": "rgb(63, 63, 63)"}}
    ))
    fig_waterfall.update_layout(title='DOW Sales Distribution', title_font=dict(size=20), yaxis_title='% of Weekly Sales', height=450)

    df_dow['Sales_Month'] = df_dow['SALE_DATE'].dt.to_period('M')
    dow_group = df_dow.groupby(['Sales_Month', 'Weekday_Group']).size().unstack().fillna(0)
    dow_group['M-F'] = dow_group.get('M-F', 0)
    dow_group['Sat-Sun'] = dow_group.get('Sat-Sun', 0)
    dow_group['Total'] = dow_group.sum(axis=1)
    dow_group['M-F %'] = (dow_group['M-F'] / dow_group['Total'] * 100).round(0)
    dow_group['Sat-Sun %'] = (dow_group['Sat-Sun'] / dow_group['Total'] * 100).round(0)

    fig_trend = go.Figure()
    formatted_dates = [p.to_timestamp().strftime('%b, %Y') for p in dow_group.index]

    fig_trend.add_trace(go.Bar(
        x=formatted_dates,
        y=dow_group['M-F'],
        name='M-F Sales',
        customdata=formatted_dates,
        hovertemplate="<b>M-F Sales</b><br>%{customdata}<br>Sales: %{y:,}<extra></extra>"
    ))
    fig_trend.add_trace(go.Bar(
        x=formatted_dates,
        y=dow_group['Sat-Sun'],
        name='Sat-Sun Sales',
        customdata=formatted_dates,
        hovertemplate="<b>Sat-Sun Sales</b><br>%{customdata}<br>Sales: %{y:,}<extra></extra>"
    ))

    fig_trend.add_trace(go.Scatter(
        x=formatted_dates,
        y=dow_group['M-F %'],
        mode='lines+markers+text',
        name='Sales % - M-F',
        yaxis='y2',
        text=[f"<b>{int(val)}%</b>" for val in dow_group['M-F %']],
        textposition="top center",
        hoverinfo='skip'
    ))
    fig_trend.add_trace(go.Scatter(
        x=formatted_dates,
        y=dow_group['Sat-Sun %'],
        mode='lines+markers',
        name='Sales % - Sat-Sun',
        yaxis='y2',
        hoverinfo='skip'
    ))

    fig_trend.update_layout(
        title='DOW Contribution to Sales',
        title_font=dict(size=20),
        barmode='group',
        yaxis=dict(title='Total Sales'),
        yaxis2=dict(title='Sales %', overlaying='y', side='right', range=[0, 100], showgrid=False),
        hovermode='closest',
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.3,
            xanchor="center",
            x=0.5
        )
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        st.plotly_chart(fig_waterfall, use_container_width=True)
    with col2:
        st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.warning("No data available for the selected filters.")

st.markdown("---")

# ======================================================================================
# Week-based charts (NOT affected by Sale Date Range filter)
# ======================================================================================
most_recent_monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
st.markdown('<div class="week-start-label">Select Week Start Date</div>', unsafe_allow_html=True)
week_start = st.date_input("Select Week Start Date", most_recent_monday, label_visibility="collapsed")
week_end = week_start + datetime.timedelta(days=6)

sales_week_df = df_final.loc[
    df_final['DIV_CODE_DESC'].isin(div_selected) &
    df_final['Hub'].isin(hubs) &
    df_final['Community Name'].isin(communities) &
    df_final['SALE_DATE'].between(pd.to_datetime(week_start), pd.to_datetime(week_end))
].copy()

# Total sales subheader
total_sales = sales_week_df.shape[0]
st.subheader(f"Total Sales This Week: {total_sales}")

# --- ECOE Distribution Chart ---
ecoe_week_df = sales_week_df.dropna(subset=['EST_COE_DATE']).copy()
if not ecoe_week_df.empty and total_sales > 0:
    ecoe_week_df = ecoe_week_df.copy()
    if 'ECOE_Month' in ecoe_week_df.columns:
        ecoe_week_df.loc[:, 'ECOE_Month_Period'] = ecoe_week_df['ECOE_Month']
    else:
        ecoe_week_df.loc[:, 'ECOE_Month_Period'] = pd.to_datetime(ecoe_week_df['EST_COE_DATE'], errors='coerce').dt.to_period('M')

    ecoe_month_counts = (
        ecoe_week_df
        .groupby('ECOE_Month_Period')
        .size()
        .reset_index(name='Homes Sold')
        .sort_values('ECOE_Month_Period')
    )

    ecoe_month_counts['MonthLabel'] = ecoe_month_counts['ECOE_Month_Period'].dt.to_timestamp().dt.strftime('%b %Y')
    ecoe_month_counts['Pct of Total'] = (ecoe_month_counts['Homes Sold'] / total_sales * 100).round(0).astype(int)
    pct_text = [f"{p}%" for p in ecoe_month_counts['Pct of Total']]

    max_val = int(ecoe_month_counts['Homes Sold'].max()) if not ecoe_month_counts.empty else 0
    y_max = int(math.ceil(max_val * 1.10)) if max_val > 0 else 1

    fig_ecoe = go.Figure()
    fig_ecoe.add_trace(go.Scatter(
        x=ecoe_month_counts['MonthLabel'],
        y=ecoe_month_counts['Homes Sold'],
        mode='lines+markers+text',
        line_shape='spline',
        fill='tozeroy',
        text=pct_text,
        textposition='top center',
        cliponaxis=False,
        hovertemplate='<b>%{x}</b><br>Homes Sold: %{y:,}<br>% of Total: %{text}<extra></extra>'
    ))

    fig_ecoe.update_layout(
        title='ECOE Distribution',
        title_font=dict(size=20),
        xaxis_title=None,
        height=150,
        margin=dict(t=50, r=0, b=0, l=40),
        hovermode='x',
        spikedistance=-1,
        hoverdistance=-1,
    )
    fig_ecoe.update_yaxes(title='Homes Sold', range=[0, y_max], automargin=True)

    st.plotly_chart(fig_ecoe, use_container_width=True)
else:
    st.info("No valid EST ECOE dates for this week's sales to display distribution.")

# --- Sales Week bar chart ---
if not sales_week_df.empty:
    weekly_chart_data = sales_week_df.groupby(['SALE_DATE', 'Realtor/Direct']).size().reset_index(name='Homes Sold')
    weekly_chart_data['DateLabel'] = weekly_chart_data['SALE_DATE'].dt.strftime('%A<br>%m/%d/%Y')
    weekly_chart_data['DateShort'] = weekly_chart_data['SALE_DATE'].dt.strftime('%b %d, %Y')
    weekly_chart_data.sort_values('SALE_DATE', inplace=True)
    date_order = weekly_chart_data['DateLabel'].unique().tolist()

    fig_week = px.bar(
        weekly_chart_data,
        x='DateLabel',
        y='Homes Sold',
        color='Realtor/Direct',
        text='Homes Sold',
        barmode='stack',
        title='Sales Week',
        category_orders={'DateLabel': date_order},
        labels={'DateLabel': 'Sale Date'}
    )

    fig_week.update_traces(
        customdata=weekly_chart_data['DateShort'],
        hovertemplate=(
            "<b>%{fullData.name}</b><br>%{customdata}<br>Sales: %{y:,}<extra></extra>"
        ),
        textposition='inside',
        textfont=dict(size=16)
    )

    fig_week.update_layout(
        title_font=dict(size=20),
        font=dict(size=16),
        xaxis=dict(title=None),
        yaxis=dict(title='Homes Sold'),
        hovermode='closest'
    )

    st.plotly_chart(fig_week, use_container_width=True)

        # --- Detail table ---
    sales_week_df = sales_week_df.copy()
    sales_week_df.loc[:, 'COE Year'] = sales_week_df['EST_COE_DATE'].dt.year
    sales_week_df.loc[:, 'COE Month'] = sales_week_df['EST_COE_DATE'].dt.strftime('%b')
    display_cols = ['Hub', 'Community Name', 'Address', 'Plan Name', 'Investor Sale',
                    'NHC_NAME', 'SALE_DATE', 'BUYER_NAME', 'Realtor/Direct',
                    'COE Year', 'COE Month']
    display_cols_available = [col for col in display_cols if col in sales_week_df.columns]
    detailed_table = sales_week_df[display_cols_available].copy()

    # Force to string format for display
    if 'SALE_DATE' in detailed_table.columns:
        detailed_table['SALE_DATE'] = detailed_table['SALE_DATE'].dt.strftime('%m/%d/%Y')

    detailed_table = detailed_table.rename(columns={
        'SALE_DATE': 'Sale Date',
        'BUYER_NAME': 'Buyer',
        'NHC_NAME': 'NHC Name'
    })

    st.dataframe(detailed_table, use_container_width=True, hide_index=True)

else:
    st.info("No data available for the selected week.")












