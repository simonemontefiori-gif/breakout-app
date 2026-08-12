"""
App Streamlit - Screener Breakout con filtri statistici (POC + volume + regime).
Deploy consigliato: Streamlit Community Cloud (gratuito), stesso hosting già
usato per dashboard_sfida.py.

Avvio locale: streamlit run app.py
"""

import streamlit as st
import pandas as pd

from data_fetch import fetch_universe, FTSE_MIB_SAMPLE
from screener import scan_universe, DEFAULT_PARAMS
from backtest import backtest_universe, compute_stats

st.set_page_config(page_title="Screener Breakout POC", layout="wide")
st.title("📈 Screener Breakout con filtri statistici")

st.sidebar.header("Universo")
universe_choice = st.sidebar.selectbox(
    "Seleziona universo (esempio FTSE MIB incluso — aggiungi liste S&P500/Nasdaq100/Stoxx600)",
    ["FTSE MIB (esempio)", "Lista personalizzata"]
)

if universe_choice == "Lista personalizzata":
    custom = st.sidebar.text_area("Ticker separati da virgola (formato Yahoo Finance)", "PRY.MI, STM.MI, G.MI")
    tickers = [t.strip() for t in custom.split(",") if t.strip()]
else:
    tickers = FTSE_MIB_SAMPLE

st.sidebar.header("Parametri criteri")
params = dict(DEFAULT_PARAMS)
params["vol_ratio_min"] = st.sidebar.slider("Volume minimo (x media 20gg)", 1.0, 3.0, DEFAULT_PARAMS["vol_ratio_min"], 0.1)
params["adx_min"] = st.sidebar.slider("ADX minimo", 10, 40, DEFAULT_PARAMS["adx_min"])
params["rr_tp2_min"] = st.sidebar.slider("R:R minimo su TP2", 1.0, 3.0, DEFAULT_PARAMS["rr_tp2_min"], 0.1)

tab1, tab2 = st.tabs(["🔍 Screener live", "📊 Backtest"])

with tab1:
    st.subheader("Segnali attuali")
    if st.button("Aggiorna scansione", type="primary"):
        with st.spinner("Recupero dati e applico i criteri..."):
            price_data = fetch_universe(tickers, period="1y")
            results = scan_universe(price_data, params)
        if results.empty:
            st.info("Nessun segnale trovato con i criteri attuali.")
        else:
            confermati = results[results["stato"] == "CONFERMATO"]
            if not confermati.empty:
                st.success(f"{len(confermati)} segnale/i CONFERMATO")
                st.dataframe(confermati, use_container_width=True)
            altri = results[results["stato"] != "CONFERMATO"]
            if not altri.empty:
                st.subheader("Monitoraggio (non ancora confermati)")
                st.dataframe(altri, use_container_width=True)

with tab2:
    st.subheader("Backtest storico dei criteri")
    st.caption(
        "Verifica se i filtri (volume, ADX, struttura, R:R minimo) portano "
        "l'expectancy sopra zero PRIMA di usare il sistema con capitale reale."
    )
    bt_period = st.selectbox("Periodo storico", ["1y", "2y", "3y", "5y"], index=1)

    if st.button("Esegui backtest"):
        with st.spinner("Scarico dati storici ed eseguo il backtest (può richiedere qualche minuto)..."):
            price_data = fetch_universe(tickers, period=bt_period)
            trades = backtest_universe(price_data, params)
            stats = compute_stats(trades)

        if stats.get("n_trades", 0) == 0:
            st.warning("Nessun trade generato nel periodo selezionato con questi criteri.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("N. trade", stats["n_trades"])
            c2.metric("Win rate", f"{stats['win_rate_pct']}%")
            c3.metric("Expectancy media", f"{stats['expectancy_pct']}%")
            c4.metric("Avg win / Avg loss", f"{stats['avg_win_pct']}% / {stats['avg_loss_pct']}%")

            st.write("Distribuzione esiti:", stats["outcome_breakdown"])
            st.dataframe(trades, use_container_width=True)

            csv = trades.to_csv(index=False).encode("utf-8")
            st.download_button("Scarica trade log (CSV)", csv, "backtest_trades.csv", "text/csv")

st.sidebar.divider()
st.sidebar.caption(
    "⚠️ Segnali generati automaticamente su base statistica. "
    "Non costituiscono consulenza finanziaria. Esegui sempre il backtest "
    "prima di operare con capitale reale."
)
