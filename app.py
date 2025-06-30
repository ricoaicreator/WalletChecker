import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time

# === CONFIGURATION ===
st.set_page_config(page_title="Pump.fun Rug Checker", layout="wide")
st.title("💣 Pump.fun Rug Checker")

# Pull Helius API key from Streamlit secrets
HELIUS_API_KEY = st.secrets.get("HELIUS_API_KEY", "YOUR_API_KEY_HERE")  # fallback for local

# === Functions ===

def fetch_pumpfun_holders(mint):
    url = f"https://pump.fun/api/tokens/{mint}/holders"
    try:
        response = requests.get(url)
        data = response.json()
        return [{"Wallet": h["buyer"], "Balance": h["balance"]} for h in data]
    except:
        return []

def get_wallet_age(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=1"
    try:
        response = requests.get(url)
        data = response.json()
        if isinstance(data, list) and data:
            ts = data[0]["timestamp"]
            first_tx = datetime.fromtimestamp(ts, tz=timezone.utc)
            age_days = (datetime.now(timezone.utc) - first_tx).days
            return age_days, age_days < 1
    except:
        pass
    return "N/A", True

# === UI ===

mint = st.text_input("Paste a pump.fun mint address:")

if st.button("🧠 Analyze Token"):
    if not mint:
        st.warning("Please enter a mint address.")
    else:
        st.info("Fetching wallet holders from pump.fun...")
        holders = fetch_pumpfun_holders(mint)

        if not holders:
            st.error("No holders found. Token might be too new or invalid.")
        else:
            st.success(f"Found {len(holders)} holders. Checking wallet ages...")

            df = pd.DataFrame(holders)
            for i, row in df.iterrows():
                age, is_new = get_wallet_age(row["Wallet"])
                df.at[i, "Wallet Age (Days)"] = age
                df.at[i, "New Wallet (<24h)"] = is_new
                time.sleep(0.25)

            st.success("Done!")
            st.dataframe(df)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", csv, "wallet_analysis.csv", "text/csv")
