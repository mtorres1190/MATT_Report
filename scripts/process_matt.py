import pandas as pd
import numpy as np
import os
import datetime
import streamlit as st

# --- Constants & Mapping Dictionaries ---
# Color coding for homesite status visualization
color_map = {
    'Model': '#ffb6c1',
    'Closed': '#ff4136',
    'Unsold': '#87cefa',
    'Backlog': '#1f77b4',
    'Grand Total': '#E5ECF6'
}

# Map HS_TYPE codes to descriptive labels
status_map = {
    'B': 'Backlog',
    'S': 'Unsold',
    'Z': 'Closed',
    'M': 'Model'
}

# List of NHC names associated with investor sales
investor_names = {
    "Chanin, Kristian                   (DFW)",
    "PEREZ, LARRY",
    "LAWRENCE PETER                          ",
    "Perez, Larry                       (DFW)",
    "Stierwalt, Tanner                  (DFW)",
    "Krueger, Cole                      (HOU)",
    "Shackelford, Leah                  (HOU)",
    "Batchelor, Christina               (HOU)"
}

# --- Helper Functions ---
# Strip whitespace from string columns
def clean_strings(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df

# Convert columns to datetime
def parse_dates(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

# Map cobroke values to Realtor/Direct flag
def map_realtor_direct(cobroke_value):
    mapping = {'Y': 'Realtor', '': 'Direct', None: 'Direct'}
    return mapping.get(cobroke_value, 'Direct')

# --- Main Processing Function ---
def process_matt_data(matt_df: pd.DataFrame) -> pd.DataFrame:
    # 1. Column Renaming & Initial Cleanup
    matt_df = matt_df.rename(columns={
        'Textbox4': 'HS_TYPE',
        'Textbox22': 'Net_Sales_Price'
    })
    clean_strings(matt_df, matt_df.columns)
    # Create cleaned Address column if present
    if 'HOMESITE_ADDRESS1' in matt_df.columns:
        matt_df['Address'] = matt_df['HOMESITE_ADDRESS1'].astype(str).str.strip()

    # 2. Merge Reference Data (Hub & Plan lookups)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hub_df = pd.read_csv(os.path.join(base_dir, 'data', 'Hub.csv'))
    plan_df = pd.read_csv(os.path.join(base_dir, 'data', 'Plan.csv'))
    matt_df['Comm_#'] = matt_df['COMMUNITY'].astype(str).str[:5].astype(int)
    matt_df['PLAN_CODE'] = matt_df['PLAN_CODE'].astype(str).str.strip().str.replace('.0', '', regex=False)
    plan_df['Plan Code'] = plan_df['Plan Code'].astype(str).str.strip()
    merged_df = pd.merge(matt_df, hub_df, how='left', left_on='Comm_#', right_on='Community Number')
    merged_df = pd.merge(merged_df, plan_df, how='left', left_on='PLAN_CODE', right_on='Plan Code')
    clean_strings(merged_df, ['Hub', 'Community Name', 'Plan Name'])

    # 3. Date Parsing & Derived Time Fields
    parse_dates(merged_df, ['SALE_DATE', 'EST_COE_DATE'])
    merged_df['DOW_Sale'] = merged_df['SALE_DATE'].dt.day_name()
    merged_df['Weekday_Group'] = np.where(
        merged_df['DOW_Sale'].isin(['Saturday', 'Sunday']), 'Sat-Sun', 'M-F'
    )

    # 4. Classification & Labeling
    investor_names_normalized = {name.strip().upper() for name in investor_names}
    merged_df['NHC_NAME_CLEAN'] = merged_df['NHC_NAME'].astype(str).str.strip().str.upper()
    merged_df['Investor Sale'] = merged_df['NHC_NAME_CLEAN'].apply(
        lambda x: "Investor" if x in investor_names_normalized else "Retail"
    )
    clean_strings(merged_df, ['SALES_CANCELLATION_DATE'])
    merged_df['SALES_CANCELLATION_DATE_PARSED'] = pd.to_datetime(
        merged_df['SALES_CANCELLATION_DATE'], errors='coerce'
    )
    merged_df['Realtor/Direct'] = merged_df['COBROKE_Y_N'].fillna('').str.strip().apply(map_realtor_direct)
    merged_df['HS_TYPE_LABEL'] = merged_df['HS_TYPE'].map(status_map).fillna(merged_df['HS_TYPE'])

    return merged_df

# --- Other Exported Functions ---
from typing import Union

def get_fred_data_filtered(start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    from scripts.fred_api import fetch_fred_30yr_mortgage_rate
    df = fetch_fred_30yr_mortgage_rate()
    return df[(df['date'] >= start_date) & (df['date'] <= end_date)].copy()

# Compute plan pricing summary statistics
def compute_plan_pricing(df: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp, group_col: Union[str, list[str]] = "Plan Name") -> pd.DataFrame:
    df = df.copy()
    df['SALE_DATE'] = pd.to_datetime(df['SALE_DATE'], errors='coerce')
    df = df[(df['SALE_DATE'] >= start_date) & (df['SALE_DATE'] <= end_date)]
    cols_to_clean = ['BASE_PRICE', 'HOMESITE_PREMIUM', 'PRICE_REDUCTION_INCENTIVES', 'OPTION_REVENUE', 'Net_Sales_Price']
    for col in cols_to_clean:
        df[col] = pd.to_numeric(
            df[col].astype(str)
                  .str.replace(r'[$,]', '', regex=True)
                  .str.replace(r'^\((.*)\)$', r'-\1', regex=True),
            errors='coerce'
        )
    df['List Price'] = (
        df['BASE_PRICE'].fillna(0) +
        df['HOMESITE_PREMIUM'].fillna(0) +
        df['PRICE_REDUCTION_INCENTIVES'].fillna(0) +
        df['OPTION_REVENUE'].fillna(0)
    )
    group_keys = group_col if isinstance(group_col, list) else [group_col]
    summary = df.groupby(group_keys, as_index=False).agg({
        'BASE_PRICE': 'mean',
        'List Price': 'mean',
        'Net_Sales_Price': 'mean',
        'TOTAL_SQFT': 'mean'
    })
    summary.rename(columns={
        'BASE_PRICE': 'Avg Base Price',
        'List Price': 'Avg List Price',
        'Net_Sales_Price': 'Avg Net Revenue',
        'TOTAL_SQFT': 'Avg SqFt'
    }, inplace=True)
    summary.sort_values(by='Avg SqFt', inplace=True)
    return summary

# Compute unsold inventory snapshot
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

# Compute pace vs margin analysis
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

# --- Module Exports ---
__all__ = [
    "compute_snapshot_unsold_inventory",
    "compute_pace_vs_margin",
    "process_matt_data",
    "map_realtor_direct",
    "compute_plan_pricing",
    "get_fred_data_filtered",
    "color_map"
]







