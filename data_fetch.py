"""
Recupero dati storici OHLCV via yfinance.
Include liste ticker di base per i 4 universi (da espandere/aggiornare periodicamente).
"""

import yfinance as yf
import pandas as pd
import time


def fetch_history(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Scarica lo storico prezzi per un singolo ticker."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        if df.empty:
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        return df
    except Exception as e:
        print(f"Errore fetch {ticker}: {e}")
        return None


def fetch_universe(tickers: list, period: str = "1y", interval: str = "1d",
                    pause: float = 0.2) -> dict:
    """
    Scarica lo storico per una lista di ticker.
    `pause` evita rate-limiting eccessivo su yfinance.
    """
    data = {}
    for t in tickers:
        df = fetch_history(t, period=period, interval=interval)
        if df is not None and len(df) > 30:
            data[t] = df
        time.sleep(pause)
    return data


# Esempi di liste ticker — da sostituire con il pull ufficiale
# (es. CSV holdings ETF, o Wikipedia per componenti indici) come già discusso
# per l'analisi look-through delle tue ETF.

FTSE_MIB_SAMPLE = [
    "PRY.MI", "STM.MI", "G.MI", "FCT.MI", "AMP.MI", "ENI.MI", "ISP.MI",
    "UCG.MI", "ENEL.MI", "STLAM.MI", "TIT.MI", "LDO.MI", "MB.MI", "RACE.MI",
]

# Per Nasdaq 100 / S&P 500 / Stoxx 600 conviene scaricare la lista aggiornata
# da fonte ufficiale (es. Wikipedia per S&P/Nasdaq, o CSV holdings ETF) e
# passarla come lista di ticker a fetch_universe().
