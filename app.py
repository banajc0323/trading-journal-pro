import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import openai

st.set_page_config(page_title="Trading Journal Pro", page_icon="📓")
DB_FILE = "journal_pro.db"

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
        return True, "Account created!"
    except sqlite3.IntegrityError:
        return False, "Name already exists"
    finally:
        conn.close()

def delete_account(account_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn.execute("DELETE FROM notes WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM trades WHERE account_id=?", (account_id,))
    conn.commit()
    conn.close()

# --- 側邊欄選單 ---
st.sidebar.title("📓 Trading Journal Pro")
menu = st.sidebar.radio("Menu", ["🏠 Accounts", "✍️ New Entry", "📋 History", "📥 Import CSV", "🧠 AI Coach"])

# --- 顯示目前帳號 ---
if st.session_state.current_account_name:
    st.sidebar.success(f"Account: {st.session_state.current_account_name}")
else:
    st.sidebar.warning("No account selected")

# ==================== Accounts Page ====================
if menu == "🏠 Accounts":
    st.title("🏠 Account Management")
    accounts_df = get_accounts()
    
    with st.expander("➕ Create New Account"):
        new_name = st.text_input("Account Name (e.g., T-12345)")
        if st.button("Create"):
            if not new_name.strip():
                st.warning("Please enter a name")
            else:
                ok, msg = create_account(new_name.strip())
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    
    st.subheader("My Accounts")
    if accounts_df.empty:
        st.info("No accounts yet. Create one above.")
    else:
        for _, row in accounts_df.iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.write(f"**{row['name']}** (Created: {row['created_at']})")
            with c2:
                if st.button("Select", key=f"sel_{row['id']}"):
                    st.session_state.current_account_id = row['id']
                    st.session_state.current_account_name = row['name']
                    st.rerun()
            with c3:
                if st.button("Delete", key=f"del_{row['id']}"):
                    delete_account(row['id'])
                    if st.session_state.current_account_id == row['id']:
                        st.session_state.current_account_id = None
                        st.session_state.current_account_name = None
                    st.rerun()

# ==================== New Entry Page ====================
elif menu == "✍️ New Entry":
    st.title("✍️ New Journal Entry")
    if not st.session_state.current_account_id:
        st.warning("Please select an account in Accounts page first")
    else:
        with st.form("note_form"):
            c1, c2 = st.columns(2)
            with c1:
                symbol = st.selectbox("Symbol", SYMBOLS, help="Start typing to search")
                phase = st.selectbox("Phase", ["Entry", "Add", "Reduce", "Trailing Stop", "Exit"])
                entry_datetime = st.text_input("Date & Time (YYYY-MM-DD HH:MM)", value=datetime.now().strftime("%Y-%m-%d %H:%M"))
            with c2:
                action_detail = st.text_input("Action Detail (optional)", placeholder="e.g., Added 1 lot")
                reason = st.text_area("Reason / Thought Process *", placeholder="Why did you take this action?")
                mood = st.text_input("Mood", placeholder="e.g., Greedy, Fearful, Calm")
            if st.form_submit_button("Save Entry"):
                if not reason.strip():
                    st.warning("Reason is required")
                else:
                    try:
                        datetime.strptime(entry_datetime, "%Y-%m-%d %H:%M")
                    except ValueError:
                        st.error("Invalid format. Use YYYY-MM-DD HH:MM")
                        st.stop()
                    conn = sqlite3.connect(DB_FILE)
                    conn.execute("INSERT INTO notes (account_id, symbol, phase, action_detail, reason, mood, entry_date) VALUES (?,?,?,?,?,?,?)",
                                 (st.session_state.current_account_id, symbol, phase, action_detail.strip(), reason.strip(), mood.strip(), entry_datetime))
                    conn.commit()
                    conn.close()
                    st.success("Entry saved!")

# ==================== History Page ====================
elif menu == "📋 History":
    st.title("📋 Journal History")
    if not st.session_state.current_account_id:
        st.warning("Please select an account first")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            filter_symbol = st.selectbox("Symbol", ["All"] + SYMBOLS)
        with c2:
            filter_phase = st.selectbox("Phase", ["All", "Entry", "Add", "Reduce", "Trailing Stop", "Exit"])
        with c3:
            sort_order = st.selectbox("Sort", ["Newest First", "Oldest First"])
        
        conn = sqlite3.connect(DB_FILE)
        query = "SELECT id, symbol, phase, action_detail, reason, mood, entry_date FROM notes WHERE account_id = ?"
        params = [st.session_state.current_account_id]
        if filter_symbol != "All":
            query += " AND symbol = ?"
            params.append(filter_symbol)
        if filter_phase != "All":
            query += " AND phase = ?"
            params.append(filter_phase)
        order = "DESC" if sort_order == "Newest First" else "ASC"
        query += f" ORDER BY entry_date {order}, id {order}"
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            st.info("No entries yet")
        else:
            df.columns = ["ID", "Symbol", "Phase", "Detail", "Reason", "Mood", "Time"]
            st.dataframe(df, use_container_width=True)

# ==================== Import CSV Page ====================
elif menu == "📥 Import CSV":
    st.title("📥 Import Topstep CSV")
    if not st.session_state.current_account_id:
        st.warning("Please select an account first")
    else:
        st.markdown("Upload Topstep CSV. Required columns: `Date`, `Symbol`, `Side`, `Quantity`, `Price`, `Profit`")
        uploaded_file = st.file_uploader("Choose CSV", type=["csv"])
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                required = {"Date", "Symbol", "Side", "Quantity", "Price", "Profit"}
                if not required.issubset(set(df.columns)):
                    st.error(f"Missing columns: {required - set(df.columns)}")
                    st.stop()
                df = df[list(required)]
                st.write("Preview:")
                st.dataframe(df.head())
                if st.button("Confirm Import"):
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
                    st.success(f"Imported {len(df)} trades!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        conn = sqlite3.connect(DB_FILE)
        cnt = pd.read_sql_query("SELECT COUNT(*) as c FROM trades WHERE account_id=?", conn, params=(st.session_state.current_account_id,)).iloc[0,0]
        conn.close()
        st.caption(f"This account has {cnt} CSV records")

# ==================== AI Coach Page ====================
elif menu == "🧠 AI Coach":
    st.title("🧠 AI Trading Coach")
    if not st.session_state.current_account_id:
        st.warning("Please select an account first")
    else:
        try:
            openai_key = st.secrets["OPENAI_API_KEY"]
        except KeyError:
            openai_key = st.text_input("OpenAI API Key", type="password")
            if not openai_key:
                st.info("Enter your key above or set in Streamlit Secrets")
                st.stop()
        openai.api_key = openai_key
        
        use_notes = st.checkbox("Include Journal Entries", value=True)
        use_trades = st.checkbox("Include CSV Trades", value=True)
        num = st.slider("Items to analyze", 3, 30, 10)
        
        if st.button("Get Coach Feedback"):
            with st.spinner("Analyzing..."):
                context = ""
                conn = sqlite3.connect(DB_FILE)
                aid = st.session_state.current_account_id
                
                if use_notes:
                    ndf = pd.read_sql_query("SELECT entry_date, symbol, phase, action_detail, reason, mood FROM notes WHERE account_id=? ORDER BY entry_date DESC LIMIT ?", conn, params=(aid, num))
                    if not ndf.empty:
                        context += "📝 Journal:\n"
                        for _, r in ndf.iterrows():
                            context += f"- {r['entry_date']} | {r['symbol']} | {r['phase']} | {r.get('action_detail','')} | Mood: {r['mood']} | Reason: {r['reason']}\n"
                        context += "\n"
                
                if use_trades:
                    tdf = pd.read_sql_query("SELECT trade_time, symbol, side, quantity, price, profit FROM trades WHERE account_id=? ORDER BY trade_time DESC LIMIT ?", conn, params=(aid, num))
                    if not tdf.empty:
                        context += "📈 Trades:\n"
                        for _, r in tdf.iterrows():
                            context += f"- {r['trade_time']} | {r['symbol']} | {r['side']} {r['quantity']} @{r['price']} | P&L: {r['profit']}\n"
                conn.close()
                
                if not context:
                    st.warning("No data to analyze")
                    st.stop()
                
                prompt = f"""You are an experienced trading psychology coach.
Analyze the following trader records and give actionable feedback on emotions, biases, and consistency.

Records:
{context}
Please provide analysis and specific improvement suggestions."""
                
                try:
                    resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], temperature=0.7)
                    st.markdown("### Coach Feedback")
                    st.write(resp.choices[0].message.content)
                except Exception as e:
                    st.error(f"API Error: {e}")
