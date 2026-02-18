import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time

st.set_page_config(page_title="StockX Highest Bid Tracker", layout="wide", page_icon="📈")
st.title("📈 StockX Live Bid Tracker")

# ─── SECURE API KEY ──────────────────────────────────────────────
api_key = st.secrets.get("STOCKX_API_KEY", None)
if not api_key:
    st.error("StockX API key not found. Add STOCKX_API_KEY in Settings → Secrets.")
    st.stop()

headers = {"Authorization": f"Bearer {api_key}"}

# ─── SESSION STATE ───────────────────────────────────────────────
if "tracked_bids" not in st.session_state:
    st.session_state.tracked_bids = pd.DataFrame(columns=[
        "SKU", "Size", "Added At", "Shoe Name", "Colorway",
        "Highest Bid", "Lowest Ask", "Last Sale", "# Asks",
        "Bid Change", "Last Updated"
    ])

# ─── FETCH MARKET DATA ───────────────────────────────────────────
def fetch_market_data(sku, size):
    try:
        # Search product
        r = requests.get(f"https://api.stockx.com/v2/search?q={sku}", headers=headers, timeout=10)
        if r.status_code != 200:
            return None, f"Search failed: {r.status_code} - {r.text[:200]}"
        data = r.json()
        if not data.get("products"):
            return None, "No product found for this SKU"

        product = data["products"][0]
        pid = product["id"]
        name = product["title"]
        color = product.get("colorway", "N/A")

        # Market data
        m = requests.get(f"https://api.stockx.com/v2/products/{pid}", headers=headers, timeout=10)
        if m.status_code != 200:
            return None, f"Market fetch failed: {m.status_code} - {m.text[:200]}"
        market = m.json().get("market", {})

        return {
            "name": name,
            "colorway": color,
            "highest_bid": market.get("highestBid", 0),
            "lowest_ask": market.get("lowestAsk", 0),
            "last_sale": market.get("lastSale", 0),
            "num_asks": market.get("numberOfAsks", 0)
        }, None

    except Exception as e:
        return None, str(e)

# ─── SIDEBAR CONTROLS ────────────────────────────────────────────
st.sidebar.header("Refresh Settings")
refresh_min = st.sidebar.slider("Auto-refresh every (minutes)", 1, 60, 5)
st.session_state.refresh_interval = refresh_min * 60

if st.sidebar.button("Force Refresh All"):
    st.rerun()

# ─── ADD NEW TRACKING ────────────────────────────────────────────
st.subheader("Track a New SKU + Size")
col1, col2 = st.columns(2)
with col1:
    sku = st.text_input("SKU", placeholder="e.g. HF7723-001")
with col2:
    size = st.text_input("UK Size", placeholder="e.g. 10.5")

if st.button("Add & Fetch Current Bid"):
    if sku and size:
        data, err = fetch_market_data(sku.strip(), size.strip())
        if err:
            st.error(err)
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = {
                "SKU": sku.strip(),
                "Size": size.strip(),
                "Added At": now,
                "Shoe Name": data["name"],
                "Colorway": data["colorway"],
                "Highest Bid": data["highest_bid"],
                "Lowest Ask": data["lowest_ask"],
                "Last Sale": data["last_sale"],
                "# Asks": data["num_asks"],
                "Bid Change": "—",
                "Last Updated": now
            }
            st.session_state.tracked_bids = pd.concat(
                [st.session_state.tracked_bids, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success(f"Added {sku} {size} – fetched live data")
    else:
        st.warning("Enter SKU and Size")

# ─── LIVE TABLE ──────────────────────────────────────────────────
st.subheader("Tracked Bids – Live Updates")

if not st.session_state.tracked_bids.empty:
    df = st.session_state.tracked_bids.copy()

    # Format currency
    for col in ["Highest Bid", "Lowest Ask", "Last Sale"]:
        df[col] = df[col].apply(lambda x: f"£{x:,.0f}" if x > 0 else "—")

    # Change formatting
    def format_change(x):
        if x == "—": return x
        if x > 0: return f"↑ £{x:,.0f}"
        if x < 0: return f"↓ £{abs(x):,.0f}"
        return "—"

    df["Bid Change"] = df["Bid Change"].apply(format_change)

    st.dataframe(
        df,
        column_config={
            "Bid Change": st.column_config.TextColumn("Bid Change", width="small"),
            "Last Updated": st.column_config.TextColumn("Last Updated", width="medium")
        },
        hide_index=True,
        use_container_width=True
    )

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "↓ Download CSV",
        csv,
        "stockx_bid_tracker.csv",
        "text/csv"
    )
else:
    st.info("Add SKUs above to start tracking live bids")

# ─── AUTO-REFRESH ────────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 300  # default 5 min

if time.time() - st.session_state.last_refresh >= st.session_state.refresh_interval:
    st.session_state.last_refresh = time.time()
    st.rerun()
