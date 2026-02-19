import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime

# ======================================================================================
# PAGE SETUP
# ======================================================================================

st.set_page_config(page_title="Sales Trend Report", layout="wide")
st.title("Sales Trend Report")

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

# --- Ensure data is available ---
if 'matt_processed' not in st.session_state:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed'].copy()

# --- Sidebar Printable Mode Toggle ---
st.sidebar.header("Printable Mode")
printable_mode = st.sidebar.radio("Select Mode", ["Off", "On"], index=0, label_visibility="collapsed")

# --- Sidebar filters ---
st.sidebar.header("Filters")

div_selection = st.sidebar.multiselect(
    "Division",
    options=df['DIV_CODE_DESC'].dropna().unique(),
    default=["HB Dallas-Fort Worth"],
    key="trend_div_selection"
)

sale_date_range = st.sidebar.date_input(
    "Sale Date Range",
    value=(datetime.date(2025, 9, 1), datetime.date.today() - datetime.timedelta(days=1)),
    key="trend_sale_date_range"
)

investor_filter = st.sidebar.selectbox(
    "Investor Sale",
    options=["All", "Retail", "Investor"],
    index=["All", "Retail", "Investor"].index("Retail"),
    key="trend_investor_filter"
)

# --- New Hub and Community Name filters ---
df_div = df[df['DIV_CODE_DESC'].isin(div_selection)]
hub_options = sorted(df_div['Hub'].dropna().unique())
selected_hubs = st.sidebar.multiselect("Hub", options=hub_options, key="trend_hubs")
hubs = selected_hubs if selected_hubs else hub_options

df_hub = df_div[df_div['Hub'].isin(hubs)]
community_options = sorted(df_hub['Community Name'].dropna().unique())
selected_communities = st.sidebar.multiselect("Community Name", options=community_options, key="trend_communities")
communities = selected_communities if selected_communities else community_options

# --- Validate and apply filters ---
if isinstance(sale_date_range, tuple) and len(sale_date_range) == 2:
    start_date = pd.to_datetime(sale_date_range[0])
    end_date = pd.to_datetime(sale_date_range[1])
else:
    st.error("Invalid date range selection.")
    st.stop()

mask = df['DIV_CODE_DESC'].isin(div_selection)
mask &= df['SALE_DATE'].between(start_date, end_date)
mask &= df['Hub'].isin(hubs)
mask &= df['Community Name'].isin(communities)
if investor_filter != "All":
    mask &= df['Investor Sale'] == investor_filter

filtered_df = df[mask].dropna(subset=['SALE_DATE'])

if filtered_df.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- Function for consistent printable label formatting ---
def add_printable_annotation(fig, x_val, y_val, text):
    fig.add_annotation(
        x=x_val,
        y=y_val,
        text=text,
        showarrow=True,
        arrowhead=2,
        ax=40,
        ay=-40,
        arrowcolor="lightgrey",
        bordercolor="lightgrey",
        borderwidth=1,
        borderpad=4,
        bgcolor="white",
        font=dict(size=12),
        opacity=0.95
    )

# --- Helper: Generate footnote ---
def generate_footnote():
    investor_label = (
        "Investor Sales" if investor_filter == "Investor"
        else "Retail Sales" if investor_filter == "Retail"
        else "Investor & Retail Sales"
    )
    return f"Source: {', '.join(div_selection)} | {start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')} | {investor_label}"

# --- Daily Sales Trend Chart ---
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

if printable_mode == "On" and not daily_sales_ma14.dropna().empty:
    add_printable_annotation(fig_avg_daily, daily_sales_ma14.dropna().index[-1], daily_sales_ma14.dropna().iloc[-1], f"Avg: {daily_sales_ma14.dropna().iloc[-1]:.1f}")

fig_avg_daily.update_layout(
    title=dict(text="Avg. Daily Sales Trend", font=dict(size=20)),
    xaxis=dict(title="Date", showgrid=True, tickfont=dict(size=14)),
    yaxis=dict(title="Avg. Daily Sales", showgrid=True, tickfont=dict(size=14)),
    hovermode="x unified",
    height=500,
    margin=dict(t=60, b=40, l=60, r=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5, font=dict(size=14))
)
st.plotly_chart(fig_avg_daily, use_container_width=True)
if printable_mode == "On":
    st.markdown(f"<div style='font-size:18px; color:gray; text-align:left; margin-top:-10px;'>{generate_footnote()}</div>", unsafe_allow_html=True)

# --- Realtor Attachment Rate Chart ---
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

if printable_mode == "On" and not daily_summary['14d_MA_RAR'].dropna().empty:
    add_printable_annotation(fig_rar, daily_summary['14d_MA_RAR'].dropna().index[-1], daily_summary['14d_MA_RAR'].dropna().iloc[-1], f"Avg: {daily_summary['14d_MA_RAR'].dropna().iloc[-1]:.1%}")

fig_rar.update_layout(
    title=dict(text="Realtor Attachment Rate", font=dict(size=20)),
    xaxis=dict(title="Date", showgrid=True, tickfont=dict(size=14)),
    yaxis=dict(title="Realtor Attachment Rate", showgrid=True, range=[0.3, 1.0], tickformat=".0%", tickfont=dict(size=14)),
    hovermode="x unified",
    height=500,
    margin=dict(t=60, b=40, l=60, r=20),
    legend=dict(font=dict(size=14))
)
st.plotly_chart(fig_rar, use_container_width=True)
if printable_mode == "On":
    st.markdown(f"<div style='font-size:18px; color:gray; text-align:left; margin-top:-10px;'>{generate_footnote()}</div>", unsafe_allow_html=True)

# --- Direct vs. Realtor Volume Chart ---
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

if printable_mode == "On" and not volume_df['Direct MA'].dropna().empty:
    add_printable_annotation(fig_vol, volume_df['Direct MA'].dropna().index[-1], volume_df['Direct MA'].dropna().iloc[-1], f"D Avg: {volume_df['Direct MA'].dropna().iloc[-1]:.1f}")
    if not volume_df['Realtor MA'].dropna().empty:
        add_printable_annotation(fig_vol, volume_df['Realtor MA'].dropna().index[-1], volume_df['Realtor MA'].dropna().iloc[-1], f"R Avg: {volume_df['Realtor MA'].dropna().iloc[-1]:.1f}")

fig_vol.update_layout(
    title=dict(text="Direct vs. Realtor Sales", font=dict(size=20)),
    xaxis=dict(title="Date", showgrid=True, tickfont=dict(size=14)),
    yaxis=dict(title="Avg. Daily Sales", showgrid=True, tickfont=dict(size=14)),
    hovermode="x unified",
    height=500,
    margin=dict(t=60, b=40, l=0, r=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5, font=dict(size=14))
)
st.plotly_chart(fig_vol, use_container_width=True)
if printable_mode == "On":
    st.markdown(f"<div style='font-size:18px; color:gray; text-align:left; margin-top:-10px;'>{generate_footnote()}</div>", unsafe_allow_html=True)
