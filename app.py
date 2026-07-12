import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import numpy as np
from datetime import datetime, date
import openai
import os
import cloudinary
import cloudinary.uploader

st.set_page_config(page_title="交易策略實驗室 Pro", page_icon="📓")

# ---- Cloudinary 設定 ----
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=os.environ.get("CLOUDINARY_API_KEY", ""),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET", "")
)

# ---- OpenAI Key ----
openai.api_key = os.environ.get("OPENAI_API_KEY", "")

# ---- 資料庫連線（Supabase PostgreSQL）----
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    st.error("請設定 DATABASE_URL 環境變數")
    st.stop()

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# ---- 商品清單 ----
SYMBOLS = [
    "MGC", "MES", "MNQ", "MYM", "M2K",
    "ES", "NQ", "YM", "RTY",
    "GC", "SI", "CL", "NG", "ZB", "ZN", "ZF",
    "6E", "6J", "6B", "6A", "6C", "6S",
    "HE", "LE", "ZC", "ZW", "ZS", "CC", "KC", "CT", "SB", "OJ"
]

DEFAULT_TICK_VALUES = {
    "MGC": 10, "MES": 5, "MNQ": 2, "MYM": 0.5, "M2K": 0.5,
    "ES": 50, "NQ": 20, "YM": 5, "RTY": 5,
    "GC": 100, "SI": 5000, "CL": 1000, "NG": 10000, "ZB": 1000, "ZN": 1000, "ZF": 1000,
    "6E": 125000, "6J": 12500000, "6B": 62500, "6A": 100000, "6C": 100000, "6S": 125000,
    "HE": 400, "LE": 400, "ZC": 50, "ZW": 50, "ZS": 50,
    "CC": 10, "KC": 375, "CT": 500, "SB": 1120, "OJ": 150
}

# ---- 初始化資料表（PostgreSQL 語法）----
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            daily_loss_limit REAL DEFAULT 1000,
            max_loss_limit REAL DEFAULT 2000,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS symbol_config (
            symbol TEXT PRIMARY KEY,
            tick_value REAL NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            strategy_id INTEGER REFERENCES strategies(id),
            symbol TEXT NOT NULL,
            phase TEXT NOT NULL,
            action_detail TEXT DEFAULT '',
            reason TEXT,
            mood TEXT,
            is_disciplined INTEGER DEFAULT 1,
            image_url TEXT DEFAULT '',
            entry_date TIMESTAMP NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id SERIAL PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES accounts(id),
            trade_time TIMESTAMP NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT,
            quantity REAL,
            price REAL,
            profit REAL
        )
    """)
    # 插入預設策略（若不存在）
    cur.execute("INSERT INTO strategies (name) VALUES ('無特定策略') ON CONFLICT (name) DO NOTHING")
    cur.execute("INSERT INTO strategies (name) VALUES ('策略A') ON CONFLICT (name) DO NOTHING")
    cur.execute("INSERT INTO strategies (name) VALUES ('策略B') ON CONFLICT (name) DO NOTHING")
    # 插入預設點值
    for sym, val in DEFAULT_TICK_VALUES.items():
        cur.execute("INSERT INTO symbol_config (symbol, tick_value) VALUES (%s, %s) ON CONFLICT (symbol) DO NOTHING", (sym, val))
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ---- Session State ----
if "current_account_id" not in st.session_state:
    st.session_state.current_account_id = None
if "current_account_name" not in st.session_state:
    st.session_state.current_account_name = None

# ---- 輔助函式（使用 psycopg2）----
def get_accounts():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, name, daily_loss_limit, max_loss_limit, created_at FROM accounts ORDER BY id", conn)
    conn.close()
    return df

def create_account(name, daily_loss=1000, max_loss=2000):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO accounts (name, daily_loss_limit, max_loss_limit) VALUES (%s, %s, %s)",
                     (name, daily_loss, max_loss))
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
    cur.execute("DELETE FROM notes WHERE account_id = %s", (account_id,))
    cur.execute("DELETE FROM trades WHERE account_id = %s", (account_id,))
    cur.execute("DELETE FROM accounts WHERE id = %s", (account_id,))
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
    cur.execute("INSERT INTO symbol_config (symbol, tick_value) VALUES (%s, %s) ON CONFLICT (symbol) DO UPDATE SET tick_value = %s",
                (symbol, value, value))
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

# ---- 側邊欄選單 ----
st.sidebar.title("📓 交易策略實驗室 Pro")
menu = st.sidebar.radio("選單", [
    "🏠 帳號管理",
    "🏷️ 策略管理",
    "✍️ 新增筆記",
    "📋 歷史紀錄",
    "📥 匯入CSV",
    "📊 績效分析",
    "🎯 停損停利建議",
    "📉 風險監控",
    "🧠 AI教練"
])
if st.session_state.current_account_name:
    st.sidebar.success(f"目前帳號：{st.session_state.current_account_name}")
else:
    st.sidebar.warning("尚未選擇帳號")

# ==================== 帳號管理 ====================
if menu == "🏠 帳號管理":
    st.title("🏠 帳號管理")
    accounts_df = get_accounts()
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
            c1.write(f"**{row['name']}** (日虧 ${row['daily_loss_limit']}, 總虧 ${row['max_loss_limit']})")
            if c2.button("選取", key=f"sel_{row['id']}"):
                st.session_state.current_account_id = row['id']
                st.session_state.current_account_name = row['name']
                st.rerun()
            if c3.button("刪除", key=f"del_{row['id']}"):
                delete_account(row['id'])
                st.session_state.current_account_id = None
                st.session_state.current_account_name = None
                st.rerun()

# ==================== 策略管理 ====================
elif menu == "🏷️ 策略管理":
    st.title("🏷️ 策略管理")
    st.dataframe(get_strategies().rename(columns={"id":"ID","name":"策略名稱"}), use_container_width=True)
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
        strategies_df = get_strategies()
        with st.form("note_form"):
            c1, c2 = st.columns(2)
            symbol = c1.selectbox("商品代碼", SYMBOLS)
            phase = c1.selectbox("交易階段", ["進場", "加碼", "減碼", "移動停利/停損", "出場"])
            strategy_id = c1.selectbox("策略", strategies_df['id'].tolist(),
                                       format_func=lambda x: strategies_df[strategies_df['id']==x]['name'].values[0])
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
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO notes (account_id, strategy_id, symbol, phase, action_detail, reason, mood, is_disciplined, image_url, entry_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (st.session_state.current_account_id, int(strategy_id), symbol, phase,
                         action_detail.strip(), reason.strip(), mood.strip(), 1 if is_disciplined else 0,
                         image_url, entry_datetime))
                    conn.commit()
                    cur.close()
                    conn.close()
                    st.success("筆記已儲存！")

# ==================== 歷史紀錄 ====================
elif menu == "📋 歷史紀錄":
    st.title("📋 歷史紀錄")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        c1, c2, c3, c4 = st.columns(4)
        filter_symbol = c1.selectbox("商品", ["全部"]+SYMBOLS)
        filter_phase = c2.selectbox("階段", ["全部","進場","加碼","減碼","移動停利/停損","出場"])
        strategies = get_strategies()
        filter_strategy = c3.selectbox("策略", ["全部"]+strategies['name'].tolist())
        filter_disc = c4.selectbox("紀律", ["全部","有紀律","無紀律"])
        sort_order = st.radio("排序", ["最新在前","最舊在前"], horizontal=True)

        conn = get_db_connection()
        query = """
            SELECT n.id, n.symbol, n.phase, s.name, n.action_detail, n.reason, n.mood,
                   CASE WHEN n.is_disciplined=1 THEN '是' ELSE '否' END, n.entry_date::text, n.image_url
            FROM notes n LEFT JOIN strategies s ON n.strategy_id = s.id
            WHERE n.account_id = %s
        """
        params = [st.session_state.current_account_id]
        if filter_symbol != "全部":
            query += " AND n.symbol = %s"
            params.append(filter_symbol)
        if filter_phase != "全部":
            query += " AND n.phase = %s"
            params.append(filter_phase)
        if filter_strategy != "全部":
            query += " AND s.name = %s"
            params.append(filter_strategy)
        if filter_disc == "有紀律":
            query += " AND n.is_disciplined = 1"
        elif filter_disc == "無紀律":
            query += " AND n.is_disciplined = 0"
        query += " ORDER BY n.entry_date " + ("DESC" if sort_order=="最新在前" else "ASC")
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        if df.empty:
            st.info("尚無紀錄")
        else:
            for _, row in df.iterrows():
                cols = st.columns([1,1,1,1,1,2,1,1,1])
                cols[0].write(row[1])
                cols[1].write(row[2])
                cols[2].write(row[3])
                cols[3].write(row[7])
                cols[4].write(row[6])
                cols[5].write(str(row[5])[:40])
                cols[6].write(row[8])
                if row[9]:
                    cols[7].image(row[9], width=60)
                else:
                    cols[7].write("無")
                st.markdown("---")

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
                        conn = get_db_connection()
                        cur = conn.cursor()
                        for _, row in df.iterrows():
                            try:
                                t = pd.to_datetime(row['Date']).strftime("%Y-%m-%d %H:%M")
                            except:
                                t = str(row['Date'])
                            cur.execute("INSERT INTO trades (account_id, trade_time, symbol, side, quantity, price, profit) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                        (st.session_state.current_account_id, t, str(row['Symbol']).upper(),
                                         str(row['Side']), float(row['Quantity']), float(row['Price']), float(row['Profit'])))
                        conn.commit()
                        cur.close()
                        conn.close()
                        st.success(f"匯入 {len(df)} 筆")
                        st.rerun()
            except Exception as e:
                st.error(f"錯誤：{e}")
        conn = get_db_connection()
        cnt = pd.read_sql_query("SELECT COUNT(*) as c FROM trades WHERE account_id=%s", conn, params=(st.session_state.current_account_id,)).iloc[0,0]
        conn.close()
        st.caption(f"此帳號有 {cnt} 筆 CSV 紀錄")

# ==================== 績效分析 ====================
elif menu == "📊 績效分析":
    st.title("📊 績效分析")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        mode = st.radio("模式", ["目前帳號策略分析", "跨帳號比較"], horizontal=True)
        conn = get_db_connection()
        if mode == "目前帳號策略分析":
            df1 = pd.read_sql_query("""
                SELECT s.name, COUNT(*) as cnt, ROUND(AVG(n.is_disciplined)*100,1) as rate
                FROM notes n JOIN strategies s ON n.strategy_id = s.id
                WHERE n.account_id = %s GROUP BY s.name
            """, conn, params=(st.session_state.current_account_id,))
            st.dataframe(df1)
            trades = pd.read_sql_query("SELECT * FROM trades WHERE account_id=%s", conn, params=(st.session_state.current_account_id,))
            if not trades.empty:
                wins = trades[trades['profit']>0]
                st.metric("總交易次數", len(trades))
                st.metric("勝率", f"{len(wins)/len(trades)*100:.1f}%")
                st.metric("總盈虧", f"${trades['profit'].sum():,.2f}")
        else:
            all_acc = get_accounts()
            selected = st.multiselect("選擇帳號", all_acc['id'].tolist(), format_func=lambda x: all_acc[all_acc['id']==x]['name'].values[0])
            for aid in selected:
                name = all_acc[all_acc['id']==aid]['name'].values[0]
                trades = pd.read_sql_query("SELECT * FROM trades WHERE account_id=%s", conn, params=(aid,))
                if not trades.empty:
                    st.write(f"**{name}**：{len(trades)}筆，勝率{len(trades[trades['profit']>0])/len(trades)*100:.1f}%，總盈虧 ${trades['profit'].sum():,.2f}")
                else:
                    st.write(f"**{name}**：無資料")
        conn.close()

# ==================== 停損停利建議 ====================
elif menu == "🎯 停損停利建議":
    st.title("🎯 停損停利建議")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        with st.expander("⚙️ 商品每點價值"):
            tv_df = get_tick_values()
            edited = st.data_editor(tv_df, num_rows="dynamic")
            if st.button("儲存設定"):
                for _, r in edited.iterrows():
                    update_tick_value(r['symbol'], r['tick_value'])
                st.success("已更新")
                st.rerun()
        conn = get_db_connection()
        trades = pd.read_sql_query("SELECT * FROM trades WHERE account_id=%s ORDER BY trade_time", conn, params=(st.session_state.current_account_id,))
        conn.close()
        if not trades.empty:
            tv = get_tick_values()
            trades = trades.merge(tv, on='symbol', how='left')
            def exit_price(row):
                if row['quantity'] and row['tick_value']:
                    if row['side'].upper() == 'BUY':
                        return row['price'] + row['profit'] / (row['quantity']*row['tick_value'])
                    else:
                        return row['price'] - row['profit'] / (row['quantity']*row['tick_value'])
                return np.nan
            trades['exit_price'] = trades.apply(exit_price, axis=1)
            trades['points'] = np.abs(trades['exit_price'] - trades['price'])
            for sym in trades['symbol'].unique():
                sub = trades[trades['symbol']==sym].dropna(subset=['points'])
                if sub.empty: continue
                avg_loss = sub[sub['profit']<0]['points'].mean() or 0
                max_loss = sub[sub['profit']<0]['points'].max() or 0
                avg_win = sub[sub['profit']>0]['points'].mean() or 0
                st.write(f"**{sym}**")
                c1,c2,c3 = st.columns(3)
                c1.metric("平均虧損", f"{avg_loss:.2f}點")
                c2.metric("最大虧損", f"{max_loss:.2f}點")
                c3.metric("建議停損", f"{max(avg_loss*1.5, 2):.1f}點")
                c1.metric("平均獲利", f"{avg_win:.2f}點")
                c2.metric("建議停利", f"{avg_win*1.2:.1f}點" if avg_win>0 else "不足")
        else:
            st.info("尚無歷史數據，可使用下方 AI 通用建議")

        st.markdown("---")
        st.subheader("🧠 AI 通用建議（無需歷史紀錄）")
        ai_sym = st.selectbox("選擇商品", SYMBOLS, key="ai_sym")
        ai_desc = st.text_area("策略簡述（選填）", key="ai_desc")
        if st.button("生成 AI 建議"):
            if not openai.api_key:
                st.warning("請先設定 OpenAI API Key")
            else:
                tv = get_tick_values()
                tick_val = tv[tv['symbol']==ai_sym]['tick_value'].values[0] if ai_sym in tv['symbol'].values else "未知"
                prompt = f"""你是一位專業期貨交易教練。交易員想交易 {ai_sym}（每點價值約 {tick_val} 美元）。
{ '他的策略：' + ai_desc if ai_desc else '未提供策略細節。' }
請提供：
1. 建議的初始停損點數及原因
2. 建議的初始停利點數（或分批出場方式）及原因
3. 該商品需注意的風險控管重點
4. 策略優化建議（繁體中文，條列式，語氣親切）"""
                with st.spinner("AI 思考中..."):
                    resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7)
                    st.write(resp.choices[0].message.content)

# ==================== 風險監控 ====================
elif menu == "📉 風險監控":
    st.title("📉 風險監控")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        conn = get_db_connection()
        acc = pd.read_sql_query("SELECT daily_loss_limit, max_loss_limit FROM accounts WHERE id=%s", conn, params=(st.session_state.current_account_id,)).iloc[0]
        today_pnl = pd.read_sql_query("SELECT SUM(profit) FROM trades WHERE account_id=%s AND trade_time::date = CURRENT_DATE", conn, params=(st.session_state.current_account_id,)).iloc[0,0] or 0
        total_pnl = pd.read_sql_query("SELECT SUM(profit) FROM trades WHERE account_id=%s", conn, params=(st.session_state.current_account_id,)).iloc[0,0] or 0
        trades_df = pd.read_sql_query("SELECT trade_time, profit FROM trades WHERE account_id=%s ORDER BY trade_time", conn, params=(st.session_state.current_account_id,))
        conn.close()
        max_dd = 0
        if not trades_df.empty:
            trades_df['cum'] = trades_df['profit'].cumsum()
            max_dd = (trades_df['cum'] - trades_df['cum'].cummax()).min()
        def light(val, limit):
            if val <= -limit: return "🔴 超過上限"
            elif val <= -limit*0.7: return "🟡 接近上限"
            return "🟢 安全"
        c1, c2 = st.columns(2)
        c1.metric("今日盈虧", f"${today_pnl:,.2f}")
        c1.caption(light(today_pnl, acc['daily_loss_limit']))
        c2.metric("累計盈虧", f"${total_pnl:,.2f}")
        c2.caption(light(total_pnl, acc['max_loss_limit']))
        st.metric("最大回撤", f"${max_dd:,.2f}")

# ==================== AI 教練（支援截圖） ====================
elif menu == "🧠 AI教練":
    st.title("🧠 AI 教練 (策略+截圖+風險)")
    if not st.session_state.current_account_id:
        st.warning("請先選擇帳號")
    else:
        if not openai.api_key:
            openai.api_key = st.text_input("OpenAI API Key", type="password")
            if not openai.api_key:
                st.stop()
        use_notes = st.checkbox("包含筆記", True)
        use_trades = st.checkbox("包含 CSV", True)
        use_images = st.checkbox("包含截圖", True)
        use_risk = st.checkbox("包含風險數據", True)
        num = st.slider("分析筆數", 3, 30, 10)

        if st.button("請求教練分析"):
            with st.spinner("分析中..."):
                context = ""
                image_urls = []
                conn = get_db_connection()
                aid = st.session_state.current_account_id
                acc = pd.read_sql_query("SELECT * FROM accounts WHERE id=%s", conn, params=(aid,)).iloc[0]
                today_pnl = pd.read_sql_query("SELECT SUM(profit) FROM trades WHERE account_id=%s AND trade_time::date = CURRENT_DATE", conn, params=(aid,)).iloc[0,0] or 0
                total_pnl = pd.read_sql_query("SELECT SUM(profit) FROM trades WHERE account_id=%s", conn, params=(aid,)).iloc[0,0] or 0

                if use_notes or use_images:
                    ndf = pd.read_sql_query("""
                        SELECT n.*, s.name as strategy_name FROM notes n LEFT JOIN strategies s ON n.strategy_id=s.id
                        WHERE n.account_id=%s ORDER BY n.entry_date DESC LIMIT %s
                    """, conn, params=(aid, num))
                    if use_notes and not ndf.empty:
                        context += "📝 筆記：\n"
                        for _, r in ndf.iterrows():
                            context += f"- {r['entry_date']} {r['symbol']} {r['phase']} 策略:{r['strategy_name']} 紀律:{'是' if r['is_disciplined'] else '否'} 心情:{r['mood']} 理由:{r['reason']}\n"
                    if use_images and not ndf.empty:
                        for _, r in ndf.iterrows():
                            if r['image_url']:
                                image_urls.append(r['image_url'])
                if use_trades:
                    tdf = pd.read_sql_query("SELECT * FROM trades WHERE account_id=%s ORDER BY trade_time DESC LIMIT %s", conn, params=(aid, num))
                    if not tdf.empty:
                        context += "📈 CSV：\n"
                        for _, r in tdf.iterrows():
                            context += f"- {r['trade_time']} {r['symbol']} {r['side']} {r['quantity']}口 @{r['price']} 盈虧:{r['profit']}\n"
                conn.close()

                risk_str = ""
                if use_risk:
                    risk_str = f"\n⚠️ 風險：今日盈虧 ${today_pnl:,.2f} (上限{acc['daily_loss_limit']})，累計盈虧 ${total_pnl:,.2f} (上限{acc['max_loss_limit']})\n"

                prompt = f"""你是專業交易教練，根據以下紀錄給出具體優化建議（繁體中文）。
{context}{risk_str}
請分析策略一致性、紀律、風險，並針對截圖中的進出場點位提出改善建議。"""
                messages = [{"role":"user","content":[{"type":"text","text":prompt}]}]
                for url in image_urls[:5]:
                    messages[0]["content"].append({"type":"image_url","image_url":{"url":url}})

                resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=messages, temperature=0.7, max_tokens=1500)
                st.markdown("### 教練建議")
                st.write(resp.choices[0].message.content)
