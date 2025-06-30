import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time

# === CONFIG ===
st.set_page_config(page_title="Rug Checker", layout="wide")
st.title("💣 Meme Coin Rug Checker")

HELIUS_API_KEY = st.secrets.get("HELIUS_API_KEY", "YOUR_API_KEY_HERE")  # fallback for local

RPC_URL = "https://api.mainnet-beta.solana.com"

# === HELPERS ===

def get_wallet_age(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=1"
    try:
        response = requests.get(url)
        data = response.json()
        if isinstance(data, list) and data:
            ts = data[0]["timestamp"]
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            days = (datetime.now(timezone.utc) - dt).days
            return days, days < 1
    except:
        pass
    return "N/A", True

def fetch_spl_holders(mint):
    headers = {"Content-Type": "application/json"}
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getParsedProgramAccounts",
        "params": [
            "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
            {
                "encoding": "jsonParsed",
                "filters": [
                    {"dataSize": 165},
                    {"memcmp": {"offset": 0, "bytes": mint}}
                ]
            }
        ]
    }
    res = requests.post(RPC_URL, json=body, headers=headers)

    # 🔍 Debug output here:
    st.text(f"Status: {res.status_code}")
    st.code(res.text[:1000])
    
    try:
        data = res.json().get("result", [])
        holders = []
        for acct in data:
            info = acct["account"]["data"]["parsed"]["info"]
            owner = info["owner"]
            amount = float(info["tokenAmount"]["uiAmount"])
            if amount > 0:
                holders.append({"Wallet": owner, "Balance": amount})
        return holders
    except:
        return []

# === UI ===

mode = st.radio("Choose input mode:", ["SPL Token (Auto)", "Manual Wallet List"])

if mode == "SPL Token (Auto)":
    mint = st.text_input("Enter SPL Token Mint Address")
    if st.button("🔍 Analyze SPL Token"):
        if not mint:
            st.warning("Please enter a mint address.")
        else:
            st.info("Fetching token holders from Solana...")
            holders = fetch_spl_holders(mint)
            if not holders:
                st.error("No holders found. Token might be invalid or empty.")
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

    if st.button("🧠 Analyze Wallet List"):
        wallets = []
        for line in raw_input.strip().splitlines():
            try:
                addr, bal = line.strip().split(",")
                wallets.append({"Wallet": addr.strip(), "Balance": float(bal.strip())})
            except:
                continue

        df = pd.DataFrame(wallets)
        for i, row in df.iterrows():
            age, is_new = get_wallet_age(row["Wallet"])
            df.at[i, "Wallet Age (Days)"] = age
            df.at[i, "New Wallet (<24h)"] = is_new
            time.sleep(0.25)
        st.success("Manual analysis complete!")
        st.dataframe(df)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, "manual_wallet_analysis.csv", "text/csv")
