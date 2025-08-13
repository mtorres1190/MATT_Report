import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime

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

# --- Sidebar filters ---
st.sidebar.header("Filters")
div_selection = st.sidebar.multiselect("Division", options=df['DIV_CODE_DESC'].dropna().unique(), default=["HB Dallas-Fort Worth"])
most_recent_sunday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday() + 1)
sale_date_range = st.sidebar.date_input("Sale Date Range", value=(datetime.date(2024, 9, 1), most_recent_sunday))
if isinstance(sale_date_range, tuple) and len(sale_date_range) == 2:
    start_date, end_date = pd.to_datetime(sale_date_range[0]), pd.to_datetime(sale_date_range[1])
else:
    st.error("Invalid date range selection.")
    st.stop()

investor_filter = st.sidebar.selectbox("Investor Sale", ["All", "Retail", "Investor"], index=1)
cobroke_filter = st.sidebar.selectbox("Realtor/Direct", ["All", "Realtor", "Direct"], index=0)

# --- Apply filters ---
mask = df['DIV_CODE_DESC'].isin(div_selection) & df['SALE_DATE'].between(start_date, end_date)
if investor_filter != "All":
    mask &= df['Investor Sale'] == investor_filter
if cobroke_filter != "All":
    mask &= df['Realtor/Direct'] == cobroke_filter
filtered_df = df[mask].copy()
if filtered_df.empty or 'Weekday_Group' not in filtered_df.columns:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- Waterfall chart ---
dow_summary = (
    filtered_df.groupby('DOW_Sale')
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

# --- Monthly trend chart ---
filtered_df['Sales_Month'] = filtered_df['SALE_DATE'].dt.to_period('M')
dow_group = filtered_df.groupby(['Sales_Month', 'Weekday_Group']).size().unstack().fillna(0)
# Ensure expected columns exist
dow_group['M-F'] = dow_group.get('M-F', 0)
dow_group['Sat-Sun'] = dow_group.get('Sat-Sun', 0)
dow_group['Total'] = dow_group.sum(axis=1)
dow_group['M-F %'] = (dow_group['M-F'] / dow_group['Total'] * 100).round(0)
dow_group['Sat-Sun %'] = (dow_group['Sat-Sun'] / dow_group['Total'] * 100).round(0)

fig_trend = go.Figure()
formatted_dates = [p.to_timestamp().strftime('%b, %Y') for p in dow_group.index]

# Updated hover labels: Category (bold) → Month, Year → Homes sold
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

# Keep % line traces but remove hovers
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

# --- Update layout for DOW Contribution to Sales chart ---
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

# --- Show charts ---
col1, col2 = st.columns([1, 2])
with col1:
    st.plotly_chart(fig_waterfall, use_container_width=True)
with col2:
    with st.container():
        st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# --- Weekly snapshot bar chart ---
most_recent_monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
st.markdown('<div class="week-start-label">Select Week Start Date</div>', unsafe_allow_html=True)
week_start = st.date_input("Select Week Start Date", most_recent_monday, label_visibility="collapsed")
week_end = week_start + datetime.timedelta(days=6)

sales_week_df = df[df['SALE_DATE'].between(pd.to_datetime(week_start), pd.to_datetime(week_end))]
if investor_filter != "All":
    sales_week_df = sales_week_df[sales_week_df['Investor Sale'] == investor_filter]

# Total sales subheader — ECOE chart goes just below this
total_sales = sales_week_df.shape[0]
st.subheader(f"Total Sales This Week: {total_sales}")

# >>> INSERTED: Sales Distribution by Est. ECOE Month (spline area chart) <<<
# Uses the same filtered set as the Sales Week chart (sales_week_df)
import math

ecoe_week_df = sales_week_df.dropna(subset=['EST_COE_DATE']).copy()
if not ecoe_week_df.empty and total_sales > 0:
    # Prefer precomputed period if present; otherwise compute
    if 'ECOE_Month' in ecoe_week_df.columns:
        ecoe_week_df['ECOE_Month_Period'] = ecoe_week_df['ECOE_Month']
    else:
        ecoe_week_df['ECOE_Month_Period'] = pd.to_datetime(ecoe_week_df['EST_COE_DATE'], errors='coerce').dt.to_period('M')

    ecoe_month_counts = (
        ecoe_week_df
        .groupby('ECOE_Month_Period')
        .size()
        .reset_index(name='Homes Sold')
        .sort_values('ECOE_Month_Period')
    )

    # Build labels and % of total
    ecoe_month_counts['MonthLabel'] = ecoe_month_counts['ECOE_Month_Period'].dt.to_timestamp().dt.strftime('%b %Y')
    ecoe_month_counts['Pct of Total'] = (ecoe_month_counts['Homes Sold'] / total_sales * 100).round(0).astype(int)
    pct_text = [f"{p}%" for p in ecoe_month_counts['Pct of Total']]

    # Dynamic y-axis ceiling: ceil(1.10 × max monthly value)
    max_val = int(ecoe_month_counts['Homes Sold'].max()) if not ecoe_month_counts.empty else 0
    y_max = int(math.ceil(max_val * 1.10)) if max_val > 0 else 1

    fig_ecoe = go.Figure()

    # Main spline area chart
    fig_ecoe.add_trace(go.Scatter(
        x=ecoe_month_counts['MonthLabel'],
        y=ecoe_month_counts['Homes Sold'],
        mode='lines+markers+text',
        line_shape='spline',          # smooth line
        fill='tozeroy',               # area under the line
        text=pct_text,                # visible % labels
        textposition='top center',
        cliponaxis=False,             # prevent first/last labels from being clipped
        hovertemplate='<b>%{x}</b><br>Homes Sold: %{y:,}<br>% of Total: %{text}<extra></extra>'
    ))

    # Layout + vertical dashed hover guide ending at datapoint
    fig_ecoe.update_layout(
        title='ECOE Distribution',
        title_font=dict(size=20),
        xaxis_title=None,
        height=150,
        margin=dict(t=50, r=0, b=0, l=40),
        hovermode='x',  # Snap hover to closest datapoint
        spikedistance=-1,
        hoverdistance=-1,
    )

    # Spikeline styling to end at datapoint
    fig_ecoe.update_xaxes(
    automargin=True,
    showspikes=True,
    spikemode='toaxis',       # <- was 'toaxis+across'; now stops at the datapoint
    spikesnap='data',         # snap to the nearest datapoint
    spikedash='dash',
    spikethickness=2,
    spikecolor='grey',
    hoverformat=''            # suppress x-axis hover label
)

    fig_ecoe.update_yaxes(title='Homes Sold', range=[0, y_max], automargin=True)

    st.plotly_chart(fig_ecoe, use_container_width=True)
else:
    st.info("No valid EST ECOE dates for this week's sales to display distribution.")
# <<< END INSERTED BLOCK >>>






# --- Existing Sales Week bar chart (unchanged) ---
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

    # --- Detail table (unchanged) ---
    sales_week_df['COE Year'] = sales_week_df['EST_COE_DATE'].dt.year
    sales_week_df['COE Month'] = sales_week_df['EST_COE_DATE'].dt.strftime('%b')
    display_cols = ['Hub', 'Community Name', 'Address', 'Plan Name', 'Investor Sale', 'NHC_NAME', 'SALE_DATE', 'BUYER_NAME', 'Realtor/Direct', 'COE Year', 'COE Month']
    display_cols_available = [col for col in display_cols if col in sales_week_df.columns]
    detailed_table = sales_week_df[display_cols_available].copy()
    if 'SALE_DATE' in detailed_table.columns:
        detailed_table['SALE_DATE'] = pd.to_datetime(detailed_table['SALE_DATE'], errors='coerce').dt.strftime('%b %d, %Y')
    detailed_table = detailed_table.rename(columns={'SALE_DATE': 'Sale Date','BUYER_NAME': 'Buyer','NHC_NAME': 'NHC Name'})
    st.dataframe(detailed_table, use_container_width=True, hide_index=True)
else:
    st.info("No data available for the selected week.")








