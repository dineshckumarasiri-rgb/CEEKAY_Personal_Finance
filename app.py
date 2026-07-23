import json
from datetime import date, datetime
from typing import Dict, List, Optional

import gspread
import pandas as pd
import plotly.express as px
import streamlit as st
from google.oauth2.service_account import Credentials


APP_TITLE = "CEEKAY Finance Manager"
WORKBOOK_NAME = "CEEKAY_Personal_Finance"
DATE_FMT = "%Y-%m-%d"

SHEETS: Dict[str, List[str]] = {
    "Assets": [
        "Record ID", "Asset Name", "Category", "Purchase Date", "Purchase Value",
        "Current Value", "Ownership %", "Income Generating", "Monthly Income",
        "Notes", "Created At", "Updated At"
    ],
    "Income": [
        "Record ID", "Date", "Income Source", "Category", "Amount", "Income Type",
        "Description", "Created At", "Updated At"
    ],
    "SalaryAllocation": [
        "Record ID", "Month", "Income Source", "Allocation Category", "Planned Amount",
        "Planned %", "Notes", "Created At", "Updated At"
    ],
    "Expenses": [
        "Record ID", "Date", "Category", "Description", "Amount", "Payment Method",
        "Scope", "Recurring", "Notes", "Created At", "Updated At"
    ],
    "Liabilities": [
        "Record ID", "Liability Date", "Liability Name", "Category", "Original Amount",
        "Interest Rate %", "Monthly Instalment", "Due Date", "Lender", "Description",
        "Status", "Created At", "Updated At"
    ],
    "LiabilityPayments": [
        "Record ID", "Payment Date", "Liability ID", "Liability Name", "Payment Amount",
        "Principal Amount", "Interest Amount", "Payment Method", "Reference No", "Notes",
        "Created At", "Updated At"
    ],
    "Budgets": [
        "Record ID", "Month", "Category", "Budget Amount", "Notes", "Created At", "Updated At"
    ],
    "SavingsGoals": [
        "Record ID", "Goal Name", "Target Amount", "Current Saved", "Target Date", "Status",
        "Notes", "Created At", "Updated At"
    ],
    "Categories": ["Type", "Category", "Active"],
    "Settings": ["Key", "Value"],
}

DEFAULT_CATEGORIES = {
    "Asset": ["Cash", "Bank Balance", "Land", "House / Building", "Vehicle", "Business Investment", "Fixed Deposit", "Gold", "Shares / Investments", "Other"],
    "Income": ["Salary", "CEEKAY Tours", "CEEKAY Homes", "Commission", "Rental Income", "Investment Return", "Other Income"],
    "Expense": ["Household", "Food", "Electricity", "Water", "Education", "Transport", "Vehicle", "Medical", "Loan Payment", "Business Expense", "Entertainment", "Savings", "Investment", "Other"],
    "Liability": ["Bank Loan", "Vehicle Loan", "Credit Card", "Personal Loan", "Business Loan", "Payable to Person", "Supplier Payable", "Other"],
    "Allocation": ["Household Expenses", "Loan Payments", "Savings", "Investments", "Transport", "Education", "Personal Expenses", "Other"],
}

PAYMENT_METHODS = ["Cash", "Bank Transfer", "Card", "Standing Order", "Cheque", "Other"]


st.set_page_config(page_title=APP_TITLE, page_icon="💰", layout="wide")

st.markdown(
    """
    <style>
    .stApp {background: linear-gradient(135deg, #f7f9fc 0%, #eef2f7 100%); color: #111827;}
    [data-testid="stSidebar"] {background: #111827;}
    [data-testid="stSidebar"] * {color: #f9fafb !important;}
    [data-testid="stMetric"] {background: white; padding: 18px; border-radius: 16px; border: 1px solid #e5e7eb; box-shadow: 0 5px 20px rgba(15,23,42,.05);}
    div[data-testid="stForm"] {background: white; padding: 18px; border-radius: 16px; border: 1px solid #e5e7eb;}
    .block-container {padding-top: 1.5rem; padding-bottom: 2.5rem;}
    .finance-title {font-size: 2rem; font-weight: 700; color: #111827; margin-bottom: .1rem;}
    .finance-subtitle {color: #6b7280; margin-bottom: 1rem;}
    .small-note {font-size:.85rem;color:#6b7280;}
    .section-card {background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:16px;margin-bottom:14px;box-shadow:0 4px 16px rgba(15,23,42,.04)}
    </style>
    """,
    unsafe_allow_html=True,
)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def make_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def money(value: float) -> str:
    return f"LKR {value:,.2f}"


def to_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


@st.cache_resource
def get_client():
    if "gcp_service_account" not in st.secrets:
        raise RuntimeError("Google service account details are missing from Streamlit Secrets.")
    info = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    return gspread.authorize(creds)


@st.cache_resource
def get_workbook():
    client = get_client()
    workbook_name = st.secrets.get("workbook_name", WORKBOOK_NAME)
    try:
        book = client.open(workbook_name)
    except gspread.SpreadsheetNotFound:
        book = client.create(workbook_name)
    initialize_workbook(book)
    return book


def initialize_workbook(book):
    existing = {ws.title for ws in book.worksheets()}
    for name, headers in SHEETS.items():
        if name not in existing:
            ws = book.add_worksheet(title=name, rows=2000, cols=max(20, len(headers) + 2))
            ws.append_row(headers)
        else:
            ws = book.worksheet(name)
            first_row = ws.row_values(1)
            if not first_row:
                ws.append_row(headers)
            elif first_row != headers:
                ws.update("A1", [headers])
    try:
        default_sheet = book.worksheet("Sheet1")
        if len(book.worksheets()) > 1 and not default_sheet.get_all_values():
            book.del_worksheet(default_sheet)
    except gspread.WorksheetNotFound:
        pass

    categories = book.worksheet("Categories")
    if len(categories.get_all_values()) <= 1:
        rows = []
        for cat_type, values in DEFAULT_CATEGORIES.items():
            rows.extend([[cat_type, value, "Yes"] for value in values])
        categories.append_rows(rows)

    settings = book.worksheet("Settings")
    if len(settings.get_all_values()) <= 1:
        settings.append_rows([
            ["Currency", "LKR"],
            ["App Name", APP_TITLE],
            ["Figures Hidden By Default", "Yes"],
        ])


@st.cache_data(ttl=60, show_spinner=False)
def load_sheet(sheet_name: str) -> pd.DataFrame:
    ws = get_workbook().worksheet(sheet_name)
    records = ws.get_all_records()
    return pd.DataFrame(records, columns=SHEETS[sheet_name]) if records else pd.DataFrame(columns=SHEETS[sheet_name])


def clear_data_cache():
    load_sheet.clear()


def append_record(sheet_name: str, record: Dict):
    headers = SHEETS[sheet_name]
    row = [record.get(header, "") for header in headers]
    get_workbook().worksheet(sheet_name).append_row(row, value_input_option="USER_ENTERED")
    clear_data_cache()


def update_record(sheet_name: str, record_id: str, updates: Dict) -> bool:
    ws = get_workbook().worksheet(sheet_name)
    values = ws.get_all_values()
    if not values:
        return False
    headers = values[0]
    try:
        id_col = headers.index("Record ID")
    except ValueError:
        return False
    for row_idx, row in enumerate(values[1:], start=2):
        if len(row) > id_col and row[id_col] == record_id:
            current = {h: row[i] if i < len(row) else "" for i, h in enumerate(headers)}
            current.update(updates)
            current["Updated At"] = now_text()
            ws.update(f"A{row_idx}", [[current.get(h, "") for h in headers]], value_input_option="USER_ENTERED")
            clear_data_cache()
            return True
    return False


def delete_record(sheet_name: str, record_id: str) -> bool:
    ws = get_workbook().worksheet(sheet_name)
    values = ws.get_all_values()
    if not values:
        return False
    headers = values[0]
    if "Record ID" not in headers:
        return False
    id_col = headers.index("Record ID")
    for row_idx, row in enumerate(values[1:], start=2):
        if len(row) > id_col and row[id_col] == record_id:
            ws.delete_rows(row_idx)
            clear_data_cache()
            return True
    return False


def categories(category_type: str) -> List[str]:
    df = load_sheet("Categories")
    if df.empty:
        return DEFAULT_CATEGORIES.get(category_type, ["Other"])
    active = df[(df["Type"] == category_type) & (df["Active"].astype(str).str.lower().isin(["yes", "true", "1"]))]
    result = active["Category"].dropna().astype(str).tolist()
    return result or DEFAULT_CATEGORIES.get(category_type, ["Other"])


def record_selector(df: pd.DataFrame, label_col: str, key: str) -> Optional[str]:
    if df.empty:
        st.info("No records are available yet.")
        return None
    options = df["Record ID"].astype(str).tolist()
    labels = {str(r["Record ID"]): f"{r.get(label_col, '')} — {r['Record ID']}" for _, r in df.iterrows()}
    return st.selectbox("Select record", options, format_func=lambda x: labels.get(x, x), key=key)


def data_editor_table(df: pd.DataFrame, hide_cols: Optional[List[str]] = None):
    if df.empty:
        st.info("No records found.")
        return
    view = df.drop(columns=hide_cols or [], errors="ignore")
    st.dataframe(view, use_container_width=True, hide_index=True)


def login():
    if st.session_state.get("authenticated"):
        return True

    # Single-card login layout, matching the clean CEEKAY Homes style.
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="collapsedControl"] {display:none !important;}
        .block-container {
            max-width: 590px !important;
            padding-top: 3.2rem !important;
            padding-bottom: 2rem !important;
        }
        .login-card-top {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-bottom: 0;
            border-radius: 28px 28px 0 0;
            padding: 28px 34px 18px;
            text-align: center;
            box-shadow: 0 20px 55px rgba(15, 23, 42, 0.10);
        }
        .login-logo {
            width: 82px;
            height: 82px;
            margin: 0 auto 15px;
            border-radius: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-size: 2.15rem;
            font-weight: 500;
            background: linear-gradient(145deg, #2563eb, #0f766e);
            box-shadow: 0 12px 28px rgba(37, 99, 235, 0.22);
        }
        .login-brand {
            color: #0f172a;
            font-size: 1.95rem;
            font-weight: 800;
            letter-spacing: -0.04em;
            margin: 0;
        }
        .login-subtitle {
            color: #64748b;
            font-size: 1.02rem;
            margin: 8px 0 0;
        }
        .login-secure {
            background: #f1f5f9;
            color: #475569;
            border-radius: 13px;
            padding: 12px 16px;
            margin-top: 20px;
            font-size: .88rem;
        }
        div[data-testid="stForm"] {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-top: 0 !important;
            border-radius: 0 0 28px 28px !important;
            padding: 4px 34px 30px !important;
            box-shadow: 0 20px 55px rgba(15, 23, 42, 0.10) !important;
        }
        div[data-testid="stForm"] h2 {
            color: #0f172a;
            font-size: 1.75rem;
            margin-top: 0;
            margin-bottom: .2rem;
        }
        div[data-testid="stForm"] p {color:#64748b; margin-bottom:1.15rem;}
        div[data-testid="stTextInput"] input {
            min-height: 52px;
            border-radius: 12px;
            background: #f8fafc;
        }
        div[data-testid="stFormSubmitButton"] button {
            min-height: 52px;
            border-radius: 12px;
            border: 0;
            background: linear-gradient(90deg, #ef4444, #fb4b55);
            color: #ffffff;
            font-weight: 700;
            margin-top: 8px;
        }
        div[data-testid="stFormSubmitButton"] button:hover {
            background: linear-gradient(90deg, #dc2626, #ef4444);
            color: #ffffff;
            border: 0;
        }
        @media (max-width: 640px) {
            .block-container {padding: 1.2rem .85rem 2rem !important;}
            .login-card-top {padding: 24px 20px 15px;}
            div[data-testid="stForm"] {padding: 4px 20px 25px !important;}
        }
        </style>
        <div class="login-card-top">
            <div class="login-logo">Rs</div>
            <div class="login-brand">CEEKAY Finance</div>
            <div class="login-subtitle">Personal Finance Manager</div>
            <div class="login-secure">🔒 Secure private access · Your financial data stays in Google Sheets</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        st.markdown("## Welcome back")
        st.markdown("Enter your credentials to continue.")
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        admin_cfg = st.secrets.get("admin", {})
        expected_user = str(admin_cfg.get("username", st.secrets.get("admin_username", "admin")))
        expected_password = str(admin_cfg.get("password", st.secrets.get("admin_password", "admin123")))
        if username.strip() == expected_user and password == expected_password:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username.strip()
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    return False


def liability_summary(liabilities: pd.DataFrame, payments: pd.DataFrame) -> pd.DataFrame:
    if liabilities.empty:
        return pd.DataFrame(columns=["Record ID", "Liability Name", "Original Amount", "Principal Paid", "Interest Paid", "Total Paid", "Outstanding", "Progress %", "Status"])
    p = payments.copy()
    for col in ["Payment Amount", "Principal Amount", "Interest Amount"]:
        if col in p:
            p[col] = p[col].apply(to_float)
    grouped = p.groupby("Liability ID", dropna=False).agg(
        Principal_Paid=("Principal Amount", "sum"),
        Interest_Paid=("Interest Amount", "sum"),
        Total_Paid=("Payment Amount", "sum"),
    ).reset_index() if not p.empty else pd.DataFrame(columns=["Liability ID", "Principal_Paid", "Interest_Paid", "Total_Paid"])

    result = liabilities.copy()
    result["Original Amount"] = result["Original Amount"].apply(to_float)
    result = result.merge(grouped, left_on="Record ID", right_on="Liability ID", how="left")
    for col in ["Principal_Paid", "Interest_Paid", "Total_Paid"]:
        result[col] = result[col].fillna(0.0)
    result["Outstanding"] = (result["Original Amount"] - result["Principal_Paid"]).clip(lower=0)
    result["Progress %"] = result.apply(lambda r: min(100.0, (r["Principal_Paid"] / r["Original Amount"] * 100) if r["Original Amount"] else 0), axis=1)
    result["Calculated Status"] = result["Outstanding"].apply(lambda x: "Paid" if x <= 0.01 else "Active")
    return result.rename(columns={"Principal_Paid": "Principal Paid", "Interest_Paid": "Interest Paid", "Total_Paid": "Total Paid"})


def dashboard():
    assets = load_sheet("Assets")
    income = load_sheet("Income")
    expenses = load_sheet("Expenses")
    liabilities = load_sheet("Liabilities")
    payments = load_sheet("LiabilityPayments")
    goals = load_sheet("SavingsGoals")

    for col in ["Current Value", "Monthly Income"]:
        if col in assets:
            assets[col] = assets[col].apply(to_float)
    if "Amount" in income:
        income["Amount"] = income["Amount"].apply(to_float)
    if "Amount" in expenses:
        expenses["Amount"] = expenses["Amount"].apply(to_float)

    liab = liability_summary(liabilities, payments)
    total_assets = assets["Current Value"].sum() if not assets.empty else 0
    outstanding = liab["Outstanding"].sum() if not liab.empty else 0
    net_worth = total_assets - outstanding

    today_month = date.today().strftime("%Y-%m")
    month_income = 0.0
    month_expenses = 0.0
    if not income.empty:
        month_income = income[income["Date"].astype(str).str.startswith(today_month)]["Amount"].sum()
    if not expenses.empty:
        month_expenses = expenses[expenses["Date"].astype(str).str.startswith(today_month)]["Amount"].sum()
    available = month_income - month_expenses

    if "show_figures" not in st.session_state:
        st.session_state["show_figures"] = False
    c1, c2 = st.columns([1, 5])
    with c1:
        if st.button("Hide Figures" if st.session_state["show_figures"] else "View Figures"):
            st.session_state["show_figures"] = not st.session_state["show_figures"]
            st.rerun()

    def secure(value: float):
        return money(value) if st.session_state["show_figures"] else "********"

    cols = st.columns(4)
    cols[0].metric("Total Assets", secure(total_assets))
    cols[1].metric("Outstanding Liabilities", secure(outstanding))
    cols[2].metric("Net Worth", secure(net_worth))
    cols[3].metric("This Month Balance", secure(available))

    cols = st.columns(4)
    cols[0].metric("This Month Income", secure(month_income))
    cols[1].metric("This Month Expenses", secure(month_expenses))
    cols[2].metric("Savings Rate", f"{((available / month_income) * 100 if month_income else 0):.1f}%")
    cols[3].metric("Debt-to-Asset Ratio", f"{((outstanding / total_assets) * 100 if total_assets else 0):.1f}%")

    left, right = st.columns(2)
    with left:
        st.subheader("Income vs Expenses")
        combined = []
        if not income.empty:
            temp = income.copy()
            temp["Month"] = temp["Date"].astype(str).str[:7]
            combined.append(temp.groupby("Month")["Amount"].sum().reset_index().assign(Type="Income"))
        if not expenses.empty:
            temp = expenses.copy()
            temp["Month"] = temp["Date"].astype(str).str[:7]
            combined.append(temp.groupby("Month")["Amount"].sum().reset_index().assign(Type="Expenses"))
        if combined:
            chart_df = pd.concat(combined, ignore_index=True)
            fig = px.bar(chart_df, x="Month", y="Amount", color="Type", barmode="group")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add income and expense records to display this chart.")

    with right:
        st.subheader("Expense Breakdown")
        if not expenses.empty:
            exp_breakdown = expenses.groupby("Category")["Amount"].sum().reset_index()
            fig = px.pie(exp_breakdown, names="Category", values="Amount", hole=.55)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add expense records to display this chart.")

    left, right = st.columns(2)
    with left:
        st.subheader("Liability Progress")
        if not liab.empty:
            show = liab[["Liability Name", "Original Amount", "Principal Paid", "Outstanding", "Progress %"]].copy()
            st.dataframe(show, use_container_width=True, hide_index=True)
        else:
            st.info("No liabilities recorded.")
    with right:
        st.subheader("Savings Goals")
        if not goals.empty:
            g = goals.copy()
            g["Target Amount"] = g["Target Amount"].apply(to_float)
            g["Current Saved"] = g["Current Saved"].apply(to_float)
            g["Progress %"] = g.apply(lambda r: min(100.0, (r["Current Saved"] / r["Target Amount"] * 100) if r["Target Amount"] else 0), axis=1)
            st.dataframe(g[["Goal Name", "Target Amount", "Current Saved", "Progress %", "Target Date", "Status"]], use_container_width=True, hide_index=True)
        else:
            st.info("No savings goals recorded.")


def assets_page():
    st.subheader("Asset Management")
    tab1, tab2, tab3 = st.tabs(["Add Asset", "Edit / Delete", "Asset List"])
    with tab1:
        with st.form("add_asset"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Asset Name")
            category = c2.selectbox("Category", categories("Asset"))
            purchase_date = c1.date_input("Purchase Date", value=date.today())
            purchase_value = c2.number_input("Purchase Value", min_value=0.0, step=1000.0)
            current_value = c1.number_input("Current Estimated Value", min_value=0.0, step=1000.0)
            ownership = c2.number_input("Ownership %", min_value=0.0, max_value=100.0, value=100.0)
            income_gen = c1.selectbox("Income Generating", ["No", "Yes"])
            monthly_income = c2.number_input("Monthly Income", min_value=0.0, step=1000.0)
            notes = st.text_area("Notes")
            if st.form_submit_button("Save Asset", use_container_width=True):
                if not name.strip():
                    st.error("Asset name is required.")
                else:
                    append_record("Assets", {
                        "Record ID": make_id("AST"), "Asset Name": name.strip(), "Category": category,
                        "Purchase Date": purchase_date.strftime(DATE_FMT), "Purchase Value": purchase_value,
                        "Current Value": current_value, "Ownership %": ownership, "Income Generating": income_gen,
                        "Monthly Income": monthly_income, "Notes": notes, "Created At": now_text(), "Updated At": now_text()
                    })
                    st.success("Asset saved.")
                    st.rerun()
    with tab2:
        df = load_sheet("Assets")
        rid = record_selector(df, "Asset Name", "asset_edit")
        if rid:
            row = df[df["Record ID"].astype(str) == rid].iloc[0]
            with st.form("edit_asset"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Asset Name", value=str(row["Asset Name"]))
                cat_opts = categories("Asset")
                category = c2.selectbox("Category", cat_opts, index=cat_opts.index(row["Category"]) if row["Category"] in cat_opts else 0)
                current_value = c1.number_input("Current Value", min_value=0.0, value=to_float(row["Current Value"]), step=1000.0)
                monthly_income = c2.number_input("Monthly Income", min_value=0.0, value=to_float(row["Monthly Income"]), step=1000.0)
                notes = st.text_area("Notes", value=str(row["Notes"]))
                save = st.form_submit_button("Update Asset", use_container_width=True)
                if save:
                    update_record("Assets", rid, {"Asset Name": name, "Category": category, "Current Value": current_value, "Monthly Income": monthly_income, "Notes": notes})
                    st.success("Asset updated.")
                    st.rerun()
            confirm = st.checkbox("I confirm that I want to delete this asset", key="delete_asset_confirm")
            if st.button("Delete Asset", type="primary", disabled=not confirm):
                delete_record("Assets", rid)
                st.success("Asset deleted.")
                st.rerun()
    with tab3:
        data_editor_table(load_sheet("Assets"), ["Created At", "Updated At"])


def income_page():
    st.subheader("Income Management")
    tab1, tab2, tab3 = st.tabs(["Add Income", "Edit / Delete", "Income List"])
    with tab1:
        with st.form("add_income"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Date", value=date.today())
            source = c2.text_input("Income Source")
            cat = c1.selectbox("Category", categories("Income"))
            amount = c2.number_input("Amount", min_value=0.0, step=1000.0)
            income_type = c1.selectbox("Income Type", ["Recurring", "One-time"])
            desc = st.text_area("Description")
            if st.form_submit_button("Save Income", use_container_width=True):
                if not source.strip() or amount <= 0:
                    st.error("Income source and a valid amount are required.")
                else:
                    append_record("Income", {"Record ID": make_id("INC"), "Date": d.strftime(DATE_FMT), "Income Source": source.strip(), "Category": cat, "Amount": amount, "Income Type": income_type, "Description": desc, "Created At": now_text(), "Updated At": now_text()})
                    st.success("Income saved.")
                    st.rerun()
    with tab2:
        df = load_sheet("Income")
        rid = record_selector(df, "Income Source", "income_edit")
        if rid:
            row = df[df["Record ID"].astype(str) == rid].iloc[0]
            with st.form("edit_income"):
                amount = st.number_input("Amount", min_value=0.0, value=to_float(row["Amount"]), step=1000.0)
                desc = st.text_area("Description", value=str(row["Description"]))
                if st.form_submit_button("Update Income", use_container_width=True):
                    update_record("Income", rid, {"Amount": amount, "Description": desc})
                    st.success("Income updated.")
                    st.rerun()
            confirm = st.checkbox("Confirm income deletion", key="delete_income_confirm")
            if st.button("Delete Income", type="primary", disabled=not confirm):
                delete_record("Income", rid)
                st.rerun()
    with tab3:
        data_editor_table(load_sheet("Income"), ["Created At", "Updated At"])


def allocation_page():
    st.subheader("Salary & Income Allocation")
    with st.form("add_allocation"):
        c1, c2 = st.columns(2)
        month = c1.text_input("Month", value=date.today().strftime("%Y-%m"), help="Use YYYY-MM format")
        source = c2.text_input("Income Source", value="Salary")
        category = c1.selectbox("Allocation Category", categories("Allocation"))
        planned_amount = c2.number_input("Planned Amount", min_value=0.0, step=1000.0)
        planned_pct = c1.number_input("Planned %", min_value=0.0, max_value=100.0, step=1.0)
        notes = st.text_area("Notes")
        if st.form_submit_button("Save Allocation", use_container_width=True):
            append_record("SalaryAllocation", {"Record ID": make_id("SAL"), "Month": month, "Income Source": source, "Allocation Category": category, "Planned Amount": planned_amount, "Planned %": planned_pct, "Notes": notes, "Created At": now_text(), "Updated At": now_text()})
            st.success("Allocation saved.")
            st.rerun()

    df = load_sheet("SalaryAllocation")
    if not df.empty:
        df["Planned Amount"] = df["Planned Amount"].apply(to_float)
        selected_month = st.selectbox("View Month", sorted(df["Month"].astype(str).unique(), reverse=True))
        show = df[df["Month"].astype(str) == selected_month]
        total_alloc = show["Planned Amount"].sum()
        income = load_sheet("Income")
        if not income.empty:
            income["Amount"] = income["Amount"].apply(to_float)
            month_income = income[income["Date"].astype(str).str.startswith(selected_month)]["Amount"].sum()
        else:
            month_income = 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Monthly Income", money(month_income))
        c2.metric("Planned Allocation", money(total_alloc))
        c3.metric("Unallocated Balance", money(month_income - total_alloc))
        if total_alloc > month_income and month_income > 0:
            st.warning("Planned allocations exceed the recorded income for this month.")
        data_editor_table(show, ["Created At", "Updated At"])


def expenses_page():
    st.subheader("Expense Management")
    tab1, tab2, tab3 = st.tabs(["Add Expense", "Edit / Delete", "Expense List"])
    with tab1:
        with st.form("add_expense"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Date", value=date.today())
            cat = c2.selectbox("Category", categories("Expense"))
            desc = c1.text_input("Description")
            amount = c2.number_input("Amount", min_value=0.0, step=500.0)
            method = c1.selectbox("Payment Method", PAYMENT_METHODS)
            scope = c2.selectbox("Scope", ["Personal", "CEEKAY Tours", "CEEKAY Homes", "Other Business"])
            recurring = c1.selectbox("Recurring", ["No", "Yes"])
            notes = st.text_area("Notes")
            if st.form_submit_button("Save Expense", use_container_width=True):
                if amount <= 0:
                    st.error("Enter a valid expense amount.")
                else:
                    append_record("Expenses", {"Record ID": make_id("EXP"), "Date": d.strftime(DATE_FMT), "Category": cat, "Description": desc, "Amount": amount, "Payment Method": method, "Scope": scope, "Recurring": recurring, "Notes": notes, "Created At": now_text(), "Updated At": now_text()})
                    st.success("Expense saved.")
                    st.rerun()
    with tab2:
        df = load_sheet("Expenses")
        rid = record_selector(df, "Description", "expense_edit")
        if rid:
            row = df[df["Record ID"].astype(str) == rid].iloc[0]
            with st.form("edit_expense"):
                amount = st.number_input("Amount", min_value=0.0, value=to_float(row["Amount"]), step=500.0)
                notes = st.text_area("Notes", value=str(row["Notes"]))
                if st.form_submit_button("Update Expense", use_container_width=True):
                    update_record("Expenses", rid, {"Amount": amount, "Notes": notes})
                    st.success("Expense updated.")
                    st.rerun()
            confirm = st.checkbox("Confirm expense deletion", key="delete_expense_confirm")
            if st.button("Delete Expense", type="primary", disabled=not confirm):
                delete_record("Expenses", rid)
                st.rerun()
    with tab3:
        data_editor_table(load_sheet("Expenses"), ["Created At", "Updated At"])


def liabilities_page():
    st.subheader("Liability Management")
    tab1, tab2, tab3 = st.tabs(["Add Liability", "Edit / Delete", "Liability Summary"])
    with tab1:
        with st.form("add_liability"):
            c1, c2 = st.columns(2)
            d = c1.date_input("Liability Date", value=date.today())
            name = c2.text_input("Liability Name")
            cat = c1.selectbox("Category", categories("Liability"))
            original = c2.number_input("Original Amount", min_value=0.0, step=1000.0)
            rate = c1.number_input("Interest Rate %", min_value=0.0, step=0.1)
            instalment = c2.number_input("Monthly Instalment", min_value=0.0, step=1000.0)
            due = c1.date_input("Due Date", value=date.today())
            lender = c2.text_input("Lender")
            desc = st.text_area("Description")
            status = st.selectbox("Status", ["Active", "On Hold", "Paid"])
            if st.form_submit_button("Save Liability", use_container_width=True):
                if not name.strip() or original <= 0:
                    st.error("Liability name and original amount are required.")
                else:
                    append_record("Liabilities", {"Record ID": make_id("LIA"), "Liability Date": d.strftime(DATE_FMT), "Liability Name": name.strip(), "Category": cat, "Original Amount": original, "Interest Rate %": rate, "Monthly Instalment": instalment, "Due Date": due.strftime(DATE_FMT), "Lender": lender, "Description": desc, "Status": status, "Created At": now_text(), "Updated At": now_text()})
                    st.success("Liability saved.")
                    st.rerun()
    with tab2:
        df = load_sheet("Liabilities")
        rid = record_selector(df, "Liability Name", "liability_edit")
        if rid:
            row = df[df["Record ID"].astype(str) == rid].iloc[0]
            with st.form("edit_liability"):
                instalment = st.number_input("Monthly Instalment", min_value=0.0, value=to_float(row["Monthly Instalment"]), step=1000.0)
                status = st.selectbox("Status", ["Active", "On Hold", "Paid"], index=["Active", "On Hold", "Paid"].index(row["Status"]) if row["Status"] in ["Active", "On Hold", "Paid"] else 0)
                desc = st.text_area("Description", value=str(row["Description"]))
                if st.form_submit_button("Update Liability", use_container_width=True):
                    update_record("Liabilities", rid, {"Monthly Instalment": instalment, "Status": status, "Description": desc})
                    st.success("Liability updated.")
                    st.rerun()
            confirm = st.checkbox("Confirm liability deletion", key="delete_liability_confirm")
            if st.button("Delete Liability", type="primary", disabled=not confirm):
                related = load_sheet("LiabilityPayments")
                if not related.empty and (related["Liability ID"].astype(str) == rid).any():
                    st.error("Delete the related liability payments first.")
                else:
                    delete_record("Liabilities", rid)
                    st.rerun()
    with tab3:
        summary = liability_summary(load_sheet("Liabilities"), load_sheet("LiabilityPayments"))
        if not summary.empty:
            data_editor_table(summary[["Record ID", "Liability Name", "Original Amount", "Principal Paid", "Interest Paid", "Total Paid", "Outstanding", "Progress %", "Calculated Status"]])
        else:
            st.info("No liabilities recorded.")


def payments_page():
    st.subheader("Liability Payments")
    liabilities = load_sheet("Liabilities")
    if liabilities.empty:
        st.warning("Add a liability before recording payments.")
        return
    summary = liability_summary(liabilities, load_sheet("LiabilityPayments"))
    active = summary[summary["Outstanding"] > 0.01]
    with st.form("add_payment"):
        options = active["Record ID"].astype(str).tolist() if not active.empty else summary["Record ID"].astype(str).tolist()
        label_map = {str(r["Record ID"]): f"{r['Liability Name']} — Outstanding {money(r['Outstanding'])}" for _, r in summary.iterrows()}
        lid = st.selectbox("Liability", options, format_func=lambda x: label_map.get(x, x))
        row = summary[summary["Record ID"].astype(str) == lid].iloc[0]
        c1, c2 = st.columns(2)
        d = c1.date_input("Payment Date", value=date.today())
        payment_amount = c2.number_input("Total Payment Amount", min_value=0.0, step=1000.0)
        principal = c1.number_input("Principal Amount", min_value=0.0, max_value=float(row["Outstanding"]), step=1000.0)
        interest = c2.number_input("Interest Amount", min_value=0.0, step=100.0)
        method = c1.selectbox("Payment Method", PAYMENT_METHODS)
        ref = c2.text_input("Reference No")
        notes = st.text_area("Notes")
        if st.form_submit_button("Save Payment", use_container_width=True):
            if payment_amount <= 0 or principal < 0:
                st.error("Enter a valid payment amount.")
            elif principal + interest > payment_amount + 0.01:
                st.error("Principal plus interest cannot exceed the total payment amount.")
            else:
                append_record("LiabilityPayments", {"Record ID": make_id("PAY"), "Payment Date": d.strftime(DATE_FMT), "Liability ID": lid, "Liability Name": row["Liability Name"], "Payment Amount": payment_amount, "Principal Amount": principal, "Interest Amount": interest, "Payment Method": method, "Reference No": ref, "Notes": notes, "Created At": now_text(), "Updated At": now_text()})
                if principal >= row["Outstanding"] - 0.01:
                    update_record("Liabilities", lid, {"Status": "Paid"})
                st.success("Payment saved.")
                st.rerun()
    st.subheader("Payment History")
    data_editor_table(load_sheet("LiabilityPayments"), ["Created At", "Updated At"])


def budgets_page():
    st.subheader("Monthly Budget")
    with st.form("add_budget"):
        c1, c2 = st.columns(2)
        month = c1.text_input("Month", value=date.today().strftime("%Y-%m"))
        category = c2.selectbox("Category", categories("Expense"))
        amount = c1.number_input("Budget Amount", min_value=0.0, step=1000.0)
        notes = st.text_area("Notes")
        if st.form_submit_button("Save Budget", use_container_width=True):
            append_record("Budgets", {"Record ID": make_id("BUD"), "Month": month, "Category": category, "Budget Amount": amount, "Notes": notes, "Created At": now_text(), "Updated At": now_text()})
            st.success("Budget saved.")
            st.rerun()

    budgets = load_sheet("Budgets")
    expenses = load_sheet("Expenses")
    if budgets.empty:
        st.info("No budgets recorded.")
        return
    budgets["Budget Amount"] = budgets["Budget Amount"].apply(to_float)
    expenses["Amount"] = expenses["Amount"].apply(to_float) if not expenses.empty else 0
    month = st.selectbox("Budget Month", sorted(budgets["Month"].astype(str).unique(), reverse=True))
    b = budgets[budgets["Month"].astype(str) == month].groupby("Category")["Budget Amount"].sum().reset_index()
    if not expenses.empty:
        e = expenses[expenses["Date"].astype(str).str.startswith(month)].groupby("Category")["Amount"].sum().reset_index().rename(columns={"Amount": "Actual Expense"})
    else:
        e = pd.DataFrame(columns=["Category", "Actual Expense"])
    compare = b.merge(e, on="Category", how="left")
    compare["Actual Expense"] = compare["Actual Expense"].fillna(0)
    compare["Remaining"] = compare["Budget Amount"] - compare["Actual Expense"]
    compare["Usage %"] = compare.apply(lambda r: (r["Actual Expense"] / r["Budget Amount"] * 100) if r["Budget Amount"] else 0, axis=1)
    st.dataframe(compare, use_container_width=True, hide_index=True)
    fig = px.bar(compare, x="Category", y=["Budget Amount", "Actual Expense"], barmode="group")
    st.plotly_chart(fig, use_container_width=True)


def goals_page():
    st.subheader("Savings Goals")
    tab1, tab2 = st.tabs(["Add Goal", "Manage Goals"])
    with tab1:
        with st.form("add_goal"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Goal Name")
            target = c2.number_input("Target Amount", min_value=0.0, step=1000.0)
            saved = c1.number_input("Current Saved", min_value=0.0, step=1000.0)
            target_date = c2.date_input("Target Date", value=date.today())
            status = c1.selectbox("Status", ["Active", "Completed", "Paused"])
            notes = st.text_area("Notes")
            if st.form_submit_button("Save Goal", use_container_width=True):
                append_record("SavingsGoals", {"Record ID": make_id("GOA"), "Goal Name": name, "Target Amount": target, "Current Saved": saved, "Target Date": target_date.strftime(DATE_FMT), "Status": status, "Notes": notes, "Created At": now_text(), "Updated At": now_text()})
                st.success("Goal saved.")
                st.rerun()
    with tab2:
        df = load_sheet("SavingsGoals")
        rid = record_selector(df, "Goal Name", "goal_edit")
        if rid:
            row = df[df["Record ID"].astype(str) == rid].iloc[0]
            with st.form("edit_goal"):
                saved = st.number_input("Current Saved", min_value=0.0, value=to_float(row["Current Saved"]), step=1000.0)
                status = st.selectbox("Status", ["Active", "Completed", "Paused"], index=["Active", "Completed", "Paused"].index(row["Status"]) if row["Status"] in ["Active", "Completed", "Paused"] else 0)
                if st.form_submit_button("Update Goal", use_container_width=True):
                    update_record("SavingsGoals", rid, {"Current Saved": saved, "Status": status})
                    st.success("Goal updated.")
                    st.rerun()
            confirm = st.checkbox("Confirm goal deletion", key="delete_goal_confirm")
            if st.button("Delete Goal", type="primary", disabled=not confirm):
                delete_record("SavingsGoals", rid)
                st.rerun()
        data_editor_table(df, ["Created At", "Updated At"])


def reports_page():
    st.subheader("Reports & Data Export")
    report = st.selectbox("Select Report", ["Assets", "Income", "Expenses", "Liabilities", "Liability Payments", "Salary Allocation", "Budgets", "Savings Goals", "Monthly Summary"])
    mapping = {
        "Assets": "Assets", "Income": "Income", "Expenses": "Expenses", "Liabilities": "Liabilities",
        "Liability Payments": "LiabilityPayments", "Salary Allocation": "SalaryAllocation",
        "Budgets": "Budgets", "Savings Goals": "SavingsGoals"
    }
    if report in mapping:
        df = load_sheet(mapping[report])
    else:
        income = load_sheet("Income")
        expenses = load_sheet("Expenses")
        if not income.empty:
            income["Amount"] = income["Amount"].apply(to_float)
            inc = income.assign(Month=income["Date"].astype(str).str[:7]).groupby("Month")["Amount"].sum().reset_index(name="Income")
        else:
            inc = pd.DataFrame(columns=["Month", "Income"])
        if not expenses.empty:
            expenses["Amount"] = expenses["Amount"].apply(to_float)
            exp = expenses.assign(Month=expenses["Date"].astype(str).str[:7]).groupby("Month")["Amount"].sum().reset_index(name="Expenses")
        else:
            exp = pd.DataFrame(columns=["Month", "Expenses"])
        df = inc.merge(exp, on="Month", how="outer").fillna(0)
        df["Balance"] = df["Income"] - df["Expenses"]
        df = df.sort_values("Month", ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True)
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name=f"{report.lower().replace(' ', '_')}.csv", mime="text/csv", use_container_width=True)


def settings_page():
    st.subheader("Categories & Settings")
    with st.form("add_category"):
        c1, c2, c3 = st.columns(3)
        cat_type = c1.selectbox("Type", list(DEFAULT_CATEGORIES.keys()))
        category = c2.text_input("New Category")
        active = c3.selectbox("Active", ["Yes", "No"])
        if st.form_submit_button("Add Category", use_container_width=True):
            if category.strip():
                get_workbook().worksheet("Categories").append_row([cat_type, category.strip(), active])
                clear_data_cache()
                st.success("Category added.")
                st.rerun()
    st.markdown('<div class="small-note">The Google Sheet is the live database. Do not rename worksheet tabs after deployment.</div>', unsafe_allow_html=True)
    data_editor_table(load_sheet("Categories"))


def main():
    if not login():
        st.stop()
    try:
        get_workbook()
    except Exception as exc:
        st.error(f"Could not connect to Google Sheets: {exc}")
        st.info("Add the Google service account details to Streamlit Secrets and share the spreadsheet with the service-account email.")
        st.stop()

    with st.sidebar:
        st.title("CEEKAY Finance")
        page = st.radio("Navigation", [
            "Dashboard", "Assets", "Income", "Salary Allocation", "Expenses",
            "Liabilities", "Liability Payments", "Monthly Budget", "Savings Goals",
            "Reports", "Settings"
        ])
        st.divider()
        st.caption("Personal finance management")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.markdown(f'<div class="finance-title">{page}</div>', unsafe_allow_html=True)
    st.markdown('<div class="finance-subtitle">Manage your financial position with clear records and reports.</div>', unsafe_allow_html=True)

    pages = {
        "Dashboard": dashboard,
        "Assets": assets_page,
        "Income": income_page,
        "Salary Allocation": allocation_page,
        "Expenses": expenses_page,
        "Liabilities": liabilities_page,
        "Liability Payments": payments_page,
        "Monthly Budget": budgets_page,
        "Savings Goals": goals_page,
        "Reports": reports_page,
        "Settings": settings_page,
    }
    pages[page]()


if __name__ == "__main__":
    main()
