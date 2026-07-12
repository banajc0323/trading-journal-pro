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

st.set_page_config(page_title="🚀 Trading Lab", page_icon="🛸", layout="wide")

# ==================== 太空主題 CSS ====================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, sans-serif;
        color: #e0e7ff;
        font-size: 16px;
    }
    .stApp {
        background: radial-gradient(ellipse at bottom, #0d1b2a 0%, #020617 70%);
        background-attachment: fixed;
    }
    /* 側邊欄 */
    [data-testid="stSidebar"] {
        background: rgba(10, 20, 40, 0.85);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(56, 189, 248, 0.2);
    }
    [data-testid="stSidebar"] * {
        color: #bae6fd !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        font-size: 1rem;
        padding: 0.5rem;
        border-radius: 6px;
    }
    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(56, 189, 248, 0.1);
    }
    /* 標題 */
    h1, h2, h3 {
        color: #38bdf8 !important;
        font-weight: 600;
    }
    h1 { font-size: 2rem !important; }
    h2 { font-size: 1.5rem !important; }
    h3 { font-size: 1.3rem !important; }
    /* 按鈕 */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb, #7c3aed);
        color: white !important;
        border: none;
        border-radius: 0.5rem;
        font-weight: 600;
        padding: 0.6rem 1.2rem;
        font-size: 1rem;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.3);
        transition: all 0.2s;
    }
    .stButton > button:hover {
        box-shadow: 0 0 25px rgba(56, 189, 248, 0.6);
        transform: scale(1.02);
    }
    /* 卡片 */
    .card, .stMetric, .streamlit-expanderHeader {
        background: rgba(15, 25, 45, 0.7);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    /* 輸入框 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background: rgba(15, 25, 45, 0.8);
        border: 1px solid rgba(56, 189, 248, 0.4);
        color: #e0e7ff;
        font-size: 1rem;
        border-radius: 8px;
    }
    /* 數字指標 */
    [data-testid="stMetricValue"] {
        color: #38bdf8 !important;
        font-weight: 700;
        font-size: 2rem !important;
    }
    /* 工具列隱藏 */
    [data-testid="stToolbar"] { display: none; }
    /* 手機適配 */
    @media (max-width: 768px) {
        h1 { font-size: 1.6rem !important; }
        h2 { font-size: 1.3rem !important; }
        .stButton > button { width: 100%; }
    }
</style>
""", unsafe_allow_html=True)

# ==================== 服務設定 ====================
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)
openai.api_key = os.environ.get("OPENAI_API_KEY", "")

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
st.sidebar.markdown("<h2 style='color:#38bdf8;'>🚀 Trading Lab</h2>", unsafe_allow_html=True)
st.sidebar.caption("星際交易指揮中心")
st.sidebar.markdown("---")
menu = st.sidebar.radio("", ["🛸 儀表板","👤 帳號管理","🏷️ 策略管理","✍️ 新增筆記","📋 歷史紀錄","📥 匯入CSV","📊 績效分析","🎯 停損停利建議","📉 風險監控","🧠 AI教練"])
if st.session_state.current_account_name:
    st.sidebar.markdown("---")
    st.sidebar.caption(f"🔹 {st.session_state.current_account_name}")
else:
    st.sidebar.markdown("---")
    st.sidebar.warning("⚠️ 尚未選擇帳號")

# ==================== 儀表板 ====================
if menu == "🛸 儀表板":
    st.header("🛸 星際交易中心")
    st.caption("光速紀律 · 蟲洞風險 · 量子 AI 教練")
    c1, c2, c3 = st.columns(3)
    with c1:
        with st.container():
            st.subheader("👤 帳號")
            if st.session_state.current_account_name:
                st.metric("目前帳號", st.session_state.current_account_name)
                acc = get_accounts_df()
                acc = acc[acc['id'] == st.session_state.current_account_id]
                if not acc.empty:
                    st.caption(f"日虧上限 ${acc.iloc[0]['daily_loss_limit']} | 總虧上限 ${acc.iloc[0]['max_loss_limit']}")
            else:
                st.warning("未選擇帳號")
    with c2:
        with st.container():
            st.subheader("📈 快速統計")
            if st.session_state.current_account_id:
                t = get_sheet_data("trades"); n = get_sheet_data("notes")
                t = t[t['account_id']==st.session_state.current_account_id] if not t.empty else pd.DataFrame()
                n = n[n['account_id']==st.session_state.current_account_id] if not n.empty else pd.DataFrame()
                st.metric("交易次數", len(t))
                st.metric("筆記數量", len(n))
            else:
                st.caption("請先選擇帳號")
    with c3:
        with st.container():
            st.subheader("🔮 AI 教練")
            st.caption("隨時分析交易靈魂與策略")

# ==================== 帳號管理 ====================
elif menu == "👤 帳號管理":
    st.header("👤 帳號管理")
    accounts_df = get_accounts_df()
    with st.expander("➕ 建立新帳號"):
        new_name = st.text_input("帳號名稱")
        c1, c2 = st.columns(2)
        daily_loss = c1.number_input("每日虧損上限", value=1000, step=100)
        max_loss = c2.number_input("總虧損上限", value=2000, step=100)
        if st.button("建立"):
            if not new_name.strip():
                st.warning("請輸入名稱")
            else:
                ok, msg = create_account(new_name.strip(), daily_loss, max_loss)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    st.subheader("我的帳號")
    if accounts_df.empty:
        st.info("尚無帳號")
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
    st.header("🏷️ 策略管理")
    st.dataframe(get_strategies_df(), use_container_width=True)
    new_strat = st.text_input("新策略名稱")
    if st.button("新增策略"):
        if new_strat.strip():
            if add_strategy(new_strat.strip()):
                st.success("已新增")
                st.rerun()
            else:
                st.error("重複或失敗")

# ==================== 新增筆記 ====================
elif menu == "✍️ 新增筆記":
    st.header("✍️ 新增交易筆記")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        strategies_df = get_strategies_df()
        with st.form("note_form"):
            c1, c2 = st.columns(2)
            symbol = c1.selectbox("商品代碼", SYMBOLS)
            phase = c1.selectbox("交易階段", ["進場","加碼","減碼","移動停利/停損","出場"])
            strategy_id = c1.selectbox("策略", strategies_df['id'].tolist(),
                                       format_func=lambda x: strategies_df[strategies_df['id']==x]['name'].values[0]) if not strategies_df.empty else 1
            is_disciplined = c1.checkbox("有照計畫執行？", True)
            entry_datetime = c1.text_input("日期時間", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
            action_detail = c2.text_input("動作細節")
            reason = c2.text_area("理由 *")
            mood = c2.text_input("心情")
            uploaded_image = c2.file_uploader("截圖 (可選)", type=["png","jpg","jpeg"])
            if st.form_submit_button("儲存"):
                if not reason.strip():
                    st.warning("理由必填")
                else:
                    image_url = upload_image_to_cloudinary(uploaded_image) if uploaded_image else ""
                    append_row("notes", [get_next_id("notes"), st.session_state.current_account_id, int(strategy_id), symbol, phase, action_detail.strip(), reason.strip(), mood.strip(), 1 if is_disciplined else 0, image_url, entry_datetime])
                    st.success("筆記已儲存！")

# ==================== 歷史紀錄 ====================
elif menu == "📋 歷史紀錄":
    st.header("📋 歷史紀錄")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        notes_df = get_sheet_data("notes")
        if notes_df.empty:
            st.info("尚無紀錄")
        else:
            notes_df = notes_df[notes_df['account_id'] == st.session_state.current_account_id]
            if notes_df.empty:
                st.info("尚無紀錄")
            else:
                st.dataframe(notes_df, use_container_width=True)

# ==================== 匯入CSV ====================
elif menu == "📥 匯入CSV":
    st.header("📥 匯入 Topstep CSV")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        uploaded = st.file_uploader("選擇 CSV", type="csv")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                required = {"Date","Symbol","Side","Quantity","Price","Profit"}
                if not required.issubset(df.columns):
                    st.error(f"缺少必要欄位：{required - set(df.columns)}")
                else:
                    st.dataframe(df.head())
                    if st.button("確認匯入"):
                        for _, row in df.iterrows():
                            try:
                                t = pd.to_datetime(row['Date']).strftime("%Y-%m-%d %H:%M")
                            except:
                                t = str(row['Date'])
                            append_row("trades", [get_next_id("trades"), st.session_state.current_account_id, t, str(row['Symbol']).upper(), str(row['Side']), float(row['Quantity']), float(row['Price']), float(row['Profit'])])
                        st.success(f"匯入 {len(df)} 筆")
                        st.rerun()
            except Exception as e:
                st.error(f"錯誤：{e}")

# ==================== 績效分析 ====================
elif menu == "📊 績效分析":
    st.header("📊 績效分析")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        trades_df = get_sheet_data("trades")
        if trades_df.empty:
            st.info("尚無交易紀錄")
        else:
            trades_df = trades_df[trades_df['account_id'] == st.session_state.current_account_id]
            if trades_df.empty:
                st.info("尚無交易紀錄")
            else:
                trades_df['profit'] = pd.to_numeric(trades_df['profit'], errors='coerce').fillna(0)
                wins = trades_df[trades_df['profit'] > 0]
                total = len(trades_df)
                wr = len(wins)/total*100 if total>0 else 0
                pnl = trades_df['profit'].sum()
                c1,c2,c3 = st.columns(3)
                c1.metric("總交易", total)
                c2.metric("勝率", f"{wr:.1f}%")
                c3.metric("總盈虧", f"${pnl:,.2f}")

# ==================== 停損停利建議 ====================
elif menu == "🎯 停損停利建議":
    st.header("🎯 停損停利建議")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        st.subheader("🧠 AI 通用建議")
        ai_sym = st.selectbox("選擇商品", SYMBOLS, key="ai_sym")
        ai_desc = st.text_area("策略簡述（選填）", key="ai_desc")
        if st.button("生成 AI 建議"):
            if not openai.api_key:
                st.warning("請先設定 OpenAI API Key")
            else:
                prompt = f"你是專業期貨交易教練。交易員想交易 {ai_sym}。{'他的策略：'+ai_desc if ai_desc else '未提供策略。'}請提供：1.建議停損點數 2.建議停利點數 3.風險控管重點 4.策略優化建議（繁體中文，條列式）"
                with st.spinner("AI 思考中..."):
                    try:
                        resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7)
                        st.write(resp.choices[0].message.content)
                    except Exception as e:
                        st.error(f"API 錯誤：{e}")

# ==================== 風險監控 ====================
elif menu == "📉 風險監控":
    st.header("📉 風險監控")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
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
    st.header("🧠 量子 AI 交易教練")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        if not openai.api_key:
            openai.api_key = st.text_input("OpenAI API Key", type="password")
            if not openai.api_key: st.stop()

        coach_style = st.selectbox("教練語氣", ["🟢 溫和教練", "🟡 直接誠實", "🔴 殘酷嚴格"])
        use_notes = st.checkbox("包含筆記", True)
        use_trades = st.checkbox("包含 CSV", True)
        use_risk = st.checkbox("包含風險數據", True)
        num = st.slider("分析筆數", 3, 30, 10)

        SYSTEM_PROMPT = """你是我長期合作的決策夥伴，不是一次性的問答使用者。
你的首要目標不是回答問題，而是幫助我提高決策品質、降低風險、提升執行效率，並建立可持續演進的成果。

【最高原則】當不同目標互相衝突時，請依照以下優先順序：1.真實 2.安全與風險 3.證據 4.邏輯 5.長期影響 6.效率。不要因為追求效率或迎合而犧牲真實性。

【思考方式】先確認我真正想解決的問題、問題定義是否正確、成功標準、限制、最大假設與風險。若我問錯問題，請直接指出真正需要解決的問題。

【分析原則】整合多領域知識，權衡衝突時清楚說明衝突點、理由、成本、風險與長期影響，再提出整合建議。

【回答原則】清楚區分已知事實、推論、假設、不確定性、個人判斷。不要把推論說成事實。沒有足夠證據就直說不知道。

【合作方式】挑戰我的假設、挑戰你自己的推論，找出盲點與偏誤。你的責任不是證明誰是對的，而是一起找到最接近真實的答案。

【溝通風格】直接、專業、誠實，不要客套或刻意鼓勵。若我的想法有問題，請直接指出。不確定性也請清楚說明。"""

        style_instruction = {
            "🟢 溫和教練": "請在回覆時保持鼓勵和支持的語氣，但依然真實直接，不要隱瞞問題。",
            "🟡 直接誠實": "請直接點出問題，不要拐彎抹角。不需要多餘的客套，但保持專業。",
            "🔴 殘酷嚴格": "請以最嚴厲、不留情面的方式批評錯誤，使用強烈字眼，讓交易員銘記教訓。"
        }

        if st.button("請求教練分析"):
            with st.spinner("分析中..."):
                context = ""
                aid = st.session_state.current_account_id
                if use_notes:
                    ndf = get_sheet_data("notes")
                    if not ndf.empty:
                        ndf = ndf[ndf['account_id']==aid]
                        if not ndf.empty:
                            context += "📝 筆記：\n"
                            for _, r in ndf.tail(num).iterrows():
                                context += f"- {r.get('entry_date','')} | {r.get('symbol','')} | {r.get('phase','')} | 心情:{r.get('mood','')} | 理由:{r.get('reason','')}\n"
                            context += "\n"
                if use_trades:
                    tdf = get_sheet_data("trades")
                    if not tdf.empty:
                        tdf = tdf[tdf['account_id']==aid]
                        if not tdf.empty:
                            context += "📈 CSV：\n"
                            for _, r in tdf.tail(num).iterrows():
                                context += f"- {r.get('trade_time','')} | {r.get('symbol','')} | {r.get('side','')} {r.get('quantity','')}口 @{r.get('price','')} | 盈虧:{r.get('profit','')}\n"
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
                                if not t.empty:
                                    pnl = pd.to_numeric(t['profit'], errors='coerce').fillna(0).sum()
                            context += f"⚠️ 風險：日虧上限 ${acc.iloc[0]['daily_loss_limit']}，總虧上限 ${acc.iloc[0]['max_loss_limit']}，目前盈虧 ${pnl:,.2f}\n"
                if not context:
                    st.warning("沒有資料")
                else:
                    user_prompt = f"以下是交易員的近期紀錄，請根據你的原則進行分析。\n\n{context}\n\n{style_instruction[coach_style]}"
                    messages = [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ]
                    try:
                        resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=messages, temperature=0.7, max_tokens=1500)
                        st.markdown("### 量子艦隊指揮官建議")
                        st.write(resp.choices[0].message.content)
                    except Exception as e:
                        st.error(f"API 錯誤：{e}")
