import pandas as pd
import numpy as np
import os
import datetime
import streamlit as st
from pathlib import Path
from typing import Union

# --- Constants & Mapping Dictionaries ---
color_map = {
    'Model': '#ffb6c1',
    'Closed': '#ff4136',
    'Unsold': '#87cefa',
    'Backlog': '#1f77b4',
    'Grand Total': '#E5ECF6',
    'Black': '#000000',
    'Red': '#ff0000',
    'Yellow': '#ffff00',
    'Green': '#008000'
}

status_map = {
    'B': 'Backlog',
    'S': 'Unsold',
    'Z': 'Closed',
    'M': 'Model'
}

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

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------

def clean_strings(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df

def parse_dates(df, cols):
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

def map_realtor_direct(cobroke_value):
    mapping = {'Y': 'Realtor', '': 'Direct', None: 'Direct'}
    return mapping.get(cobroke_value, 'Direct')

# -------------------------------------------------------------
# Main Processing Function
# -------------------------------------------------------------

def process_matt_data(matt_df: pd.DataFrame) -> pd.DataFrame:

    matt_df = matt_df.rename(columns={
        'Textbox4': 'HS_TYPE',
        'Textbox22': 'Net_Sales_Price'
    })

    clean_strings(matt_df, matt_df.columns)

    if 'HOMESITE_ADDRESS1' in matt_df.columns:
        matt_df['Address'] = matt_df['HOMESITE_ADDRESS1'].astype(str).str.strip()

    if 'COMMUNITY' in matt_df.columns:
        matt_df['Comm_#'] = (
            matt_df['COMMUNITY']
            .astype(str)
            .str.strip()
            .str[:5]
        )

    if 'PLAN_CODE' in matt_df.columns:
        matt_df['PLAN_CODE'] = (
            matt_df['PLAN_CODE']
            .astype(str)
            .str.replace('.0', '', regex=False)
            .str.strip()
        )

    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / 'data'
    if not data_dir.exists():
        data_dir = Path.cwd() / 'data'

    hub_df = pd.read_csv(data_dir / 'Hub.csv')
    plan_df = pd.read_csv(data_dir / 'Plan.csv')

    hub_df['PROJECT_NUMBER'] = hub_df['PROJECT_NUMBER'].astype(str).str.replace('.0','',regex=False).str.strip()
    plan_df['PLAN_NUMBER'] = plan_df['PLAN_NUMBER'].astype(str).str.replace('.0','',regex=False).str.strip()

    if 'Comm_#' in matt_df.columns:
        matt_df['Comm_#'] = matt_df['Comm_#'].astype(str).str.replace('.0','',regex=False).str.strip()

    merged_df = pd.merge(
        matt_df,
        hub_df,
        how='left',
        left_on='Comm_#',
        right_on='PROJECT_NUMBER'
    )

    merged_df = pd.merge(
        merged_df,
        plan_df,
        how='left',
        left_on='PLAN_CODE',
        right_on='PLAN_NUMBER'
    )

    rename_map = {
        'HUB': 'Hub',
        'PROJECT_NAME': 'Community Name',
        'PROJECT_NUMBER': 'Community Number',
        'PLAN_NAME': 'Plan Name'
    }

    if 'COLLECTION' in merged_df.columns:
        rename_map['COLLECTION'] = 'Collection'

    merged_df.rename(columns=rename_map, inplace=True)

    if 'Collection' not in merged_df.columns:
        merged_df['Collection'] = ""

    clean_strings(merged_df, ['Hub','Community Name','Plan Name','Collection'])

    # --- Date Handling ---
    parse_dates(merged_df, [
        'SALE_DATE',
        'EST_COE_DATE',
        'CONSTRUCTION_COMPLETE_DATE',
        'EST_DELIVERABLE_DATE'
    ])

    if 'SALE_DATE' in merged_df.columns:
        merged_df['DOW_Sale'] = merged_df['SALE_DATE'].dt.day_name()
        merged_df['Weekday_Group'] = np.where(
            merged_df['DOW_Sale'].isin(['Saturday','Sunday']),
            'Sat-Sun','M-F'
        )

    # --- Investor Classification ---
    investor_names_normalized = {name.strip().upper() for name in investor_names}
    if 'NHC_NAME' in merged_df.columns:
        merged_df['NHC_NAME_CLEAN'] = merged_df['NHC_NAME'].astype(str).str.strip().str.upper()
        merged_df['Investor Sale'] = merged_df['NHC_NAME_CLEAN'].apply(
            lambda x: "Investor" if x in investor_names_normalized else "Retail"
        )
    else:
        merged_df['Investor Sale'] = 'Retail'

    # --- Realtor Flag ---
    if 'COBROKE_Y_N' in merged_df.columns:
        merged_df['Realtor/Direct'] = merged_df['COBROKE_Y_N'].fillna('').str.strip().apply(map_realtor_direct)
    else:
        merged_df['Realtor/Direct'] = 'Direct'

    return merged_df.copy()

# -------------------------------------------------------------
# PRICING CALCULATION (RESTORED)
# -------------------------------------------------------------

def compute_plan_pricing(
    df: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    group_col: Union[str, list[str]] = "Plan Name"
) -> pd.DataFrame:

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
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str)
                    .str.replace(r'[$,]', '', regex=True)
                    .str.replace(r'^\((.*)\)$', r'-\1', regex=True),
                errors='coerce'
            )
        else:
            df[col] = 0

    # --- List Price Calculation ---
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

def compute_snapshot_unsold_inventory(
    df: pd.DataFrame,
    group_col: str,
    snapshot_date: pd.Timestamp,
    coe_start: pd.Timestamp,
    coe_end: pd.Timestamp,
    label: str
) -> pd.DataFrame:
    """
    Computes unsold inventory and average age for a given snapshot date.
    Fully defensive against string date columns.
    """

    df = df.copy()

    # -------------------------------------------------------
    # ENSURE DATE TYPES (critical fix)
    # -------------------------------------------------------
    df['EST_COE_DATE'] = pd.to_datetime(df['EST_COE_DATE'], errors='coerce')
    df['SALE_DATE'] = pd.to_datetime(df['SALE_DATE'], errors='coerce')
    df['TRENCH_DATE'] = pd.to_datetime(df['TRENCH_DATE'], errors='coerce')

    # -------------------------------------------------------
    # Filter to COE window
    # -------------------------------------------------------
    df = df.loc[
        df['EST_COE_DATE'].notna() &
        (df['EST_COE_DATE'] >= coe_start) &
        (df['EST_COE_DATE'] <= coe_end)
    ]

    # -------------------------------------------------------
    # Unsold as of snapshot
    # -------------------------------------------------------
    unsold_mask = (
        df['SALE_DATE'].isna() |
        (df['SALE_DATE'] > snapshot_date)
    )

    df_unsold = df.loc[unsold_mask].copy()

    if df_unsold.empty:
        return pd.DataFrame(columns=[group_col, 'Unsold', 'Avg_Age'])

    # -------------------------------------------------------
    # Age calculation (safe now)
    # -------------------------------------------------------
    df_unsold['Age'] = (snapshot_date - df_unsold['TRENCH_DATE']).dt.days
    df_unsold['Age'] = df_unsold['Age'].fillna(0)

    agg_df = (
        df_unsold
        .groupby(group_col)
        .agg(
            Unsold=(group_col, 'count'),
            Avg_Age=('Age', 'mean')
        )
        .reset_index()
    )

    return agg_df


# -------------------------------------------------------------
# EXPORTS
# -------------------------------------------------------------

__all__ = [
    "process_matt_data",
    "compute_plan_pricing",
    "map_realtor_direct",
    "color_map"
]


