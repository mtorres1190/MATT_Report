import streamlit as st
import pandas as pd
import os

from config import ENABLE_FIREWALL, FIREWALL_PASSCODE, DEVELOPER_MODE
from scripts.process_matt import process_matt_data

# Set page config
st.set_page_config(page_title="MATT Upload", layout="wide")
st.title("MATT Report Upload Page")

# Define required MATT headers (just a few key ones for validation)
REQUIRED_COLUMNS = {
    "DIV_CODE_DESC", "PROJECT", "BUYER_NAME", "COMMUNITY",
    "PLAN_CODE", "SALE_DATE", "NHC_NAME", "SALES_CANCELLATION_DATE"
}

# Firewall logic
if ENABLE_FIREWALL and not st.session_state.get("authenticated"):
    st.subheader("\U0001F512 Enter 4-Digit Access Code")
    code_input = st.text_input("Access Code", type="password", max_chars=4)
    if code_input == FIREWALL_PASSCODE:
        st.session_state["authenticated"] = True
        st.success("Access granted.")
        st.rerun()
    elif code_input:
        st.error("Invalid code. Please try again.")
    st.stop()

# Developer mode logic
if DEVELOPER_MODE:
    try:
        sample_path = os.path.join(os.path.dirname(__file__), 'data', 'Homesite Detail Data (MATT).csv')
        df = pd.read_csv(sample_path)
        st.session_state['matt_raw'] = df
        st.session_state['matt_processed'] = process_matt_data(df)
        st.success("Latest MATT Report Loaded.")
    except Exception as e:
        st.error("Failed to load sample file. Please ensure 'sample_matt.csv' exists in the data folder.")
else:
    st.markdown("""
    Upload the **raw MATT report CSV** as exported from the company data portal. Once uploaded,
    the file will be processed and available across all pages of the application.
    """)
    uploaded_file = st.file_uploader("Upload MATT Report CSV", type="csv")
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            missing_cols = REQUIRED_COLUMNS - set(df.columns)
            if missing_cols:
                st.error("The uploaded file does not appear to be a valid MATT Report. Please upload the correct file exported from the company data portal.")
            else:
                st.session_state['matt_raw'] = df
                st.session_state['matt_processed'] = process_matt_data(df)
        except Exception as e:
            st.error("Failed to read the uploaded file. Please ensure it is a valid CSV.")
    else:
        st.warning("Please upload a file to proceed.")

# To run the streamlit application
# streamlit run MATT_Upload.py




