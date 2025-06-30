import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time
from collections import defaultdict

# === CONFIG ===
st.set_page_config(page_title="Manual Rug Checker", layout="wide")
st.title("💣 Manual Wallet Rug Checker")

HELIUS_API_KEY = st.secrets.get("HELIUS_API_KEY", "YOUR_API_KEY_HERE")  # Replace if local

# === Wallet Age Check (uses Solana RPC passthrough) ===
def get_wallet_age(wallet):
    url = f"https://rpc.helius.xyz/?api-key={HELIUS_API_KEY}"
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [wallet, {"limit": 1}]
    }
    try:
        res = requests.post(url, json=body)
        data = res.json().get("result", [])
        if data and data[0].get("blockTime"):
            ts = data[0]["blockTime"]
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            days = (datetime.now(timezone.utc) - dt).days
            return days, days < 1
    except:
        pass
    return "N/A", True  # fallback if no result

# === Cluster Detection ===
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
    except:
        return []

# === UI ===
st.markdown("### 📋 Paste wallet addresses (one per line):")
wallet_input = st.text_area("Wallets", height=200, value="""7Lg4egzEujYwMkXzZYCSkSbsVym1pGmZYWBiXixQ8RAQ
4Q9bq2AP4TVbtE8G6ezP4WpXqGCEcLvF5VNQcd9nMLmN""")

if st.button("🚨 Run Rug Check"):
    wallets = list(set(line.strip() for line in wallet_input.strip().splitlines() if line.strip()))

    if not wallets:
        st.warning("Please paste at least one wallet address.")
    else:
        results = []
        funder_map = defaultdict(list)

        st.info("Analyzing wallets... this may take a moment.")
        progress = st.progress(0)

        for i, wallet in enumerate(wallets):
            age, is_new = get_wallet_age(wallet)
            funders = get_funders(wallet)

            # Track which wallets were funded by same sources
            for f in funders:
                funder_map[f].append(wallet)

            results.append({
                "Wallet": wallet,
                "Wallet Age (Days)": age,
                "New Wallet (<24h)": is_new,
                "Funders": ", ".join(funders)
            })

            progress.progress((i + 1) / len(wallets))
            time.sleep(0.25)

        df = pd.DataFrame(results)

        # Label clusters
        wallet_cluster_map = {}
        for funder, funded_wallets in funder_map.items():
            if len(funded_wallets) > 1:
                for w in funded_wallets:
                    wallet_cluster_map[w] = f"Cluster via {funder[:6]}..."

        df["In Cluster"] = df["Wallet"].apply(lambda w: wallet_cluster_map.get(w, ""))

        st.success("✅ Scan complete.")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, "manual_rug_check.csv", "text/csv")
