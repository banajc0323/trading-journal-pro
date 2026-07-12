import streamlit as st
import psycopg2
import pandas as pd
import numpy as np
from datetime import datetime, date
import openai
import os
import cloudinary
import cloudinary.uploader

st.set_page_config(page_title="交易策略實驗室 Pro", page_icon="📓")

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)
openai.api_key = os.environ.get("OPENAI_API_KEY", "")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    st.error("請設定 DATABASE_URL 環境變數")
    st.stop()

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

SYMBOLS = [
    "MGC","MES","MNQ","MYM","M2K","ES","NQ","YM","RTY",
    "GC","SI","CL","NG","ZB","ZN","ZF",
    "6E","6J","6B","6A","6C","6S",
    "HE","LE","ZC","ZW","ZS","CC","KC","CT","SB","OJ"
]
DEFAULT_TICK_VALUES = {
    "MGC":10,"MES":5,"MNQ":2,"MYM":0.5,"M2K":0.5,"ES":50,"NQ":20,"YM":5,"RTY":5,
    "GC":100,"SI":5000,"CL":1000,"NG":10000,"ZB":1000,"ZN":1000,"ZF":1000,
    "6E":125000,"6J":12500000,"6B":62500,"6A":100000,"6C":100000,"6S":125000,
    "HE":400,"LE":400,"ZC":50,"ZW":50,"ZS":50,"CC":10,"KC":375,"CT":500,"SB":1120,"OJ":150
}

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL,
        daily_loss_limit REAL DEFAULT 1000, max_loss_limit REAL DEFAULT 2000,
        created_at TIMESTAMP DEFAULT NOW())""")
    cur.execute("""CREATE TABLE IF NOT EXISTS strategies (
        id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS symbol_config (
        symbol TEXT PRIMARY KEY, tick_value REAL NOT NULL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS notes (
        id SERIAL PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
        strategy_id INTEGER REFERENCES strategies(id), symbol TEXT NOT NULL,
        phase TEXT NOT NULL, action_detail TEXT DEFAULT '', reason TEXT, mood TEXT,
        is_disciplined INTEGER DEFAULT 1, image_url TEXT DEFAULT '', entry_date TIMESTAMP NOT NULL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS trades (
        id SERIAL PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(id),
        trade_time TIMESTAMP NOT NULL, symbol TEXT NOT NULL, side TEXT,
        quantity REAL, price REAL, profit REAL)""")
    cur.execute("INSERT INTO strategies (name) VALUES ('無特定策略') ON CONFLICT (name) DO NOTHING")
    cur.execute("INSERT INTO strategies (name) VALUES ('策略A') ON CONFLICT (name) DO NOTHING")
    cur.execute("INSERT INTO strategies (name) VALUES ('策略B') ON CONFLICT (name) DO NOTHING")
    for sym, val in DEFAULT_TICK_VALUES.items():
        cur.execute("INSERT INTO symbol_config (symbol, tick_value) VALUES (%s,%s) ON CONFLICT (symbol) DO NOTHING", (sym, val))
    conn.commit()
    cur.close()
    conn.close()

init_db()

if "current_account_id" not in st.session_state:
    st.session_state.current_account_id = None
if "current_account_name" not in st.session_state:
    st.session_state.current_account_name = None

def get_accounts():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, name, daily_loss_limit, max_loss_limit, created_at FROM accounts ORDER BY id", conn)
    conn.close()
    return df

def create_account(name, daily_loss=1000, max_loss=2000):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO accounts (name, daily_loss_limit, max_loss_limit) VALUES (%s,%s,%s)", (name, daily_loss, max_loss))
        conn.commit()
        cur.close()
        return True, "帳號建立成功！"
    except psycopg2.IntegrityError:
        conn.rollback()
        return False, "帳號名稱已存在"
    finally:
        conn.close()

def delete_account(account_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM notes WHERE account_id=%s", (account_id,))
    cur.execute("DELETE FROM trades WHERE account_id=%s", (account_id,))
    cur.execute("DELETE FROM accounts WHERE id=%s", (account_id,))
    conn.commit()
    cur.close()
    conn.close()

def get_strategies():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, name FROM strategies ORDER BY id", conn)
    conn.close()
    return df

def add_strategy(name):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO strategies (name) VALUES (%s)", (name,))
        conn.commit()
        cur.close()
        return True
    except:
        return False
    finally:
        conn.close()

def get_tick_values():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM symbol_config", conn)
    conn.close()
    return df

def update_tick_value(symbol, value):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO symbol_config (symbol, tick_value) VALUES (%s,%s) ON CONFLICT (symbol) DO UPDATE SET tick_value=%s", (symbol, value, value))
    conn.commit()
    cur.close()
    conn.close()

def upload_image_to_cloudinary(image_file):
    if image_file is None:
        return ""
    try:
        response = cloudinary.uploader.upload(image_file, folder="trading_journal")
        return response.get("secure_url", "")
    except Exception as e:
        st.error(f"圖片上傳失敗：{e}")
        return ""

st.sidebar.title("📓 交易策略實驗室 Pro")
menu = st.sidebar.radio("選單", [
    "🏠 帳號管理","🏷️ 策略管理","✍️ 新增筆記","📋 歷史紀錄",
    "📥 匯入CSV","📊 績效分析","🎯 停損停利建議","📉 風險監控","🧠 AI教練"
])
if st.session_state.current_account_name:
    st.sidebar.success(f"目前帳號：{st.session_state.current_account_name}")
else:
    st.sidebar.warning("尚未選擇帳號")

# 下面各頁面程式碼與之前相同，因篇幅限制此處省略...
# 請直接使用前一次我提供的完整 PostgreSQL 版 app.py
