"""
Modulo indicatori tecnici per lo screener breakout.
Calcola: POC (Point of Control) da volume profile, ADX, pendenza media mobile,
struttura massimi/minimi (swing highs/lows).
"""

import numpy as np
import pandas as pd


def calc_poc(df: pd.DataFrame, lookback: int = 60, n_bins: int = 40) -> float:
    """
    Calcola il Point of Control (prezzo con maggior volume scambiato)
    su un volume profile costruito sugli ultimi `lookback` periodi.

    df: DataFrame con colonne ['High', 'Low', 'Close', 'Volume']
    """
    window = df.tail(lookback).copy()
    if len(window) < 5:
        return np.nan

    price_min = window["Low"].min()
    price_max = window["High"].max()
    if price_max <= price_min:
        return np.nan

    bins = np.linspace(price_min, price_max, n_bins + 1)
    vol_per_bin = np.zeros(n_bins)

    # Distribuisce il volume di ogni candela in modo proporzionale
    # sui bin di prezzo che il range High-Low della candela attraversa.
    for _, row in window.iterrows():
        low, high, vol = row["Low"], row["High"], row["Volume"]
        if high <= low or vol == 0 or pd.isna(vol):
            continue
        bin_low = np.searchsorted(bins, low, side="right") - 1
        bin_high = np.searchsorted(bins, high, side="right") - 1
        bin_low = max(0, min(bin_low, n_bins - 1))
        bin_high = max(0, min(bin_high, n_bins - 1))
        span = bin_high - bin_low + 1
        vol_per_bin[bin_low:bin_high + 1] += vol / span

    poc_bin = int(np.argmax(vol_per_bin))
    poc_price = (bins[poc_bin] + bins[poc_bin + 1]) / 2
    return float(poc_price)


def calc_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calcola ADX (Average Directional Index) standard a `period` periodi."""
    high, low, close = df["High"], df["Low"], df["Close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean() / atr

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx


def calc_ma_slope(df: pd.DataFrame, ma_period: int = 50, slope_lookback: int = 8) -> float:
    """
    Pendenza della media mobile a `ma_period`, calcolata come variazione
    percentuale della MA sugli ultimi `slope_lookback` periodi.
    Positiva = MA in salita.
    """
    ma = df["Close"].rolling(ma_period).mean()
    if len(ma.dropna()) < slope_lookback + 1:
        return np.nan
    recent = ma.tail(slope_lookback)
    return float((recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0] * 100)


def volume_ratio(df: pd.DataFrame, vol_ma_period: int = 20) -> float:
    """Rapporto tra volume dell'ultima candela e la sua media mobile a `vol_ma_period`."""
    vol_ma = df["Volume"].rolling(vol_ma_period).mean()
    if pd.isna(vol_ma.iloc[-1]) or vol_ma.iloc[-1] == 0:
        return np.nan
    return float(df["Volume"].iloc[-1] / vol_ma.iloc[-1])


def swing_highs_decreasing(df: pd.DataFrame, n_swings: int = 3, order: int = 3) -> bool:
    """
    Verifica se gli ultimi `n_swings` massimi locali (swing high) sono decrescenti
    -> struttura ribassista ancora non invertita.
    `order`: numero di candele a sinistra/destra per definire un massimo locale.
    """
    highs = df["High"].values
    swing_idx = []
    for i in range(order, len(highs) - order):
        window = highs[i - order:i + order + 1]
        if highs[i] == window.max():
            swing_idx.append(i)

    if len(swing_idx) < n_swings:
        return False  # dati insufficienti, non blocca il segnale

    last_swings = [highs[i] for i in swing_idx[-n_swings:]]
    return all(last_swings[i] > last_swings[i + 1] for i in range(len(last_swings) - 1))


def recent_swing_low(df: pd.DataFrame, lookback: int = 10) -> float:
    """Minimo delle ultime `lookback` candele, usato come base per lo stop loss."""
    return float(df["Low"].tail(lookback).min())


def calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range - usato per calcolare stop loss più precisi/stretti."""
    high, low, close = df["High"], df["Low"], df["Close"]
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    if atr.empty or pd.isna(atr.iloc[-1]):
        return np.nan
    return float(atr.iloc[-1])


def calc_drawdown_pct(df: pd.DataFrame, lookback: int = 252) -> float:
    """
    Drawdown percentuale del prezzo attuale rispetto al massimo degli ultimi
    `lookback` periodi (default 252 = ~1 anno di borsa). Valore positivo = quanto
    il titolo è sceso dal massimo (es. 45 = -45% dal massimo).
    """
    window = df.tail(lookback)
    if window.empty:
        return np.nan
    high_period = window["High"].max()
    current = df["Close"].iloc[-1]
    if high_period <= 0:
        return np.nan
    return float((high_period - current) / high_period * 100)


def calc_deceleration(df: pd.DataFrame, window: int = 20) -> dict:
    """
    Confronta il tasso di variazione (ROC) del prezzo nella finestra recente
    vs quella precedente, per rilevare se la discesa sta rallentando.
    roc_recent più alto (meno negativo) di roc_prior = discesa in decelerazione.
    """
    close = df["Close"]
    if len(close) < window * 2 + 1:
        return dict(roc_recent=np.nan, roc_prior=np.nan, decelerating=False)

    recent = close.tail(window)
    prior = close.tail(window * 2).head(window)

    roc_recent = float((recent.iloc[-1] - recent.iloc[0]) / recent.iloc[0] * 100)
    roc_prior = float((prior.iloc[-1] - prior.iloc[0]) / prior.iloc[0] * 100)

    decelerating = roc_recent > roc_prior  # meno negativo = rallentamento della discesa
    return dict(roc_recent=round(roc_recent, 2), roc_prior=round(roc_prior, 2), decelerating=decelerating)


def calc_relative_strength(df: pd.DataFrame, benchmark_df: pd.DataFrame, window: int = 60) -> float:
    """
    Forza relativa rispetto a un benchmark (es. indice di riferimento) sugli ultimi
    `window` periodi. Valore positivo = il titolo sta recuperando più velocemente
    del mercato/indice; negativo = sta recuperando più lentamente (segnale più debole).
    """
    if benchmark_df is None or len(benchmark_df) < window or len(df) < window:
        return np.nan
    stock_ret = (df["Close"].iloc[-1] / df["Close"].iloc[-window] - 1) * 100
    bench_ret = (benchmark_df["Close"].iloc[-1] / benchmark_df["Close"].iloc[-window] - 1) * 100
    return round(float(stock_ret - bench_ret), 2)


def calc_distance_from_52w_low(df: pd.DataFrame, lookback: int = 252) -> float:
    """Distanza percentuale del prezzo attuale dal minimo delle ultime `lookback` candele."""
    window = df.tail(lookback)
    if window.empty:
        return np.nan
    low_period = window["Low"].min()
    current = df["Close"].iloc[-1]
    if low_period <= 0:
        return np.nan
    return round(float((current - low_period) / low_period * 100), 2)


def days_since_breakout(df: pd.DataFrame, range_high: float) -> int:
    """Quanti giorni fa il prezzo ha chiuso per la prima volta sopra range_high (utile per capire se il segnale è 'fresco')."""
    closes = df["Close"]
    above = closes > range_high
    if not above.any():
        return -1
    first_above_idx = above.idxmax()
    return int((df.index[-1] - first_above_idx).days)


def detect_base(df: pd.DataFrame, lookback: int = 25, exclude_today: bool = True,
                 max_range_pct: float = 15.0) -> dict:
    """
    Cerca una fase di lateralizzazione/base nelle ultime `lookback` candele
    (esclusa quella odierna, che potrebbe essere il giorno della rottura).
    Ritorna il massimo e il minimo della base se il range è abbastanza stretto
    da poter essere considerato consolidamento (non trend direzionale forte).
    """
    window = df.tail(lookback + 1)
    base_window = window.iloc[:-1] if exclude_today else window
    if len(base_window) < lookback * 0.6:
        return dict(valid=False)

    range_high = float(base_window["High"].max())
    range_low = float(base_window["Low"].min())
    if range_low <= 0:
        return dict(valid=False)

    range_pct = (range_high - range_low) / range_low * 100
    valid = range_pct <= max_range_pct

    return dict(valid=valid, range_high=range_high, range_low=range_low, range_pct=round(range_pct, 2))


def recent_resistance_levels(df: pd.DataFrame, lookback: int = 90, n_levels: int = 2) -> list:
    """
    Individua i massimi locali più rilevanti sopra il prezzo corrente
    negli ultimi `lookback` periodi, da usare come TP1/TP2.
    """
    window = df.tail(lookback)
    current_price = df["Close"].iloc[-1]
    highs = window["High"]

    local_maxima = []
    values = highs.values
    for i in range(2, len(values) - 2):
        if values[i] == values[i - 2:i + 3].max() and values[i] > current_price:
            local_maxima.append(values[i])

    local_maxima = sorted(set(local_maxima))
    return local_maxima[:n_levels] if local_maxima else []
