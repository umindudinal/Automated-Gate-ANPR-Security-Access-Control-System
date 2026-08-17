import streamlit as st
import pandas as pd
import sqlite3
import os
import sys
from PIL import Image
from datetime import datetime

# Add root directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

st.set_page_config(
    page_title="Automated Gate ANPR Security Dashboard",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1.2rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #2563EB;
    }
    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🚘 Automated Gate Automatic Number Plate Recognition (ANPR)</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Enterprise Vehicle Access Control (Yellow Rear Entry / White Front Exit) & Presence Register</div>', unsafe_allow_html=True)

from src.database import Database

# Helper function to load logs from MySQL (or SQLite fallback)
def load_data(table_name="vehicle_logs"):
    try:
        db = Database()
        if table_name == "inside_logs":
            logs = db.get_inside_logs()
        elif table_name == "exited_logs":
            logs = db.get_exited_logs()
        else:
            logs = db.get_logs_from_table(table_name)

        if not logs:
            return pd.DataFrame(columns=[
                'id', 'entry_date', 'entry_time', 'exit_time', 'number_plate',
                'vehicle_type', 'status', 'duration', 'confidence', 'crop_entry', 'crop_exit', 'plate_color'
            ])
        
        # Tuple schema: id, date, time, exit_time, number_plate, vehicle_type, status, duration, confidence, crop_path, exit_crop_path, exit_date, plate_color
        records = []
        for r in logs:
            col_val = r[12] if len(r) > 12 and r[12] else "YELLOW"
            records.append({
                'id': r[0],
                'entry_date': r[1],
                'entry_time': r[2],
                'exit_time': r[3] if r[3] else "-",
                'number_plate': r[4],
                'vehicle_type': r[5],
                'status': r[6],
                'duration': r[7],
                'confidence': float(r[8]),
                'crop_entry': r[9],
                'crop_exit': r[10],
                'plate_color': "🟡 Yellow Rear (Entry)" if col_val == "YELLOW" else "⚪ White Front (Exit)"
            })
        return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return pd.DataFrame()

df_logs = load_data("vehicle_logs")
df_inside = load_data("inside_logs")
df_exited = load_data("exited_logs")
df_verified = load_data("verified_vehicle_logs")
df_review = load_data("review_vehicle_logs")

# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)

total_visits = len(df_logs) if not df_logs.empty else 0
inside_count = len(df_inside) if not df_inside.empty else 0
exited_count = len(df_exited) if not df_exited.empty else 0

if not df_logs.empty:
    top_row = df_logs.iloc[0]
    latest_entry = f"{top_row['number_plate']} ({top_row['status']})"
else:
    latest_entry = "None"

with col1:
    st.markdown(f'<div class="metric-card"><div class="metric-value">{total_visits}</div><div class="metric-label">TOTAL VEHICLE VISITS</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #059669;">{inside_count}</div><div class="metric-label">CURRENTLY ON PREMISES</div></div>', unsafe_allow_html=True)
with col3:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="color: #64748B;">{exited_count}</div><div class="metric-label">EXITED VEHICLES</div></div>', unsafe_allow_html=True)
with col4:
    st.markdown(f'<div class="metric-card"><div class="metric-value" style="font-size: 1.2rem; color: #4F46E5;">{latest_entry}</div><div class="metric-label">LAST GATE ACTION</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Main Navigation Tabs
tab1, tab2, tab3 = st.tabs(["📋 Security Access Logs", "📸 Crop Audit Trail", "⚙️ System Configuration"])

with tab1:
    st.subheader("Vehicle Gate Access Register")
    
    # Filter Controls
    table_col, search_col, type_col, status_col = st.columns([3, 3, 2, 2])
    
    with table_col:
        selected_table_label = st.selectbox(
            "Select View / Filter Segment:",
            [
                "Master Register (All Visits)",
                "Currently On Premises (ඇතුළත)",
                "Exited Vehicles (පිටවූ)",
                "Verified Logs (Confidence ≥ 90%)",
                "Pending Review Logs (< 90%)"
            ]
        )
        
        table_map = {
            "Master Register (All Visits)": "vehicle_logs",
            "Currently On Premises (ඇතුළත)": "inside_logs",
            "Exited Vehicles (පිටවූ)": "exited_logs",
            "Verified Logs (Confidence ≥ 90%)": "verified_vehicle_logs",
            "Pending Review Logs (< 90%)": "review_vehicle_logs"
        }
        active_table = table_map[selected_table_label]
        df_display = load_data(active_table)

    with search_col:
        search_query = st.text_input("🔍 Search License Plate Number:", "", placeholder="e.g. NW KL - 6036")
    
    with type_col:
        selected_type = st.selectbox("Vehicle Type:", ["All Types", "Car", "Bike", "Bus", "Truck", "Van"])

    with status_col:
        selected_status = st.selectbox("Gate Status:", ["All Statuses", "INSIDE", "EXITED"])
        
    filtered_df = df_display.copy() if not df_display.empty else pd.DataFrame()
    
    if not filtered_df.empty:
        if search_query:
            filtered_df = filtered_df[filtered_df['number_plate'].str.contains(search_query.upper(), na=False)]
        
        if selected_type != "All Types" and 'vehicle_type' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['vehicle_type'] == selected_type]

        if selected_status != "All Statuses" and 'status' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['status'] == selected_status]
        
        # Display Table
        st.dataframe(
            filtered_df[['id', 'entry_date', 'entry_time', 'exit_time', 'number_plate', 'vehicle_type', 'plate_color', 'status', 'duration', 'confidence']],
            column_config={
                "id": "ID",
                "entry_date": "Date",
                "entry_time": "Entry Time",
                "exit_time": "Exit Time",
                "number_plate": "License Plate",
                "vehicle_type": "Vehicle Type",
                "plate_color": "Plate View (Color)",
                "status": "Gate Status",
                "duration": "Stay Duration",
                "confidence": st.column_config.NumberColumn("OCR Confidence Score", format="%.2f%%")
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Download Report
        csv_data = filtered_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Gate Security Access Log (CSV)",
            data=csv_data,
            file_name=f"Campus_ANPR_Gate_Logs_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("No vehicle logs found matching criteria.")

with tab2:
    st.subheader("License Plate Crop Audit Trail (Yellow Rear Entry & White Front Exit)")
    
    if not df_logs.empty:
        selected_id = st.selectbox(
            "Select a Logged Access Entry to view Cropped Images & Audit Metadata:",
            options=df_logs['id'].tolist(),
            format_func=lambda x: f"ID #{x} | {df_logs[df_logs['id']==x]['number_plate'].values[0]} ({df_logs[df_logs['id']==x]['vehicle_type'].values[0]}) | View: {df_logs[df_logs['id']==x]['plate_color'].values[0]} | Status: {df_logs[df_logs['id']==x]['status'].values[0]}"
        )
        
        selected_row = df_logs[df_logs['id'] == selected_id].iloc[0]
        crop_entry_path = selected_row['crop_entry']
        crop_exit_path = selected_row['crop_exit']
        
        col_img1, col_img2, col_meta = st.columns([1, 1, 2])
        
        with col_img1:
            st.markdown("##### 🟡 Yellow Rear Plate (Gate Entry)")
            if crop_entry_path and os.path.exists(crop_entry_path):
                img_entry = Image.open(crop_entry_path)
                st.image(img_entry, caption=f"Yellow Entry: {selected_row['number_plate']}", use_container_width=True)
            else:
                st.info("Entry crop image file missing or not available.")

        with col_img2:
            st.markdown("##### ⚪ White Front Plate (Gate Exit)")
            if crop_exit_path and os.path.exists(crop_exit_path):
                img_exit = Image.open(crop_exit_path)
                st.image(img_exit, caption=f"White Exit: {selected_row['number_plate']}", use_container_width=True)
            else:
                st.info("Vehicle has not exited yet (or exit crop missing).")

        with col_meta:
            st.markdown("##### 📊 Visit Audit Details")
            st.markdown(f"**License Plate:** `{selected_row['number_plate']}`")
            st.markdown(f"**Vehicle Category:** `{selected_row['vehicle_type']}`")
            st.markdown(f"**Plate View Classification:** `{selected_row['plate_color']}`")
            st.markdown(f"**Campus Gate Status:** `{selected_row['status']}`")
            st.markdown(f"**Entry Date & Time:** {selected_row['entry_date']} at `{selected_row['entry_time']}`")
            st.markdown(f"**Exit Time:** `{selected_row['exit_time']}`")
            st.markdown(f"**Stay Duration:** `{selected_row['duration']}`")
            st.markdown(f"**OCR Confidence Score:** `{selected_row['confidence']}%`")
    else:
        st.info("No access logs available for crop viewing.")

with tab3:
    st.subheader("ANPR System Parameters & Settings")
    
    st.json({
        "YOLO Plate Model Path": config.YOLO_MODEL_PATH,
        "YOLO Vehicle Classification Model": config.FALLBACK_YOLO_MODEL,
        "OCR Confidence Threshold": f"{config.OCR_CONFIDENCE_THRESHOLD * 100}%",
        "Frame Skip Rate": config.FRAME_SKIP_RATE,
        "Voting Buffer Window Frames": config.VOTING_WINDOW_FRAMES,
        "Vehicle Cooldown Window": f"{config.PLATE_COOLDOWN_SECONDS} seconds",
        "Supported Province Codes": config.PROVINCE_CODES,
        "Default Province Fallback": config.DEFAULT_PROVINCE,
        "SQLite DB Path": config.SQLITE_DB_PATH,
        "CSV Log Path": config.CSV_LOG_PATH
    })

    st.markdown("---")
    st.subheader("🗑️ Database & System Purge Controls")
    st.warning("⚠️ Warning: Clearing log data will permanently delete all records from MySQL, SQLite, CSV files, and purge all crop image files.")
    
    if st.button("🗑️ Purge All System Logs", type="primary"):
        db = Database()
        db.clear_all_logs()
        st.success("All vehicle logs and crop image files have been purged successfully!")
        st.rerun()
