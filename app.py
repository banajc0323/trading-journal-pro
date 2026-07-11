import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import openai
import os

st.set_page_config(page_title="交易心態日誌 Pro", page_icon="📓")

DB_FILE = os.path.join("/tmp", "journal_pro.db")

SYMBOLS = [
    "MGC", "MES", "MNQ", "MYM", "M2K",
    "ES", "NQ", "YM", "RTY",
    "GC", "SI", "CL", "NG", "ZB", "ZN", "ZF",
    "6E", "6J", "6B", "6A", "6C", "6S",
    "HE", "LE", "ZC", "ZW", "ZS", "CC", "KC", "CT", "SB", "OJ"
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, created_at TEXT DEFAULT (datetime('now')))''')
    c.execute('''CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, symbol TEXT NOT NULL, phase TEXT NOT NULL, action_detail TEXT DEFAULT '', reason TEXT, mood TEXT, entry_date TEXT NOT NULL, FOREIGN KEY (account_id) REFERENCES accounts(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER NOT NULL, trade_time TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT, quantity REAL, price REAL, profit REAL, FOREIGN KEY (account_id) REFERENCES accounts(id))''')
    conn.commit()
    conn.close()

init_db()

if "current_account_id" not in st.session_state:
    st.session_state.current_account_id = None
if "current_account_name" not in st.session_state:
    st.session_state.current_account_name = None

def get_accounts():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, name, created_at FROM accounts ORDER BY id", conn)
    conn.close()
    return df

def create_account(name):
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("INSERT INTO accounts (name) VALUES (?)", (name,))
        conn.commit()
        return True, "帳號建立成功！"
    except sqlite3.IntegrityError:
        return False, "帳號名稱已存在"
    finally:
        conn.close()

def delete_account(account_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn.execute("DELETE FROM notes WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM trades WHERE account_id=?", (account_id,))
    conn.commit()
    conn.close()

st.sidebar.title("📓 交易心態日誌 Pro")
menu = st.sidebar.radio("選單", ["🏠 帳號管理", "✍️ 新增筆記", "📋 歷史紀錄", "📥 匯入CSV", "🧠 AI教練"])

if st.session_state.current_account_name:
    st.sidebar.success(f"目前帳號：{st.session_state.current_account_name}")
else:
    st.sidebar.warning("尚未選擇帳號")

# ==================== 帳號管理 ====================
if menu == "🏠 帳號管理":
    st.title("🏠 帳號管理")
    accounts_df = get_accounts()
    with st.expander("➕ 建立新帳號"):
        new_name = st.text_input("帳號名稱（例如：T-12345）")
        if st.button("建立"):
            if not new_name.strip():
                st.warning("請輸入帳號名稱")
            else:
                ok, msg = create_account(new_name.strip())
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    st.subheader("我的帳號")
    if accounts_df.empty:
        st.info("尚未建立任何帳號，請在上方建立")
    else:
        for _, row in accounts_df.iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.write(f"**{row['name']}**（建立於：{row['created_at']}）")
            with c2:
                if st.button("選取", key=f"sel_{row['id']}"):
                    st.session_state.current_account_id = row['id']
                    st.session_state.current_account_name = row['name']
                    st.rerun()
            with c3:
                if st.button("刪除", key=f"del_{row['id']}"):
                    delete_account(row['id'])
                    if st.session_state.current_account_id == row['id']:
                        st.session_state.current_account_id = None
                        st.session_state.current_account_name = None
                    st.rerun()

# ==================== 新增筆記 ====================
elif menu == "✍️ 新增筆記":
    st.title("✍️ 新增交易筆記")
    if not st.session_state.current_account_id:
        st.warning("請先在「帳號管理」中選擇一個帳號")
    else:
        with st.form("note_form"):
            c1, c2 = st.columns(2)
            with c1:
                symbol = st.selectbox("商品代碼", SYMBOLS, help="直接打字即可搜尋，例如輸入 M")
                phase = st.selectbox("交易階段", ["進場", "加碼", "減碼", "移動停利/停損", "出場"])
                entry_datetime = st.text_input("日期時間（YYYY-MM-DD HH:MM）", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
            with c2:
                action_detail = st.text_input("動作細節（選填）", placeholder="例如：加碼 1 口，移動停損到 1850")
                reason = st.text_area("理由 / 想法 *", placeholder="為什麼做這個動作？看到什麼訊號？")
                mood = st.text_input("心情", placeholder="例如：貪心、害怕、冷靜、緊張")
            if st.form_submit_button("儲存筆記"):
                if not reason.strip():
                    st.warning("理由為必填欄位")
                else:
                    try:
                        datetime.strptime(entry_datetime, "%Y-%m-%d %H:%M")
                    except ValueError:
                        st.error("日期格式錯誤，請使用 YYYY-MM-DD HH:MM")
                        st.stop()
                    conn = sqlite3.connect(DB_FILE)
                    conn.execute("INSERT INTO notes (account_id, symbol, phase, action_detail, reason, mood, entry_date) VALUES (?,?,?,?,?,?,?)",
                                 (st.session_state.current_account_id, symbol, phase, action_detail.strip(), reason.strip(), mood.strip(), entry_datetime))
                    conn.commit()
                    conn.close()
                    st.success("筆記已儲存！")

# ==================== 歷史紀錄 ====================
elif menu == "📋 歷史紀錄":
    st.title("📋 歷史紀錄")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            filter_symbol = st.selectbox("商品", ["全部"] + SYMBOLS)
        with c2:
            filter_phase = st.selectbox("階段", ["全部", "進場", "加碼", "減碼", "移動停利/停損", "出場"])
        with c3:
            sort_order = st.selectbox("排序", ["最新在前", "最舊在前"])
        conn = sqlite3.connect(DB_FILE)
        query = "SELECT id, symbol, phase, action_detail, reason, mood, entry_date FROM notes WHERE account_id = ?"
        params = [st.session_state.current_account_id]
        if filter_symbol != "全部":
            query += " AND symbol = ?"
            params.append(filter_symbol)
        if filter_phase != "全部":
            query += " AND phase = ?"
            params.append(filter_phase)
        order = "DESC" if sort_order == "最新在前" else "ASC"
        query += f" ORDER BY entry_date {order}, id {order}"
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        if df.empty:
            st.info("尚無任何紀錄")
        else:
            df.columns = ["ID", "商品", "階段", "細節", "理由", "心情", "時間"]
            st.dataframe(df, use_container_width=True)

# ==================== 匯入CSV ====================
elif menu == "📥 匯入CSV":
    st.title("📥 匯入 Topstep CSV")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        st.markdown("上傳 Topstep 的每日交易 CSV 檔，需包含以下欄位：`Date`、`Symbol`、`Side`、`Quantity`、`Price`、`Profit`")
        uploaded_file = st.file_uploader("選擇 CSV 檔案", type=["csv"])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                required = {"Date", "Symbol", "Side", "Quantity", "Price", "Profit"}
                if not required.issubset(set(df.columns)):
                    st.error(f"缺少必要欄位：{required - set(df.columns)}")
                    st.stop()
                df = df[list(required)]
                st.write("預覽前 5 筆：")
                st.dataframe(df.head())
                if st.button("確認匯入"):
                    conn = sqlite3.connect(DB_FILE)
                    for _, row in df.iterrows():
                        try:
                            t = pd.to_datetime(row['Date']).strftime("%Y-%m-%d %H:%M")
                        except:
                            t = str(row['Date'])
                        conn.execute("INSERT INTO trades (account_id, trade_time, symbol, side, quantity, price, profit) VALUES (?,?,?,?,?,?,?)",
                                     (st.session_state.current_account_id, t, str(row['Symbol']).upper(), str(row['Side']), float(row['Quantity']), float(row['Price']), float(row['Profit'])))
                    conn.commit()
                    conn.close()
                    st.success(f"成功匯入 {len(df)} 筆交易紀錄！")
                    st.rerun()
            except Exception as e:
                st.error(f"解析失敗：{e}")
        conn = sqlite3.connect(DB_FILE)
        cnt = pd.read_sql_query("SELECT COUNT(*) as c FROM trades WHERE account_id=?", conn, params=(st.session_state.current_account_id,)).iloc[0,0]
        conn.close()
        st.caption(f"此帳號目前有 {cnt} 筆 CSV 交易紀錄")

# ==================== AI教練 ====================
elif menu == "🧠 AI教練":
    st.title("🧠 AI 交易教練")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        try:
            openai_key = st.secrets["OPENAI_API_KEY"]
        except KeyError:
            openai_key = st.text_input("請輸入 OpenAI API Key", type="password")
            if not openai_key:
                st.info("請輸入金鑰，或在 Streamlit Secrets 中設定")
                st.stop()
        openai.api_key = openai_key
        use_notes = st.checkbox("包含交易筆記", value=True)
        use_trades = st.checkbox("包含 CSV 交易紀錄", value=True)
        num = st.slider("要分析最近幾筆？", 3, 30, 10)
        if st.button("請 AI 教練分析"):
            with st.spinner("教練正在分析你的資料..."):
                context = ""
                conn = sqlite3.connect(DB_FILE)
                aid = st.session_state.current_account_id
                if use_notes:
                    ndf = pd.read_sql_query("SELECT entry_date, symbol, phase, action_detail, reason, mood FROM notes WHERE account_id=? ORDER BY entry_date DESC LIMIT ?", conn, params=(aid, num))
                    if not ndf.empty:
                        context += "📝 交易筆記：\n"
                        for _, r in ndf.iterrows():
                            context += f"- {r['entry_date']} | {r['symbol']} | {r['phase']} | {r.get('action_detail','')} | 心情：{r['mood']} | 理由：{r['reason']}\n"
                        context += "\n"
                if use_trades:
                    tdf = pd.read_sql_query("SELECT trade_time, symbol, side, quantity, price, profit FROM trades WHERE account_id=? ORDER BY trade_time DESC LIMIT ?", conn, params=(aid, num))
                    if not tdf.empty:
                        context += "📈 CSV 交易紀錄：\n"
                        for _, r in tdf.iterrows():
                            context += f"- {r['trade_time']} | {r['symbol']} | {r['side']} {r['quantity']}口 @{r['price']} | 盈虧：{r['profit']}\n"
                conn.close()
                if not context:
                    st.warning("沒有資料可以分析")
                    st.stop()
                prompt = f"""你是一位經驗豐富的交易心理教練，專精於期貨與 prop firm 考核。
以下是交易員最近的紀錄（包含交易筆記與實際交易明細）。
請根據這些資料分析他的心理模式、常見偏誤，並提供具體改善建議。
請用親切、鼓勵的語氣，以繁體中文回覆。

=== 交易員紀錄開始 ===
{context}
=== 交易員紀錄結束 ===

請從以下面向分析：
1. 情緒模式與認知偏誤
2. 進出場與資金管理的一致性
3. 具體可執行的改善行動（如停損紀律、情緒調節方法）
最後給予一個總結。"""
                try:
                    resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7)
                    st.markdown("### 教練的建議")
                    st.write(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"API 錯誤：{e}")
