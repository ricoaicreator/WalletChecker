import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time

# === CONFIG ===
st.set_page_config(page_title="Rug Checker", layout="wide")
st.title("💣 Meme Coin Rug Checker")

HELIUS_API_KEY = st.secrets.get("HELIUS_API_KEY", "YOUR_API_KEY_HERE")  # Replace if local

# === SOLSCAN HOLDER API ===
def fetch_spl_holders_solscan(mint):
    url = f"https://public-api.solscan.io/token/holders?tokenAddress={mint}&limit=1000"
    headers = {"accept": "application/json"}
    try:
        res = requests.get(url, headers=headers)
        st.text(f"Solscan Status: {res.status_code}")
        st.code(res.text[:1000])

        data = res.json()
        holders = []
        for h in data:
            holders.append({
                "Wallet": h.get("owner", ""),
                "Balance": h.get("tokenAmount", {}).get("uiAmount", 0)
            })
        return holders
    except Exception as e:
        st.error("❌ Error fetching token holders from Solscan.")
        return []

# === HELIUS WALLET AGE ===
def get_wallet_age(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=1"
    try:
        res = requests.get(url)
        data = res.json()
        if isinstance(data, list) and data:
            ts = data[0]["timestamp"]
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            days = (datetime.now(timezone.utc) - dt).days
            return days, days < 1
    except:
        pass
    return "N/A", True

# === UI ===
mode = st.radio("Choose input mode:", ["SPL Token (Auto)", "Manual Wallet List"])

if mode == "SPL Token (Auto)":
    mint = st.text_input("Enter SPL Token Mint Address")
    if st.button("🔍 Analyze SPL Token"):
        if not mint:
            st.warning("Please enter a mint address.")
        else:
            st.info("Fetching token holders from Solscan...")
            holders = fetch_spl_holders_solscan(mint)
            if not holders:
                st.error("No holders found. Token might be invalid or too new.")
            else:
                df = pd.DataFrame(holders)
                for i, row in df.iterrows():
                    age, is_new = get_wallet_age(row["Wallet"])
                    df.at[i, "Wallet Age (Days)"] = age
                    df.at[i, "New Wallet (<24h)"] = is_new
                    time.sleep(0.25)
                st.success("Analysis complete!")
                st.dataframe(df)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("📥 Download CSV", csv, "spl_token_analysis.csv", "text/csv")

elif mode == "Manual Wallet List":
    st.markdown("Paste wallet addresses and balances (CSV format):")
    ex = """7Lg4egzEujYwMkXzZYCSkSbsVym1pGmZYWBiXixQ8RAQ, 2800
4Q9bq2AP4TVbtE8G6ezP4WpXqGCEcLvF5VNQcd9nMLmN, 1200"""
    raw_input = st.text_area("Wallet, Balance", value=ex, height=200)

    if st.button
