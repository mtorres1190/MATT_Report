import pandas as pd
import requests
import os
import streamlit as st

def fetch_fred_30yr_mortgage_rate() -> pd.DataFrame:
    """
    Fetches weekly 30-Year Fixed Rate Mortgage (FRM) data from FRED API.
    Returns a DataFrame with columns: ['date', 'value']
    """
    # Use API key from Streamlit secrets or environment
    api_key = st.secrets.get("FRED_API_KEY", os.getenv("FRED_API_KEY"))
    if not api_key:
        st.error("FRED API key is missing. Please set it in Streamlit secrets or as an environment variable.")
        st.stop()

    # FRED Series ID for 30-Year Fixed Mortgage Rate
    series_id = "MORTGAGE30US"
    url = f"https://api.stlouisfed.org/fred/series/observations"

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        records = [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in data["observations"]
            if obs["value"] not in (".", None)
        ]
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        return df

    except Exception as e:
        st.error("Failed to fetch mortgage rate data from FRED API.")
        st.exception(e)
        return pd.DataFrame(columns=["date", "value"])
