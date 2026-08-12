# Screener Breakout POC — Guida rapida

App Streamlit che applica i criteri della spec (`spec_app_breakout_trading.md`) per filtrare i breakout con maggiore probabilità statistica di successo: conferma volume, filtro regime/trend (ADX + pendenza MM), struttura prezzo, R:R minimo.

## Cosa contiene

| File | Funzione |
|---|---|
| `indicators.py` | POC (volume profile), ADX, pendenza MM, struttura swing high/low |
| `screener.py` | Applica i criteri di ingresso e genera i segnali (IN AVVICINAMENTO / VICINISSIMO / CONFERMATO) |
| `data_fetch.py` | Recupero dati storici via yfinance |
| `backtest.py` | Motore di backtest — **da eseguire prima di usare i segnali con capitale reale** |
| `telegram_alerts.py` | Invio alert al bot Telegram esistente |
| `app.py` | App Streamlit (screener live + backtest) |

## 1. Test in locale (5 minuti)

```bash
pip install streamlit yfinance pandas numpy requests
streamlit run app.py
```

Si apre in automatico nel browser su `localhost:8501`.

## 2. Deploy gratuito su Streamlit Community Cloud (stesso hosting di dashboard_sfida.py)

1. Crea un repo GitHub con questi file + un `requirements.txt`:
   ```
   streamlit
   yfinance
   pandas
   numpy
   requests
   ```
2. Vai su [share.streamlit.io](https://share.streamlit.io), collega il repo GitHub
3. Seleziona `app.py` come file principale → Deploy
4. L'app è live gratis su un URL tipo `tuonome-app.streamlit.app`

## 3. Prima di usarlo per operare davvero

**Passo obbligatorio:** vai sulla tab "Backtest", esegui su almeno 2-3 anni di dati sull'universo che ti interessa (FTSE MIB, poi aggiungi S&P500/Nasdaq100/Stoxx600), e guarda:
- Win rate
- Expectancy media (deve essere positiva)
- Distribuzione esiti (quanti STOP vs TP1 vs TP2 vs TIMEOUT)

Se l'expectancy resta negativa anche con i filtri attivi, il problema non sono i parametri ma il metodo POC breakout stesso in quel regime di mercato — vale la pena saperlo prima, non dopo.

## 4. Estendere l'universo di ticker

`data_fetch.py` contiene solo una lista di esempio FTSE MIB. Per S&P 500 / Nasdaq 100 / Stoxx 600, il modo più robusto è:
- Scaricare la lista componenti da fonte ufficiale (es. pagina Wikipedia dell'indice, o file CSV holdings dell'ETF che già usi per il look-through)
- Salvarla come lista Python o CSV separato
- Passarla a `fetch_universe()` in `app.py`

## 5. Integrazione col bot Telegram esistente

In `telegram_alerts.py` trovi `send_signals(results_df, bot_token, chat_id)`. Basta richiamarla dopo `scan_universe()` usando lo stesso `bot_token`/`chat_id` che hai già configurato per le morning briefing, e schedularla (es. cron job su Railway/Fly.io) per girare dopo la chiusura di mercato — coerente col criterio "conferma su chiusura, non intraday" della spec.

## Note

- I filtri sono tutti parametrici (soglie volume, ADX, R:R minimo) e modificabili dalla sidebar dell'app senza toccare il codice
- Il backtest è vettorializzato per ticker singolo — su universi grandi (500+ titoli, anni di storico) può richiedere qualche minuto: normale
- yfinance a volte ha rate-limit o buchi nei dati per titoli meno liquidi; se noti dati mancanti, valuta una fonte a pagamento più affidabile (Twelve Data, Polygon.io) solo se il progetto scala
