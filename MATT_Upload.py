import streamlit as st
import pandas as pd
import os

from config import ENABLE_FIREWALL, FIREWALL_PASSCODE, DEVELOPER_MODE
from scripts.process_matt import process_matt_data

# --- Set up the Streamlit page ---
st.set_page_config(page_title="MATT Upload", layout="wide")
st.title("MATT Report Upload Page")

# --- Define required MATT headers for validation (same names, new positions) ---
REQUIRED_COLUMNS = {
    "DIV_CODE_DESC", "PROJECT", "BUYER_NAME", "COMMUNITY",
    "PLAN_CODE", "SALE_DATE", "NHC_NAME", "SALES_CANCELLATION_DATE"
}

# --- Firewall logic to restrict access ---
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

# --- Developer mode loads a sample file automatically ---
if DEVELOPER_MODE:
    try:
        sample_path = os.path.join(os.path.dirname(__file__), 'data', 'Homesite Detail Data (MATT).csv')
        df = pd.read_csv(sample_path, low_memory=False)
        st.session_state['matt_raw'] = df
        st.session_state['matt_processed'] = process_matt_data(df)
        st.success("Latest MATT Report Loaded.")
    except Exception as e:
        st.error("Failed to load sample file. Please ensure 'Homesite Detail Data (MATT).csv' exists in the data folder.")

# --- User file upload logic ---
else:
    st.markdown("""
    Upload the **raw MATT report CSV** as exported from the company data portal. Once uploaded,
    the file will be processed and available across all pages of the application.
    """)

    uploaded_file = st.file_uploader("Upload MATT Report CSV", type="csv")

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, low_memory=False)
            st.write("**Uploaded Columns:**", list(df.columns))  # Debugging aid
            normalized_cols = {col.strip() for col in df.columns}
            missing_cols = REQUIRED_COLUMNS - normalized_cols
            if missing_cols:
                st.error("The uploaded file does not appear to be a valid MATT Report. Missing columns: " + ", ".join(missing_cols))
            else:
                st.session_state['matt_raw'] = df
                st.session_state['matt_processed'] = process_matt_data(df)
                st.success("MATT Report uploaded and processed successfully.")
        except Exception as e:
            st.error("Failed to read the uploaded file. Please ensure it is a valid CSV.")
            st.exception(e)
    else:
        st.warning("Please upload a file to proceed.")

# --- Streamlit command to run this file locally ---
# streamlit run MATT_Upload.py






