"""
App Streamlit — Screener "Inversione dopo forte ribasso" su large cap.
Grafica: sfondo bianco, card statistiche, grafici interattivi Plotly con
i livelli operativi marcati.

Deploy: Streamlit Community Cloud (gratuito).
Avvio locale: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import time

from data_fetch import (
    get_full_universe, fetch_universe, fetch_history,
    refresh_last_bar_with_live_price
)
from screener import scan_universe, DEFAULT_PARAMS
from backtest import backtest_universe, compute_stats
from charts import signal_chart, drawdown_gauge, rr_bar_chart

st.set_page_config(page_title="Screener Inversione Large Cap", layout="wide", page_icon="📈")

# ---------------------------------------------------------------------------
# STILE: sfondo bianco, card pulite, tipografia curata
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .stApp { background-color: #ffffff; }
    section[data-testid="stSidebar"] { background-color: #f9fafb; border-right: 1px solid #e5e7eb; }

    h1, h2, h3 { color: #111827; font-family: 'Segoe UI', Arial, sans-serif; }
    p, span, label, div { color: #1f2937; }

    div[data-testid="stMetric"] {
        background-color: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 14px 16px;
    }
    div[data-testid="stMetric"] label { color: #6b7280 !important; font-weight: 500; }

    .signal-card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-left: 5px solid #16a34a;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .signal-card.warn { border-left-color: #f59e0b; }
    .signal-card.watch { border-left-color: #6b7280; }

    .ticker-title { font-size: 20px; font-weight: 700; color: #111827; }
    .badge {
        display: inline-block; padding: 3px 10px; border-radius: 20px;
        font-size: 12px; font-weight: 600; margin-left: 8px;
    }
    .badge-green { background-color: #dcfce7; color: #166534; }
    .badge-amber { background-color: #fef3c7; color: #92400e; }
    .badge-gray { background-color: #f3f4f6; color: #4b5563; }

    .stButton > button {
        background-color: #111827; color: white; border-radius: 8px; border: none;
        font-weight: 600; padding: 10px 20px;
    }
    .stButton > button:hover { background-color: #374151; }

    .stTabs [data-baseweb="tab"] { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

st.title("📈 Screener Inversione dopo forte ribasso — Large Cap")
st.caption(
    "FTSE MIB · Nasdaq 100 · S&P 500 — titoli scesi pesantemente dai massimi, con discesa in "
    "decelerazione, base di consolidamento vicino al POC, rottura confermata da volume. "
    "Solo segnali con Risk:Reward ≥ soglia minima."
)

# --- Sidebar ---
st.sidebar.header("🌍 Universo")
if "universe_cache" not in st.session_state:
    st.session_state.universe_cache = None

if st.sidebar.button("🔄 Aggiorna liste indici"):
    with st.spinner("Scarico componenti FTSE MIB / Nasdaq 100 / S&P 500..."):
        st.session_state.universe_cache = get_full_universe()

if st.session_state.universe_cache:
    counts = {k: len(v) for k, v in st.session_state.universe_cache.items()}
    st.sidebar.caption(f"MIB: {counts.get('FTSE MIB',0)} · N100: {counts.get('Nasdaq 100',0)} · SP500: {counts.get('S&P 500',0)}")

indices_choice = st.sidebar.multiselect(
    "Indici da scansionare",
    ["FTSE MIB", "Nasdaq 100", "S&P 500"],
    default=["FTSE MIB", "Nasdaq 100", "S&P 500"],
)

st.sidebar.header("⚙️ Parametri strategia")
params = dict(DEFAULT_PARAMS)
params["min_drawdown_pct"] = st.sidebar.slider("Drawdown minimo dal massimo (%)", 20, 70, int(DEFAULT_PARAMS["min_drawdown_pct"]))
params["max_base_range_pct"] = st.sidebar.slider("Ampiezza massima base (%)", 5, 30, int(DEFAULT_PARAMS["max_base_range_pct"]))
params["vol_ratio_min"] = st.sidebar.slider("Volume minimo rottura (x media 20gg)", 1.0, 3.0, DEFAULT_PARAMS["vol_ratio_min"], 0.1)
params["rr_min"] = st.sidebar.slider("R:R minimo richiesto", 1.0, 6.0, DEFAULT_PARAMS["rr_min"], 0.5)

use_live_price = st.sidebar.checkbox("Prezzo quasi real-time", value=True,
                                       help="Sostituisce l'ultima chiusura con l'ultimo prezzo disponibile (ritardo tipico di pochi minuti).")

st.sidebar.divider()
st.sidebar.caption("⚠️ Segnali generati automaticamente. Non è consulenza finanziaria.")


def badge(stato: str) -> str:
    if stato == "CONFERMATO":
        return '<span class="badge badge-green">✅ CONFERMATO</span>'
    if "R:R insufficiente" in stato:
        return '<span class="badge badge-amber">⚠️ R:R INSUFFICIENTE</span>'
    if "SENZA VOLUME" in stato:
        return '<span class="badge badge-amber">⚠️ VOLUME DEBOLE</span>'
    return f'<span class="badge badge-gray">👀 {stato}</span>'


def render_signal_card(row: dict, df=None):
    css_class = "signal-card"
    if row["stato"] != "CONFERMATO":
        css_class += " warn" if "R:R" in row["stato"] or "VOLUME" in row["stato"] else " watch"

    st.markdown(f"""
    <div class="{css_class}">
        <span class="ticker-title">{row['ticker']}</span> {badge(row['stato'])}
        <div style="margin-top:8px; color:#6b7280; font-size:14px;">
            Prezzo: <b>{row['prezzo']}</b> &nbsp;|&nbsp;
            Drawdown: <b>-{row['drawdown_pct']}%</b> &nbsp;|&nbsp;
            POC: <b>{row['poc']}</b>
            {f" &nbsp;|&nbsp; Base: <b>{row['base_range_pct']}%</b>" if pd.notna(row.get('base_range_pct')) else ""}
            {f" &nbsp;|&nbsp; Volume: <b>{row['volume_ratio']}x</b>" if pd.notna(row.get('volume_ratio')) else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if row["stato"].startswith("CONFERMATO") and pd.notna(row.get("entry")):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Entry", row["entry"])
        c2.metric("Stop", row["stop"])
        c3.metric("TP1", row.get("tp1", "—"))
        c4.metric("TP2", row.get("tp2", "—"))
        c5.metric("R:R (TP2)", row.get("rr_tp2", "—"))
        rs = row.get("forza_relativa")
        c6.metric("Forza relativa", f"{rs:+.1f}%" if pd.notna(rs) else "—")

        extra_cols = st.columns(3)
        d52 = row.get("distanza_minimo_52w")
        gb = row.get("giorni_da_rottura")
        extra_cols[0].caption(f"📏 Distanza da minimo 52 sett.: **{d52:+.1f}%**" if pd.notna(d52) else "")
        extra_cols[1].caption(f"🕒 Giorni dalla rottura: **{gb}**" if pd.notna(gb) and gb >= 0 else "")
        extra_cols[2].caption(row.get("note", ""))

        if df is not None:
            with st.expander("📊 Grafico dettagliato", expanded=False):
                st.plotly_chart(signal_chart(df, row), use_container_width=True)


tab1, tab2 = st.tabs(["🔍 Screener live", "📊 Backtest"])

with tab1:
    if st.button("🔎 Aggiorna scansione", type="primary"):
        if not st.session_state.universe_cache:
            with st.spinner("Prima scansione: scarico le liste degli indici..."):
                st.session_state.universe_cache = get_full_universe()

        tickers = []
        for idx_name in indices_choice:
            tickers += st.session_state.universe_cache.get(idx_name, [])
        tickers = list(dict.fromkeys(tickers))

        if not tickers:
            st.error("Nessun ticker recuperato. Riprova ad 'Aggiornare liste indici'.")
        else:
            st.info(f"Scansione di {len(tickers)} titoli in corso...")
            progress = st.progress(0)
            price_data = {}
            for i, t in enumerate(tickers):
                df = fetch_history(t, period="2y")
                if df is not None and len(df) > 260:
                    if use_live_price:
                        df = refresh_last_bar_with_live_price(df, t)
                    price_data[t] = df
                progress.progress((i + 1) / len(tickers))
            progress.empty()

            results = scan_universe(price_data, params)
            st.session_state.last_results = results
            st.session_state.last_price_data = price_data

    results = st.session_state.get("last_results")
    price_data = st.session_state.get("last_price_data", {})

    if results is not None and not results.empty:
        confermati = results[results["stato"] == "CONFERMATO"]
        altri = results[results["stato"] != "CONFERMATO"]

        st.subheader("📊 Riepilogo scansione")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Titoli scansionati", len(price_data))
        m2.metric("Segnali CONFERMATI", len(confermati))
        m3.metric("In monitoraggio", len(altri))
        m4.metric("R:R medio confermati", f"{confermati['rr_tp2'].dropna().mean():.2f}" if not confermati.empty and confermati['rr_tp2'].notna().any() else "—")

        if not confermati.empty:
            st.plotly_chart(rr_bar_chart(confermati), use_container_width=True)

            st.subheader("🎯 Segnali confermati")
            for _, row in confermati.iterrows():
                render_signal_card(row.to_dict(), df=price_data.get(row["ticker"]))
        else:
            st.warning("Nessun segnale ha raggiunto tutti i criteri (incluso R:R minimo) in questa scansione.")

        if not altri.empty:
            with st.expander(f"👀 Titoli in monitoraggio ({len(altri)})", expanded=False):
                for _, row in altri.iterrows():
                    render_signal_card(row.to_dict())
    elif results is not None:
        st.info("Nessun segnale trovato con i criteri attuali su questo universo.")

with tab2:
    st.subheader("Backtest storico della strategia")
    st.caption("Verifica l'expectancy della strategia PRIMA di usarla con capitale reale.")

    bt_indices = st.multiselect("Indici per il backtest", ["FTSE MIB", "Nasdaq 100", "S&P 500"], default=["FTSE MIB"])
    bt_period = st.selectbox("Periodo storico", ["2y", "3y", "5y"], index=1)

    if st.button("▶️ Esegui backtest"):
        if not st.session_state.universe_cache:
            with st.spinner("Scarico le liste degli indici..."):
                st.session_state.universe_cache = get_full_universe()

        bt_tickers = []
        for idx_name in bt_indices:
            bt_tickers += st.session_state.universe_cache.get(idx_name, [])
        bt_tickers = list(dict.fromkeys(bt_tickers))

        with st.spinner(f"Scarico dati storici per {len(bt_tickers)} titoli ed eseguo il backtest..."):
            bt_price_data = fetch_universe(bt_tickers, period=bt_period)
            trades = backtest_universe(bt_price_data, params)
            stats = compute_stats(trades)

        if stats.get("n_trades", 0) == 0:
            st.warning("Nessun trade generato nel periodo selezionato (normale: strategia molto selettiva).")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("N. trade", stats["n_trades"])
            c2.metric("Win rate", f"{stats['win_rate_pct']}%")
            c3.metric("Expectancy media", f"{stats['expectancy_pct']}%")
            c4.metric("Avg win / Avg loss", f"{stats['avg_win_pct']}% / {stats['avg_loss_pct']}%")

            st.bar_chart(pd.Series(stats["outcome_breakdown"]))
            st.dataframe(trades, use_container_width=True)

            csv = trades.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Scarica trade log (CSV)", csv, "backtest_trades.csv", "text/csv")
