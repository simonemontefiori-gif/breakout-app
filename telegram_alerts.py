"""
Invio alert Telegram per segnali CONFERMATO della strategia "Inversione dopo forte ribasso".
Da integrare con il bot Telegram già esistente (stesso token/chat_id in uso
per le morning briefing).
"""

import requests


def format_signal_message(sig: dict) -> str:
    if sig["stato"] != "CONFERMATO":
        return None

    lines = [
        f"🟢 INVERSIONE CONFERMATA — {sig['ticker']}",
        "",
        f"Prezzo attuale: {sig['prezzo']}",
        f"Drawdown dal massimo: -{sig['drawdown_pct']}%",
        f"POC: {sig['poc']}",
        f"Ampiezza base: {sig['base_range_pct']}%",
        f"Volume: {sig['volume_ratio']}x media 20gg",
        "",
        f"📍 Entry: {sig['entry']}",
        f"🛑 Stop: {sig['stop']}",
        f"🎯 TP1: {sig['tp1']} (R:R {sig['rr_tp1']})",
        f"🎯 TP2: {sig['tp2']} (R:R {sig['rr_tp2']})",
        "",
        f"{sig.get('note', '')}",
    ]
    return "\n".join(lines)


def send_telegram_message(bot_token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"Errore invio Telegram: {e}")
        return False


def send_signals(signals_df, bot_token: str, chat_id: str):
    if signals_df is None or signals_df.empty:
        return
    confermati = signals_df[signals_df["stato"] == "CONFERMATO"]
    for _, row in confermati.iterrows():
        msg = format_signal_message(row.to_dict())
        if msg:
            send_telegram_message(bot_token, chat_id, msg)
