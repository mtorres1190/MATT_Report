import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import math

# ======================================================================================
# PAGE SETUP
# ======================================================================================

st.set_page_config(page_title="DOW Report", layout="wide")
st.title("Day of Week (DOW) Sales Report")

st.markdown("""
<style>

/* Multiselect styling */
.stMultiSelect [data-baseweb="tag"] {
    background-color: #1f77b4 !important;
}

/* Existing custom classes */
.chart-title {
    font-size: 20px !important;
    font-weight: bold !important;
}

.week-start-label {
    font-size: 20px !important;
    font-weight: bold !important;
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

# --- Check if processed MATT data is available ---
if 'matt_processed' not in st.session_state:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed'].copy()

# ======================================================================================
# Sidebar filters — CASCADING, DATA-AWARE OPTIONS
# ======================================================================================
with st.sidebar:
    st.header("Filters")

    most_recent_sunday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday() + 1)

    sale_date_range = st.date_input(
        "Sale Date Range",
        value=(datetime.date(2025, 9, 1), most_recent_sunday)
    )

    if not isinstance(sale_date_range, tuple) or len(sale_date_range) != 2:
        st.error("Invalid date range selection.")
        st.stop()

    start_date = pd.to_datetime(sale_date_range[0])
    end_date = pd.to_datetime(sale_date_range[1])

    df_base = df.copy()

    # Division
    div_options = sorted(df_base['DIV_CODE_DESC'].dropna().astype(str).unique())
    div_selection = st.multiselect("Division", options=div_options, default=[])
    div_selected = div_selection if div_selection else div_options
    df_div = df_base.loc[df_base['DIV_CODE_DESC'].isin(div_selected)].copy()

    # Hub
    hub_options = sorted(df_div['Hub'].dropna().astype(str).unique())
    selected_hubs = st.multiselect("Hub", options=hub_options, default=[])
    hubs = selected_hubs if selected_hubs else hub_options
    df_hub = df_div.loc[df_div['Hub'].isin(hubs)].copy()

    # Community
    community_options = sorted(df_hub['Community Name'].dropna().astype(str).unique())
    selected_communities = st.multiselect("Community Name", options=community_options, default=[])
    communities = selected_communities if selected_communities else community_options
    df_comm = df_hub.loc[df_hub['Community Name'].isin(communities)].copy()

    # Investor
    if 'Investor Sale' in df_comm.columns:
        investor_options = sorted(df_comm['Investor Sale'].dropna().astype(str).unique())
        investor_options = [opt for opt in investor_options if not df_comm.loc[df_comm['Investor Sale'] == opt].empty]
    else:
        investor_options = []

    default_index = 0
    if "Retail" in investor_options:
        default_index = (["All"] + investor_options).index("Retail")

    investor_filter = st.selectbox("Investor Sale", ["All"] + investor_options, index=default_index)
    df_inv = df_comm.copy()
    if investor_filter != "All":
        df_inv = df_inv.loc[df_inv['Investor Sale'] == investor_filter].copy()

    # Realtor / Direct
    if 'Realtor/Direct' in df_inv.columns:
        rd_options = sorted(df_inv['Realtor/Direct'].dropna().astype(str).unique())
        rd_options = [opt for opt in rd_options if not df_inv.loc[df_inv['Realtor/Direct'] == opt].empty]
    else:
        rd_options = []

    cobroke_filter = st.selectbox("Realtor/Direct", ["All"] + rd_options, index=0)
    df_final = df_inv.copy()
    if cobroke_filter != "All":
        df_final = df_final.loc[df_final['Realtor/Direct'] == cobroke_filter].copy()

# ======================================================================================
# Safe Date Filter for DOW Charts
# ======================================================================================

df_dow = df_final.loc[
    df_final['SALE_DATE'].notna() &
    (df_final['SALE_DATE'] >= start_date) &
    (df_final['SALE_DATE'] <= end_date)
].copy()

# ======================================================================================
# DOW Charts
# ======================================================================================

if not df_dow.empty and 'Weekday_Group' in df_dow.columns:

    dow_summary = (
        df_dow.groupby('DOW_Sale')
        .agg(Sales=('DOW_Sale', 'count'))
        .reindex(['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'])
        .fillna(0)
    )

    if dow_summary['Sales'].sum() == 0:
        st.warning("No data available for the selected filters.")
    else:
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
            hovertemplate="<b>%{x}</b><br>Share: %{y:.0f}%<br>Sales: %{customdata:,}<extra></extra>"
        ))

        fig_waterfall.update_layout(
            title='DOW Sales Distribution',
            title_font=dict(size=20),
            yaxis_title='% of Weekly Sales',
            height=450
        )

        # Monthly Trend
        df_dow['Sales_Month'] = df_dow['SALE_DATE'].dt.to_period('M')
        dow_group = df_dow.groupby(['Sales_Month','Weekday_Group']).size().unstack().fillna(0)

        dow_group['M-F'] = dow_group.get('M-F',0)
        dow_group['Sat-Sun'] = dow_group.get('Sat-Sun',0)
        dow_group['Total'] = dow_group.sum(axis=1)

        dow_group['M-F %'] = (dow_group['M-F'] / dow_group['Total'] * 100).round(0)
        dow_group['Sat-Sun %'] = (dow_group['Sat-Sun'] / dow_group['Total'] * 100).round(0)

        formatted_dates = [p.to_timestamp().strftime('%b, %Y') for p in dow_group.index]

        fig_trend = go.Figure()

        fig_trend.add_trace(go.Bar(
            x=formatted_dates,
            y=dow_group['M-F'],
            name='M-F Sales'
        ))

        fig_trend.add_trace(go.Bar(
            x=formatted_dates,
            y=dow_group['Sat-Sun'],
            name='Sat-Sun Sales'
        ))

        fig_trend.add_trace(go.Scatter(
            x=formatted_dates,
            y=dow_group['M-F %'],
            mode='lines+markers+text',
            name='Sales % - M-F',
            yaxis='y2',
            text=[f"{int(val)}%" for val in dow_group['M-F %']],
            textposition="top center"
        ))

        fig_trend.add_trace(go.Scatter(
            x=formatted_dates,
            y=dow_group['Sat-Sun %'],
            mode='lines+markers',
            name='Sales % - Sat-Sun',
            yaxis='y2'
        ))

        fig_trend.update_layout(
            title='DOW Contribution to Sales',
            title_font=dict(size=20),
            barmode='group',
            height=480,  # <-- Adjust this value as desired
            yaxis=dict(title='Total Sales'),
            yaxis2=dict(
                title='Sales %',
                overlaying='y',
                side='right',
                range=[0,100],
                showgrid=False
            ),
            hovermode='closest',
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.3,
                xanchor="center",
                x=0.5
            )
        )

        col1, col2 = st.columns([1,2])
        with col1:
            st.plotly_chart(fig_waterfall, use_container_width=True)
        with col2:
            st.plotly_chart(fig_trend, use_container_width=True)

else:
    st.warning("No data available for the selected filters.")

st.markdown("---")

# ======================================================================================
# Week-Based Section
# ======================================================================================

most_recent_monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
st.markdown('<div class="week-start-label">Select Week Start Date</div>', unsafe_allow_html=True)

week_start = st.date_input("Select Week Start Date", most_recent_monday, label_visibility="collapsed")
week_end = week_start + datetime.timedelta(days=6)

sales_week_df = df_final.loc[
    df_final['SALE_DATE'].notna() &
    df_final['SALE_DATE'].between(pd.to_datetime(week_start), pd.to_datetime(week_end))
].copy()

total_sales = sales_week_df.shape[0]
st.subheader(f"Total Sales This Week: {total_sales}")

if not sales_week_df.empty:

    # ==================================================================================
    # ECOE Distribution
    # ==================================================================================

    ecoe_week_df = sales_week_df.dropna(subset=['EST_COE_DATE']).copy()

    if not ecoe_week_df.empty and total_sales > 0:

        ecoe_week_df['ECOE_Month_Period'] = pd.to_datetime(
            ecoe_week_df['EST_COE_DATE'],
            errors='coerce'
        ).dt.to_period('M')

        ecoe_month_counts = (
            ecoe_week_df.groupby('ECOE_Month_Period')
            .size()
            .reset_index(name='Homes Sold')
            .sort_values('ECOE_Month_Period')
        )

        ecoe_month_counts['MonthLabel'] = ecoe_month_counts['ECOE_Month_Period'] \
            .dt.to_timestamp().dt.strftime('%b %Y')

        ecoe_month_counts['Pct of Total'] = (
            ecoe_month_counts['Homes Sold'] / total_sales * 100
        ).round(0).astype(int)

        max_val = int(ecoe_month_counts['Homes Sold'].max()) if not ecoe_month_counts.empty else 0

        # Add extra headroom (25%) so labels never clip
        y_max = int(math.ceil(max_val * 1.25)) if max_val > 0 else 1

        fig_ecoe = go.Figure()

        fig_ecoe.add_trace(go.Scatter(
            x=ecoe_month_counts['MonthLabel'],
            y=ecoe_month_counts['Homes Sold'],
            mode='lines+markers+text',
            line=dict(shape='spline', smoothing=1.2),  # <-- Smoothed line
            marker=dict(size=8),
            fill='tozeroy',
            text=[f"{p}%" for p in ecoe_month_counts['Pct of Total']],
            textposition='top center'
        ))

        fig_ecoe.update_layout(
            title='ECOE Distribution',
            title_font=dict(size=20),
            height=260,  # Increased height
            margin=dict(
                t=90,  # Increased top padding
                r=20,
                b=40,
                l=50
            )
        )

        fig_ecoe.update_yaxes(
            title='Homes Sold',
            range=[0, y_max]
        )

        st.plotly_chart(fig_ecoe, use_container_width=True)



    # Weekly Sales Chart
    weekly_chart_data = sales_week_df.groupby(['SALE_DATE','Realtor/Direct']).size().reset_index(name='Homes Sold')
    weekly_chart_data['DateLabel'] = weekly_chart_data['SALE_DATE'].dt.strftime('%A<br>%m/%d/%Y')

    fig_week = px.bar(
        weekly_chart_data,
        x='DateLabel',
        y='Homes Sold',
        color='Realtor/Direct',
        text='Homes Sold',
        barmode='stack',
        title='Sales Week'
    )

    fig_week.update_layout(
        title_font=dict(size=20),
        font=dict(size=16),
        xaxis=dict(title=None),
        yaxis=dict(title='Homes Sold')
    )

    st.plotly_chart(fig_week, use_container_width=True)

    # ==================================================================================
    # Weekly Detail Table
    # ==================================================================================

    st.markdown("### Weekly Sales Detail")

    detail_df = sales_week_df.copy()

    # ----------------------------------------------------------------------------------
    # Ensure correct column names based on process_matt.py structure
    # ----------------------------------------------------------------------------------

    # Homesite Address comes from 'Address'
    if 'Address' in detail_df.columns:
        detail_df['Homesite Address'] = detail_df['Address']

    # NHC Name comes from 'NHC_NAME'
    if 'NHC_NAME' in detail_df.columns:
        detail_df['NHC Name'] = detail_df['NHC_NAME']

    # ----------------------------------------------------------------------------------
    # Create ECOE Month column
    # ----------------------------------------------------------------------------------

    detail_df['ECOE Month'] = pd.to_datetime(
        detail_df['EST_COE_DATE'],
        errors='coerce'
    ).dt.to_period('M').dt.to_timestamp()

    detail_df['ECOE Month'] = pd.to_datetime(
        detail_df['ECOE Month'],
        errors='coerce'
    ).dt.strftime('%b %Y')

    # ----------------------------------------------------------------------------------
    # Format Sale Date
    # ----------------------------------------------------------------------------------

    detail_df['Sale Date'] = pd.to_datetime(
        detail_df['SALE_DATE'],
        errors='coerce'
    ).dt.strftime('%m/%d/%Y')

    # ----------------------------------------------------------------------------------
    # Select and order columns
    # ----------------------------------------------------------------------------------

    detail_columns = [
        'Hub',
        'Community Name',
        'Collection',
        'Plan Name',
        'Homesite Address',
        'NHC Name',
        'Sale Date',
        'ECOE Month',
        'Realtor/Direct',
        'Investor Sale'
    ]

    # Keep only columns that actually exist (defensive programming)
    existing_columns = [col for col in detail_columns if col in detail_df.columns]
    detail_df = detail_df[existing_columns].copy()

    # ----------------------------------------------------------------------------------
    # Sort newest sales first (using actual datetime column before formatting)
    # ----------------------------------------------------------------------------------

    if 'SALE_DATE' in sales_week_df.columns:
        detail_df = detail_df.assign(
            _sort_date=pd.to_datetime(sales_week_df['SALE_DATE'], errors='coerce')
        ).sort_values(by='_sort_date', ascending=False).drop(columns=['_sort_date'])

    # ----------------------------------------------------------------------------------
    # Remove index column in Streamlit display
    # ----------------------------------------------------------------------------------

    detail_df.reset_index(drop=True, inplace=True)

    st.dataframe(detail_df, use_container_width=True, hide_index=True)
