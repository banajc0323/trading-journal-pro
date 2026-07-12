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

st.set_page_config(page_title="交易策略實驗室 Pro", page_icon="📓")

# ==================== Cloudinary ====================
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)

# ==================== OpenAI ====================
openai.api_key = os.environ.get("OPENAI_API_KEY", "")

# ==================== Google Sheets 連線 ====================
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

# ==================== 初始化工作表 ====================
def init_sheets():
    sheets_list = [ws.title for ws in sheet.worksheets()]
    if "accounts" not in sheets_list:
        ws = sheet.add_worksheet("accounts", 1000, 10)
        ws.append_row(["id", "name", "daily_loss_limit", "max_loss_limit", "created_at"])
    if "strategies" not in sheets_list:
        ws = sheet.add_worksheet("strategies", 1000, 5)
        ws.append_row(["id", "name"])
        ws.append_row([1, "無特定策略"])
        ws.append_row([2, "策略A"])
        ws.append_row([3, "策略B"])
    if "notes" not in sheets_list:
        ws = sheet.add_worksheet("notes", 5000, 12)
        ws.append_row(["id", "account_id", "strategy_id", "symbol", "phase", "action_detail", "reason", "mood", "is_disciplined", "image_url", "entry_date"])
    if "trades" not in sheets_list:
        ws = sheet.add_worksheet("trades", 5000, 8)
        ws.append_row(["id", "account_id", "trade_time", "symbol", "side", "quantity", "price", "profit"])
    if "symbol_config" not in sheets_list:
        ws = sheet.add_worksheet("symbol_config", 100, 3)
        ws.append_row(["symbol", "tick_value"])
        for sym, val in {
            "MGC":10,"MES":5,"MNQ":2,"MYM":0.5,"M2K":0.5,"ES":50,"NQ":20,"YM":5,"RTY":5,
            "GC":100,"SI":5000,"CL":1000,"NG":10000,"ZB":1000,"ZN":1000,"ZF":1000,
            "6E":125000,"6J":12500000,"6B":62500,"6A":100000,"6C":100000,"6S":125000,
            "HE":400,"LE":400,"ZC":50,"ZW":50,"ZS":50,"CC":10,"KC":375,"CT":500,"SB":1120,"OJ":150
        }.items():
            ws.append_row([sym, val])

init_sheets()

# ==================== 輔助函式 ====================
def get_sheet_data(ws_name):
    ws = sheet.worksheet(ws_name)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()

def append_row(ws_name, row):
    ws = sheet.worksheet(ws_name)
    ws.append_row(row)

def get_next_id(ws_name):
    ws = sheet.worksheet(ws_name)
    all_rows = ws.get_all_values()
    if len(all_rows) <= 1:
        return 1
    try:
        return max([int(r[0]) for r in all_rows[1:] if r[0].isdigit()]) + 1
    except:
        return 1

# ==================== Session State ====================
if "current_account_id" not in st.session_state:
    st.session_state.current_account_id = None
if "current_account_name" not in st.session_state:
    st.session_state.current_account_name = None

def get_accounts_df():
    return get_sheet_data("accounts")

def create_account(name, daily_loss=1000, max_loss=2000):
    df = get_accounts_df()
    if not df.empty and name in df['name'].values:
        return False, "帳號名稱已存在"
    new_id = get_next_id("accounts")
    append_row("accounts", [new_id, name, daily_loss, max_loss, datetime.now().strftime("%Y-%m-%d %H:%M")])
    return True, "帳號建立成功！"

def delete_account(account_id):
    ws = sheet.worksheet("accounts")
    rows = ws.get_all_values()
    for i, row in enumerate(rows):
        if row[0] == str(account_id):
            ws.delete_rows(i+1)
            break

def get_strategies_df():
    return get_sheet_data("strategies")

def add_strategy(name):
    df = get_strategies_df()
    if not df.empty and name in df['name'].values:
        return False
    new_id = get_next_id("strategies")
    append_row("strategies", [new_id, name])
    return True

def get_tick_values_df():
    return get_sheet_data("symbol_config")

def upload_image_to_cloudinary(image_file):
    if image_file is None:
        return ""
    try:
        response = cloudinary.uploader.upload(image_file, folder="trading_journal")
        return response.get("secure_url", "")
    except Exception as e:
        st.error(f"圖片上傳失敗：{e}")
        return ""

# ==================== 商品清單 ====================
SYMBOLS = [
    "MGC","MES","MNQ","MYM","M2K","ES","NQ","YM","RTY",
    "GC","SI","CL","NG","ZB","ZN","ZF",
    "6E","6J","6B","6A","6C","6S",
    "HE","LE","ZC","ZW","ZS","CC","KC","CT","SB","OJ"
]

# ==================== 側邊欄 ====================
st.sidebar.title("📓 交易策略實驗室 Pro")
menu = st.sidebar.radio("選單", [
    "🏠 帳號管理","🏷️ 策略管理","✍️ 新增筆記","📋 歷史紀錄",
    "📥 匯入CSV","📊 績效分析","🎯 停損停利建議","📉 風險監控","🧠 AI教練"
])
if st.session_state.current_account_name:
    st.sidebar.success(f"目前帳號：{st.session_state.current_account_name}")
else:
    st.sidebar.warning("尚未選擇帳號")

# ==================== 帳號管理 ====================
if menu == "🏠 帳號管理":
    st.title("🏠 帳號管理")
    accounts_df = get_accounts_df()
    with st.expander("➕ 建立新帳號"):
        new_name = st.text_input("帳號名稱")
        c1, c2 = st.columns(2)
        daily_loss = c1.number_input("每日虧損上限", value=1000, step=100)
        max_loss = c2.number_input("總虧損上限", value=2000, step=100)
        if st.button("建立帳號"):
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
    st.title("🏷️ 策略管理")
    st.dataframe(get_strategies_df())
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
    st.title("✍️ 新增交易筆記")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        strategies_df = get_strategies_df()
        with st.form("note_form"):
            c1, c2 = st.columns(2)
            symbol = c1.selectbox("商品代碼", SYMBOLS)
            phase = c1.selectbox("交易階段", ["進場","加碼","減碼","移動停利/停損","出場"])
            if not strategies_df.empty:
                strategy_id = c1.selectbox("策略", strategies_df['id'].tolist(),
                    format_func=lambda x: strategies_df[strategies_df['id']==x]['name'].values[0])
            else:
                strategy_id = 1
            is_disciplined = c1.checkbox("有照計畫執行？", value=True)
            entry_datetime = c1.text_input("日期時間", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
            action_detail = c2.text_input("動作細節")
            reason = c2.text_area("理由 *")
            mood = c2.text_input("心情")
            uploaded_image = c2.file_uploader("截圖 (可選)", type=["png","jpg","jpeg"])
            if st.form_submit_button("儲存"):
                if not reason.strip():
                    st.warning("理由必填")
                else:
                    try:
                        datetime.strptime(entry_datetime, "%Y-%m-%d %H:%M")
                    except:
                        st.error("日期格式錯誤")
                        st.stop()
                    image_url = upload_image_to_cloudinary(uploaded_image) if uploaded_image else ""
                    new_id = get_next_id("notes")
                    append_row("notes", [new_id, st.session_state.current_account_id, int(strategy_id), symbol, phase,
                                         action_detail.strip(), reason.strip(), mood.strip(),
                                         1 if is_disciplined else 0, image_url, entry_datetime])
                    st.success("筆記已儲存！")

# ==================== 歷史紀錄 ====================
elif menu == "📋 歷史紀錄":
    st.title("📋 歷史紀錄")
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

# ==================== 匯入 CSV ====================
elif menu == "📥 匯入CSV":
    st.title("📥 匯入 Topstep CSV")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        uploaded = st.file_uploader("選擇 CSV", type="csv")
        if uploaded:
            try:
                df = pd.read_csv(uploaded)
                required = {"Date","Symbol","Side","Quantity","Price","Profit"}
                if not required.issubset(df.columns):
                    st.error(f"缺少欄位：{required-set(df.columns)}")
                else:
                    st.dataframe(df.head())
                    if st.button("確認匯入"):
                        for _, row in df.iterrows():
                            new_id = get_next_id("trades")
                            try:
                                t = pd.to_datetime(row['Date']).strftime("%Y-%m-%d %H:%M")
                            except:
                                t = str(row['Date'])
                            append_row("trades", [new_id, st.session_state.current_account_id, t,
                                                  str(row['Symbol']).upper(), str(row['Side']),
                                                  float(row['Quantity']), float(row['Price']), float(row['Profit'])])
                        st.success(f"匯入 {len(df)} 筆")
                        st.rerun()
            except Exception as e:
                st.error(f"錯誤：{e}")

# ==================== 績效分析 ====================
elif menu == "📊 績效分析":
    st.title("📊 績效分析")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        trades_df = get_sheet_data("trades")
        if not trades_df.empty:
            trades_df = trades_df[trades_df['account_id'] == st.session_state.current_account_id]
            if not trades_df.empty:
                trades_df['profit'] = pd.to_numeric(trades_df['profit'], errors='coerce').fillna(0)
                wins = trades_df[trades_df['profit'] > 0]
                total_trades = len(trades_df)
                win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
                total_pnl = trades_df['profit'].sum()
                avg_win = wins['profit'].mean() if len(wins) > 0 else 0
                avg_loss = trades_df[trades_df['profit'] < 0]['profit'].mean() if len(trades_df[trades_df['profit'] < 0]) > 0 else 0
                profit_factor = wins['profit'].sum() / abs(trades_df[trades_df['profit'] < 0]['profit'].sum()) if len(trades_df[trades_df['profit'] < 0]) > 0 else np.inf

                col1, col2, col3 = st.columns(3)
                col1.metric("總交易次數", total_trades)
                col2.metric("勝率", f"{win_rate:.1f}%")
                col3.metric("總盈虧", f"${total_pnl:,.2f}")
                col1.metric("平均贏", f"${avg_win:,.2f}")
                col2.metric("平均輸", f"${avg_loss:,.2f}")
                col3.metric("利潤因子", f"{profit_factor:.2f}" if profit_factor != np.inf else "∞")
            else:
                st.info("尚無交易紀錄")
        else:
            st.info("尚無交易紀錄")

# ==================== 停損停利建議 ====================
elif menu == "🎯 停損停利建議":
    st.title("🎯 停損停利建議")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        with st.expander("⚙️ 商品每點價值設定"):
            tv_df = get_tick_values_df()
            st.dataframe(tv_df, use_container_width=True)

        st.subheader("🧠 AI 通用建議（無需歷史紀錄）")
        ai_sym = st.selectbox("選擇商品", SYMBOLS, key="ai_sym")
        ai_desc = st.text_area("策略簡述（選填）", key="ai_desc")
        if st.button("生成 AI 建議"):
            if not openai.api_key:
                st.warning("請先設定 OpenAI API Key")
            else:
                tv_df = get_tick_values_df()
                tick_val = "未知"
                if not tv_df.empty:
                    match = tv_df[tv_df['symbol'] == ai_sym]
                    if not match.empty:
                        tick_val = match.iloc[0]['tick_value']
                prompt = f"""你是一位專業期貨交易教練。交易員想交易 {ai_sym}（每點價值約 {tick_val} 美元）。
{'他的策略：' + ai_desc if ai_desc else '未提供策略細節。'}
請提供：
1. 建議的初始停損點數及原因
2. 建議的初始停利點數（或分批出場方式）及原因
3. 該商品需注意的風險控管重點
4. 策略優化建議（繁體中文，條列式，語氣親切）"""
                with st.spinner("AI 思考中..."):
                    try:
                        resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7)
                        st.write(resp.choices[0].message.content)
                    except Exception as e:
                        st.error(f"API 錯誤：{e}")

# ==================== 風險監控 ====================
elif menu == "📉 風險監控":
    st.title("📉 風險監控")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        accounts_df = get_accounts_df()
        if not accounts_df.empty:
            acc = accounts_df[accounts_df['id'] == st.session_state.current_account_id]
            if not acc.empty:
                daily_limit = float(acc.iloc[0]['daily_loss_limit'])
                max_limit = float(acc.iloc[0]['max_loss_limit'])
                trades_df = get_sheet_data("trades")
                today_str = date.today().isoformat()
                total_pnl = 0.0
                today_pnl = 0.0
                if not trades_df.empty:
                    trades_df = trades_df[trades_df['account_id'] == st.session_state.current_account_id]
                    if not trades_df.empty:
                        trades_df['profit'] = pd.to_numeric(trades_df['profit'], errors='coerce').fillna(0)
                        total_pnl = trades_df['profit'].sum()
                        if 'trade_time' in trades_df.columns:
                            today_trades = trades_df[trades_df['trade_time'].str.startswith(today_str)]
                            today_pnl = today_trades['profit'].sum() if not today_trades.empty else 0.0

                def light(val, limit):
                    if val <= -limit:
                        return "🔴 已超過上限！"
                    elif val <= -limit * 0.7:
                        return "🟡 接近上限"
                    else:
                        return "🟢 安全"

                col1, col2 = st.columns(2)
                col1.metric("今日盈虧", f"${today_pnl:,.2f}")
                col1.caption(light(today_pnl, daily_limit))
                col2.metric("累計盈虧", f"${total_pnl:,.2f}")
                col2.caption(light(total_pnl, max_limit))
            else:
                st.info("帳號資料異常")
        else:
            st.info("尚無帳號")

# ==================== AI 教練 ====================
elif menu == "🧠 AI教練":
    st.title("🧠 AI 交易教練（策略+風險）")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        if not openai.api_key:
            openai.api_key = st.text_input("OpenAI API Key", type="password")
            if not openai.api_key:
                st.stop()
        use_notes = st.checkbox("包含筆記", True)
        use_trades = st.checkbox("包含 CSV", True)
        use_risk = st.checkbox("包含風險數據", True)
        num = st.slider("分析筆數", 3, 30, 10)
        if st.button("請求教練分析"):
            with st.spinner("分析中..."):
                context = ""
                aid = st.session_state.current_account_id

                if use_notes:
                    notes_df = get_sheet_data("notes")
                    if not notes_df.empty:
                        notes_df = notes_df[notes_df['account_id'] == aid]
                        if not notes_df.empty:
                            notes_df = notes_df.tail(num)
                            context += "📝 交易筆記：\n"
                            for _, r in notes_df.iterrows():
                                context += f"- {r.get('entry_date','')} | {r.get('symbol','')} | {r.get('phase','')} | 心情:{r.get('mood','')} | 理由:{r.get('reason','')}\n"
                            context += "\n"

                if use_trades:
                    trades_df = get_sheet_data("trades")
                    if not trades_df.empty:
                        trades_df = trades_df[trades_df['account_id'] == aid]
                        if not trades_df.empty:
                            trades_df = trades_df.tail(num)
                            context += "📈 CSV交易紀錄：\n"
                            for _, r in trades_df.iterrows():
                                context += f"- {r.get('trade_time','')} | {r.get('symbol','')} | {r.get('side','')} {r.get('quantity','')}口 @{r.get('price','')} | 盈虧:{r.get('profit','')}\n"
                            context += "\n"

                if use_risk:
                    accounts_df = get_accounts_df()
                    if not accounts_df.empty:
                        acc = accounts_df[accounts_df['id'] == aid]
                        if not acc.empty:
                            daily_limit = float(acc.iloc[0]['daily_loss_limit'])
                            max_limit = float(acc.iloc[0]['max_loss_limit'])
                            trades_df = get_sheet_data("trades")
                            total_pnl = 0.0
                            if not trades_df.empty:
                                t = trades_df[trades_df['account_id'] == aid]
                                if not t.empty:
                                    t['profit'] = pd.to_numeric(t['profit'], errors='coerce').fillna(0)
                                    total_pnl = t['profit'].sum()
                            context += f"⚠️ 風險數據：每日虧損上限 ${daily_limit}，總虧損上限 ${max_limit}，目前累計盈虧 ${total_pnl:,.2f}\n"

                if not context:
                    st.warning("沒有資料可以分析")
                    st.stop()

                prompt = f"""你是一位經驗豐富的交易心理教練，專精於期貨與 prop firm 考核。
以下是交易員最近的紀錄，請根據這些資料分析他的心理模式、常見偏誤，並提供具體改善建議。
請用親切、鼓勵的語氣，以繁體中文回覆。

=== 交易員紀錄開始 ===
{context}
=== 交易員紀錄結束 ===

請從以下面向分析：
1. 情緒模式與認知偏誤
2. 進出場與資金管理的一致性
3. 具體可執行的改善行動
最後給予一個總結。"""

                try:
                    resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7, max_tokens=1500)
                    st.markdown("### 教練的建議")
                    st.write(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"API 錯誤：{e}")
