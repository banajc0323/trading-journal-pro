import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import openai

# ===================== Page Config =====================
st.set_page_config(page_title="Trading Journal Pro", page_icon="📓")

DB_FILE = "journal_pro.db"

# Symbols list (you can edit this anytime)
SYMBOLS = [
    "MGC", "MES", "MNQ", "MYM", "M2K",
    "ES", "NQ", "YM", "RTY",
    "GC", "SI", "CL", "NG", "ZB", "ZN", "ZF",
    "6E", "6J", "6B", "6A", "6C", "6S",
    "HE", "LE", "ZC", "ZW", "ZS", "CC", "KC", "CT", "SB", "OJ"
]

# ===================== Database Init =====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            phase TEXT NOT NULL,
            action_detail TEXT DEFAULT '',
            reason TEXT,
            mood TEXT,
            entry_date TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            trade_time TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT,
            quantity REAL,
            price REAL,
            profit REAL,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ===================== Session State =====================
if "current_account_id" not in st.session_state:
    st.session_state.current_account_id = None
if "current_account_name" not in st.session_state:
    st.session_state.current_account_name = None

# ===================== Helpers =====================
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
        return True, "Account created successfully"
    except sqlite3.IntegrityError:
        return False, "Account name already exists"
    finally:
        conn.close()

def delete_account(account_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn.execute("DELETE FROM notes WHERE account_id=?", (account_id,))
    conn.execute("DELETE FROM trades WHERE account_id=?", (account_id,))
    conn.commit()
    conn.close()

# ===================== Pages =====================
def account_page():
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
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{row['name']}**  (Created: {row['created_at']})")
            with col2:
                if st.button("Select", key=f"sel_{row['id']}"):
                    st.session_state.current_account_id = row['id']
                    st.session_state.current_account_name = row['name']
                    st.rerun()
            with col3:
                if st.button("Delete", key=f"del_{row['id']}"):
                    delete_account(row['id'])
                    if st.session_state.current_account_id == row['id']:
                        st.session_state.current_account_id = None
                        st.session_state.current_account_name = None
                    st.rerun()
        if st.session_state.current_account_name:
            st.success(f"Current account: **{st.session_state.current_account_name}**")

def note_page():
    st.title("✍️ New Journal Entry")
    if not st.session_state.current_account_id:
        st.warning("Please select an account in Account Management first")
        return

    with st.form("note_form"):
        col1, col2 = st.columns(2)
        with col1:
            symbol = st.selectbox("Symbol", SYMBOLS, help="Start typing to search (e.g., 'M')")
            phase = st.selectbox("Phase", ["Entry", "Add", "Reduce", "Trailing Stop", "Exit"])
            entry_datetime = st.text_input(
                "Date & Time (YYYY-MM-DD HH:MM)",
                value=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        with col2:
            action_detail = st.text_input("Action Detail (optional)", placeholder="e.g., Added 1 lot, moved stop to 1850")
            reason = st.text_area("Reason / Thought Process *", placeholder="Why did you take this action?")
            mood = st.text_input("Mood", placeholder="e.g., Greedy, Fearful, Calm, Nervous")

        submitted = st.form_submit_button("Save Entry")
        if submitted:
            if not reason.strip():
                st.warning("Reason is required")
            else:
                try:
                    datetime.strptime(entry_datetime, "%Y-%m-%d %H:%M")
                except ValueError:
                    st.error("Invalid date format. Use YYYY-MM-DD HH:MM")
                    st.stop()
                conn = sqlite3.connect(DB_FILE)
                conn.execute(
                    "INSERT INTO notes (account_id, symbol, phase, action_detail, reason, mood, entry_date) VALUES (?,?,?,?,?,?,?)",
                    (st.session_state.current_account_id, symbol, phase, action_detail.strip(),
                     reason.strip(), mood.strip(), entry_datetime)
                )
                conn.commit()
                conn.close()
                st.success("Entry saved!")

def history_page():
    st.title("📋 Journal History")
    if not st.session_state.current_account_id:
        st.warning("Please select an account first")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_symbol = st.selectbox("Symbol", ["All"] + SYMBOLS)
    with col2:
        filter_phase = st.selectbox("Phase", ["All", "Entry", "Add", "Reduce", "Trailing Stop", "Exit"])
    with col3:
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
        df.columns = ["ID", "Symbol", "Phase", "Action Detail", "Reason", "Mood", "Time"]
        st.dataframe(df, use_container_width=True, hide_index=True)

def import_csv_page():
    st.title("📥 Import Topstep CSV")
    if not st.session_state.current_account_id:
        st.warning("Please select an account first")
        return

    st.markdown("""
    Upload your Topstep daily trading CSV. Required columns:  
    `Date`, `Symbol`, `Side`, `Quantity`, `Price`, `Profit`
    """)

    uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            required_cols = {"Date", "Symbol", "Side", "Quantity", "Price", "Profit"}
            if not required_cols.issubset(set(df.columns)):
                missing = required_cols - set(df.columns)
                st.error(f"Missing required columns: {missing}")
                st.stop()
            df = df[list(required_cols)]
            st.write("Preview (first 5 rows):")
            st.dataframe(df.head())
            if st.button("Confirm Import"):
                conn = sqlite3.connect(DB_FILE)
                for _, row in df.iterrows():
                    try:
                        trade_time = pd.to_datetime(row['Date']).strftime("%Y-%m-%d %H:%M")
                    except:
                        trade_time = str(row['Date'])
                    conn.execute(
                        "INSERT INTO trades (account_id, trade_time, symbol, side, quantity, price, profit) VALUES (?,?,?,?,?,?,?)",
                        (st.session_state.current_account_id, trade_time,
                         str(row['Symbol']).upper(), str(row['Side']),
                         float(row['Quantity']), float(row['Price']), float(row['Profit']))
                    )
                conn.commit()
                conn.close()
                st.success(f"Imported {len(df)} trades successfully!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to parse file: {e}")

    conn = sqlite3.connect(DB_FILE)
    count = pd.read_sql_query(
        "SELECT COUNT(*) as cnt FROM trades WHERE account_id=?",
        conn, params=(st.session_state.current_account_id,)
    ).iloc[0, 0]
    conn.close()
    st.caption(f"This account has {count} CSV trade records")

def ai_coach_page():
    st.title("🧠 AI Trading Coach")
    if not st.session_state.current_account_id:
        st.warning("Please select an account first")
        return

    try:
        openai_api_key = st.secrets["OPENAI_API_KEY"]
    except KeyError:
        openai_api_key = st.text_input("Enter your OpenAI API Key", type="password")
        if not openai_api_key:
            st.info("Set your API key in Streamlit Secrets, or enter it above")
            st.stop()
    openai.api_key = openai_api_key

    use_notes = st.checkbox("Include Journal Entries", value=True)
    use_trades = st.checkbox("Include CSV Trade Records", value=True)
    num_items = st.slider("How many recent items to analyze?", 3, 30, 10)

    if st.button("Get Coach Feedback"):
        with st.spinner("Coach is analyzing your data..."):
            context = ""
            conn = sqlite3.connect(DB_FILE)
            account_id = st.session_state.current_account_id

            if use_notes:
                notes_df = pd.read_sql_query(
                    "SELECT entry_date, symbol, phase, action_detail, reason, mood FROM notes WHERE account_id=? ORDER BY entry_date DESC LIMIT ?",
                    conn, params=(account_id, num_items)
                )
                if not notes_df.empty:
                    context += "📝 **Journal Entries**\n"
                    for _, r in notes_df.iterrows():
                        context += f"- {r['entry_date']} | {r['symbol']} | {r['phase']} | {r.get('action_detail','')} | Mood: {r['mood']} | Reason: {r['reason']}\n"
                    context += "\n"

            if use_trades:
                trades_df = pd.read_sql_query(
                    "SELECT trade_time, symbol, side, quantity, price, profit FROM trades WHERE account_id=? ORDER BY trade_time DESC LIMIT ?",
                    conn, params=(account_id, num_items)
                )
                if not trades_df.empty:
                    context += "📈 **CSV Trade Records**\n"
                    for _, r in trades_df.iterrows():
                        context += f"- {r['trade_time']} | {r['symbol']} | {r['side']} {r['quantity']} @{r['price']} | P&L: {r['profit']}\n"
            conn.close()

            if not context:
                st.warning("No data to analyze")
                st.stop()

            prompt = f"""You are an experienced trading psychology coach specializing in futures and prop firm evaluations.
Below are recent records from a trader (journal entries and/or trade data).
Analyze their psychological patterns, cognitive biases, and provide actionable improvement suggestions.
Be encouraging and constructive.

=== Trader Records ===
{context}
=== End of Records ===

Please cover:
1. Emotional patterns and cognitive biases
2. Consistency in entry/exit and position management
3. Concrete actionable steps for improvement (stop loss discipline, emotional regulation, etc.)
End with a supportive summary."""

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                )
                st.markdown("### Coach Feedback")
                st.write(response.choices[0].message.content)
            except Exception as e:
                st.error(f"OpenAI API call failed: {e}")

# ===================== Navigation =====================
st.sidebar.title("📓 Trading Journal Pro")
st.sidebar.caption("Works on mobile & desktop")

pages = [
    st.Page(account_page, title="Accounts", icon="🏠"),
    st.Page(note_page, title="New Entry", icon="✍️"),
    st.Page(history_page, title="History", icon="📋"),
    st.Page(import_csv_page, title="Import CSV", icon="📥"),
    st.Page(ai_coach_page, title="AI Coach", icon="🧠"),
]

pg = st.navigation(pages)
pg.run()

if st.session_state.current_account_name:
    st.sidebar.success(f"Account: {st.session_state.current_account_name}")
else:
    st.sidebar.warning("No account selected")
