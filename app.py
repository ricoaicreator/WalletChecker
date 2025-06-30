import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time
from collections import defaultdict
import plotly.express as px

# === CONFIG ===
APP_VERSION = "0.02"
st.set_page_config(page_title=f"Manual Rug Checker v{APP_VERSION}", layout="wide")
st.title(f"\U0001F4A3 Manual Wallet Rug Checker — v{APP_VERSION}")

HELIUS_API_KEY = st.secrets.get("HELIUS_API_KEY", "YOUR_API_KEY_HERE")

# === Wallet Age Detection (with debug printing)
def get_wallet_age(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=1"
    try:
        res = requests.get(url)
        txs = res.json()

        if not txs or not isinstance(txs, list):
            return "N/A", True

        tx = txs[0]
        ts = tx.get("timestamp") or tx.get("blockTime")
        if not ts:
            return "N/A", True

        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        days_old = (datetime.now(timezone.utc) - dt).days
        return days_old, days_old < 1

    except Exception:
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
    except Exception:
        return []

# === Wallet Input UI
st.markdown("### \U0001F4CB Paste wallet addresses (one per line):")
wallet_input = st.text_area("Wallets", height=200, value="""7Lg4egzEujYwMkXzZYCSkSbsVym1pGmZYWBiXixQ8RAQ
4Q9bq2AP4TVbtE8G6ezP4WpXqGCEcLvF5VNQcd9nMLmN""")

if st.button("\U0001F6A8 Run Rug Check"):
    raw_wallets = wallet_input.strip().splitlines()
    wallets = list(set(w.strip() for w in raw_wallets if len(w.strip()) >= 32))

    if not wallets:
        st.warning("Please paste at least one valid wallet address.")
    else:
        results = []
        funder_map = defaultdict(list)
        new_wallets = 0

        with st.spinner("Analyzing wallets... this may take a few seconds..."):
            for wallet in wallets:
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

                if is_new:
                    new_wallets += 1
                time.sleep(0.1)

        df = pd.DataFrame(results)

        wallet_cluster_map = {}
        for funder, funded_wallets in funder_map.items():
            if len(funded_wallets) > 1:
                for w in funded_wallets:
                    wallet_cluster_map[w] = f"Cluster via {funder[:6]}..."

        df["In Cluster"] = df["Wallet"].apply(lambda w: wallet_cluster_map.get(w, ""))

        def risk_score(row):
            if row["New Wallet (<24h)"] and row["In Cluster"]:
                return "High"
            elif row["New Wallet (<24h)"] or row["In Cluster"]:
                return "Medium"
            return "Low"

        df["Risk Score"] = df.apply(risk_score, axis=1)

        # Display summary sidebar
        st.sidebar.header("📊 Summary")
        st.sidebar.markdown(f"**Total Wallets:** {len(wallets)}")
        st.sidebar.markdown(f"**New Wallets (<24h):** {new_wallets}")
        st.sidebar.markdown(f"**Clustered Wallets:** {sum(df['In Cluster'] != '')}")

        # Pie chart
        pie_data = pd.DataFrame({
            "Type": ["New", "Old"],
            "Count": [new_wallets, len(wallets) - new_wallets]
        })
        fig = px.pie(pie_data, values="Count", names="Type", title="New vs Old Wallets")
        st.plotly_chart(fig, use_container_width=True)

        # Display results with tooltips
        st.success("✅ Analysis complete.")
        st.markdown("### 🧾 Results")
        st.dataframe(df.style.applymap(
            lambda val: "background-color: #ffcccc" if val is True else "",
            subset=["New Wallet (<24h)"]
        ).applymap(
            lambda val: "background-color: #ffe599" if isinstance(val, str) and val else "",
            subset=["In Cluster"]
        ).applymap(
            lambda val: "color: red; font-weight: bold" if val == "High" else ("color: orange" if val == "Medium" else "color: green"),
            subset=["Risk Score"]
        ))

        # CSV Export
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", csv, "manual_rug_check_v02.csv", "text/csv")
