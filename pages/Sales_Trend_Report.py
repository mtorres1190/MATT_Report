import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="Sales Trend Report", layout="wide")
st.title("Sales Trend Report")

st.markdown("""
    <style>
        .stMultiSelect [data-baseweb=\"tag\"] {
            background-color: #1f77b4 !important;
        }
    </style>
""", unsafe_allow_html=True)

# Ensure processed data is available
if 'matt_processed' not in st.session_state:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed'].copy()

# Inline filters
st.sidebar.header("Filters")

div_selection = st.sidebar.multiselect(
    "Division",
    options=df['DIV_CODE_DESC'].dropna().unique(),
    default=["HB Dallas-Fort Worth"],
    key="trend_div_selection"
)

sale_date_range = st.sidebar.date_input(
    "Sale Date Range",
    value=(datetime.date(2024, 9, 1), datetime.date.today() - datetime.timedelta(days=1)),
    key="trend_sale_date_range"
)

investor_filter = st.sidebar.selectbox(
    "Investor Sale",
    options=["All", "Retail", "Investor"],
    index=["All", "Retail", "Investor"].index("Retail"),
    key="trend_investor_filter"
)

if isinstance(sale_date_range, tuple) and len(sale_date_range) == 2:
    start_date = pd.to_datetime(sale_date_range[0])
    end_date = pd.to_datetime(sale_date_range[1])
else:
    st.error("Invalid date range selection.")
    st.stop()

# Apply filter mask
mask = df['DIV_CODE_DESC'].isin(div_selection)
mask &= df['SALE_DATE'].between(start_date, end_date)
if investor_filter != "All":
    mask &= df['Investor Sale'] == investor_filter
filtered_df = df[mask]

# Exit if no data
if filtered_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# Drop NA sale dates
filtered_df = filtered_df.dropna(subset=['SALE_DATE'])

# --- Avg. Daily Sales Trend Chart ---
daily_sales = filtered_df.groupby('SALE_DATE').size()
daily_sales_ma14 = daily_sales.rolling(window=14).mean()
daily_sales_ma30 = daily_sales.rolling(window=30).mean()

fig_avg_daily = go.Figure()
fig_avg_daily.add_trace(go.Scatter(
    x=daily_sales.index,
    y=daily_sales_ma14,
    mode='lines',
    line=dict(color='steelblue', width=2),
    name='Daily Sales 14DMA',
    hovertemplate='%{x|%b %d, %Y}<br>14DMA: %{y:.1f}<extra></extra>'
))
fig_avg_daily.add_trace(go.Scatter(
    x=daily_sales.index,
    y=daily_sales_ma30,
    mode='lines',
    line=dict(color='steelblue', width=2, dash='dot'),
    name='Daily Sales 30DMA',
    hovertemplate='%{x|%b %d, %Y}<br>30DMA: %{y:.1f}<extra></extra>'
))
fig_avg_daily.update_layout(
    title=dict(text="Avg. Daily Sales Trend", font=dict(size=20)),
    xaxis=dict(title=dict(text="Date", font=dict(size=16)), showgrid=True, tickfont=dict(size=14)),
    yaxis=dict(title=dict(text="Avg. Daily Sales", font=dict(size=16)), showgrid=True, tickfont=dict(size=14)),
    hovermode="x unified",
    height=500,
    margin=dict(t=60, b=40, l=60, r=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5, font=dict(size=14))
)
st.plotly_chart(fig_avg_daily, use_container_width=True)

# --- RAR Plot ---
daily_summary = filtered_df.groupby(['SALE_DATE', 'Realtor/Direct']).size().unstack(fill_value=0)
daily_summary['Total Sales'] = daily_summary.sum(axis=1)
daily_summary['Realtor %'] = daily_summary.get('Realtor', 0) / daily_summary['Total Sales']
daily_summary['14d_MA_RAR'] = daily_summary['Realtor %'].rolling(window=14).mean()

fig_rar = go.Figure()
fig_rar.add_trace(go.Scatter(
    x=daily_summary.index,
    y=daily_summary['14d_MA_RAR'],
    mode='lines',
    line=dict(color='orangered', width=2),
    name='14 per. Mov. Avg. (RAR)',
    hovertemplate='%{x|%b %d, %Y}<br>RAR: %{y:.1%}<extra></extra>'
))
fig_rar.update_layout(
    title=dict(text="Realtor Attachment Rate", font=dict(size=20)),
    xaxis=dict(title=dict(text="Date", font=dict(size=16)), showgrid=True, tickfont=dict(size=14)),
    yaxis=dict(title=dict(text="Realtor Attachment Rate", font=dict(size=16)), showgrid=True, range=[0.3, 1.0], tickformat=".0%", tickfont=dict(size=14)),
    hovermode="x unified",
    height=500,
    margin=dict(t=60, b=40, l=60, r=20),
    legend=dict(font=dict(size=14))
)
st.plotly_chart(fig_rar, use_container_width=True)

# --- Direct vs Realtor Volume Plot ---
volume_df = filtered_df.groupby(['SALE_DATE', 'Realtor/Direct']).size().unstack(fill_value=0)
volume_df['Direct MA'] = volume_df.get('Direct', 0).rolling(window=14).mean()
volume_df['Realtor MA'] = volume_df.get('Realtor', 0).rolling(window=14).mean()

fig_vol = go.Figure()
fig_vol.add_trace(go.Scatter(
    x=volume_df.index,
    y=volume_df['Direct MA'],
    mode='lines',
    line=dict(color='steelblue', width=2),
    name='Direct 14DMA',
    hovertemplate='%{x|%b %d, %Y}<br>Direct Sales Avg: %{y:.1f}<extra></extra>'
))
fig_vol.add_trace(go.Scatter(
    x=volume_df.index,
    y=volume_df['Realtor MA'],
    mode='lines',
    line=dict(color='darkorange', width=2),
    name='Realtor 14DMA',
    hovertemplate='%{x|%b %d, %Y}<br>Realtor Sales Avg: %{y:.1f}<extra></extra>'
))
fig_vol.update_layout(
    title=dict(text="Direct vs. Realtor Sales", font=dict(size=20)),
    xaxis=dict(title=dict(text="Date", font=dict(size=16)), showgrid=True, tickfont=dict(size=14)),
    yaxis=dict(title=dict(text="Avg. Daily Sales", font=dict(size=16)), showgrid=True, tickfont=dict(size=14)),
    hovermode="x unified",
    height=500,
    margin=dict(t=60, b=40, l=60, r=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5, font=dict(size=14))
)
st.plotly_chart(fig_vol, use_container_width=True)


