"""
Grafici interattivi (Plotly) per visualizzare i segnali: candlestick con
POC, base, entry/stop/target marcati — sfondo bianco, stile pulito.
"""

import plotly.graph_objects as go
import pandas as pd


COLORS = dict(
    up="#16a34a",       # verde
    down="#dc2626",     # rosso
    poc="#7c3aed",      # viola
    base="#fbbf24",     # ambra (area base)
    entry="#2563eb",    # blu
    stop="#dc2626",     # rosso
    tp="#16a34a",       # verde
    bg="#ffffff",
    grid="#e5e7eb",
    text="#1f2937",
)


def signal_chart(df: pd.DataFrame, signal: dict, lookback_days: int = 180) -> go.Figure:
    """
    Costruisce un grafico candlestick con:
    - linea POC (viola tratteggiata)
    - area base (banda ambra)
    - linee entry/stop/TP1/TP2
    """
    plot_df = df.tail(lookback_days).copy()

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=plot_df.index, open=plot_df["Open"], high=plot_df["High"],
        low=plot_df["Low"], close=plot_df["Close"],
        increasing_line_color=COLORS["up"], decreasing_line_color=COLORS["down"],
        name="Prezzo", showlegend=False,
    ))

    poc = signal.get("poc")
    if poc:
        fig.add_hline(y=poc, line_dash="dash", line_color=COLORS["poc"], line_width=1.5,
                       annotation_text=f"POC {poc}", annotation_position="right",
                       annotation_font_color=COLORS["poc"])

    range_high, range_low = signal.get("range_high"), signal.get("range_low")
    if range_high and range_low:
        fig.add_hrect(y0=range_low, y1=range_high, fillcolor=COLORS["base"], opacity=0.15,
                       line_width=0, annotation_text="Base", annotation_position="top left")

    level_specs = [
        ("entry", "Entry", COLORS["entry"]),
        ("stop", "Stop", COLORS["stop"]),
        ("tp1", "TP1", COLORS["tp"]),
        ("tp2", "TP2", COLORS["tp"]),
    ]
    for key, label, color in level_specs:
        val = signal.get(key)
        if val:
            fig.add_hline(y=val, line_dash="dot", line_color=color, line_width=1.5,
                           annotation_text=f"{label} {val}", annotation_position="left",
                           annotation_font_color=color)

    fig.update_layout(
        plot_bgcolor=COLORS["bg"], paper_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"], family="Arial, sans-serif"),
        xaxis=dict(gridcolor=COLORS["grid"], rangeslider_visible=False),
        yaxis=dict(gridcolor=COLORS["grid"], title="Prezzo"),
        margin=dict(l=10, r=10, t=30, b=10),
        height=420,
        title=dict(text=signal.get("ticker", ""), font=dict(size=18)),
    )
    return fig


def drawdown_gauge(drawdown_pct: float, min_required: float) -> go.Figure:
    """Piccolo indicatore visivo di quanto il drawdown supera la soglia minima richiesta."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=drawdown_pct,
        number={"suffix": "%", "font": {"color": COLORS["text"]}},
        gauge=dict(
            axis=dict(range=[0, max(80, drawdown_pct + 10)], tickcolor=COLORS["text"]),
            bar=dict(color=COLORS["down"]),
            steps=[
                dict(range=[0, min_required], color="#f3f4f6"),
                dict(range=[min_required, max(80, drawdown_pct + 10)], color="#fee2e2"),
            ],
            threshold=dict(line=dict(color=COLORS["poc"], width=3), value=min_required),
        ),
    ))
    fig.update_layout(paper_bgcolor=COLORS["bg"], height=180, margin=dict(l=20, r=20, t=10, b=10))
    return fig


def rr_bar_chart(signals_df) -> go.Figure:
    """Grafico a barre orizzontali del R:R di ogni segnale confermato, per confronto rapido."""
    if signals_df is None or signals_df.empty:
        return go.Figure()

    d = signals_df.copy()
    d["rr_display"] = d.apply(
        lambda r: r["rr_tp2"] if pd.notna(r.get("rr_tp2")) else r.get("rr_tp1"), axis=1
    )
    d = d.dropna(subset=["rr_display"]).sort_values("rr_display")

    fig = go.Figure(go.Bar(
        x=d["rr_display"], y=d["ticker"], orientation="h",
        marker_color=COLORS["tp"], text=d["rr_display"].round(2), textposition="outside",
    ))
    fig.update_layout(
        plot_bgcolor=COLORS["bg"], paper_bgcolor=COLORS["bg"],
        font=dict(color=COLORS["text"]),
        xaxis=dict(title="Risk:Reward", gridcolor=COLORS["grid"]),
        yaxis=dict(title=""),
        margin=dict(l=10, r=10, t=10, b=10),
        height=max(200, 35 * len(d)),
    )
    return fig
