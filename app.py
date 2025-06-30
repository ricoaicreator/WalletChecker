import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone
import time
from collections import defaultdict
import plotly.express as px

# === CONFIG ===
APP_VERSION = "0.06"
st.set_page_config(page_title=f"Manual Rug Checker v{APP_VERSION}", layout="wide")
st.title(f"\U0001F4A3 Manual Wallet Rug Checker — v{APP_VERSION}")

HELIUS_API_KEY = st.secrets.get("HELIUS_API_KEY", "YOUR_API_KEY_HERE")

# System or program addresses to ignore in clustering
IGNORED_FUNDERS = {
    "11111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "pfnUxCuZcfP6yidkG3EsqyR5DTbyie3R74fGoA5oB3J"
}

# === Wallet Age Detection with debug logging
def get_wallet_age(wallet):
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions?api-key={HELIUS_API_KEY}&limit=100"
    try:
        res = requests.get(url)
        st.sidebar.write(f"[{wallet}] Status {res.status_code}")
        txs = res.json()

        if not isinstance(txs, list) or len(txs) == 0:
            st.sidebar.write(f"[{wallet}] ❌ No transactions returned")
            return "N/A", True

        timestamps = []
        for tx in txs:
            ts = tx.get("timestamp") or tx.get("blockTime")
            if ts:
                timestamps.append(ts)
                st.sidebar.write(f"[{wallet}] → {ts}")

        if not timestamps:
            st.sidebar.write(f"[{wallet}] ❌ No valid timestamps found")
            return "N/A", True

        oldest_ts = min(timestamps)
        dt = datetime.fromtimestamp(oldest_ts, tz=timezone.utc)
        days_old = (datetime.now(timezone.utc) - dt).days
        st.sidebar.write(f"[{wallet}] ✅ Oldest Age: {days_old} days")

        return days_old, days_old < 1

    except Exception as e:
        st.sidebar.write(f"[{wallet}] ❌ Error: {str(e)}")
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
                if sender and sender != wallet and sender not in IGNORED_FUNDERS:
                    funders.add(sender)
        return list(funders)
    except Exception:
        return []

# === Fetch holders from Solscan
def get_wallets_from_solscan(token_address):
    url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}&limit=1000&offset=0"
    try:
        res = requests.get(url, headers={"accept": "application/json"})
        if res.status_code != 200:
            return [], f"❌ Solscan returned status code {res.status_code}"
        data = res.json()
        return [holder["owner"] for holder in data], None
    except Exception as e:
        return [], f"❌ Error fetching from Solscan: {str(e)}"

# === UI: Paste Wallets or Token
st.markdown("### \U0001F4CB Option 1: Paste wallet addresses (one per line)")
wallet_input = st.text_area("Wallets", height=200, value="")

st.markdown("### \U0001F50E Option 2: Paste a Solscan Token URL or Address")
token_input = st.text_input("Solscan Token (e.g. https://solscan.io/token/...) or address")

hide_low = st.checkbox("🔍 Hide Low Risk Wallets")

if st.button("\U0001F6A8 Run Rug Check"):
    wallets = []
    notes = ""

    if token_input.strip():
        token_id = token_input.strip().split("/")[-1]
        wallets, err = get_wallets_from_solscan(token_id)
        if err:
            st.error(err)
            st.stop()
        st.success(f"✅ Imported {len(wallets)} holders from token {token_id}")
    else:
        raw_wallets = wallet_input.strip().splitlines()
        wallets = list(set(w.strip() for w in raw_wallets if len(w.strip()) >= 32))

    if not wallets:
        st.warning("Please provide wallet addresses or a token.")
        st.stop()

    results = []
    funder_map = defaultdict(list)
    reverse_map = defaultdict(list)
    new_wallets = 0

    with st.spinner("Analyzing wallets... this may take a few seconds..."):
        for wallet in wallets:
            age, is_new = get_wallet_age(wallet)
            funders = get_funders(wallet)

            for f in funders:
                funder_map[f].append(wallet)
                reverse_map[wallet].append(f)

            results.append({
                "Wallet": wallet,
                "Wallet Age (Days)": age,
                "New Wallet (<24h)": "✅" if is_new else "",
                "Is New Wallet": is_new,
                "Funders": ", ".join(funders)
            })

            if is_new:
                new_wallets += 1
            time.sleep(0.1)

    df = pd.DataFrame(results)

    wallet_cluster_map = {}
    funder_flag_map = defaultdict(bool)
    for funder, funded_wallets in funder_map.items():
        if len(funded_wallets) > 1:
            for w in funded_wallets:
                wallet_cluster_map[w] = f"Cluster via {funder[:6]}..."
            if funder in wallets:
                funder_flag_map[funder] = True

    df["In Cluster"] = df["Wallet"].apply(lambda w: wallet_cluster_map.get(w, ""))
    df["Is Funder"] = df["Wallet"].apply(lambda w: "✅" if funder_flag_map.get(w, False) else "")

    def risk_score(row):
        if row["Is New Wallet"] and row["In Cluster"]:
            return "High"
        elif row["Is New Wallet"] or row["In Cluster"]:
            return "Medium"
        return "Low"

    df["Risk Score"] = df.apply(risk_score, axis=1)

    st.sidebar.header("📊 Summary")
    st.sidebar.markdown(f"**Total Wallets:** {len(wallets)}")
    st.sidebar.markdown(f"**New Wallets (<24h):** {new_wallets}")
    st.sidebar.markdown(f"**Clustered Wallets:** {sum(df['In Cluster'] != '')}")
    st.sidebar.markdown(f"**Wallets That Are Funders:** {df['Is Funder'].value_counts().get('✅', 0)}")

    display_df = df.drop(columns=["Is New Wallet"])
    if hide_low:
        display_df = display_df[display_df["Risk Score"] != "Low"]

    st.success("✅ Analysis complete.")
    st.markdown("### 🧾 Results")
    st.dataframe(display_df.style
        .applymap(lambda val: "color: green; font-weight: bold" if val == "✅" else "", subset=["New Wallet (<24h)", "Is Funder"])
        .applymap(lambda val: "background-color: #ffe599" if isinstance(val, str) and val else "", subset=["In Cluster"])
        .applymap(lambda val:
                  "background-color: #ffcccc" if val == "High" else
                  ("background-color: #fff2cc" if val == "Medium" else ""),
                  subset=["Risk Score"]))

    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", csv, "manual_rug_check_v06.csv", "text/csv")
