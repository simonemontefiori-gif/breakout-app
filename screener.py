"""
Screener breakout: applica i criteri di ingresso definiti nella spec
e genera segnali con stato IN AVVICINAMENTO / VICINISSIMO / CONFERMATO.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional

from indicators import (
    calc_poc, calc_adx, calc_ma_slope, volume_ratio,
    swing_highs_decreasing, recent_swing_low, recent_resistance_levels
)


@dataclass
class Signal:
    ticker: str
    stato: str                  # IN AVVICINAMENTO / VICINISSIMO / CONFERMATO
    prezzo: float
    poc: float
    distanza_poc_pct: float
    volume_ratio: float
    adx: float
    ma_slope: float
    struttura_ribassista: bool
    entry: Optional[float] = None
    stop: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    rr_tp1: Optional[float] = None
    rr_tp2: Optional[float] = None
    size_note: Optional[str] = None

    def to_dict(self):
        return asdict(self)


# --- Soglie configurabili (personalizzabili da UI) ---
DEFAULT_PARAMS = dict(
    poc_lookback=60,
    vol_ma_period=20,
    vol_ratio_min=1.5,       # criterio 2.2
    adx_min=20,              # criterio 2.3
    ma_period=50,
    ma_slope_min=0.0,        # pendenza positiva
    swing_lookback_stop=10,  # per calcolo stop loss
    rr_tp2_min=1.5,          # criterio 4 - filtro R:R minimo
    avvicinamento_min_pct=2.0,
    avvicinamento_max_pct=5.0,
    vicinissimo_max_pct=1.0,
)


def evaluate_ticker(ticker: str, df: pd.DataFrame, params: dict = None) -> Optional[Signal]:
    """
    Valuta un singolo ticker sui criteri di breakout.
    df deve avere colonne: Open, High, Low, Close, Volume (index = date, ordine crescente).
    Ritorna un oggetto Signal oppure None se dati insufficienti.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}

    if df is None or len(df) < max(p["poc_lookback"], p["ma_period"]) + 10:
        return None

    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    price = float(df["Close"].iloc[-1])

    poc = calc_poc(df, lookback=p["poc_lookback"])
    if np.isnan(poc) or poc <= 0:
        return None

    dist_pct = (price - poc) / poc * 100
    vol_ratio = volume_ratio(df, vol_ma_period=p["vol_ma_period"])
    adx_series = calc_adx(df)
    adx_val = float(adx_series.iloc[-1]) if not adx_series.empty else np.nan
    ma_slope = calc_ma_slope(df, ma_period=p["ma_period"])
    struttura_ribassista = swing_highs_decreasing(df)

    # --- Determina stato ---
    stato = None
    if dist_pct < 0:
        # prezzo ancora sotto il POC
        dist_abs = abs(dist_pct)
        if p["avvicinamento_min_pct"] <= dist_abs <= p["avvicinamento_max_pct"]:
            stato = "IN AVVICINAMENTO"
        elif dist_abs < p["vicinissimo_max_pct"]:
            stato = "VICINISSIMO"
    else:
        # prezzo sopra il POC -> verifica se tutti i criteri di conferma sono soddisfatti
        criteri_ok = (
            (not np.isnan(vol_ratio)) and vol_ratio >= p["vol_ratio_min"] and
            (
                ((not np.isnan(adx_val)) and adx_val >= p["adx_min"]) or
                ((not np.isnan(ma_slope)) and ma_slope >= p["ma_slope_min"])
            ) and
            (not struttura_ribassista)
        )
        if criteri_ok:
            stato = "CONFERMATO"
        elif dist_pct < p["vicinissimo_max_pct"]:
            stato = "VICINISSIMO"  # rottura appena avvenuta ma non ancora confermata

    if stato is None:
        return None

    sig = Signal(
        ticker=ticker,
        stato=stato,
        prezzo=round(price, 4),
        poc=round(poc, 4),
        distanza_poc_pct=round(dist_pct, 2),
        volume_ratio=round(vol_ratio, 2) if not np.isnan(vol_ratio) else None,
        adx=round(adx_val, 2) if not np.isnan(adx_val) else None,
        ma_slope=round(ma_slope, 2) if not np.isnan(ma_slope) else None,
        struttura_ribassista=struttura_ribassista,
    )

    if stato == "CONFERMATO":
        entry = round(price * 1.003, 4)  # piccolo buffer di conferma
        stop = round(recent_swing_low(df, lookback=p["swing_lookback_stop"]), 4)
        resistances = recent_resistance_levels(df)

        tp1 = round(resistances[0], 4) if len(resistances) >= 1 else None
        tp2 = round(resistances[1], 4) if len(resistances) >= 2 else None

        risk = entry - stop
        rr_tp1 = round((tp1 - entry) / risk, 2) if tp1 and risk > 0 else None
        rr_tp2 = round((tp2 - entry) / risk, 2) if tp2 and risk > 0 else None

        # Filtro R:R minimo (criterio 4): declassa se non soddisfatto
        if rr_tp2 is not None and rr_tp2 < p["rr_tp2_min"]:
            sig.stato = "CONFERMATO (R:R insufficiente)"

        sig.entry, sig.stop, sig.tp1, sig.tp2 = entry, stop, tp1, tp2
        sig.rr_tp1, sig.rr_tp2 = rr_tp1, rr_tp2

    return sig


def scan_universe(price_data: dict, params: dict = None) -> pd.DataFrame:
    """
    price_data: dict {ticker: DataFrame OHLCV}
    Ritorna un DataFrame con tutti i segnali generati (stati != None), ordinato per rilevanza.
    """
    rows = []
    for ticker, df in price_data.items():
        sig = evaluate_ticker(ticker, df, params)
        if sig is not None:
            rows.append(sig.to_dict())

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    stato_order = {
        "CONFERMATO": 0,
        "CONFERMATO (R:R insufficiente)": 1,
        "VICINISSIMO": 2,
        "IN AVVICINAMENTO": 3,
    }
    result["_order"] = result["stato"].map(stato_order)
    result = result.sort_values(["_order", "distanza_poc_pct"]).drop(columns="_order")
    return result.reset_index(drop=True)
