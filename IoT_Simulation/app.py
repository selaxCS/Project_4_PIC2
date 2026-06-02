import streamlit as st
import pandas as pd
import psycopg2
import os
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

st.set_page_config(page_title="IoT Hybrid Monitor", layout="wide")

# --- UNIT LOGIC ---
def get_unit_from_config(plc_id, sensor_type):
    
    try:
        config_path = Path(__file__).parent.resolve() / 'config.json'
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            for plc in config.get('plcs', []):
                if str(plc['id']) == str(plc_id):
                    for s in plc.get('sensors', []):
                        if s['type'] == sensor_type:
                            return s.get('unit')
    except Exception as e:
        st.error(f"Error llegint config.json: {e}") 
    return None

def get_final_unit(plc_id, sensor_type, db_unit):
    """Hybrid logic: Config for simulation, DB for Real ESP."""
    config_unit = get_unit_from_config(plc_id, sensor_type)
    if config_unit:
        return config_unit
    return db_unit if db_unit and db_unit != "None" else "u."

# --- DATABASE HELPERS ---
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "iot_database"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def query_db(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if cur.description:
                cols = [d[0] for d in cur.description]
                return pd.DataFrame(cur.fetchall(), columns=cols)
            return pd.DataFrame()
    finally:
        conn.close()

# --- SIDEBAR (TIME FILTERS ONLY) ---
st.sidebar.header("⏱️ Time Filters")
range_type = st.sidebar.selectbox("Range:", ["Minutes", "Hours", "Custom", "Last 100"])

sql_filter = ""
sql_params = []

if range_type == "Minutes":
    m = st.sidebar.slider("Minutes:", 5, 120, 30)
    sql_filter = "AND timestamp >= NOW() - INTERVAL '%s minutes'"
    sql_params = [m]
elif range_type == "Hours":
    h = st.sidebar.slider("Hours:", 1, 72, 1)
    sql_filter = "AND timestamp >= NOW() - INTERVAL '%s hours'"
    sql_params = [h]
elif range_type == "Custom":
    c1, c2 = st.sidebar.columns(2)
    with c1: start = st.date_input("Start", datetime.now() - timedelta(days=1))
    with c2: end = st.date_input("End", datetime.now())
    sql_filter = "AND timestamp BETWEEN %s AND %s"
    sql_params = [start, end]
else:
    sql_filter = "ORDER BY timestamp DESC LIMIT 100"

# --- HEADER ---
col_t, col_r = st.columns([8, 2])
with col_t:
    st.title("🛰️ IoT Device Control Panel")
with col_r:
    st.write("")
    auto_refresh = st.toggle("🔄 Auto-Refresh", value=(range_type != "Custom"))

# --- DEVICE DETECTION ---
def get_status():
    try:
        df = query_db("SELECT plc_id, MAX(timestamp) as last_seen FROM sensor_data GROUP BY plc_id")
        now = datetime.now()
        if df.empty: return {}
        return {
            str(r['plc_id']): f"PLC_Sim_{r['plc_id']} {'🟢' if (now-r['last_seen']).total_seconds() < 20 else '🔴'}" 
            for _, r in df.iterrows()
        }
    except: return {}

devices = get_status()

if devices:
    c_a, c_b = st.columns(2)
    with c_a:
        sel_name = st.selectbox("Select Device:", list(devices.values()))
        selected_id = [k for k, v in devices.items() if v == sel_name][0]
    with c_b:
        view_mode = st.radio("Display:", ["Graph", "Tables"], horizontal=True)
else:
    st.warning("Waiting for data...")
    if auto_refresh: time.sleep(5); st.rerun()
    st.stop()

st.divider()

try:
    query = f"SELECT timestamp, sensor, value, unit FROM sensor_data WHERE plc_id = %s {sql_filter}"
    if range_type != "Last 100": query += " ORDER BY timestamp ASC"
    
    df = query_db(query, [selected_id] + sql_params)

    if not df.empty:
        sensors = df['sensor'].unique()
        
        if view_mode == "Graph":
            sensors = df['sensor'].unique()
            for s in sensors:
                s_df = df[df['sensor'] == s].copy()
                unit = get_final_unit(selected_id, s, s_df['unit'].iloc[0])
                
                st.subheader(f"Sensor: {s.upper()} ({unit})")
                
                
                limit = st.slider(f"Threshold for {s.capitalize()} ({unit})", 0, 100, 35, key=f"lim_{s}")
                
                # Alert logic
                current_val = s_df['value'].iloc[-1]
                if current_val > limit:
                    st.error(f"⚠️ ALERT: {current_val}{unit} exceeds the limit of {limit}{unit}!")

                chart_data = s_df.set_index('timestamp')[['value']].copy()
                chart_data['Limit Line'] = limit
                st.line_chart(chart_data, color=["#1f77b4", "#ff0000"])
        else:
            cols = st.columns(len(sensors))
            for i, s in enumerate(sensors):
                with cols[i]:
                    s_df = df[df['sensor'] == s].copy()
                    db_unit = s_df['unit'].iloc[0] if 'unit' in s_df.columns else None
                    unit = get_final_unit(selected_id, s, db_unit)
                    
                    st.write(f"**{s.capitalize()} Table ({unit})**")
                    table = s_df[['timestamp', 'value']].rename(columns={'value': f'Value ({unit})'})
                    st.dataframe(table, hide_index=True, width=500)
    else:
        st.info("No records found.")
except Exception as e:
    st.error(f"Error: {e}")

if auto_refresh:
    time.sleep(5)
    st.rerun()