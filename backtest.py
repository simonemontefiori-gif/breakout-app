"""
Motore di backtest: simula l'applicazione dei criteri di screener.py
su dati storici, per misurare win rate ed expectancy PRIMA di usare
il sistema con capitale reale (vedi sezione 6 della spec).
"""

import numpy as np
import pandas as pd
from screener import evaluate_ticker, DEFAULT_PARAMS


def backtest_ticker(ticker: str, df: pd.DataFrame, params: dict = None,
                     min_history: int = 100, max_hold_days: int = 60) -> pd.DataFrame:
    """
    Scorre la storia di un ticker giorno per giorno, generando segnali
    CONFERMATO come se lo screener girasse ogni giorno, e simula l'esito
    (stop colpito, TP1, TP2, o chiusura per timeout).

    Ritorna un DataFrame con una riga per ogni trade simulato.
    """
    params = {**DEFAULT_PARAMS, **(params or {})}
    trades = []

    for i in range(min_history, len(df) - 1):
        window = df.iloc[:i + 1]
        sig = evaluate_ticker(ticker, window, params)

        if sig is None or not sig.stato.startswith("CONFERMATO") or sig.stato.endswith("insufficiente)"):
            continue
        if sig.entry is None or sig.stop is None:
            continue

        entry, stop, tp1, tp2 = sig.entry, sig.stop, sig.tp1, sig.tp2
        entry_date = df.index[i]

        # Simula l'esito nei giorni successivi
        future = df.iloc[i + 1: i + 1 + max_hold_days]
        outcome, exit_price, exit_date, days_held = "TIMEOUT", None, None, None

        for j, (date, row) in enumerate(future.iterrows()):
            if row["Low"] <= stop:
                outcome, exit_price, exit_date, days_held = "STOP", stop, date, j + 1
                break
            if tp2 and row["High"] >= tp2:
                outcome, exit_price, exit_date, days_held = "TP2", tp2, date, j + 1
                break
            if tp1 and row["High"] >= tp1:
                outcome, exit_price, exit_date, days_held = "TP1", tp1, date, j + 1
                break

        if exit_price is None and len(future) > 0:
            exit_price = future["Close"].iloc[-1]
            exit_date = future.index[-1]
            days_held = len(future)

        if exit_price is None:
            continue  # dati insufficienti a fine serie

        pnl_pct = (exit_price - entry) / entry * 100

        trades.append(dict(
            ticker=ticker, entry_date=entry_date, entry=entry, stop=stop,
            tp1=tp1, tp2=tp2, exit_date=exit_date, exit_price=exit_price,
            outcome=outcome, pnl_pct=round(pnl_pct, 2), days_held=days_held,
            volume_ratio=sig.volume_ratio, adx=sig.adx,
        ))

    return pd.DataFrame(trades)


def backtest_universe(price_data: dict, params: dict = None) -> pd.DataFrame:
    """Esegue il backtest su tutti i ticker forniti e concatena i risultati."""
    all_trades = []
    for ticker, df in price_data.items():
        t = backtest_ticker(ticker, df, params)
        if not t.empty:
            all_trades.append(t)
    if not all_trades:
        return pd.DataFrame()
    return pd.concat(all_trades, ignore_index=True)


def compute_stats(trades: pd.DataFrame) -> dict:
    """
    Calcola le statistiche chiave del backtest (sezione 6 della spec):
    win rate, expectancy, R:R realizzato medio.
    """
    if trades.empty:
        return dict(n_trades=0)

    wins = trades[trades["pnl_pct"] > 0]
    losses = trades[trades["pnl_pct"] <= 0]

    win_rate = len(wins) / len(trades) * 100
    avg_win = wins["pnl_pct"].mean() if not wins.empty else 0
    avg_loss = losses["pnl_pct"].mean() if not losses.empty else 0

    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    return dict(
        n_trades=len(trades),
        win_rate_pct=round(win_rate, 1),
        avg_win_pct=round(avg_win, 2),
        avg_loss_pct=round(avg_loss, 2),
        expectancy_pct=round(expectancy, 2),
        outcome_breakdown=trades["outcome"].value_counts().to_dict(),
    )
