import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time
from collections import defaultdict

# === CONFIG ===
APP_VERSION = "0.01"
st.set_page_config(page_title=f"Manual Rug Checker v{APP_VERSION}", layout="wide")
st.title(f"💣 Manual Wallet Rug Checker — v{APP_VERSION}")

HELIUS_API_KEY = st.secrets.get("HELIUS_API_KEY", "YOUR_API_KEY_HERE")

# === Wallet Age Detection (with debug printing)
def get_wallet_age(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=1"
    try:
        res = requests.get(url)
        print(f"[{wallet}] Status Code:", res.status_code)

        if res.status_code != 200:
            print(f"[{wallet}] Failed to get transactions.")
            return "N/A", True

        txs = res.json()
        if not txs or not isinstance(txs, list):
            print(f"[{wallet}] No transactions returned.")
            return "N/A", True

        tx = txs[0]
        print(f"[{wallet}] First TX:", tx)

        ts = tx.get("timestamp") or tx.get("blockTime")
        if not ts:
            print(f"[{wallet}] No timestamp/blockTime.")
            return "N/A", True

        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        days_old = (datetime.now(timezone.utc) - dt).days
        print(f"[{wallet}] Wallet is {days_old} days old.")
        return days_old, days_old < 1

    except Exception as e:
        print(f"[{wallet}] Wallet Age Error:", e)
        return "N/A", True

# === Cluster Detection
def get_funders(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=10"
    try:
        res = requests.get(url)
        data = res.json()
        funders = set()
        for tx in data:
            if tx.get("type") in ["TRANSFER", "TRANSFER_SOL"]:
                sender = tx.get("source")
                if sender and sender != wallet:
                    funders.add(sender)
        return list(funders)
    except Exception as e:
        print(f"[{wallet}] Funder Error:", e)
        return []

# === Wallet Input UI
st.markdown("### 📋 Paste wallet addresses (one per line):")
wallet_input = st.text_area("Wallets", height=200, value="""7Lg4egzEujYwMkXzZYCSkSbsVym1pGmZYWBiXixQ8RAQ
4Q9bq2AP4TVbtE8G6ezP4WpXqGCEcLvF5VNQcd9nMLmN""")

if st.button("🚨 Run Rug Check"):
    raw_wallets = wallet_input.strip().splitlines()
    wallets = list(set(w.strip() for w in raw_wallets if len(w.strip()) >= 32))

    if not wallets:
        st.warning("Please paste at least one valid wallet address.")
    else:
        results = []
        funder_map = defaultdict(list)

        st.info("Analyzing wallets... please hold tight.")
        progress = st.progress(0)

        for i, wallet in enumerate(wallets):
            age, is_new = get_wallet_age(wallet)
            funders = get_funders(wallet)

            for f in funders:
                funder_map[f].append(wallet)

            results.append({
                "Wallet": wallet,
                "Wallet Age (Days)": age,
                "New Wallet (<24h)": is_new,
                "Funders": ", ".join(funders)
            })

            progress.progress((i + 1) / len(wallets))
            time.sleep(0.2)

        df = pd.DataFrame(results)

        # Cluster labels
        wallet_cluster_map = {}
        for funder, funded_wallets in funder_map.items():
            if len(funded_wallets) > 1:
                for w in funded_wallets:
                    wallet_cluster_map[w] = f"Cluster via {funder[:6]}..."

        df["In Cluster"] = df["Wallet"].apply(lambda w: wallet_cluster_map.get(w, ""))

        # Display results
        st.success("✅ Analysis complete.")
        st.dataframe(df)

        # Download
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, "manual_rug_check.csv", "text/csv")
