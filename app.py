import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
from datetime import datetime, date
import openai
import os
import cloudinary
import cloudinary.uploader

st.set_page_config(page_title="Trading Lab", page_icon="⚡", layout="wide")

# ==================== 極簡科技風 CSS ====================
st.markdown("""
<style>
    .stApp { background: #0d1117; }
    [data-testid="stSidebar"] { background: #161b22; border-right: 1px solid #30363d; }
    [data-testid="stSidebar"] * { color: #c9d1d9 !important; }
    h1 { color: #f0f6fc !important; font-weight: 600 !important; font-size: 1.8rem !important; }
    h2, h3 { color: #e6edf3 !important; font-weight: 500 !important; }
    .card { background: rgba(22,27,34,0.8); border: 1px solid #30363d; border-radius: 12px; padding: 24px; margin: 8px 0; }
    .card:hover { border-color: #58a6ff; box-shadow: 0 4px 24px rgba(88,166,255,0.1); }
    .stButton > button { background: #238636; color: #fff !important; border: 1px solid #2ea043; border-radius: 8px; font-weight: 500; }
    .stButton > button:hover { background: #2ea043; }
    .stTextInput > div > div > input, .stTextArea > div > div > textarea, .stSelectbox > div > div { background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #c9d1d9; }
    [data-testid="stMetricValue"] { color: #58a6ff !important; font-weight: 600 !important; }
    [data-testid="stMetricDelta"] { color: #3fb950 !important; }
    div[data-testid="stRadio"] > div { gap: 2px; }
    div[data-testid="stRadio"] label { background: transparent; border: none; border-radius: 8px; padding: 8px 12px; width: 100%; color: #8b949e !important; font-size: 0.9rem; }
    div[data-testid="stRadio"] label:hover { background: #1c2128; color: #c9d1d9 !important; }
    hr { border-color: #30363d; }
    .stSuccess { background: #0d3320; border: 1px solid #238636; }
    .stWarning { background: #332b0d; border: 1px solid #9e6a03; }
</style>
""", unsafe_allow_html=True)

# ==================== Cloudinary ====================
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)

# ==================== OpenAI ====================
openai.api_key = os.environ.get("OPENAI_API_KEY", "")

# ==================== Google Sheets ====================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = {
    "type": os.environ.get("GOOGLE_TYPE", ""),
    "project_id": os.environ.get("GOOGLE_PROJECT_ID", ""),
    "private_key_id": os.environ.get("GOOGLE_PRIVATE_KEY_ID", ""),
    "private_key": os.environ.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": os.environ.get("GOOGLE_CLIENT_EMAIL", ""),
    "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
    "auth_uri": os.environ.get("GOOGLE_AUTH_URI", ""),
    "token_uri": os.environ.get("GOOGLE_TOKEN_URI", ""),
    "auth_provider_x509_cert_url": os.environ.get("GOOGLE_AUTH_PROVIDER_X509_CERT_URL", ""),
    "client_x509_cert_url": os.environ.get("GOOGLE_CLIENT_X509_CERT_URL", "")
}
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

SHEET_ID = os.environ.get("SHEET_ID", "")
if not SHEET_ID:
    st.error("請設定 SHEET_ID")
    st.stop()

sheet = client.open_by_key(SHEET_ID)

def init_sheets():
    sheets_list = [ws.title for ws in sheet.worksheets()]
    if "accounts" not in sheets_list:
        ws = sheet.add_worksheet("accounts", 1000, 10)
        ws.append_row(["id","name","daily_loss_limit","max_loss_limit","created_at"])
    if "strategies" not in sheets_list:
        ws = sheet.add_worksheet("strategies", 1000, 5)
        ws.append_row(["id","name"])
        ws.append_row([1,"無特定策略"]); ws.append_row([2,"策略A"]); ws.append_row([3,"策略B"])
    if "notes" not in sheets_list:
        ws = sheet.add_worksheet("notes", 5000, 12)
        ws.append_row(["id","account_id","strategy_id","symbol","phase","action_detail","reason","mood","is_disciplined","image_url","entry_date"])
    if "trades" not in sheets_list:
        ws = sheet.add_worksheet("trades", 5000, 8)
        ws.append_row(["id","account_id","trade_time","symbol","side","quantity","price","profit"])
    if "symbol_config" not in sheets_list:
        ws = sheet.add_worksheet("symbol_config", 100, 3)
        ws.append_row(["symbol","tick_value"])
        for sym, val in {"MGC":10,"MES":5,"MNQ":2,"MYM":0.5,"M2K":0.5,"ES":50,"NQ":20,"YM":5,"RTY":5,"GC":100,"SI":5000,"CL":1000,"NG":10000,"ZB":1000,"ZN":1000,"ZF":1000,"6E":125000,"6J":12500000,"6B":62500,"6A":100000,"6C":100000,"6S":125000,"HE":400,"LE":400,"ZC":50,"ZW":50,"ZS":50,"CC":10,"KC":375,"CT":500,"SB":1120,"OJ":150}.items():
            ws.append_row([sym, val])

init_sheets()

def get_sheet_data(ws_name):
    ws = sheet.worksheet(ws_name)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()

def append_row(ws_name, row):
    sheet.worksheet(ws_name).append_row(row)

def get_next_id(ws_name):
    ws = sheet.worksheet(ws_name)
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1: return 1
    try: return max([int(r[0]) for r in all_rows[1:] if r[0].isdigit()]) + 1
    except: return 1

if "current_account_id" not in st.session_state:
    st.session_state.current_account_id = None
if "current_account_name" not in st.session_state:
    st.session_state.current_account_name = None

def get_accounts_df(): return get_sheet_data("accounts")
def create_account(name, daily_loss=1000, max_loss=2000):
    df = get_accounts_df()
    if not df.empty and name in df['name'].values: return False, "帳號名稱已存在"
    append_row("accounts", [get_next_id("accounts"), name, daily_loss, max_loss, datetime.now().strftime("%Y-%m-%d %H:%M")])
    return True, "帳號建立成功！"

def delete_account(account_id):
    ws = sheet.worksheet("accounts")
    for i, row in enumerate(ws.get_all_values()):
        if row[0] == str(account_id): ws.delete_rows(i+1); break

def get_strategies_df(): return get_sheet_data("strategies")
def add_strategy(name):
    df = get_strategies_df()
    if not df.empty and name in df['name'].values: return False
    append_row("strategies", [get_next_id("strategies"), name])
    return True

def get_tick_values_df(): return get_sheet_data("symbol_config")

def upload_image_to_cloudinary(image_file):
    if image_file is None: return ""
    try:
        resp = cloudinary.uploader.upload(image_file, folder="trading_journal")
        return resp.get("secure_url", "")
    except Exception as e:
        st.error(f"圖片上傳失敗：{e}")
        return ""

SYMBOLS = ["MGC","MES","MNQ","MYM","M2K","ES","NQ","YM","RTY","GC","SI","CL","NG","ZB","ZN","ZF","6E","6J","6B","6A","6C","6S","HE","LE","ZC","ZW","ZS","CC","KC","CT","SB","OJ"]

# ==================== 側邊欄 ====================
st.sidebar.markdown("<h2 style='text-align:center; color:#58a6ff; font-weight:600;'>⚡ Trading Lab</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align:center; color:#484f58; font-size:0.8rem;'>策略實驗室 v3.0</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")
menu = st.sidebar.radio("", ["🏠 儀表板","👤 帳號管理","🏷️ 策略管理","✍️ 新增筆記","📋 歷史紀錄","📥 匯入CSV","📊 績效分析","🎯 停損停利建議","📉 風險監控","🧠 AI教練"])
if st.session_state.current_account_name:
    st.sidebar.markdown("---")
    st.sidebar.caption(f"🔹 {st.session_state.current_account_name}")
else:
    st.sidebar.markdown("---")
    st.sidebar.warning("⚠️ 尚未選擇帳號")

# ==================== 儀表板 ====================
if menu == "🏠 儀表板":
    st.markdown("<h1>⚡ Trading Lab</h1>", unsafe_allow_html=True)
    st.caption("Prop Firm 交易心理 × 策略優化 × AI 教練")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("👤 帳號")
        if st.session_state.current_account_name:
            st.metric("目前帳號", st.session_state.current_account_name)
            acc = get_accounts_df()
            acc = acc[acc['id'] == st.session_state.current_account_id]
            if not acc.empty: st.caption(f"日虧上限 ${acc.iloc[0]['daily_loss_limit']} | 總虧上限 ${acc.iloc[0]['max_loss_limit']}")
        else: st.warning("未選擇帳號")
        st.markdown("</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("📈 統計")
        if st.session_state.current_account_id:
            t = get_sheet_data("trades"); n = get_sheet_data("notes")
            t = t[t['account_id']==st.session_state.current_account_id] if not t.empty else pd.DataFrame()
            n = n[n['account_id']==st.session_state.current_account_id] if not n.empty else pd.DataFrame()
            st.metric("交易次數", len(t)); st.metric("筆記數量", len(n))
        else: st.caption("請先選擇帳號")
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.subheader("🔮 AI 教練")
        st.caption("隨時分析交易心理與策略")
        st.markdown("</div>", unsafe_allow_html=True)

# ==================== 帳號管理 ====================
elif menu == "👤 帳號管理":
    st.markdown("<h1>👤 帳號管理</h1>", unsafe_allow_html=True)
    accounts_df = get_accounts_df()
    with st.expander("➕ 建立新帳號"):
        new_name = st.text_input("帳號名稱")
        c1, c2 = st.columns(2)
        daily_loss = c1.number_input("每日虧損上限", value=1000, step=100)
        max_loss = c2.number_input("總虧損上限", value=2000, step=100)
        if st.button("建立"):
            if not new_name.strip(): st.warning("請輸入名稱")
            else:
                ok, msg = create_account(new_name.strip(), daily_loss, max_loss)
                st.success(msg) if ok else st.error(msg)
                if ok: st.rerun()
    st.subheader("我的帳號")
    if accounts_df.empty: st.info("尚無帳號")
    else:
        for _, row in accounts_df.iterrows():
            c1, c2, c3 = st.columns([3,1,1])
            c1.write(f"**{row['name']}**")
            if c2.button("選取", key=f"sel_{row['id']}"):
                st.session_state.current_account_id = int(row['id'])
                st.session_state.current_account_name = row['name']
                st.rerun()
            if c3.button("刪除", key=f"del_{row['id']}"):
                delete_account(int(row['id']))
                st.rerun()

# ==================== 策略管理 ====================
elif menu == "🏷️ 策略管理":
    st.markdown("<h1>🏷️ 策略管理</h1>", unsafe_allow_html=True)
    st.dataframe(get_strategies_df(), use_container_width=True)
    new_strat = st.text_input("新策略名稱")
    if st.button("新增策略") and new_strat.strip():
        st.success("已新增") if add_strategy(new_strat.strip()) else st.error("重複或失敗")
        st.rerun()

# ==================== 新增筆記 ====================
elif menu == "✍️ 新增筆記":
    st.markdown("<h1>✍️ 新增交易筆記</h1>", unsafe_allow_html=True)
    if not st.session_state.current_account_id: st.warning("請先選擇帳號")
    else:
        strategies_df = get_strategies_df()
        with st.form("note_form"):
            c1, c2 = st.columns(2)
            symbol = c1.selectbox("商品代碼", SYMBOLS)
            phase = c1.selectbox("交易階段", ["進場","加碼","減碼","移動停利/停損","出場"])
            strategy_id = c1.selectbox("策略", strategies_df['id'].tolist(), format_func=lambda x: strategies_df[strategies_df['id']==x]['name'].values[0]) if not strategies_df.empty else 1
            is_disciplined = c1.checkbox("有照計畫執行？", True)
            entry_datetime = c1.text_input("日期時間", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
            action_detail = c2.text_input("動作細節")
            reason = c2.text_area("理由 *")
            mood = c2.text_input("心情")
            uploaded_image = c2.file_uploader("截圖 (可選)", type=["png","jpg","jpeg"])
            if st.form_submit_button("儲存"):
                if not reason.strip(): st.warning("理由必填")
                else:
                    image_url = upload_image_to_cloudinary(uploaded_image) if uploaded_image else ""
                    append_row("notes", [get_next_id("notes"), st.session_state.current_account_id, int(strategy_id), symbol, phase, action_detail.strip(), reason.strip(), mood.strip(), 1 if is_disciplined else 0, image_url, entry_datetime])
                    st.success("筆記已儲存！")

# ==================== 歷史紀錄 ====================
elif menu == "📋 歷史紀錄":
    st.markdown("<h1>📋 歷史紀錄</h1>", unsafe_allow_html=True)
    if not st.session_state.current_account_id: st.warning("請先選擇帳號")
    else:
        notes_df = get_sheet_data("notes")
        if notes_df.empty: st.info("尚無紀錄")
        else:
            notes_df = notes_df[notes_df['account_id'] == st.session_state.current_account_id]
            st.dataframe(notes_df, use_container_width=True) if not notes_df.empty else st.info("尚無紀錄")

# ==================== 匯入CSV ====================
elif menu == "📥 匯入CSV":
    st.markdown("<h1>📥 匯入 Topstep CSV</h1>", unsafe_allow_html=True)
    if not st.session_state.current_account_id: st.warning("請先選擇帳號")
    else:
        uploaded = st.file_uploader("選擇 CSV", type="csv")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                if not {"Date","Symbol","Side","Quantity","Price","Profit"}.issubset(df.columns): st.error("缺少必要欄位")
                else:
                    st.dataframe(df.head())
                    if st.button("確認匯入"):
                        for _, row in df.iterrows():
                            try: t = pd.to_datetime(row['Date']).strftime("%Y-%m-%d %H:%M")
                            except: t = str(row['Date'])
                            append_row("trades", [get_next_id("trades"), st.session_state.current_account_id, t, str(row['Symbol']).upper(), str(row['Side']), float(row['Quantity']), float(row['Price']), float(row['Profit'])])
                        st.success(f"匯入 {len(df)} 筆"); st.rerun()
            except Exception as e: st.error(f"錯誤：{e}")

# ==================== 績效分析 ====================
elif menu == "📊 績效分析":
    st.markdown("<h1>📊 績效分析</h1>", unsafe_allow_html=True)
    if not st.session_state.current_account_id: st.warning("請先選擇帳號")
    else:
        trades_df = get_sheet_data("trades")
        if trades_df.empty: st.info("尚無交易紀錄")
        else:
            trades_df = trades_df[trades_df['account_id'] == st.session_state.current_account_id]
            if trades_df.empty: st.info("尚無交易紀錄")
            else:
                trades_df['profit'] = pd.to_numeric(trades_df['profit'], errors='coerce').fillna(0)
                wins = trades_df[trades_df['profit'] > 0]
                total = len(trades_df)
                wr = len(wins)/total*100 if total>0 else 0
                pnl = trades_df['profit'].sum()
                c1,c2,c3 = st.columns(3)
                c1.metric("總交易", total); c2.metric("勝率", f"{wr:.1f}%"); c3.metric("總盈虧", f"${pnl:,.2f}")

# ==================== 停損停利建議 ====================
elif menu == "🎯 停損停利建議":
    st.markdown("<h1>🎯 停損停利建議</h1>", unsafe_allow_html=True)
    if not st.session_state.current_account_id: st.warning("請先選擇帳號")
    else:
        st.subheader("🧠 AI 通用建議")
        ai_sym = st.selectbox("選擇商品", SYMBOLS, key="ai_sym")
        ai_desc = st.text_area("策略簡述（選填）", key="ai_desc")
        if st.button("生成 AI 建議"):
            if not openai.api_key: st.warning("請先設定 OpenAI API Key")
            else:
                prompt = f"你是專業期貨交易教練。交易員想交易 {ai_sym}。{'他的策略：'+ai_desc if ai_desc else '未提供策略。'}請提供：1.建議停損點數 2.建議停利點數 3.風險控管重點 4.策略優化建議（繁體中文，條列式）"
                with st.spinner("AI 思考中..."):
                    try:
                        resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7)
                        st.write(resp.choices[0].message.content)
                    except Exception as e: st.error(f"API 錯誤：{e}")

# ==================== 風險監控 ====================
elif menu == "📉 風險監控":
    st.markdown("<h1>📉 風險監控</h1>", unsafe_allow_html=True)
    if not st.session_state.current_account_id: st.warning("請先選擇帳號")
    else:
        accounts_df = get_accounts_df()
        if not accounts_df.empty:
            acc = accounts_df[accounts_df['id'] == st.session_state.current_account_id]
            if not acc.empty:
                max_limit = float(acc.iloc[0]['max_loss_limit'])
                trades_df = get_sheet_data("trades")
                total_pnl = 0.0
                if not trades_df.empty:
                    t = trades_df[trades_df['account_id'] == st.session_state.current_account_id]
                    if not t.empty:
                        t['profit'] = pd.to_numeric(t['profit'], errors='coerce').fillna(0)
                        total_pnl = t['profit'].sum()
                def light(v, l):
                    if v <= -l: return "🔴 超過上限"
                    elif v <= -l*0.7: return "🟡 接近上限"
                    return "🟢 安全"
                st.metric("累計盈虧", f"${total_pnl:,.2f}")
                st.caption(light(total_pnl, max_limit))

# ==================== AI教練 ====================
elif menu == "🧠 AI教練":
    st.markdown("<h1>🧠 AI 交易教練</h1>", unsafe_allow_html=True)
    if not st.session_state.current_account_id: st.warning("請先選擇帳號")
    else:
        if not openai.api_key:
            openai.api_key = st.text_input("OpenAI API Key", type="password")
            if not openai.api_key: st.stop()
        use_notes = st.checkbox("包含筆記", True)
        use_trades = st.checkbox("包含 CSV", True)
        use_risk = st.checkbox("包含風險數據", True)
        num = st.slider("分析筆數", 3, 30, 10)
        if st.button("請求教練分析"):
            with st.spinner("分析中..."):
                context = ""; aid = st.session_state.current_account_id
                if use_notes:
                    ndf = get_sheet_data("notes")
                    if not ndf.empty:
                        ndf = ndf[ndf['account_id']==aid]
                        if not ndf.empty:
                            context += "📝 筆記：\n"
                            for _, r in ndf.tail(num).iterrows(): context += f"- {r.get('entry_date','')} | {r.get('symbol','')} | {r.get('phase','')} | 心情:{r.get('mood','')} | 理由:{r.get('reason','')}\n"
                            context += "\n"
                if use_trades:
                    tdf = get_sheet_data("trades")
                    if not tdf.empty:
                        tdf = tdf[tdf['account_id']==aid]
                        if not tdf.empty:
                            context += "📈 CSV：\n"
                            for _, r in tdf.tail(num).iterrows(): context += f"- {r.get('trade_time','')} | {r.get('symbol','')} | {r.get('side','')} {r.get('quantity','')}口 @{r.get('price','')} | 盈虧:{r.get('profit','')}\n"
                            context += "\n"
                if use_risk:
                    acc = get_accounts_df()
                    if not acc.empty:
                        acc = acc[acc['id']==aid]
                        if not acc.empty:
                            tdf = get_sheet_data("trades")
                            pnl = 0.0
                            if not tdf.empty:
                                t = tdf[tdf['account_id']==aid]
                                if not t.empty: pnl = pd.to_numeric(t['profit'], errors='coerce').fillna(0).sum()
                            context += f"⚠️ 風險：日虧上限 ${acc.iloc[0]['daily_loss_limit']}，總虧上限 ${acc.iloc[0]['max_loss_limit']}，目前盈虧 ${pnl:,.2f}\n"
                if not context: st.warning("沒有資料")
                else:
                    prompt = f"你是資深交易教練，請分析以下紀錄給出具體改善建議（繁體中文）：\n{context}\n請分析：1.情緒模式 2.進出場一致性 3.具體改善行動 4.總結"
                    try:
                        resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7, max_tokens=1500)
                        st.markdown("### 教練建議")
                        st.write(resp.choices[0].message.content)
                    except Exception as e: st.error(f"API 錯誤：{e}")
