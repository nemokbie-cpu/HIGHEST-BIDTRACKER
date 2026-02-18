import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time

st.set_page_config(page_title="StockX Bid Tracker", layout="wide", page_icon="📈")
st.title("StockX Highest Bid Tracker")

# ─── SECURE API KEY ──────────────────────────────────────────────
api_key = st.secrets.get("STOCKX_API_KEY", None)
if not api_key:
    st.error("StockX API key not found. Add STOCKX_API_KEY in Settings → Secrets.")
    st.stop()

headers = {"Authorization": f"Bearer {api_key}"}

# ─── SESSION STATE ───────────────────────────────────────────────
if "tracked_items" not in st.session_state:
    st.session_state.tracked_items = pd.DataFrame(columns=[
        "SKU", "Size", "Added At", "Shoe Name", "Colorway",
        "Current Highest Bid", "Lowest Ask", "Last Sale", "# Asks",
        "Change", "Last Updated"
    ])

if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 300  # seconds

# ─── FETCH FUNCTION ──────────────────────────────────────────────
def fetch_bid_data(sku, size):
    try:
        # Search product
        r = requests.get(f"https://api.stockx.com/v2/search?q={sku}", headers=headers, timeout=8)
        if r.status_code != 200:
            return None, f"Search failed: {r.status_code}"
        data = r.json()
        if not data.get("products"):
            return None, "No product found"

        product = data["products"][0]
        pid = product["id"]
        name = product["title"]
        color = product.get("colorway", "N/A")

        # Market data
        m = requests.get(f"https://api.stockx.com/v2/products/{pid}", headers=headers, timeout=8)
        if m.status_code != 200:
            return None, f"Market failed: {m.status_code}"
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
st.sidebar.header("Controls")
refresh_min = st.sidebar.slider("Auto-refresh every (minutes)", 1, 30, 5)
st.session_state.refresh_interval = refresh_min * 60

if st.sidebar.button("Refresh All Now"):
    st.rerun()

# ─── ADD NEW ITEM ────────────────────────────────────────────────
st.subheader("Track New SKU + Size")
col1, col2 = st.columns(2)
with col1:
    sku_input = st.text_input("SKU", placeholder="e.g. HF7723-001")
with col2:
    size_input = st.text_input("UK Size", placeholder="e.g. 10.5")

if st.button("Add & Fetch Bid"):
    if sku_input and size_input:
        data, err = fetch_bid_data(sku_input.strip(), size_input.strip())
        if err:
            st.error(err)
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = {
                "SKU": sku_input.strip(),
                "Size": size_input.strip(),
                "Added At": now,
                "Shoe Name": data["name"],
                "Colorway": data["colorway"],
                "Current Highest Bid": data["highest_bid"],
                "Lowest Ask": data["lowest_ask"],
                "Last Sale": data["last_sale"],
                "# Asks": data["num_asks"],
                "Change": "—",
                "Last Updated": now
            }
            st.session_state.tracked_items = pd.concat(
                [st.session_state.tracked_items, pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success(f"Added {sku_input} {size_input}")
    else:
        st.warning("Enter SKU and Size")

# ─── LIVE TABLE ──────────────────────────────────────────────────
st.subheader("Tracked Items – Live Bids")

if not st.session_state.tracked_items.empty:
    df = st.session_state.tracked_items.copy()

    # Format currency
    for col in ["Current Highest Bid", "Lowest Ask", "Last Sale"]:
        df[col] = df[col].apply(lambda x: f"£{x:,.0f}" if x > 0 else "—")

    # Show table
    st.dataframe(
        df,
        column_config={
            "Change": st.column_config.TextColumn("Change", width="small"),
            "Added At": st.column_config.TextColumn("Added", width="medium"),
            "Last Updated": st.column_config.TextColumn("Updated", width="medium")
        },
        hide_index=True,
        use_container_width=True
    )

    # Export
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "↓ Download CSV",
        csv,
        "stockx_bid_tracker.csv",
        "text/csv"
    )
else:
    st.info("Add SKUs above to start tracking")

# ─── AUTO-REFRESH LOGIC ──────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

if time.time() - st.session_state.last_refresh >= st.session_state.refresh_interval:
    st.session_state.last_refresh = time.time()
    st.rerun()
