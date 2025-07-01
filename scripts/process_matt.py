import pandas as pd
import numpy as np
import os
import datetime
import streamlit as st

# --- Color Map for Homesite Status ---
color_map = {
    'Model': '#ffb6c1',       # Light Pink
    'Closed': '#ff4136',      # Red
    'Unsold': '#87cefa',      # Light Blue
    'Backlog': '#1f77b4',     # Dark Blue
    'Grand Total': '#E5ECF6'  # Light Gray for totals
}

# --- Main Data Processing Function ---
def process_matt_data(matt_df: pd.DataFrame) -> pd.DataFrame:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hub_path = os.path.join(base_dir, 'data', 'Hub.csv')
    plan_path = os.path.join(base_dir, 'data', 'Plan.csv')

    hub_df = pd.read_csv(hub_path)
    plan_df = pd.read_csv(plan_path)

    # Merge Hub and Plan details
    matt_df['Comm_#'] = matt_df['COMMUNITY'].astype(str).str[:5].astype(int)

    # Normalize PLAN_CODE types for matching
    matt_df['PLAN_CODE'] = matt_df['PLAN_CODE'].astype(str).str.strip().str.replace('.0', '', regex=False)
    plan_df['Plan Code'] = plan_df['Plan Code'].astype(str).str.strip()

    merged_df = pd.merge(matt_df, hub_df, how='left', left_on='Comm_#', right_on='Community Number')
    merged_df = pd.merge(merged_df, plan_df, how='left', left_on='PLAN_CODE', right_on='Plan Code')

    merged_df.rename(columns={
        'Community Name': 'Community Name',
        'Hub': 'Hub',
        'Plan Name': 'Plan Name',
        'Collection': 'Collection',
        'Core': 'Core',
        'Textbox4': 'HS_TYPE',
        'Textbox22': 'NET SALES PRICE'
    }, inplace=True)

    # Normalize Hub and Community names to uppercase
    merged_df['Hub'] = merged_df['Hub'].astype(str).str.strip()
    merged_df['Community Name'] = merged_df['Community Name'].astype(str).str.strip()

    # Do not uppercase Plan Name to preserve original formatting
    merged_df['Plan Name'] = merged_df['Plan Name'].astype(str).str.strip()

    # Date conversions
    merged_df['SALE_DATE'] = pd.to_datetime(merged_df['SALE_DATE'], errors='coerce')
    merged_df['EST_COE_DATE'] = pd.to_datetime(merged_df['EST_COE_DATE'], errors='coerce')

    # Weekday groups
    merged_df['DOW_Sale'] = merged_df['SALE_DATE'].dt.day_name()
    merged_df['Weekday_Group'] = np.where(
        merged_df['DOW_Sale'].isin(['Saturday', 'Sunday']), 'Sat-Sun', 'M-F'
    )

    # Investor Sale flag
    investor_names = {
        "Chanin, Kristian                   (DFW)",
        "PEREZ, LARRY",
        "Perez, Larry                       (DFW)",
        "Stierwalt, Tanner                  (DFW)",
        "Krueger, Cole                      (HOU)",
        "Shackelford, Leah                  (HOU)",
        "Batchelor, Christina               (HOU)"
    }
    merged_df['Investor Sale'] = merged_df['NHC_NAME'].apply(
        lambda x: "Investor" if x in investor_names else "Retail"
    )

    # Cancellation date parsing
    merged_df['SALES_CANCELLATION_DATE'] = merged_df['SALES_CANCELLATION_DATE'].astype(str).str.strip()
    merged_df['SALES_CANCELLATION_DATE_PARSED'] = pd.to_datetime(
        merged_df['SALES_CANCELLATION_DATE'], errors='coerce'
    )

    # Realtor/Direct flag
    merged_df['Realtor/Direct'] = merged_df['COBROKE_Y_N'].fillna('').apply(map_realtor_direct)

    # HS_TYPE label mapping
    status_map = {
        'B': 'Backlog',
        'S': 'Unsold',
        'Z': 'Closed',
        'M': 'Model'
    }
    merged_df['HS_TYPE_LABEL'] = merged_df['HS_TYPE'].map(status_map).fillna(merged_df['HS_TYPE'])

    return merged_df

# --- Realtor/Direct Mapper ---
def map_realtor_direct(cobroke_value):
    mapping = {'Y': 'Realtor', '': 'Direct', None: 'Direct'}
    return mapping.get(cobroke_value, 'Direct')

# --- Plan-Level Pricing Aggregation for Sold Homes ---
from typing import Union

def compute_plan_pricing(df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp, group_col: Union[str, list[str]] = "Plan Name") -> pd.DataFrame:
    df = df.copy()
    df['SALE_DATE'] = pd.to_datetime(df['SALE_DATE'], errors='coerce')
    df = df[(df['SALE_DATE'] >= start_date) & (df['SALE_DATE'] <= end_date)]

    # Clean and convert monetary fields
    cols_to_clean = ['BASE_PRICE', 'HOMESITE_PREMIUM', 'PRICE_REDUCTION_INCENTIVES', 'OPTION_REVENUE', 'NET SALES PRICE']
    for col in cols_to_clean:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['List Price'] = (
        df['BASE_PRICE'] +
        df['HOMESITE_PREMIUM'] +
        df['PRICE_REDUCTION_INCENTIVES'] +
        df['OPTION_REVENUE']
    )

    group_keys = group_col if isinstance(group_col, list) else [group_col]
    summary = df.groupby(group_keys, as_index=False).agg({
        'BASE_PRICE': 'mean',
        'List Price': 'mean',
        'NET SALES PRICE': 'mean',
        'TOTAL_SQFT': 'mean'
    })

    summary.rename(columns={
        'BASE_PRICE': 'Avg Base Price',
        'List Price': 'Avg List Price',
        'NET SALES PRICE': 'Avg Net Revenue',
        'TOTAL_SQFT': 'Avg SqFt'
    }, inplace=True)

    summary.sort_values(by='Avg SqFt', inplace=True)
    return summary

# --- Snapshot Unsold Inventory Calculator ---
def compute_snapshot_unsold_inventory(df, group_col, snapshot_date, coe_start, coe_end, label):
    snapshot_date = pd.to_datetime(snapshot_date)
    coe_start = pd.to_datetime(coe_start)
    coe_end = pd.to_datetime(coe_end)
    snapshot_df = df[
        ((df['SALE_DATE'].isna()) | (df['SALE_DATE'] > snapshot_date)) &
        (df['EST_COE_DATE'] >= coe_start) &
        (df['EST_COE_DATE'] <= coe_end)
    ].copy()
    snapshot_df['Age'] = (snapshot_df['EST_COE_DATE'] - snapshot_date).dt.days
    result = snapshot_df.groupby(group_col).agg(
        Unsold=('EST_COE_DATE', 'count'),
        Avg_Age=('Age', 'mean')
    ).reset_index()
    result['Week'] = label
    return result

# --- Pace vs. Margin Calculator ---
def compute_pace_vs_margin(df: pd.DataFrame, target_date: datetime.date, coe_start: datetime.date, coe_end: datetime.date) -> tuple[pd.DataFrame, float]:
    today = datetime.date.today()
    df['EST_COE_DATE'] = pd.to_datetime(df['EST_COE_DATE'], errors='coerce')
    df['SALE_DATE'] = pd.to_datetime(df['SALE_DATE'], errors='coerce')

    unsold_df = df[
        (df['HS_TYPE'] == 'S') &
        (df['EST_COE_DATE'] >= pd.Timestamp(coe_start)) &
        (df['EST_COE_DATE'] <= pd.Timestamp(coe_end))
    ]

    three_weeks_ago = pd.Timestamp(today - datetime.timedelta(days=21))
    sold_df = df[(df['HS_TYPE'].isin(['B', 'Z'])) & (df['SALE_DATE'] >= three_weeks_ago)]
    pace = sold_df.groupby('Community Name').size() / 3

    weeks_left = (target_date - today).days / 7
    slope = 1 / weeks_left if weeks_left > 0 else 0
    unsold_counts = unsold_df.groupby('Community Name').size()

    summary = pd.DataFrame({
        'Unsold': unsold_counts,
        '3Wk Avg Sales Pace': pace
    }).fillna(0)

    summary['Needed Pace'] = summary['Unsold'] / weeks_left
    summary['Delta'] = summary['3Wk Avg Sales Pace'] - summary['Needed Pace']

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

# --- Exports ---
__all__ = [
    "compute_snapshot_unsold_inventory",
    "compute_pace_vs_margin",
    "process_matt_data",
    "map_realtor_direct",
    "compute_plan_pricing",
    "color_map"
]
