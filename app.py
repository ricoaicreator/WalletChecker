import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time

# === SETTINGS ===
HELIUS_API_KEY = "0543b724-a39c-4ee3-8516-ea18f806b612"

st.set_page_config(page_title="Pump.fun Scam Scanner", layout="wide")
st.title("💣 Pump.fun Meme Coin Wallet Scanner")

# === User Input Section ===
st.markdown("Paste wallet data from pump.fun or another source:")
example = """wallet1, 1000
wallet2, 500
wallet3, 250"""
raw_input = st.text_area("Wallet Address, Balance", value=example, height=200)

# Parse input
wallet_data = []
for line in raw_input.strip().splitlines():
    try:
        addr, bal = line.strip().split(",")
        wallet_data.append({"Wallet": addr.strip(), "Balance": float(bal.strip())})
    except:
        continue

df = pd.DataFrame(wallet_data)

# === Wallet Age Lookup ===
def get_wallet_age(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=1"
    try:
        response = requests.get(url)
        data = response.json()
        if isinstance(data, list) and data:
            ts = data[0]["timestamp"]
            first_tx_time = datetime.fromtimestamp(ts, tz=timezone.utc)
            days_old = (datetime.now(timezone.utc) - first_tx_time).days
            return days_old, days_old < 1
    except:
        pass
    return "N/A", True

if st.button("🔍 Analyze Wallets"):
    st.write("Checking wallet ages...")
    ages = []
    for i, row in df.iterrows():
        age, is_new = get_wallet_age(row["Wallet"])
        df.at[i, "Wallet Age (Days)"] = age
        df.at[i, "New Wallet (<24h)"] = is_new
        time.sleep(0.2)

    st.success("Analysis complete!")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", csv, "wallet_analysis.csv", "text/csv")
