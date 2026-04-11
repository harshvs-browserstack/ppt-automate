"""
Generation History — View all past slide generations.
Displays a log of every slide created with timestamps, templates, and links.
"""
import streamlit as st
from core.config import get_config
from core.auth_helpers import get_sheets_service
import pandas as pd

st.set_page_config(page_title="Generation History", layout="wide")

config = get_config()

st.title("📊 Generation History")
st.caption("All slide generations logged here for audit trail and reference.")
st.markdown("<br>", unsafe_allow_html=True)

# Load history from sheet
history_sheet_id = config.history_sheet_id

if not history_sheet_id or history_sheet_id == "-":
    st.info("History tracking not configured. Set HISTORY_SHEET_ID to enable.")
    st.stop()

try:
    service = get_sheets_service(config.gdrive_credentials_path)

    # Fetch data from Generations sheet
    result = service.spreadsheets().values().get(
        spreadsheetId=history_sheet_id,
        range="Generations!A:F"
    ).execute()

    rows = result.get("values", [])

    if not rows or len(rows) < 2:
        st.info("No generations yet. Create your first deck to start building history.")
        st.stop()

    # Convert to DataFrame
    headers = rows[0]
    data = rows[1:]
    df = pd.DataFrame(data, columns=headers)

    # Display summary stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Generations", len(df))
    col2.metric("Unique Templates", df["Template"].nunique() if "Template" in df.columns else 0)
    col3.metric("Unique Targets", df["Target Value"].nunique() if "Target Value" in df.columns else 0)
    col4.metric("Latest Generation", df["Timestamp"].iloc[-1] if len(df) > 0 else "—")

    st.markdown("<br>", unsafe_allow_html=True)

    # Display full history table with clickable links
    st.subheader("All Generations")

    # Make Slide URL clickable
    if "Slide URL" in df.columns:
        df_display = df.copy()
        df_display["Slide URL"] = df_display["Slide URL"].apply(
            lambda url: f'[Open ↗]({url})' if url and url != "N/A" else url
        )

        # Reorder columns for better readability
        column_order = [
            "Timestamp",
            "Template",
            "Target Value",
            "PDF Filename",
            "Slide URL",
            "Slide ID"
        ]
        df_display = df_display[[col for col in column_order if col in df_display.columns]]

        st.markdown(
            df_display.to_markdown(index=False),
            unsafe_allow_html=True
        )
    else:
        st.dataframe(df, use_container_width=True)

    # Export option
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Export")

    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name="generation_history.csv",
        mime="text/csv"
    )

except Exception as e:
    st.error(f"Could not load history: {e}")
    st.info(f"Make sure HISTORY_SHEET_ID is set correctly and the service account has access to the sheet.")
