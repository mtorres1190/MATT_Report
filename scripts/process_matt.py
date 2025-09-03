import pandas as pd
import numpy as np
import os
import datetime
import streamlit as st
from pathlib import Path

# --- Constants & Mapping Dictionaries ---
# Color coding for homesite status visualization
color_map = {
    'Model': '#ffb6c1',
    'Closed': '#ff4136',
    'Unsold': '#87cefa',
    'Backlog': '#1f77b4',
    'Grand Total': '#E5ECF6',
    # Age Buckets
    'Black': '#000000',
    'Red': '#ff0000',
    'Yellow': '#ffff00',
    'Green': '#008000'
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
        matt_df = matt_df.assign(
            Address=matt_df['HOMESITE_ADDRESS1'].astype(str).str.strip()
        )

    # Ensure Comm_# exists (first 5 digits of COMMUNITY)
    if 'COMMUNITY' in matt_df.columns:
        matt_df['Comm_#'] = (
            matt_df['COMMUNITY'].astype(str).str[:5].str.replace(r"[^0-9]", "", regex=True)
        )
        with pd.option_context('mode.use_inf_as_na', True):
            matt_df['Comm_#'] = pd.to_numeric(matt_df['Comm_#'], errors='coerce').astype('Int64')

    # Normalize PLAN_CODE (strip and remove trailing .0)
    if 'PLAN_CODE' in matt_df.columns:
        matt_df['PLAN_CODE'] = (
            matt_df['PLAN_CODE'].astype(str).str.strip().str.replace('.0', '', regex=False)
        )

    # 2. Merge Reference Data (Hub & Plan lookups) — robust path resolution
    # Expect repo layout: <repo_root>/data/Hub.csv and Plan.csv
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / 'data'
    if not data_dir.exists():
        # Fallback to CWD/data for hosted environments that set a different working dir
        data_dir = Path.cwd() / 'data'

    hub_path = data_dir / 'Hub.csv'
    plan_path = data_dir / 'Plan.csv'

    if not hub_path.exists() or not plan_path.exists():
        st.error(f"Missing reference files in '{data_dir}'. Expected Hub.csv and Plan.csv.")
        st.stop()

    hub_df = pd.read_csv(hub_path)
    plan_df = pd.read_csv(plan_path)

    # Clean lookup keys
    if 'Plan Code' in plan_df.columns:
        plan_df['Plan Code'] = plan_df['Plan Code'].astype(str).str.strip()

    # Perform merges
    merged_df = matt_df.copy()
    if 'Comm_#' in merged_df.columns and 'Community Number' in hub_df.columns:
        merged_df = pd.merge(
            merged_df,
            hub_df,
            how='left',
            left_on='Comm_#',
            right_on='Community Number'
        )

    if 'PLAN_CODE' in merged_df.columns and 'Plan Code' in plan_df.columns:
        merged_df = pd.merge(
            merged_df,
            plan_df,
            how='left',
            left_on='PLAN_CODE',
            right_on='Plan Code'
        )

    clean_strings(merged_df, ['Hub', 'Community Name', 'Plan Name'])

    # 3. Date Parsing & Derived Time Fields
    parse_dates(merged_df, ['SALE_DATE', 'EST_COE_DATE', 'CONSTRUCTION_COMPLETE_DATE', 'EST_DELIVERABLE_DATE'])
    if 'SALE_DATE' in merged_df.columns:
        merged_df['DOW_Sale'] = merged_df['SALE_DATE'].dt.day_name()
        merged_df['Weekday_Group'] = np.where(
            merged_df['DOW_Sale'].isin(['Saturday', 'Sunday']), 'Sat-Sun', 'M-F'
        )
    else:
        merged_df['DOW_Sale'] = pd.NaT
        merged_df['Weekday_Group'] = np.nan

    # Optional one-liner for page-level ECOE month aggregations
    if 'EST_COE_DATE' in merged_df.columns:
        merged_df['ECOE_Month'] = merged_df['EST_COE_DATE'].dt.to_period('M')

    # 4. Classification & Labeling
    investor_names_normalized = {name.strip().upper() for name in investor_names}
    if 'NHC_NAME' in merged_df.columns:
        merged_df['NHC_NAME_CLEAN'] = merged_df['NHC_NAME'].astype(str).str.strip().str.upper()
        merged_df['Investor Sale'] = merged_df['NHC_NAME_CLEAN'].apply(
            lambda x: "Investor" if x in investor_names_normalized else "Retail"
        )
    else:
        merged_df['Investor Sale'] = 'Retail'

    # Sales cancellation date (keep original text + parsed)
    if 'SALES_CANCELLATION_DATE' in merged_df.columns:
        clean_strings(merged_df, ['SALES_CANCELLATION_DATE'])
        merged_df['SALES_CANCELLATION_DATE_PARSED'] = pd.to_datetime(
            merged_df['SALES_CANCELLATION_DATE'], errors='coerce'
        )

    # Realtor/Direct flag
    if 'COBROKE_Y_N' in merged_df.columns:
        merged_df['Realtor/Direct'] = merged_df['COBROKE_Y_N'].fillna('').str.strip().apply(map_realtor_direct)
    else:
        merged_df['Realtor/Direct'] = 'Direct'

    # HS_TYPE human label
    if 'HS_TYPE' in merged_df.columns:
        merged_df['HS_TYPE_LABEL'] = merged_df['HS_TYPE'].map(status_map).fillna(merged_df['HS_TYPE'])

    # 5. Age Calculation (Construction Complete or Est Deliverable)
    today = pd.Timestamp.today().normalize()
    chosen = None
    if 'CONSTRUCTION_COMPLETE_DATE' in merged_df.columns:
        chosen = merged_df['CONSTRUCTION_COMPLETE_DATE']
    if 'EST_DELIVERABLE_DATE' in merged_df.columns:
        chosen = chosen.combine_first(merged_df['EST_DELIVERABLE_DATE']) if chosen is not None else merged_df['EST_DELIVERABLE_DATE']
    if chosen is not None:
        merged_df['Chosen_Date'] = chosen
        merged_df['Age'] = (pd.to_datetime(merged_df['Chosen_Date'], errors='coerce') - today).dt.days

        def categorize_age(days):
            if pd.isna(days):
                return None
            if days < 0:
                return 'Black'
            elif 0 <= days <= 30:
                return 'Red'
            elif 31 <= days <= 60:
                return 'Yellow'
            else:
                return 'Green'

        merged_df['Age_Bucket'] = merged_df['Age'].apply(categorize_age)
    else:
        merged_df['Age'] = np.nan
        merged_df['Age_Bucket'] = np.nan

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
    cols_to_clean = [
        'BASE_PRICE', 
        'HOMESITE_PREMIUM', 
        'PRICE_REDUCTION_INCENTIVES', 
        'OPTION_REVENUE', 
        'Net_Sales_Price',
        'TOTAL_SQFT'
    ]

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
    summary['Needed Pace'] = summary['Unsold'] / weeks_left if weeks_left > 0 else 0
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









