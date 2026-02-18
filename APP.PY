import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="WTB Tracker (Manual Mode)", layout="wide", page_icon="👟")
st.title("WTB Tracker – Manual Sales Paste Mode")
st.info("API fetch is temporarily disabled due to 403 errors. Paste raw StockX sales data below to analyze.")

# ─── PAYOUT FORMULA ──────────────────────────────────────────────
def calculate_net(price):
    if price < 57:
        return round(price - 4.5 - (price * 0.03) - 4.00, 2)
    else:
        return round(price - (price * 0.08) - (price * 0.03) - 4.00, 2)

def get_target_roi(est_days):
    if est_days < 5:
        return 0.30
    elif 6 <= est_days <= 25:
        return 0.35
    else:
        return 0.40

# ─── MANUAL ANALYSIS FUNCTION ────────────────────────────────────
def analyze_pasted_sales(raw_text, sku, size, listed_price=0, platform="Manual", priority="Medium (Yellow)"):
    prices = []
    lines = raw_text.strip().split('\n')
    cutoff = datetime.now() - timedelta(days=120)

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if '/' in line and ',' in line:  # date line
            try:
                date_part = line.split(',')[0].strip()
                date = datetime.strptime(date_part, '%m/%d/%y')
                if date > datetime.now():
                    date = date.replace(year=date.year - 100)
                i += 1
                while i < len(lines):
                    price_line = lines[i].strip()
                    if price_line.startswith('£'):
                        price_str = price_line.replace('£', '').replace(',', '').strip()
                        price = float(price_str)
                        if date >= cutoff:
                            prices.append(price)
                        break
                    i += 1
                continue
            except:
                pass
        i += 1

    if not prices:
        return None, "No valid sales found in last 120 days."

    n = len(prices)
    avg_sale = sum(prices) / n
    avg_net = sum(calculate_net(p) for p in prices) / n
    est_days = 120 / n if n > 0 else 999
    roi_target = get_target_roi(est_days)
    rec_price = round(avg_net / (1 + roi_target), 2) if avg_net > 0 else 0
    roi_pct = round((avg_net - listed_price) / listed_price * 100, 1) if listed_price > 0 else 0

    result_row = {
        "SKU": sku,
        "Size": size,
        "Platform": platform,
        "Listed Price": listed_price,
        "Priority": priority,
        "#Sales 120D": n,
        "Avg Sale £": round(avg_sale, 2),
        "Avg Payout £": round(avg_net, 2),
        "ROI %": roi_pct,
        "Recommended Pay £": rec_price,
        "Est Days to Sell": round(est_days, 1)
    }
    return result_row, None

# ─── SESSION STATE TABLES ────────────────────────────────────────
platforms = ["Vinted", "eBay", "Other/Retail"]
if "tables" not in st.session_state:
    st.session_state.tables = {}
    for p in platforms:
        st.session_state.tables[p] = pd.DataFrame(columns=[
            "SKU", "Size", "Platform", "Listed Price", "Priority",
            "#Sales 120D", "Avg Sale £", "Avg Payout £", "ROI %",
            "Recommended Pay £", "Est Days to Sell"
        ])

# ─── ADD MANUAL ENTRY ────────────────────────────────────────────
with st.expander("➕ Add New Manual Entry", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sku = st.text_input("SKU")
        size = st.text_input("UK Size")
    with col2:
        platform = st.selectbox("Platform", platforms)
        listed_price = st.number_input("Listed Price (£)", min_value=0.0, value=0.0)
    with col3:
        priority = st.selectbox("Priority", ["High (Red)", "Medium (Yellow)", "Low (Green)"])
    with col4:
        raw_sales = st.text_area("Paste Raw StockX Sales Data Here", height=150)

    if st.button("Analyze & Add to Table"):
        if sku and size and raw_sales:
            row, err = analyze_pasted_sales(raw_sales, sku, size, listed_price, platform, priority)
            if err:
                st.error(err)
            else:
                st.session_state.tables[platform] = pd.concat(
                    [st.session_state.tables[platform], pd.DataFrame([row])],
                    ignore_index=True
                )
                st.success(f"Added {sku} {size} to {platform}")
        else:
            st.warning("Fill all fields + paste sales data")

# ─── DISPLAY TABLES ──────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["Vinted", "eBay", "Other/Retail"])

for tab, p in zip([tab1, tab2, tab3], platforms):
    with tab:
        edited_df = st.data_editor(
            st.session_state.tables[p],
            num_rows="dynamic",
            use_container_width=True,
            key=f"{p.lower()}_editor"
        )
        st.session_state.tables[p] = edited_df

# ─── DASHBOARD ───────────────────────────────────────────────────
st.header("📊 Dashboard")
total = sum(len(df) for df in st.session_state.tables.values())
high_cost = sum(df[df["Priority"] == "High (Red)"]["Recommended Pay £"].sum() for df in st.session_state.tables.values())

cols = st.columns(3)
cols[0].metric("Total Items", total)
cols[1].metric("High Priority Cost", f"£{high_cost:,.0f}")

# Export
if st.button("Export All to CSV"):
    all_df = pd.concat(st.session_state.tables.values(), ignore_index=True)
    st.download_button("Download CSV", all_df.to_csv(index=False), "wtb_tracker.csv")

st.caption("Manual mode – paste StockX sales data • API coming back soon")
