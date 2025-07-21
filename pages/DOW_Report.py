import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime

# --- Page setup ---
st.set_page_config(page_title="DOW Report", layout="wide")
st.title("Day of Week (DOW) Sales Report")

# --- Custom CSS for multi-select filter tags ---
st.markdown("""
    <style>
        .stMultiSelect [data-baseweb="tag"] {
            background-color: #1f77b4 !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- Check if processed MATT data is available in session ---
uploaded = 'matt_processed' in st.session_state
if not uploaded:
    st.warning("Please upload a valid MATT report on the MATT Upload page.")
    st.stop()

df = st.session_state['matt_processed']

# --- Sidebar filters ---
st.sidebar.header("Filters")

# Division filter
div_selection = st.sidebar.multiselect(
    "Division",
    options=df['DIV_CODE_DESC'].dropna().unique(),
    default=["HB Dallas-Fort Worth"],
    key="div_selection"
)

# Sale date range filter
most_recent_sunday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday() + 1)
sale_date_range = st.sidebar.date_input(
    "Sale Date Range",
    value=(datetime.date(2024, 9, 1), most_recent_sunday),
    key="sale_date_range"
)
if isinstance(sale_date_range, tuple) and len(sale_date_range) == 2:
    start_date = pd.to_datetime(sale_date_range[0])
    end_date = pd.to_datetime(sale_date_range[1])
else:
    st.error("Invalid date range selection.")
    st.stop()

# Investor sale filter with default set to Retail
investor_filter = st.sidebar.selectbox(
    "Investor Sale",
    options=["All", "Retail", "Investor"],
    index=["All", "Retail", "Investor"].index("Retail"),
    key="investor_filter"
)

# Realtor/Direct filter
cobroke_filter = st.sidebar.selectbox(
    "Realtor/Direct",
    options=["All", "Realtor", "Direct"],
    index=["All", "Realtor", "Direct"].index("All"),
    key="cobroke_filter"
)

# --- Apply filters to the dataset ---
mask = df['DIV_CODE_DESC'].isin(div_selection)
mask &= df['SALE_DATE'].between(pd.to_datetime(start_date), pd.to_datetime(end_date))
if investor_filter != "All":
    mask &= df['Investor Sale'] == investor_filter
if cobroke_filter != "All":
    mask &= df['Realtor/Direct'] == cobroke_filter
filtered_df = df[mask].copy()

# --- Stop if no data available ---
if filtered_df.empty or 'Weekday_Group' not in filtered_df.columns:
    st.warning("No data available for the selected filters.")
    st.stop()

# --- Waterfall chart: DOW Summary ---
dow_summary = (
    filtered_df.groupby('DOW_Sale')
    .agg(Sales=('DOW_Sale', 'count'))
    .reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    .fillna(0)
)
dow_summary['Sales %'] = 100 * dow_summary['Sales'] / dow_summary['Sales'].sum()
dow_summary['Running %'] = dow_summary['Sales %'].cumsum()

text_labels = [f"{round(val)}%" for val in dow_summary['Sales %']] + ["100%"]
custom_hover = [
    f"<b>{day}</b><br>Total Sales: {dow_summary.loc[day, 'Sales']}<br>Sales %: {round(dow_summary.loc[day, 'Sales %'], 1)}%"
    for day in dow_summary.index
] + [
    f"<b>Grand Total</b><br>Total Sales: {dow_summary['Sales'].sum()}<br>Sales %: 100%"
]

fig_waterfall = go.Figure(go.Waterfall(
    name="",
    orientation="v",
    measure=["relative"] * len(dow_summary) + ["total"],
    x=list(dow_summary.index) + ["Grand Total"],
    y=list(dow_summary['Sales %']) + [100],
    text=text_labels,
    textposition="inside",
    insidetextanchor="middle",
    textfont=dict(color="white", family="Arial", size=14),
    textangle=90,
    customdata=custom_hover,
    hovertemplate="%{customdata}<extra></extra>",
    connector={"line": {"color": "rgb(63, 63, 63)"}},
    showlegend=False
))
fig_waterfall.update_layout(title='DOW Sales Distribution', title_font=dict(size=20), yaxis_title='% of Weekly Sales')

# --- Monthly bar + line trend chart ---
filtered_df['Sales_Month'] = filtered_df['SALE_DATE'].dt.to_period('M')
dow_group = filtered_df.groupby(['Sales_Month', 'Weekday_Group']).size().unstack().fillna(0)
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
    name='Sales - M-F',
    customdata=dow_group[['M-F', 'Total']],
    hovertemplate='<b>%{x}</b><br>M-F Sales: %{customdata[0]}<br>Total Sales: %{customdata[1]}<extra></extra>'
))
fig_trend.add_trace(go.Bar(
    x=formatted_dates,
    y=dow_group['Sat-Sun'],
    name='Sales - Sat-Sun',
    customdata=dow_group[['Sat-Sun', 'Total']],
    hovertemplate='<b>%{x}</b><br>Sat-Sun Sales: %{customdata[0]}<br>Total Sales: %{customdata[1]}<extra></extra>'
))
fig_trend.add_trace(go.Scatter(
    x=formatted_dates,
    y=dow_group['M-F %'],
    mode='lines+markers+text',
    name='Sales % - M-F',
    yaxis='y2',
    text=[f"<b>{int(val)}%</b>" for val in dow_group['M-F %']],
    textposition="top center",
    hovertemplate='<b>%{x}</b><br>M-F %: %{y:.0f}%<extra></extra>'
))
fig_trend.add_trace(go.Scatter(
    x=formatted_dates,
    y=dow_group['Sat-Sun %'],
    mode='lines+markers',
    name='Sales % - Sat-Sun',
    yaxis='y2',
    hovertemplate='<b>%{x}</b><br>Sat-Sun %: %{y:.0f}%<extra></extra>'
))
fig_trend.update_layout(
    title='DOW Contribution to Sales',
    barmode='group',
    yaxis=dict(title='Total Sales'),
    yaxis2=dict(title='Sales %', overlaying='y', side='right', showgrid=False, range=[0, 100]),
    margin=dict(b=120),
    height=500,
    legend=dict(orientation="h", yanchor="top", y=-0.3, xanchor="center", x=0.5)
)

# --- Show charts side-by-side ---
col1, col2 = st.columns([1, 2])
with col1:
    st.plotly_chart(fig_waterfall, use_container_width=True)
with col2:
    st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")

# --- Weekly snapshot bar chart ---
most_recent_monday = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())
week_start = st.date_input("Select Week Start Date", most_recent_monday)
week_end = week_start + datetime.timedelta(days=6)

# Filter sales data by date range first
sales_week_df = df[df['SALE_DATE'].between(pd.to_datetime(week_start), pd.to_datetime(week_end))]

# Apply existing investor sale filter if not "All"
if investor_filter != "All":
    sales_week_df = sales_week_df[sales_week_df['Investor Sale'] == investor_filter]

total_sales = sales_week_df.shape[0]
st.subheader(f"Total Sales This Week: {total_sales}")

if not sales_week_df.empty:
    weekly_chart_data = sales_week_df.groupby(['SALE_DATE', 'Realtor/Direct']).size().reset_index(name='Homes Sold')
    weekly_chart_data['DateLabel'] = weekly_chart_data['SALE_DATE'].dt.strftime('%A<br>%m/%d/%Y')
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
        labels={'DateLabel': '', 'Homes Sold': 'Homes Sold'},
        custom_data=['Realtor/Direct', 'Homes Sold'],
        category_orders={'DateLabel': date_order}
    )
    fig_week.update_traces(textposition='inside', textfont=dict(size=16))
    fig_week.update_traces(hovertemplate='<b>%{x}</b><br>Realtor/Direct: %{customdata[0]}<br>Homes Sold: %{customdata[1]}<extra></extra>')

    fig_week.update_layout(
        xaxis=dict(tickfont=dict(size=16)),
        title_font=dict(size=20),
        legend_font=dict(size=16),
        font=dict(size=16),
        yaxis_title='Homes Sold',
        legend_title_text=''
    )
    st.plotly_chart(fig_week, use_container_width=True)

    # --- Detailed sales table for the selected week ---
    sales_week_df = sales_week_df.copy()  # Avoid SettingWithCopyWarning

    sales_week_df['COE Year'] = sales_week_df['EST_COE_DATE'].dt.year
    sales_week_df['COE Month'] = sales_week_df['EST_COE_DATE'].dt.strftime('%b')  # 3-letter month abbreviation

    display_cols = [
        'Hub',
        'Community Name',
        'Plan Name',
        'Investor Sale',
        'NHC_NAME',
        'SALE_DATE',
        'BUYER_NAME',
        'Realtor/Direct',
        'COE Year',
        'COE Month'
    ]

    display_cols_available = [col for col in display_cols if col in sales_week_df.columns]

    detailed_table = sales_week_df[display_cols_available].copy()

    if 'SALE_DATE' in detailed_table.columns:
        detailed_table['SALE_DATE'] = pd.to_datetime(detailed_table['SALE_DATE'], errors='coerce')
        detailed_table['SALE_DATE'] = detailed_table['SALE_DATE'].dt.strftime('%b %d, %Y')

    # Rename columns for display
    detailed_table = detailed_table.rename(columns={
        'SALE_DATE': 'Sale Date',
        'BUYER_NAME': 'Buyer',
        'NHC_NAME': 'NHC Name'
    })

    st.dataframe(detailed_table, use_container_width=True, hide_index=True)

else:
    st.info("No data available for the selected week.")








