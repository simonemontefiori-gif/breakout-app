"""
Screener "Inversione dopo forte ribasso" — strategia:
1. Titolo large cap (FTSE MIB / Nasdaq 100 / S&P 500) sceso pesantemente dal massimo
2. La discesa sta decelerando (rallentamento del momentum ribassista)
3. Il prezzo si avvicina/lateralizza vicino al POC (area di accumulo) — POC sotto il prezzo
4. Si forma una base (range stretto, pattern di inversione)
5. Rottura della base al rialzo con volume in conferma → SEGNALE
6. Solo segnali con R:R >= soglia minima (default 1:4) vengono proposti
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Optional

from indicators import (
    calc_poc, volume_ratio, calc_atr,
    calc_drawdown_pct, calc_deceleration, detect_base,
    recent_resistance_levels, calc_relative_strength,
    calc_distance_from_52w_low, days_since_breakout
)


@dataclass
class Signal:
    ticker: str
    stato: str
    prezzo: float
    poc: float
    drawdown_pct: float
    decelerazione: bool
    base_range_pct: Optional[float]
    volume_ratio: Optional[float]
    entry: Optional[float] = None
    stop: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    rr_tp1: Optional[float] = None
    rr_tp2: Optional[float] = None
    note: Optional[str] = None
    forza_relativa: Optional[float] = None
    distanza_minimo_52w: Optional[float] = None
    giorni_da_rottura: Optional[int] = None
    range_high: Optional[float] = None
    range_low: Optional[float] = None

    def to_dict(self):
        return asdict(self)


DEFAULT_PARAMS = dict(
    poc_lookback=60,
    drawdown_lookback=252,       # ~1 anno di borsa
    min_drawdown_pct=40.0,       # deve essere sceso almeno del 40% dal massimo
    decel_window=20,
    base_lookback=25,            # candele usate per definire la base/consolidamento
    max_base_range_pct=15.0,     # ampiezza massima della base per essere "consolidamento"
    vol_ma_period=20,
    vol_ratio_min=1.5,           # volume di conferma sulla rottura
    atr_period=14,
    atr_mult_stop=1.5,           # buffer sotto il minimo base per lo stop
    rr_min=4.0,                  # R:R minimo richiesto (1:4)
    n_resistance_levels=4,       # quante resistenze cercare per i target
    avvicinamento_pct=8.0,       # entro quanta % dalla base alta segnala "in avvicinamento"
)


def evaluate_ticker(ticker: str, df: pd.DataFrame, params: dict = None,
                     benchmark_df: pd.DataFrame = None) -> Optional[Signal]:
    p = {**DEFAULT_PARAMS, **(params or {})}

    min_len = max(p["drawdown_lookback"], p["poc_lookback"]) + 10
    if df is None or len(df) < min_len:
        return None

    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    price = float(df["Close"].iloc[-1])

    # 1. Drawdown dal massimo
    drawdown = calc_drawdown_pct(df, lookback=p["drawdown_lookback"])
    if np.isnan(drawdown) or drawdown < p["min_drawdown_pct"]:
        return None  # non è sceso abbastanza, fuori strategia

    # 2. Decelerazione della discesa
    decel = calc_deceleration(df, window=p["decel_window"])
    if not decel["decelerating"]:
        return None  # sta ancora accelerando al ribasso, troppo presto

    # 3. POC — deve stare sotto il prezzo attuale (area di supporto/accumulo)
    poc = calc_poc(df, lookback=p["poc_lookback"])
    if np.isnan(poc) or poc <= 0 or poc >= price * 1.02:
        return None  # POC non è sotto il prezzo, non è l'area di accumulo cercata

    # 4. Base/consolidamento recente
    base = detect_base(df, lookback=p["base_lookback"], max_range_pct=p["max_base_range_pct"])
    if not base.get("valid"):
        dist_to_poc = (price - poc) / poc * 100
        if 0 <= dist_to_poc <= p["avvicinamento_pct"]:
            return Signal(
                ticker=ticker, stato="IN AVVICINAMENTO", prezzo=round(price, 4),
                poc=round(poc, 4), drawdown_pct=round(drawdown, 1),
                decelerazione=True, base_range_pct=None, volume_ratio=None,
                note="Decelerazione confermata, base non ancora formata"
            )
        return None

    range_high, range_low = base["range_high"], base["range_low"]
    vol_ratio = volume_ratio(df, vol_ma_period=p["vol_ma_period"])

    # 5. Rottura della base al rialzo
    breakout_oggi = price > range_high
    volume_ok = (not np.isnan(vol_ratio)) and vol_ratio >= p["vol_ratio_min"]

    if not breakout_oggi:
        dist_to_high = (range_high - price) / price * 100
        stato = "VICINISSIMO" if dist_to_high <= 2.0 else "IN AVVICINAMENTO"
        if dist_to_high <= p["avvicinamento_pct"]:
            return Signal(
                ticker=ticker, stato=stato, prezzo=round(price, 4), poc=round(poc, 4),
                drawdown_pct=round(drawdown, 1), decelerazione=True,
                base_range_pct=base["range_pct"], volume_ratio=round(vol_ratio, 2) if not np.isnan(vol_ratio) else None,
                note=f"Base identificata {round(range_low,2)}-{round(range_high,2)}, in attesa di rottura"
            )
        return None

    if not volume_ok:
        return Signal(
            ticker=ticker, stato="ROTTURA SENZA VOLUME (attendere conferma)",
            prezzo=round(price, 4), poc=round(poc, 4), drawdown_pct=round(drawdown, 1),
            decelerazione=True, base_range_pct=base["range_pct"],
            volume_ratio=round(vol_ratio, 2) if not np.isnan(vol_ratio) else None,
            note="Rottura del pattern ma volume non in conferma — alto rischio falso breakout"
        )

    # --- Segnale CONFERMATO: calcolo parametri operativi ---
    entry = round(price * 1.003, 4)

    atr = calc_atr(df, period=p["atr_period"])
    stop_struct = range_low
    stop_atr = entry - p["atr_mult_stop"] * atr if not np.isnan(atr) else stop_struct
    stop = round(max(stop_struct, stop_atr) if stop_struct < entry else stop_struct, 4)

    risk = entry - stop
    if risk <= 0:
        return None

    resistances = recent_resistance_levels(df, lookback=p["drawdown_lookback"], n_levels=p["n_resistance_levels"])
    measured_move = range_high + (range_high - range_low)
    all_targets = sorted(set([t for t in resistances if t > entry] + [measured_move]))

    target_used, rr_used = None, None
    for t in all_targets:
        rr = (t - entry) / risk
        if rr >= p["rr_min"]:
            target_used, rr_used = t, round(rr, 2)
            break

    tp1 = round(all_targets[0], 4) if all_targets else None
    tp2 = round(all_targets[1], 4) if len(all_targets) > 1 else None
    rr_tp1 = round((tp1 - entry) / risk, 2) if tp1 else None
    rr_tp2 = round((tp2 - entry) / risk, 2) if tp2 else None

    if target_used is None:
        stato = "CONFERMATO (R:R insufficiente)"
        note = f"Nessun target disponibile raggiunge R:R {p['rr_min']}:1 — miglior R:R disponibile {max(rr_tp1 or 0, rr_tp2 or 0)}"
    else:
        stato = "CONFERMATO"
        note = f"Target selezionato {target_used} — R:R {rr_used}:1"

    rs = calc_relative_strength(df, benchmark_df) if benchmark_df is not None else None
    dist_52w_low = calc_distance_from_52w_low(df)
    days_breakout = days_since_breakout(df, range_high)

    return Signal(
        ticker=ticker, stato=stato, prezzo=round(price, 4), poc=round(poc, 4),
        drawdown_pct=round(drawdown, 1), decelerazione=True, base_range_pct=base["range_pct"],
        volume_ratio=round(vol_ratio, 2), entry=entry, stop=stop, tp1=tp1, tp2=tp2,
        rr_tp1=rr_tp1, rr_tp2=rr_tp2, note=note, forza_relativa=rs,
        distanza_minimo_52w=dist_52w_low, giorni_da_rottura=days_breakout,
        range_high=round(range_high, 4), range_low=round(range_low, 4),
    )


def scan_universe(price_data: dict, params: dict = None, benchmark_df: pd.DataFrame = None) -> pd.DataFrame:
    rows = []
    for ticker, df in price_data.items():
        try:
            sig = evaluate_ticker(ticker, df, params, benchmark_df=benchmark_df)
        except Exception as e:
            print(f"Errore valutazione {ticker}: {e}")
            sig = None
        if sig is not None:
            rows.append(sig.to_dict())

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    stato_order = {
        "CONFERMATO": 0,
        "CONFERMATO (R:R insufficiente)": 1,
        "ROTTURA SENZA VOLUME (attendere conferma)": 2,
        "VICINISSIMO": 3,
        "IN AVVICINAMENTO": 4,
    }
    result["_order"] = result["stato"].map(stato_order).fillna(9)
    result = result.sort_values(["_order", "drawdown_pct"], ascending=[True, False]).drop(columns="_order")
    return result.reset_index(drop=True)
