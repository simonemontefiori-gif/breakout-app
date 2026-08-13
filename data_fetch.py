"""
Recupero dati storici OHLCV via yfinance, e liste componenti degli indici
(FTSE MIB, Nasdaq 100, S&P 500) scaricate dinamicamente da Wikipedia —
così l'universo scansionato è sempre aggiornato senza dover mantenere
manualmente le liste ticker.
"""

import yfinance as yf
import pandas as pd
import time


# ---------------------------------------------------------------------------
# Liste componenti indici (scaricate live da Wikipedia — richiede connessione
# internet, non funziona nel sandbox di sviluppo ma funziona regolarmente
# sul tuo computer / su Streamlit Cloud).
# ---------------------------------------------------------------------------

def fetch_sp500_tickers() -> list:
    """Scarica la lista aggiornata dei componenti S&P 500 da Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    tickers = df["Symbol"].astype(str).str.strip().tolist()
    # yfinance vuole il trattino al posto del punto per titoli come BRK.B -> BRK-B
    tickers = [t.replace(".", "-") for t in tickers]
    return tickers


def fetch_nasdaq100_tickers() -> list:
    """Scarica la lista aggiornata dei componenti Nasdaq 100 da Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(url)
    # La tabella dei componenti di solito ha una colonna 'Ticker' o 'Symbol'
    for t in tables:
        cols = [c.lower() for c in t.columns.astype(str)]
        if "ticker" in cols or "symbol" in cols:
            col_name = t.columns[cols.index("ticker")] if "ticker" in cols else t.columns[cols.index("symbol")]
            tickers = t[col_name].astype(str).str.strip().tolist()
            return [tk.replace(".", "-") for tk in tickers]
    return []


def fetch_ftsemib_tickers() -> list:
    """Scarica la lista aggiornata dei componenti FTSE MIB da Wikipedia (suffisso .MI per yfinance)."""
    url = "https://en.wikipedia.org/wiki/FTSE_MIB"
    tables = pd.read_html(url)
    for t in tables:
        cols = [c.lower() for c in t.columns.astype(str)]
        if "ticker" in cols or "symbol" in cols:
            col_name = t.columns[cols.index("ticker")] if "ticker" in cols else t.columns[cols.index("symbol")]
            tickers = t[col_name].astype(str).str.strip().tolist()
            return [f"{tk}.MI" if not tk.endswith(".MI") else tk for tk in tickers]
    return []


def get_full_universe() -> dict:
    """
    Ritorna un dizionario {nome_indice: lista_ticker} scaricando tutte e tre
    le liste. Se una fonte fallisce (es. Wikipedia cambia struttura pagina),
    quell'indice risulta vuoto ma gli altri proseguono normalmente.
    """
    universe = {}
    for name, fetch_fn in [
        ("FTSE MIB", fetch_ftsemib_tickers),
        ("Nasdaq 100", fetch_nasdaq100_tickers),
        ("S&P 500", fetch_sp500_tickers),
    ]:
        try:
            tickers = fetch_fn()
            universe[name] = tickers
        except Exception as e:
            print(f"Errore recupero lista {name}: {e}")
            universe[name] = []
    return universe


# ---------------------------------------------------------------------------
# Recupero storico prezzi e prezzo corrente (quasi real-time)
# ---------------------------------------------------------------------------

def fetch_history(ticker: str, period: str = "2y", interval: str = "1d"):
    """Scarica lo storico prezzi per un singolo ticker (usato per pattern/POC/drawdown)."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        if df.empty:
            return None
        return df[["Open", "High", "Low", "Close", "Volume"]].copy()
    except Exception as e:
        print(f"Errore fetch storico {ticker}: {e}")
        return None


def fetch_universe(tickers: list, period: str = "2y", interval: str = "1d",
                    pause: float = 0.15) -> dict:
    """Scarica lo storico per una lista di ticker, con pausa per evitare rate-limiting."""
    data = {}
    for t in tickers:
        df = fetch_history(t, period=period, interval=interval)
        if df is not None and len(df) > 30:
            data[t] = df
        time.sleep(pause)
    return data


def get_live_price(ticker: str) -> float:
    """
    Ritorna il prezzo più recente disponibile (quasi real-time, con il ritardo
    tipico dei dati gratuiti — di norma pochi minuti in orario di mercato aperto).
    Usa fast_info che interroga l'ultimo prezzo scambiato.
    """
    try:
        info = yf.Ticker(ticker).fast_info
        return float(info["last_price"])
    except Exception:
        try:
            df = yf.Ticker(ticker).history(period="1d", interval="1m")
            if not df.empty:
                return float(df["Close"].iloc[-1])
        except Exception as e:
            print(f"Errore prezzo live {ticker}: {e}")
    return None


def refresh_last_bar_with_live_price(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Sostituisce il prezzo di chiusura dell'ultima riga dello storico giornaliero
    con il prezzo live più recente, così lo screener valuta condizioni aggiornate
    anche durante la sessione di mercato, non solo sulla chiusura del giorno prima.
    """
    live_price = get_live_price(ticker)
    if live_price is None or df is None or df.empty:
        return df
    df = df.copy()
    df.iloc[-1, df.columns.get_loc("Close")] = live_price
    df.iloc[-1, df.columns.get_loc("High")] = max(df["High"].iloc[-1], live_price)
    df.iloc[-1, df.columns.get_loc("Low")] = min(df["Low"].iloc[-1], live_price)
    return df
